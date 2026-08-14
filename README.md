# Control de Maquinaria — Zanjadora (MAQ-001)

App web para reemplazar la planilla "Control de Maquinaria" en Excel: varios operadores cargan su jornada desde un formulario, y el tablero se actualiza solo (no hay que regenerar nada a mano).

## Qué incluye

- **Formulario** (`/formulario`): carga diaria (fecha, turno, operador, horómetros, combustible, avance). Calcula automáticamente horas operadas, consumo, volumen excavado, rendimiento, costos y estado de mantención — con las mismas fórmulas validadas contra la planilla original y el modelo de Power BI.
- **Tablero** (`/`): las mismas tarjetas de indicadores que la hoja "Resumen" (horas totales, combustible, consumo promedio, desvío vs objetivo, avance, costos) + gráfico de evolución + tabla de registros.
- **Parámetros** (`/parametros`): precio combustible, costo operador, objetivos de consumo/rendimiento, datos de mantención — editables sin tocar código.
- **Acceso con contraseña compartida** (simple, para uso interno del equipo). No hay usuarios individuales todavía — ver sección "Siguientes pasos" si más adelante quieres login por persona.

## Probar en tu computador (opcional)

```bash
pip install -r requirements.txt
export APP_PASSWORD="la-clave-que-quieras"
python3 app.py
```

Abre http://localhost:5000 — te va a pedir nombre y la contraseña que definiste en `APP_PASSWORD`.

## Desplegarlo para que tus usuarios lo usen de verdad

Necesitas un hosting porque este archivo no puede quedar corriendo solo en tu computador o en esta sesión de Claude. Dos opciones, ambas gratis para este tamaño de uso:

### Opción recomendada: Fly.io (tiene disco persistente gratis)

Los datos (`zanjadora.db`) se guardan en un archivo. Fly.io permite un volumen persistente sin costo, así que los registros no se pierden entre actualizaciones — por eso es la opción recomendada por sobre Render/Railway en su plan gratuito.

1. Crea una cuenta en https://fly.io e instala `flyctl` (`curl -L https://fly.io/install.sh | sh`).
2. Dentro de esta carpeta: `fly auth login`, luego `fly launch` (elige un nombre, región `scl` para Chile, y responde "No" cuando pregunte si quiere desplegar altiro).
3. Copia `fly.toml.example` a `fly.toml` si `fly launch` no generó uno con volumen, y ajusta el nombre de la app.
4. Crea el volumen: `fly volumes create zanjadora_data --size 1 --region scl`
5. Define tus variables secretas:
   ```bash
   fly secrets set APP_PASSWORD="elige-una-clave-segura" SECRET_KEY="una-cadena-larga-aleatoria"
   ```
6. Despliega: `fly deploy`
7. Tu app queda en `https://<nombre-que-elegiste>.fly.dev` — ese es el link que compartes con los operadores.

### Alternativa: Render.com (más simple de clickear, pero el disco persistente requiere plan pago desde ~USD 7/mes)

1. Sube esta carpeta a un repositorio de GitHub.
2. En Render: **New → Web Service**, conecta el repo.
3. Build command: `pip install -r requirements.txt` — Start command: `gunicorn app:app`.
4. En **Environment**, agrega `APP_PASSWORD` y `SECRET_KEY`.
5. Si quieres que los datos sobrevivan a cada despliegue, agrega un **Disk** (requiere plan pago) montado en `/data` y define la variable `DB_PATH=/data/zanjadora.db`. Sin esto, cada vez que actualices el código se borra la base de datos.

## Siguientes pasos posibles (dime si quieres que los agregue)

- Login individual por operador (usuario + contraseña propia, en vez de una clave compartida) — la tabla `usuarios` ya está creada en `models.py`, solo falta conectarla.
- Exportar los registros a Excel/CSV desde el tablero.
- Editar un registro ya cargado (hoy solo se puede eliminar y volver a cargar).
- Notificación automática (correo/WhatsApp) cuando el estado de mantención pase a "Alerta".
- Respaldo automático de la base de datos.
