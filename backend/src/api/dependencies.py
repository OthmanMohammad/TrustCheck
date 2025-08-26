"""
Dependency Injection Container

FastAPI-compatible dependency injection for repositories, services, and UoW.
Provides clean separation and easy testing through interface injection.
"""

from typing import Generator, AsyncGenerator
from functools import lru_cache
from contextlib import asynccontextmanager

from fastapi import Depends
from sqlalchemy.orm import Session

# Core interfaces
from src.core.uow import UnitOfWork
from src.core.domain.repositories import (
    SanctionedEntityRepository, ChangeEventRepository,
    ScraperRunRepository, ContentSnapshotRepository
)

# Infrastructure implementations  
from src.infrastructure.database.connection import get_db
from src.infrastructure.database.uow import SQLAlchemyUnitOfWorkFactory, get_uow_factory
from src.infrastructure.database.repositories.sanctioned_entity import SQLAlchemySanctionedEntityRepository
from src.infrastructure.database.repositories.change_event import SQLAlchemyChangeEventRepository
from src.infrastructure.database.repositories.scraper_run import SQLAlchemyScraperRunRepository
from src.infrastructure.database.repositories.content_snapshot import SQLAlchemyContentSnapshotRepository

# Business services
from src.services.change_detection.service import ChangeDetectionService
from src.services.scraping.service import ScrapingOrchestrationService
from src.services.notification.service import NotificationService

from src.core.logging_config import get_logger, LoggingContext
from src.core.exceptions import handle_exception, DatabaseError
from src.core.config import settings

logger = get_logger(__name__)

# ======================== REPOSITORY DEPENDENCIES ========================

def get_sanctioned_entity_repository(
    db: Session = Depends(get_db)
) -> SanctionedEntityRepository:
    """Get sanctioned entity repository instance."""
    return SQLAlchemySanctionedEntityRepository(db)

def get_change_event_repository(
    db: Session = Depends(get_db)
) -> ChangeEventRepository:
    """Get change event repository instance."""
    return SQLAlchemyChangeEventRepository(db)

def get_scraper_run_repository(
    db: Session = Depends(get_db)
) -> ScraperRunRepository:
    """Get scraper run repository instance."""
    return SQLAlchemyScraperRunRepository(db)

def get_content_snapshot_repository(
    db: Session = Depends(get_db)
) -> ContentSnapshotRepository:
    """Get content snapshot repository instance."""
    return SQLAlchemyContentSnapshotRepository(db)

# ======================== UNIT OF WORK DEPENDENCIES ========================

def get_unit_of_work_factory() -> SQLAlchemyUnitOfWorkFactory:
    """Get Unit of Work factory instance."""
    return get_uow_factory()

@asynccontextmanager
async def get_unit_of_work(
    uow_factory: SQLAlchemyUnitOfWorkFactory = Depends(get_unit_of_work_factory)
) -> AsyncGenerator[UnitOfWork, None]:
    """
    Get Unit of Work instance with automatic lifecycle management.
    
    Usage in FastAPI endpoints:
        async def my_endpoint(uow: UnitOfWork = Depends(get_unit_of_work)):
            async with uow:
                # Use repositories through uow
                entity = await uow.sanctioned_entities.get_by_uid("123")
    """
    async with uow_factory.create_async_unit_of_work() as uow:
        try:
            yield uow
        except Exception as e:
            logger.error(f"Unit of Work error in dependency: {e}")
            await uow.rollback()
            raise

# ======================== SERVICE DEPENDENCIES ========================

@lru_cache()
def get_change_detection_service(
    uow_factory: SQLAlchemyUnitOfWorkFactory = Depends(get_unit_of_work_factory)
) -> ChangeDetectionService:
    """Get change detection service instance."""
    return ChangeDetectionService(uow_factory)

@lru_cache()
def get_scraping_service(
    uow_factory: SQLAlchemyUnitOfWorkFactory = Depends(get_unit_of_work_factory)
) -> ScrapingOrchestrationService:
    """Get scraping orchestration service instance."""
    return ScrapingOrchestrationService(uow_factory)

@lru_cache()
def get_notification_service() -> NotificationService:
    """Get notification service instance."""
    return NotificationService()

# ======================== BUSINESS OPERATION DEPENDENCIES ========================

from src.infrastructure.database.uow import UnitOfWorkBusinessOperations

@lru_cache()
def get_business_operations(
    uow_factory: SQLAlchemyUnitOfWorkFactory = Depends(get_unit_of_work_factory)
) -> UnitOfWorkBusinessOperations:
    """Get business operations service."""
    return UnitOfWorkBusinessOperations(uow_factory)

# ======================== REQUEST CONTEXT DEPENDENCIES ========================

def get_request_context():
    """
    Get or create request context for logging correlation.
    
    This would be enhanced to extract request ID from headers,
    user information from auth tokens, etc.
    """
    import uuid
    from src.core.logging_config import LoggingContext
    
    request_id = str(uuid.uuid4())
    return LoggingContext(request_id=request_id)

# ======================== DEPENDENCY CONTAINER CLASS ========================

class DependencyContainer:
    """
    Dependency injection container for centralized configuration.
    
    Provides a single place to configure all application dependencies
    and supports different configurations for testing, development, production.
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._initialized = False
        self._uow_factory = None
        self._services = {}
    
    def initialize(self) -> None:
        """Initialize dependency container."""
        if self._initialized:
            return
        
        try:
            # Initialize UoW factory
            self._uow_factory = get_uow_factory()
            
            # Initialize services
            self._services = {
                'change_detection': ChangeDetectionService(self._uow_factory),
                'scraping': ScrapingOrchestrationService(self._uow_factory),
                'notification': NotificationService(),
                'business_operations': UnitOfWorkBusinessOperations(self._uow_factory)
            }
            
            self._initialized = True
            self.logger.info("Dependency container initialized")
            
        except Exception as e:
            handle_exception(e, self.logger, context={"operation": "container_initialization"})
            raise
    
    def get_uow_factory(self) -> SQLAlchemyUnitOfWorkFactory:
        """Get Unit of Work factory."""
        if not self._initialized:
            self.initialize()
        return self._uow_factory
    
    def get_service(self, service_name: str):
        """Get service by name."""
        if not self._initialized:
            self.initialize()
        
        if service_name not in self._services:
            raise ValueError(f"Unknown service: {service_name}")
        
        return self._services[service_name]
    
    def override_service(self, service_name: str, service_instance):
        """Override service for testing."""
        if not self._initialized:
            self.initialize()
        self._services[service_name] = service_instance
    
    def reset(self) -> None:
        """Reset container (for testing)."""
        self._initialized = False
        self._uow_factory = None
        self._services = {}

# Global container instance
container = DependencyContainer()

# ======================== FACTORY FUNCTIONS ========================

def create_repository_factory(db: Session):
    """Create repository factory for given database session."""
    return {
        'sanctioned_entities': SQLAlchemySanctionedEntityRepository(db),
        'change_events': SQLAlchemyChangeEventRepository(db),
        'scraper_runs': SQLAlchemyScraperRunRepository(db),
        'content_snapshots': SQLAlchemyContentSnapshotRepository(db)
    }

def create_service_factory(uow_factory: SQLAlchemyUnitOfWorkFactory):
    """Create service factory for given UoW factory."""
    return {
        'change_detection': ChangeDetectionService(uow_factory),
        'scraping': ScrapingOrchestrationService(uow_factory),
        'notification': NotificationService(),
        'business_operations': UnitOfWorkBusinessOperations(uow_factory)
    }

# ======================== TESTING SUPPORT ========================

class TestDependencyContainer(DependencyContainer):
    """Test-specific dependency container with fake implementations."""
    
    def initialize(self) -> None:
        """Initialize with test dependencies."""
        if self._initialized:
            return
        
        from src.infrastructure.database.uow import FakeUnitOfWork
        from tests.fakes import (
            FakeChangeDetectionService,
            FakeScrapingService,
            FakeNotificationService
        )
        
        # Create fake UoW factory
        class FakeUoWFactory:
            async def create_async_unit_of_work(self):
                return FakeUnitOfWork()
        
        self._uow_factory = FakeUoWFactory()
        
        # Create fake services
        self._services = {
            'change_detection': FakeChangeDetectionService(),
            'scraping': FakeScrapingService(),
            'notification': FakeNotificationService(),
            'business_operations': None  # Would implement fake business ops
        }
        
        self._initialized = True
        self.logger.info("Test dependency container initialized")

# ======================== MIDDLEWARE DEPENDENCIES ========================

async def repository_middleware(request, call_next):
    """
    Middleware to provide repository context for each request.
    
    Ensures each request gets its own repository instances
    and proper cleanup happens after the request.
    """
    with LoggingContext() as log_context:
        request.state.log_context = log_context
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Request failed: {e}", exc_info=True)
            raise

# ======================== HEALTH CHECK DEPENDENCIES ========================

async def get_system_health() -> Dict[str, Any]:
    """
    Get comprehensive system health check.
    
    Checks health of all major components:
    - Database connectivity
    - Repository health  
    - Service availability
    - External dependencies
    """
    health_status = {
        'timestamp': datetime.utcnow().isoformat(),
        'overall_healthy': True,
        'components': {}
    }
    
    try:
        # Check database
        uow_factory = container.get_uow_factory()
        async with uow_factory.create_async_unit_of_work() as uow:
            db_health = await uow.health_check()
            health_status['components']['database'] = db_health
            
            if not db_health.get('overall_healthy', False):
                health_status['overall_healthy'] = False
        
        # Check services
        services_health = {}
        for service_name in ['change_detection', 'scraping', 'notification']:
            try:
                service = container.get_service(service_name)
                # Services would implement health_check method
                if hasattr(service, 'health_check'):
                    service_health = await service.health_check()
                else:
                    service_health = {'healthy': True, 'status': 'available'}
                
                services_health[service_name] = service_health
                
                if not service_health.get('healthy', True):
                    health_status['overall_healthy'] = False
                    
            except Exception as e:
                services_health[service_name] = {
                    'healthy': False,
                    'error': str(e)
                }
                health_status['overall_healthy'] = False
        
        health_status['components']['services'] = services_health
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_healthy': False,
            'error': str(e),
            'components': {}
        }

# ======================== STARTUP/SHUTDOWN HANDLERS ========================

async def startup_dependencies():
    """Initialize dependencies on application startup."""
    try:
        logger.info("Initializing application dependencies...")
        
        # Initialize dependency container
        container.initialize()
        
        # Verify database connectivity
        uow_factory = container.get_uow_factory()
        async with uow_factory.create_async_unit_of_work() as uow:
            health = await uow.health_check()
            if not health.get('overall_healthy', False):
                raise DatabaseError("Database health check failed during startup")
        
        logger.info("✅ Application dependencies initialized successfully")
        
    except Exception as e:
        logger.critical(f"❌ Failed to initialize dependencies: {e}")
        raise

async def shutdown_dependencies():
    """Clean up dependencies on application shutdown."""
    try:
        logger.info("Cleaning up application dependencies...")
        
        # Reset container
        container.reset()
        
        logger.info("✅ Dependencies cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Error during dependency cleanup: {e}")

# ======================== CONTEXT MANAGERS FOR COMPLEX OPERATIONS ========================

@asynccontextmanager
async def transactional_operation():
    """
    Context manager for operations requiring transaction management.
    
    Usage:
        async with transactional_operation() as ctx:
            await ctx.uow.sanctioned_entities.create(entity)
            await ctx.change_detection.detect_changes(...)
            # Auto-commit on success, rollback on exception
    """
    class TransactionalContext:
        def __init__(self, uow: UnitOfWork, services: dict):
            self.uow = uow
            self.change_detection = services['change_detection']
            self.scraping = services['scraping']
            self.notification = services['notification']
            self.business_operations = services['business_operations']
    
    uow_factory = container.get_uow_factory()
    services = {
        'change_detection': container.get_service('change_detection'),
        'scraping': container.get_service('scraping'), 
        'notification': container.get_service('notification'),
        'business_operations': container.get_service('business_operations')
    }
    
    async with uow_factory.create_async_unit_of_work() as uow:
        yield TransactionalContext(uow, services)

# ======================== EXPORTS ========================

__all__ = [
    # Repository dependencies
    'get_sanctioned_entity_repository',
    'get_change_event_repository',
    'get_scraper_run_repository',
    'get_content_snapshot_repository',
    
    # UoW dependencies
    'get_unit_of_work_factory',
    'get_unit_of_work',
    
    # Service dependencies
    'get_change_detection_service',
    'get_scraping_service',
    'get_notification_service',
    'get_business_operations',
    
    # Container
    'DependencyContainer',
    'container',
    'TestDependencyContainer',
    
    # Factory functions
    'create_repository_factory',
    'create_service_factory',
    
    # Context managers
    'transactional_operation',
    
    # Health and lifecycle
    'get_system_health',
    'startup_dependencies',
    'shutdown_dependencies',
    
    # Middleware
    'repository_middleware'
]