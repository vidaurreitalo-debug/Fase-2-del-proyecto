-- =====================================================================
-- Expedientes Digitales - Hospital de Diagnostico (Tarea 3)
-- Crea la base de datos, sus 5 tablas relacionadas y carga datos de ejemplo.
-- Se importa en phpMyAdmin (pestana Importar). Se puede importar varias veces.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS hospital CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE hospital;

-- 1. Borrar las tablas si ya existian (primero las hijas, despues las padres)
DROP TABLE IF EXISTS archivos;
DROP TABLE IF EXISTS documentos;
DROP TABLE IF EXISTS empleados;
DROP TABLE IF EXISTS checklist;
DROP TABLE IF EXISTS tipos_documento;

-- 2. tipos_documento: catalogo UNICO de documentos.
--    Cada documento existe una sola vez (el DUI tiene un solo id para
--    administrativos y medicos). requiereVencimiento = 1 obliga a
--    escribir la fecha de vencimiento al subir el archivo.
CREATE TABLE tipos_documento (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(60) NOT NULL UNIQUE,
    requiereVencimiento TINYINT(1) NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- 3. checklist: que documentos exige cada perfil.
--    Solo guarda el perfil y el id del tipo de documento.
CREATE TABLE checklist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    perfil VARCHAR(20) NOT NULL,
    tipoDocumentoId INT NOT NULL,
    UNIQUE (perfil, tipoDocumentoId),
    FOREIGN KEY (tipoDocumentoId) REFERENCES tipos_documento(id)
) ENGINE=InnoDB;

-- 4. empleados: tabla principal
CREATE TABLE empleados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL,
    perfil VARCHAR(20) NOT NULL,
    departamento VARCHAR(60) NOT NULL,
    fechaIngreso DATE NOT NULL
) ENGINE=InnoDB;

-- 5. documentos: el expediente de cada empleado (un registro por cada
--    documento de su checklist). Su estado ya no se escribe a mano:
--    se calcula con los archivos realmente subidos.
--    ON DELETE CASCADE: al eliminar un empleado se borran sus documentos.
CREATE TABLE documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empleadoId INT NOT NULL,
    tipoDocumentoId INT NOT NULL,
    UNIQUE (empleadoId, tipoDocumentoId),
    FOREIGN KEY (empleadoId) REFERENCES empleados(id) ON DELETE CASCADE,
    FOREIGN KEY (tipoDocumentoId) REFERENCES tipos_documento(id)
) ENGINE=InnoDB;

-- 6. archivos: cada version subida de un documento (PDF o Word).
--    Subir de nuevo NO reemplaza: se inserta una fila con version + 1.
--    ON DELETE CASCADE: al borrar el documento (o el empleado) se borran
--    sus archivos, asi no quedan archivos huerfanos.
CREATE TABLE archivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    documentoId INT NOT NULL,
    version INT NOT NULL,
    nombreOriginal VARCHAR(255) NOT NULL,
    tamano INT NOT NULL,
    contenido LONGBLOB NOT NULL,
    fechaVencimiento DATE NULL,
    fechaSubida DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (documentoId, version),
    FOREIGN KEY (documentoId) REFERENCES documentos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 7. Catalogo de documentos (ids 1 a 8)
INSERT INTO tipos_documento (nombre, requiereVencimiento) VALUES
('DUI', 1),
('Titulo academico', 0),
('Titulo de medico', 0),
('Carnet de la Junta de Vigilancia', 0),
('Constancia de especialidad', 0),
('Antecedentes penales', 0),
('Solvencia de la PNC', 0),
('Certificado de salud', 0);

-- 8. Checklist: 5 documentos para administrativo y 7 para medico.
--    Los documentos comunes (DUI, antecedentes, solvencia y certificado)
--    usan el MISMO id en los dos perfiles.
INSERT INTO checklist (perfil, tipoDocumentoId) VALUES
('administrativo', 1),
('administrativo', 2),
('administrativo', 6),
('administrativo', 7),
('administrativo', 8),
('medico', 1),
('medico', 3),
('medico', 4),
('medico', 5),
('medico', 6),
('medico', 7),
('medico', 8);

-- 9. Empleados de ejemplo (ids 1 a 6)
INSERT INTO empleados (nombre, perfil, departamento, fechaIngreso) VALUES
('Ana Lopez', 'administrativo', 'Recursos Humanos', '2024-02-12'),
('Luis Martinez', 'medico', 'Radiologia', '2023-08-01'),
('Sofia Hernandez', 'administrativo', 'Facturacion', '2025-01-20'),
('Carlos Ramirez', 'medico', 'Laboratorio clinico', '2026-10-01'),
('Marta Rivas', 'medico', 'Ultrasonografia', '2022-05-16'),
('Pedro Alvarado', 'administrativo', 'Admision', '2026-09-28');

-- 10. Expediente de cada empleado: un documento por cada fila del checklist
--     de su perfil (5 para administrativos y 7 para medicos = 36 documentos).
INSERT INTO documentos (empleadoId, tipoDocumentoId)
SELECT e.id, c.tipoDocumentoId
FROM empleados e JOIN checklist c ON c.perfil = e.perfil
ORDER BY e.id, c.id;

-- La tabla archivos empieza vacia: los archivos se suben desde el navegador.
-- (No se guardan archivos reales en este script.)
