
Control de Inventario de Piezas y Refacciones — MIN
Aplicación web para controlar el almacén de Mantenimiento Industrial del Norte. Tiene tres tipos de usuario: Administrador, Gerente y Técnico.

Cómo ejecutarla
1. Instalar Python (solo si no lo tiene)
Descargar Python 3.10 o más reciente desde https://www.python.org/downloads/. En el instalador, marcar la casilla "Add Python to PATH".

2. Descargar el proyecto
En GitHub, presionar el botón verde Code → Download ZIP y descomprimir la carpeta.

3. Abrir una terminal dentro de la carpeta
En Windows: abrir la carpeta descomprimida, hacer clic en la barra de dirección, escribir cmd y presionar Enter.

4. Instalar lo necesario (solo la primera vez)
pip install -r requirements.txt
5. Iniciar la aplicación
python app.py
6. Abrir en el navegador
Entrar a http://127.0.0.1:5000

Para detener la aplicación, presionar Ctrl + C en la terminal.

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

