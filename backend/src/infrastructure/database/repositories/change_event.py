"""
SQLAlchemy Change Event Repository Implementation
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from sqlalchemy.exc import SQLAlchemyError

from src.core.domain.entities import ChangeEventDomain
from src.core.domain.repositories import ChangeEventRepository
from src.core.enums import DataSource, ChangeType, RiskLevel
from src.core.exceptions import DatabaseError, handle_exception
from src.infrastructure.database.repositories.base import SQLAlchemyBaseRepository
from src.infrastructure.database.models import ChangeEvent as ChangeEventORM

class SQLAlchemyChangeEventRepository(SQLAlchemyBaseRepository):
    """SQLAlchemy implementation of ChangeEventRepository."""
    
    def __init__(self, session: Session):
        super().__init__(session, ChangeEventORM)
    
    def _orm_to_domain(self, orm_change: ChangeEventORM) -> ChangeEventDomain:
        """Convert ORM model to domain entity."""
        from src.core.domain.entities import FieldChange
        
        field_changes = []
        if orm_change.field_changes:
            field_changes = [
                FieldChange(
                    field_name=fc.get('field_name', ''),
                    old_value=fc.get('old_value'),
                    new_value=fc.get('new_value'), 
                    change_type=fc.get('change_type', '')
                )
                for fc in orm_change.field_changes
            ]
        
        return ChangeEventDomain(
            event_id=orm_change.event_id,
            entity_uid=orm_change.entity_uid,
            entity_name=orm_change.entity_name,
            source=DataSource(orm_change.source),
            change_type=ChangeType(orm_change.change_type),
            risk_level=RiskLevel(orm_change.risk_level),
            field_changes=field_changes,
            change_summary=orm_change.change_summary,
            old_content_hash=orm_change.old_content_hash,
            new_content_hash=orm_change.new_content_hash,
            detected_at=orm_change.detected_at,
            scraper_run_id=orm_change.scraper_run_id,
            processing_time_ms=orm_change.processing_time_ms,
            notification_sent_at=orm_change.notification_sent_at,
            notification_channels=orm_change.notification_channels or []
        )
    
    def _domain_to_orm(self, domain_change: ChangeEventDomain) -> ChangeEventORM:
        """Convert domain entity to ORM model."""
        field_changes_dict = []
        if domain_change.field_changes:
            field_changes_dict = [
                {
                    'field_name': fc.field_name,
                    'old_value': fc.old_value,
                    'new_value': fc.new_value,
                    'change_type': fc.change_type
                }
                for fc in domain_change.field_changes
            ]
        
        return ChangeEventORM(
            event_id=domain_change.event_id,
            entity_uid=domain_change.entity_uid,
            entity_name=domain_change.entity_name,
            source=domain_change.source.value,
            change_type=domain_change.change_type.value,
            risk_level=domain_change.risk_level.value,
            field_changes=field_changes_dict,
            change_summary=domain_change.change_summary,
            old_content_hash=domain_change.old_content_hash,
            new_content_hash=domain_change.new_content_hash,
            detected_at=domain_change.detected_at,
            scraper_run_id=domain_change.scraper_run_id,
            processing_time_ms=domain_change.processing_time_ms,
            notification_sent_at=domain_change.notification_sent_at,
            notification_channels=domain_change.notification_channels
        )
    
    async def create(self, change_event: ChangeEventDomain) -> ChangeEventDomain:
        """Create new change event."""
        try:
            orm_change = self._domain_to_orm(change_event)
            self.session.add(orm_change)
            self.session.flush()
            
            return self._orm_to_domain(orm_change)
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "create_change_event",
                "entity_uid": change_event.entity_uid
            })
            raise DatabaseError("Failed to create change event", cause=e)
    
    async def create_many(self, events: List[ChangeEventDomain]) -> List[ChangeEventDomain]:
        """Create multiple change events efficiently."""
        try:
            orm_events = [self._domain_to_orm(event) for event in events]
            self.session.add_all(orm_events)
            self.session.flush()
            
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "create_many_change_events",
                "event_count": len(events)
            })
            raise DatabaseError("Failed to create multiple change events", cause=e)
    
    async def find_recent(
        self,
        days: int = 7,
        source: Optional[DataSource] = None,
        risk_level: Optional[RiskLevel] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find recent change events with filters."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            query = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.detected_at >= since
            )
            
            if source:
                query = query.filter(ChangeEventORM.source == source.value)
            
            if risk_level:
                query = query.filter(ChangeEventORM.risk_level == risk_level.value)
            
            query = query.order_by(desc(ChangeEventORM.detected_at)).offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_events = query.all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_recent_changes",
                "days": days,
                "source": source.value if source else None
            })
            raise DatabaseError("Failed to find recent change events", cause=e)
    
    async def count_by_risk_level(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[RiskLevel, int]:
        """Count changes by risk level."""
        try:
            query = self.session.query(
                ChangeEventORM.risk_level,
                func.count(ChangeEventORM.event_id).label('count')
            )
            
            if since:
                query = query.filter(ChangeEventORM.detected_at >= since)
            
            if source:
                query = query.filter(ChangeEventORM.source == source.value)
            
            query = query.group_by(ChangeEventORM.risk_level)
            
            result = query.all()
            
            return {
                RiskLevel(row.risk_level): row.count 
                for row in result
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "count_by_risk_level",
                "source": source.value if source else None
            })
            raise DatabaseError("Failed to count changes by risk level", cause=e)
    
    async def count_by_change_type(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[ChangeType, int]:
        """Count changes by type."""
        try:
            query = self.session.query(
                ChangeEventORM.change_type,
                func.count(ChangeEventORM.event_id).label('count')
            )
            
            if since:
                query = query.filter(ChangeEventORM.detected_at >= since)
            
            if source:
                query = query.filter(ChangeEventORM.source == source.value)
            
            query = query.group_by(ChangeEventORM.change_type)
            
            result = query.all()
            
            return {
                ChangeType(row.change_type): row.count 
                for row in result
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "count_by_change_type", 
                "source": source.value if source else None
            })
            raise DatabaseError("Failed to count changes by change type", cause=e)