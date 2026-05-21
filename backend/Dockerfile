# Dockerfile esplicito per Railway. Bypassa il bug Nixpacks su pip install uv==$NIXPACKS_UV_V.
# uv installato via installer ufficiale Astral (pin a 0.11.x), poi uv sync --frozen.
# release: alembic upgrade head viene eseguito una volta all'avvio del container.

FROM python:3.12-slim

# uv installer ufficiale ha bisogno di curl + ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Installa uv (versione stabile pinned per riproducibilità).
ENV UV_INSTALL_DIR=/usr/local/bin
RUN curl -LsSf https://astral.sh/uv/0.11.15/install.sh | sh

WORKDIR /app

# Sfrutta la cache Docker: lock file separato dal resto del codice.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

# Railway inietta $PORT a runtime; default 8080 in locale.
ENV PORT=8080

# Alembic upgrade idempotente + start uvicorn. Migration già applicate sono no-op.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
