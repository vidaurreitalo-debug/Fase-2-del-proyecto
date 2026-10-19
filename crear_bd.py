import sqlite3

# Crea la base de datos del reto Expedientes Digitales y carga datos de ejemplo
conexion = sqlite3.connect("hospital.db")
cursor = conexion.cursor()

# 1. Borrar las tablas si ya existian, para empezar desde cero
cursor.execute("DROP TABLE IF EXISTS documentos")
cursor.execute("DROP TABLE IF EXISTS empleados")
cursor.execute("DROP TABLE IF EXISTS checklist")

# 2. Crear las tablas
# checklist: documentos que exige cada perfil (antes estaban fijos en el codigo)
cursor.execute("""
CREATE TABLE checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    perfil TEXT NOT NULL,
    documento TEXT NOT NULL
)
""")

# empleados: tabla principal
cursor.execute("""
CREATE TABLE empleados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    perfil TEXT NOT NULL,
    departamento TEXT NOT NULL,
    fechaIngreso TEXT NOT NULL
)
""")

# documentos: el expediente de cada empleado, un registro por documento del checklist
cursor.execute("""
CREATE TABLE documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empleadoId INTEGER NOT NULL,
    documento TEXT NOT NULL,
    estado TEXT NOT NULL,
    version INTEGER NOT NULL,
    fechaActualizacion TEXT,
    FOREIGN KEY (empleadoId) REFERENCES empleados(id)
)
""")

# 3. Cargar el checklist de cada perfil (5 documentos administrativo, 7 medico)
checklist = [
    ("administrativo", "DUI"),
    ("administrativo", "Titulo academico"),
    ("administrativo", "Antecedentes penales"),
    ("administrativo", "Solvencia de la PNC"),
    ("administrativo", "Certificado de salud"),
    ("medico", "DUI"),
    ("medico", "Titulo de medico"),
    ("medico", "Carnet de la Junta de Vigilancia"),
    ("medico", "Constancia de especialidad"),
    ("medico", "Antecedentes penales"),
    ("medico", "Solvencia de la PNC"),
    ("medico", "Certificado de salud"),
]
cursor.executemany("INSERT INTO checklist (perfil, documento) VALUES (?, ?)", checklist)

# 4. Cargar empleados de ejemplo: (nombre, perfil, departamento, fechaIngreso, documentos entregados)
empleados = [
    ("Ana Lopez", "administrativo", "Recursos Humanos", "2024-02-12", 5),
    ("Luis Martinez", "medico", "Radiologia", "2023-08-01", 4),
    ("Sofia Hernandez", "administrativo", "Facturacion", "2025-01-20", 2),
    ("Carlos Ramirez", "medico", "Laboratorio clinico", "2026-10-01", 0),
    ("Marta Rivas", "medico", "Ultrasonografia", "2022-05-16", 7),
    ("Pedro Alvarado", "administrativo", "Admision", "2026-09-28", 0),
]

for nombre, perfil, departamento, fechaIngreso, entregados in empleados:
    cursor.execute(
        "INSERT INTO empleados (nombre, perfil, departamento, fechaIngreso) VALUES (?, ?, ?, ?)",
        (nombre, perfil, departamento, fechaIngreso)
    )
    empleadoId = cursor.lastrowid

    # Crear el expediente: los primeros "entregados" documentos quedan entregados
    documentosPerfil = cursor.execute(
        "SELECT documento FROM checklist WHERE perfil = ? ORDER BY id", (perfil,)
    ).fetchall()

    contador = 0
    for fila in documentosPerfil:
        if contador < entregados:
            estado = "entregado"
            version = 1
            fecha = fechaIngreso
        else:
            estado = "pendiente"
            version = 0
            fecha = None
        cursor.execute(
            "INSERT INTO documentos (empleadoId, documento, estado, version, fechaActualizacion) VALUES (?, ?, ?, ?, ?)",
            (empleadoId, fila[0], estado, version, fecha)
        )
        contador = contador + 1

# Marta renovo su carnet de la Junta: ese documento va en su version 2
cursor.execute(
    "UPDATE documentos SET version = 2 WHERE documento = ? AND empleadoId = (SELECT id FROM empleados WHERE nombre = ?)",
    ("Carnet de la Junta de Vigilancia", "Marta Rivas")
)

conexion.commit()
conexion.close()
print("Base de datos hospital.db creada con", len(empleados), "empleados de ejemplo.")
