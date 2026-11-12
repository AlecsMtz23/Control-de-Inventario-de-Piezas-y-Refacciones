"""Prueba rápida de extremo a extremo con una base de datos temporal.

Ejecutar:  python smoke_test.py
"""
import os
import re
import sqlite3
import tempfile

tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
tmp.close()
os.remove(tmp.name)
os.environ["MIN_DB"] = tmp.name

import app as m  # noqa: E402  (la BD se crea al importar)

app = m.app


def client_as(usuario, password):
    c = app.test_client()
    r = c.post("/login", data={"username": usuario, "password": password}, follow_redirects=True)
    assert r.status_code == 200 and "Dashboard" in r.text, f"login {usuario}"
    with c.session_transaction() as s:
        c.csrf = s["csrf_token"]
    return c


def stock(codigo):
    with sqlite3.connect(tmp.name) as db:
        return db.execute("SELECT cantidad FROM piezas WHERE codigo=?", (codigo,)).fetchone()[0]


def pid(codigo):
    with sqlite3.connect(tmp.name) as db:
        return db.execute("SELECT id FROM piezas WHERE codigo=?", (codigo,)).fetchone()[0]


# RF1: login y rechazo de credenciales inválidas
anon = app.test_client()
assert anon.get("/").status_code == 302, "sin sesión debe redirigir"
r = anon.post("/login", data={"username": "admin", "password": "mala"})
assert "incorrectos" in r.text

admin = client_as("admin", "Admin2026!")
gerente = client_as("gerente", "Gerente2026!")
tecnico = client_as("tecnico1", "Tecnico2026!")

# RF3: 20+ piezas iniciales
with sqlite3.connect(tmp.name) as db:
    assert db.execute("SELECT COUNT(*) FROM piezas").fetchone()[0] >= 20

# RF2/RF8: dashboard con alertas
r = admin.get("/")
assert "Resumen general" in r.text and "Alertas de inventario" in r.text and "P011" in r.text

# RF4: búsqueda y permisos
assert "Sensor inductivo" in tecnico.get("/piezas?q=sensor").text
assert tecnico.get("/piezas/nueva").status_code == 403
assert tecnico.get("/usuarios").status_code == 403
assert gerente.get("/usuarios").status_code == 403
assert tecnico.get("/movimientos").status_code == 403

# Administrador: alta, edición (ajuste), entrada y eliminación
r = admin.post("/piezas/nueva", data={"csrf_token": admin.csrf, "codigo": "P099", "nombre": "Pieza prueba",
                                      "categoria": "Mecánico", "cantidad": "5", "minimo": "2",
                                      "ubicacion": "Taller"}, follow_redirects=True)
assert "registrada" in r.text and stock("P099") == 5
r = admin.post(f"/piezas/{pid('P099')}/editar", data={"csrf_token": admin.csrf, "codigo": "P099", "nombre": "Pieza prueba",
                                                      "categoria": "Mecánico", "cantidad": "8", "minimo": "2",
                                                      "ubicacion": "Taller"}, follow_redirects=True)
assert stock("P099") == 8
admin.post("/inventario/entrada", data={"csrf_token": admin.csrf, "pieza_id": pid("P099"), "cantidad": "2",
                                        "referencia": "Factura X"})
assert stock("P099") == 10
assert admin.post(f"/piezas/{pid('P099')}/eliminar", data={"csrf_token": "x"}).status_code == 400  # CSRF
admin.post(f"/piezas/{pid('P099')}/eliminar", data={"csrf_token": admin.csrf})
with sqlite3.connect(tmp.name) as db:
    assert not db.execute("SELECT 1 FROM piezas WHERE codigo='P099'").fetchone()

# RF5: solicitud del técnico
antes = stock("P003")
r = tecnico.post("/solicitudes/nueva", data={"csrf_token": tecnico.csrf, "pieza_id": pid("P003"), "cantidad": "5",
                                             "motivo": "OT-1 prueba"}, follow_redirects=True)
assert "enviada" in r.text
sid = int(re.search(r"SOL-(\d+)", r.text).group(1))
assert stock("P003") == antes, "no debe descontar antes de aprobar"
r = tecnico.post("/solicitudes/nueva", data={"csrf_token": tecnico.csrf, "pieza_id": pid("P003"), "cantidad": "999",
                                             "motivo": "excede"}, follow_redirects=True)
assert "Solo hay" in r.text

# RF6/RF7/RF9: aprobación descuenta existencias y registra salida
assert tecnico.post(f"/solicitudes/{sid}/aprobar", data={"csrf_token": tecnico.csrf}).status_code == 403
gerente.post(f"/solicitudes/{sid}/aprobar", data={"csrf_token": gerente.csrf, "comentario": "ok"})
assert stock("P003") == antes - 5
r = gerente.post(f"/solicitudes/{sid}/aprobar", data={"csrf_token": gerente.csrf}, follow_redirects=True)
assert "ya fue" in r.text and stock("P003") == antes - 5, "no se aprueba dos veces"
assert "SOL-%03d" % sid in gerente.get("/movimientos?tipo=Salida").text

# Rechazo no altera existencias
tecnico.post("/solicitudes/nueva", data={"csrf_token": tecnico.csrf, "pieza_id": pid("P004"), "cantidad": "3", "motivo": "x"})
with sqlite3.connect(tmp.name) as db:
    sid2 = db.execute("SELECT MAX(id) FROM solicitudes").fetchone()[0]
s4 = stock("P004")
gerente.post(f"/solicitudes/{sid2}/rechazar", data={"csrf_token": gerente.csrf})
assert stock("P004") == s4
assert "Rechazada" in tecnico.get("/solicitudes").text

# Reportes y CSV
assert "Existencias por categoría" in gerente.get("/reportes").text
assert gerente.get("/reportes/inventario.csv").data.startswith("﻿".encode())

# Administración de usuarios
r = admin.post("/usuarios/nuevo", data={"csrf_token": admin.csrf, "usuario": "tecnico3", "nombre": "Prueba",
                                        "rol": "Técnico", "password": "Prueba123!", "activo": "on"}, follow_redirects=True)
assert "guardado" in r.text
client_as("tecnico3", "Prueba123!")

try:
    os.remove(tmp.name)
except OSError:
    pass  # Windows puede mantener el archivo abierto un instante
print("OK: todas las pruebas pasaron.")
