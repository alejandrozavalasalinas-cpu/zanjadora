import csv
import io
import os
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response,
    send_from_directory, abort,
)
from werkzeug.utils import secure_filename

import models

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB, para los PDF de respaldo
APP_PASSWORD = os.environ.get("APP_PASSWORD", "zanjadora2026")

MANTENCIONES_DIR = os.path.join(os.path.dirname(models.DB_PATH), "mantenciones_pdfs")
os.makedirs(MANTENCIONES_DIR, exist_ok=True)

models.init_db()


# ---------- Autenticación simple (contraseña compartida) ----------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("autenticado"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def operador_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("rol") == "visor":
            flash("Tu cuenta solo tiene acceso al tablero.", "error")
            return redirect(url_for("tablero"))
        return view(*args, **kwargs)
    return wrapped


def obtener_ip_cliente():
    # Fly.io entrega la IP real del cliente en este header (el proxy interno
    # queda en X-Forwarded-For/remote_addr).
    ip = request.headers.get("Fly-Client-IP")
    if ip:
        return ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        password = request.form.get("password") or ""
        usuario = models.verificar_usuario(nombre, password)
        if usuario:
            session["autenticado"] = True
            session["usuario"] = usuario["nombre"]
            session["rol"] = usuario["rol"]
            models.registrar_acceso(session["usuario"], ip=obtener_ip_cliente())
            destino = url_for("tablero") if usuario["rol"] == "visor" else (request.args.get("next") or url_for("tablero"))
            return redirect(destino)
        error = "Usuario o contraseña incorrectos."
    return render_template("login.html", error=error)


@app.route("/registro", methods=["GET", "POST"])
def registro():
    error = None
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        password = request.form.get("password") or ""
        confirmar = request.form.get("confirmar") or ""
        clave_invitacion = request.form.get("clave_invitacion") or ""
        try:
            if not nombre:
                raise ValueError("El usuario es obligatorio.")
            if " " in nombre:
                raise ValueError("El usuario no puede tener espacios.")
            if len(password) < 6:
                raise ValueError("La contraseña debe tener al menos 6 caracteres.")
            if password != confirmar:
                raise ValueError("Las contraseñas no coinciden.")
            if clave_invitacion != APP_PASSWORD:
                raise ValueError("Clave de equipo incorrecta.")
            models.crear_usuario(nombre, password)
            flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
            return redirect(url_for("login"))
        except ValueError as e:
            error = str(e)
    return render_template("registro.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Vistas ----------

MESES = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]


@app.route("/")
@login_required
def tablero():
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    poza = request.args.get("poza") or None
    kpis = models.resumen_kpis(anio=anio, mes=mes, poza=poza)
    registros = models.listar_registros(limit=20, anio=anio, mes=mes, poza=poza)
    anios_disponibles = models.listar_anios_disponibles()
    pozas_disponibles = models.listar_pozas_disponibles()
    avance_perimetral_pct = None
    avance_transversal_pct = None
    metros_perimetral_totales_poza = None
    metros_transversal_totales_poza = None
    meta_m3_poza = None
    avance_m3_poza_pct = None
    if poza:
        poza_info = models.obtener_poza(poza)
        if poza_info and poza_info.get("metros_perimetral_totales"):
            metros_perimetral_totales_poza = poza_info["metros_perimetral_totales"]
            avance_perimetral_pct = (kpis["avance_perimetral_total"] / metros_perimetral_totales_poza) * 100
        if poza_info and poza_info.get("metros_transversal_totales"):
            metros_transversal_totales_poza = poza_info["metros_transversal_totales"]
            avance_transversal_pct = (kpis["avance_transversal_total"] / metros_transversal_totales_poza) * 100
        metros_totales_poza = (poza_info.get("metros_perimetral_totales") or 0) + (poza_info.get("metros_transversal_totales") or 0) if poza_info else 0
        if poza_info and metros_totales_poza and poza_info.get("altura_cm"):
            ancho_zanja_cm = models.get_parametros().get("ancho_zanja_cm") or 0
            meta_m3_poza = metros_totales_poza * (poza_info["altura_cm"] / 100) * (ancho_zanja_cm / 100)
            if meta_m3_poza:
                avance_m3_poza_pct = (kpis["volumen_total"] / meta_m3_poza) * 100
    picas_por_mes = models.picas_reemplazadas_por_mes(anio=anio, poza=poza)
    roturas_por_mes = models.roturas_identificadas_por_mes(anio=anio, poza=poza)
    return render_template(
        "tablero.html",
        kpis=kpis,
        registros=registros,
        meses=MESES,
        anios_disponibles=anios_disponibles,
        pozas_disponibles=pozas_disponibles,
        anio_sel=anio,
        mes_sel=mes,
        poza_sel=poza,
        avance_perimetral_pct=avance_perimetral_pct,
        avance_transversal_pct=avance_transversal_pct,
        metros_perimetral_totales_poza=metros_perimetral_totales_poza,
        metros_transversal_totales_poza=metros_transversal_totales_poza,
        meta_m3_poza=meta_m3_poza,
        avance_m3_poza_pct=avance_m3_poza_pct,
        picas_por_mes=picas_por_mes,
        roturas_por_mes=roturas_por_mes,
        aviso_anticipado=models.get_parametros().get("aviso_anticipado") or 0,
    )


@app.route("/ranking")
@login_required
def ranking():
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    poza = request.args.get("poza") or None
    ranking_data = models.ranking_operadores(anio=anio, mes=mes, poza=poza)
    return render_template(
        "ranking.html",
        ranking=ranking_data,
        meses=MESES,
        anios_disponibles=models.listar_anios_disponibles(),
        pozas_disponibles=models.listar_pozas_disponibles(),
        anio_sel=anio,
        mes_sel=mes,
        poza_sel=poza,
    )


@app.route("/formulario", methods=["GET", "POST"])
@login_required
@operador_required
def formulario():
    params = models.get_parametros()
    if request.method == "POST":
        try:
            data = {
                "fecha": request.form.get("fecha"),
                "turno": request.form.get("turno"),
                "operador": request.form.get("operador"),
                "poza": request.form.get("poza"),
                "horometro_inicial": float(request.form.get("horometro_inicial") or 0),
                "horometro_final": float(request.form.get("horometro_final") or 0),
                "combustible_l": float(request.form.get("combustible_l") or 0),
                "avance_perimetral_m": float(request.form.get("avance_perimetral_m") or 0),
                "avance_transversal_m": float(request.form.get("avance_transversal_m") or 0),
                "profundidad_cm": float(request.form.get("profundidad_cm") or params.get("profundidad_zanja_cm") or 0),
                "observaciones": request.form.get("observaciones"),
                "horas_sistema_automatico": float(request.form.get("horas_sistema_automatico") or 0),
                "picas_reemplazadas": float(request.form.get("picas_reemplazadas") or 0),
                "roturas_identificadas": float(request.form.get("roturas_identificadas") or 0),
            }
            data["avance_m"] = data["avance_perimetral_m"] + data["avance_transversal_m"]
            if not data["fecha"]:
                raise ValueError("La fecha es obligatoria.")
            if not data["poza"]:
                raise ValueError("La poza es obligatoria.")
            ultimo_horometro = models.ultimo_horometro_final()
            if ultimo_horometro is not None and data["horometro_inicial"] != ultimo_horometro:
                raise ValueError(
                    f"El horómetro inicial debe ser igual al último horómetro final registrado ({ultimo_horometro})."
                )
            if data["horometro_final"] < data["horometro_inicial"]:
                raise ValueError("El horómetro final no puede ser menor que el inicial.")
            if data["horas_sistema_automatico"] > (data["horometro_final"] - data["horometro_inicial"]):
                raise ValueError("Las horas de sistema automático no pueden superar las horas operadas.")
            models.crear_registro(data)
            flash("Registro guardado correctamente.", "success")
            return redirect(url_for("formulario"))
        except ValueError as e:
            flash(f"Error: {e}", "error")
    return render_template(
        "formulario.html",
        params=params,
        hoy=datetime.now().strftime("%Y-%m-%d"),
        registros=models.listar_registros(limit=15),
        pozas=models.listar_pozas(),
        operadores=models.listar_operadores(),
        ultimo_horometro=models.ultimo_horometro_final(),
    )


@app.route("/registros")
@login_required
@operador_required
def registros():
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    poza = request.args.get("poza") or None
    return render_template(
        "registros.html",
        registros=models.listar_registros(limit=100000, anio=anio, mes=mes, poza=poza),
        meses=MESES,
        anios_disponibles=models.listar_anios_disponibles(),
        pozas_disponibles=models.listar_pozas_disponibles(),
        anio_sel=anio,
        mes_sel=mes,
        poza_sel=poza,
    )


@app.route("/registros/exportar")
@login_required
def exportar_registros():
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    poza = request.args.get("poza") or None
    registros = models.listar_registros(limit=100000, anio=anio, mes=mes, poza=poza)
    cols = [
        "fecha", "turno", "operador", "poza", "horometro_inicial", "horometro_final",
        "combustible_l", "avance_m", "profundidad_cm", "horas_operadas",
        "consumo_lh", "volumen_m3", "rendimiento_mh", "costo_combustible",
        "costo_operador", "costo_total", "costo_hora", "costo_metro",
        "hrs_para_mantencion", "estado_mant", "observaciones",
    ]
    headers = [
        "Fecha", "Turno", "Operador", "Poza", "Horómetro inicial", "Horómetro final",
        "Combustible (L)", "Avance (m)", "Profundidad (cm)", "Horas operadas",
        "Consumo (L/h)", "Volumen (m3)", "Rendimiento (m/h)", "Costo combustible",
        "Costo operador", "Costo total", "Costo por hora", "Costo por metro",
        "Horas para mantención", "Estado mantención", "Observaciones",
    ]
    output = io.StringIO()
    output.write(chr(0xFEFF))
    writer = csv.writer(output, delimiter=";")
    writer.writerow(headers)
    for r in registros:
        writer.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
    filename = f"zanjadora_registros_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/registros/<int:reg_id>/editar", methods=["GET", "POST"])
@login_required
@operador_required
def editar_registro(reg_id):
    registro = models.obtener_registro(reg_id)
    if not registro:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("formulario"))
    params = models.get_parametros()
    if request.method == "POST":
        try:
            data = {
                "fecha": request.form.get("fecha"),
                "turno": request.form.get("turno"),
                "operador": request.form.get("operador"),
                "poza": request.form.get("poza"),
                "horometro_inicial": float(request.form.get("horometro_inicial") or 0),
                "horometro_final": float(request.form.get("horometro_final") or 0),
                "combustible_l": float(request.form.get("combustible_l") or 0),
                "avance_perimetral_m": float(request.form.get("avance_perimetral_m") or 0),
                "avance_transversal_m": float(request.form.get("avance_transversal_m") or 0),
                "profundidad_cm": float(request.form.get("profundidad_cm") or params.get("profundidad_zanja_cm") or 0),
                "observaciones": request.form.get("observaciones"),
                "horas_sistema_automatico": float(request.form.get("horas_sistema_automatico") or 0),
                "picas_reemplazadas": float(request.form.get("picas_reemplazadas") or 0),
                "roturas_identificadas": float(request.form.get("roturas_identificadas") or 0),
            }
            data["avance_m"] = data["avance_perimetral_m"] + data["avance_transversal_m"]
            if not data["fecha"]:
                raise ValueError("La fecha es obligatoria.")
            if not data["poza"]:
                raise ValueError("La poza es obligatoria.")
            if data["horometro_final"] < data["horometro_inicial"]:
                raise ValueError("El horómetro final no puede ser menor que el inicial.")
            if data["horas_sistema_automatico"] > (data["horometro_final"] - data["horometro_inicial"]):
                raise ValueError("Las horas de sistema automático no pueden superar las horas operadas.")
            models.actualizar_registro(reg_id, data)
            flash("Registro actualizado correctamente.", "success")
            return redirect(url_for("formulario"))
        except ValueError as e:
            flash(f"Error: {e}", "error")
    return render_template(
        "editar_registro.html",
        registro=registro,
        params=params,
        pozas=models.listar_pozas(),
        operadores=models.listar_operadores(),
    )


@app.route("/registros/<int:reg_id>/eliminar", methods=["POST"])
@login_required
@operador_required
def eliminar_registro(reg_id):
    models.eliminar_registro(reg_id)
    flash("Registro eliminado.", "success")
    return redirect(request.referrer or url_for("formulario"))


@app.route("/accesos")
@login_required
@operador_required
def accesos():
    return render_template("accesos.html", accesos=models.listar_accesos(limit=200))


@app.route("/parametros", methods=["GET", "POST"])
@login_required
@operador_required
def parametros():
    if request.method == "POST":
        campos_num = [
            "anio", "precio_combustible", "costo_operador_hora", "consumo_objetivo",
            "rendimiento_objetivo", "intervalo_mantencion", "horometro_ultima_mantencion",
            "aviso_anticipado", "profundidad_zanja_cm", "ancho_zanja_cm",
        ]
        campos_txt = ["codigo_interno", "nombre", "marca", "modelo", "numero_serie"]
        data = {c: request.form.get(c) or "" for c in campos_txt}
        for c in campos_num:
            try:
                data[c] = float(request.form.get(c) or 0)
            except ValueError:
                data[c] = 0
        data["anio"] = int(data["anio"])
        models.update_parametros(data)
        flash("Parámetros actualizados.", "success")
        return redirect(url_for("parametros"))
    return render_template(
        "parametros.html",
        params=models.get_parametros(),
        pozas=models.listar_pozas(),
        operadores=models.listar_operadores(),
        mantenciones=models.listar_mantenciones(),
    )


@app.route("/parametros/pozas", methods=["POST"])
@login_required
@operador_required
def crear_poza():
    nombre = (request.form.get("nombre") or "").strip()
    try:
        metros_perimetral_totales = float(request.form.get("metros_perimetral_totales") or 0)
        metros_transversal_totales = float(request.form.get("metros_transversal_totales") or 0)
        altura_cm = float(request.form.get("altura_cm") or 0)
        if not nombre:
            raise ValueError("El nombre de la poza es obligatorio.")
        models.crear_poza(nombre, metros_perimetral_totales, metros_transversal_totales, altura_cm)
        flash("Poza agregada.", "success")
    except ValueError as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("parametros"))


@app.route("/parametros/pozas/<int:poza_id>/eliminar", methods=["POST"])
@login_required
@operador_required
def eliminar_poza(poza_id):
    models.eliminar_poza(poza_id)
    flash("Poza eliminada.", "success")
    return redirect(url_for("parametros"))


@app.route("/parametros/operadores", methods=["POST"])
@login_required
@operador_required
def crear_operador():
    nombre = (request.form.get("nombre") or "").strip()
    apellido = (request.form.get("apellido") or "").strip()
    try:
        if not nombre or not apellido:
            raise ValueError("El nombre y apellido son obligatorios.")
        models.crear_operador(f"{nombre} {apellido}")
        flash("Operador agregado.", "success")
    except ValueError as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("parametros"))


@app.route("/parametros/operadores/<int:operador_id>/eliminar", methods=["POST"])
@login_required
@operador_required
def eliminar_operador(operador_id):
    models.eliminar_operador(operador_id)
    flash("Operador eliminado.", "success")
    return redirect(url_for("parametros"))


@app.route("/parametros/mantenciones", methods=["POST"])
@login_required
@operador_required
def crear_mantencion():
    try:
        fecha = request.form.get("fecha")
        horometro = float(request.form.get("horometro") or 0)
        descripcion = request.form.get("descripcion")
        if not fecha:
            raise ValueError("La fecha es obligatoria.")

        archivo = request.files.get("pdf")
        pdf_filename = None
        if archivo and archivo.filename:
            if not archivo.filename.lower().endswith(".pdf"):
                raise ValueError("El respaldo debe ser un archivo PDF.")
            cabecera = archivo.read(5)
            archivo.seek(0)
            if cabecera != b"%PDF-":
                raise ValueError("El archivo no es un PDF válido.")
            pdf_filename = f"{uuid.uuid4().hex}_{secure_filename(archivo.filename)}"
            archivo.save(os.path.join(MANTENCIONES_DIR, pdf_filename))

        models.crear_mantencion(fecha, horometro, descripcion, pdf_filename)
        flash("Mantención registrada.", "success")
    except ValueError as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("parametros"))


@app.route("/parametros/mantenciones/<int:mantencion_id>/eliminar", methods=["POST"])
@login_required
@operador_required
def eliminar_mantencion(mantencion_id):
    pdf_filename = models.eliminar_mantencion(mantencion_id)
    if pdf_filename:
        ruta = os.path.join(MANTENCIONES_DIR, pdf_filename)
        if os.path.exists(ruta):
            os.remove(ruta)
    flash("Mantención eliminada.", "success")
    return redirect(url_for("parametros"))


@app.route("/mantenciones/<int:mantencion_id>/pdf")
@login_required
def ver_pdf_mantencion(mantencion_id):
    mantencion = models.obtener_mantencion(mantencion_id)
    if not mantencion or not mantencion.get("pdf_filename"):
        abort(404)
    return send_from_directory(MANTENCIONES_DIR, mantencion["pdf_filename"])


# ---------- API JSON (para el gráfico del tablero) ----------

@app.route("/api/registros")
@login_required
def api_registros():
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    poza = request.args.get("poza") or None
    return jsonify(models.listar_registros(limit=500, anio=anio, mes=mes, poza=poza))


@app.route("/api/disponibilidad")
@login_required
def api_disponibilidad():
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    poza = request.args.get("poza") or None
    return jsonify({
        "dias": models.disponibilidad_diaria(anio=anio, mes=mes, poza=poza),
        "jornada_horas": models.JORNADA_HORAS,
        "acumulado_pct": models.disponibilidad_acumulada(anio=anio, mes=mes, poza=poza),
    })


@app.route("/api/resumen")
@login_required
def api_resumen():
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    poza = request.args.get("poza") or None
    return jsonify(models.resumen_kpis(anio=anio, mes=mes, poza=poza))


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG") == "1")
