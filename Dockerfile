# TrustCheck Dockerfile
# Multi-stage build for optimal image size

# ===== Build Stage =====
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir build pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels -e .

# ===== Production Stage =====
FROM python:3.12-slim as production

# Labels
LABEL maintainer="TrustCheck Team"
LABEL description="TrustCheck Sanctions Screening Platform"
LABEL version="3.0.0"

# Create non-root user for security
RUN groupadd -r trustcheck && useradd -r -g trustcheck trustcheck

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini .
COPY pyproject.toml .

# Create data directory for SQLite database
RUN mkdir -p /app/data && chown -R trustcheck:trustcheck /app

# Switch to non-root user
USER trustcheck

# Environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV DATABASE_URL=sqlite+aiosqlite:///data/trustcheck.db

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "trustcheck.main", "serve", "--host", "0.0.0.0", "--port", "8000"]
