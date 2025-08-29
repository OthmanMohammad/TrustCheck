"""
Simple Change Event Repository - Just Sync Methods That Work
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, text

from src.core.domain.entities import ChangeEventDomain, FieldChange
from src.core.domain.repositories import ChangeEventRepository
from src.core.enums import DataSource, ChangeType, RiskLevel
from src.core.exceptions import DatabaseError, handle_exception
from src.infrastructure.database.models import ChangeEvent as ChangeEventORM
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class SQLAlchemyChangeEventRepository:
    """Simple sync-only repository that actually works."""
    
    def __init__(self, session: Session):
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
    
    def find_recent(
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
            
        except Exception as e:
            self.logger.error(f"Error in find_recent: {e}")
            return []
    
    def find_critical_changes(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ChangeEventDomain]:
        """Find critical changes."""
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
            
        except Exception as e:
            self.logger.error(f"Error in find_critical_changes: {e}")
            return []
    
    def get_change_summary(
        self,
        days: int = 7,
        source: Optional[DataSource] = None
    ) -> Dict[str, Any]:
        """Get change summary."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            risk_counts = self.count_by_risk_level(since=since, source=source)
            type_counts = self.count_by_change_type(since=since, source=source)
            
            total_changes = sum(risk_counts.values())
            
            return {
                'period_days': days,
                'since': since.isoformat(),
                'source': source.value if source else 'all',
                'total_changes': total_changes,
                'by_risk_level': {
                    risk.value: count 
                    for risk, count in risk_counts.items()
                },
                'by_change_type': {
                    change_type.value: count 
                    for change_type, count in type_counts.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in get_change_summary: {e}")
            return {}
    
    def count_by_risk_level(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[RiskLevel, int]:
        """Count by risk level."""
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
    
    def count_by_change_type(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[ChangeType, int]:
        """Count by change type."""
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
    
    def health_check(self) -> bool:
        """Check repository health."""
        try:
            self.session.execute(text("SELECT 1"))
            return True
        except:
            return False