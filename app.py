import csv
import io
import mysql.connector
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, jsonify, abort, Response

app = Flask(__name__)
app.json.sort_keys = False


def conectar():
    # Servidor MySQL de XAMPP: usuario root y contrasena vacia
    return mysql.connector.connect(host="localhost", user="root", password="", database="hospital")


# ---------------------------------------------------------------------
# Filtros para mostrar datos en las plantillas
# ---------------------------------------------------------------------
@app.template_filter("fecha")
def formatoFecha(valor):
    # Muestra una fecha como dd/mm/aaaa (o un guion si esta vacia)
    if valor is None or valor == "":
        return "-"
    return valor.strftime("%d/%m/%Y")


@app.template_filter("kb")
def formatoKb(bytes):
    # Muestra un tamano en KB con un decimal
    return str(round(bytes / 1024, 1)) + " KB"


# ---------------------------------------------------------------------
# Funciones de apoyo
# ---------------------------------------------------------------------
def obtenerPerfiles(conexion):
    # Los perfiles validos salen del checklist guardado en la base de datos
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT perfil FROM checklist ORDER BY perfil")
    filas = cursor.fetchall()
    cursor.close()
    perfiles = []
    for fila in filas:
        perfiles.append(fila["perfil"])
    return perfiles


def validarEmpleado(datos, perfiles):
    # Devuelve el mensaje de error, o "" si los datos son correctos
    if datos["nombre"] == "" or datos["departamento"] == "" or datos["fechaIngreso"] == "":
        return "Todos los campos son obligatorios."
    if not datos["nombre"].replace(" ", "").isalpha():
        return "El nombre solo puede tener letras y espacios."
    if datos["perfil"] not in perfiles:
        return "Perfil no reconocido. Perfiles validos: " + ", ".join(perfiles)
    try:
        fecha = datetime.strptime(datos["fechaIngreso"], "%Y-%m-%d").date()
    except ValueError:
        return "La fecha de ingreso no es valida (formato AAAA-MM-DD)."
    if fecha > date.today():
        return "La fecha de ingreso no puede ser futura."
    return ""


def estadoArchivo(archivo, versionMaxima):
    # Regla del reto: cada version es vigente, vencida o version anterior
    if archivo["version"] < versionMaxima:
        return "version anterior"
    elif archivo["fechaVencimiento"] is not None and archivo["fechaVencimiento"] < date.today():
        return "vencido"
    else:
        return "vigente"


def obtenerDocumentos(conexion, empleadoId=None):
    # Documentos del expediente (JOIN de 3 tablas) con sus versiones subidas.
    # Si se manda empleadoId, solo trae los de ese empleado.
    cursor = conexion.cursor(dictionary=True)
    sqlDocumentos = ("SELECT d.id, d.empleadoId, e.nombre, e.perfil, e.departamento, "
                     "t.nombre AS documento, t.requiereVencimiento "
                     "FROM documentos d "
                     "JOIN empleados e ON e.id = d.empleadoId "
                     "JOIN tipos_documento t ON t.id = d.tipoDocumentoId ")
    # Los listados NO traen la columna contenido: solo los datos que se muestran
    sqlArchivos = ("SELECT a.id, a.documentoId, a.version, a.nombreOriginal, a.tamano, "
                   "a.fechaVencimiento, a.fechaSubida "
                   "FROM archivos a JOIN documentos d ON d.id = a.documentoId ")
    if empleadoId is None:
        cursor.execute(sqlDocumentos + "ORDER BY e.nombre, d.id")
        documentos = cursor.fetchall()
        cursor.execute(sqlArchivos + "ORDER BY a.documentoId, a.version DESC")
        archivos = cursor.fetchall()
    else:
        cursor.execute(sqlDocumentos + "WHERE d.empleadoId = %s ORDER BY d.id", (empleadoId,))
        documentos = cursor.fetchall()
        cursor.execute(sqlArchivos + "WHERE d.empleadoId = %s ORDER BY a.documentoId, a.version DESC",
                       (empleadoId,))
        archivos = cursor.fetchall()
    cursor.close()

    for documento in documentos:
        # Versiones de este documento, de la mas reciente a la mas antigua
        versiones = []
        for archivo in archivos:
            if archivo["documentoId"] == documento["id"]:
                versiones.append(archivo)

        if len(versiones) == 0:
            documento["estado"] = "pendiente"
            documento["actual"] = None
            documento["version"] = 0
        else:
            versionMaxima = versiones[0]["version"]
            for archivo in versiones:
                archivo["estado"] = estadoArchivo(archivo, versionMaxima)
            documento["actual"] = versiones[0]
            documento["estado"] = versiones[0]["estado"]
            documento["version"] = versionMaxima
        documento["versiones"] = versiones

    return documentos


def evaluarEstado(vigentes, subidos, requeridos):
    # Clasificacion del expediente con los archivos realmente subidos
    if subidos == 0:
        return "sin iniciar"
    elif vigentes < requeridos:
        return "incompleto"
    elif vigentes == requeridos:
        return "completo"
    else:
        return "error: documentos exceden el checklist"


def obtenerExpedientes(conexion):
    # Recorre todos los empleados y cuenta sus documentos vigentes y vencidos
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados ORDER BY nombre")
    empleados = cursor.fetchall()
    cursor.close()
    documentos = obtenerDocumentos(conexion)

    expedientes = []
    for empleado in empleados:
        requeridos = 0
        vigentes = 0
        vencidos = 0
        subidos = 0
        for documento in documentos:
            if documento["empleadoId"] == empleado["id"]:
                requeridos = requeridos + 1
                if documento["estado"] == "vigente":
                    vigentes = vigentes + 1
                    subidos = subidos + 1
                elif documento["estado"] == "vencido":
                    vencidos = vencidos + 1
                    subidos = subidos + 1

        expedientes.append({
            "id": empleado["id"],
            "nombre": empleado["nombre"],
            "perfil": empleado["perfil"],
            "departamento": empleado["departamento"],
            "fechaIngreso": empleado["fechaIngreso"],
            "documentosVigentes": vigentes,
            "documentosVencidos": vencidos,
            "documentosRequeridos": requeridos,
            "documentosPendientes": requeridos - vigentes,
            "estado": evaluarEstado(vigentes, subidos, requeridos)
        })

    return expedientes


# ---------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------
@app.route("/")
def inicio():
    return redirect("/empleados")


# CONSULTAR: listado de empleados con el estado de su expediente
# MEJORA (Carlos Campos): busqueda por texto en el nombre o el departamento
@app.route("/empleados")
def listarEmpleados():
    buscar = request.args.get("buscar", "").strip()
    conexion = conectar()
    expedientes = obtenerExpedientes(conexion)

    if buscar != "":
        # Los % son comodines de LIKE: buscan el texto en cualquier parte.
        # El texto del usuario va como parametro %s, nunca pegado al SQL.
        patron = "%" + buscar + "%"
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id FROM empleados WHERE nombre LIKE %s OR departamento LIKE %s",
                       (patron, patron))
        filas = cursor.fetchall()
        cursor.close()

        idsEncontrados = []
        for fila in filas:
            idsEncontrados.append(fila["id"])

        # Solo se dejan los expedientes de los empleados encontrados
        encontrados = []
        for expediente in expedientes:
            if expediente["id"] in idsEncontrados:
                encontrados.append(expediente)
        expedientes = encontrados

    conexion.close()
    return render_template("empleados.html", expedientes=expedientes, buscar=buscar)


# REGISTRAR: formulario para registrar un empleado
@app.route("/empleados/nuevo", methods=["GET", "POST"])
def registrarEmpleado():
    conexion = conectar()
    perfiles = obtenerPerfiles(conexion)
    error = ""
    datos = {"nombre": "", "perfil": "", "departamento": "", "fechaIngreso": ""}

    if request.method == "POST":
        datos["nombre"] = request.form.get("nombre", "").strip()
        datos["perfil"] = request.form.get("perfil", "").strip().lower()
        datos["departamento"] = request.form.get("departamento", "").strip()
        datos["fechaIngreso"] = request.form.get("fechaIngreso", "").strip()

        # 1. Validar los datos del empleado
        error = validarEmpleado(datos, perfiles)

        # 2. Si no hay error, guardar el empleado (padre) y despues su expediente (hijos)
        if error == "":
            cursor = conexion.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO empleados (nombre, perfil, departamento, fechaIngreso) VALUES (%s, %s, %s, %s)",
                (datos["nombre"], datos["perfil"], datos["departamento"], datos["fechaIngreso"])
            )
            # id que MySQL le dio al empleado nuevo: es la llave foranea de sus documentos
            empleadoId = cursor.lastrowid

            # Un documento por cada tipo de documento del checklist de su perfil
            cursor.execute("SELECT tipoDocumentoId FROM checklist WHERE perfil = %s ORDER BY id",
                           (datos["perfil"],))
            checklist = cursor.fetchall()
            for fila in checklist:
                cursor.execute("INSERT INTO documentos (empleadoId, tipoDocumentoId) VALUES (%s, %s)",
                               (empleadoId, fila["tipoDocumentoId"]))

            conexion.commit()
            cursor.close()
            conexion.close()
            return redirect("/empleados/" + str(empleadoId))

    conexion.close()
    return render_template("nuevo.html", error=error, datos=datos, perfiles=perfiles)


# CONSULTAR un expediente: documentos de un empleado con todas sus versiones
@app.route("/empleados/<int:empleadoId>")
def verExpediente(empleadoId):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados WHERE id = %s", (empleadoId,))
    empleado = cursor.fetchone()
    cursor.close()
    if empleado is None:
        conexion.close()
        abort(404)

    documentos = obtenerDocumentos(conexion, empleadoId)
    conexion.close()

    vigentes = 0
    vencidos = 0
    for documento in documentos:
        if documento["estado"] == "vigente":
            vigentes = vigentes + 1
        elif documento["estado"] == "vencido":
            vencidos = vencidos + 1
    estado = evaluarEstado(vigentes, vigentes + vencidos, len(documentos))

    if len(documentos) > 0:
        avance = round(vigentes * 100 / len(documentos))
    else:
        avance = 0

    return render_template("expediente.html", empleado=empleado, documentos=documentos,
                           vigentes=vigentes, vencidos=vencidos, estado=estado, avance=avance)


# LISTADO DE ARCHIVOS: todas las versiones subidas, de la mas reciente a la mas antigua
@app.route("/archivos")
def listarArchivos():
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute(
        "SELECT a.id, a.documentoId, a.version, a.nombreOriginal, a.tamano, a.fechaVencimiento, "
        "a.fechaSubida, e.id AS empleadoId, e.nombre, t.nombre AS documento "
        "FROM archivos a "
        "JOIN documentos d ON d.id = a.documentoId "
        "JOIN empleados e ON e.id = d.empleadoId "
        "JOIN tipos_documento t ON t.id = d.tipoDocumentoId "
        "ORDER BY e.nombre, d.id, a.version DESC"
    )
    filas = cursor.fetchall()
    cursor.close()
    conexion.close()

    # Version mas alta de cada documento
    maximas = {}
    for fila in filas:
        if fila["documentoId"] not in maximas or fila["version"] > maximas[fila["documentoId"]]:
            maximas[fila["documentoId"]] = fila["version"]

    # Estado de cada version y contadores
    vigentes = 0
    vencidos = 0
    anteriores = 0
    for fila in filas:
        fila["estado"] = estadoArchivo(fila, maximas[fila["documentoId"]])
        if fila["estado"] == "vigente":
            vigentes = vigentes + 1
        elif fila["estado"] == "vencido":
            vencidos = vencidos + 1
        else:
            anteriores = anteriores + 1

    # MEJORA (Italo Vidaurre) adaptada a los archivos: filtro por estado del documento
    filtro = request.args.get("estado", "")
    if filtro not in ["vigente", "vencido", "version anterior"]:
        filtro = ""
    mostrados = []
    for fila in filas:
        if filtro == "" or fila["estado"] == filtro:
            mostrados.append(fila)

    return render_template("archivos.html", archivos=mostrados, total=len(filas), vigentes=vigentes,
                           vencidos=vencidos, anteriores=anteriores, filtro=filtro)


# CONSULTA CON JOIN: todos los empleados con cada uno de sus documentos y su estado
@app.route("/documentos")
def listarDocumentos():
    conexion = conectar()
    documentos = obtenerDocumentos(conexion)
    conexion.close()

    vigentes = 0
    vencidos = 0
    pendientes = 0
    for documento in documentos:
        if documento["estado"] == "vigente":
            vigentes = vigentes + 1
        elif documento["estado"] == "vencido":
            vencidos = vencidos + 1
        else:
            pendientes = pendientes + 1

    return render_template("documentos.html", documentos=documentos, vigentes=vigentes,
                           vencidos=vencidos, pendientes=pendientes)


# MEJORA (Majo Guirola): exportar a CSV el listado con JOIN de empleados y documentos
@app.route("/documentos/csv")
def exportarCsv():
    conexion = conectar()
    documentos = obtenerDocumentos(conexion)
    conexion.close()

    # Se escribe el CSV en memoria: primero los encabezados y luego una fila por documento
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["Empleado", "Perfil", "Departamento", "Documento", "Estado", "Version actual"])
    for documento in documentos:
        escritor.writerow([documento["nombre"], documento["perfil"], documento["departamento"],
                           documento["documento"], documento["estado"], documento["version"]])

    # utf-8-sig hace que Excel muestre bien las tildes
    return Response(salida.getvalue().encode("utf-8-sig"), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=expedientes.csv"})


# Ruta JSON de la Fase 1, ahora leyendo el expediente desde MySQL
@app.route("/api/expediente/<int:empleadoId>")
def expedienteJson(empleadoId):
    conexion = conectar()
    expedientes = obtenerExpedientes(conexion)
    conexion.close()
    for expediente in expedientes:
        if expediente["id"] == empleadoId:
            expediente["fechaIngreso"] = str(expediente["fechaIngreso"])
            return jsonify(expediente)
    return jsonify({"error": "empleado no encontrado"}), 404


# ELIMINAR: borra el empleado. Por el ON DELETE CASCADE se borran sus
# documentos y, en cadena, todos sus archivos: no quedan huerfanos.
@app.route("/empleados/eliminar/<int:empleadoId>", methods=["POST"])
def eliminarEmpleado(empleadoId):
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM empleados WHERE id = %s", (empleadoId,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect("/empleados")


# RESUMEN: recorre todos los expedientes y cuenta cuantos hay de cada estado
@app.route("/resumen")
def resumen():
    conexion = conectar()
    expedientes = obtenerExpedientes(conexion)
    conexion.close()

    completos = 0
    incompletos = 0
    sinIniciar = 0
    conVencidos = 0

    for expediente in expedientes:
        if expediente["estado"] == "completo":
            completos = completos + 1
        elif expediente["estado"] == "incompleto":
            incompletos = incompletos + 1
        else:
            sinIniciar = sinIniciar + 1
        if expediente["documentosVencidos"] > 0:
            conVencidos = conVencidos + 1

    # MEJORA (Italo Vidaurre): filtro por clasificacion.
    # Los contadores siempre cuentan a todos; la tabla muestra solo la clasificacion elegida.
    filtro = request.args.get("estado", "")
    if filtro not in ["completo", "incompleto", "sin iniciar"]:
        filtro = ""

    mostrados = []
    for expediente in expedientes:
        if filtro == "" or expediente["estado"] == filtro:
            mostrados.append(expediente)

    return render_template("resumen.html", expedientes=mostrados, total=len(expedientes),
                           completos=completos, incompletos=incompletos, sinIniciar=sinIniciar,
                           conVencidos=conVencidos, filtro=filtro)


# MEJORA (Diego Diaz): segundo reporte con contadores y acumuladores por departamento
@app.route("/reporte/departamentos")
def reporteDepartamentos():
    conexion = conectar()
    expedientes = obtenerExpedientes(conexion)
    conexion.close()

    departamentos = {}
    for expediente in expedientes:
        nombre = expediente["departamento"]
        # Si es la primera vez que aparece el departamento, se crean sus contadores en 0
        if nombre not in departamentos:
            departamentos[nombre] = {"departamento": nombre, "empleados": 0, "completos": 0,
                                     "incompletos": 0, "sinIniciar": 0,
                                     "entregados": 0, "requeridos": 0}
        datos = departamentos[nombre]

        # Contadores
        datos["empleados"] = datos["empleados"] + 1
        if expediente["estado"] == "completo":
            datos["completos"] = datos["completos"] + 1
        elif expediente["estado"] == "incompleto":
            datos["incompletos"] = datos["incompletos"] + 1
        else:
            datos["sinIniciar"] = datos["sinIniciar"] + 1

        # Acumuladores
        datos["entregados"] = datos["entregados"] + expediente["documentosVigentes"]
        datos["requeridos"] = datos["requeridos"] + expediente["documentosRequeridos"]

    # Porcentaje de avance de cada departamento
    filas = []
    totalEntregados = 0
    totalRequeridos = 0
    for nombre in sorted(departamentos):
        datos = departamentos[nombre]
        if datos["requeridos"] > 0:
            datos["avance"] = round(datos["entregados"] * 100 / datos["requeridos"])
        else:
            datos["avance"] = 0
        totalEntregados = totalEntregados + datos["entregados"]
        totalRequeridos = totalRequeridos + datos["requeridos"]
        filas.append(datos)

    avanceGeneral = 0
    if totalRequeridos > 0:
        avanceGeneral = round(totalEntregados * 100 / totalRequeridos)

    return render_template("reporte_departamentos.html", filas=filas,
                           totalEntregados=totalEntregados, totalRequeridos=totalRequeridos,
                           avanceGeneral=avanceGeneral)


# El servidor se inicia al final, despues de definir TODAS las rutas
if __name__ == "__main__":
    app.run(debug=True)
