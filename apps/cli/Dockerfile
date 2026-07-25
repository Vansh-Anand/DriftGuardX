# Stage 1: Build
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

RUN addgroup --system appgroup && adduser --system --group appuser
USER appuser

COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

COPY --chown=appuser:appgroup packages/ ./packages/
COPY --chown=appuser:appgroup apps/cli/ ./apps/cli/

ENTRYPOINT ["python", "-m", "apps.cli.experiments"]
