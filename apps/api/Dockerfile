FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY packages/ ./packages/
COPY apps/api/ ./apps/api/

# Run database migrations then start server
CMD ["sh", "-c", "cd apps/api && alembic upgrade head && cd /app && uvicorn apps.api.src.main:app --host 0.0.0.0 --port 8000"]

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
