"""
Test Configuration for TrustCheck

test setup with:
- Database fixtures and isolation
- Service mocking and dependency injection
- Test data factories
- Performance testing utilities
"""

import pytest
import asyncio
from typing import Generator, Dict, Any
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient
import os
import sys

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# Import application components
from src.main import app, get_entity_service, get_entity_repository, get_cache_service
from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models.base import Base
from src.infrastructure.database.repositories.entity_repository import EntityRepository
from src.services.entity_service import EntityService
from src.infrastructure.cache.redis_client import CacheService
from src.core.config.settings import settings
from src.core.enums import EntityType, SanctionsSource, RiskLevel, ChangeType
from src.domain.entities.sanctioned_entity import SanctionedEntity, EntityId


# ======================== TEST DATABASE CONFIGURATION ========================

# Test database URL (use SQLite for speed in tests)
TEST_DATABASE_URL = "sqlite:///./test_trustcheck.db"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {}
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# ======================== DATABASE FIXTURES ========================

@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine for the session."""
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def test_db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create a test database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def override_get_db(test_db_session):
    """Override the get_db dependency for testing."""
    def _override_get_db():
        yield test_db_session
    
    app.dependency_overrides[get_db] = _override_get_db
    yield test_db_session
    app.dependency_overrides.clear()


# ======================== SERVICE FIXTURES ========================

@pytest.fixture
def mock_cache_service() -> Mock:
    """Mock cache service for testing."""
    mock_cache = Mock(spec=CacheService)
    mock_cache.is_available = False
    mock_cache.get.return_value = None
    mock_cache.set.return_value = True
    mock_cache.delete.return_value = True
    mock_cache.get_stats.return_value = {
        'hit_count': 0,
        'miss_count': 0,
        'error_count': 0,
        'is_available': False
    }
    return mock_cache


@pytest.fixture
def entity_repository(test_db_session) -> EntityRepository:
    """Create entity repository for testing."""
    return EntityRepository(test_db_session)


@pytest.fixture
def entity_service(entity_repository, mock_cache_service) -> EntityService:
    """Create entity service with test dependencies."""
    # Create mock change repository
    mock_change_repo = Mock()
    
    return EntityService(
        entity_repository=entity_repository,
        change_repository=mock_change_repo,
        cache_service=mock_cache_service
    )


@pytest.fixture
def override_entity_service(entity_service):
    """Override entity service dependency for testing."""
    def _override_entity_service():
        return entity_service
    
    app.dependency_overrides[get_entity_service] = _override_entity_service
    yield entity_service
    app.dependency_overrides.clear()


# ======================== HTTP CLIENT FIXTURES ========================

@pytest.fixture
def test_client(override_get_db, override_entity_service) -> TestClient:
    """Create test client with dependency overrides."""
    return TestClient(app)


@pytest.fixture
def authenticated_client(test_client) -> TestClient:
    """Create authenticated test client."""
    # TODO: Add authentication headers when auth is implemented
    return test_client


# ======================== TEST DATA FACTORIES ========================

class EntityFactory:
    """Factory for creating test entities."""
    
    @staticmethod
    def create_entity_data(**kwargs) -> Dict[str, Any]:
        """Create entity data dictionary."""
        defaults = {
            'uid': f"TEST-{datetime.utcnow().timestamp()}",
            'name': 'Test Entity',
            'entity_type': EntityType.PERSON,
            'source': SanctionsSource.US_OFAC,
            'programs': ['SDGT'],
            'aliases': ['Test Alias'],
            'addresses': ['123 Test St, Test City'],
            'dates_of_birth': ['1980-01-01'],
            'places_of_birth': ['Test City'],
            'nationalities': ['US'],
            'remarks': 'Test entity for testing',
            'is_active': True
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    def create_domain_entity(**kwargs) -> SanctionedEntity:
        """Create domain entity for testing."""
        data = EntityFactory.create_entity_data(**kwargs)
        
        entity_id = EntityId(
            source=data['source'],
            uid=data['uid']
        )
        
        return SanctionedEntity(
            entity_id=entity_id,
            name=data['name'],
            entity_type=data['entity_type'],
            programs=data['programs'],
            aliases=data['aliases'],
            addresses=data['addresses'],
            dates_of_birth=data['dates_of_birth'],
            places_of_birth=data['places_of_birth'],
            nationalities=data['nationalities'],
            remarks=data['remarks'],
            is_active=data['is_active'],
            created_at=datetime.utcnow()
        )
    
    @staticmethod
    def create_multiple_entities(count: int, **kwargs) -> List[SanctionedEntity]:
        """Create multiple test entities."""
        entities = []
        for i in range(count):
            entity_kwargs = kwargs.copy()
            entity_kwargs['uid'] = f"TEST-{i}-{datetime.utcnow().timestamp()}"
            entity_kwargs['name'] = f"Test Entity {i}"
            entities.append(EntityFactory.create_domain_entity(**entity_kwargs))
        return entities


@pytest.fixture
def sample_entity() -> SanctionedEntity:
    """Create a sample entity for testing."""
    return EntityFactory.create_domain_entity()


@pytest.fixture
def sample_entities() -> List[SanctionedEntity]:
    """Create multiple sample entities for testing."""
    return EntityFactory.create_multiple_entities(5)


# ======================== API TEST FIXTURES ========================

@pytest.fixture
def api_headers() -> Dict[str, str]:
    """Standard API headers for testing."""
    return {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'TrustCheck-Test-Client/1.0'
    }


@pytest.fixture
def create_entity_payload() -> Dict[str, Any]:
    """Valid entity creation payload."""
    return {
        'uid': f"TEST-API-{datetime.utcnow().timestamp()}",
        'name': 'API Test Entity',
        'entity_type': 'PERSON',
        'source': 'US_OFAC',
        'programs': ['SDGT', 'TERRORISM'],
        'aliases': ['API Test Alias'],
        'addresses': ['456 API Test Ave, API City'],
        'dates_of_birth': ['1985-06-15'],
        'places_of_birth': ['API City'],
        'nationalities': ['US'],
        'remarks': 'Entity created for API testing'
    }


# ======================== MOCK FIXTURES ========================

@pytest.fixture
def mock_scraper():
    """Mock scraper for testing."""
    mock = Mock()
    mock.scrape_and_store.return_value = Mock(
        status="SUCCESS",
        entities_processed=100,
        entities_added=10,
        entities_updated=5,
        entities_removed=2,
        duration_seconds=30.5
    )
    return mock


@pytest.fixture
def mock_change_detector():
    """Mock change detector for testing."""
    mock = Mock()
    mock.detect_changes.return_value = ([], {
        'entities_added': 0,
        'entities_modified': 0,
        'entities_removed': 0,
        'critical_changes': 0,
        'high_risk_changes': 0,
        'medium_risk_changes': 0,
        'low_risk_changes': 0
    })
    return mock


@pytest.fixture
def mock_notification_service():
    """Mock notification service for testing."""
    mock = Mock()
    mock.dispatch_changes.return_value = {
        'status': 'success',
        'immediate_sent': 0,
        'high_priority_sent': 0,
        'low_priority_queued': 0,
        'failed': 0
    }
    return mock


# ======================== PERFORMANCE TEST FIXTURES ========================

@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = datetime.utcnow()
        
        def stop(self):
            self.end_time = datetime.utcnow()
        
        @property
        def duration_ms(self) -> float:
            if self.start_time and self.end_time:
                return (self.end_time - self.start_time).total_seconds() * 1000
            return 0
    
    return Timer()


# ======================== ASYNC TEST SUPPORT ========================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ======================== CLEANUP FIXTURES ========================

@pytest.fixture(autouse=True)
def cleanup_test_environment():
    """Automatic cleanup after each test."""
    yield
    # Cleanup operations can be added here
    # For example: clearing temporary files, resetting global state, etc.


# ======================== PARAMETRIZED TEST DATA ========================

@pytest.fixture(params=[
    EntityType.PERSON,
    EntityType.COMPANY,
    EntityType.VESSEL,
    EntityType.AIRCRAFT
])
def entity_type(request):
    """Parametrized entity types for testing."""
    return request.param


@pytest.fixture(params=[
    SanctionsSource.US_OFAC,
    SanctionsSource.UN_CONSOLIDATED,
    SanctionsSource.EU_CONSOLIDATED
])
def sanctions_source(request):
    """Parametrized sanctions sources for testing."""
    return request.param


# ======================== ERROR TESTING FIXTURES ========================

@pytest.fixture
def database_error_session(test_db_session):
    """Database session that raises errors for error testing."""
    class ErrorSession:
        def __init__(self, real_session):
            self.real_session = real_session
            self.should_error = False
        
        def __getattr__(self, name):
            if self.should_error and name in ['query', 'add', 'commit']:
                from src.core.exceptions import DatabaseOperationError
                raise DatabaseOperationError(f"Test database error in {name}")
            return getattr(self.real_session, name)
        
        def enable_errors(self):
            self.should_error = True
        
        def disable_errors(self):
            self.should_error = False
    
    return ErrorSession(test_db_session)


# ======================== VALIDATION TEST DATA ========================

@pytest.fixture
def invalid_entity_data():
    """Invalid entity data for validation testing."""
    return [
        # Missing required fields
        {'name': '', 'entity_type': 'PERSON', 'source': 'US_OFAC'},
        
        # Invalid entity type
        {'uid': 'TEST-1', 'name': 'Test', 'entity_type': 'INVALID', 'source': 'US_OFAC'},
        
        # Invalid source
        {'uid': 'TEST-2', 'name': 'Test', 'entity_type': 'PERSON', 'source': 'INVALID'},
        
        # Invalid dates
        {'uid': 'TEST-3', 'name': 'Test', 'entity_type': 'PERSON', 'source': 'US_OFAC',
         'dates_of_birth': ['invalid-date']},
        
        # Empty required arrays
        {'uid': 'TEST-4', 'name': 'Test', 'entity_type': 'PERSON', 'source': 'US_OFAC',
         'programs': []},
    ]


# ======================== INTEGRATION TEST FIXTURES ========================

@pytest.fixture
def integration_db_session():
    """Database session for integration tests (uses real test database)."""
    # This could connect to a dedicated integration test database
    # For now, use the same test database
    session = TestSessionLocal()
    yield session
    session.close()


# ======================== BENCHMARK FIXTURES ========================

@pytest.fixture
def benchmark_data():
    """Large dataset for benchmark testing."""
    return EntityFactory.create_multiple_entities(1000)


@pytest.fixture
def memory_profiler():
    """Memory profiling fixture for performance tests."""
    import tracemalloc
    
    class MemoryProfiler:
        def __init__(self):
            self.start_snapshot = None
            self.end_snapshot = None
        
        def start(self):
            tracemalloc.start()
            self.start_snapshot = tracemalloc.take_snapshot()
        
        def stop(self):
            self.end_snapshot = tracemalloc.take_snapshot()
            tracemalloc.stop()
        
        def get_memory_diff(self):
            if self.start_snapshot and self.end_snapshot:
                top_stats = self.end_snapshot.compare_to(
                    self.start_snapshot, 'lineno'
                )
                return top_stats
            return []
    
    return MemoryProfiler()


# ======================== HELPER FUNCTIONS ========================

def assert_entity_equals(actual: SanctionedEntity, expected: SanctionedEntity):
    """Helper function to compare entities in tests."""
    assert actual.name == expected.name
    assert actual.entity_type == expected.entity_type
    assert actual.entity_id.source == expected.entity_id.source
    assert actual.entity_id.uid == expected.entity_id.uid
    assert actual.programs == expected.programs
    assert actual.aliases == expected.aliases
    assert actual.is_active == expected.is_active


def create_test_change_event(entity: SanctionedEntity, change_type: ChangeType = ChangeType.ADDED):
    """Helper function to create test change events."""
    from src.services.change_detection.change_detector import EntityChange
    
    return EntityChange(
        entity_uid=entity.entity_id.uid,
        entity_name=entity.name,
        change_type=change_type.value,
        risk_level=RiskLevel.MEDIUM.value,
        field_changes=[],
        change_summary=f"Test {change_type.value.lower()} change for {entity.name}"
    )


# ======================== TEST MARKERS ========================

# Custom pytest markers for organizing tests
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "api: mark test as an API test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )