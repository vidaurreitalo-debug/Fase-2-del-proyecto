# Expedientes Digitales: Fase 2

Reto del Socio Formador **Hospital de Diagnóstico (Recursos Humanos)**.

**Integrantes:** Diego Peralta , Maria Guirola, Italo Vidaurre, Carlos Moises

## Qué hace el sistema

Administra los expedientes digitales de los empleados del hospital. Cada empleado tiene un perfil (administrativo o médico), y cada perfil exige un checklist de documentos distinto: 5 para administrativo y 7 para médico.

El sistema permite:

- registrar empleados, con su expediente creado de forma automática según el checklist de su perfil;
- consultar el listado de empleados con el estado de su expediente;
- ver el expediente de cada empleado y actualizar el estado de cada documento: entregarlo, subir una nueva versión (renovación) o marcarlo como pendiente;
- eliminar empleados junto con su expediente;
- ver un resumen que clasifica todos los expedientes como **completo**, **incompleto** o **sin iniciar**, y cuenta cuántos hay de cada tipo.

Esta fase hace crecer la ruta `/expediente` de la Fase 1. Se conserva la misma lógica: los estados sin iniciar, incompleto y completo, el checklist por perfil y la regla de que una renovación se guarda como nueva versión y no suma un documento nuevo. Ahora los datos se leen de una base de datos SQLite en lugar de venir en la URL o estar fijos en el código.

## Cómo ejecutarlo

```
pip install flask
python crear_bd.py
python app.py
```

Después, abrir en el navegador:

- http://127.0.0.1:5000/empleados
- http://127.0.0.1:5000/empleados/nuevo
- http://127.0.0.1:5000/resumen

`crear_bd.py` borra y vuelve a crear la base de datos `hospital.db` con 6 empleados de ejemplo. Se puede ejecutar de nuevo para volver a los datos iniciales.

## Estructura de archivos

```
Fase-2-del-proyecto/
|-- app.py                      # rutas de Flask y lógica del sistema
|-- crear_bd.py                 # crea las tablas y carga los datos de ejemplo
|-- requirements.txt            # dependencias (flask)
|-- .gitignore                  # archivos que Git ignora (hospital.db, __pycache__)
|-- README.md                   # esta documentación
|-- templates/
|   |-- base.html               # plantilla común: encabezado, menú y enlace a style.css
|   |-- empleados.html          # listado de empleados con el estado del expediente
|   |-- nuevo.html              # formulario para registrar un empleado
|   |-- expediente.html         # documentos del expediente de un empleado
|   |-- editar_documento.html   # formulario para actualizar un documento
|   |-- resumen.html            # resumen con los contadores por clasificación
|-- static/
|   |-- style.css               # hoja de estilos única del sitio
```

Todas las páginas extienden `base.html`, que es la única que enlaza `static/style.css`. Así todo el sitio usa la misma hoja de estilos y ningún estilo se repite dentro de las páginas.

## Rutas

| Ruta | Método | Mantenimiento | Qué hace |
|---|---|---|---|
| `/` | GET | | Redirige al listado de empleados |
| `/empleados` | GET | Consultar | Lista los empleados con el estado de su expediente |
| `/empleados/nuevo` | GET, POST | Registrar | GET muestra el formulario; POST valida y guarda el empleado |
| `/empleados/<id>` | GET | Consultar | Muestra los documentos del expediente de un empleado |
| `/documentos/editar/<id>` | GET, POST | Modificar | GET muestra el formulario; POST actualiza el estado del documento |
| `/empleados/eliminar/<id>` | POST | Eliminar | Borra el empleado y sus documentos, previa confirmación |
| `/resumen` | GET | | Recorre los expedientes y cuenta cuántos hay de cada clasificación |
| `/api/expediente/<id>` | GET | Consultar | Devuelve en JSON el estado del expediente, como en la Fase 1 |

Todas las sentencias SQL usan parámetros con `?`. Ningún texto escrito por el usuario se concatena dentro de una sentencia. Los `UPDATE` y `DELETE` siempre llevan `WHERE`.

## Base de datos (`hospital.db`)

**Tabla `checklist`**: documentos que exige cada perfil.

| Campo | Tipo | Descripción |
|---|---|---|
| id | INTEGER | Llave primaria |
| perfil | TEXT | administrativo o medico |
| documento | TEXT | Nombre del documento requerido |

**Tabla `empleados`** (tabla principal):

| Campo | Tipo | Descripción |
|---|---|---|
| id | INTEGER | Llave primaria |
| nombre | TEXT | Nombre completo |
| perfil | TEXT | Perfil del puesto; define el checklist |
| departamento | TEXT | Departamento donde trabaja |
| fechaIngreso | TEXT | Fecha de ingreso (AAAA-MM-DD) |

**Tabla `documentos`**: el expediente, con un registro por cada documento del checklist del empleado.

| Campo | Tipo | Descripción |
|---|---|---|
| id | INTEGER | Llave primaria |
| empleadoId | INTEGER | Empleado dueño del documento |
| documento | TEXT | Nombre del documento |
| estado | TEXT | pendiente o entregado |
| version | INTEGER | Número de versión: 0 sin entregar, y sube con cada entrega o renovación |
| fechaActualizacion | TEXT | Fecha del último cambio |

## Validaciones

**Registrar empleado:** no guarda y muestra un mensaje si algún campo está vacío, si el nombre tiene números o símbolos, si el perfil no existe en el checklist o si la fecha de ingreso no es válida o es futura. Si los datos son correctos, guarda y redirige al listado.

**Actualizar documento** (la misma lógica de la Fase 1):

| Acción | Si el documento está pendiente | Si el documento está entregado |
|---|---|---|
| Entregar (documento nuevo) | Pasa a entregado y sube la versión | Error: el documento ya existía, usar nueva versión |
| Nueva versión (renovación) | Error: no se ha entregado | Sigue entregado y sube la versión, conservando su historial |
| Marcar pendiente | Error: ya está pendiente | Pasa a pendiente y conserva el número de versión |

## Cómo funciona el resumen

La ruta `/resumen` usa la función `obtenerExpedientes()`, que hace lo siguiente:

1. Lee todos los empleados de la base de datos.
2. Los recorre con `for`. Para cada empleado lee sus documentos y los recorre con otro `for`, contando cuántos tienen estado `entregado`.
3. Con `evaluarEstado()` decide su estado comparando los documentos entregados con los requeridos por su perfil:
   - 0 entregados → **sin iniciar**
   - menos de los requeridos → **incompleto**
   - igual a los requeridos → **completo**

Luego el resumen recorre esa lista con un `for` y, con `if/elif/else`, suma 1 al contador correspondiente (`completos`, `incompletos` o `sinIniciar`). En pantalla se muestra el total de cada clasificación en una tarjeta de color: verde para completo, amarillo para incompleto y gris para sin iniciar. También se muestra la tabla de empleados con cada fila coloreada según su clasificación.

## Parte del código desarrollada por cada integrante

- **Diego Peralta**: base de datos (`crear_bd.py`), conexión, función de estado de la Fase 1 adaptada a SQLite, listado de empleados, plantilla base y hoja de estilos inicial.
- **Maria Guirola**: registro de empleados con validación (`/empleados/nuevo`, `nuevo.html`).
- **Italo Vidaurre**: consulta del expediente y modificación de documentos con la lógica de versiones (`/empleados/<id>`, `/documentos/editar/<id>`, ruta JSON).
- **Carlos Moises**: eliminación de empleados con confirmación (`/empleados/eliminar/<id>`), resumen con repetición, decisión y contadores (`/resumen`, `resumen.html`) y colores de cada clasificación en `style.css`.
