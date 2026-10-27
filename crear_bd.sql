CREATE DATABASE IF NOT EXISTS hospital CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE hospital;

-- 1. Borrar las tablas si ya existian (primero la hija, despues la principal)
DROP TABLE IF EXISTS documentos;
DROP TABLE IF EXISTS empleados;
DROP TABLE IF EXISTS checklist;

-- 2. checklist: documentos que exige cada perfil
CREATE TABLE checklist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    perfil VARCHAR(20) NOT NULL,
    documento VARCHAR(60) NOT NULL
) ENGINE=InnoDB;

-- 3. empleados: tabla principal
CREATE TABLE empleados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL,
    perfil VARCHAR(20) NOT NULL,
    departamento VARCHAR(60) NOT NULL,
    fechaIngreso DATE NOT NULL
) ENGINE=InnoDB;

-- 4. documentos: tabla relacionada. Cada documento pertenece a un empleado.
--    ON DELETE CASCADE: al eliminar un empleado se borran sus documentos,
--    asi no quedan documentos huerfanos.
CREATE TABLE documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empleadoId INT NOT NULL,
    documento VARCHAR(60) NOT NULL,
    estado VARCHAR(15) NOT NULL,
    version INT NOT NULL DEFAULT 0,
    fechaActualizacion DATE NULL,
    FOREIGN KEY (empleadoId) REFERENCES empleados(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. Checklist de cada perfil: 5 documentos administrativo, 7 medico
INSERT INTO checklist (perfil, documento) VALUES
('administrativo', 'DUI'),
('administrativo', 'Titulo academico'),
('administrativo', 'Antecedentes penales'),
('administrativo', 'Solvencia de la PNC'),
('administrativo', 'Certificado de salud'),
('medico', 'DUI'),
('medico', 'Titulo de medico'),
('medico', 'Carnet de la Junta de Vigilancia'),
('medico', 'Constancia de especialidad'),
('medico', 'Antecedentes penales'),
('medico', 'Solvencia de la PNC'),
('medico', 'Certificado de salud');

-- 6. Empleados de ejemplo (ids 1 a 6)
INSERT INTO empleados (nombre, perfil, departamento, fechaIngreso) VALUES
('Ana Lopez', 'administrativo', 'Recursos Humanos', '2024-02-12'),
('Luis Martinez', 'medico', 'Radiologia', '2023-08-01'),
('Sofia Hernandez', 'administrativo', 'Facturacion', '2025-01-20'),
('Carlos Ramirez', 'medico', 'Laboratorio clinico', '2026-10-01'),
('Marta Rivas', 'medico', 'Ultrasonografia', '2022-05-16'),
('Pedro Alvarado', 'administrativo', 'Admision', '2026-09-28');

-- 7. Expediente de cada empleado: un registro por documento de su checklist
INSERT INTO documentos (empleadoId, documento, estado, version, fechaActualizacion) VALUES
-- Ana Lopez (administrativo): 5 de 5 entregados -> completo
(1, 'DUI', 'entregado', 1, '2024-02-12'),
(1, 'Titulo academico', 'entregado', 1, '2024-02-12'),
(1, 'Antecedentes penales', 'entregado', 1, '2024-02-12'),
(1, 'Solvencia de la PNC', 'entregado', 1, '2024-02-12'),
(1, 'Certificado de salud', 'entregado', 1, '2024-02-12'),
-- Luis Martinez (medico): 4 de 7 entregados -> incompleto
(2, 'DUI', 'entregado', 1, '2023-08-01'),
(2, 'Titulo de medico', 'entregado', 1, '2023-08-01'),
(2, 'Carnet de la Junta de Vigilancia', 'entregado', 1, '2023-08-01'),
(2, 'Constancia de especialidad', 'entregado', 1, '2023-08-01'),
(2, 'Antecedentes penales', 'pendiente', 0, NULL),
(2, 'Solvencia de la PNC', 'pendiente', 0, NULL),
(2, 'Certificado de salud', 'pendiente', 0, NULL),
-- Sofia Hernandez (administrativo): 2 de 5 entregados -> incompleto
(3, 'DUI', 'entregado', 1, '2025-01-20'),
(3, 'Titulo academico', 'entregado', 1, '2025-01-20'),
(3, 'Antecedentes penales', 'pendiente', 0, NULL),
(3, 'Solvencia de la PNC', 'pendiente', 0, NULL),
(3, 'Certificado de salud', 'pendiente', 0, NULL),
-- Carlos Ramirez (medico): 0 de 7 entregados -> sin iniciar
(4, 'DUI', 'pendiente', 0, NULL),
(4, 'Titulo de medico', 'pendiente', 0, NULL),
(4, 'Carnet de la Junta de Vigilancia', 'pendiente', 0, NULL),
(4, 'Constancia de especialidad', 'pendiente', 0, NULL),
(4, 'Antecedentes penales', 'pendiente', 0, NULL),
(4, 'Solvencia de la PNC', 'pendiente', 0, NULL),
(4, 'Certificado de salud', 'pendiente', 0, NULL),
-- Marta Rivas (medico): 7 de 7 entregados -> completo (renovo su carnet: version 2)
(5, 'DUI', 'entregado', 1, '2022-05-16'),
(5, 'Titulo de medico', 'entregado', 1, '2022-05-16'),
(5, 'Carnet de la Junta de Vigilancia', 'entregado', 2, '2025-05-16'),
(5, 'Constancia de especialidad', 'entregado', 1, '2022-05-16'),
(5, 'Antecedentes penales', 'entregado', 1, '2022-05-16'),
(5, 'Solvencia de la PNC', 'entregado', 1, '2022-05-16'),
(5, 'Certificado de salud', 'entregado', 1, '2022-05-16'),
-- Pedro Alvarado (administrativo): 0 de 5 entregados -> sin iniciar
(6, 'DUI', 'pendiente', 0, NULL),
(6, 'Titulo academico', 'pendiente', 0, NULL),
(6, 'Antecedentes penales', 'pendiente', 0, NULL),
(6, 'Solvencia de la PNC', 'pendiente', 0, NULL),
(6, 'Certificado de salud', 'pendiente', 0, NULL);
