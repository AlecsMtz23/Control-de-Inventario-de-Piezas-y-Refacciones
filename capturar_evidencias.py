"""Recorre la aplicación en un navegador real y guarda las capturas de evidencia.

Requiere:  pip install playwright   (usa el Google Chrome instalado)
Ejecutar:  python capturar_evidencias.py
Reinicia la base de datos de demostración y guarda las imágenes en evidencias/.
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
OUT = BASE / "evidencias"
OUT.mkdir(exist_ok=True)
DB = BASE / "data" / "inventario.sqlite3"
PORT = 5057
URL = f"http://127.0.0.1:{PORT}"

if DB.exists():
    DB.unlink()
server = subprocess.Popen([sys.executable, "app.py"], cwd=BASE, env={**os.environ, "PORT": str(PORT)})
for _ in range(50):
    try:
        urllib.request.urlopen(URL + "/login")
        break
    except OSError:
        time.sleep(0.2)


def shot(page, name, full=False):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    print("captura", name)


def login(page, user, pw):
    page.goto(URL + "/login")
    page.fill("input[name=username]", user)
    page.fill("input[name=password]", pw)
    page.click("button")
    page.wait_for_url(URL + "/")


def logout(page):
    page.click("button.logout")


def crear_solicitud(page, codigo, cantidad, motivo):
    page.goto(URL + "/solicitudes/nueva")
    page.select_option("select[name=pieza_id]", label=page.locator(
        f"select[name=pieza_id] option:has-text('{codigo} ·')").inner_text().strip())
    page.fill("input[name=cantidad]", str(cantidad))
    page.fill("textarea[name=motivo]", motivo)


def resolver(page, folio, accion, comentario=""):
    row = page.locator("tr", has_text=folio)
    row.locator("input[name=comentario]").fill(comentario)
    row.locator(f"button:has-text('{accion}')").click()


try:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1400, "height": 860}, device_scale_factor=1.25, locale="es-MX")
        page.on("dialog", lambda d: d.accept())

        # Historial previo (para que el sistema tenga datos realistas)
        login(page, "tecnico2", "Tecnico2026!")
        crear_solicitud(page, "P001", 4, "OT-2301 · Cambio de rodamientos en bomba de enfriamiento"); page.click("button.primary")
        crear_solicitud(page, "P017", 2, "OT-2302 · Lubricación preventiva de transportador"); page.click("button.primary")
        crear_solicitud(page, "P009", 1, "OT-2303 · Reemplazo de cilindro en prensa 3"); page.click("button.primary")
        logout(page)
        login(page, "gerente", "Gerente2026!")
        page.goto(URL + "/solicitudes?estado=Pendiente")
        resolver(page, "SOL-001", "Aprobar", "Autorizado para mantenimiento preventivo")
        resolver(page, "SOL-003", "Rechazar", "Usar cilindro reacondicionado del taller")
        logout(page)

        # 1. Inicio de sesión
        page.goto(URL + "/login")
        shot(page, "01_login")
        page.fill("input[name=username]", "admin"); page.fill("input[name=password]", "incorrecta"); page.click("button")
        shot(page, "02_login_error")

        # 2. Administrador
        login(page, "admin", "Admin2026!")
        shot(page, "03_admin_dashboard", full=True)
        page.goto(URL + "/piezas")
        shot(page, "04_admin_piezas", full=True)
        page.goto(URL + "/piezas/nueva")
        page.fill("input[name=codigo]", "P025")
        page.fill("input[name=nombre]", "Rodamiento cónico 30205")
        page.select_option("select[name=categoria]", "Rodamientos")
        page.fill("input[name=cantidad]", "12")
        page.fill("input[name=minimo]", "4")
        page.fill("input[name=ubicacion]", "Almacén Principal - Rack A5")
        shot(page, "05_admin_agregar_pieza")
        page.click("button.primary")
        page.wait_for_url(URL + "/piezas")
        page.locator("tr", has_text="P025").scroll_into_view_if_needed()
        page.evaluate("window.scrollTo(0, 0)")
        shot(page, "06_admin_pieza_registrada", full=True)
        page.goto(URL + "/piezas?q=P006")
        page.locator("a[title=Editar]").first.click()
        shot(page, "07_admin_editar_pieza")
        page.goto(URL + "/inventario/entrada")
        page.select_option("select[name=pieza_id]", label=page.locator("select[name=pieza_id] option:has-text('P006 ·')").inner_text().strip())
        page.fill("input[name=cantidad]", "10")
        page.fill("input[name=referencia]", "Factura F-1029 · Motores del Norte")
        shot(page, "08_admin_recibir_inventario")
        page.click("button.primary")
        shot(page, "09_admin_entrada_registrada")
        page.goto(URL + "/usuarios")
        shot(page, "10_admin_usuarios")
        page.goto(URL + "/usuarios/nuevo")
        page.fill("input[name=usuario]", "tecnico3")
        page.fill("input[name=nombre]", "Luis Medina")
        page.select_option("select[name=rol]", "Técnico")
        page.fill("input[name=password]", "Tecnico2026!")
        page.click("button.primary")
        shot(page, "11_admin_usuario_creado")
        logout(page)

        # 3. Técnico: consulta y solicitud
        login(page, "tecnico1", "Tecnico2026!")
        shot(page, "12_tecnico_dashboard", full=True)
        page.goto(URL + "/piezas?q=sensor")
        shot(page, "13_tecnico_busqueda")
        crear_solicitud(page, "P003", 5, "OT-2311 · Cambio de sensor en línea de empaque 2")
        shot(page, "14_tecnico_nueva_solicitud")
        page.click("button.primary")
        shot(page, "15_tecnico_solicitud_enviada")
        crear_solicitud(page, "P004", 10, "OT-2312 · Reposición de fusibles en tablero principal"); page.click("button.primary")
        page.goto(URL + "/usuarios")
        shot(page, "16_tecnico_acceso_denegado")
        logout(page)

        # 4. Gerente: autorización
        login(page, "gerente", "Gerente2026!")
        shot(page, "17_gerente_dashboard", full=True)
        page.goto(URL + "/piezas?q=P003")
        shot(page, "18_stock_antes")
        page.goto(URL + "/solicitudes?estado=Pendiente")
        page.locator("tr", has_text="SOL-004").locator("input[name=comentario]").fill("Autorizado para OT-2311")
        shot(page, "19_gerente_por_autorizar")
        resolver(page, "SOL-004", "Aprobar", "Autorizado para OT-2311")
        shot(page, "20_gerente_solicitud_aprobada")
        page.goto(URL + "/piezas?q=P003")
        shot(page, "21_stock_despues")
        page.goto(URL + "/movimientos?q=SOL-004")
        shot(page, "22_movimiento_salida")
        page.goto(URL + "/movimientos")
        shot(page, "23_movimientos", full=True)
        page.goto(URL + "/reportes")
        shot(page, "24_gerente_reportes", full=True)
        page.goto(URL + "/piezas?estado=bajo")
        shot(page, "25_alertas_stock_bajo")
        page.goto(URL + "/piezas?estado=sin")
        shot(page, "26_alertas_agotadas")
        logout(page)

        # 5. Técnico revisa el estado
        login(page, "tecnico1", "Tecnico2026!")
        page.goto(URL + "/solicitudes")
        shot(page, "27_tecnico_estado_solicitudes")

        # Vista móvil
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        login(mobile, "gerente", "Gerente2026!")
        shot(mobile, "28_vista_movil")
        browser.close()
finally:
    server.terminate()
