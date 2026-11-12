# Expedientes Digitales: Tarea 3 (subida de archivos)

Reto del Socio Formador **Hospital de Diagnóstico (Recursos Humanos)**.

**Integrantes:** Diego Peralta, Maria Guirola, Italo Vidaurre, Carlos Campos

**Repositorio:** https://github.com/vidaurreitalo-debug/Fase-2-del-proyecto

**Video de pruebas (YouTube):** 

## Qué hace el sistema

Administra los expedientes digitales de los empleados del hospital. Cada empleado tiene un perfil (administrativo o médico) y cada perfil exige un checklist de documentos: 5 para administrativo y 7 para médico.

El sistema permite:

- **registrar** empleados (con su expediente creado de forma automática según su perfil) y, si se quiere, subir su DUI en el mismo formulario;
- **subir** los documentos del expediente en **PDF o Word**, que se guardan dentro de MySQL (columna `LONGBLOB`);
- conservar el **historial de versiones**: subir de nuevo un documento crea una versión nueva y la anterior se conserva;
- **descargar** cualquier versión con su nombre original;
- mostrar el **estado** de cada documento: **vigente**, **vencido** o **versión anterior**;
- **consultar**, **modificar** y **eliminar** empleados (al eliminar se borran también sus documentos y archivos);
- ver un **resumen** que clasifica los expedientes según los archivos realmente subidos;
- ver las **alertas de vencimiento** (documentos vencidos y por vencer en los próximos 30 días).

## Cómo ejecutarlo desde cero

1. Abrir el **Panel de Control de XAMPP** y presionar **Start** en **MySQL** y en **Apache**.
2. Abrir http://localhost/phpmyadmin, ir a la pestaña **Importar**, elegir el archivo `crear_bd.sql` y presionar **Importar**. Se crea la base de datos `hospital` con sus 5 tablas y los datos de ejemplo.
3. En una terminal, dentro de la carpeta del repositorio, instalar las dependencias:

```
pip install -r requirements.txt
```

4. Ejecutar el sistema:

```
python app.py
```

5. Abrir en el navegador http://127.0.0.1:5000/empleados

La conexión usa el usuario `root` de XAMPP con la contraseña vacía. Para volver a los datos iniciales basta con importar `crear_bd.sql` otra vez (la tabla `archivos` empieza vacía: los archivos se suben desde el navegador).

En la carpeta `documentos_prueba/` hay documentos **inventados** para hacer las pruebas: nunca se debe subir un DUI ni otro documento real, porque el repositorio es público.

## Estructura de archivos

```
Fase-2-del-proyecto/
|-- app.py                          # rutas de Flask, conexion a MySQL y logica del sistema
|-- crear_bd.sql                    # crea la base, las 5 tablas relacionadas y carga los datos
|-- requirements.txt                # flask y mysql-connector-python
|-- README.md                       # esta documentacion
|-- documentos_prueba/              # archivos ficticios para las pruebas
|-- templates/
|   |-- base.html                   # plantilla comun: menu, mensajes y enlace a style.css
|   |-- empleados.html              # listado de empleados con el estado del expediente
|   |-- nuevo.html                  # registrar empleado (con subida opcional del DUI)
|   |-- editar_empleado.html        # modificar los datos de un empleado
|   |-- expediente.html             # documentos de un empleado con todas sus versiones
|   |-- subir.html                  # formulario de subida de archivos
|   |-- archivos.html               # listado de todas las versiones subidas
|   |-- documentos.html             # empleados con sus documentos (consulta con JOIN)
|   |-- vencimientos.html           # alertas de vencimiento
|   |-- resumen.html                # resumen con los contadores por clasificacion
|   |-- reporte_departamentos.html  # reporte por departamento
|   |-- 404.html                    # pagina para registros que no existen
|-- static/
|   |-- style.css                   # hoja de estilos unica del sitio
```

## Rutas

| Ruta | Método | Qué hace |
|---|---|---|
| `/` | GET | Redirige al listado de empleados |
| `/empleados` | GET | Lista los empleados con el estado de su expediente. Acepta `?buscar=texto` |
| `/empleados/nuevo` | GET, POST | Registra un empleado y su expediente; permite subir el DUI |
| `/empleados/<id>` | GET | Expediente: cada documento con todas sus versiones |
| `/empleados/editar/<id>` | GET, POST | Modifica nombre, departamento y fecha de ingreso |
| `/empleados/eliminar/<id>` | POST | Borra el empleado; sus documentos y archivos se borran en cascada |
| **`/empleados/<id>/subir`** | GET, POST | **Subida** de un archivo (acepta `?documento=<id>` para elegirlo de una vez) |
| **`/archivos`** | GET | **Listado** de todas las versiones subidas. Acepta `?estado=vigente`, `vencido` o `version anterior` |
| **`/archivos/<id>/descargar`** | GET | **Descarga** el archivo con su nombre original; 404 si no existe |
| `/documentos` | GET | Todos los empleados con sus documentos (consulta con **JOIN**) |
| `/documentos/csv` | GET | Descarga el listado en CSV, con versión, archivo y vencimiento |
| `/vencimientos` | GET | Alertas: documentos vencidos, por vencer y al día |
| `/resumen` | GET | Clasifica los expedientes y cuenta cuántos hay de cada tipo. Acepta `?estado=` |
| `/reporte/departamentos` | GET | Contadores y acumuladores por departamento |
| `/api/expediente/<id>` | GET | Estado del expediente en JSON |

Todas las sentencias SQL usan parámetros con `%s`. Los `UPDATE` y `DELETE` siempre llevan `WHERE`.

## Base de datos (`hospital`)

En esta entrega se **unificó** el catálogo de documentos. Antes la tabla `checklist` repetía el nombre del documento para cada perfil (el DUI tenía un id para administrativo y otro para médico). Ahora cada documento existe **una sola vez** en `tipos_documento` y el resto de las tablas lo usan por su id.

```
tipos_documento 1 ── * checklist           (que documentos exige cada perfil)
tipos_documento 1 ── * documentos
empleados       1 ── * documentos          ON DELETE CASCADE
documentos      1 ── * archivos            ON DELETE CASCADE
```

**Tabla `tipos_documento`** (catálogo único):

| Campo | Tipo | Descripción |
|---|---|---|
| id | INT AUTO_INCREMENT | Llave primaria |
| nombre | VARCHAR(60) UNIQUE | DUI, Titulo academico, Solvencia de la PNC, etc. |
| requiereVencimiento | TINYINT(1) | 1 = la fecha de vencimiento es obligatoria (DUI) |

**Tabla `checklist`**: id, perfil (VARCHAR) y tipoDocumentoId (**llave foránea** hacia `tipos_documento.id`).

**Tabla `empleados`** (tabla principal): id, nombre, perfil, departamento, fechaIngreso.

**Tabla `documentos`** (el expediente: un registro por documento del checklist del empleado):

| Campo | Tipo | Descripción |
|---|---|---|
| id | INT AUTO_INCREMENT | Llave primaria |
| empleadoId | INT | **Llave foránea** hacia `empleados.id` con `ON DELETE CASCADE` |
| tipoDocumentoId | INT | **Llave foránea** hacia `tipos_documento.id` |

**Tabla `archivos`** (cada versión subida):

| Campo | Tipo | Descripción |
|---|---|---|
| id | INT AUTO_INCREMENT | Llave primaria |
| documentoId | INT | **Llave foránea** hacia `documentos.id` con `ON DELETE CASCADE` |
| version | INT | 1, 2, 3... (no se repite para el mismo documento) |
| nombreOriginal | VARCHAR(255) | Nombre con el que se subió el archivo |
| tamano | INT | Tamaño en bytes |
| contenido | LONGBLOB | El archivo completo |
| fechaVencimiento | DATE | Obligatoria para el DUI; opcional para los demás |
| fechaSubida | DATETIME | Se llena sola con la fecha y hora de la subida |

El tipo de documento de cada archivo se obtiene con su `documentoId` → `tipoDocumentoId`, sin repetir el nombre.

**Sin huérfanos:** al eliminar un empleado, MySQL borra sus documentos y, en cadena, todos sus archivos.

**Los listados no traen el archivo:** todas las consultas de los listados usan `SELECT` solo con las columnas que muestran. La única consulta que lee la columna `contenido` es la de la descarga.

## Subida de archivos

El formulario lleva `method="POST"` y `enctype="multipart/form-data"`; en Flask el archivo se recibe con `request.files`. Antes de guardar se valida, en este orden:

1. Que se eligió un tipo de documento del expediente de ese empleado.
2. Que se eligió un archivo.
3. Que la extensión es `.pdf`, `.doc` o `.docx` (sin importar mayúsculas).
4. Que el archivo no está vacío.
5. Que no pasa de **500 KB**.
6. Que la fecha de vencimiento es válida, y que existe si el documento es el DUI.

Si algo falla no se guarda nada y se muestra el mensaje de error.

**Tamaño máximo:** el MySQL de XAMPP trae `max_allowed_packet=1M`; con un límite de 500 KB el archivo siempre cabe. Para aceptar archivos más pesados se cambia `max_allowed_packet=16M` en el `my.ini` de XAMPP, se reinicia MySQL y se sube la constante `TAMANO_MAXIMO_KB` en `app.py`.

## Cómo funcionan las versiones y los estados

**Versiones:** subir un documento nunca reemplaza al anterior. La función `guardarArchivo()` calcula la versión siguiente con `SELECT MAX(version)` (si no hay ninguna, la primera es 1) e inserta un registro nuevo. El expediente y `/archivos` muestran todas las versiones de la más reciente a la más antigua.

**Estado de cada versión** (función `estadoArchivo()`, con `if/elif/else`):

| Condición | Estado |
|---|---|
| Su versión es menor que la última del documento | **versión anterior** |
| Es la última y su fecha de vencimiento ya pasó | **vencido** |
| En cualquier otro caso | **vigente** |

Un documento sin archivos se muestra como **pendiente**.

## Cómo funciona el resumen

La función `obtenerExpedientes()` recorre con `for` todos los empleados y, para cada uno, recorre sus documentos contando cuántos tienen la última versión **vigente** y cuántos **vencida**. Después `evaluarEstado()` decide:

- ningún archivo subido → **sin iniciar**;
- menos documentos vigentes que los requeridos → **incompleto** (un documento vencido no cuenta);
- todos los documentos vigentes → **completo**.

La ruta `/resumen` recorre esa lista y suma 1 al contador de cada clasificación, y además cuenta cuántos expedientes tienen documentos vencidos.

## Equipo: parte del código y mejora individual de cada integrante

| Integrante | Usuario de GitHub | Mejora individual (Desafío 2) | Adaptación a los archivos (Tarea 3) |
|---|---|---|---|
| Italo Vidaurre | vidaurreitalo-debug | **Filtro por clasificación** en `/resumen` (`?estado=`) | El resumen clasifica con los archivos subidos y `/archivos` filtra por estado del documento (vigente, vencido, versión anterior) |
| Carlos Campos | Camp3s | **Búsqueda por texto** en `/empleados` (`?buscar=`) | También encuentra al empleado por el **nombre del archivo** subido |
| Majo Guirola | MajoGuirola | **Exportar a CSV** (`/documentos/csv`) | El CSV incluye estado, versión actual, nombre del archivo, vencimiento y fecha de subida |
| Diego Peralta | Leapeonn | **Reporte por departamento** (`/reporte/departamentos`) | Cuenta documentos vigentes y acumula los vencidos por departamento |

**Mejora extra del equipo: alertas de vencimiento** (`/vencimientos`). Revisa la versión actual de cada documento con fecha de vencimiento, calcula los días que le faltan y lo clasifica con `if/elif/else` como **vencido**, **por vencer** (30 días o menos) o **al día**. Muestra contadores y un botón para subir la renovación.
