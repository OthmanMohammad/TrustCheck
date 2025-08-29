"""
Content Snapshot Repository - Async Implementation
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from src.core.domain.entities import ContentSnapshotDomain
from src.core.enums import DataSource
from src.infrastructure.database.models import ContentSnapshot as ContentSnapshotORM
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class SQLAlchemyContentSnapshotRepository:
    """Async repository for content snapshots."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(__name__)
    
    def _orm_to_domain(self, orm_snapshot: ContentSnapshotORM) -> ContentSnapshotDomain:
        """Convert ORM to domain."""
        if not orm_snapshot:
            return None
        
        try:
            source = DataSource(orm_snapshot.source) if orm_snapshot.source else DataSource.OFAC
        except:
            source = DataSource.OFAC
        
        return ContentSnapshotDomain(
            snapshot_id=orm_snapshot.snapshot_id,
            source=source,
            content_hash=orm_snapshot.content_hash,
            content_size_bytes=orm_snapshot.content_size_bytes,
            snapshot_time=orm_snapshot.snapshot_time,
            scraper_run_id=orm_snapshot.scraper_run_id,
            s3_archive_path=orm_snapshot.s3_archive_path
        )
    
    async def create(self, snapshot: ContentSnapshotDomain) -> ContentSnapshotDomain:
        """Create content snapshot."""
        orm_snapshot = ContentSnapshotORM(
            snapshot_id=snapshot.snapshot_id,
            source=snapshot.source.value,
            content_hash=snapshot.content_hash,
            content_size_bytes=snapshot.content_size_bytes,
            snapshot_time=snapshot.snapshot_time,
            scraper_run_id=snapshot.scraper_run_id,
            s3_archive_path=snapshot.s3_archive_path
        )
        
        self.session.add(orm_snapshot)
        await self.session.flush()
        return snapshot
    
    async def get_last_content_hash(self, source: DataSource) -> Optional[str]:
        """Get content hash from most recent snapshot."""
        try:
            stmt = select(ContentSnapshotORM.content_hash).where(
                ContentSnapshotORM.source == source.value
            ).order_by(desc(ContentSnapshotORM.snapshot_time)).limit(1)
            
            result = await self.session.execute(stmt)
            content_hash = result.scalar_one_or_none()
            return content_hash
        except Exception as e:
            self.logger.error(f"Error in get_last_content_hash: {e}")
            return None
    
    async def health_check(self) -> bool:
        """Check repository health."""
        try:
            stmt = select(func.count(ContentSnapshotORM.snapshot_id)).limit(1)
            await self.session.execute(stmt)
            return True
        except:
            return False