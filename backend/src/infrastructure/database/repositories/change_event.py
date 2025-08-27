"""
SQLAlchemy Change Event Repository Implementation
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID

from src.core.domain.entities import ChangeEventDomain, FieldChange
from src.core.domain.repositories import ChangeEventRepository
from src.core.enums import DataSource, ChangeType, RiskLevel
from src.core.exceptions import DatabaseError, handle_exception
from src.infrastructure.database.repositories.base import SQLAlchemyBaseRepository
from src.infrastructure.database.models import ChangeEvent as ChangeEventORM

class SQLAlchemyChangeEventRepository(SQLAlchemyBaseRepository):
    """SQLAlchemy implementation of ChangeEventRepository - FIXED."""
    
    def __init__(self, session: Session):
        super().__init__(session, ChangeEventORM)
    
    def _orm_to_domain(self, orm_change: ChangeEventORM) -> ChangeEventDomain:
        """Convert ORM model to domain entity - FIXED to handle None values."""
        
        # Parse field changes safely
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
        
        # FIXED: Handle None values for enums
        try:
            source = DataSource(orm_change.source) if orm_change.source else DataSource.OFAC
        except (ValueError, KeyError):
            source = DataSource.OFAC  # Default fallback
            
        try:
            change_type = ChangeType(orm_change.change_type) if orm_change.change_type else ChangeType.MODIFIED
        except (ValueError, KeyError):
            change_type = ChangeType.MODIFIED  # Default fallback
            
        try:
            risk_level = RiskLevel(orm_change.risk_level) if orm_change.risk_level else RiskLevel.MEDIUM
        except (ValueError, KeyError):
            risk_level = RiskLevel.MEDIUM  # Default fallback
        
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
            source=domain_change.source.value if hasattr(domain_change.source, 'value') else str(domain_change.source),
            change_type=domain_change.change_type.value if hasattr(domain_change.change_type, 'value') else str(domain_change.change_type),
            risk_level=domain_change.risk_level.value if hasattr(domain_change.risk_level, 'value') else str(domain_change.risk_level),
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
    
    async def get_by_id(self, event_id: UUID) -> Optional[ChangeEventDomain]:
        """Get change event by ID."""
        try:
            orm_change = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.event_id == event_id
            ).first()
            
            return self._orm_to_domain(orm_change) if orm_change else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_change_event_by_id",
                "event_id": str(event_id)
            })
            raise DatabaseError("Failed to get change event", cause=e)
    
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
                source_value = source.value if hasattr(source, 'value') else str(source)
                query = query.filter(ChangeEventORM.source == source_value)
            
            if risk_level:
                risk_value = risk_level.value if hasattr(risk_level, 'value') else str(risk_level)
                query = query.filter(ChangeEventORM.risk_level == risk_value)
            
            query = query.order_by(desc(ChangeEventORM.detected_at)).offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_events = query.all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_recent_changes",
                "days": days,
                "source": source.value if source and hasattr(source, 'value') else str(source) if source else None
            })
            raise DatabaseError("Failed to find recent change events", cause=e)
    
    async def find_by_source(
        self,
        source: DataSource,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find change events by source."""
        try:
            source_value = source.value if hasattr(source, 'value') else str(source)
            query = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.source == source_value
            )
            
            if since:
                query = query.filter(ChangeEventORM.detected_at >= since)
            
            query = query.order_by(desc(ChangeEventORM.detected_at)).offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_events = query.all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_by_source",
                "source": source_value if source else None
            })
            raise DatabaseError("Failed to find changes by source", cause=e)
    
    async def find_by_entity(
        self,
        entity_uid: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find all changes for specific entity."""
        try:
            query = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.entity_uid == entity_uid
            ).order_by(desc(ChangeEventORM.detected_at)).offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_events = query.all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_by_entity",
                "entity_uid": entity_uid
            })
            raise DatabaseError("Failed to find changes by entity", cause=e)
    
    async def find_by_change_type(
        self,
        change_type: ChangeType,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find changes by type."""
        try:
            change_value = change_type.value if hasattr(change_type, 'value') else str(change_type)
            query = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.change_type == change_value
            )
            
            if since:
                query = query.filter(ChangeEventORM.detected_at >= since)
            
            query = query.order_by(desc(ChangeEventORM.detected_at)).offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_events = query.all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_by_change_type",
                "change_type": change_value
            })
            raise DatabaseError("Failed to find changes by type", cause=e)
    
    async def find_by_risk_level(
        self,
        risk_level: RiskLevel,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find changes by risk level."""
        try:
            risk_value = risk_level.value if hasattr(risk_level, 'value') else str(risk_level)
            query = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.risk_level == risk_value
            )
            
            if since:
                query = query.filter(ChangeEventORM.detected_at >= since)
            
            query = query.order_by(desc(ChangeEventORM.detected_at)).offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            orm_events = query.all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_by_risk_level",
                "risk_level": risk_value
            })
            raise DatabaseError("Failed to find changes by risk level", cause=e)
    
    async def find_critical_changes(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ChangeEventDomain]:
        """Find critical changes requiring immediate attention."""
        try:
            query = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.risk_level == 'CRITICAL'
            )
            
            if since:
                query = query.filter(ChangeEventORM.detected_at >= since)
            
            query = query.order_by(desc(ChangeEventORM.detected_at))
            
            if limit:
                query = query.limit(limit)
            
            orm_events = query.all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_critical_changes"
            })
            raise DatabaseError("Failed to find critical changes", cause=e)
    
    async def find_pending_notifications(
        self,
        limit: Optional[int] = None
    ) -> List[ChangeEventDomain]:
        """Find changes that need notification dispatch."""
        try:
            query = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.notification_sent_at.is_(None)
            ).order_by(desc(ChangeEventORM.detected_at))
            
            if limit:
                query = query.limit(limit)
            
            orm_events = query.all()
            return [self._orm_to_domain(orm_event) for orm_event in orm_events]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_pending_notifications"
            })
            raise DatabaseError("Failed to find pending notifications", cause=e)
    
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
                source_value = source.value if hasattr(source, 'value') else str(source)
                query = query.filter(ChangeEventORM.source == source_value)
            
            query = query.group_by(ChangeEventORM.risk_level)
            
            result = query.all()
            
            # FIXED: Handle None or invalid risk levels
            counts = {}
            for row in result:
                if row.risk_level:
                    try:
                        risk_level = RiskLevel(row.risk_level)
                        counts[risk_level] = row.count
                    except (ValueError, KeyError):
                        # Skip invalid risk levels
                        pass
            
            return counts
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "count_by_risk_level",
                "source": source.value if source and hasattr(source, 'value') else str(source) if source else None
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
                source_value = source.value if hasattr(source, 'value') else str(source)
                query = query.filter(ChangeEventORM.source == source_value)
            
            query = query.group_by(ChangeEventORM.change_type)
            
            result = query.all()
            
            # FIXED: Handle None or invalid change types
            counts = {}
            for row in result:
                if row.change_type:
                    try:
                        change_type = ChangeType(row.change_type)
                        counts[change_type] = row.count
                    except (ValueError, KeyError):
                        # Skip invalid change types
                        pass
            
            return counts
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "count_by_change_type", 
                "source": source.value if source and hasattr(source, 'value') else str(source) if source else None
            })
            raise DatabaseError("Failed to count changes by change type", cause=e)
    
    async def get_change_summary(
        self,
        days: int = 7,
        source: Optional[DataSource] = None
    ) -> Dict[str, Any]:
        """Get comprehensive change summary."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            risk_counts = await self.count_by_risk_level(since=since, source=source)
            type_counts = await self.count_by_change_type(since=since, source=source)
            
            total_changes = sum(risk_counts.values())
            
            return {
                'period_days': days,
                'since': since.isoformat(),
                'source': source.value if source and hasattr(source, 'value') else str(source) if source else 'all',
                'total_changes': total_changes,
                'by_risk_level': {
                    risk.value if hasattr(risk, 'value') else str(risk): count 
                    for risk, count in risk_counts.items()
                },
                'by_change_type': {
                    change_type.value if hasattr(change_type, 'value') else str(change_type): count 
                    for change_type, count in type_counts.items()
                }
            }
            
        except Exception as e:
            handle_exception(e, self.logger, context={
                "operation": "get_change_summary",
                "days": days
            })
            raise DatabaseError("Failed to get change summary", cause=e)
    
    async def mark_notification_sent(
        self,
        event_id: UUID,
        channels: List[str],
        sent_at: Optional[datetime] = None
    ) -> bool:
        """Mark change event notification as sent."""
        try:
            orm_event = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.event_id == event_id
            ).first()
            
            if orm_event:
                orm_event.notification_sent_at = sent_at or datetime.utcnow()
                orm_event.notification_channels = channels
                self.session.flush()
                return True
            
            return False
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "mark_notification_sent",
                "event_id": str(event_id)
            })
            raise DatabaseError("Failed to mark notification as sent", cause=e)
    
    async def mark_many_notifications_sent(
        self,
        event_ids: List[UUID],
        channels: List[str],
        sent_at: Optional[datetime] = None
    ) -> int:
        """Mark multiple notifications as sent. Returns count updated."""
        try:
            notification_time = sent_at or datetime.utcnow()
            
            updated_count = self.session.query(ChangeEventORM).filter(
                ChangeEventORM.event_id.in_(event_ids)
            ).update({
                'notification_sent_at': notification_time,
                'notification_channels': channels
            }, synchronize_session=False)
            
            self.session.flush()
            return updated_count
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "mark_many_notifications_sent",
                "event_count": len(event_ids)
            })
            raise DatabaseError("Failed to mark notifications as sent", cause=e)
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            self.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False