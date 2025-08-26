"""
Unit of Work Pattern Interface

Manages transactions across multiple repositories to ensure data consistency.
Provides a single interface for complex business operations that span multiple entities.
"""

from typing import Protocol, Optional, Any, Dict
from abc import abstractmethod
from contextlib import asynccontextmanager

from src.core.domain.repositories import (
    SanctionedEntityRepository, ChangeEventRepository, 
    ScraperRunRepository, ContentSnapshotRepository
)
from src.core.exceptions import TransactionError, DatabaseError
from src.core.logging_config import get_logger

logger = get_logger(__name__)

# ======================== UNIT OF WORK INTERFACE ========================

class UnitOfWork(Protocol):
    """
    Unit of Work interface for coordinated repository operations.
    
    Ensures that all operations within a business transaction either
    all succeed or all fail together, maintaining data consistency.
    
    Usage:
        async with uow:
            entity = await uow.sanctioned_entities.create(entity_data)
            change = await uow.change_events.create(change_data)
            # Both operations commit together or rollback together
    """
    
    # ======================== REPOSITORY INTERFACES ========================
    
    sanctioned_entities: SanctionedEntityRepository
    change_events: ChangeEventRepository
    scraper_runs: ScraperRunRepository
    content_snapshots: ContentSnapshotRepository
    
    # ======================== TRANSACTION MANAGEMENT ========================
    
    async def __aenter__(self) -> 'UnitOfWork':
        """Enter async context manager and begin transaction."""
        ...
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, handling commit/rollback."""
        ...
    
    async def begin(self) -> None:
        """Explicitly begin transaction."""
        ...
    
    async def commit(self) -> None:
        """Commit all pending changes across repositories."""
        ...
    
    async def rollback(self) -> None:
        """Rollback all pending changes across repositories."""
        ...
    
    async def flush(self) -> None:
        """Flush pending changes without committing."""
        ...
    
    # ======================== HEALTH AND MONITORING ========================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all repositories."""
        ...
    
    @property
    def is_active(self) -> bool:
        """Check if unit of work has an active transaction."""
        ...

# ======================== UNIT OF WORK FACTORY ========================

class UnitOfWorkFactory(Protocol):
    """Factory for creating Unit of Work instances."""
    
    def create_unit_of_work(self) -> UnitOfWork:
        """Create new Unit of Work instance."""
        ...
    
    async def create_async_unit_of_work(self) -> UnitOfWork:
        """Create new async Unit of Work instance."""
        ...

# ======================== BUSINESS OPERATION CONTEXTS ========================

class ScrapingOperationContext:
    """
    Context manager for scraping operations that need coordinated repository access.
    
    Handles the complex workflow of:
    1. Creating/updating scraper run
    2. Storing content snapshot  
    3. Performing change detection
    4. Storing change events
    5. Updating entities
    """
    
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        self.scraper_run = None
        self.content_snapshot = None
        self.change_detection_result = None
        
    async def __aenter__(self) -> 'ScrapingOperationContext':
        """Enter scraping operation context."""
        await self.uow.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit scraping operation context."""
        if exc_type is not None:
            logger.error(f"Scraping operation failed: {exc_val}")
            await self.rollback_scraping_operation()
        
        await self.uow.__aexit__(exc_type, exc_val, exc_tb)
    
    async def rollback_scraping_operation(self) -> None:
        """Rollback scraping operation with cleanup."""
        try:
            # Mark scraper run as failed if it exists
            if self.scraper_run:
                self.scraper_run.mark_failed("Operation rolled back due to error")
                await self.uow.scraper_runs.update(self.scraper_run)
            
            await self.uow.rollback()
            
        except Exception as e:
            logger.error(f"Failed to rollback scraping operation: {e}")

class ChangeDetectionContext:
    """
    Context manager for change detection operations.
    
    Coordinates change detection workflow across multiple repositories.
    """
    
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        self.changes_detected = []
        self.entities_updated = []
        
    async def __aenter__(self) -> 'ChangeDetectionContext':
        """Enter change detection context."""
        await self.uow.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit change detection context."""
        if exc_type is not None:
            logger.error(f"Change detection failed: {exc_val}")
            await self.rollback_change_detection()
        
        await self.uow.__aexit__(exc_type, exc_val, exc_tb)
    
    async def rollback_change_detection(self) -> None:
        """Rollback change detection with proper cleanup."""
        try:
            logger.warning(f"Rolling back {len(self.changes_detected)} change events")
            await self.uow.rollback()
            
        except Exception as e:
            logger.error(f"Failed to rollback change detection: {e}")

# ======================== UNIT OF WORK UTILITIES ========================

@asynccontextmanager
async def managed_unit_of_work(uow: UnitOfWork):
    """
    Utility context manager for automatic Unit of Work lifecycle.
    
    Usage:
        async with managed_unit_of_work(uow) as managed_uow:
            await managed_uow.sanctioned_entities.create(entity)
            # Auto-commit on success, auto-rollback on exception
    """
    try:
        async with uow:
            yield uow
            await uow.commit()
    except Exception as e:
        logger.error(f"Unit of work operation failed: {e}")
        await uow.rollback()
        raise

@asynccontextmanager  
async def scraping_operation(uow: UnitOfWork):
    """
    Utility context manager for scraping operations.
    
    Usage:
        async with scraping_operation(uow) as ctx:
            ctx.scraper_run = await uow.scraper_runs.create(run)
            # Automatic cleanup on failure
    """
    async with ScrapingOperationContext(uow) as ctx:
        yield ctx

@asynccontextmanager
async def change_detection_operation(uow: UnitOfWork):
    """
    Utility context manager for change detection operations.
    
    Usage:
        async with change_detection_operation(uow) as ctx:
            changes = await detect_changes(...)
            ctx.changes_detected = changes
            # Automatic cleanup on failure
    """
    async with ChangeDetectionContext(uow) as ctx:
        yield ctx

# ======================== TRANSACTION DECORATORS ========================

def transactional(uow_factory: UnitOfWorkFactory):
    """
    Decorator to make a function transactional.
    
    Usage:
        @transactional(uow_factory)
        async def some_business_operation(data):
            # Function automatically gets uow parameter injected
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with uow_factory.create_async_unit_of_work() as uow:
                # Inject uow as first parameter
                return await func(uow, *args, **kwargs)
        return wrapper
    return decorator

def requires_transaction(func):
    """
    Decorator to ensure function is called within an active transaction.
    
    Usage:
        @requires_transaction
        async def some_repository_operation(uow: UnitOfWork, data):
            # This function requires an active UnitOfWork
            pass
    """
    async def wrapper(uow: UnitOfWork, *args, **kwargs):
        if not uow.is_active:
            raise TransactionError("Function requires an active transaction")
        return await func(uow, *args, **kwargs)
    return wrapper

# ======================== SPECIALIZED BUSINESS OPERATIONS ========================

class BusinessOperations:
    """
    High-level business operations that coordinate multiple repositories.
    
    These operations encapsulate complex business workflows that span
    multiple entities and require transactional consistency.
    """
    
    def __init__(self, uow_factory: UnitOfWorkFactory):
        self.uow_factory = uow_factory
        self.logger = get_logger(__name__)
    
    async def perform_full_scraping_cycle(
        self,
        source: 'DataSource',
        entities_data: list,
        scraper_run_data: dict,
        content_snapshot_data: dict
    ) -> Dict[str, Any]:
        """
        Perform complete scraping cycle with change detection.
        
        This is a complex business operation that:
        1. Creates scraper run record
        2. Stores content snapshot
        3. Performs change detection
        4. Updates entities
        5. Records change events
        6. Updates scraper run with results
        """
        async with self.uow_factory.create_async_unit_of_work() as uow:
            try:
                results = {
                    'scraper_run': None,
                    'content_snapshot': None,
                    'change_detection_result': None,
                    'success': False
                }
                
                # Step 1: Create scraper run
                from src.core.domain.entities import ScraperRunDomain
                scraper_run = ScraperRunDomain(**scraper_run_data)
                scraper_run = await uow.scraper_runs.create(scraper_run)
                results['scraper_run'] = scraper_run
                
                # Step 2: Store content snapshot
                from src.core.domain.entities import ContentSnapshotDomain
                content_snapshot = ContentSnapshotDomain(**content_snapshot_data)
                content_snapshot = await uow.content_snapshots.create(content_snapshot)
                results['content_snapshot'] = content_snapshot
                
                # Step 3: Perform change detection (if this is implemented)
                # This would be implemented by the concrete UnitOfWork
                if hasattr(uow, 'perform_change_detection'):
                    change_result = await uow.perform_change_detection(
                        source=source,
                        new_entities=entities_data,
                        scraper_run_id=scraper_run.run_id,
                        old_content_hash="",  # Would be retrieved from last snapshot
                        new_content_hash=content_snapshot.content_hash
                    )
                    results['change_detection_result'] = change_result
                
                # Step 4: Update scraper run with results
                scraper_run.mark_completed(scraper_run.status)
                scraper_run = await uow.scraper_runs.update(scraper_run)
                results['scraper_run'] = scraper_run
                
                # Step 5: Commit all changes
                await uow.commit()
                results['success'] = True
                
                self.logger.info(
                    f"Completed full scraping cycle for {source.value}",
                    extra={
                        "source": source.value,
                        "entities_processed": len(entities_data),
                        "scraper_run_id": scraper_run.run_id
                    }
                )
                
                return results
                
            except Exception as e:
                self.logger.error(
                    f"Scraping cycle failed for {source.value}: {e}",
                    extra={"source": source.value},
                    exc_info=True
                )
                await uow.rollback()
                raise
    
    async def bulk_entity_update(
        self,
        source: 'DataSource',
        entities: list,
        scraper_run_id: str
    ) -> Dict[str, int]:
        """
        Perform bulk entity update with change tracking.
        
        Returns:
            Dict with counts of added, updated, removed entities.
        """
        async with self.uow_factory.create_async_unit_of_work() as uow:
            try:
                # This would delegate to repository implementation
                result = await uow.sanctioned_entities.replace_source_data(
                    source=source,
                    entities=entities
                )
                
                await uow.commit()
                
                self.logger.info(
                    f"Bulk update completed for {source.value}",
                    extra={
                        "source": source.value,
                        "added": result.get('added', 0),
                        "updated": result.get('updated', 0),
                        "removed": result.get('removed', 0)
                    }
                )
                
                return result
                
            except Exception as e:
                self.logger.error(
                    f"Bulk update failed for {source.value}: {e}",
                    exc_info=True
                )
                await uow.rollback()
                raise

# ======================== EXPORTS ========================

__all__ = [
    # Main interfaces
    'UnitOfWork',
    'UnitOfWorkFactory',
    
    # Context managers
    'ScrapingOperationContext',
    'ChangeDetectionContext',
    
    # Utilities
    'managed_unit_of_work',
    'scraping_operation',
    'change_detection_operation',
    
    # Decorators
    'transactional',
    'requires_transaction',
    
    # Business operations
    'BusinessOperations'
]