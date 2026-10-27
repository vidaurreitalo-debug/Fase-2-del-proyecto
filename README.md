# Expedientes Digitales: Desafío 2 (MySQL)

Reto del Socio Formador **Hospital de Diagnóstico (Recursos Humanos)**.

**Integrantes:** Diego Peralta, Maria Guirola, Italo Vidaurre, Carlos Moises

**Repositorio:** https://github.com/vidaurreitalo-debug/Fase-2-del-proyecto

## Qué hace el sistema

Administra los expedientes digitales de los empleados del hospital. Cada empleado tiene un perfil (administrativo o médico) y cada perfil exige un checklist de documentos distinto: 5 para administrativo y 7 para médico.

El sistema permite:

- **registrar** empleados, con su expediente creado de forma automática según el checklist de su perfil;
- **consultar** el listado de empleados con el estado de su expediente, el expediente de cada empleado y el listado de todos los empleados con sus documentos (consulta con JOIN);
- **modificar** el estado de cada documento: entregarlo, subir una nueva versión (renovación) o marcarlo como pendiente;
- **eliminar** empleados junto con todo su expediente, sin dejar documentos huérfanos;
- ver un **resumen** que clasifica todos los expedientes como completo, incompleto o sin iniciar, y cuenta cuántos hay de cada tipo.

En esta entrega los datos pasan de SQLite a **MySQL (XAMPP y phpMyAdmin)**, las tablas `empleados` y `documentos` quedan relacionadas por una llave foránea, y cada integrante agregó una mejora individual.

## Cómo ejecutarlo desde cero

1. Abrir el **Panel de Control de XAMPP** y presionar **Start** en **MySQL** (y en Apache, para usar phpMyAdmin).
2. Abrir http://localhost/phpmyadmin, ir a la pestaña **Importar**, elegir el archivo `crear_bd.sql` del repositorio y presionar **Importar**. Se crea la base de datos `hospital` con sus tablas y datos de ejemplo.
3. En una terminal, dentro de la carpeta del repositorio, instalar las dependencias:

```
pip install -r requirements.txt
```

4. Ejecutar el sistema:

```
python app.py
```

5. Abrir en el navegador:

- http://127.0.0.1:5000/empleados
- http://127.0.0.1:5000/empleados/nuevo
- http://127.0.0.1:5000/documentos
- http://127.0.0.1:5000/resumen
- http://127.0.0.1:5000/reporte/departamentos
- http://127.0.0.1:5000/documentos/csv

La conexión usa el usuario `root` de XAMPP con la contraseña vacía. Para volver a los datos iniciales basta con importar `crear_bd.sql` otra vez.

## Estructura de archivos

```
Fase-2-del-proyecto/
|-- app.py                          # rutas de Flask, conexion a MySQL y logica del sistema
|-- crear_bd.sql                    # crea la base, las tablas relacionadas y carga los datos
|-- requirements.txt                # flask y mysql-connector-python
|-- .gitignore                      # archivos que Git ignora
|-- README.md                       # esta documentacion
|-- templates/
|   |-- base.html                   # plantilla comun: encabezado, menu y enlace a style.css
|   |-- empleados.html              # listado de empleados con el estado del expediente
|   |-- nuevo.html                  # formulario para registrar un empleado
|   |-- expediente.html             # documentos del expediente de un empleado
|   |-- editar_documento.html       # formulario para actualizar un documento
|   |-- documentos.html             # empleados con sus documentos (consulta con JOIN)
|   |-- resumen.html                # resumen con los contadores por clasificacion
|   |-- reporte_departamentos.html  # reporte por departamento (mejora de Diego)
|-- static/
|   |-- style.css                   # hoja de estilos unica del sitio
```

Todas las páginas extienden `base.html`, que es la única que enlaza `static/style.css`.

## Rutas

| Ruta | Método | Mantenimiento | Qué hace |
|---|---|---|---|
| `/` | GET | | Redirige al listado de empleados |
| `/empleados` | GET | Consultar | Lista los empleados con el estado de su expediente. Acepta `?buscar=texto` |
| `/empleados/nuevo` | GET, POST | Registrar | GET muestra el formulario; POST valida y guarda el empleado y su expediente |
| `/empleados/<id>` | GET | Consultar | Muestra los documentos del expediente de un empleado |
| `/documentos` | GET | Consultar | Lista todos los empleados con sus documentos usando un **JOIN** |
| `/documentos/csv` | GET | Consultar | Descarga el listado con JOIN en un archivo CSV |
| `/documentos/editar/<id>` | GET, POST | Modificar | GET muestra el formulario; POST actualiza el estado del documento |
| `/empleados/eliminar/<id>` | POST | Eliminar | Borra el empleado; sus documentos se borran por el `ON DELETE CASCADE` |
| `/resumen` | GET | | Recorre los expedientes y cuenta cuántos hay de cada clasificación. Acepta `?estado=` |
| `/reporte/departamentos` | GET | | Contadores y acumuladores por departamento |
| `/api/expediente/<id>` | GET | Consultar | Devuelve en JSON el estado del expediente, como en la Fase 1 |

La conexión se hace con `mysql-connector-python` en la función `conectar()`. Todas las sentencias SQL usan parámetros con `%s`: ningún texto escrito por el usuario se concatena dentro de una sentencia. Los `UPDATE` y `DELETE` siempre llevan `WHERE`.

## Base de datos (`hospital`)

**Tabla `empleados`** (tabla principal):

| Campo | Tipo | Descripción |
|---|---|---|
| id | INT AUTO_INCREMENT | Llave primaria |
| nombre | VARCHAR(80) | Nombre completo |
| perfil | VARCHAR(20) | administrativo o medico; define el checklist |
| departamento | VARCHAR(60) | Departamento donde trabaja |
| fechaIngreso | DATE | Fecha de ingreso |

**Tabla `documentos`** (tabla relacionada: cada documento pertenece a un empleado):

| Campo | Tipo | Descripción |
|---|---|---|
| id | INT AUTO_INCREMENT | Llave primaria |
| empleadoId | INT | **Llave foránea** hacia `empleados.id` con `ON DELETE CASCADE` |
| documento | VARCHAR(60) | Nombre del documento |
| estado | VARCHAR(15) | pendiente o entregado |
| version | INT | 0 sin entregar; sube con cada entrega o renovación |
| fechaActualizacion | DATE | Fecha del último cambio (vacía si nunca se entregó) |

**Tabla `checklist`** (catálogo): id (INT, llave primaria), perfil (VARCHAR) y documento (VARCHAR). Guarda los documentos que exige cada perfil, para que no estén fijos en el código.

**Relación:** un empleado tiene muchos documentos (uno a muchos). Al registrar se inserta primero el empleado (padre) y con su `id` se insertan sus documentos (hijos). Al eliminar un empleado, MySQL borra sus documentos por el `ON DELETE CASCADE`, así no quedan documentos huérfanos.

**Consulta con JOIN** (ruta `/documentos`):

```sql
SELECT e.id AS empleadoId, e.nombre, e.perfil, e.departamento,
       d.id, d.documento, d.estado, d.version, d.fechaActualizacion
FROM empleados e JOIN documentos d ON d.empleadoId = e.id
ORDER BY e.nombre, d.id
```

`crear_bd.sql` carga 6 empleados y 36 documentos de ejemplo.

## Validaciones

**Registrar empleado:** no guarda y muestra un mensaje si algún campo está vacío, si el nombre tiene números o símbolos, si el perfil no existe en el checklist o si la fecha de ingreso no es válida o es futura.

**Actualizar documento** (la misma lógica de la Fase 1):

| Acción | Si el documento está pendiente | Si el documento está entregado |
|---|---|---|
| Entregar (documento nuevo) | Pasa a entregado y sube la versión | Error: el documento ya existía, usar nueva versión |
| Nueva versión (renovación) | Error: no se ha entregado | Sigue entregado y sube la versión |
| Marcar pendiente | Error: ya está pendiente | Pasa a pendiente y conserva el número de versión |

## Cómo funciona el resumen

La ruta `/resumen` usa la función `obtenerExpedientes()`, que:

1. Lee todos los empleados de MySQL.
2. Los recorre con `for`. Para cada empleado lee sus documentos y los recorre con otro `for`, contando cuántos tienen estado `entregado`.
3. Con `evaluarEstado()` decide su clasificación comparando los entregados con los requeridos por su perfil: 0 entregados → **sin iniciar**; menos de los requeridos → **incompleto**; igual a los requeridos → **completo**.

Luego el resumen recorre esa lista con `for` y, con `if/elif/else`, suma 1 al contador correspondiente (`completos`, `incompletos` o `sinIniciar`). Con los datos de ejemplo da 2 completos, 2 incompletos y 2 sin iniciar.

## Equipo: parte del código y mejora individual de cada integrante

| Integrante | Usuario de GitHub | Parte del código | Mejora individual (pull request) |
|---|---|---|---|
| Italo Vidaurre | vidaurreitalo-debug | Base de datos, conexión, función de estado y listado de empleados | **Filtro por clasificación** en `/resumen` (`?estado=completo`, `incompleto` o `sin iniciar`): los contadores siguen contando a todos y la tabla muestra solo la clasificación elegida |
| Carlos Campos | Camp3s | Registro de empleados con validación (`/empleados/nuevo`) | **Búsqueda por texto** en `/empleados` (`?buscar=`): busca en el nombre o el departamento con `LIKE %s` |
| Majo Guirola | MajoGuirola | Consulta del expediente, modificación de documentos y ruta JSON | **Exportar a CSV** el listado con JOIN (`/documentos/csv`) |
| Diego Peralta | Leapeonn | Eliminación de empleados, resumen con contadores y colores | **Reporte por departamento** (`/reporte/departamentos`): cuenta completos, incompletos y sin iniciar, y acumula los documentos entregados y requeridos para calcular el avance |
