"""
Scraper Run Repository - Async Implementation
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc, func

from src.core.domain.entities import ScraperRunDomain
from src.core.enums import DataSource, ScrapingStatus
from src.infrastructure.database.models import ScraperRun as ScraperRunORM
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class SQLAlchemyScraperRunRepository:
    """Async repository for scraper runs."""
    
    def __init__(self, session: AsyncSession):
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
            status = ScrapingStatus(orm_run.status) if orm_run.status else ScrapingStatus.RUNNING
        except:
            status = ScrapingStatus.RUNNING
        
        return ScraperRunDomain(
            run_id=orm_run.run_id,
            source=source,
            started_at=orm_run.started_at,
            completed_at=orm_run.completed_at,
            status=status,
            source_url=orm_run.source_url,
            content_hash=orm_run.content_hash,
            content_size_bytes=orm_run.content_size_bytes,
            content_changed=orm_run.content_changed,
            entities_processed=orm_run.entities_processed,
            entities_added=orm_run.entities_added,
            entities_modified=orm_run.entities_modified,
            entities_removed=orm_run.entities_removed,
            critical_changes=orm_run.critical_changes,
            high_risk_changes=orm_run.high_risk_changes,
            medium_risk_changes=orm_run.medium_risk_changes,
            low_risk_changes=orm_run.low_risk_changes,
            download_time_ms=orm_run.download_time_ms,
            parsing_time_ms=orm_run.parsing_time_ms,
            diff_time_ms=orm_run.diff_time_ms,
            storage_time_ms=orm_run.storage_time_ms,
            error_message=orm_run.error_message,
            retry_count=orm_run.retry_count
        )
    
    async def create(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        """Create new scraper run."""
        orm_run = ScraperRunORM(
            run_id=scraper_run.run_id,
            source=scraper_run.source.value,
            started_at=scraper_run.started_at,
            status=scraper_run.status.value,
            source_url=scraper_run.source_url
        )
        
        self.session.add(orm_run)
        await self.session.flush()
        return scraper_run
    
    async def update(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        """Update scraper run."""
        stmt = update(ScraperRunORM).where(
            ScraperRunORM.run_id == scraper_run.run_id
        ).values(
            completed_at=scraper_run.completed_at,
            status=scraper_run.status.value,
            entities_processed=scraper_run.entities_processed,
            entities_added=scraper_run.entities_added,
            entities_modified=scraper_run.entities_modified,
            entities_removed=scraper_run.entities_removed,
            critical_changes=scraper_run.critical_changes,
            high_risk_changes=scraper_run.high_risk_changes,
            medium_risk_changes=scraper_run.medium_risk_changes,
            low_risk_changes=scraper_run.low_risk_changes,
            error_message=scraper_run.error_message
        )
        
        await self.session.execute(stmt)
        await self.session.flush()
        return scraper_run
    
    async def get_by_run_id(self, run_id: str) -> Optional[ScraperRunDomain]:
        """Get by ID."""
        try:
            stmt = select(ScraperRunORM).where(ScraperRunORM.run_id == run_id)
            result = await self.session.execute(stmt)
            orm_run = result.scalar_one_or_none()
            return self._orm_to_domain(orm_run) if orm_run else None
        except Exception as e:
            self.logger.error(f"Error in get_by_run_id: {e}")
            return None
    
    async def find_recent(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None
    ) -> List[ScraperRunDomain]:
        """Find recent runs."""
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            stmt = select(ScraperRunORM).where(ScraperRunORM.started_at >= since)
            
            if source:
                stmt = stmt.where(ScraperRunORM.source == source.value)
            
            stmt = stmt.order_by(desc(ScraperRunORM.started_at))
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            orm_runs = result.scalars().all()
            return [self._orm_to_domain(orm_run) for orm_run in orm_runs]
        except Exception as e:
            self.logger.error(f"Error in find_recent: {e}")
            return []
    
    async def count_by_status(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[ScrapingStatus, int]:
        """Count runs by status."""
        try:
            stmt = select(
                ScraperRunORM.status,
                func.count(ScraperRunORM.run_id).label('count')
            )
            
            if since:
                stmt = stmt.where(ScraperRunORM.started_at >= since)
            
            if source:
                stmt = stmt.where(ScraperRunORM.source == source.value)
            
            stmt = stmt.group_by(ScraperRunORM.status)
            result = await self.session.execute(stmt)
            
            counts = {}
            for row in result:
                try:
                    status = ScrapingStatus(row.status)
                    counts[status] = row.count
                except:
                    pass
            
            return counts
        except Exception as e:
            self.logger.error(f"Error in count_by_status: {e}")
            return {}
    
    async def health_check(self) -> bool:
        """Check repository health."""
        try:
            stmt = select(func.count(ScraperRunORM.run_id)).limit(1)
            await self.session.execute(stmt)
            return True
        except:
            return False