import csv
import io
import mysql.connector
from datetime import date, datetime
from flask import (Flask, render_template, request, redirect, jsonify, abort, Response,
                   send_file, flash)

app = Flask(__name__)
app.json.sort_keys = False
# La clave secreta la necesita flash() para mostrar mensajes entre paginas
app.secret_key = "expedientes-digitales-tarea3"

# Reglas de los archivos que se pueden subir
EXTENSIONES_PERMITIDAS = [".pdf", ".doc", ".docx"]
# El MySQL de XAMPP trae max_allowed_packet = 1M. Con 500 KB el archivo
# siempre cabe en la sentencia INSERT sin cortar la conexion.
TAMANO_MAXIMO_KB = 500
TAMANO_MAXIMO = TAMANO_MAXIMO_KB * 1024


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


def validarArchivo(archivo):
    # Revisa el archivo recibido con request.files.
    # Devuelve (error, nombreOriginal, contenido). Si error no es "", no se guarda nada.
    if archivo is None or archivo.filename == "":
        return "Elija un archivo para subir.", "", None

    # Nombre original sin la ruta de la carpeta (algunos navegadores la envian)
    nombreOriginal = archivo.filename.replace("\\", "/").split("/")[-1]
    if len(nombreOriginal) > 255:
        return "El nombre del archivo es demasiado largo (maximo 255 caracteres).", "", None

    # La extension se compara en minusculas: .PDF y .pdf son validas
    extensionValida = False
    for extension in EXTENSIONES_PERMITIDAS:
        if nombreOriginal.lower().endswith(extension):
            extensionValida = True
    if not extensionValida:
        return "Tipo de archivo no permitido. Solo se aceptan PDF o Word (.pdf, .doc, .docx).", "", None

    contenido = archivo.read()
    if len(contenido) == 0:
        return "El archivo esta vacio (0 bytes).", "", None
    if len(contenido) > TAMANO_MAXIMO:
        return ("El archivo pesa " + formatoKb(len(contenido)) + " y el maximo permitido es "
                + str(TAMANO_MAXIMO_KB) + " KB."), "", None
    return "", nombreOriginal, contenido


def validarVencimiento(texto, requiereVencimiento):
    # Devuelve (error, fecha). La fecha es None si el documento no la necesita.
    if texto == "":
        if requiereVencimiento:
            return "La fecha de vencimiento es obligatoria para este documento.", None
        return "", None
    try:
        fecha = datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        return "La fecha de vencimiento no es valida (formato AAAA-MM-DD).", None
    if fecha.year < 2000 or fecha.year > 2100:
        return "La fecha de vencimiento esta fuera de rango.", None
    return "", fecha


def guardarArchivo(cursor, documentoId, nombreOriginal, contenido, fechaVencimiento):
    # Nunca reemplaza: calcula la version siguiente y guarda un registro nuevo
    cursor.execute("SELECT MAX(version) AS ultima FROM archivos WHERE documentoId = %s", (documentoId,))
    fila = cursor.fetchone()
    if fila["ultima"] is None:
        version = 1
    else:
        version = fila["ultima"] + 1
    cursor.execute(
        "INSERT INTO archivos (documentoId, version, nombreOriginal, tamano, contenido, fechaVencimiento) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (documentoId, version, nombreOriginal, len(contenido), contenido, fechaVencimiento)
    )
    return version


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
# MEJORA (Carlos Campos): busqueda por nombre, departamento o nombre de archivo
@app.route("/empleados")
def listarEmpleados():
    buscar = request.args.get("buscar", "").strip()
    conexion = conectar()
    expedientes = obtenerExpedientes(conexion)

    if buscar != "":
        # Los % son comodines de LIKE: buscan el texto en cualquier parte.
        # El texto del usuario va como parametro %s, nunca pegado al SQL.
        # LEFT JOIN: tambien aparecen empleados que todavia no tienen archivos.
        patron = "%" + buscar + "%"
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            "SELECT DISTINCT e.id FROM empleados e "
            "LEFT JOIN documentos d ON d.empleadoId = e.id "
            "LEFT JOIN archivos a ON a.documentoId = d.id "
            "WHERE e.nombre LIKE %s OR e.departamento LIKE %s OR a.nombreOriginal LIKE %s",
            (patron, patron, patron)
        )
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


# REGISTRAR: formulario para registrar un empleado (y, si se quiere, subir su DUI)
@app.route("/empleados/nuevo", methods=["GET", "POST"])
def registrarEmpleado():
    conexion = conectar()
    perfiles = obtenerPerfiles(conexion)
    error = ""
    datos = {"nombre": "", "perfil": "", "departamento": "", "fechaIngreso": "", "venceDui": ""}

    if request.method == "POST":
        datos["nombre"] = request.form.get("nombre", "").strip()
        datos["perfil"] = request.form.get("perfil", "").strip().lower()
        datos["departamento"] = request.form.get("departamento", "").strip()
        datos["fechaIngreso"] = request.form.get("fechaIngreso", "").strip()
        datos["venceDui"] = request.form.get("venceDui", "").strip()
        archivoDui = request.files.get("archivoDui")

        # 1. Validar los datos del empleado
        error = validarEmpleado(datos, perfiles)

        # 2. El DUI es opcional al registrar; si se eligio un archivo, se valida
        subirDui = archivoDui is not None and archivoDui.filename != ""
        if error == "" and subirDui:
            error, nombreDui, contenidoDui = validarArchivo(archivoDui)
            if error == "":
                error, fechaDui = validarVencimiento(datos["venceDui"], True)

        # 3. Si no hay error, guardar el empleado (padre) y despues su expediente (hijos)
        if error == "":
            cursor = conexion.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO empleados (nombre, perfil, departamento, fechaIngreso) VALUES (%s, %s, %s, %s)",
                (datos["nombre"], datos["perfil"], datos["departamento"], datos["fechaIngreso"])
            )
            # id que MySQL le dio al empleado nuevo: es la llave foranea de sus documentos
            empleadoId = cursor.lastrowid

            cursor.execute("SELECT tipoDocumentoId FROM checklist WHERE perfil = %s ORDER BY id",
                           (datos["perfil"],))
            checklist = cursor.fetchall()
            for fila in checklist:
                cursor.execute("INSERT INTO documentos (empleadoId, tipoDocumentoId) VALUES (%s, %s)",
                               (empleadoId, fila["tipoDocumentoId"]))

            if subirDui:
                cursor.execute(
                    "SELECT d.id FROM documentos d JOIN tipos_documento t ON t.id = d.tipoDocumentoId "
                    "WHERE d.empleadoId = %s AND t.nombre = %s", (empleadoId, "DUI"))
                documentoDui = cursor.fetchone()
                if documentoDui is not None:
                    guardarArchivo(cursor, documentoDui["id"], nombreDui, contenidoDui, fechaDui)

            conexion.commit()
            cursor.close()
            conexion.close()
            flash("Empleado " + datos["nombre"] + " registrado correctamente.", "exito")
            return redirect("/empleados/" + str(empleadoId))

    conexion.close()
    return render_template("nuevo.html", error=error, datos=datos, perfiles=perfiles,
                           tamanoMaximo=TAMANO_MAXIMO_KB)


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


# MODIFICAR: editar los datos de un empleado (el perfil no cambia porque define su checklist)
@app.route("/empleados/editar/<int:empleadoId>", methods=["GET", "POST"])
def editarEmpleado(empleadoId):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados WHERE id = %s", (empleadoId,))
    empleado = cursor.fetchone()
    if empleado is None:
        cursor.close()
        conexion.close()
        abort(404)

    error = ""
    datos = {"nombre": empleado["nombre"], "perfil": empleado["perfil"],
             "departamento": empleado["departamento"], "fechaIngreso": str(empleado["fechaIngreso"])}

    if request.method == "POST":
        datos["nombre"] = request.form.get("nombre", "").strip()
        datos["departamento"] = request.form.get("departamento", "").strip()
        datos["fechaIngreso"] = request.form.get("fechaIngreso", "").strip()
        error = validarEmpleado(datos, [empleado["perfil"]])
        if error == "":
            cursor.execute(
                "UPDATE empleados SET nombre = %s, departamento = %s, fechaIngreso = %s WHERE id = %s",
                (datos["nombre"], datos["departamento"], datos["fechaIngreso"], empleadoId)
            )
            conexion.commit()
            cursor.close()
            conexion.close()
            flash("Datos de " + datos["nombre"] + " actualizados.", "exito")
            return redirect("/empleados/" + str(empleadoId))

    cursor.close()
    conexion.close()
    return render_template("editar_empleado.html", empleado=empleado, datos=datos, error=error)


# SUBIR ARCHIVO: formulario con enctype multipart/form-data.
# Cada subida crea una version nueva; las anteriores se conservan.
@app.route("/empleados/<int:empleadoId>/subir", methods=["GET", "POST"])
def subirArchivo(empleadoId):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados WHERE id = %s", (empleadoId,))
    empleado = cursor.fetchone()
    cursor.close()
    if empleado is None:
        conexion.close()
        abort(404)

    documentos = obtenerDocumentos(conexion, empleadoId)
    error = ""
    documentoElegido = request.args.get("documento", "")
    fechaVencimiento = ""

    if request.method == "POST":
        documentoElegido = request.form.get("documentoId", "")
        fechaVencimiento = request.form.get("fechaVencimiento", "").strip()
        archivo = request.files.get("archivo")

        # 1. El tipo de documento debe ser uno del expediente de este empleado
        documento = None
        for opcion in documentos:
            if str(opcion["id"]) == documentoElegido:
                documento = opcion
        if documento is None:
            error = "Elija el tipo de documento que va a subir."

        # 2. Validar el archivo (elegido, extension, vacio y tamano)
        if error == "":
            error, nombreOriginal, contenido = validarArchivo(archivo)

        # 3. Validar la fecha de vencimiento (obligatoria para el DUI)
        if error == "":
            error, fecha = validarVencimiento(fechaVencimiento, documento["requiereVencimiento"])

        # 4. Solo si todo esta bien se guarda en MySQL
        if error == "":
            cursor = conexion.cursor(dictionary=True)
            try:
                version = guardarArchivo(cursor, documento["id"], nombreOriginal, contenido, fecha)
                conexion.commit()
            except mysql.connector.Error:
                version = 0
                error = ("MySQL no pudo guardar el archivo. Revise que max_allowed_packet "
                         "en my.ini de XAMPP sea mayor que el archivo.")
            cursor.close()
            if error == "":
                conexion.close()
                flash(documento["documento"] + ": se guardo la version " + str(version) +
                      " (" + nombreOriginal + ").", "exito")
                return redirect("/empleados/" + str(empleadoId))

    conexion.close()
    return render_template("subir.html", empleado=empleado, documentos=documentos, error=error,
                           documentoElegido=documentoElegido, fechaVencimiento=fechaVencimiento,
                           tamanoMaximo=TAMANO_MAXIMO_KB)


# DESCARGA: busca el archivo por id y lo devuelve con su nombre original
@app.route("/archivos/<int:archivoId>/descargar")
def descargarArchivo(archivoId):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    # Esta es la unica consulta que trae la columna contenido
    cursor.execute("SELECT nombreOriginal, contenido FROM archivos WHERE id = %s", (archivoId,))
    archivo = cursor.fetchone()
    cursor.close()
    conexion.close()
    if archivo is None:
        abort(404)
    return send_file(io.BytesIO(archivo["contenido"]), download_name=archivo["nombreOriginal"],
                     as_attachment=True)


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


# MEJORA (Majo Guirola): exportar a CSV el listado con JOIN, ahora con los datos del archivo
@app.route("/documentos/csv")
def exportarCsv():
    conexion = conectar()
    documentos = obtenerDocumentos(conexion)
    conexion.close()

    # Se escribe el CSV en memoria: primero los encabezados y luego una fila por documento
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["Empleado", "Perfil", "Departamento", "Documento", "Estado", "Version actual",
                       "Archivo", "Fecha de vencimiento", "Fecha de subida"])
    for documento in documentos:
        actual = documento["actual"]
        if actual is None:
            archivo = ""
            vence = ""
            subida = ""
        else:
            archivo = actual["nombreOriginal"]
            vence = actual["fechaVencimiento"] or ""
            subida = actual["fechaSubida"]
        escritor.writerow([documento["nombre"], documento["perfil"], documento["departamento"],
                           documento["documento"], documento["estado"], documento["version"],
                           archivo, vence, subida])

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
    flash("Empleado eliminado junto con su expediente y sus archivos.", "exito")
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


# Pagina para cuando un empleado o un archivo no existe
@app.errorhandler(404)
def noEncontrado(error):
    return render_template("404.html"), 404


# El servidor se inicia al final, despues de definir TODAS las rutas
if __name__ == "__main__":
    app.run(debug=True)
