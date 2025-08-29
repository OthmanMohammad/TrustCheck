# TrustCheck Complete Test Suite for Windows

Write-Host "`n🧪 TrustCheck Complete Test Suite" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

$TESTS_PASSED = 0
$TESTS_FAILED = 0

function Test-Component {
    param(
        [string]$TestName,
        [scriptblock]$TestCommand
    )
    
    Write-Host "`nTesting: $TestName" -ForegroundColor Yellow
    try {
        & $TestCommand
        Write-Host "✅ $TestName passed" -ForegroundColor Green
        $script:TESTS_PASSED++
    }
    catch {
        Write-Host "❌ $TestName failed: $_" -ForegroundColor Red
        $script:TESTS_FAILED++
    }
}

# Change to root directory (3 levels up from script location)
Set-Location -Path "$PSScriptRoot\..\..\.."
Write-Host "Working directory: $(Get-Location)" -ForegroundColor Gray

# 0. Clean up first
Write-Host "`nCleaning up old containers..." -ForegroundColor Yellow
docker-compose down --remove-orphans -v 2>$null

# 1. Environment Setup Test
Test-Component "Environment configuration" {
    if (-not (Test-Path ".env")) {
        throw ".env file not found in root directory"
    }
    Write-Host "  Found .env file" -ForegroundColor Gray
}

# 2. Docker Build Test
Test-Component "Docker image build" {
    docker-compose build --quiet
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }
}

# 3. Start PostgreSQL
Test-Component "PostgreSQL startup" {
    docker-compose up -d postgres
    Write-Host "  Waiting for PostgreSQL to initialize..." -ForegroundColor Gray
    Start-Sleep -Seconds 10
    
    $result = docker-compose exec -T postgres pg_isready -U trustcheck_user -d trustcheck
    if ($LASTEXITCODE -ne 0) { 
        Write-Host "  PostgreSQL logs:" -ForegroundColor Red
        docker-compose logs --tail=20 postgres
        throw "PostgreSQL not ready" 
    }
}

# 4. Start Redis
Test-Component "Redis startup" {
    docker-compose up -d redis
    Start-Sleep -Seconds 3
    $result = docker-compose exec -T redis redis-cli ping
    if ($result -ne "PONG") { throw "Redis not responding" }
}

# 5. Database Migration Test
Test-Component "Database migrations" {
    docker-compose run --rm web alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Migrations failed" }
}

# 6. API Startup Test
Test-Component "API startup" {
    docker-compose up -d web
    Write-Host "  Waiting for API to start..." -ForegroundColor Gray
    Start-Sleep -Seconds 15
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
        $health = $response.Content | ConvertFrom-Json
        Write-Host "  API Status: $($health.status)" -ForegroundColor Gray
    } catch {
        Write-Host "  API logs:" -ForegroundColor Red
        docker-compose logs --tail=20 web
        throw "API not responding"
    }
}

# 7. Test API Endpoints
Test-Component "API v2 entities endpoint" {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/entities" -UseBasicParsing
    if ($response.StatusCode -ne 200) { throw "Entities endpoint failed" }
}

# 8. Celery Worker Test
Test-Component "Celery worker startup" {
    docker-compose up -d worker
    Start-Sleep -Seconds 10
    $result = docker-compose exec -T worker celery -A src.celery_app.app inspect ping 2>&1
    if ($LASTEXITCODE -ne 0) { 
        Write-Host "  Worker logs:" -ForegroundColor Red
        docker-compose logs --tail=20 worker
        throw "Worker not responding" 
    }
}

# 9. Show running containers
Write-Host "`n==================================" -ForegroundColor Cyan
Write-Host "Running Containers:" -ForegroundColor Cyan
docker-compose ps

# Print results
Write-Host "`n==================================" -ForegroundColor Cyan
Write-Host "Test Results:" -ForegroundColor Cyan
Write-Host "Passed: $TESTS_PASSED" -ForegroundColor Green
Write-Host "Failed: $TESTS_FAILED" -ForegroundColor Red

if ($TESTS_FAILED -eq 0) {
    Write-Host "`n🎉 All tests passed!" -ForegroundColor Green
    Write-Host "`nAccess points:" -ForegroundColor Cyan
    Write-Host "  API:     http://localhost:8000" -ForegroundColor White
    Write-Host "  Docs:    http://localhost:8000/docs" -ForegroundColor White
    Write-Host "  Flower:  http://localhost:5555" -ForegroundColor White
    exit 0
} else {
    Write-Host "`n⚠️  Some tests failed. Check the output above." -ForegroundColor Red
    exit 1
}