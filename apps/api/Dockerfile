# Stage 1: Build
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Non-root user
RUN addgroup --system appgroup && adduser --system --group appuser
USER appuser

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

COPY --chown=appuser:appgroup packages/ ./packages/
COPY --chown=appuser:appgroup apps/api/ ./apps/api/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start server
CMD ["sh", "-c", "cd apps/api && alembic upgrade head && cd /app && uvicorn apps.api.src.main:app --host 0.0.0.0 --port 8000"]
