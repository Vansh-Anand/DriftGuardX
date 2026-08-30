# Stage 1: Create the runtime environment from the canonical frozen lock.
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY apps/ ./apps/
COPY packages/ ./packages/
RUN python -m pip install --no-cache-dir uv==0.11.23 \
    && uv sync --frozen --no-dev --extra infra

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

# Non-root user
RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

# Copy the path-stable frozen environment built at the same /app prefix.
COPY --from=builder /app/.venv /app/.venv

COPY --chown=appuser:appgroup packages/ ./packages/
COPY --chown=appuser:appgroup apps/api/ ./apps/api/
COPY --chown=appuser:appgroup uv.lock ./uv.lock

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=3)" || exit 1

# Schema migration is an explicit one-shot deployment job. API replicas never
# race one another to mutate the database schema during startup.
CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
