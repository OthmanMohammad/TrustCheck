"""
Simple Scraper Run Repository - Just Sync Methods
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, text

from src.core.domain.entities import ScraperRunDomain
from src.core.domain.repositories import ScraperRunRepository
from src.core.enums import DataSource, ScrapingStatus
from src.core.exceptions import DatabaseError
from src.infrastructure.database.models import ScraperRun as ScraperRunORM
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class SQLAlchemyScraperRunRepository:
    """Simple sync-only repository."""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = get_logger(__name__)
    
    def _orm_to_domain(self, orm_run: ScraperRunORM) -> ScraperRunDomain:
        """Convert ORM to domain."""
        if not orm_run:
            return None
        
        try:
            source = DataSource(orm_run.source) if orm_run.source else DataSource.OFAC
        except:
            source = DataSource.OFAC
        
        try:
            status = ScrapingStatus(orm_run.status) if orm_run.status else ScrapingStatus.PENDING
        except:
            status = ScrapingStatus.PENDING
        
        return ScraperRunDomain(
            run_id=orm_run.run_id,
            source=source,
            status=status,
            started_at=orm_run.started_at,
            completed_at=orm_run.completed_at,
            entities_found=orm_run.entities_found or 0,
            entities_added=orm_run.entities_added or 0,
            entities_updated=orm_run.entities_updated or 0,
            entities_deactivated=orm_run.entities_deactivated or 0,
            changes_detected=orm_run.changes_detected or 0,
            errors=orm_run.errors or [],
            processing_time_ms=orm_run.processing_time_ms,
            memory_usage_mb=orm_run.memory_usage_mb,
            metadata=orm_run.metadata or {}
        )
    
    def get_by_run_id(self, run_id: str) -> Optional[ScraperRunDomain]:
        """Get by ID."""
        try:
            orm_run = self.session.query(ScraperRunORM).filter(
                ScraperRunORM.run_id == run_id
            ).first()
            return self._orm_to_domain(orm_run) if orm_run else None
        except Exception as e:
            self.logger.error(f"Error in get_by_run_id: {e}")
            return None
    
    def find_recent_runs(
        self,
        source: Optional[DataSource] = None,
        status: Optional[ScrapingStatus] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[ScraperRunDomain]:
        """Find recent runs."""
        try:
            query = self.session.query(ScraperRunORM)
            
            if source:
                query = query.filter(ScraperRunORM.source == source.value)
            
            if status:
                query = query.filter(ScraperRunORM.status == status.value)
            
            query = query.order_by(desc(ScraperRunORM.started_at))
            query = query.offset(offset).limit(limit)
            
            orm_runs = query.all()
            return [self._orm_to_domain(orm_run) for orm_run in orm_runs]
        except Exception as e:
            self.logger.error(f"Error in find_recent_runs: {e}")
            return []
    
    def get_last_successful_run(self, source: DataSource) -> Optional[ScraperRunDomain]:
        """Get last successful run."""
        try:
            orm_run = self.session.query(ScraperRunORM).filter(
                and_(
                    ScraperRunORM.source == source.value,
                    ScraperRunORM.status == ScrapingStatus.COMPLETED.value
                )
            ).order_by(desc(ScraperRunORM.completed_at)).first()
            
            return self._orm_to_domain(orm_run) if orm_run else None
        except Exception as e:
            self.logger.error(f"Error in get_last_successful_run: {e}")
            return None
    
    def get_run_statistics(
        self,
        days: int = 7,
        source: Optional[DataSource] = None
    ) -> Dict[str, Any]:
        """Get statistics."""
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
                    'successful_runs': 0,
                    'failed_runs': 0,
                    'average_duration_ms': 0
                }
            
            successful = [r for r in runs if r.status == ScrapingStatus.COMPLETED.value]
            failed = [r for r in runs if r.status == ScrapingStatus.FAILED.value]
            
            total_duration = sum(r.processing_time_ms or 0 for r in successful)
            avg_duration = total_duration / len(successful) if successful else 0
            
            return {
                'total_runs': len(runs),
                'successful_runs': len(successful),
                'failed_runs': len(failed),
                'average_duration_ms': avg_duration
            }
        except Exception as e:
            self.logger.error(f"Error in get_run_statistics: {e}")
            return {}