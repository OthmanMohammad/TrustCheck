"""
Simple Content Snapshot Repository - Just Sync Methods
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, text

from src.core.domain.entities import ContentSnapshotDomain
from src.core.domain.repositories import ContentSnapshotRepository
from src.core.enums import DataSource
from src.core.exceptions import DatabaseError
from src.infrastructure.database.models import ContentSnapshot as ContentSnapshotORM
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class SQLAlchemyContentSnapshotRepository:
    """Simple sync-only repository."""
    
    def __init__(self, session: Session):
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
            entity_uid=orm_snapshot.entity_uid,
            source=source,
            content_hash=orm_snapshot.content_hash,
            content_data=orm_snapshot.content_data or {},
            captured_at=orm_snapshot.captured_at,
            scraper_run_id=orm_snapshot.scraper_run_id,
            version=orm_snapshot.version or 1,
            is_current=orm_snapshot.is_current if hasattr(orm_snapshot, 'is_current') else True
        )
    
    def get_by_id(self, snapshot_id: str) -> Optional[ContentSnapshotDomain]:
        """Get by ID."""
        try:
            orm_snapshot = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.snapshot_id == snapshot_id
            ).first()
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
        except Exception as e:
            self.logger.error(f"Error in get_by_id: {e}")
            return None
    
    def get_latest_by_entity(
        self,
        entity_uid: str,
        source: Optional[DataSource] = None
    ) -> Optional[ContentSnapshotDomain]:
        """Get latest snapshot for entity."""
        try:
            query = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.entity_uid == entity_uid
            )
            
            if source:
                query = query.filter(ContentSnapshotORM.source == source.value)
            
            orm_snapshot = query.order_by(desc(ContentSnapshotORM.captured_at)).first()
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
        except Exception as e:
            self.logger.error(f"Error in get_latest_by_entity: {e}")
            return None
    
    def get_by_content_hash(self, content_hash: str) -> Optional[ContentSnapshotDomain]:
        """Get by content hash."""
        try:
            orm_snapshot = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.content_hash == content_hash
            ).first()
            return self._orm_to_domain(orm_snapshot) if orm_snapshot else None
        except Exception as e:
            self.logger.error(f"Error in get_by_content_hash: {e}")
            return None
    
    def find_entity_history(
        self,
        entity_uid: str,
        days: int = 30,
        limit: Optional[int] = None
    ) -> List[ContentSnapshotDomain]:
        """Find entity history."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            query = self.session.query(ContentSnapshotORM).filter(
                and_(
                    ContentSnapshotORM.entity_uid == entity_uid,
                    ContentSnapshotORM.captured_at >= since
                )
            )
            
            query = query.order_by(desc(ContentSnapshotORM.captured_at))
            
            if limit:
                query = query.limit(limit)
            
            orm_snapshots = query.all()
            return [self._orm_to_domain(s) for s in orm_snapshots]
        except Exception as e:
            self.logger.error(f"Error in find_entity_history: {e}")
            return []
    
    def find_by_scraper_run(
        self,
        scraper_run_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ContentSnapshotDomain]:
        """Find by scraper run."""
        try:
            query = self.session.query(ContentSnapshotORM).filter(
                ContentSnapshotORM.scraper_run_id == scraper_run_id
            )
            
            query = query.order_by(ContentSnapshotORM.captured_at)
            query = query.offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_snapshots = query.all()
            return [self._orm_to_domain(s) for s in orm_snapshots]
        except Exception as e:
            self.logger.error(f"Error in find_by_scraper_run: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics."""
        try:
            total_snapshots = self.session.query(func.count(ContentSnapshotORM.id)).scalar() or 0
            
            unique_entities = self.session.query(
                func.count(func.distinct(ContentSnapshotORM.entity_uid))
            ).scalar() or 0
            
            return {
                'total_snapshots': total_snapshots,
                'unique_entities': unique_entities
            }
        except Exception as e:
            self.logger.error(f"Error in get_statistics: {e}")
            return {}