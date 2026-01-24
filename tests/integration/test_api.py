"""
TrustCheck API Integration Tests.

Tests for the FastAPI endpoints.
"""

import os
import pathlib

# Clean up any existing test database first
_test_db_file = pathlib.Path("test_trustcheck.db")
if _test_db_file.exists():
    _test_db_file.unlink()

# Set test database URL BEFORE any imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_trustcheck.db"
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "true"

# Clear settings cache before importing trustcheck
import sys
# Remove any cached trustcheck modules to force reimport with new env vars
modules_to_remove = [k for k in sys.modules.keys() if k.startswith("trustcheck")]
for mod in modules_to_remove:
    del sys.modules[mod]

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def test_app():
    """Create a test application with clean database."""
    from trustcheck.config import get_settings, settings
    from trustcheck.database.models import Base
    import trustcheck.database.connection as db_conn

    # Reset the global engine if it exists
    if db_conn._engine is not None:
        await db_conn._engine.dispose()
        db_conn._engine = None
    db_conn._session_factory = None

    # Create fresh engine
    engine = db_conn.get_engine()

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Import and configure app
    from fastapi import FastAPI
    from trustcheck.api.routes import (
        health_router,
        entities_router,
        screening_router,
        changes_router,
        admin_router,
    )

    # Create minimal test app (without lifespan to avoid scheduler/db conflicts)
    app = FastAPI(
        title="TrustCheck Test",
        version="1.0.0",
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(entities_router)
    app.include_router(screening_router)
    app.include_router(changes_router)
    app.include_router(admin_router)

    yield app

    # Cleanup tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Dispose engine
    await engine.dispose()
    db_conn._engine = None
    db_conn._session_factory = None

    # Clean up test database file
    if _test_db_file.exists():
        _test_db_file.unlink()


@pytest.fixture
async def client(test_app):
    """Create an async test client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestRootEndpoint:
    """Tests for the root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_api_info(self, client: AsyncClient):
        """Test root endpoint returns API information."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "docs" in data


class TestHealthEndpoint:
    """Tests for the health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "database" in data
        assert "scheduler" in data
        assert "timestamp" in data


class TestEntitiesEndpoints:
    """Tests for entities endpoints."""

    @pytest.mark.asyncio
    async def test_list_entities_empty(self, client: AsyncClient):
        """Test listing entities when database is empty."""
        response = await client.get("/api/entities")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_list_entities_with_pagination(self, client: AsyncClient):
        """Test listing entities with pagination parameters."""
        response = await client.get("/api/entities?limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "pagination" in data
        if data["pagination"]:
            assert data["pagination"]["limit"] == 10
            assert data["pagination"]["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_entities_with_filters(self, client: AsyncClient):
        """Test listing entities with filters."""
        response = await client.get("/api/entities?entity_type=INDIVIDUAL&active_only=true")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, client: AsyncClient):
        """Test getting non-existent entity."""
        response = await client.get("/api/entities/non-existent-id")

        # Should return 404 or error response
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_search_entities(self, client: AsyncClient):
        """Test entity search endpoint."""
        response = await client.get(
            "/api/entities/search",
            params={"query": "John Smith", "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data


class TestScreeningEndpoints:
    """Tests for screening endpoints."""

    @pytest.mark.asyncio
    async def test_screen_name(self, client: AsyncClient):
        """Test screening a single name."""
        response = await client.post(
            "/api/screen",
            json={
                "name": "John Smith",
                "threshold": 0.8,
                "max_results": 10
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "request_id" in data
        assert "query" in data
        assert "matches" in data
        assert "screened_at" in data
        assert "processing_time_ms" in data

    @pytest.mark.asyncio
    async def test_screen_name_with_options(self, client: AsyncClient):
        """Test screening with additional options."""
        response = await client.post(
            "/api/screen",
            json={
                "name": "Mohammad Ali Khan",
                "threshold": 0.7,
                "include_inactive": True,
                "max_results": 50
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["query"] == "Mohammad Ali Khan"

    @pytest.mark.asyncio
    async def test_screen_name_validation_empty(self, client: AsyncClient):
        """Test screening with empty name."""
        response = await client.post(
            "/api/screen",
            json={"name": ""}
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_screen_name_validation_threshold(self, client: AsyncClient):
        """Test screening with invalid threshold."""
        response = await client.post(
            "/api/screen",
            json={"name": "John Smith", "threshold": 1.5}
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_screening(self, client: AsyncClient):
        """Test batch screening endpoint."""
        response = await client.post(
            "/api/screen/batch",
            json={
                "names": ["John Smith", "Jane Doe", "Mohammad Ali"],
                "threshold": 0.8
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["total_names"] == 3
        assert "total_matches" in data
        assert "results" in data

    @pytest.mark.asyncio
    async def test_batch_screening_empty_list(self, client: AsyncClient):
        """Test batch screening with empty list."""
        response = await client.post(
            "/api/screen/batch",
            json={"names": []}
        )

        # Should return validation error
        assert response.status_code == 422


class TestChangesEndpoints:
    """Tests for changes endpoints."""

    @pytest.mark.asyncio
    async def test_list_changes_empty(self, client: AsyncClient):
        """Test listing changes when database is empty."""
        response = await client.get("/api/changes")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data

    @pytest.mark.asyncio
    async def test_list_changes_with_filters(self, client: AsyncClient):
        """Test listing changes with filters."""
        response = await client.get("/api/changes?source=OFAC_SDN&change_type=ADDED")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_get_change_stats(self, client: AsyncClient):
        """Test getting change statistics."""
        response = await client.get("/api/changes/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        if data["data"]:
            assert "changes_last_24h" in data["data"]
            assert "changes_last_7d" in data["data"]


class TestAdminEndpoints:
    """Tests for admin endpoints."""

    @pytest.mark.asyncio
    async def test_get_system_status(self, client: AsyncClient):
        """Test getting system status."""
        response = await client.get("/api/admin/status")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "version" in data
        assert "environment" in data
        assert "database_connected" in data
        assert "scheduler_running" in data

    @pytest.mark.asyncio
    async def test_get_dashboard_stats(self, client: AsyncClient):
        """Test getting dashboard statistics."""
        response = await client.get("/api/admin/dashboard")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        if data["data"]:
            assert "total_entities" in data["data"]
            assert "active_entities" in data["data"]


class TestValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_screen_name_too_long(self, client: AsyncClient):
        """Test screening with name exceeding max length."""
        long_name = "A" * 600
        response = await client.post(
            "/api/screen",
            json={"name": long_name}
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_screening_too_many_names(self, client: AsyncClient):
        """Test batch screening exceeding max names."""
        # Generate more than 10000 names
        names = [f"Name {i}" for i in range(10001)]
        response = await client.post(
            "/api/screen/batch",
            json={"names": names}
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_entity_type_filter(self, client: AsyncClient):
        """Test listing with invalid entity type."""
        response = await client.get("/api/entities?entity_type=INVALID_TYPE")

        # Should either return validation error or empty results
        # depending on implementation
        assert response.status_code in [200, 400, 422]


class TestResponseFormat:
    """Tests for consistent response format."""

    @pytest.mark.asyncio
    async def test_success_response_format(self, client: AsyncClient):
        """Test successful response format."""
        response = await client.get("/api/entities")

        assert response.status_code == 200
        data = response.json()

        # All successful responses should have 'success' field
        assert "success" in data
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_error_response_format(self, client: AsyncClient):
        """Test error response format."""
        # Invalid JSON should trigger error
        response = await client.post(
            "/api/screen",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [400, 422]


class TestContentTypes:
    """Tests for content type handling."""

    @pytest.mark.asyncio
    async def test_json_content_type(self, client: AsyncClient):
        """Test JSON content type in response."""
        response = await client.get("/api/entities")

        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_accepts_json_request(self, client: AsyncClient):
        """Test API accepts JSON requests."""
        response = await client.post(
            "/api/screen",
            json={"name": "Test Name"},
            headers={"Accept": "application/json"}
        )

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
