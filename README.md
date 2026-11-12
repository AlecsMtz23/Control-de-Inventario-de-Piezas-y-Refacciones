
Control de Inventario de Piezas y Refacciones — MIN
Aplicación web para controlar el almacén de Mantenimiento Industrial del Norte. Tiene tres tipos de usuario: Administrador, Gerente y Técnico.

Cómo ejecutarla
Requisito: Python 3.10 o más reciente. La única dependencia es Flask (requirements.txt).

Primero, clonar o descargar el repositorio (Code → Download ZIP) y entrar a la carpeta.

Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
En Debian/Ubuntu, si venv no está instalado: sudo apt install python3-venv

Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
Abrir en el navegador
Entrar a http://127.0.0.1:5000. Para detener la aplicación: Ctrl + C en la terminal.

Las siguientes veces solo hay que activar el entorno (source .venv/bin/activate o .venv\Scripts\activate) y ejecutar python app.py.

Usuarios y contraseñas
Rol	Usuario	Contraseña
Administrador	admin	Admin2026!
Gerente	gerente	Gerente2026!
Técnico	tecnico1	Tecnico2026!
Técnico	tecnico2	Tecnico2026!
Qué puede hacer cada usuario
Administrador: agregar, editar y eliminar piezas; registrar entradas de inventario; administrar usuarios; ver movimientos y reportes.
Gerente: consultar el inventario; aprobar o rechazar solicitudes; ver movimientos y generar reportes.
Técnico: consultar y buscar piezas; crear solicitudes de material; revisar el estado de sus solicitudes.
Prueba sugerida del proceso completo
Entrar como tecnico1 → Solicitudes → Nueva solicitud → pedir una pieza.
Cerrar sesión y entrar como gerente → Solicitudes → Aprobar.
En Piezas se ve que la cantidad bajó, y en Movimientos aparece la salida registrada.
Nota: al iniciar por primera vez, la aplicación crea sola la base de datos con 24 piezas y los usuarios de la tabla. Para volver a empezar desde cero, cerrar la aplicación y borrar la carpeta data.

