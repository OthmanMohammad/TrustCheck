"""
Dependency Injection - Async Only
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.uow import get_uow_factory
from src.infrastructure.database.repositories.sanctioned_entity import SQLAlchemySanctionedEntityRepository
from src.infrastructure.database.repositories.change_event import SQLAlchemyChangeEventRepository
from src.infrastructure.database.repositories.scraper_run import SQLAlchemyScraperRunRepository
from src.infrastructure.database.repositories.content_snapshot import SQLAlchemyContentSnapshotRepository

from src.services.change_detection.service import ChangeDetectionService
from src.services.scraping.service import ScrapingOrchestrationService
from src.services.notification.service import NotificationService

from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Repository dependencies
async def get_sanctioned_entity_repository(
    db: AsyncSession = Depends(get_db)
) -> SQLAlchemySanctionedEntityRepository:
    """Get sanctioned entity repository."""
    return SQLAlchemySanctionedEntityRepository(db)

async def get_change_event_repository(
    db: AsyncSession = Depends(get_db)
) -> SQLAlchemyChangeEventRepository:
    """Get change event repository."""
    return SQLAlchemyChangeEventRepository(db)

async def get_scraper_run_repository(
    db: AsyncSession = Depends(get_db)
) -> SQLAlchemyScraperRunRepository:
    """Get scraper run repository."""
    return SQLAlchemyScraperRunRepository(db)

async def get_content_snapshot_repository(
    db: AsyncSession = Depends(get_db)
) -> SQLAlchemyContentSnapshotRepository:
    """Get content snapshot repository."""
    return SQLAlchemyContentSnapshotRepository(db)

# Service dependencies
def get_change_detection_service() -> ChangeDetectionService:
    """Get change detection service."""
    uow_factory = get_uow_factory()
    return ChangeDetectionService(uow_factory)

def get_scraping_service() -> ScrapingOrchestrationService:
    """Get scraping orchestration service."""
    uow_factory = get_uow_factory()
    return ScrapingOrchestrationService(uow_factory)

def get_notification_service() -> NotificationService:
    """Get notification service."""
    return NotificationService()

__all__ = [
    'get_sanctioned_entity_repository',
    'get_change_event_repository',
    'get_scraper_run_repository',
    'get_content_snapshot_repository',
    'get_change_detection_service',
    'get_scraping_service',
    'get_notification_service'
]