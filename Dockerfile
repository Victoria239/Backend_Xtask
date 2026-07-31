# XTask Backend Dockerfile
# Local dev: docker compose lo usa con CMD override
# Render: usa este CMD por defecto, mode monolith, $PORT inyectado
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Render inyecta $PORT (default 10000). Local docker-compose lo overridea.
ENV PORT=8000
EXPOSE 8000

# Monolith mode: gateway carga todos los routers en proceso (single web service).
CMD ["sh", "-c", "uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
