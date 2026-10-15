FROM python:3.12-slim

# Chromium para convertir los artes HTML a PNG; fuentes para que el texto se vea bien
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium fonts-liberation fonts-lato fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATA_DIR=/data \
    AGENCIA_DIR=/app/agencia \
    CHROME=/usr/bin/chromium \
    PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
