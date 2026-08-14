import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, jsonify, flash
)

import models

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "zanjadora2026")

models.init_db()


# ---------- Autenticación simple (contraseña compartida) ----------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("autenticado"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["autenticado"] = True
            session["usuario"] = request.form.get("nombre") or "Operador"
            models.registrar_acceso(session["usuario"])
            destino = request.args.get("next") or url_for("tablero")
            return redirect(destino)
        error = "Contraseña incorrecta."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Vistas ----------

@app.route("/")
@login_required
def tablero():
    kpis = models.resumen_kpis()
    registros = models.listar_registros(limit=50)
    return render_template("tablero.html", kpis=kpis, registros=registros)


@app.route("/formulario", methods=["GET", "POST"])
@login_required
def formulario():
    params = models.get_parametros()
    if request.method == "POST":
        try:
            data = {
                "fecha": request.form.get("fecha"),
                "turno": request.form.get("turno"),
                "operador": request.form.get("operador"),
                "horometro_inicial": float(request.form.get("horometro_inicial") or 0),
                "horometro_final": float(request.form.get("horometro_final") or 0),
                "combustible_l": float(request.form.get("combustible_l") or 0),
                "avance_m": float(request.form.get("avance_m") or 0),
                "profundidad_cm": float(request.form.get("profundidad_cm") or params.get("profundidad_zanja_cm") or 0),
                "observaciones": request.form.get("observaciones"),
            }
            if not data["fecha"]:
                raise ValueError("La fecha es obligatoria.")
            if data["horometro_final"] < data["horometro_inicial"]:
                raise ValueError("El horómetro final no puede ser menor que el inicial.")
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
    )


@app.route("/registros/<int:reg_id>/eliminar", methods=["POST"])
@login_required
def eliminar_registro(reg_id):
    models.eliminar_registro(reg_id)
    flash("Registro eliminado.", "success")
    return redirect(request.referrer or url_for("formulario"))


@app.route("/accesos")
@login_required
def accesos():
    return render_template("accesos.html", accesos=models.listar_accesos(limit=200))


@app.route("/parametros", methods=["GET", "POST"])
@login_required
def parametros():
    if request.method == "POST":
        campos_num = [
            "anio", "precio_combustible", "costo_operador_hora", "consumo_objetivo",
            "rendimiento_objetivo", "intervalo_mantencion", "horometro_ultima_mantencion",
            "aviso_anticipado", "profundidad_zanja_cm", "ancho_zanja_cm",
        ]
        campos_txt = ["codigo_interno", "nombre", "marca", "modelo", "numero_serie"]
        data = {c: request.form.get(c) for c in campos_txt}
        for c in campos_num:
            try:
                data[c] = float(request.form.get(c) or 0)
            except ValueError:
                data[c] = 0
        data["anio"] = int(data["anio"])
        models.update_parametros(data)
        flash("Parámetros actualizados.", "success")
        return redirect(url_for("parametros"))
    return render_template("parametros.html", params=models.get_parametros())


# ---------- API JSON (para el gráfico del tablero) ----------

@app.route("/api/registros")
@login_required
def api_registros():
    return jsonify(models.listar_registros(limit=500))


@app.route("/api/resumen")
@login_required
def api_resumen():
    return jsonify(models.resumen_kpis())


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG") == "1")
