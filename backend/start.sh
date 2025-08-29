set -e  # Exit on error

echo "======================================"
echo "Starting TrustCheck Services"
echo "======================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running"
    exit 1
fi

# Build images
echo "Building Docker images..."
docker-compose build

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for database using proper health check
echo "Waiting for database to be ready..."
MAX_TRIES=30
TRIES=0
while [ $TRIES -lt $MAX_TRIES ]; do
    if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "Database is ready!"
        break
    fi
    TRIES=$((TRIES + 1))
    if [ $TRIES -eq $MAX_TRIES ]; then
        echo "Error: Database failed to start after $MAX_TRIES attempts"
        docker-compose logs postgres
        exit 1
    fi
    echo "Waiting for database... (attempt $TRIES/$MAX_TRIES)"
    sleep 2
done

# Run migrations with proper error handling
echo "Running database migrations..."
if docker-compose exec -T web alembic upgrade head; then
    echo "✅ Migrations completed successfully"
else
    echo "❌ Migration failed! Check logs below:"
    docker-compose logs web
    echo "Stopping services due to migration failure..."
    docker-compose down
    exit 1
fi

# Check service health
echo ""
echo "======================================"
echo "Service Status:"
echo "======================================"
docker-compose ps

# Verify API is responding
echo "Checking API health..."
MAX_TRIES=10
TRIES=0
while [ $TRIES -lt $MAX_TRIES ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API is healthy!"
        break
    fi
    TRIES=$((TRIES + 1))
    if [ $TRIES -eq $MAX_TRIES ]; then
        echo "⚠️  API health check failed after $MAX_TRIES attempts"
    fi
    sleep 2
done

echo ""
echo "======================================"
echo "TrustCheck is running!"
echo "======================================"
echo "API:     http://localhost:8000"
echo "Flower:  http://localhost:5555"
echo ""
echo "Commands:"
echo "  View logs:        docker-compose logs -f"
echo "  Stop services:    docker-compose down"
echo "  Restart services: docker-compose restart"
echo "======================================"