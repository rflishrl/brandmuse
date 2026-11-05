# Build stage using Astral uv
FROM ghcr.io/astral-sh/uv:0.5.21 AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies using uv
COPY apps/api/pyproject.toml apps/api/uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

# Final runtime stage for Hugging Face Spaces (runs as non-root user 1000 on port 7860)
FROM python:3.12-slim AS runtime

# Hugging Face Spaces requires user ID 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH="/app/.venv/bin:$PATH" \
    PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy virtual environment and application source
COPY --from=builder --chown=user:user /app/.venv /app/.venv
COPY --chown=user:user apps/api/app/ ./app/
COPY --chown=user:user apps/api/alembic/ ./alembic/
COPY --chown=user:user apps/api/alembic.ini ./

EXPOSE 7860

# Start Uvicorn bound to port 7860 for Hugging Face Spaces
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers"]
