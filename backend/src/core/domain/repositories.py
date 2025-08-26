"""
Repository Interfaces - Pure Abstractions

Protocol-based repository interfaces.
These define the contracts that concrete implementations must follow.
"""

from typing import Protocol, List, Optional, Dict, Any, AsyncIterator
from abc import abstractmethod
from uuid import UUID
from datetime import datetime, timedelta

from src.core.domain.entities import (
    SanctionedEntityDomain, ChangeEventDomain, ScraperRunDomain, 
    ContentSnapshotDomain, ChangeDetectionResult, ScrapingRequest
)
from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel, ScrapingStatus
from src.core.exceptions import ResourceNotFoundError, RepositoryError

# ======================== BASE REPOSITORY INTERFACE ========================

class BaseRepository(Protocol):
    """Base repository interface with common operations."""
    
    async def begin_transaction(self) -> None:
        """Begin database transaction."""
        ...
    
    async def commit_transaction(self) -> None:
        """Commit current transaction."""
        ...
    
    async def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        ...
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        ...

# ======================== SANCTIONED ENTITY REPOSITORY ========================

class SanctionedEntityRepository(BaseRepository, Protocol):
    """
    Repository for sanctioned entity operations.
    
    Defines all operations for managing sanctioned entities
    without any database implementation details.
    """
    
    # ======================== BASIC CRUD OPERATIONS ========================
    
    async def create(self, entity: SanctionedEntityDomain) -> SanctionedEntityDomain:
        """Create new sanctioned entity."""
        ...
    
    async def get_by_uid(self, uid: str) -> Optional[SanctionedEntityDomain]:
        """Get entity by unique identifier."""
        ...
    
    async def get_by_id(self, entity_id: int) -> Optional[SanctionedEntityDomain]:
        """Get entity by database ID."""
        ...
    
    async def update(self, entity: SanctionedEntityDomain) -> SanctionedEntityDomain:
        """Update existing entity."""
        ...
    
    async def delete_by_uid(self, uid: str) -> bool:
        """Delete entity by UID (returns True if deleted)."""
        ...
    
    async def deactivate_by_uid(self, uid: str) -> bool:
        """Soft delete entity by UID."""
        ...
    
    # ======================== BULK OPERATIONS ========================
    
    async def create_many(self, entities: List[SanctionedEntityDomain]) -> List[SanctionedEntityDomain]:
        """Create multiple entities efficiently."""
        ...
    
    async def update_many(self, entities: List[SanctionedEntityDomain]) -> List[SanctionedEntityDomain]:
        """Update multiple entities efficiently."""
        ...
    
    async def replace_source_data(
        self, 
        source: DataSource, 
        entities: List[SanctionedEntityDomain]
    ) -> Dict[str, int]:
        """
        Replace all data for a source with new entities.
        
        Returns:
            Dict with counts: {added: int, updated: int, removed: int}
        """
        ...
    
    # ======================== QUERY OPERATIONS ========================
    
    async def find_by_source(
        self, 
        source: DataSource, 
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find entities by source."""
        ...
    
    async def find_by_entity_type(
        self, 
        entity_type: EntityType,
        limit: Optional[int] = None,
        offset: int = 0  
    ) -> List[SanctionedEntityDomain]:
        """Find entities by type."""
        ...
    
    async def search_by_name(
        self, 
        name: str, 
        fuzzy: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Search entities by name (including aliases)."""
        ...
    
    async def find_by_program(
        self, 
        program: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find entities by sanctions program."""
        ...
    
    async def find_by_nationality(
        self, 
        nationality: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find entities by nationality."""
        ...
    
    async def find_recently_updated(
        self, 
        since: datetime,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None
    ) -> List[SanctionedEntityDomain]:
        """Find entities updated since given time."""
        ...
    
    # ======================== AGGREGATE OPERATIONS ========================
    
    async def count_by_source(self, source: DataSource) -> int:
        """Count entities by source."""
        ...
    
    async def count_by_entity_type(self, entity_type: EntityType) -> int:
        """Count entities by type."""
        ...
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get repository statistics.
        
        Returns:
            Dict with counts by source, type, active/inactive, etc.
        """
        ...
    
    async def get_sources_summary(self) -> Dict[DataSource, Dict[str, Any]]:
        """
        Get summary statistics by source.
        
        Returns:
            Dict mapping sources to their statistics.
        """
        ...
    
    # ======================== CHANGE DETECTION SUPPORT ========================
    
    async def get_all_for_change_detection(
        self, 
        source: DataSource
    ) -> List[SanctionedEntityDomain]:
        """Get all entities for change detection comparison."""
        ...
    
    async def get_content_hashes(self, source: DataSource) -> Dict[str, str]:
        """Get mapping of entity UID to content hash for a source."""
        ...
    
    async def find_by_content_hash(self, content_hash: str) -> List[SanctionedEntityDomain]:
        """Find entities with specific content hash."""
        ...

# ======================== CHANGE EVENT REPOSITORY ========================

class ChangeEventRepository(BaseRepository, Protocol):
    """Repository for change event operations."""
    
    # ======================== BASIC CRUD ========================
    
    async def create(self, change_event: ChangeEventDomain) -> ChangeEventDomain:
        """Create new change event."""
        ...
    
    async def get_by_id(self, event_id: UUID) -> Optional[ChangeEventDomain]:
        """Get change event by ID."""
        ...
    
    async def create_many(self, events: List[ChangeEventDomain]) -> List[ChangeEventDomain]:
        """Create multiple change events efficiently."""
        ...
    
    # ======================== QUERY OPERATIONS ========================
    
    async def find_by_source(
        self,
        source: DataSource,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find change events by source."""
        ...
    
    async def find_by_entity(
        self,
        entity_uid: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find all changes for specific entity."""
        ...
    
    async def find_by_change_type(
        self,
        change_type: ChangeType,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find changes by type."""
        ...
    
    async def find_by_risk_level(
        self,
        risk_level: RiskLevel,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find changes by risk level."""
        ...
    
    async def find_recent(
        self,
        days: int = 7,
        source: Optional[DataSource] = None,
        risk_level: Optional[RiskLevel] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChangeEventDomain]:
        """Find recent change events with filters."""
        ...
    
    async def find_critical_changes(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ChangeEventDomain]:
        """Find critical changes requiring immediate attention."""
        ...
    
    async def find_pending_notifications(
        self,
        limit: Optional[int] = None
    ) -> List[ChangeEventDomain]:
        """Find changes that need notification dispatch."""
        ...
    
    # ======================== AGGREGATE OPERATIONS ========================
    
    async def count_by_risk_level(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[RiskLevel, int]:
        """Count changes by risk level."""
        ...
    
    async def count_by_change_type(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[ChangeType, int]:
        """Count changes by type."""
        ...
    
    async def get_change_summary(
        self,
        days: int = 7,
        source: Optional[DataSource] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive change summary.
        
        Returns:
            Dict with change counts, trends, risk distribution, etc.
        """
        ...
    
    # ======================== NOTIFICATION SUPPORT ========================
    
    async def mark_notification_sent(
        self,
        event_id: UUID,
        channels: List[str],
        sent_at: Optional[datetime] = None
    ) -> bool:
        """Mark change event notification as sent."""
        ...
    
    async def mark_many_notifications_sent(
        self,
        event_ids: List[UUID],
        channels: List[str],
        sent_at: Optional[datetime] = None
    ) -> int:
        """Mark multiple notifications as sent. Returns count updated."""
        ...

# ======================== SCRAPER RUN REPOSITORY ========================

class ScraperRunRepository(BaseRepository, Protocol):
    """Repository for scraper run tracking."""
    
    # ======================== BASIC CRUD ========================
    
    async def create(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        """Create new scraper run."""
        ...
    
    async def get_by_run_id(self, run_id: str) -> Optional[ScraperRunDomain]:
        """Get scraper run by run ID."""
        ...
    
    async def update(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        """Update scraper run."""
        ...
    
    # ======================== QUERY OPERATIONS ========================
    
    async def find_by_source(
        self,
        source: DataSource,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ScraperRunDomain]:
        """Find runs by source, ordered by start time desc."""
        ...
    
    async def find_by_status(
        self,
        status: ScrapingStatus,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ScraperRunDomain]:
        """Find runs by status."""
        ...
    
    async def find_recent(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None
    ) -> List[ScraperRunDomain]:
        """Find recent runs within time window."""
        ...
    
    async def find_successful_runs(
        self,
        source: DataSource,
        limit: Optional[int] = None
    ) -> List[ScraperRunDomain]:
        """Find successful runs for a source."""
        ...
    
    async def find_failed_runs(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ScraperRunDomain]:
        """Find failed runs for investigation."""
        ...
    
    async def get_last_successful_run(
        self,
        source: DataSource
    ) -> Optional[ScraperRunDomain]:
        """Get most recent successful run for a source."""
        ...
    
    async def get_last_run(
        self,
        source: DataSource
    ) -> Optional[ScraperRunDomain]:
        """Get most recent run (any status) for a source."""
        ...
    
    # ======================== AGGREGATE OPERATIONS ========================
    
    async def get_run_statistics(
        self,
        source: Optional[DataSource] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get scraper run statistics.
        
        Returns:
            Dict with success rates, average duration, error patterns, etc.
        """
        ...
    
    async def get_performance_metrics(
        self,
        source: DataSource,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get performance metrics for a source."""
        ...
    
    async def count_by_status(
        self,
        since: Optional[datetime] = None,
        source: Optional[DataSource] = None
    ) -> Dict[ScrapingStatus, int]:
        """Count runs by status."""
        ...
    
    # ======================== MAINTENANCE OPERATIONS ========================
    
    async def cleanup_old_runs(
        self,
        older_than_days: int = 90,
        keep_failed: bool = True
    ) -> int:
        """Clean up old run records. Returns count deleted."""
        ...
    
    async def get_long_running_jobs(
        self,
        threshold_minutes: int = 30
    ) -> List[ScraperRunDomain]:
        """Find currently running jobs that are taking too long."""
        ...

# ======================== CONTENT SNAPSHOT REPOSITORY ========================

class ContentSnapshotRepository(BaseRepository, Protocol):
    """Repository for content snapshots."""
    
    # ======================== BASIC CRUD ========================
    
    async def create(self, snapshot: ContentSnapshotDomain) -> ContentSnapshotDomain:
        """Create content snapshot."""
        ...
    
    async def get_by_id(self, snapshot_id: UUID) -> Optional[ContentSnapshotDomain]:
        """Get snapshot by ID."""
        ...
    
    async def get_by_content_hash(self, content_hash: str) -> Optional[ContentSnapshotDomain]:
        """Get snapshot by content hash."""
        ...
    
    # ======================== QUERY OPERATIONS ========================
    
    async def find_by_source(
        self,
        source: DataSource,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ContentSnapshotDomain]:
        """Find snapshots by source, ordered by time desc."""
        ...
    
    async def get_latest_snapshot(
        self,
        source: DataSource
    ) -> Optional[ContentSnapshotDomain]:
        """Get most recent snapshot for a source."""
        ...
    
    async def find_by_scraper_run(
        self,
        run_id: str
    ) -> Optional[ContentSnapshotDomain]:
        """Find snapshot by scraper run ID."""
        ...
    
    async def find_recent(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None,
        limit: Optional[int] = None
    ) -> List[ContentSnapshotDomain]:
        """Find recent snapshots."""
        ...
    
    # ======================== CHANGE DETECTION SUPPORT ========================
    
    async def get_last_content_hash(self, source: DataSource) -> Optional[str]:
        """Get content hash from most recent snapshot."""
        ...
    
    async def has_content_changed(
        self,
        source: DataSource,
        new_content_hash: str
    ) -> bool:
        """Check if content has changed since last snapshot."""
        ...
    
    async def find_duplicate_hashes(
        self,
        source: DataSource
    ) -> List[ContentSnapshotDomain]:
        """Find snapshots with duplicate content hashes."""
        ...
    
    # ======================== MAINTENANCE OPERATIONS ========================
    
    async def cleanup_old_snapshots(
        self,
        older_than_days: int = 30,
        keep_count: int = 10
    ) -> int:
        """Clean up old snapshots, keeping recent ones. Returns count deleted."""
        ...
    
    async def get_storage_statistics(self) -> Dict[str, Any]:
        """Get storage statistics for snapshots."""
        ...

# ======================== SPECIALIZED REPOSITORY INTERFACES ========================

class ChangeDetectionRepository(Protocol):
    """
    Specialized repository for change detection operations.
    
    Combines multiple repositories for complex change detection workflows.
    """
    
    async def perform_change_detection(
        self,
        source: DataSource,
        new_entities: List[SanctionedEntityDomain],
        scraper_run_id: str,
        old_content_hash: str,
        new_content_hash: str
    ) -> ChangeDetectionResult:
        """
        Perform comprehensive change detection.
        
        This method:
        1. Compares old vs new entities
        2. Creates change events
        3. Updates entities
        4. Returns detection results
        """
        ...
    
    async def get_change_detection_summary(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get comprehensive change detection summary."""
        ...

class ReportingRepository(Protocol):
    """Repository for generating reports and analytics."""
    
    async def get_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        sources: Optional[List[DataSource]] = None
    ) -> Dict[str, Any]:
        """Generate compliance report for date range."""
        ...
    
    async def get_change_trend_analysis(
        self,
        days: int = 30,
        source: Optional[DataSource] = None
    ) -> Dict[str, Any]:
        """Analyze change trends over time."""
        ...
    
    async def get_risk_assessment_report(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """Generate risk assessment report."""
        ...
    
    async def get_system_health_report(self) -> Dict[str, Any]:
        """Generate system health and performance report."""
        ...

# ======================== UNIT OF WORK INTERFACE ========================

class UnitOfWork(Protocol):
    """
    Unit of Work interface for managing transactions across repositories.
    
    Ensures all repository operations within a business transaction
    succeed or fail together.
    """
    
    # Repository access
    sanctioned_entities: SanctionedEntityRepository
    change_events: ChangeEventRepository  
    scraper_runs: ScraperRunRepository
    content_snapshots: ContentSnapshotRepository
    
    # Transaction management
    async def __aenter__(self) -> 'UnitOfWork':
        """Enter async context and begin transaction."""
        ...
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context, commit or rollback based on exceptions."""
        ...
    
    async def commit(self) -> None:
        """Commit all pending changes."""
        ...
    
    async def rollback(self) -> None:
        """Rollback all pending changes."""
        ...

# ======================== REPOSITORY EXCEPTIONS ========================

class RepositoryError(Exception):
    """Base repository error."""
    pass

class EntityNotFoundError(RepositoryError):
    """Entity not found in repository."""
    pass

class DuplicateEntityError(RepositoryError):
    """Attempt to create duplicate entity."""
    pass

class TransactionError(RepositoryError):
    """Transaction operation failed."""
    pass

class QueryError(RepositoryError):
    """Query execution failed."""
    pass

# ======================== EXPORTS ========================

__all__ = [
    # Base interfaces
    'BaseRepository',
    
    # Core repositories
    'SanctionedEntityRepository',
    'ChangeEventRepository',
    'ScraperRunRepository', 
    'ContentSnapshotRepository',
    
    # Specialized repositories
    'ChangeDetectionRepository',
    'ReportingRepository',
    
    # Unit of Work
    'UnitOfWork',
    
    # Exceptions
    'RepositoryError',
    'EntityNotFoundError',
    'DuplicateEntityError',
    'TransactionError',
    'QueryError'
]