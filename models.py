"""Capa de datos: SQLite puro (sin ORM) para simplicidad y cero dependencias externas."""
import sqlite3
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "zanjadora.db"))
SANTIAGO_TZ = ZoneInfo("America/Santiago")

DEFAULT_PARAMETROS = {
    "codigo_interno": "ZA-10707",
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
            poza TEXT,
            horometro_inicial REAL,
            horometro_final REAL,
            combustible_l REAL,
            avance_m REAL,
            avance_perimetral_m REAL,
            avance_transversal_m REAL,
            profundidad_cm REAL,
            observaciones TEXT,
            horas_sistema_automatico REAL,
            picas_reemplazadas REAL,
            roturas_identificadas REAL,
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pozas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            metros_totales REAL,
            metros_perimetral_totales REAL,
            metros_transversal_totales REAL,
            altura_cm REAL,
            creado_en TEXT
        )
    """)
    cols_pozas = [r["name"] for r in conn.execute("PRAGMA table_info(pozas)").fetchall()]
    if "altura_cm" not in cols_pozas:
        conn.execute("ALTER TABLE pozas ADD COLUMN altura_cm REAL")
    if "metros_perimetral_totales" not in cols_pozas:
        conn.execute("ALTER TABLE pozas ADD COLUMN metros_perimetral_totales REAL")
    if "metros_transversal_totales" not in cols_pozas:
        conn.execute("ALTER TABLE pozas ADD COLUMN metros_transversal_totales REAL")

    cols_registros = [r["name"] for r in conn.execute("PRAGMA table_info(registros)").fetchall()]
    if "poza" not in cols_registros:
        conn.execute("ALTER TABLE registros ADD COLUMN poza TEXT")
    if "horas_sistema_automatico" not in cols_registros:
        conn.execute("ALTER TABLE registros ADD COLUMN horas_sistema_automatico REAL")
    if "picas_reemplazadas" not in cols_registros:
        conn.execute("ALTER TABLE registros ADD COLUMN picas_reemplazadas REAL")
    if "roturas_identificadas" not in cols_registros:
        conn.execute("ALTER TABLE registros ADD COLUMN roturas_identificadas REAL")
    if "avance_perimetral_m" not in cols_registros:
        conn.execute("ALTER TABLE registros ADD COLUMN avance_perimetral_m REAL")
    if "avance_transversal_m" not in cols_registros:
        conn.execute("ALTER TABLE registros ADD COLUMN avance_transversal_m REAL")

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
        "fecha", "turno", "operador", "poza", "horometro_inicial", "horometro_final",
        "combustible_l", "avance_m", "avance_perimetral_m", "avance_transversal_m", "profundidad_cm", "observaciones",
        "horas_sistema_automatico", "picas_reemplazadas", "roturas_identificadas",
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
        "fecha", "turno", "operador", "poza", "horometro_inicial", "horometro_final",
        "combustible_l", "avance_m", "avance_perimetral_m", "avance_transversal_m", "profundidad_cm", "observaciones",
        "horas_sistema_automatico", "picas_reemplazadas", "roturas_identificadas",
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


def _filtro_periodo(anio, mes, poza=None):
    condiciones = []
    valores = []
    if anio:
        condiciones.append("substr(fecha, 1, 4) = ?")
        valores.append(f"{anio:04d}")
    if mes:
        condiciones.append("substr(fecha, 6, 2) = ?")
        valores.append(f"{mes:02d}")
    if poza:
        condiciones.append("poza = ?")
        valores.append(poza)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return where, valores


def listar_registros(limit=500, anio=None, mes=None, poza=None):
    where, valores = _filtro_periodo(anio, mes, poza)
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


def crear_poza(nombre, metros_perimetral_totales, metros_transversal_totales, altura_cm):
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO pozas
               (nombre, metros_perimetral_totales, metros_transversal_totales, altura_cm, creado_en)
               VALUES (?, ?, ?, ?, ?)""",
            (nombre, metros_perimetral_totales, metros_transversal_totales, altura_cm, datetime.utcnow().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Ya existe una poza con ese nombre.")
    finally:
        conn.close()


def listar_pozas():
    conn = get_db()
    rows = conn.execute("SELECT * FROM pozas ORDER BY nombre").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtener_poza(nombre):
    conn = get_db()
    row = conn.execute("SELECT * FROM pozas WHERE nombre = ?", (nombre,)).fetchone()
    conn.close()
    return dict(row) if row else None


def eliminar_poza(poza_id):
    conn = get_db()
    conn.execute("DELETE FROM pozas WHERE id = ?", (poza_id,))
    conn.commit()
    conn.close()


def listar_pozas_disponibles():
    return [p["nombre"] for p in listar_pozas()]


def picas_reemplazadas_por_mes(anio=None, poza=None):
    condiciones = []
    valores = []
    if anio:
        condiciones.append("substr(fecha, 1, 4) = ?")
        valores.append(f"{anio:04d}")
    if poza:
        condiciones.append("poza = ?")
        valores.append(poza)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    conn = get_db()
    rows = conn.execute(f"""
        SELECT substr(fecha, 1, 7) AS mes, COALESCE(SUM(picas_reemplazadas), 0) AS total
        FROM registros {where}
        GROUP BY mes
        ORDER BY mes DESC
    """, valores).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def roturas_identificadas_por_mes(anio=None, poza=None):
    condiciones = []
    valores = []
    if anio:
        condiciones.append("substr(fecha, 1, 4) = ?")
        valores.append(f"{anio:04d}")
    if poza:
        condiciones.append("poza = ?")
        valores.append(poza)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    conn = get_db()
    rows = conn.execute(f"""
        SELECT substr(fecha, 1, 7) AS mes, COALESCE(SUM(roturas_identificadas), 0) AS total
        FROM registros {where}
        GROUP BY mes
        ORDER BY mes DESC
    """, valores).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ranking_operadores(anio=None, mes=None, poza=None):
    where, valores = _filtro_periodo(anio, mes, poza)
    condicion_operador = "operador IS NOT NULL AND operador != ''"
    where = f"{where} AND {condicion_operador}" if where else f"WHERE {condicion_operador}"
    conn = get_db()
    rows = conn.execute(f"""
        SELECT
            operador,
            COUNT(*) AS registros,
            COALESCE(SUM(horas_operadas), 0) AS horas_operadas_total,
            COALESCE(SUM(avance_m), 0) AS avance_total,
            COALESCE(SUM(avance_perimetral_m), 0) AS avance_perimetral_total,
            COALESCE(SUM(avance_transversal_m), 0) AS avance_transversal_total,
            COALESCE(SUM(combustible_l), 0) AS combustible_total
        FROM registros {where}
        GROUP BY operador
        ORDER BY avance_total DESC
    """, valores).fetchall()
    conn.close()
    resultado = []
    for r in rows:
        d = dict(r)
        d["rendimiento_mh"] = _safe_div(d["avance_total"], d["horas_operadas_total"]) or 0
        d["consumo_lh"] = _safe_div(d["combustible_total"], d["horas_operadas_total"]) or 0
        resultado.append(d)
    return resultado


def ultimo_horometro_final():
    conn = get_db()
    row = conn.execute(
        "SELECT horometro_final FROM registros ORDER BY fecha DESC, id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["horometro_final"] if row else None


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
    resultado = []
    for r in rows:
        d = dict(r)
        try:
            dt_utc = datetime.fromisoformat(d["fecha_hora"]).replace(tzinfo=ZoneInfo("UTC"))
            d["fecha_hora_cl"] = dt_utc.astimezone(SANTIAGO_TZ).strftime("%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            d["fecha_hora_cl"] = d["fecha_hora"]
        resultado.append(d)
    return resultado


def resumen_kpis(anio=None, mes=None, poza=None):
    where, valores = _filtro_periodo(anio, mes, poza)
    conn = get_db()
    row = conn.execute(f"""
        SELECT
            COUNT(*) AS registros_ingresados,
            COALESCE(SUM(horas_operadas), 0) AS horas_operadas_total,
            COALESCE(SUM(combustible_l), 0) AS combustible_total,
            COALESCE(SUM(avance_m), 0) AS avance_total,
            COALESCE(SUM(avance_perimetral_m), 0) AS avance_perimetral_total,
            COALESCE(SUM(avance_transversal_m), 0) AS avance_transversal_total,
            COALESCE(SUM(volumen_m3), 0) AS volumen_total,
            COALESCE(SUM(costo_total), 0) AS costo_total_acumulado,
            COALESCE(SUM(horas_sistema_automatico), 0) AS horas_sistema_automatico_total,
            COALESCE(SUM(picas_reemplazadas), 0) AS picas_reemplazadas_total,
            COALESCE(SUM(roturas_identificadas), 0) AS roturas_identificadas_total
        FROM registros {where}
    """, valores).fetchone()
    conn.close()
    params = get_parametros()
    d = dict(row)
    d["consumo_promedio"] = _safe_div(d["combustible_total"], d["horas_operadas_total"]) or 0
    d["rendimiento_promedio"] = _safe_div(d["avance_total"], d["horas_operadas_total"]) or 0
    d["costo_por_hora"] = _safe_div(d["costo_total_acumulado"], d["horas_operadas_total"]) or 0
    d["costo_por_metro"] = _safe_div(d["costo_total_acumulado"], d["avance_total"]) or 0
    d["utilizacion_automatico_pct"] = _safe_div(
        d["horas_sistema_automatico_total"], d["horas_operadas_total"]
    )
    if d["utilizacion_automatico_pct"] is not None:
        d["utilizacion_automatico_pct"] *= 100
    objetivo = params.get("consumo_objetivo") or 0
    d["desvio_consumo_pct"] = (
        _safe_div(d["consumo_promedio"] - objetivo, objetivo) if objetivo else None
    )
    return d
