"""MIN - Sistema web de inventario para Mantenimiento Industrial del Norte.

Aplicación Flask con tres roles (Administrador, Gerente y Técnico) que controla
piezas y refacciones, solicitudes de material, autorizaciones, alertas de stock
y movimientos de entrada/salida del almacén.
"""
import csv
import io
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DB = Path(os.getenv("MIN_DB", DATA / "inventario.sqlite3"))
DATA.mkdir(exist_ok=True)

secret_path = DATA / ".secret_key"
if not secret_path.exists():
    secret_path.write_text(secrets.token_hex(32), encoding="utf-8")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY") or secret_path.read_text(encoding="utf-8"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

ROLES = ("Administrador", "Gerente", "Técnico")
CATEGORIAS = ("Eléctrico", "Mecánico", "Neumático", "Hidráulico", "Rodamientos",
              "Sensores", "Transmisión", "Lubricantes", "Otro")
UBICACIONES = ("Almacén Principal", "Almacén Secundario", "Taller")

# 20+ piezas industriales iniciales: código, nombre, categoría, cantidad, mínimo, ubicación (rack)
PIEZAS_INICIALES = [
    ("P001", "Rodamiento de bolas 6204", "Rodamientos", 48, 15, "Almacén Principal - Rack A1"),
    ("P002", "Banda en V tipo A-42", "Transmisión", 30, 10, "Almacén Principal - Rack B2"),
    ("P003", "Sensor inductivo M18", "Sensores", 15, 5, "Almacén Principal - Rack C1"),
    ("P004", "Fusible cerámico 10 A", "Eléctrico", 50, 20, "Almacén Principal - Rack D3"),
    ("P005", "Contactor trifásico 25 A", "Eléctrico", 12, 4, "Almacén Principal - Rack D1"),
    ("P006", "Motor DC 24 V", "Eléctrico", 4, 10, "Almacén Secundario - Rack E2"),
    ("P007", "Relevador térmico 9-13 A", "Eléctrico", 9, 4, "Almacén Principal - Rack D2"),
    ("P008", "Sensor óptico difuso", "Sensores", 2, 5, "Almacén Principal - Rack C2"),
    ("P009", "Cilindro neumático 50x100 mm", "Neumático", 7, 3, "Almacén Secundario - Rack F1"),
    ("P010", "Electroválvula 5/2 24 VDC", "Neumático", 11, 4, "Almacén Secundario - Rack F2"),
    ("P011", "Banda transportadora industrial 2 m", "Transmisión", 0, 5, "Almacén Secundario - Rack B4"),
    ("P012", "Aceite hidráulico ISO 68 (19 L)", "Lubricantes", 14, 6, "Almacén Secundario - Zona L"),
    ("P013", "Rodamiento rígido 6001", "Rodamientos", 3, 10, "Almacén Principal - Rack A2"),
    ("P014", "Cadena de rodillos ANSI 40 (3 m)", "Transmisión", 18, 6, "Almacén Principal - Rack B1"),
    ("P015", "Bomba hidráulica de engranes", "Hidráulico", 3, 2, "Almacén Secundario - Rack G1"),
    ("P016", "Manguera hidráulica 1/2\" (1 m)", "Hidráulico", 40, 12, "Almacén Secundario - Rack G2"),
    ("P017", "Grasa de litio EP2 (400 g)", "Lubricantes", 25, 10, "Almacén Secundario - Zona L"),
    ("P018", "Retén de aceite 35x52x7", "Mecánico", 60, 20, "Almacén Principal - Rack A3"),
    ("P019", "Acoplamiento flexible tipo L-100", "Mecánico", 6, 3, "Almacén Principal - Rack B3"),
    ("P020", "Variador de frecuencia 2 HP", "Eléctrico", 2, 1, "Taller - Gabinete 1"),
    ("P021", "Engrane recto 40 dientes", "Mecánico", 8, 3, "Almacén Principal - Rack B5"),
    ("P022", "Filtro de aire FRL 1/4\"", "Neumático", 0, 3, "Almacén Secundario - Rack F3"),
    ("P023", "Termopar tipo K", "Sensores", 10, 4, "Almacén Principal - Rack C3"),
    ("P024", "Tornillo hexagonal M10x40 (caja 50)", "Mecánico", 22, 8, "Almacén Principal - Rack A4"),
]

USUARIOS_INICIALES = [
    ("admin", "Laura Hernández", "Administrador", "MIN_PASS_ADMIN", "Admin2026!"),
    ("gerente", "Ricardo Salas", "Gerente", "MIN_PASS_GERENTE", "Gerente2026!"),
    ("tecnico1", "Jorge Ramírez", "Técnico", "MIN_PASS_TECNICO1", "Tecnico2026!"),
    ("tecnico2", "Ana Torres", "Técnico", "MIN_PASS_TECNICO2", "Tecnico2026!"),
]


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@contextmanager
def connection():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def init_db():
    with connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                rol TEXT NOT NULL CHECK (rol IN ('Administrador','Gerente','Técnico')),
                password_hash TEXT NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS piezas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                categoria TEXT NOT NULL,
                cantidad INTEGER NOT NULL CHECK (cantidad >= 0),
                minimo INTEGER NOT NULL CHECK (minimo >= 0),
                ubicacion TEXT NOT NULL,
                actualizado TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS solicitudes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tecnico_id INTEGER NOT NULL REFERENCES usuarios(id),
                pieza_id INTEGER NOT NULL REFERENCES piezas(id),
                cantidad INTEGER NOT NULL CHECK (cantidad > 0),
                motivo TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'Pendiente'
                    CHECK (estado IN ('Pendiente','Aprobada','Rechazada')),
                creada TEXT NOT NULL,
                gerente_id INTEGER REFERENCES usuarios(id),
                resuelta TEXT,
                comentario TEXT
            );
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pieza_id INTEGER REFERENCES piezas(id) ON DELETE SET NULL,
                codigo TEXT NOT NULL,
                pieza TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN ('Entrada','Salida','Ajuste')),
                cantidad INTEGER NOT NULL,
                existencia INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                referencia TEXT NOT NULL,
                fecha TEXT NOT NULL
            );
        """)
        if not db.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            for usuario, nombre, rol, env, fallback in USUARIOS_INICIALES:
                db.execute("INSERT INTO usuarios (usuario, nombre, rol, password_hash) VALUES (?,?,?,?)",
                           (usuario, nombre, rol, generate_password_hash(os.getenv(env, fallback))))
        if not db.execute("SELECT 1 FROM piezas LIMIT 1").fetchone():
            admin_id = db.execute("SELECT id FROM usuarios WHERE rol='Administrador' ORDER BY id").fetchone()[0]
            for codigo, nombre, cat, cant, minimo, ubic in PIEZAS_INICIALES:
                cur = db.execute(
                    "INSERT INTO piezas (codigo, nombre, categoria, cantidad, minimo, ubicacion, actualizado) "
                    "VALUES (?,?,?,?,?,?,?)", (codigo, nombre, cat, cant, minimo, ubic, ahora()))
                if cant:
                    registrar_movimiento(db, cur.lastrowid, "Entrada", cant, admin_id, "Inventario inicial")


def registrar_movimiento(db, pieza_id, tipo, cantidad, usuario_id, referencia):
    pieza = db.execute("SELECT * FROM piezas WHERE id = ?", (pieza_id,)).fetchone()
    db.execute(
        "INSERT INTO movimientos (pieza_id, codigo, pieza, tipo, cantidad, existencia, usuario_id, referencia, fecha) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (pieza_id, pieza["codigo"], pieza["nombre"], tipo, cantidad, pieza["cantidad"],
         usuario_id, referencia, ahora()))


init_db()


# ----------------------------------------------------------------- utilidades
def usuario_actual():
    if "uid" not in session:
        return None
    with connection() as db:
        return db.execute("SELECT * FROM usuarios WHERE id = ? AND activo = 1", (session["uid"],)).fetchone()


def login_required(*roles):
    """Exige sesión iniciada y, opcionalmente, uno de los roles indicados."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = usuario_actual()
            if user is None:
                session.clear()
                return redirect(url_for("login"))
            if roles and user["rol"] not in roles:
                abort(403)
            request.user = user
            return view(*args, **kwargs)
        return wrapped
    return decorator


def check_csrf():
    if not secrets.compare_digest(session.get("csrf_token", ""), request.form.get("csrf_token", "")):
        abort(400, "Formulario vencido. Recarga la página e inténtalo de nuevo.")


def estado_stock(p):
    if p["cantidad"] == 0:
        return "Sin stock"
    if p["cantidad"] <= p["minimo"]:
        return "Stock bajo"
    return "En stock"


def folio(sol_id):
    return f"SOL-{sol_id:03d}"


def entero(valor, nombre, minimo=0, maximo=100000):
    try:
        n = int(str(valor).strip())
    except ValueError:
        raise ValueError(f"{nombre} debe ser un número entero.")
    if n < minimo or n > maximo:
        raise ValueError(f"{nombre} debe estar entre {minimo} y {maximo}.")
    return n


def alertas(db):
    return db.execute("SELECT * FROM piezas WHERE cantidad <= minimo "
                      "ORDER BY cantidad = 0 DESC, cantidad * 1.0 / MAX(minimo, 1), codigo").fetchall()


@app.context_processor
def common():
    user = usuario_actual() if "uid" in session else None
    data = {"csrf_token": session.get("csrf_token", ""), "user": user, "estado_stock": estado_stock,
            "folio": folio, "ROLES": ROLES, "CATEGORIAS": CATEGORIAS}
    if user:
        with connection() as db:
            data["num_alertas"] = db.execute("SELECT COUNT(*) FROM piezas WHERE cantidad <= minimo").fetchone()[0]
            data["num_pendientes"] = db.execute(
                "SELECT COUNT(*) FROM solicitudes WHERE estado='Pendiente'").fetchone()[0]
    return data


SOLICITUDES_SQL = """
    SELECT s.*, p.codigo, p.nombre AS pieza, p.cantidad AS stock, t.nombre AS tecnico,
           g.nombre AS gerente
    FROM solicitudes s
    JOIN piezas p ON p.id = s.pieza_id
    JOIN usuarios t ON t.id = s.tecnico_id
    LEFT JOIN usuarios g ON g.id = s.gerente_id
"""


# ----------------------------------------------------------------- sesión
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("username", "").strip().lower()
        with connection() as db:
            user = db.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
        if user and user["activo"] and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"] = user["id"]
            session["csrf_token"] = secrets.token_hex(32)
            flash(f"Bienvenido(a), {user['nombre']} ({user['rol']}).", "ok")
            return redirect(url_for("dashboard"))
        flash("Usuario o contraseña incorrectos, o la cuenta está desactivada.", "error")
    return render_template("login.html")


@app.post("/logout")
@login_required()
def logout():
    check_csrf()
    session.clear()
    flash("Sesión cerrada correctamente.", "ok")
    return redirect(url_for("login"))


# ----------------------------------------------------------------- dashboard
@app.get("/")
@login_required()
def dashboard():
    user = request.user
    with connection() as db:
        total = db.execute("SELECT COUNT(*) FROM piezas").fetchone()[0]
        unidades = db.execute("SELECT COALESCE(SUM(cantidad),0) FROM piezas").fetchone()[0]
        sin = db.execute("SELECT COUNT(*) FROM piezas WHERE cantidad = 0").fetchone()[0]
        bajo = db.execute("SELECT COUNT(*) FROM piezas WHERE cantidad > 0 AND cantidad <= minimo").fetchone()[0]
        lista_alertas = alertas(db)
        if user["rol"] == "Técnico":
            solicitudes = db.execute(SOLICITUDES_SQL + " WHERE s.tecnico_id = ? ORDER BY s.id DESC LIMIT 5",
                                     (user["id"],)).fetchall()
        else:
            solicitudes = db.execute(SOLICITUDES_SQL + " WHERE s.estado = 'Pendiente' ORDER BY s.id LIMIT 5").fetchall()
        movimientos = db.execute("SELECT m.*, u.nombre AS usuario FROM movimientos m "
                                 "JOIN usuarios u ON u.id = m.usuario_id ORDER BY m.id DESC LIMIT 6").fetchall()
        categorias = db.execute("SELECT categoria, COUNT(*) n, SUM(cantidad) u FROM piezas "
                                "GROUP BY categoria ORDER BY u DESC").fetchall()
    ok = total - sin - bajo
    pct = lambda n: round(n * 100 / total, 1) if total else 0
    return render_template("dashboard.html", total=total, unidades=unidades, ok=ok, bajo=bajo, sin=sin,
                           p_ok=pct(ok), p_bajo=pct(bajo), p_sin=pct(sin), alertas=lista_alertas,
                           solicitudes=solicitudes, movimientos=movimientos, categorias=categorias)


# ----------------------------------------------------------------- piezas
@app.get("/piezas")
@login_required()
def piezas():
    q = request.args.get("q", "").strip()[:80]
    cat = request.args.get("categoria", "")
    est = request.args.get("estado", "")
    sql, args = "SELECT * FROM piezas WHERE (codigo LIKE ? OR nombre LIKE ? OR ubicacion LIKE ?)", [f"%{q}%"] * 3
    if cat in CATEGORIAS:
        sql += " AND categoria = ?"
        args.append(cat)
    if est == "sin":
        sql += " AND cantidad = 0"
    elif est == "bajo":
        sql += " AND cantidad > 0 AND cantidad <= minimo"
    elif est == "ok":
        sql += " AND cantidad > minimo"
    with connection() as db:
        lista = db.execute(sql + " ORDER BY codigo", args).fetchall()
    return render_template("piezas.html", piezas=lista, q=q, cat=cat, est=est)


def pieza_form():
    f = {k: request.form.get(k, "").strip() for k in ("codigo", "nombre", "categoria", "cantidad", "minimo", "ubicacion")}
    f["codigo"] = f["codigo"].upper()
    if not f["codigo"] or len(f["codigo"]) > 15 or not f["codigo"].replace("-", "").isalnum():
        raise ValueError("El código es obligatorio (máx. 15 caracteres alfanuméricos).")
    if not f["nombre"] or len(f["nombre"]) > 100:
        raise ValueError("El nombre es obligatorio (máx. 100 caracteres).")
    if f["categoria"] not in CATEGORIAS:
        raise ValueError("Selecciona una categoría válida.")
    if not f["ubicacion"] or len(f["ubicacion"]) > 80:
        raise ValueError("La ubicación es obligatoria (máx. 80 caracteres).")
    f["cantidad"] = entero(f["cantidad"], "La cantidad")
    f["minimo"] = entero(f["minimo"], "El stock mínimo")
    return f


@app.route("/piezas/nueva", methods=["GET", "POST"])
@login_required("Administrador")
def pieza_nueva():
    form = {}
    if request.method == "POST":
        check_csrf()
        form = request.form
        try:
            f = pieza_form()
            with connection() as db:
                cur = db.execute("INSERT INTO piezas (codigo, nombre, categoria, cantidad, minimo, ubicacion, actualizado) "
                                 "VALUES (?,?,?,?,?,?,?)", (f["codigo"], f["nombre"], f["categoria"], f["cantidad"],
                                                            f["minimo"], f["ubicacion"], ahora()))
                if f["cantidad"]:
                    registrar_movimiento(db, cur.lastrowid, "Entrada", f["cantidad"], request.user["id"], "Alta de pieza")
            flash(f"Pieza {f['codigo']} registrada correctamente.", "ok")
            return redirect(url_for("piezas"))
        except sqlite3.IntegrityError:
            flash("Ya existe una pieza con ese código.", "error")
        except ValueError as e:
            flash(str(e), "error")
    return render_template("pieza_form.html", form=form, pieza=None)


def get_pieza(db, pid):
    p = db.execute("SELECT * FROM piezas WHERE id = ?", (pid,)).fetchone()
    if p is None:
        abort(404)
    return p


@app.route("/piezas/<int:pid>/editar", methods=["GET", "POST"])
@login_required("Administrador")
def pieza_editar(pid):
    with connection() as db:
        pieza = get_pieza(db, pid)
    form = dict(pieza)
    if request.method == "POST":
        check_csrf()
        form = request.form
        try:
            f = pieza_form()
            with connection() as db:
                db.execute("UPDATE piezas SET codigo=?, nombre=?, categoria=?, cantidad=?, minimo=?, ubicacion=?, "
                           "actualizado=? WHERE id=?", (f["codigo"], f["nombre"], f["categoria"], f["cantidad"],
                                                         f["minimo"], f["ubicacion"], ahora(), pid))
                diff = f["cantidad"] - pieza["cantidad"]
                if diff:
                    registrar_movimiento(db, pid, "Ajuste", diff, request.user["id"], "Ajuste por edición de pieza")
            flash(f"Pieza {f['codigo']} actualizada.", "ok")
            return redirect(url_for("piezas"))
        except sqlite3.IntegrityError:
            flash("Ya existe otra pieza con ese código.", "error")
        except ValueError as e:
            flash(str(e), "error")
    return render_template("pieza_form.html", form=form, pieza=pieza)


@app.post("/piezas/<int:pid>/eliminar")
@login_required("Administrador")
def pieza_eliminar(pid):
    check_csrf()
    with connection() as db:
        pieza = get_pieza(db, pid)
        if db.execute("SELECT 1 FROM solicitudes WHERE pieza_id = ? AND estado = 'Pendiente'", (pid,)).fetchone():
            flash("No se puede eliminar: la pieza tiene solicitudes pendientes.", "error")
            return redirect(url_for("piezas"))
        if db.execute("SELECT 1 FROM solicitudes WHERE pieza_id = ?", (pid,)).fetchone():
            flash("No se puede eliminar: la pieza tiene historial de solicitudes. Ajusta su cantidad a 0.", "error")
            return redirect(url_for("piezas"))
        db.execute("DELETE FROM piezas WHERE id = ?", (pid,))
    flash(f"Pieza {pieza['codigo']} eliminada.", "ok")
    return redirect(url_for("piezas"))


@app.route("/inventario/entrada", methods=["GET", "POST"])
@login_required("Administrador")
def entrada():
    with connection() as db:
        lista = db.execute("SELECT * FROM piezas ORDER BY codigo").fetchall()
    if request.method == "POST":
        check_csrf()
        try:
            cant = entero(request.form.get("cantidad", ""), "La cantidad", 1)
            ref = request.form.get("referencia", "").strip()[:80] or "Recepción de proveedor"
            with connection() as db:
                pieza = get_pieza(db, entero(request.form.get("pieza_id", "0"), "La pieza", 1, 10**9))
                db.execute("UPDATE piezas SET cantidad = cantidad + ?, actualizado = ? WHERE id = ?",
                           (cant, ahora(), pieza["id"]))
                registrar_movimiento(db, pieza["id"], "Entrada", cant, request.user["id"], ref)
            flash(f"Entrada registrada: +{cant} de {pieza['codigo']} ({pieza['nombre']}).", "ok")
            return redirect(url_for("movimientos"))
        except ValueError as e:
            flash(str(e), "error")
    return render_template("entrada.html", piezas=lista, sel=request.args.get("pieza", type=int))


# ----------------------------------------------------------------- solicitudes
@app.get("/solicitudes")
@login_required()
def solicitudes():
    user = request.user
    est = request.args.get("estado", "")
    sql, args = SOLICITUDES_SQL + " WHERE 1=1", []
    if user["rol"] == "Técnico":
        sql += " AND s.tecnico_id = ?"
        args.append(user["id"])
    if est in ("Pendiente", "Aprobada", "Rechazada"):
        sql += " AND s.estado = ?"
        args.append(est)
    with connection() as db:
        lista = db.execute(sql + " ORDER BY s.estado = 'Pendiente' DESC, s.id DESC", args).fetchall()
    return render_template("solicitudes.html", solicitudes=lista, est=est)


@app.route("/solicitudes/nueva", methods=["GET", "POST"])
@login_required("Técnico")
def solicitud_nueva():
    with connection() as db:
        lista = db.execute("SELECT * FROM piezas ORDER BY codigo").fetchall()
    if request.method == "POST":
        check_csrf()
        try:
            cant = entero(request.form.get("cantidad", ""), "La cantidad", 1, 1000)
            motivo = request.form.get("motivo", "").strip()
            if not motivo or len(motivo) > 200:
                raise ValueError("Describe el motivo o la orden de trabajo (máx. 200 caracteres).")
            with connection() as db:
                pieza = get_pieza(db, entero(request.form.get("pieza_id", "0"), "La pieza", 1, 10**9))
                if cant > pieza["cantidad"]:
                    raise ValueError(f"Solo hay {pieza['cantidad']} unidades disponibles de {pieza['codigo']}.")
                cur = db.execute("INSERT INTO solicitudes (tecnico_id, pieza_id, cantidad, motivo, creada) "
                                 "VALUES (?,?,?,?,?)", (request.user["id"], pieza["id"], cant, motivo, ahora()))
            flash(f"Solicitud {folio(cur.lastrowid)} enviada al gerente para su autorización.", "ok")
            return redirect(url_for("solicitudes"))
        except ValueError as e:
            flash(str(e), "error")
    return render_template("solicitud_form.html", piezas=lista, sel=request.args.get("pieza", type=int))


@app.post("/solicitudes/<int:sid>/<accion>")
@login_required("Gerente")
def solicitud_resolver(sid, accion):
    check_csrf()
    if accion not in ("aprobar", "rechazar"):
        abort(404)
    comentario = request.form.get("comentario", "").strip()[:200]
    with connection() as db:
        sol = db.execute(SOLICITUDES_SQL + " WHERE s.id = ?", (sid,)).fetchone()
        if sol is None:
            abort(404)
        if sol["estado"] != "Pendiente":
            flash(f"La solicitud {folio(sid)} ya fue {sol['estado'].lower()}.", "error")
            return redirect(url_for("solicitudes"))
        if accion == "aprobar":
            # Descuento atómico: solo procede si hay existencias suficientes.
            cur = db.execute("UPDATE piezas SET cantidad = cantidad - ?, actualizado = ? "
                             "WHERE id = ? AND cantidad >= ?", (sol["cantidad"], ahora(), sol["pieza_id"], sol["cantidad"]))
            if cur.rowcount == 0:
                flash(f"No hay existencias suficientes de {sol['codigo']} (disponibles: {sol['stock']}).", "error")
                return redirect(url_for("solicitudes"))
            registrar_movimiento(db, sol["pieza_id"], "Salida", -sol["cantidad"], request.user["id"],
                                 f"{folio(sid)} - {sol['tecnico']}")
            estado = "Aprobada"
        else:
            estado = "Rechazada"
        db.execute("UPDATE solicitudes SET estado=?, gerente_id=?, resuelta=?, comentario=? WHERE id=?",
                   (estado, request.user["id"], ahora(), comentario, sid))
    if estado == "Aprobada":
        flash(f"{folio(sid)} aprobada: se descontaron {sol['cantidad']} unidades de {sol['codigo']}.", "ok")
    else:
        flash(f"{folio(sid)} rechazada.", "ok")
    return redirect(url_for("solicitudes"))


# ----------------------------------------------------------------- movimientos y reportes
@app.get("/movimientos")
@login_required("Administrador", "Gerente")
def movimientos():
    tipo = request.args.get("tipo", "")
    q = request.args.get("q", "").strip()[:80]
    sql = ("SELECT m.*, u.nombre AS usuario FROM movimientos m JOIN usuarios u ON u.id = m.usuario_id "
           "WHERE (m.codigo LIKE ? OR m.pieza LIKE ? OR m.referencia LIKE ?)")
    args = [f"%{q}%"] * 3
    if tipo in ("Entrada", "Salida", "Ajuste"):
        sql += " AND m.tipo = ?"
        args.append(tipo)
    with connection() as db:
        lista = db.execute(sql + " ORDER BY m.id DESC", args).fetchall()
    return render_template("movimientos.html", movimientos=lista, tipo=tipo, q=q)


@app.get("/reportes")
@login_required("Administrador", "Gerente")
def reportes():
    with connection() as db:
        por_cat = db.execute("SELECT categoria, COUNT(*) piezas, SUM(cantidad) unidades, "
                             "SUM(cantidad <= minimo) alertas FROM piezas GROUP BY categoria ORDER BY categoria").fetchall()
        mov = db.execute("SELECT tipo, COUNT(*) n, SUM(ABS(cantidad)) u FROM movimientos GROUP BY tipo").fetchall()
        sol = db.execute("SELECT estado, COUNT(*) n FROM solicitudes GROUP BY estado").fetchall()
        top = db.execute("SELECT codigo, pieza, SUM(-cantidad) u FROM movimientos WHERE tipo='Salida' "
                         "GROUP BY codigo, pieza ORDER BY u DESC LIMIT 5").fetchall()
        tecnicos = db.execute("SELECT t.nombre, COUNT(*) n, SUM(s.estado='Aprobada') a, "
                              "SUM(CASE WHEN s.estado='Aprobada' THEN s.cantidad ELSE 0 END) u "
                              "FROM solicitudes s JOIN usuarios t ON t.id = s.tecnico_id GROUP BY t.nombre").fetchall()
        lista_alertas = alertas(db)
    return render_template("reportes.html", por_cat=por_cat, mov={r["tipo"]: r for r in mov},
                           sol={r["estado"]: r["n"] for r in sol}, top=top, tecnicos=tecnicos,
                           alertas=lista_alertas, generado=ahora())


def csv_response(nombre, encabezados, filas):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(encabezados)
    for f in filas:
        w.writerow(["'" + str(v) if str(v)[:1] in "=+-@" and not str(v).lstrip("-").isdigit() else v for v in f])
    return app.response_class("﻿" + out.getvalue(), mimetype="text/csv; charset=utf-8",
                              headers={"Content-Disposition": f"attachment; filename={nombre}"})


@app.get("/reportes/inventario.csv")
@login_required("Administrador", "Gerente")
def reporte_inventario():
    with connection() as db:
        filas = db.execute("SELECT * FROM piezas ORDER BY codigo").fetchall()
    return csv_response("inventario_min.csv", ("Código", "Pieza", "Categoría", "Cantidad", "Mínimo", "Ubicación", "Estado"),
                        [(p["codigo"], p["nombre"], p["categoria"], p["cantidad"], p["minimo"], p["ubicacion"],
                          estado_stock(p)) for p in filas])


@app.get("/reportes/movimientos.csv")
@login_required("Administrador", "Gerente")
def reporte_movimientos():
    with connection() as db:
        filas = db.execute("SELECT m.*, u.nombre AS usuario FROM movimientos m JOIN usuarios u ON u.id=m.usuario_id "
                           "ORDER BY m.id").fetchall()
    return csv_response("movimientos_min.csv", ("Fecha", "Tipo", "Código", "Pieza", "Cantidad", "Existencia", "Usuario", "Referencia"),
                        [(m["fecha"], m["tipo"], m["codigo"], m["pieza"], m["cantidad"], m["existencia"], m["usuario"],
                          m["referencia"]) for m in filas])


# ----------------------------------------------------------------- usuarios
@app.get("/usuarios")
@login_required("Administrador")
def usuarios():
    with connection() as db:
        lista = db.execute("SELECT * FROM usuarios ORDER BY rol, usuario").fetchall()
    return render_template("usuarios.html", usuarios=lista)


@app.route("/usuarios/nuevo", methods=["GET", "POST"])
@app.route("/usuarios/<int:uid>/editar", methods=["GET", "POST"])
@login_required("Administrador")
def usuario_form(uid=None):
    with connection() as db:
        u = db.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone() if uid else None
    if uid and u is None:
        abort(404)
    form = dict(u) if u else {}
    if request.method == "POST":
        check_csrf()
        form = request.form
        usuario = request.form.get("usuario", "").strip().lower()
        nombre = request.form.get("nombre", "").strip()
        rol = request.form.get("rol", "")
        pw = request.form.get("password", "")
        activo = 1 if request.form.get("activo") else 0
        try:
            if not usuario.isalnum() or len(usuario) > 30:
                raise ValueError("El usuario debe ser alfanumérico (máx. 30 caracteres).")
            if not nombre or len(nombre) > 80:
                raise ValueError("El nombre completo es obligatorio.")
            if rol not in ROLES:
                raise ValueError("Selecciona un rol válido.")
            if (not u or pw) and len(pw) < 8:
                raise ValueError("La contraseña debe tener al menos 8 caracteres.")
            if u and u["id"] == request.user["id"] and (rol != "Administrador" or not activo):
                raise ValueError("No puedes quitarte el rol de Administrador ni desactivar tu propia cuenta.")
            with connection() as db:
                if u:
                    db.execute("UPDATE usuarios SET usuario=?, nombre=?, rol=?, activo=? WHERE id=?",
                               (usuario, nombre, rol, activo, uid))
                    if pw:
                        db.execute("UPDATE usuarios SET password_hash=? WHERE id=?", (generate_password_hash(pw), uid))
                else:
                    db.execute("INSERT INTO usuarios (usuario, nombre, rol, password_hash, activo) VALUES (?,?,?,?,?)",
                               (usuario, nombre, rol, generate_password_hash(pw), activo))
            flash(f"Usuario {usuario} guardado.", "ok")
            return redirect(url_for("usuarios"))
        except sqlite3.IntegrityError:
            flash("Ese nombre de usuario ya existe.", "error")
        except ValueError as e:
            flash(str(e), "error")
    return render_template("usuario_form.html", form=form, u=u)


@app.post("/usuarios/<int:uid>/eliminar")
@login_required("Administrador")
def usuario_eliminar(uid):
    check_csrf()
    if uid == request.user["id"]:
        flash("No puedes eliminar tu propia cuenta.", "error")
        return redirect(url_for("usuarios"))
    with connection() as db:
        u = db.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
        if u is None:
            abort(404)
        usado = db.execute("SELECT 1 FROM solicitudes WHERE tecnico_id=? OR gerente_id=? UNION "
                           "SELECT 1 FROM movimientos WHERE usuario_id=?", (uid, uid, uid)).fetchone()
        if usado:
            db.execute("UPDATE usuarios SET activo = 0 WHERE id = ?", (uid,))
            flash(f"{u['usuario']} tiene historial; se desactivó en lugar de eliminarse.", "ok")
        else:
            db.execute("DELETE FROM usuarios WHERE id = ?", (uid,))
            flash(f"Usuario {u['usuario']} eliminado.", "ok")
    return redirect(url_for("usuarios"))


@app.errorhandler(403)
def prohibido(_):
    return render_template("error.html", codigo=403,
                           mensaje="Tu rol no tiene permiso para acceder a esta sección."), 403


@app.errorhandler(404)
def no_encontrado(_):
    return render_template("error.html", codigo=404, mensaje="La página o el registro no existe."), 404


if __name__ == "__main__":
    app.run(debug=False, port=int(os.getenv("PORT", 5000)))
