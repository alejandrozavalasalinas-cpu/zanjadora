# Control de Maquinaria — Zanjadora (MAQ-001)

App web para reemplazar la planilla "Control de Maquinaria" en Excel: varios operadores cargan su jornada desde un formulario, y el tablero se actualiza solo (no hay que regenerar nada a mano).

## Qué incluye

- **Formulario** (`/formulario`): carga diaria (fecha, turno, operador, poza, horómetros, combustible, avance, uso del sistema automático en horas, reemplazo de picas). Calcula automáticamente horas operadas, consumo, volumen excavado, rendimiento, costos y estado de mantención — con las mismas fórmulas validadas contra la planilla original y el modelo de Power BI. Los registros ya cargados se pueden editar o eliminar.
- **Tablero** (`/`): las mismas tarjetas de indicadores que la hoja "Resumen" (horas totales, combustible, consumo promedio, desvío vs objetivo, avance, costos, % de utilización del sistema automático, picas reemplazadas) + gráfico de evolución (costo, avance y combustible) + tabla de registros + tabla de picas reemplazadas por mes. Se puede filtrar por año/mes/poza, y exportar los registros a Excel/CSV. Al filtrar por una poza específica, muestra además el % de avance en metros lineales y en m³ (según la meta de esa poza) y el % de utilización del sistema automático en ella.
- **Parámetros** (`/parametros`): precio combustible, costo operador, objetivos de consumo/rendimiento, datos de mantención, ancho de zanja — editables sin tocar código. También permite crear/eliminar las **pozas** de trabajo, cada una con su meta de metros lineales totales y su altura de corte (usados para calcular el % de avance y m³ en el tablero).
- **Cuentas individuales por operador** (`/registro` y `/login`): cada persona crea su propia cuenta (usuario sin espacios + contraseña de al menos 6 caracteres) usando la **clave de equipo** como código de invitación — sin conocerla no se puede crear una cuenta. Una vez registrado, cada quien entra con su propio usuario y contraseña; la clave de equipo ya no sirve para entrar directo, solo para registrarse. El historial de accesos (quién entró y cuándo) queda disponible en `/accesos`.
- **Rol "visor" (solo tablero, sin costos)**: además del rol normal ("operador", que se auto-asigna al registrarse), existe un rol restringido que solo puede ver el Tablero — sin acceso a Formulario, Parámetros, Accesos, ni a editar/eliminar registros — y en el que no se muestran las tarjetas de "Costo total acumulado", "Costo por hora" ni "Costo por metro". No hay un formulario público para crear cuentas con este rol (para que nadie se lo pueda auto-asignar); se crea manualmente en la base de datos con `rol = 'visor'`.

## Probar en tu computador (opcional)

```bash
pip install -r requirements.txt
export APP_PASSWORD="la-clave-de-equipo-que-quieras"
python3 app.py
```

Abre http://localhost:5000, entra a "Crear una" cuenta usando la clave que definiste en `APP_PASSWORD` como clave de equipo, y desde ahí inicia sesión con tu usuario y contraseña propios.

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

Desde entonces, cada `git push` a `main` dispara un deploy automático vía GitHub Actions (`.github/workflows/fly-deploy.yml`), usando el secreto `FLY_API_TOKEN` configurado en el repo.

### Alternativa: Render.com (más simple de clickear, pero el disco persistente requiere plan pago desde ~USD 7/mes)

1. Sube esta carpeta a un repositorio de GitHub.
2. En Render: **New → Web Service**, conecta el repo.
3. Build command: `pip install -r requirements.txt` — Start command: `gunicorn app:app`.
4. En **Environment**, agrega `APP_PASSWORD` y `SECRET_KEY`.
5. Si quieres que los datos sobrevivan a cada despliegue, agrega un **Disk** (requiere plan pago) montado en `/data` y define la variable `DB_PATH=/data/zanjadora.db`. Sin esto, cada vez que actualices el código se borra la base de datos.

## Siguientes pasos posibles (dime si quieres que los agregue)

- Notificación automática (correo/WhatsApp) cuando el estado de mantención pase a "Alerta".
- Respaldo automático de la base de datos.
