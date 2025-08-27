"""
SQLAlchemy Content Snapshot Repository Implementation
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError

from src.core.domain.entities import ContentSnapshotDomain
from src.core.domain.repositories import ContentSnapshotRepository
from src.core.enums import DataSource
from src.core.exceptions import DatabaseError, handle_exception
from src.infrastructure.database.repositories.base import SQLAlchemyBaseRepository
from src.infrastructure.database.models import ContentSnapshot as ContentSnapshotORM

class SQLAlchemyContentSnapshotRepository(SQLAlchemyBaseRepository):
    """SQLAlchemy implementation of ContentSnapshotRepository."""
    
    def __init__(self, session: Session):
        super().__init__(session, ContentSnapshotORM)
    
    def _orm_to_domain(self, orm_snapshot: ContentSnapshotORM) -> ContentSnapshotDomain:
        """Convert ORM model to domain entity."""
        return ContentSnapshotDomain(
            snapshot_id=orm_snapshot.snapshot_id,
            source=DataSource(orm_snapshot.source),
            content_hash=orm_snapshot.content_hash,
            content_size_bytes=orm_snapshot.content_size_bytes,
            snapshot_time=orm_snapshot.snapshot_time,
            scraper_run_id=orm_snapshot.scraper_run_id,
            s3_archive_path=orm_snapshot.s3_archive_path
        )
    
    def _domain_to_orm(self, domain_snapshot: ContentSnapshotDomain) -> ContentSnapshotORM:
        """Convert domain entity to ORM model."""
        return ContentSnapshotORM(
            snapshot_id=domain_snapshot.snapshot_id,
            source=domain_snapshot.source.value,
            content_hash=domain_snapshot.content_hash,
            content_size_bytes=domain_snapshot.content_size_bytes,
            snapshot_time=domain_snapshot.snapshot_time,
            scraper_run_id=domain_snapshot.scraper_run_id,
            s3_archive_path=domain_snapshot.s3_archive_path
        )
    
    async def create(self, snapshot: ContentSnapshotDomain) -> ContentSnapshotDomain:
        """Create content snapshot."""
        try:
            orm_snapshot = self._domain_to_orm(snapshot)
            self.session.add(orm_snapshot)
            self.session.flush()
            
            return self._orm_to_domain(orm_snapshot)
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "create_content_snapshot",
                "source": snapshot.source.value
            })
            raise DatabaseError("Failed to create content snapshot", cause=e)
    
    async def get_latest_snapshot(
        self,
        source: DataSource
    ) -> Optional[ContentSnapshotDomain]:
        """Get most recent snapshot for a source."""
        try:
            orm_snapshot = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.source == source.value
            ).order_by(desc(ContentSnapshotORM.snapshot_time)).first()
            
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_latest_snapshot",
                "source": source.value
            })
            raise DatabaseError("Failed to get latest snapshot", cause=e)
    
    async def get_last_content_hash(self, source: DataSource) -> Optional[str]:
        """Get content hash from most recent snapshot."""
        try:
            result = self.session.query(ContentSnapshotORM.content_hash).filter(
                ContentSnapshotORM.source == source.value
            ).order_by(desc(ContentSnapshotORM.snapshot_time)).first()
            
            return result.content_hash if result else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_last_content_hash",
                "source": source.value
            })
            raise DatabaseError("Failed to get last content hash", cause=e)
    
    async def find_by_source(
        self,
        source: DataSource,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ContentSnapshotDomain]:
        """Find snapshots by source, ordered by time desc."""
        try:
            query = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.source == source.value
            ).order_by(desc(ContentSnapshotORM.snapshot_time)).offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_snapshots = query.all()
            return [self._orm_to_domain(orm_snapshot) for orm_snapshot in orm_snapshots]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_by_source",
                "source": source.value
            })
            raise DatabaseError("Failed to find snapshots by source", cause=e)