# TrustCheck Dockerfile
# Multi-stage build for optimal image size

# ===== Build Stage =====
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies (including PostgreSQL client libs for asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir build pip setuptools wheel && \
    pip install --no-cache-dir asyncpg && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels -e .

# ===== Production Stage =====
FROM python:3.12-slim as production

LABEL maintainer="TrustCheck Team"
LABEL description="TrustCheck Sanctions Screening Platform"
LABEL version="4.0.0"

# Create non-root user
RUN groupadd -r trustcheck && useradd -r -g trustcheck trustcheck

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* asyncpg && rm -rf /wheels

# Copy application code
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini .
COPY pyproject.toml .

# Create data directory and set permissions
RUN mkdir -p /app/data && chown -R trustcheck:trustcheck /app

USER trustcheck

# Environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "trustcheck.main", "serve", "--host", "0.0.0.0", "--port", "8000"]
