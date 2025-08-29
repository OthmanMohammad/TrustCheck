#!/bin/bash
# Comprehensive testing script

set -e

echo "🧪 TrustCheck Complete Test Suite"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "\n${YELLOW}Testing: $test_name${NC}"
    if eval "$test_command"; then
        echo -e "${GREEN}✅ $test_name passed${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}❌ $test_name failed${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# 1. Environment Setup Test
run_test "Environment configuration" "test -f backend/.env || cp backend/.env.example backend/.env"

# 2. Docker Build Test
run_test "Docker image build" "docker-compose build --quiet"

# 3. Database Connection Test
run_test "PostgreSQL startup" "docker-compose up -d postgres && sleep 5 && docker-compose exec -T postgres pg_isready"

# 4. Redis Connection Test
run_test "Redis startup" "docker-compose up -d redis && sleep 2 && docker-compose exec -T redis redis-cli ping | grep -q PONG"

# 5. Database Migration Test
run_test "Database migrations" "docker-compose run --rm web alembic upgrade head"

# 6. API Startup Test
run_test "API startup" "docker-compose up -d web && sleep 10 && curl -f http://localhost:8000/health"

# 7. API Endpoints Test
run_test "API v2 entities endpoint" "curl -f http://localhost:8000/api/v2/entities"
run_test "API v2 changes endpoint" "curl -f http://localhost:8000/api/v2/changes"

# 8. Celery Worker Test
run_test "Celery worker startup" "docker-compose up -d worker && sleep 5 && docker-compose exec -T worker celery -A src.celery_app.app inspect ping"

# 9. Celery Beat Test
run_test "Celery beat startup" "docker-compose up -d beat && sleep 5 && docker-compose ps beat | grep -q Up"

# 10. Flower Monitoring Test
run_test "Flower dashboard" "docker-compose up -d flower && sleep 5 && curl -f http://admin:changeme@localhost:5555/api/workers"

# 11. Scraper Test (if OFAC is accessible)
run_test "OFAC scraper task" "docker-compose exec -T worker celery -A src.celery_app.app call src.tasks.scraping_tasks.check_scraper_health_task"

# 12. Database Query Test
run_test "Database query" "docker-compose exec -T postgres psql -U postgres -d trustcheck -c 'SELECT COUNT(*) FROM sanctioned_entities;'"

# 13. Health Check Test
run_test "Container health checks" "docker-compose ps | grep -v unhealthy"

# 14. Logs Check
run_test "No critical errors in logs" "! docker-compose logs --tail=100 2>&1 | grep -i 'critical\\|fatal'"

# Print results
echo -e "\n=================================="
echo -e "Test Results:"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}⚠️  Some tests failed. Please check the output above.${NC}"
    exit 1
fi