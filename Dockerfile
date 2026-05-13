FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY kgent/web_assets ../kgent/web_assets
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KGENT_HOST=0.0.0.0 \
    KGENT_PORT=8088

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY kgent ./kgent
COPY --from=frontend /app/kgent/web ./kgent/web

RUN pip install --upgrade pip && pip install ".[postgres]"

RUN useradd --create-home --shell /bin/bash kgent \
 && mkdir -p /data \
 && chown -R kgent:kgent /data /app
USER kgent

ENV KGENT_STORE_PATH=/data/index.json \
    KGENT_DB_URL=sqlite:////data/chat.db
VOLUME ["/data"]

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${KGENT_PORT}/api/health" || exit 1

CMD ["kgent", "serve", "--host", "0.0.0.0", "--port", "8088"]
