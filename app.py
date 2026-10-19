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


if __name__ == "__main__":
    app.run(debug=True)
