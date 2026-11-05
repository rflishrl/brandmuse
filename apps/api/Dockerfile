# Build stage using Python with Astral uv
FROM python:3.12-slim AS builder

# Install uv by copying the standalone binary from official uv image
COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies using uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

# Final runtime stage
FROM python:3.12-slim AS runtime

# Create non-root user
RUN groupadd -r brandmuse && useradd -r -g brandmuse -d /app brandmuse

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PORT=10000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application source and alembic configuration
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Change ownership to non-root user
RUN chown -R brandmuse:brandmuse /app

USER brandmuse

EXPOSE 10000

# Health check matching Render requirements
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '10000') + '/api/health').read()" || exit 1

# Start Uvicorn with proxy headers and binding to $PORT (Render provides dynamic $PORT)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers"]
