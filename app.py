import sqlite3
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, jsonify, abort

app = Flask(__name__)
app.json.sort_keys = False

BASE_DE_DATOS = "hospital.db"


def conectar():
    conexion = sqlite3.connect(BASE_DE_DATOS)
    conexion.row_factory = sqlite3.Row
    return conexion


def obtenerPerfiles(conexion):
    # Los perfiles validos salen del checklist guardado en la base de datos
    filas = conexion.execute("SELECT DISTINCT perfil FROM checklist ORDER BY perfil").fetchall()
    perfiles = []
    for fila in filas:
        perfiles.append(fila["perfil"])
    return perfiles


def obtenerRequeridos(conexion, perfil):
    # Numero de documentos del checklist del perfil (0 si el perfil no existe)
    fila = conexion.execute("SELECT COUNT(*) AS total FROM checklist WHERE perfil = ?", (perfil,)).fetchone()
    return fila["total"]


def evaluarEstado(documentosEntregados, documentosRequeridos):
    # Misma decision de la Fase 1, ahora con los datos de la base de datos
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
    empleados = conexion.execute("SELECT * FROM empleados ORDER BY nombre").fetchall()
    expedientes = []

    for empleado in empleados:
        documentos = conexion.execute(
            "SELECT estado FROM documentos WHERE empleadoId = ?", (empleado["id"],)
        ).fetchall()

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
            "fechaIngreso": empleado["fechaIngreso"],
            "documentosEntregados": documentosEntregados,
            "documentosRequeridos": documentosRequeridos,
            "documentosPendientes": documentosRequeridos - documentosEntregados,
            "estado": evaluarEstado(documentosEntregados, documentosRequeridos)
        })

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

        # 2. Si no hay error, guardar el empleado y crear su expediente vacio
        if error == "":
            cursor = conexion.execute(
                "INSERT INTO empleados (nombre, perfil, departamento, fechaIngreso) VALUES (?, ?, ?, ?)",
                (datos["nombre"], datos["perfil"], datos["departamento"], datos["fechaIngreso"])
            )
            empleadoId = cursor.lastrowid

            checklist = conexion.execute(
                "SELECT documento FROM checklist WHERE perfil = ? ORDER BY id", (datos["perfil"],)
            ).fetchall()
            for fila in checklist:
                conexion.execute(
                    "INSERT INTO documentos (empleadoId, documento, estado, version, fechaActualizacion) VALUES (?, ?, ?, ?, ?)",
                    (empleadoId, fila["documento"], "pendiente", 0, None)
                )

            conexion.commit()
            conexion.close()
            return redirect("/empleados")

    conexion.close()
    return render_template("nuevo.html", error=error, datos=datos, perfiles=perfiles)

if __name__ == "__main__":
    app.run(debug=True)

# CONSULTAR un expediente: documentos de un empleado
@app.route("/empleados/<int:empleadoId>")
def verExpediente(empleadoId):
    conexion = conectar()
    empleado = conexion.execute("SELECT * FROM empleados WHERE id = ?", (empleadoId,)).fetchone()
    if empleado is None:
        conexion.close()
        abort(404)

    documentos = conexion.execute(
        "SELECT * FROM documentos WHERE empleadoId = ? ORDER BY id", (empleadoId,)
    ).fetchall()
    conexion.close()

    documentosEntregados = 0
    for documento in documentos:
        if documento["estado"] == "entregado":
            documentosEntregados = documentosEntregados + 1
    estado = evaluarEstado(documentosEntregados, len(documentos))

    return render_template("expediente.html", empleado=empleado, documentos=documentos,
                           documentosEntregados=documentosEntregados, estado=estado)


# MODIFICAR: actualizar el estado de un documento del expediente
@app.route("/documentos/editar/<int:documentoId>", methods=["GET", "POST"])
def editarDocumento(documentoId):
    conexion = conectar()
    documento = conexion.execute(
        "SELECT d.*, e.nombre FROM documentos d JOIN empleados e ON e.id = d.empleadoId WHERE d.id = ?",
        (documentoId,)
    ).fetchone()
    if documento is None:
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
            conexion.execute(
                "UPDATE documentos SET estado = ?, version = ?, fechaActualizacion = ? WHERE id = ?",
                (nuevoEstado, nuevaVersion, date.today().isoformat(), documentoId)
            )
            conexion.commit()
            conexion.close()
            return redirect("/empleados/" + str(documento["empleadoId"]))

    conexion.close()
    return render_template("editar_documento.html", documento=documento, error=error)


# Ruta JSON de la Fase 1, ahora leyendo el expediente desde la base de datos
@app.route("/api/expediente/<int:empleadoId>")
def expedienteJson(empleadoId):
    conexion = conectar()
    expedientes = obtenerExpedientes(conexion)
    conexion.close()
    for expediente in expedientes:
        if expediente["id"] == empleadoId:
            return jsonify(expediente)
    return jsonify({"error": "empleado no encontrado"}), 404


if __name__ == "__main__":
    app.run(debug=True)
