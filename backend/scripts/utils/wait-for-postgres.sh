#!/bin/bash
# PostgreSQL readiness check
# More reliable than generic TCP port checking

set -e

# Configuration with defaults
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-trustcheck}"
MAX_RETRIES="${DB_MAX_RETRIES:-30}"
RETRY_INTERVAL="${DB_RETRY_INTERVAL:-2}"

echo "🔄 Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."

retries=0
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; do
  retries=$((retries + 1))
  
  if [ $retries -ge $MAX_RETRIES ]; then
    echo "❌ PostgreSQL did not become ready in time (${MAX_RETRIES} attempts)"
    exit 1
  fi
  
  echo "⏳ PostgreSQL is unavailable - sleeping (attempt $retries/$MAX_RETRIES)"
  sleep $RETRY_INTERVAL
done

echo "✅ PostgreSQL is ready!"

# Execute any command passed as arguments
exec "$@"