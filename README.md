# MIN — Sistema web de inventario de piezas y refacciones

Aplicación web para **Mantenimiento Industrial del Norte (MIN)** que controla las piezas y refacciones del almacén. Sustituye el registro manual por un sistema con tres roles, solicitudes de material con autorización, actualización automática de existencias, alertas de stock y bitácora de movimientos.

Hecha con **Python 3 + Flask**, **SQLite**, **HTML5 / Jinja2**, **CSS3** y **JavaScript** (sin frameworks externos).

## Funciones por rol

| Rol | Puede hacer |
|---|---|
| **Administrador** | Registrar, modificar y eliminar piezas; recibir inventario (entradas); administrar usuarios (alta, edición, desactivación); consultar movimientos y reportes. |
| **Gerente** | Consultar inventario; aprobar o rechazar solicitudes de material; consultar movimientos; generar reportes y exportarlos a CSV. |
| **Técnico** | Consultar y buscar piezas disponibles; crear solicitudes de material; revisar el estado de sus solicitudes. |

## Requisitos del caso de estudio cubiertos

1. Inicio de sesión para los tres tipos de usuarios (contraseñas con hash).
2. Dashboard con resumen del inventario, gráfica de estado, alertas, solicitudes y últimos movimientos.
3. 24 piezas industriales precargadas (código, nombre, categoría, cantidad, stock mínimo y ubicación).
4. Consulta, búsqueda, filtros y administración de piezas según permisos.
5. Solicitudes de materiales creadas por técnicos.
6. Aprobación o rechazo por el gerente (con comentario).
7. Descuento automático y atómico de existencias al aprobar una salida.
8. Alertas de piezas agotadas y con existencias bajas (dashboard, campana y filtros).
9. Registro de movimientos de entrada, salida y ajuste con usuario, fecha y existencia resultante.

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abrir <http://127.0.0.1:5000>. La primera ejecución crea `data/inventario.sqlite3` con las piezas y estas cuentas de demostración:

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `Admin2026!` | Administrador |
| `gerente` | `Gerente2026!` | Gerente |
| `tecnico1` | `Tecnico2026!` | Técnico |
| `tecnico2` | `Tecnico2026!` | Técnico |

Las contraseñas pueden cambiarse antes de la primera ejecución con las variables `MIN_PASS_ADMIN`, `MIN_PASS_GERENTE`, `MIN_PASS_TECNICO1` y `MIN_PASS_TECNICO2`. Para reiniciar los datos, elimina `data/inventario.sqlite3`.

## Pruebas y evidencias

- `python smoke_test.py` ejecuta una prueba de extremo a extremo (login, permisos, alta/edición/eliminación de piezas, solicitud, aprobación, rechazo, descuento de stock, movimientos, reportes y usuarios) sobre una base temporal.
- `python capturar_evidencias.py` (requiere `pip install playwright` y Google Chrome) reinicia la base de demostración, recorre la aplicación con los tres roles y guarda las capturas en `evidencias/`.

## Estructura

```
app.py                  rutas, reglas de negocio y base de datos
templates/              vistas Jinja2 (login, dashboard, piezas, solicitudes, movimientos, reportes, usuarios)
static/style.css        estilos y diseño adaptable
smoke_test.py           prueba automatizada
capturar_evidencias.py  generación de capturas
evidencias/             capturas del funcionamiento
```

## Seguridad

Contraseñas con hash (Werkzeug), sesión con cookie `HttpOnly`/`SameSite=Lax`, token CSRF en todos los formularios que modifican datos, control de acceso por rol en el servidor (HTTP 403), consultas SQL parametrizadas y protección contra fórmulas en los CSV. Para un uso real, cambia las contraseñas iniciales y publica detrás de HTTPS con un servidor WSGI de producción.
