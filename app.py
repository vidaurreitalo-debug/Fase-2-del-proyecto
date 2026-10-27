import mysql.connector
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, jsonify, abort

app = Flask(__name__)
app.json.sort_keys = False


def conectar():
    # Servidor MySQL de XAMPP: usuario root y contrasena vacia
    return mysql.connector.connect(host="localhost", user="root", password="", database="hospital")


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


def obtenerRequeridos(conexion, perfil):
    # Numero de documentos del checklist del perfil (0 si el perfil no existe)
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total FROM checklist WHERE perfil = %s", (perfil,))
    fila = cursor.fetchone()
    cursor.close()
    return fila["total"]


def evaluarEstado(documentosEntregados, documentosRequeridos):
    # Misma decision de la Fase 1, ahora con los datos de MySQL
    if documentosEntregados == 0:
        return "sin iniciar"
    elif documentosEntregados < documentosRequeridos:
        return "incompleto"
    elif documentosEntregados == documentosRequeridos:
        return "completo"
    else:
        return "error: documentos exceden el checklist"


def obtenerExpedientes(conexion):
    # Recorre todos los empleados y cuenta sus documentos entregados
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados ORDER BY nombre")
    empleados = cursor.fetchall()
    expedientes = []

    for empleado in empleados:
        cursor.execute("SELECT estado FROM documentos WHERE empleadoId = %s", (empleado["id"],))
        documentos = cursor.fetchall()

        documentosEntregados = 0
        for documento in documentos:
            if documento["estado"] == "entregado":
                documentosEntregados = documentosEntregados + 1

        documentosRequeridos = obtenerRequeridos(conexion, empleado["perfil"])

        expedientes.append({
            "id": empleado["id"],
            "nombre": empleado["nombre"],
            "perfil": empleado["perfil"],
            "departamento": empleado["departamento"],
            "fechaIngreso": str(empleado["fechaIngreso"]),
            "documentosEntregados": documentosEntregados,
            "documentosRequeridos": documentosRequeridos,
            "documentosPendientes": documentosRequeridos - documentosEntregados,
            "estado": evaluarEstado(documentosEntregados, documentosRequeridos)
        })

    cursor.close()
    return expedientes


@app.route("/")
def inicio():
    return redirect("/empleados")


# CONSULTAR: listado de empleados con el estado de su expediente
@app.route("/empleados")
def listarEmpleados():
    conexion = conectar()
    expedientes = obtenerExpedientes(conexion)
    conexion.close()
    return render_template("empleados.html", expedientes=expedientes)


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

        # 1. Validar los datos antes de guardar
        if datos["nombre"] == "" or datos["departamento"] == "" or datos["fechaIngreso"] == "":
            error = "Todos los campos son obligatorios."
        elif not datos["nombre"].replace(" ", "").isalpha():
            error = "El nombre solo puede tener letras y espacios."
        elif datos["perfil"] not in perfiles:
            error = "Perfil no reconocido. Perfiles validos: " + ", ".join(perfiles)
        else:
            try:
                fecha = datetime.strptime(datos["fechaIngreso"], "%Y-%m-%d").date()
                if fecha > date.today():
                    error = "La fecha de ingreso no puede ser futura."
            except ValueError:
                error = "La fecha de ingreso no es valida (formato AAAA-MM-DD)."

        # 2. Si no hay error, guardar el empleado (padre) y despues su expediente (hijos)
        if error == "":
            cursor = conexion.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO empleados (nombre, perfil, departamento, fechaIngreso) VALUES (%s, %s, %s, %s)",
                (datos["nombre"], datos["perfil"], datos["departamento"], datos["fechaIngreso"])
            )
            # id que MySQL le dio al empleado nuevo: es la llave foranea de sus documentos
            empleadoId = cursor.lastrowid

            cursor.execute("SELECT documento FROM checklist WHERE perfil = %s ORDER BY id", (datos["perfil"],))
            checklist = cursor.fetchall()
            for fila in checklist:
                cursor.execute(
                    "INSERT INTO documentos (empleadoId, documento, estado, version, fechaActualizacion) VALUES (%s, %s, %s, %s, %s)",
                    (empleadoId, fila["documento"], "pendiente", 0, None)
                )

            conexion.commit()
            cursor.close()
            conexion.close()
            return redirect("/empleados")

    conexion.close()
    return render_template("nuevo.html", error=error, datos=datos, perfiles=perfiles)


# CONSULTAR un expediente: documentos de un empleado
@app.route("/empleados/<int:empleadoId>")
def verExpediente(empleadoId):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados WHERE id = %s", (empleadoId,))
    empleado = cursor.fetchone()
    if empleado is None:
        cursor.close()
        conexion.close()
        abort(404)

    cursor.execute("SELECT * FROM documentos WHERE empleadoId = %s ORDER BY id", (empleadoId,))
    documentos = cursor.fetchall()
    cursor.close()
    conexion.close()

    documentosEntregados = 0
    for documento in documentos:
        if documento["estado"] == "entregado":
            documentosEntregados = documentosEntregados + 1
    estado = evaluarEstado(documentosEntregados, len(documentos))

    return render_template("expediente.html", empleado=empleado, documentos=documentos,
                           documentosEntregados=documentosEntregados, estado=estado)


# CONSULTA CON JOIN: todos los empleados con cada uno de sus documentos y su estado
@app.route("/documentos")
def listarDocumentos():
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute(
        "SELECT e.id AS empleadoId, e.nombre, e.perfil, e.departamento, "
        "d.id, d.documento, d.estado, d.version, d.fechaActualizacion "
        "FROM empleados e JOIN documentos d ON d.empleadoId = e.id "
        "ORDER BY e.nombre, d.id"
    )
    filas = cursor.fetchall()
    cursor.close()
    conexion.close()

    entregados = 0
    for fila in filas:
        if fila["estado"] == "entregado":
            entregados = entregados + 1

    return render_template("documentos.html", filas=filas, entregados=entregados,
                           pendientes=len(filas) - entregados)


# MODIFICAR: actualizar el estado de un documento del expediente
@app.route("/documentos/editar/<int:documentoId>", methods=["GET", "POST"])
def editarDocumento(documentoId):
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute(
        "SELECT d.*, e.nombre FROM documentos d JOIN empleados e ON e.id = d.empleadoId WHERE d.id = %s",
        (documentoId,)
    )
    documento = cursor.fetchone()
    if documento is None:
        cursor.close()
        conexion.close()
        abort(404)

    error = ""
    if request.method == "POST":
        accion = request.form.get("accion", "")

        # Misma logica de la Fase 1: documento nuevo, nueva version o error
        if accion == "entregar":
            if documento["estado"] == "entregado":
                error = "El documento ya existia. Si es una renovacion, elija 'Nueva version'."
            else:
                nuevoEstado = "entregado"
                nuevaVersion = documento["version"] + 1
        elif accion == "nueva version":
            if documento["estado"] != "entregado":
                error = "No se puede crear una nueva version de un documento que no se ha entregado."
            else:
                nuevoEstado = "entregado"
                nuevaVersion = documento["version"] + 1
        elif accion == "pendiente":
            if documento["estado"] == "pendiente":
                error = "El documento ya esta pendiente."
            else:
                # Se conserva el numero de version como historial
                nuevoEstado = "pendiente"
                nuevaVersion = documento["version"]
        else:
            error = "Elija una accion valida."

        if error == "":
            cursor.execute(
                "UPDATE documentos SET estado = %s, version = %s, fechaActualizacion = %s WHERE id = %s",
                (nuevoEstado, nuevaVersion, date.today(), documentoId)
            )
            conexion.commit()
            cursor.close()
            conexion.close()
            return redirect("/empleados/" + str(documento["empleadoId"]))

    cursor.close()
    conexion.close()
    return render_template("editar_documento.html", documento=documento, error=error)


# Ruta JSON de la Fase 1, ahora leyendo el expediente desde MySQL
@app.route("/api/expediente/<int:empleadoId>")
def expedienteJson(empleadoId):
    conexion = conectar()
    expedientes = obtenerExpedientes(conexion)
    conexion.close()
    for expediente in expedientes:
        if expediente["id"] == empleadoId:
            return jsonify(expediente)
    return jsonify({"error": "empleado no encontrado"}), 404


# ELIMINAR: borra el empleado. Sus documentos se borran solos por el
# ON DELETE CASCADE de la llave foranea, asi no quedan documentos huerfanos.
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

    for expediente in expedientes:
        if expediente["estado"] == "completo":
            completos = completos + 1
        elif expediente["estado"] == "incompleto":
            incompletos = incompletos + 1
        else:
            sinIniciar = sinIniciar + 1

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
                           filtro=filtro)


# El servidor se inicia al final, despues de definir TODAS las rutas
if __name__ == "__main__":
    app.run(debug=True)
