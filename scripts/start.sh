#!/bin/bash
# TrustCheck Production Startup Script
# Handles migrations and starts the server
#
# Usage: ./scripts/start.sh
# Environment variables:
#   DATABASE_URL - PostgreSQL connection string (required)
#   PORT - Server port (default: 8000)
#   HOST - Server host (default: 0.0.0.0)
#   SKIP_MIGRATIONS - Set to "true" to skip migrations
#   INITIAL_SCRAPE - Set to "true" to run initial scrape on startup

set -e

echo "========================================"
echo "  TrustCheck Production Startup"
echo "========================================"

# Check required environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

# Set defaults
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "Environment: ${ENVIRONMENT:-production}"
echo "Port: $PORT"

# Wait for database to be ready (with retry)
echo ""
echo "Checking database connection..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "
import asyncio
from trustcheck.database import check_db_connection
result = asyncio.run(check_db_connection())
exit(0 if result.get('connected') else 1)
" 2>/dev/null; then
        echo "Database connection successful!"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "Waiting for database... ($RETRY_COUNT/$MAX_RETRIES)"
        sleep 2
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Could not connect to database after $MAX_RETRIES attempts"
    exit 1
fi

# Run database migrations
if [ "$SKIP_MIGRATIONS" != "true" ]; then
    echo ""
    echo "Running database migrations..."
    alembic upgrade head
    echo "Migrations complete!"
else
    echo "Skipping migrations (SKIP_MIGRATIONS=true)"
fi

# Check if pg_trgm extension is enabled
echo ""
echo "Verifying pg_trgm extension..."
python -c "
import asyncio
from trustcheck.database import get_session_context
from sqlalchemy import text

async def check_extension():
    async with get_session_context() as session:
        result = await session.execute(text(\"SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'\"))
        row = result.fetchone()
        if not row:
            print('WARNING: pg_trgm extension not installed!')
            print('Fuzzy search may not work. Run: CREATE EXTENSION IF NOT EXISTS pg_trgm;')
        else:
            print('pg_trgm extension verified!')

asyncio.run(check_extension())
"

# Run initial scrape if requested
if [ "$INITIAL_SCRAPE" = "true" ]; then
    echo ""
    echo "Running initial sanctions data scrape..."
    python -m trustcheck.main scrape --all
    echo "Initial scrape complete!"
fi

# Start the server
echo ""
echo "========================================"
echo "  Starting TrustCheck Server"
echo "========================================"
echo "URL: http://$HOST:$PORT"
echo "Health: http://$HOST:$PORT/health"
echo "API Docs: http://$HOST:$PORT/docs"
echo "Web UI: http://$HOST:$PORT/ui/"
echo "========================================"
echo ""

exec python -m trustcheck.main serve --host "$HOST" --port "$PORT"
