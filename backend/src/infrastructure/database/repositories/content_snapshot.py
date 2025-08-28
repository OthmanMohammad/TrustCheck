"""
SQLAlchemy Content Snapshot Repository Implementation - FIXED with Proper Async Support
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, text, func, select
from sqlalchemy.exc import SQLAlchemyError
import asyncio
from functools import wraps

from src.core.domain.entities import ContentSnapshotDomain
from src.core.domain.repositories import ContentSnapshotRepository
from src.core.enums import DataSource
from src.core.exceptions import DatabaseError, handle_exception
from src.infrastructure.database.models import ContentSnapshot as ContentSnapshotORM
from src.core.logging_config import get_logger

logger = get_logger(__name__)

def async_compatible(func):
    """Decorator to make sync methods callable from async context."""
    @wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        if self.is_async:
            return await self._execute_async(func.__name__, *args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, self, *args, **kwargs)
    
    func.async_version = async_wrapper
    return func

class SQLAlchemyContentSnapshotRepository:
    """
    SQLAlchemy implementation of ContentSnapshotRepository.
    Supports both sync and async operations.
    """
    
    def __init__(self, session: Union[Session, AsyncSession]):
        self.session = session
        self.is_async = isinstance(session, AsyncSession)
        self.logger = get_logger(__name__)
    
    def _orm_to_domain(self, orm_snapshot: ContentSnapshotORM) -> ContentSnapshotDomain:
        """Convert ORM model to domain entity."""
        if not orm_snapshot:
            return None
            
        try:
            source = DataSource(orm_snapshot.source) if orm_snapshot.source else DataSource.OFAC
        except (ValueError, KeyError):
            source = DataSource.OFAC
        
        return ContentSnapshotDomain(
            snapshot_id=orm_snapshot.snapshot_id,
            source=source,
            content_hash=orm_snapshot.content_hash or '',
            content_size_bytes=orm_snapshot.content_size_bytes or 0,
            snapshot_time=orm_snapshot.snapshot_time or datetime.utcnow(),
            scraper_run_id=orm_snapshot.scraper_run_id or '',
            s3_archive_path=orm_snapshot.s3_archive_path
        )
    
    def _domain_to_orm(self, domain_snapshot: ContentSnapshotDomain) -> ContentSnapshotORM:
        """Convert domain entity to ORM model."""
        return ContentSnapshotORM(
            snapshot_id=domain_snapshot.snapshot_id,
            source=domain_snapshot.source.value if hasattr(domain_snapshot.source, 'value') else str(domain_snapshot.source),
            content_hash=domain_snapshot.content_hash,
            content_size_bytes=domain_snapshot.content_size_bytes,
            snapshot_time=domain_snapshot.snapshot_time,
            scraper_run_id=domain_snapshot.scraper_run_id,
            s3_archive_path=domain_snapshot.s3_archive_path
        )
    
    async def _execute_async(self, method_name: str, *args, **kwargs):
        """Execute the async version of a method."""
        method = getattr(self, f'_async_{method_name}')
        return await method(*args, **kwargs)
    
    # ======================== SYNC METHODS (for v1 API) ========================
    
    @async_compatible
    def create(self, snapshot: ContentSnapshotDomain) -> ContentSnapshotDomain:
        """Create content snapshot (sync)."""
        try:
            orm_snapshot = self._domain_to_orm(snapshot)
            self.session.add(orm_snapshot)
            self.session.flush()
            
            return self._orm_to_domain(orm_snapshot)
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "create_content_snapshot",
                "source": snapshot.source.value if hasattr(snapshot.source, 'value') else str(snapshot.source)
            })
            raise DatabaseError("Failed to create content snapshot", cause=e)
    
    @async_compatible
    def get_by_id(self, snapshot_id: UUID) -> Optional[ContentSnapshotDomain]:
        """Get snapshot by ID (sync)."""
        try:
            orm_snapshot = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.snapshot_id == snapshot_id
            ).first()
            
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_snapshot_by_id",
                "snapshot_id": str(snapshot_id)
            })
            raise DatabaseError("Failed to get snapshot", cause=e)
    
    @async_compatible
    def get_latest_snapshot(
        self,
        source: DataSource
    ) -> Optional[ContentSnapshotDomain]:
        """Get most recent snapshot for a source (sync)."""
        try:
            source_value = source.value if hasattr(source, 'value') else str(source)
            orm_snapshot = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.source == source_value
            ).order_by(desc(ContentSnapshotORM.snapshot_time)).first()
            
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_latest_snapshot",
                "source": source_value
            })
            raise DatabaseError("Failed to get latest snapshot", cause=e)
    
    @async_compatible
    def get_last_content_hash(self, source: DataSource) -> Optional[str]:
        """Get content hash from most recent snapshot (sync)."""
        try:
            source_value = source.value if hasattr(source, 'value') else str(source)
            result = self.session.query(ContentSnapshotORM.content_hash).filter(
                ContentSnapshotORM.source == source_value
            ).order_by(desc(ContentSnapshotORM.snapshot_time)).first()
            
            return result.content_hash if result else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_last_content_hash",
                "source": source_value
            })
            raise DatabaseError("Failed to get last content hash", cause=e)
    
    @async_compatible
    def has_content_changed(
        self,
        source: DataSource,
        new_content_hash: str
    ) -> bool:
        """Check if content has changed since last snapshot (sync)."""
        try:
            last_hash = self.get_last_content_hash(source)
            return last_hash != new_content_hash if last_hash else True
            
        except Exception as e:
            handle_exception(e, self.logger, context={
                "operation": "has_content_changed",
                "source": source.value if hasattr(source, 'value') else str(source),
                "new_hash": new_content_hash
            })
            raise DatabaseError("Failed to check content change", cause=e)
    
    # ======================== ASYNC METHODS (for v2 API) ========================
    
    async def _async_create(self, snapshot: ContentSnapshotDomain) -> ContentSnapshotDomain:
        """Create content snapshot (async)."""
        try:
            orm_snapshot = self._domain_to_orm(snapshot)
            self.session.add(orm_snapshot)
            await self.session.flush()
            
            return self._orm_to_domain(orm_snapshot)
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_create_content_snapshot",
                "source": snapshot.source.value if hasattr(snapshot.source, 'value') else str(snapshot.source)
            })
            raise DatabaseError("Failed to create content snapshot", cause=e)
    
    async def _async_get_by_id(self, snapshot_id: UUID) -> Optional[ContentSnapshotDomain]:
        """Get snapshot by ID (async)."""
        try:
            query = select(ContentSnapshotORM).where(
                ContentSnapshotORM.snapshot_id == snapshot_id
            )
            result = await self.session.execute(query)
            orm_snapshot = result.scalar_one_or_none()
            
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_get_snapshot_by_id",
                "snapshot_id": str(snapshot_id)
            })
            raise DatabaseError("Failed to get snapshot", cause=e)
    
    async def _async_get_latest_snapshot(
        self,
        source: DataSource
    ) -> Optional[ContentSnapshotDomain]:
        """Get most recent snapshot for a source (async)."""
        try:
            source_value = source.value if hasattr(source, 'value') else str(source)
            query = select(ContentSnapshotORM).where(
                ContentSnapshotORM.source == source_value
            ).order_by(desc(ContentSnapshotORM.snapshot_time))
            
            result = await self.session.execute(query)
            orm_snapshot = result.scalar_one_or_none()
            
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_get_latest_snapshot",
                "source": source_value
            })
            raise DatabaseError("Failed to get latest snapshot", cause=e)
    
    async def _async_get_last_content_hash(self, source: DataSource) -> Optional[str]:
        """Get content hash from most recent snapshot (async)."""
        try:
            source_value = source.value if hasattr(source, 'value') else str(source)
            query = select(ContentSnapshotORM.content_hash).where(
                ContentSnapshotORM.source == source_value
            ).order_by(desc(ContentSnapshotORM.snapshot_time))
            
            result = await self.session.execute(query)
            row = result.first()
            
            return row.content_hash if row else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_get_last_content_hash",
                "source": source_value
            })
            raise DatabaseError("Failed to get last content hash", cause=e)
    
    async def _async_has_content_changed(
        self,
        source: DataSource,
        new_content_hash: str
    ) -> bool:
        """Check if content has changed since last snapshot (async)."""
        try:
            last_hash = await self._async_get_last_content_hash(source)
            return last_hash != new_content_hash if last_hash else True
            
        except Exception as e:
            handle_exception(e, self.logger, context={
                "operation": "async_has_content_changed",
                "source": source.value if hasattr(source, 'value') else str(source),
                "new_hash": new_content_hash
            })
            raise DatabaseError("Failed to check content change", cause=e)
    
    # ======================== HEALTH CHECK ========================
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            if self.is_async:
                await self.session.execute(text("SELECT 1"))
            else:
                self.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    # ======================== METHOD RESOLUTION ========================
    
    def __getattr__(self, name):
        """Route method calls to sync or async versions based on context."""
        if name in ['create', 'get_by_id', 'get_latest_snapshot', 'get_last_content_hash', 'has_content_changed']:
            base_method = getattr(self, name, None)
            if base_method and hasattr(base_method, 'async_version'):
                return base_method.async_version
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")