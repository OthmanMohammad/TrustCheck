"""
Test file to verify async API v1 endpoints work correctly
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel
from src.core.domain.entities import (
    SanctionedEntityDomain, ChangeEventDomain, Address, FieldChange
)
from src.api.change_detection import router
from src.api.dependencies import (
    get_sanctioned_entity_repository,
    get_change_event_repository,
    get_change_detection_service
)

# Create test app
app = FastAPI()
app.include_router(router)

# Create mock repositories with async methods
class MockSanctionedEntityRepository:
    async def find_all(self, active_only=True, limit=None, offset=0):
        """Mock async find_all method"""
        return [
            SanctionedEntityDomain(
                uid="TEST-001",
                name="Test Entity",
                entity_type=EntityType.PERSON,
                source=DataSource.OFAC,
                programs=["SDGT"],
                aliases=["Test Alias"],
                addresses=[Address(city="New York", country="USA")]
            )
        ]
    
    async def find_by_source(self, source, active_only=True, limit=None, offset=0):
        """Mock async find_by_source method"""
        return await self.find_all(active_only, limit, offset)
    
    async def find_by_entity_type(self, entity_type, limit=None, offset=0):
        """Mock async find_by_entity_type method"""
        return await self.find_all(True, limit, offset)
    
    async def search_by_name(self, name, fuzzy=False, limit=20, offset=0):
        """Mock async search_by_name method"""
        return await self.find_all(True, limit, offset)
    
    async def get_by_uid(self, uid):
        """Mock async get_by_uid method"""
        if uid == "TEST-001":
            return SanctionedEntityDomain(
                uid="TEST-001",
                name="Test Entity",
                entity_type=EntityType.PERSON,
                source=DataSource.OFAC,
                programs=["SDGT"],
                aliases=["Test Alias"],
                addresses=[Address(city="New York", country="USA")]
            )
        return None
    
    async def get_statistics(self):
        """Mock async get_statistics method"""
        return {
            'total_active': 100,
            'total_inactive': 10,
            'by_source': {'OFAC': 50, 'UN': 50},
            'by_type': {'PERSON': 60, 'COMPANY': 40}
        }
    
    async def health_check(self):
        """Mock async health_check method"""
        return True

class MockChangeEventRepository:
    async def find_recent(self, days=7, source=None, risk_level=None, limit=None, offset=0):
        """Mock async find_recent method"""
        return [
            ChangeEventDomain(
                entity_uid="TEST-001",
                entity_name="Test Entity",
                source=DataSource.OFAC,
                change_type=ChangeType.ADDED,
                risk_level=RiskLevel.HIGH,
                field_changes=[],
                change_summary="Entity added to OFAC list",
                scraper_run_id="RUN-001"
            )
        ]
    
    async def health_check(self):
        """Mock async health_check method"""
        return True

class MockChangeDetectionService:
    async def get_change_summary(self, days=7, source=None, risk_level=None):
        """Mock async get_change_summary method"""
        return {
            'period': {
                'days': days,
                'start_date': (datetime.utcnow() - timedelta(days=days)).isoformat(),
                'end_date': datetime.utcnow().isoformat()
            },
            'totals': {
                'total_changes': 10,
                'critical_changes': 2,
                'high_risk_changes': 3,
                'medium_risk_changes': 3,
                'low_risk_changes': 2
            },
            'by_type': {
                'added': 5,
                'modified': 3,
                'removed': 2
            }
        }
    
    async def get_critical_changes(self, hours=24, source=None):
        """Mock async get_critical_changes method"""
        return [
            ChangeEventDomain(
                entity_uid="CRITICAL-001",
                entity_name="Critical Entity",
                source=DataSource.OFAC,
                change_type=ChangeType.REMOVED,
                risk_level=RiskLevel.CRITICAL,
                field_changes=[
                    FieldChange(
                        field_name="programs",
                        old_value=["SDGT"],
                        new_value=[],
                        change_type="field_removed"
                    )
                ],
                change_summary="Entity removed from OFAC list",
                scraper_run_id="RUN-002"
            )
        ]

# Override dependencies
mock_entity_repo = MockSanctionedEntityRepository()
mock_change_repo = MockChangeEventRepository()
mock_change_service = MockChangeDetectionService()

app.dependency_overrides[get_sanctioned_entity_repository] = lambda: mock_entity_repo
app.dependency_overrides[get_change_event_repository] = lambda: mock_change_repo
app.dependency_overrides[get_change_detection_service] = lambda: mock_change_service

# Create test client
client = TestClient(app)

def test_list_entities():
    """Test that list_entities properly awaits async repository calls"""
    response = client.get("/api/v1/entities")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert len(data["data"]["entities"]) > 0
    assert data["data"]["statistics"]["total_active"] == 100

def test_search_entities():
    """Test that search_entities properly awaits async repository calls"""
    response = client.get("/api/v1/entities/search?name=Test")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert len(data["data"]["results"]) > 0

def test_get_entity_by_uid():
    """Test that get_entity_by_uid properly awaits async repository calls"""
    response = client.get("/api/v1/entities/TEST-001")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["data"]["uid"] == "TEST-001"

def test_list_changes():
    """Test that list_changes properly awaits async repository and service calls"""
    response = client.get("/api/v1/changes")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert len(data["data"]["changes"]) > 0
    assert data["data"]["summary"]["totals"]["total_changes"] == 10

def test_get_critical_changes():
    """Test that get_critical_changes properly awaits async service calls"""
    response = client.get("/api/v1/changes/critical")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert len(data["data"]["critical_changes"]) > 0
    assert data["data"]["critical_changes"][0]["risk_level"] == "CRITICAL"

def test_get_statistics():
    """Test that get_statistics properly awaits async repository and service calls"""
    response = client.get("/api/v1/statistics")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["data"]["entities"]["total_active"] == 100
    assert data["data"]["changes"]["totals"]["total_changes"] == 10

def test_health_check():
    """Test that health_check properly awaits async repository calls"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["entities_repository"] == "ok"
    assert data["checks"]["changes_repository"] == "ok"

if __name__ == "__main__":
    # Run tests
    print("Running async API v1 tests...")
    test_list_entities()
    print("✓ test_list_entities passed")
    test_search_entities()
    print("✓ test_search_entities passed")
    test_get_entity_by_uid()
    print("✓ test_get_entity_by_uid passed")
    test_list_changes()
    print("✓ test_list_changes passed")
    test_get_critical_changes()
    print("✓ test_get_critical_changes passed")
    test_get_statistics()
    print("✓ test_get_statistics passed")
    test_health_check()
    print("✓ test_health_check passed")
    print("\n✅ All tests passed!")