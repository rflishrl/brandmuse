# Build stage using Python with Astral uv
FROM python:3.12-slim AS builder

# Install uv by copying the standalone binary from official uv image
COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies using uv
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Final runtime stage
FROM python:3.12-slim AS runtime

RUN useradd -m -u 1000 appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PORT=10000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy virtual environment and application source
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser apps/api/app/ ./app/
COPY --chown=appuser:appuser apps/api/alembic/ ./alembic/
COPY --chown=appuser:appuser apps/api/alembic.ini ./

USER appuser

EXPOSE 10000

# Start Uvicorn bound to dynamic PORT provided by Render (defaults to 10000)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers"]
