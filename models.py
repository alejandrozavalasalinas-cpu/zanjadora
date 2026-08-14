"""Capa de datos: SQLite puro (sin ORM) para simplicidad y cero dependencias externas."""
import sqlite3
import os
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "zanjadora.db"))

DEFAULT_PARAMETROS = {
    "codigo_interno": "MAQ-001",
    "nombre": "Zanjadora",
    "marca": "Tesmec",
    "modelo": "Tesmec 975 CS",
    "anio": 2018,
    "numero_serie": "SN-000000",
    "precio_combustible": 1150.0,
    "costo_operador_hora": 4500.0,
    "consumo_objetivo": 68.0,
    "rendimiento_objetivo": 45.0,
    "intervalo_mantencion": 250.0,
    "horometro_ultima_mantencion": 0.0,
    "aviso_anticipado": 25.0,
    "profundidad_zanja_cm": 183.0,
    "ancho_zanja_cm": 45.7,
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parametros (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            codigo_interno TEXT,
            nombre TEXT,
            marca TEXT,
            modelo TEXT,
            anio INTEGER,
            numero_serie TEXT,
            precio_combustible REAL,
            costo_operador_hora REAL,
            consumo_objetivo REAL,
            rendimiento_objetivo REAL,
            intervalo_mantencion REAL,
            horometro_ultima_mantencion REAL,
            aviso_anticipado REAL,
            profundidad_zanja_cm REAL,
            ancho_zanja_cm REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            turno TEXT,
            operador TEXT,
            horometro_inicial REAL,
            horometro_final REAL,
            combustible_l REAL,
            avance_m REAL,
            profundidad_cm REAL,
            observaciones TEXT,
            horas_operadas REAL,
            consumo_lh REAL,
            volumen_m3 REAL,
            rendimiento_mh REAL,
            costo_combustible REAL,
            costo_operador REAL,
            costo_total REAL,
            costo_hora REAL,
            costo_metro REAL,
            hrs_para_mantencion REAL,
            estado_mant TEXT,
            creado_en TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accesos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            fecha_hora TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'operador',
            creado_en TEXT
        )
    """)
    row = conn.execute("SELECT COUNT(*) c FROM parametros").fetchone()
    if row["c"] == 0:
        cols = ", ".join(DEFAULT_PARAMETROS.keys())
        placeholders = ", ".join(["?"] * len(DEFAULT_PARAMETROS))
        conn.execute(
            f"INSERT INTO parametros (id, {cols}) VALUES (1, {placeholders})",
            tuple(DEFAULT_PARAMETROS.values()),
        )
    conn.commit()
    conn.close()


def get_parametros():
    conn = get_db()
    row = conn.execute("SELECT * FROM parametros WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else dict(DEFAULT_PARAMETROS)


def update_parametros(data):
    conn = get_db()
    fields = list(DEFAULT_PARAMETROS.keys())
    set_clause = ", ".join([f"{f} = ?" for f in fields])
    values = [data.get(f) for f in fields]
    conn.execute(f"UPDATE parametros SET {set_clause} WHERE id = 1", values)
    conn.commit()
    conn.close()


def _safe_div(a, b):
    try:
        if b in (None, 0):
            return None
        return a / b
    except (TypeError, ZeroDivisionError):
        return None


def calcular_derivados(reg, params):
    """Replica las fórmulas validadas contra la planilla original y el modelo de Power BI."""
    horas_operadas = None
    if reg["horometro_inicial"] is not None and reg["horometro_final"] is not None:
        horas_operadas = reg["horometro_final"] - reg["horometro_inicial"]

    consumo_lh = _safe_div(reg["combustible_l"], horas_operadas)

    ancho_m = (params.get("ancho_zanja_cm") or 45.7) / 100
    profundidad_cm = reg.get("profundidad_cm") or params.get("profundidad_zanja_cm") or 0
    seccion_m2 = (profundidad_cm / 100) * ancho_m
    volumen_m3 = (reg["avance_m"] or 0) * seccion_m2

    rendimiento_mh = _safe_div(reg["avance_m"], horas_operadas)

    costo_combustible = (reg["combustible_l"] or 0) * (params.get("precio_combustible") or 0)
    costo_operador = (horas_operadas or 0) * (params.get("costo_operador_hora") or 0)
    costo_total = costo_combustible + costo_operador
    costo_hora = _safe_div(costo_total, horas_operadas)
    costo_metro = _safe_div(costo_total, reg["avance_m"])

    hrs_para_mantencion = None
    if reg["horometro_final"] is not None:
        hrs_para_mantencion = (params.get("intervalo_mantencion") or 0) - (
            reg["horometro_final"] - (params.get("horometro_ultima_mantencion") or 0)
        )
    estado_mant = "OK"
    if hrs_para_mantencion is not None and hrs_para_mantencion <= (params.get("aviso_anticipado") or 0):
        estado_mant = "Alerta"

    return {
        "horas_operadas": horas_operadas,
        "consumo_lh": consumo_lh,
        "volumen_m3": volumen_m3,
        "rendimiento_mh": rendimiento_mh,
        "costo_combustible": costo_combustible,
        "costo_operador": costo_operador,
        "costo_total": costo_total,
        "costo_hora": costo_hora,
        "costo_metro": costo_metro,
        "hrs_para_mantencion": hrs_para_mantencion,
        "estado_mant": estado_mant,
    }


def crear_registro(data):
    params = get_parametros()
    derivados = calcular_derivados(data, params)
    conn = get_db()
    cols = [
        "fecha", "turno", "operador", "horometro_inicial", "horometro_final",
        "combustible_l", "avance_m", "profundidad_cm", "observaciones",
        "horas_operadas", "consumo_lh", "volumen_m3", "rendimiento_mh",
        "costo_combustible", "costo_operador", "costo_total", "costo_hora",
        "costo_metro", "hrs_para_mantencion", "estado_mant", "creado_en",
    ]
    values = {**data, **derivados, "creado_en": datetime.utcnow().isoformat()}
    placeholders = ", ".join(["?"] * len(cols))
    conn.execute(
        f"INSERT INTO registros ({', '.join(cols)}) VALUES ({placeholders})",
        [values.get(c) for c in cols],
    )
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]
    conn.close()
    return new_id


def actualizar_registro(reg_id, data):
    params = get_parametros()
    derivados = calcular_derivados(data, params)
    conn = get_db()
    cols = [
        "fecha", "turno", "operador", "horometro_inicial", "horometro_final",
        "combustible_l", "avance_m", "profundidad_cm", "observaciones",
        "horas_operadas", "consumo_lh", "volumen_m3", "rendimiento_mh",
        "costo_combustible", "costo_operador", "costo_total", "costo_hora",
        "costo_metro", "hrs_para_mantencion", "estado_mant",
    ]
    values = {**data, **derivados}
    set_clause = ", ".join([f"{c} = ?" for c in cols])
    conn.execute(
        f"UPDATE registros SET {set_clause} WHERE id = ?",
        [values.get(c) for c in cols] + [reg_id],
    )
    conn.commit()
    conn.close()


def _filtro_periodo(anio, mes):
    condiciones = []
    valores = []
    if anio:
        condiciones.append("substr(fecha, 1, 4) = ?")
        valores.append(f"{anio:04d}")
    if mes:
        condiciones.append("substr(fecha, 6, 2) = ?")
        valores.append(f"{mes:02d}")
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return where, valores


def listar_registros(limit=500, anio=None, mes=None):
    where, valores = _filtro_periodo(anio, mes)
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM registros {where} ORDER BY fecha DESC, id DESC LIMIT ?",
        (*valores, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_anios_disponibles():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT substr(fecha, 1, 4) AS anio FROM registros ORDER BY anio DESC"
    ).fetchall()
    conn.close()
    return [int(r["anio"]) for r in rows if r["anio"]]


def obtener_registro(reg_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM registros WHERE id = ?", (reg_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def eliminar_registro(reg_id):
    conn = get_db()
    conn.execute("DELETE FROM registros WHERE id = ?", (reg_id,))
    conn.commit()
    conn.close()


def crear_usuario(nombre, password, rol="operador"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO usuarios (nombre, password_hash, rol, creado_en) VALUES (?, ?, ?, ?)",
            (nombre, generate_password_hash(password), rol, datetime.utcnow().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Ya existe un usuario registrado con ese nombre.")
    finally:
        conn.close()


def obtener_usuario(nombre):
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE nombre = ?", (nombre,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verificar_usuario(nombre, password):
    usuario = obtener_usuario(nombre)
    if usuario and check_password_hash(usuario["password_hash"], password):
        return usuario
    return None


def registrar_acceso(nombre):
    conn = get_db()
    conn.execute(
        "INSERT INTO accesos (nombre, fecha_hora) VALUES (?, ?)",
        (nombre, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def listar_accesos(limit=200):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM accesos ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resumen_kpis(anio=None, mes=None):
    where, valores = _filtro_periodo(anio, mes)
    conn = get_db()
    row = conn.execute(f"""
        SELECT
            COUNT(*) AS registros_ingresados,
            COALESCE(SUM(horas_operadas), 0) AS horas_operadas_total,
            COALESCE(SUM(combustible_l), 0) AS combustible_total,
            COALESCE(SUM(avance_m), 0) AS avance_total,
            COALESCE(SUM(costo_total), 0) AS costo_total_acumulado
        FROM registros {where}
    """, valores).fetchone()
    conn.close()
    params = get_parametros()
    d = dict(row)
    d["consumo_promedio"] = _safe_div(d["combustible_total"], d["horas_operadas_total"]) or 0
    d["rendimiento_promedio"] = _safe_div(d["avance_total"], d["horas_operadas_total"]) or 0
    d["costo_por_hora"] = _safe_div(d["costo_total_acumulado"], d["horas_operadas_total"]) or 0
    d["costo_por_metro"] = _safe_div(d["costo_total_acumulado"], d["avance_total"]) or 0
    objetivo = params.get("consumo_objetivo") or 0
    d["desvio_consumo_pct"] = (
        _safe_div(d["consumo_promedio"] - objetivo, objetivo) if objetivo else None
    )
    return d
