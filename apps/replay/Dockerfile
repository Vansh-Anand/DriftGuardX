FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY apps/ ./apps/
COPY packages/ ./packages/
RUN python -m pip install --no-cache-dir uv==0.11.23 \
    && uv sync --frozen --no-dev --extra infra

FROM python:3.11-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --no-create-home --shell /usr/sbin/nologin appuser
COPY --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appgroup packages/ ./packages/
COPY --chown=appuser:appgroup uv.lock ./uv.lock
USER appuser
ENTRYPOINT ["python"]
