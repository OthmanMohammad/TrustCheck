"""
Dependency Injection Container - FIXED with Auto-Detection

Automatically provides sync or async repositories based on the session type.
"""

from typing import Generator, AsyncGenerator, Dict, Any, Union
from functools import lru_cache
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

# Core interfaces
from src.core.uow import UnitOfWork
from src.core.domain.repositories import (
    SanctionedEntityRepository, ChangeEventRepository,
    ScraperRunRepository, ContentSnapshotRepository
)

# Infrastructure implementations  
from src.infrastructure.database.connection import get_db, get_async_db
from src.infrastructure.database.uow import SQLAlchemyUnitOfWorkFactory, get_uow_factory

# Repository implementations (now support both sync and async)
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

# ======================== V1 SYNC REPOSITORY DEPENDENCIES ========================

def get_sanctioned_entity_repository(
    db: Session = Depends(get_db)
) -> SQLAlchemySanctionedEntityRepository:
    """Get sanctioned entity repository instance for v1 API (sync)."""
    return SQLAlchemySanctionedEntityRepository(db)

def get_change_event_repository(
    db: Session = Depends(get_db)
) -> SQLAlchemyChangeEventRepository:
    """Get change event repository instance for v1 API (sync)."""
    return SQLAlchemyChangeEventRepository(db)

def get_scraper_run_repository(
    db: Session = Depends(get_db)
) -> SQLAlchemyScraperRunRepository:
    """Get scraper run repository instance for v1 API (sync)."""
    return SQLAlchemyScraperRunRepository(db)

def get_content_snapshot_repository(
    db: Session = Depends(get_db)
) -> SQLAlchemyContentSnapshotRepository:
    """Get content snapshot repository instance for v1 API (sync)."""
    return SQLAlchemyContentSnapshotRepository(db)

# ======================== V2 ASYNC REPOSITORY DEPENDENCIES ========================

async def get_async_sanctioned_entity_repository(
    db: AsyncSession = Depends(get_async_db)
) -> SQLAlchemySanctionedEntityRepository:
    """Get sanctioned entity repository instance for v2 API (async)."""
    # Same class, but initialized with AsyncSession
    return SQLAlchemySanctionedEntityRepository(db)

async def get_async_change_event_repository(
    db: AsyncSession = Depends(get_async_db)
) -> SQLAlchemyChangeEventRepository:
    """Get change event repository instance for v2 API (async)."""
    # Same class, but initialized with AsyncSession
    return SQLAlchemyChangeEventRepository(db)

async def get_async_scraper_run_repository(
    db: AsyncSession = Depends(get_async_db)
) -> SQLAlchemyScraperRunRepository:
    """Get scraper run repository instance for v2 API (async)."""
    # Same class, but initialized with AsyncSession
    return SQLAlchemyScraperRunRepository(db)

async def get_async_content_snapshot_repository(
    db: AsyncSession = Depends(get_async_db)
) -> SQLAlchemyContentSnapshotRepository:
    """Get content snapshot repository instance for v2 API (async)."""
    # Same class, but initialized with AsyncSession
    return SQLAlchemyContentSnapshotRepository(db)

# ======================== UNIT OF WORK DEPENDENCIES ========================

def get_unit_of_work_factory() -> SQLAlchemyUnitOfWorkFactory:
    """Get Unit of Work factory instance."""
    return get_uow_factory()

@asynccontextmanager
async def get_unit_of_work(
    uow_factory: SQLAlchemyUnitOfWorkFactory = Depends(get_unit_of_work_factory)
) -> AsyncGenerator[UnitOfWork, None]:
    """Get Unit of Work instance with automatic lifecycle management."""
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

# ======================== HEALTH CHECK DEPENDENCIES ========================

async def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health check."""
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
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_healthy': False,
            'error': str(e),
            'components': {}
        }

# ======================== DEPENDENCY CONTAINER CLASS ========================

class DependencyContainer:
    """Dependency injection container for centralized configuration."""
    
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
            self._uow_factory = get_uow_factory()
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
    
    def get_uow_factory(self):
        """Get UoW factory."""
        if not self._initialized:
            self.initialize()
        return self._uow_factory

# Global container instance
container = DependencyContainer()

# ======================== EXPORTS ========================

__all__ = [
    # Sync repositories (v1)
    'get_sanctioned_entity_repository',
    'get_change_event_repository',
    'get_scraper_run_repository',
    'get_content_snapshot_repository',
    
    # Async repositories (v2)
    'get_async_sanctioned_entity_repository',
    'get_async_change_event_repository',
    'get_async_scraper_run_repository',
    'get_async_content_snapshot_repository',
    
    # Services
    'get_change_detection_service',
    'get_scraping_service',
    'get_notification_service',
    'get_business_operations',
    
    # UoW
    'get_unit_of_work_factory',
    'get_unit_of_work',
    
    # Health
    'get_system_health',
    
    # Container
    'container'
]