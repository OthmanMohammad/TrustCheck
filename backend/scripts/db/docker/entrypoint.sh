#!/bin/bash
# Production entrypoint for web service
set -e

echo "🚀 Starting TrustCheck Application"

# Wait for database
/app/scripts/utils/wait-for-postgres.sh

# Run migrations if not in development
if [ "$ENVIRONMENT" != "development" ]; then
  echo "📦 Running database migrations..."
  alembic upgrade head || {
    echo "❌ Migration failed!"
    exit 1
  }
else
  echo "⚠️  Skipping migrations in development mode"
fi

# Verify database connectivity
python -c "
from src.infrastructure.database.connection import db_manager
import asyncio
asyncio.run(db_manager.check_connection())
" || {
  echo "❌ Database connection check failed!"
  exit 1
}

echo "✅ All checks passed, starting application..."

# Execute the main command
exec "$@"