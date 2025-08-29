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

# Wait for database to be ready
echo "Waiting for database..."
sleep 10

# Run migrations
echo "Running database migrations..."
docker-compose exec -T web alembic upgrade head 2>/dev/null || echo "Migrations already up to date"

# Check service health
echo ""
echo "======================================"
echo "Service Status:"
echo "======================================"
docker-compose ps

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