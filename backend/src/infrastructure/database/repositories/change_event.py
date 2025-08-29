"""
Change Event Repository - Async Implementation
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc, func
from uuid import UUID

from src.core.domain.entities import ChangeEventDomain, FieldChange
from src.core.enums import DataSource, ChangeType, RiskLevel
from src.infrastructure.database.models import ChangeEvent as ChangeEventORM
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class SQLAlchemyChangeEventRepository:
    """Async repository for change events."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(__name__)
    
    def _orm_to_domain(self, orm_change: ChangeEventORM) -> ChangeEventDomain:
        """Convert ORM model to domain entity."""
        if not orm_change:
            return None
            
        field_changes = []
        if orm_change.field_changes:
            for fc in orm_change.field_changes:
                if isinstance(fc, dict):
                    field_changes.append(FieldChange(
                        field_name=fc.get('field_name', ''),
                        old_value=fc.get('old_value'),
                        new_value=fc.get('new_value'), 
                        change_type=fc.get('change_type', '')
                    ))
        
        try:
            source = DataSource(orm_change.source) if orm_change.source else DataSource.OFAC
        except:
            source = DataSource.OFAC
            
        try:
            change_type = ChangeType(orm_change.change_type) if orm_change.change_type else ChangeType.MODIFIED
        except:
            change_type = ChangeType.MODIFIED
            
        try:
            risk_level = RiskLevel(orm_change.risk_level) if orm_change.risk_level else RiskLevel.MEDIUM
        except:
            risk_level = RiskLevel.MEDIUM
        
        return ChangeEventDomain(
            event_id=orm_change.event_id,
            entity_uid=orm_change.entity_uid or '',
            entity_name=orm_change.entity_name or 'Unknown',
            source=source,
            change_type=change_type,
            risk_level=risk_level,
            field_changes=field_changes,
            change_summary=orm_change.change_summary or '',
            old_content_hash=orm_change.old_content_hash,
            new_content_hash=orm_change.new_content_hash,
            detected_at=orm_change.detected_at or datetime.utcnow(),
            scraper_run_id=orm_change.scraper_run_id or '',
            processing_time_ms=orm_change.processing_time_ms,
            notification_sent_at=orm_change.notification_sent_at,
            notification_channels=orm_change.notification_channels or []
        )
    
    async def create(self, change_event: ChangeEventDomain) -> ChangeEventDomain:
        """Create new change event."""
        orm_change = ChangeEventORM(
            event_id=change_event.event_id,
            entity_uid=change_event.entity_uid,
            entity_name=change_event.entity_name,
            source=change_event.source.value,
            change_type=change_event.change_type.value,
            risk_level=change_event.risk_level.value,
            field_changes=[{
                'field_name': fc.field_name,
                'old_value': fc.old_value,
                'new_value': fc.new_value,
                'change_type': fc.change_type
            } for fc in change_event.field_changes],
            change_summary=change_event.change_summary,
            old_content_hash=change_event.old_content_hash,
            new_content_hash=change_event.new_content_hash,
            detected_at=change_event.detected_at,
            scraper_run_id=change_event.scraper_run_id,
            processing_time_ms=change_event.processing_time_ms
        )
        
        self.session.add(orm_change)
        await self.session.flush()
        return change_event
    
    async def create_many(self, events: List[ChangeEventDomain]) -> List[ChangeEventDomain]:
        """Create multiple change events."""
        for event in events:
            await self.create(event)
        return events
    
    async def find_recent(
        self,
        days: int = 7,
        source: Optional[DataSource] = None,
        risk_level: Optional[RiskLevel] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find recent change events."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            stmt = select(ChangeEventORM).where(
                ChangeEventORM.detected_at >= since
            )
            
            if source:
                stmt = stmt.where(ChangeEventORM.source == source.value)
            
            if risk_level:
                stmt = stmt.where(ChangeEventORM.risk_level == risk_level.value)
            
            stmt = stmt.order_by(desc(ChangeEventORM.detected_at)).offset(offset)
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            orm_events = result.scalars().all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except Exception as e:
            self.logger.error(f"Error in find_recent: {e}")
            return []
    
    async def find_critical_changes(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ChangeEventDomain]:
        """Find critical changes."""
        try:
            stmt = select(ChangeEventORM).where(
                ChangeEventORM.risk_level == 'CRITICAL'
            )
            
            if since:
                stmt = stmt.where(ChangeEventORM.detected_at >= since)
            
            stmt = stmt.order_by(desc(ChangeEventORM.detected_at))
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            orm_events = result.scalars().all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except Exception as e:
            self.logger.error(f"Error in find_critical_changes: {e}")
            return []
    
    async def find_by_risk_level(
        self,
        risk_level: RiskLevel,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ChangeEventDomain]:
        """Find changes by risk level."""
        try:
            stmt = select(ChangeEventORM).where(
                ChangeEventORM.risk_level == risk_level.value
            )
            
            if since:
                stmt = stmt.where(ChangeEventORM.detected_at >= since)
            
            stmt = stmt.order_by(desc(ChangeEventORM.detected_at))
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            orm_events = result.scalars().all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except Exception as e:
            self.logger.error(f"Error in find_by_risk_level: {e}")
            return []
    
    async def count_by_risk_level(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[RiskLevel, int]:
        """Count by risk level."""
        try:
            stmt = select(
                ChangeEventORM.risk_level,
                func.count(ChangeEventORM.event_id).label('count')
            )
            
            if since:
                stmt = stmt.where(ChangeEventORM.detected_at >= since)
            
            if source:
                stmt = stmt.where(ChangeEventORM.source == source.value)
            
            stmt = stmt.group_by(ChangeEventORM.risk_level)
            result = await self.session.execute(stmt)
            
            counts = {}
            for row in result:
                if row.risk_level:
                    try:
                        risk = RiskLevel(row.risk_level)
                        counts[risk] = row.count
                    except:
                        pass
            
            return counts
            
        except Exception as e:
            self.logger.error(f"Error in count_by_risk_level: {e}")
            return {}
    
    async def count_by_change_type(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[ChangeType, int]:
        """Count by change type."""
        try:
            stmt = select(
                ChangeEventORM.change_type,
                func.count(ChangeEventORM.event_id).label('count')
            )
            
            if since:
                stmt = stmt.where(ChangeEventORM.detected_at >= since)
            
            if source:
                stmt = stmt.where(ChangeEventORM.source == source.value)
            
            stmt = stmt.group_by(ChangeEventORM.change_type)
            result = await self.session.execute(stmt)
            
            counts = {}
            for row in result:
                if row.change_type:
                    try:
                        change_type = ChangeType(row.change_type)
                        counts[change_type] = row.count
                    except:
                        pass
            
            return counts
            
        except Exception as e:
            self.logger.error(f"Error in count_by_change_type: {e}")
            return {}
    
    async def health_check(self) -> bool:
        """Check repository health."""
        try:
            stmt = select(func.count(ChangeEventORM.event_id)).limit(1)
            await self.session.execute(stmt)
            return True
        except:
            return False