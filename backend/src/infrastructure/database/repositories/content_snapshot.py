"""
SQLAlchemy Content Snapshot Repository Implementation - FIXED
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, text, func
from sqlalchemy.exc import SQLAlchemyError

from src.core.domain.entities import ContentSnapshotDomain
from src.core.domain.repositories import ContentSnapshotRepository
from src.core.enums import DataSource
from src.core.exceptions import DatabaseError, handle_exception
from src.infrastructure.database.repositories.base import SQLAlchemyBaseRepository
from src.infrastructure.database.models import ContentSnapshot as ContentSnapshotORM

class SQLAlchemyContentSnapshotRepository(SQLAlchemyBaseRepository):
    """SQLAlchemy implementation of ContentSnapshotRepository - FIXED."""
    
    def __init__(self, session: Session):
        super().__init__(session, ContentSnapshotORM)
    
    def _orm_to_domain(self, orm_snapshot: ContentSnapshotORM) -> ContentSnapshotDomain:
        """Convert ORM model to domain entity - FIXED to handle None values."""
        
        # Handle None values for enums
        try:
            source = DataSource(orm_snapshot.source) if orm_snapshot.source else DataSource.OFAC
        except (ValueError, KeyError):
            source = DataSource.OFAC  # Default fallback
        
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
    
    # REMOVED async - these are synchronous operations
    def create(self, snapshot: ContentSnapshotDomain) -> ContentSnapshotDomain:
        """Create content snapshot."""
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
    
    def get_by_id(self, snapshot_id: UUID) -> Optional[ContentSnapshotDomain]:
        """Get snapshot by ID."""
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
    
    def get_latest_snapshot(
        self,
        source: DataSource
    ) -> Optional[ContentSnapshotDomain]:
        """Get most recent snapshot for a source."""
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
    
    def get_last_content_hash(self, source: DataSource) -> Optional[str]:
        """Get content hash from most recent snapshot."""
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
    
    def has_content_changed(
        self,
        source: DataSource,
        new_content_hash: str
    ) -> bool:
        """Check if content has changed since last snapshot."""
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
    
    # Keep async versions for compatibility
    async def create_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.create(*args, **kwargs)
    
    async def get_by_id_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.get_by_id(*args, **kwargs)
    
    async def get_latest_snapshot_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.get_latest_snapshot(*args, **kwargs)
    
    async def get_last_content_hash_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.get_last_content_hash(*args, **kwargs)
    
    async def has_content_changed_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.has_content_changed(*args, **kwargs)
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            self.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False