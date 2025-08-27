"""
SQLAlchemy Scraper Run Repository Implementation
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from sqlalchemy.exc import SQLAlchemyError

from src.core.domain.entities import ScraperRunDomain
from src.core.domain.repositories import ScraperRunRepository
from src.core.enums import DataSource, ScrapingStatus
from src.core.exceptions import DatabaseError, handle_exception
from src.infrastructure.database.repositories.base import SQLAlchemyBaseRepository
from src.infrastructure.database.models import ScraperRun as ScraperRunORM

class SQLAlchemyScraperRunRepository(SQLAlchemyBaseRepository):
    """SQLAlchemy implementation of ScraperRunRepository."""
    
    def __init__(self, session: Session):
        super().__init__(session, ScraperRunORM)
    
    def _orm_to_domain(self, orm_run: ScraperRunORM) -> ScraperRunDomain:
        """Convert ORM model to domain entity."""
        return ScraperRunDomain(
            run_id=orm_run.run_id,
            source=DataSource(orm_run.source),
            started_at=orm_run.started_at,
            completed_at=orm_run.completed_at,
            status=ScrapingStatus(orm_run.status),
            source_url=orm_run.source_url,
            content_hash=orm_run.content_hash,
            content_size_bytes=orm_run.content_size_bytes,
            content_changed=orm_run.content_changed or False,
            entities_processed=orm_run.entities_processed or 0,
            entities_added=orm_run.entities_added or 0,
            entities_modified=orm_run.entities_modified or 0,
            entities_removed=orm_run.entities_removed or 0,
            critical_changes=orm_run.critical_changes or 0,
            high_risk_changes=orm_run.high_risk_changes or 0,
            medium_risk_changes=orm_run.medium_risk_changes or 0,
            low_risk_changes=orm_run.low_risk_changes or 0,
            download_time_ms=orm_run.download_time_ms,
            parsing_time_ms=orm_run.parsing_time_ms,
            diff_time_ms=orm_run.diff_time_ms,
            storage_time_ms=orm_run.storage_time_ms,
            error_message=orm_run.error_message,
            retry_count=orm_run.retry_count or 0
        )
    
    def _domain_to_orm(self, domain_run: ScraperRunDomain) -> ScraperRunORM:
        """Convert domain entity to ORM model."""
        return ScraperRunORM(
            run_id=domain_run.run_id,
            source=domain_run.source.value,
            started_at=domain_run.started_at,
            completed_at=domain_run.completed_at,
            duration_seconds=int(domain_run.duration_seconds) if domain_run.duration_seconds else None,
            status=domain_run.status.value,
            source_url=domain_run.source_url,
            content_hash=domain_run.content_hash,
            content_size_bytes=domain_run.content_size_bytes,
            content_changed=domain_run.content_changed,
            entities_processed=domain_run.entities_processed,
            entities_added=domain_run.entities_added,
            entities_modified=domain_run.entities_modified,
            entities_removed=domain_run.entities_removed,
            critical_changes=domain_run.critical_changes,
            high_risk_changes=domain_run.high_risk_changes,
            medium_risk_changes=domain_run.medium_risk_changes,
            low_risk_changes=domain_run.low_risk_changes,
            download_time_ms=domain_run.download_time_ms,
            parsing_time_ms=domain_run.parsing_time_ms,
            diff_time_ms=domain_run.diff_time_ms,
            storage_time_ms=domain_run.storage_time_ms,
            error_message=domain_run.error_message,
            retry_count=domain_run.retry_count
        )
    
    async def create(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        """Create new scraper run."""
        try:
            orm_run = self._domain_to_orm(scraper_run)
            self.session.add(orm_run)
            self.session.flush()
            
            return self._orm_to_domain(orm_run)
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "create_scraper_run",
                "run_id": scraper_run.run_id
            })
            raise DatabaseError("Failed to create scraper run", cause=e)
    
    async def update(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        """Update existing scraper run."""
        try:
            orm_run = self.session.query(ScraperRunORM).filter(
                ScraperRunORM.run_id == scraper_run.run_id
            ).first()
            
            if not orm_run:
                raise DatabaseError(f"Scraper run not found: {scraper_run.run_id}")
            
            # Update fields
            updated_orm = self._domain_to_orm(scraper_run)
            for key, value in updated_orm.__dict__.items():
                if not key.startswith('_'):
                    setattr(orm_run, key, value)
            
            self.session.flush()
            return self._orm_to_domain(orm_run)
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "update_scraper_run",
                "run_id": scraper_run.run_id
            })
            raise DatabaseError("Failed to update scraper run", cause=e)
    
    async def find_recent(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None
    ) -> List[ScraperRunDomain]:
        """Find recent runs within time window."""
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            query = self.session.query(ScraperRunORM).filter(
                ScraperRunORM.started_at >= since
            )
            
            if source:
                query = query.filter(ScraperRunORM.source == source.value)
            
            query = query.order_by(desc(ScraperRunORM.started_at))
            
            if limit:
                query = query.limit(limit)
            
            orm_runs = query.all()
            return [self._orm_to_domain(orm_run) for orm_run in orm_runs]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_recent_runs",
                "hours": hours,
                "source": source.value if source else None
            })
            raise DatabaseError("Failed to find recent scraper runs", cause=e)
    
    async def count_by_status(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[ScrapingStatus, int]:
        """Count runs by status."""
        try:
            query = self.session.query(
                ScraperRunORM.status,
                func.count(ScraperRunORM.run_id).label('count')
            )
            
            if since:
                query = query.filter(ScraperRunORM.started_at >= since)
            
            if source:
                query = query.filter(ScraperRunORM.source == source.value)
            
            query = query.group_by(ScraperRunORM.status)
            
            result = query.all()
            
            return {
                ScrapingStatus(row.status): row.count 
                for row in result
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "count_by_status",
                "source": source.value if source else None
            })
            raise DatabaseError("Failed to count runs by status", cause=e)
    
    async def get_run_statistics(
        self,
        source: Optional[DataSource] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get scraper run statistics."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            query = self.session.query(ScraperRunORM).filter(
                ScraperRunORM.started_at >= since
            )
            
            if source:
                query = query.filter(ScraperRunORM.source == source.value)
            
            runs = query.all()
            
            if not runs:
                return {
                    'total_runs': 0,
                    'success_rate': 0.0,
                    'average_duration_seconds': 0.0,
                    'by_status': {}
                }
            
            total_runs = len(runs)
            successful_runs = len([r for r in runs if r.status == 'SUCCESS'])
            success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0
            
            durations = [r.duration_seconds for r in runs if r.duration_seconds]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            status_counts = {}
            for run in runs:
                status = ScrapingStatus(run.status)
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'total_runs': total_runs,
                'success_rate': round(success_rate, 2),
                'average_duration_seconds': round(avg_duration, 2),
                'by_status': {status.value: count for status, count in status_counts.items()}
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_run_statistics",
                "source": source.value if source else None,
                "days": days
            })
            raise DatabaseError("Failed to get run statistics", cause=e)