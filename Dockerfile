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

# Final runtime stage (Hugging Face Spaces runs as user ID 1000)
FROM python:3.12-slim AS runtime

RUN useradd -m -u 1000 appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    HOME="/home/appuser" \
    PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy virtual environment and application source
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser apps/api/app/ ./app/
COPY --chown=appuser:appuser apps/api/alembic/ ./alembic/
COPY --chown=appuser:appuser apps/api/alembic.ini ./

# Ensure write permissions for appuser on required directories
RUN mkdir -p /app/data /tmp && chown -R appuser:appuser /app /tmp /home/appuser

USER appuser

# Hugging Face Spaces listens on port 7860 by default
EXPOSE 7860

# Start Uvicorn bound to dynamic PORT (defaults to 7860 for Hugging Face Spaces, allows override)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
