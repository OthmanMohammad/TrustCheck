"""
SQLAlchemy Scraper Run Repository Implementation - FIXED with Proper Async Support
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func, text, select
from sqlalchemy.exc import SQLAlchemyError
import asyncio
from functools import wraps

from src.core.domain.entities import ScraperRunDomain
from src.core.domain.repositories import ScraperRunRepository
from src.core.enums import DataSource, ScrapingStatus
from src.core.exceptions import DatabaseError, handle_exception
from src.infrastructure.database.models import ScraperRun as ScraperRunORM
from src.core.logging_config import get_logger

logger = get_logger(__name__)

def async_compatible(func):
    """Decorator to make sync methods callable from async context."""
    @wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        if self.is_async:
            return await self._execute_async(func.__name__, *args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, self, *args, **kwargs)
    
    func.async_version = async_wrapper
    return func

class SQLAlchemyScraperRunRepository:
    """
    SQLAlchemy implementation of ScraperRunRepository.
    Supports both sync and async operations.
    """
    
    def __init__(self, session: Union[Session, AsyncSession]):
        self.session = session
        self.is_async = isinstance(session, AsyncSession)
        self.logger = get_logger(__name__)
    
    def _orm_to_domain(self, orm_run: ScraperRunORM) -> ScraperRunDomain:
        """Convert ORM model to domain entity."""
        if not orm_run:
            return None
            
        try:
            source = DataSource(orm_run.source) if orm_run.source else DataSource.OFAC
        except (ValueError, KeyError):
            source = DataSource.OFAC
            
        try:
            status = ScrapingStatus(orm_run.status) if orm_run.status else ScrapingStatus.FAILED
        except (ValueError, KeyError):
            status = ScrapingStatus.FAILED
        
        return ScraperRunDomain(
            run_id=orm_run.run_id or '',
            source=source,
            started_at=orm_run.started_at or datetime.utcnow(),
            completed_at=orm_run.completed_at,
            status=status,
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
            source=domain_run.source.value if hasattr(domain_run.source, 'value') else str(domain_run.source),
            started_at=domain_run.started_at,
            completed_at=domain_run.completed_at,
            duration_seconds=int(domain_run.duration_seconds) if domain_run.duration_seconds else None,
            status=domain_run.status.value if hasattr(domain_run.status, 'value') else str(domain_run.status),
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
    
    async def _execute_async(self, method_name: str, *args, **kwargs):
        """Execute the async version of a method."""
        method = getattr(self, f'_async_{method_name}')
        return await method(*args, **kwargs)
    
    # ======================== SYNC METHODS (for v1 API) ========================
    
    @async_compatible
    def create(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        """Create new scraper run (sync)."""
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
    
    @async_compatible
    def get_by_run_id(self, run_id: str) -> Optional[ScraperRunDomain]:
        """Get scraper run by run ID (sync)."""
        try:
            orm_run = self.session.query(ScraperRunORM).filter(
                ScraperRunORM.run_id == run_id
            ).first()
            
            return self._orm_to_domain(orm_run) if orm_run else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_scraper_run_by_id",
                "run_id": run_id
            })
            raise DatabaseError("Failed to get scraper run", cause=e)
    
    @async_compatible
    def find_recent(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None
    ) -> List[ScraperRunDomain]:
        """Find recent runs within time window (sync)."""
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            query = self.session.query(ScraperRunORM).filter(
                ScraperRunORM.started_at >= since
            )
            
            if source:
                source_value = source.value if hasattr(source, 'value') else str(source)
                query = query.filter(ScraperRunORM.source == source_value)
            
            query = query.order_by(desc(ScraperRunORM.started_at))
            
            if limit:
                query = query.limit(limit)
            
            orm_runs = query.all()
            return [self._orm_to_domain(orm_run) for orm_run in orm_runs]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_recent_runs",
                "hours": hours
            })
            raise DatabaseError("Failed to find recent scraper runs", cause=e)
    
    @async_compatible
    def get_run_statistics(
        self,
        source: Optional[DataSource] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get scraper run statistics (sync)."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            query = self.session.query(ScraperRunORM).filter(
                ScraperRunORM.started_at >= since
            )
            
            if source:
                source_value = source.value if hasattr(source, 'value') else str(source)
                query = query.filter(ScraperRunORM.source == source_value)
            
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
                if run.status:
                    try:
                        status = ScrapingStatus(run.status)
                        status_counts[status] = status_counts.get(status, 0) + 1
                    except (ValueError, KeyError):
                        pass
            
            return {
                'total_runs': total_runs,
                'success_rate': round(success_rate, 2),
                'average_duration_seconds': round(avg_duration, 2),
                'by_status': {status.value: count for status, count in status_counts.items()}
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_run_statistics"
            })
            raise DatabaseError("Failed to get run statistics", cause=e)
    
    # ======================== ASYNC METHODS (for v2 API) ========================
    
    async def _async_create(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        """Create new scraper run (async)."""
        try:
            orm_run = self._domain_to_orm(scraper_run)
            self.session.add(orm_run)
            await self.session.flush()
            
            return self._orm_to_domain(orm_run)
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_create_scraper_run",
                "run_id": scraper_run.run_id
            })
            raise DatabaseError("Failed to create scraper run", cause=e)
    
    async def _async_get_by_run_id(self, run_id: str) -> Optional[ScraperRunDomain]:
        """Get scraper run by run ID (async)."""
        try:
            query = select(ScraperRunORM).where(
                ScraperRunORM.run_id == run_id
            )
            result = await self.session.execute(query)
            orm_run = result.scalar_one_or_none()
            
            return self._orm_to_domain(orm_run) if orm_run else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_get_scraper_run_by_id",
                "run_id": run_id
            })
            raise DatabaseError("Failed to get scraper run", cause=e)
    
    async def _async_find_recent(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None
    ) -> List[ScraperRunDomain]:
        """Find recent runs within time window (async)."""
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            query = select(ScraperRunORM).where(
                ScraperRunORM.started_at >= since
            )
            
            if source:
                source_value = source.value if hasattr(source, 'value') else str(source)
                query = query.where(ScraperRunORM.source == source_value)
            
            query = query.order_by(desc(ScraperRunORM.started_at))
            
            if limit:
                query = query.limit(limit)
            
            result = await self.session.execute(query)
            orm_runs = result.scalars().all()
            
            return [self._orm_to_domain(orm_run) for orm_run in orm_runs]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_find_recent_runs",
                "hours": hours
            })
            raise DatabaseError("Failed to find recent scraper runs", cause=e)
    
    async def _async_get_run_statistics(
        self,
        source: Optional[DataSource] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get scraper run statistics (async)."""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            query = select(ScraperRunORM).where(
                ScraperRunORM.started_at >= since
            )
            
            if source:
                source_value = source.value if hasattr(source, 'value') else str(source)
                query = query.where(ScraperRunORM.source == source_value)
            
            result = await self.session.execute(query)
            runs = result.scalars().all()
            
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
                if run.status:
                    try:
                        status = ScrapingStatus(run.status)
                        status_counts[status] = status_counts.get(status, 0) + 1
                    except (ValueError, KeyError):
                        pass
            
            return {
                'total_runs': total_runs,
                'success_rate': round(success_rate, 2),
                'average_duration_seconds': round(avg_duration, 2),
                'by_status': {status.value: count for status, count in status_counts.items()}
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_get_run_statistics"
            })
            raise DatabaseError("Failed to get run statistics", cause=e)
    
    # ======================== HEALTH CHECK ========================
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            if self.is_async:
                await self.session.execute(text("SELECT 1"))
            else:
                self.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    # ======================== METHOD RESOLUTION ========================
    
    def __getattr__(self, name):
        """Route method calls to sync or async versions based on context."""
        if name in ['create', 'get_by_run_id', 'find_recent', 'get_run_statistics']:
            base_method = getattr(self, name, None)
            if base_method and hasattr(base_method, 'async_version'):
                return base_method.async_version
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")