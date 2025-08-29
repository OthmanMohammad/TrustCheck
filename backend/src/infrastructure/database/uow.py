"""
SQLAlchemy Unit of Work - Async Implementation
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from src.core.logging_config import get_logger
from src.infrastructure.database.repositories.sanctioned_entity import SQLAlchemySanctionedEntityRepository
from src.infrastructure.database.repositories.change_event import SQLAlchemyChangeEventRepository
from src.infrastructure.database.repositories.scraper_run import SQLAlchemyScraperRunRepository
from src.infrastructure.database.repositories.content_snapshot import SQLAlchemyContentSnapshotRepository

logger = get_logger(__name__)

class SQLAlchemyUnitOfWork:
    """Async Unit of Work implementation."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(__name__)
        
        # Initialize repositories
        self.sanctioned_entities = SQLAlchemySanctionedEntityRepository(session)
        self.change_events = SQLAlchemyChangeEventRepository(session)
        self.scraper_runs = SQLAlchemyScraperRunRepository(session)
        self.content_snapshots = SQLAlchemyContentSnapshotRepository(session)
        
        self._committed = False
        self._rolled_back = False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        elif not self._committed and not self._rolled_back:
            await self.commit()
    
    async def commit(self) -> None:
        """Commit transaction."""
        if self._committed:
            return
        
        try:
            await self.session.commit()
            self._committed = True
            self.logger.debug("Transaction committed")
        except Exception as e:
            await self.rollback()
            raise
    
    async def rollback(self) -> None:
        """Rollback transaction."""
        if self._rolled_back:
            return
        
        try:
            await self.session.rollback()
            self._rolled_back = True
            self.logger.debug("Transaction rolled back")
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            self._rolled_back = True
            raise
    
    async def flush(self) -> None:
        """Flush pending changes."""
        await self.session.flush()
    
    @property
    def is_active(self) -> bool:
        """Check if UoW is active."""
        return not self._committed and not self._rolled_back
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all repositories."""
        health_results = {
            'sanctioned_entities': await self.sanctioned_entities.health_check(),
            'change_events': await self.change_events.health_check(),
            'scraper_runs': await self.scraper_runs.health_check(),
            'content_snapshots': await self.content_snapshots.health_check()
        }
        
        overall_healthy = all(health_results.values())
        
        return {
            'overall_healthy': overall_healthy,
            'repositories': health_results
        }

class SQLAlchemyUnitOfWorkFactory:
    """Factory for creating Unit of Work instances."""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.logger = get_logger(__name__)
    
    @asynccontextmanager
    async def create_async_unit_of_work(self):
        """Create async Unit of Work."""
        async with self.session_factory() as session:
            uow = SQLAlchemyUnitOfWork(session)
            try:
                yield uow
            except Exception:
                await uow.rollback()
                raise

# Dependency injection
from src.infrastructure.database.connection import db_manager

def get_uow_factory() -> SQLAlchemyUnitOfWorkFactory:
    """Get Unit of Work factory."""
    return SQLAlchemyUnitOfWorkFactory(db_manager.AsyncSessionLocal)

__all__ = ['SQLAlchemyUnitOfWork', 'SQLAlchemyUnitOfWorkFactory', 'get_uow_factory']