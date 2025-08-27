"""
SQLAlchemy Unit of Work Implementation

Concrete implementation of Unit of Work pattern using SQLAlchemy.
Manages transactions across multiple repositories with proper rollback.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager

from src.core.uow import UnitOfWork, UnitOfWorkFactory
from src.core.domain.repositories import (
    SanctionedEntityRepository, ChangeEventRepository,
    ScraperRunRepository, ContentSnapshotRepository
)
from src.core.exceptions import TransactionError, DatabaseError, handle_exception
from src.core.logging_config import get_logger, log_exception, log_performance

# Concrete repository implementations
from src.infrastructure.database.repositories.sanctioned_entity import SQLAlchemySanctionedEntityRepository
from src.infrastructure.database.repositories.change_event import SQLAlchemyChangeEventRepository
from src.infrastructure.database.repositories.scraper_run import SQLAlchemyScraperRunRepository
from src.infrastructure.database.repositories.content_snapshot import SQLAlchemyContentSnapshotRepository

logger = get_logger(__name__)

# ======================== SQLALCHEMY UNIT OF WORK ========================

class SQLAlchemyUnitOfWork:
    """
    SQLAlchemy implementation of Unit of Work pattern.
    
    Manages database sessions and transactions across multiple repositories.
    Ensures ACID properties for complex business operations.
    """
    
    def __init__(self, session: Session):
        self.session = session
        self._transaction_started = False
        self._committed = False
        self._rolled_back = False
        self.logger = get_logger(__name__)
        
        # Initialize repositories with shared session
        self.sanctioned_entities: SanctionedEntityRepository = SQLAlchemySanctionedEntityRepository(session)
        self.change_events: ChangeEventRepository = SQLAlchemyChangeEventRepository(session)
        self.scraper_runs: ScraperRunRepository = SQLAlchemyScraperRunRepository(session)
        self.content_snapshots: ContentSnapshotRepository = SQLAlchemyContentSnapshotRepository(session)
    
    # ======================== CONTEXT MANAGER PROTOCOL ========================
    
    async def __aenter__(self) -> 'SQLAlchemyUnitOfWork':
        """Enter async context and begin transaction."""
        await self.begin()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, handling commit/rollback based on exceptions."""
        if exc_type is not None:
            # Exception occurred - rollback
            self.logger.warning(
                f"Exception in UnitOfWork context, rolling back: {exc_type.__name__}: {exc_val}",
                extra={
                    "exception_type": exc_type.__name__,
                    "exception_message": str(exc_val),
                    "transaction_active": self._transaction_started
                }
            )
            await self.rollback()
        elif not self._committed and not self._rolled_back:
            # No exception and not already committed - auto-commit
            await self.commit()
    
    # ======================== TRANSACTION MANAGEMENT ========================
    
    async def begin(self) -> None:
        """Begin transaction."""
        if self._transaction_started:
            self.logger.warning("Transaction already started")
            return
        
        try:
            if not self.session.in_transaction():
                self.session.begin()
            
            self._transaction_started = True
            self.logger.debug("Transaction started")
            
        except SQLAlchemyError as e:
            error = handle_exception(e, self.logger, context={"operation": "begin_transaction"})
            raise TransactionError("Failed to begin transaction", cause=e) from error
    
    async def commit(self) -> None:
        """Commit all pending changes."""
        if self._committed:
            self.logger.warning("Transaction already committed")
            return
        
        if self._rolled_back:
            raise TransactionError("Cannot commit after rollback")
        
        start_time = datetime.utcnow()
        
        try:
            self.session.commit()
            self._committed = True
            
            commit_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            log_performance(
                self.logger,
                "uow_commit",
                commit_time,
                success=True
            )
            
            self.logger.debug("Transaction committed successfully")
            
        except SQLAlchemyError as e:
            self._committed = False
            error = handle_exception(e, self.logger, context={"operation": "commit_transaction"})
            
            # Attempt rollback after failed commit
            try:
                await self.rollback()
            except Exception as rollback_error:
                self.logger.error(f"Failed to rollback after commit failure: {rollback_error}")
            
            raise TransactionError("Failed to commit transaction", cause=e) from error
    
    async def rollback(self) -> None:
        """Rollback all pending changes."""
        if self._rolled_back:
            self.logger.warning("Transaction already rolled back")
            return
        
        try:
            self.session.rollback()
            self._rolled_back = True
            
            self.logger.debug("Transaction rolled back")
            
        except SQLAlchemyError as e:
            error = handle_exception(e, self.logger, context={"operation": "rollback_transaction"})
            # Still mark as rolled back to prevent further operations
            self._rolled_back = True
            raise TransactionError("Failed to rollback transaction", cause=e) from error
    
    async def flush(self) -> None:
        """Flush pending changes without committing."""
        if not self._transaction_started:
            raise TransactionError("No active transaction to flush")
        
        if self._committed or self._rolled_back:
            raise TransactionError("Cannot flush completed transaction")
        
        try:
            self.session.flush()
            self.logger.debug("Session flushed")
            
        except SQLAlchemyError as e:
            error = handle_exception(e, self.logger, context={"operation": "flush_session"})
            raise TransactionError("Failed to flush session", cause=e) from error
    
    # ======================== HEALTH AND MONITORING ========================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all repositories."""
        health_results = {
            'unit_of_work': {
                'transaction_active': self._transaction_started,
                'committed': self._committed,
                'rolled_back': self._rolled_back,
                'session_active': bool(self.session)
            },
            'repositories': {}
        }
        
        # Check each repository
        repositories = {
            'sanctioned_entities': self.sanctioned_entities,
            'change_events': self.change_events,
            'scraper_runs': self.scraper_runs,
            'content_snapshots': self.content_snapshots
        }
        
        for name, repo in repositories.items():
            try:
                is_healthy = await repo.health_check()
                health_results['repositories'][name] = {
                    'healthy': is_healthy,
                    'error': None
                }
            except Exception as e:
                health_results['repositories'][name] = {
                    'healthy': False,
                    'error': str(e)
                }
        
        # Overall health
        all_repos_healthy = all(
            repo_health['healthy'] 
            for repo_health in health_results['repositories'].values()
        )
        health_results['overall_healthy'] = all_repos_healthy and bool(self.session)
        
        return health_results
    
    @property
    def is_active(self) -> bool:
        """Check if unit of work has an active transaction."""
        return self._transaction_started and not self._committed and not self._rolled_back
    
    # ======================== SPECIALIZED OPERATIONS ========================
    
    async def perform_change_detection(
        self,
        source: 'DataSource',
        new_entities: list,
        scraper_run_id: str,
        old_content_hash: str,
        new_content_hash: str
    ) -> 'ChangeDetectionResult':
        """
        Perform comprehensive change detection across repositories.
        
        This orchestrates a complex workflow:
        1. Get current entities from repository
        2. Compare with new entities
        3. Create change events
        4. Update entities
        5. Return results
        """
        from datetime import datetime
        from src.core.domain.entities import ChangeDetectionResult
        
        if not self.is_active:
            raise TransactionError("Change detection requires active transaction")
        
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(
                f"Starting change detection for {source.value}",
                extra={
                    "source": source.value,
                    "scraper_run_id": scraper_run_id,
                    "new_entities_count": len(new_entities)
                }
            )
            
            # Step 1: Get current entities
            current_entities = await self.sanctioned_entities.get_all_for_change_detection(source)
            
            # Step 2: Detect changes (this would use your change detection service)
            from src.services.change_detection.change_detector import ChangeDetector
            detector = ChangeDetector(source.value)
            
            # Convert domain entities to dict format for detector
            current_entities_dict = [
                {
                    'uid': entity.uid,
                    'name': entity.name,
                    'entity_type': entity.entity_type.value,
                    'programs': entity.programs,
                    'aliases': entity.aliases,
                    # ... other fields
                }
                for entity in current_entities
            ]
            
            changes, metrics = detector.detect_changes(
                old_entities=current_entities_dict,
                new_entities=new_entities,
                old_content_hash=old_content_hash,
                new_content_hash=new_content_hash,
                scraper_run_id=scraper_run_id
            )
            
            # Step 3: Store change events
            if changes:
                await self.change_events.create_many(changes)
            
            # Step 4: Update entities (replace source data)
            from src.core.domain.entities import create_sanctioned_entity
            domain_entities = []
            for entity_dict in new_entities:
                domain_entity = create_sanctioned_entity(
                    uid=entity_dict['uid'],
                    name=entity_dict['name'],
                    entity_type=entity_dict['entity_type'],
                    source=source,
                    **entity_dict
                )
                domain_entities.append(domain_entity)
            
            replace_result = await self.sanctioned_entities.replace_source_data(
                source=source,
                entities=domain_entities
            )
            
            # Step 5: Create result
            detection_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = ChangeDetectionResult(
                changes_detected=changes,
                entities_added=replace_result.get('added', 0),
                entities_modified=replace_result.get('updated', 0),
                entities_removed=replace_result.get('removed', 0),
                processing_time_ms=int(detection_time),
                content_changed=len(changes) > 0
            )
            
            log_performance(
                self.logger,
                "change_detection",
                detection_time,
                success=True,
                source=source.value,
                changes_detected=len(changes),
                entities_processed=len(new_entities)
            )
            
            return result
            
        except Exception as e:
            error = handle_exception(e, self.logger, context={
                "operation": "perform_change_detection",
                "source": source.value,
                "scraper_run_id": scraper_run_id
            })
            raise DatabaseError("Change detection failed", cause=e) from error

# ======================== UNIT OF WORK FACTORY ========================

class SQLAlchemyUnitOfWorkFactory:
    """Factory for creating SQLAlchemy Unit of Work instances."""
    
    def __init__(self, session_factory):
        """
        Initialize factory with SQLAlchemy session factory.
        
        Args:
            session_factory: Callable that returns SQLAlchemy Session
        """
        self.session_factory = session_factory
        self.logger = get_logger(__name__)
    
    def create_unit_of_work(self) -> SQLAlchemyUnitOfWork:
        """Create new Unit of Work instance."""
        try:
            session = self.session_factory()
            return SQLAlchemyUnitOfWork(session)
        except Exception as e:
            handle_exception(e, self.logger, context={"operation": "create_unit_of_work"})
            raise DatabaseError("Failed to create Unit of Work", cause=e)
    
    async def create_async_unit_of_work(self) -> SQLAlchemyUnitOfWork:
        """Create new async Unit of Work instance."""
        # For SQLAlchemy, this is the same as sync version
        return self.create_unit_of_work()

# ======================== DEPENDENCY INJECTION HELPERS ========================

from src.infrastructure.database.connection import db_manager

def get_uow_factory() -> SQLAlchemyUnitOfWorkFactory:
    """Get Unit of Work factory instance."""
    return SQLAlchemyUnitOfWorkFactory(db_manager.SessionLocal)

@asynccontextmanager
async def get_unit_of_work():
    """Get Unit of Work instance as dependency."""
    factory = get_uow_factory()
    async with factory.create_async_unit_of_work() as uow:
        yield uow

# ======================== TESTING SUPPORT ========================

class InMemoryUnitOfWork(SQLAlchemyUnitOfWork):
    """In-memory Unit of Work for testing."""
    
    def __init__(self):
        # This would use an in-memory SQLite database for testing
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine("sqlite:///:memory:")
        Session = sessionmaker(bind=engine)
        session = Session()
        
        super().__init__(session)
    
    async def rollback(self) -> None:
        """Override rollback for testing scenarios."""
        await super().rollback()
        # Additional cleanup for testing

class FakeUnitOfWork:
    """Fake Unit of Work for testing without database."""
    
    def __init__(self):
        # Use fake repositories for testing
        from tests.fakes import (
            FakeSanctionedEntityRepository,
            FakeChangeEventRepository,
            FakeScraperRunRepository,
            FakeContentSnapshotRepository
        )
        
        self.sanctioned_entities = FakeSanctionedEntityRepository()
        self.change_events = FakeChangeEventRepository()
        self.scraper_runs = FakeScraperRunRepository()
        self.content_snapshots = FakeContentSnapshotRepository()
        
        self._committed = False
        self._rolled_back = False
        self._transaction_started = False
    
    async def __aenter__(self):
        self._transaction_started = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
    
    async def begin(self) -> None:
        self._transaction_started = True
    
    async def commit(self) -> None:
        self._committed = True
    
    async def rollback(self) -> None:
        self._rolled_back = True
    
    async def flush(self) -> None:
        pass
    
    @property
    def is_active(self) -> bool:
        return self._transaction_started and not self._committed and not self._rolled_back
    
    async def health_check(self) -> Dict[str, Any]:
        return {"overall_healthy": True}

# ======================== BUSINESS OPERATIONS WITH UOW ========================

class UnitOfWorkBusinessOperations:
    """Business operations that use Unit of Work for complex workflows."""
    
    def __init__(self, uow_factory: SQLAlchemyUnitOfWorkFactory):
        self.uow_factory = uow_factory
        self.logger = get_logger(__name__)
    
    async def complete_scraping_workflow(
        self,
        source: 'DataSource',
        raw_content: str,
        parsed_entities: list,
        scraper_run_data: dict
    ) -> Dict[str, Any]:
        """
        Complete end-to-end scraping workflow with change detection.
        
        This orchestrates:
        1. Content snapshot creation
        2. Change detection  
        3. Entity updates
        4. Change event recording
        5. Scraper run completion
        """
        async with self.uow_factory.create_async_unit_of_work() as uow:
            try:
                # Import at runtime to avoid circular imports
                from src.core.domain.entities import ScraperRunDomain, ContentSnapshotDomain
                import hashlib
                
                # Step 1: Create and store scraper run
                scraper_run = ScraperRunDomain(**scraper_run_data)
                scraper_run = await uow.scraper_runs.create(scraper_run)
                
                # Step 2: Create content snapshot
                content_hash = hashlib.sha256(raw_content.encode('utf-8')).hexdigest()
                snapshot = ContentSnapshotDomain(
                    source=source,
                    content_hash=content_hash,
                    content_size_bytes=len(raw_content.encode('utf-8')),
                    scraper_run_id=scraper_run.run_id
                )
                await uow.content_snapshots.create(snapshot)
                
                # Step 3: Perform change detection and entity updates
                old_content_hash = await uow.content_snapshots.get_last_content_hash(source)
                
                change_result = await uow.perform_change_detection(
                    source=source,
                    new_entities=parsed_entities,
                    scraper_run_id=scraper_run.run_id,
                    old_content_hash=old_content_hash or '',
                    new_content_hash=content_hash
                )
                
                # Step 4: Update scraper run with results
                scraper_run.entities_processed = len(parsed_entities)
                scraper_run.entities_added = change_result.entities_added
                scraper_run.entities_modified = change_result.entities_modified
                scraper_run.entities_removed = change_result.entities_removed
                scraper_run.mark_completed(scraper_run.status)
                
                await uow.scraper_runs.update(scraper_run)
                
                # Step 5: Commit all changes
                await uow.commit()
                
                self.logger.info(
                    f"Completed scraping workflow for {source.value}",
                    extra={
                        "source": source.value,
                        "scraper_run_id": scraper_run.run_id,
                        "entities_processed": len(parsed_entities),
                        "changes_detected": change_result.total_changes,
                        "content_changed": change_result.content_changed
                    }
                )
                
                return {
                    'success': True,
                    'scraper_run': scraper_run,
                    'change_detection_result': change_result,
                    'content_snapshot': snapshot
                }
                
            except Exception as e:
                self.logger.error(
                    f"Scraping workflow failed for {source.value}: {e}",
                    exc_info=True
                )
                await uow.rollback()
                raise

# ======================== EXPORTS ========================

__all__ = [
    'SQLAlchemyUnitOfWork',
    'SQLAlchemyUnitOfWorkFactory',
    'InMemoryUnitOfWork',
    'FakeUnitOfWork',
    'UnitOfWorkBusinessOperations',
    'get_uow_factory',
    'get_unit_of_work'
]