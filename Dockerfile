FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

# /data se monta como volumen persistente en el host (Fly.io, Railway, Render Disk, etc.)
ENV DB_PATH=/data/zanjadora.db
RUN mkdir -p /data

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 app:app"]
