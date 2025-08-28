"""
SQLAlchemy Content Snapshot Repository Implementation
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
        
        # FIXED: Handle None values for enums
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
                "source": snapshot.source.value if hasattr(snapshot.source, 'value') else str(snapshot.source)
            })
            raise DatabaseError("Failed to create content snapshot", cause=e)
    
    async def get_by_id(self, snapshot_id: UUID) -> Optional[ContentSnapshotDomain]:
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
    
    async def get_by_content_hash(self, content_hash: str) -> Optional[ContentSnapshotDomain]:
        """Get snapshot by content hash."""
        try:
            orm_snapshot = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.content_hash == content_hash
            ).first()
            
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_snapshot_by_hash",
                "content_hash": content_hash
            })
            raise DatabaseError("Failed to get snapshot by hash", cause=e)
    
    async def get_latest_snapshot(
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
    
    async def find_by_scraper_run(
        self,
        run_id: str
    ) -> Optional[ContentSnapshotDomain]:
        """Find snapshot by scraper run ID."""
        try:
            orm_snapshot = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.scraper_run_id == run_id
            ).first()
            
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_snapshot_by_run",
                "run_id": run_id
            })
            raise DatabaseError("Failed to find snapshot by run", cause=e)
    
    async def get_last_content_hash(self, source: DataSource) -> Optional[str]:
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
    
    async def has_content_changed(
        self,
        source: DataSource,
        new_content_hash: str
    ) -> bool:
        """Check if content has changed since last snapshot."""
        try:
            last_hash = await self.get_last_content_hash(source)
            return last_hash != new_content_hash if last_hash else True
            
        except Exception as e:
            handle_exception(e, self.logger, context={
                "operation": "has_content_changed",
                "source": source.value if hasattr(source, 'value') else str(source),
                "new_hash": new_content_hash
            })
            raise DatabaseError("Failed to check content change", cause=e)
    
    async def find_by_source(
        self,
        source: DataSource,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ContentSnapshotDomain]:
        """Find snapshots by source, ordered by time desc."""
        try:
            source_value = source.value if hasattr(source, 'value') else str(source)
            query = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.source == source_value
            ).order_by(desc(ContentSnapshotORM.snapshot_time)).offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_snapshots = query.all()
            return [self._orm_to_domain(orm_snapshot) for orm_snapshot in orm_snapshots]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_by_source",
                "source": source_value
            })
            raise DatabaseError("Failed to find snapshots by source", cause=e)
    
    async def find_recent(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None
    ) -> List[ContentSnapshotDomain]:
        """Find recent snapshots."""
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            query = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.snapshot_time >= since
            )
            
            if source:
                source_value = source.value if hasattr(source, 'value') else str(source)
                query = query.filter(ContentSnapshotORM.source == source_value)
            
            query = query.order_by(desc(ContentSnapshotORM.snapshot_time))
            
            if limit:
                query = query.limit(limit)
            
            orm_snapshots = query.all()
            return [self._orm_to_domain(orm_snapshot) for orm_snapshot in orm_snapshots]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_recent_snapshots",
                "hours": hours,
                "source": source.value if source and hasattr(source, 'value') else str(source) if source else None
            })
            raise DatabaseError("Failed to find recent snapshots", cause=e)
    
    async def find_duplicate_hashes(
        self,
        source: DataSource
    ) -> List[ContentSnapshotDomain]:
        """Find snapshots with duplicate content hashes."""
        try:
            # Fix the SQL query for finding duplicates
            subquery = self.session.query(
                ContentSnapshotORM.content_hash,
                func.count(ContentSnapshotORM.snapshot_id).label('count')
            ).filter(
                ContentSnapshotORM.source == source.value
            ).group_by(
                ContentSnapshotORM.content_hash
            ).having(
                func.count(ContentSnapshotORM.snapshot_id) > 1  # Fixed: count snapshot_id not content_hash
            ).subquery()
            
            orm_snapshots = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.content_hash.in_(
                    self.session.query(subquery.c.content_hash)
                )
            ).all()
            
            return [self._orm_to_domain(orm_snapshot) for orm_snapshot in orm_snapshots]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_duplicate_hashes",
                "source": source.value
            })
            raise DatabaseError("Failed to find duplicate hashes", cause=e)
    
    async def cleanup_old_snapshots(
        self,
        older_than_days: int = 30,
        keep_count: int = 10
    ) -> int:
        """Clean up old snapshots, keeping recent ones. Returns count deleted."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            
            # For each source, keep the most recent keep_count snapshots
            sources = self.session.query(
                ContentSnapshotORM.source
            ).distinct().all()
            
            total_deleted = 0
            
            for (source,) in sources:
                # Get IDs to keep
                keep_ids = self.session.query(
                    ContentSnapshotORM.snapshot_id
                ).filter(
                    ContentSnapshotORM.source == source
                ).order_by(
                    desc(ContentSnapshotORM.snapshot_time)
                ).limit(keep_count).all()
                
                keep_id_list = [id[0] for id in keep_ids]
                
                # Delete old snapshots not in keep list
                deleted = self.session.query(ContentSnapshotORM).filter(
                    ContentSnapshotORM.source == source,
                    ContentSnapshotORM.snapshot_time < cutoff_date,
                    ~ContentSnapshotORM.snapshot_id.in_(keep_id_list)
                ).delete(synchronize_session=False)
                
                total_deleted += deleted
            
            self.session.flush()
            return total_deleted
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "cleanup_old_snapshots",
                "older_than_days": older_than_days
            })
            raise DatabaseError("Failed to cleanup old snapshots", cause=e)
    
    async def get_storage_statistics(self) -> Dict[str, Any]:
        """Get storage statistics for snapshots."""
        try:
            from sqlalchemy import func
            
            # Get total stats
            total_stats = self.session.query(
                func.count(ContentSnapshotORM.snapshot_id).label('total_snapshots'),
                func.sum(ContentSnapshotORM.content_size_bytes).label('total_size_bytes'),
                func.min(ContentSnapshotORM.snapshot_time).label('oldest_snapshot'),
                func.max(ContentSnapshotORM.snapshot_time).label('newest_snapshot')
            ).first()
            
            # Get stats by source
            source_stats = self.session.query(
                ContentSnapshotORM.source,
                func.count(ContentSnapshotORM.snapshot_id).label('count'),
                func.sum(ContentSnapshotORM.content_size_bytes).label('size_bytes')
            ).group_by(ContentSnapshotORM.source).all()
            
            return {
                'total_snapshots': total_stats.total_snapshots or 0,
                'total_size_bytes': total_stats.total_size_bytes or 0,
                'total_size_mb': (total_stats.total_size_bytes or 0) / (1024 * 1024),
                'oldest_snapshot': total_stats.oldest_snapshot.isoformat() if total_stats.oldest_snapshot else None,
                'newest_snapshot': total_stats.newest_snapshot.isoformat() if total_stats.newest_snapshot else None,
                'by_source': {
                    row.source: {
                        'count': row.count,
                        'size_bytes': row.size_bytes or 0,
                        'size_mb': (row.size_bytes or 0) / (1024 * 1024)
                    }
                    for row in source_stats
                }
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_storage_statistics"
            })
            raise DatabaseError("Failed to get storage statistics", cause=e)
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            self.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False