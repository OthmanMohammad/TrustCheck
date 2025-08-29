"""
Fake Implementations for Testing

Provides fake repositories and services for unit testing without database dependencies.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

from src.core.domain.entities import (
    SanctionedEntityDomain, ChangeEventDomain, ScraperRunDomain, 
    ContentSnapshotDomain, ChangeDetectionResult
)
from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel, ScrapingStatus

# ======================== FAKE REPOSITORIES ========================

class FakeSanctionedEntityRepository:
    """Fake sanctioned entity repository for testing."""
    
    def __init__(self):
        self.entities: Dict[str, SanctionedEntityDomain] = {}
        self._healthy = True
    
    async def create(self, entity: SanctionedEntityDomain) -> SanctionedEntityDomain:
        self.entities[entity.uid] = entity
        return entity
    
    async def get_by_uid(self, uid: str) -> Optional[SanctionedEntityDomain]:
        return self.entities.get(uid)
    
    async def get_by_id(self, entity_id: int) -> Optional[SanctionedEntityDomain]:
        # For testing, just return first entity
        return next(iter(self.entities.values()), None)
    
    async def update(self, entity: SanctionedEntityDomain) -> SanctionedEntityDomain:
        self.entities[entity.uid] = entity
        return entity
    
    async def delete_by_uid(self, uid: str) -> bool:
        if uid in self.entities:
            del self.entities[uid]
            return True
        return False
    
    async def deactivate_by_uid(self, uid: str) -> bool:
        if uid in self.entities:
            self.entities[uid].deactivate()
            return True
        return False
    
    async def create_many(self, entities: List[SanctionedEntityDomain]) -> List[SanctionedEntityDomain]:
        for entity in entities:
            self.entities[entity.uid] = entity
        return entities
    
    async def update_many(self, entities: List[SanctionedEntityDomain]) -> List[SanctionedEntityDomain]:
        for entity in entities:
            self.entities[entity.uid] = entity
        return entities
    
    async def replace_source_data(
        self, source: DataSource, entities: List[SanctionedEntityDomain]
    ) -> Dict[str, int]:
        # Simple fake implementation
        old_count = len([e for e in self.entities.values() if e.source == source])
        
        # Remove old entities for this source
        self.entities = {k: v for k, v in self.entities.items() if v.source != source}
        
        # Add new entities
        for entity in entities:
            self.entities[entity.uid] = entity
        
        return {
            'added': len(entities),
            'updated': 0,
            'removed': old_count
        }
    
    async def find_by_source(
        self, source: DataSource, active_only: bool = True,
        limit: Optional[int] = None, offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        results = [e for e in self.entities.values() if e.source == source]
        if active_only:
            results = [e for e in results if e.is_active]
        
        if limit:
            results = results[offset:offset + limit]
        return results
    
    async def find_by_entity_type(
        self, entity_type: EntityType, limit: Optional[int] = None, offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        results = [e for e in self.entities.values() if e.entity_type == entity_type]
        if limit:
            results = results[offset:offset + limit]
        return results
    
    async def search_by_name(
        self, name: str, fuzzy: bool = False, limit: int = 20, offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        results = [e for e in self.entities.values() if name.lower() in e.name.lower()]
        return results[offset:offset + limit]
    
    async def count_by_source(self, source: DataSource) -> int:
        return len([e for e in self.entities.values() if e.source == source and e.is_active])
    
    async def get_statistics(self) -> Dict[str, Any]:
        return {
            'total_active': len([e for e in self.entities.values() if e.is_active]),
            'total_inactive': len([e for e in self.entities.values() if not e.is_active]),
            'by_source': {},
            'by_type': {},
            'last_updated': datetime.utcnow().isoformat()
        }
    
    async def get_all_for_change_detection(self, source: DataSource) -> List[SanctionedEntityDomain]:
        return [e for e in self.entities.values() if e.source == source and e.is_active]
    
    async def get_content_hashes(self, source: DataSource) -> Dict[str, str]:
        return {e.uid: e.content_hash or '' for e in self.entities.values() if e.source == source}
    
    async def find_by_content_hash(self, content_hash: str) -> List[SanctionedEntityDomain]:
        return [e for e in self.entities.values() if e.content_hash == content_hash]
    
    async def health_check(self) -> bool:
        return self._healthy

class FakeChangeEventRepository:
    """Fake change event repository for testing."""
    
    def __init__(self):
        self.events: Dict[UUID, ChangeEventDomain] = {}
    
    async def create(self, change_event: ChangeEventDomain) -> ChangeEventDomain:
        self.events[change_event.event_id] = change_event
        return change_event
    
    async def get_by_id(self, event_id: UUID) -> Optional[ChangeEventDomain]:
        return self.events.get(event_id)
    
    async def create_many(self, events: List[ChangeEventDomain]) -> List[ChangeEventDomain]:
        for event in events:
            self.events[event.event_id] = event
        return events
    
    async def find_recent(
        self, days: int = 7, source: Optional[DataSource] = None,
        risk_level: Optional[RiskLevel] = None, limit: Optional[int] = None, offset: int = 0
    ) -> List[ChangeEventDomain]:
        results = list(self.events.values())
        if source:
            results = [e for e in results if e.source == source]
        if risk_level:
            results = [e for e in results if e.risk_level == risk_level]
        
        if limit:
            results = results[offset:offset + limit]
        return results
    
    async def count_by_risk_level(
        self, since: Optional[datetime] = None, source: Optional[DataSource] = None
    ) -> Dict[RiskLevel, int]:
        events = list(self.events.values())
        if source:
            events = [e for e in events if e.source == source]
        
        counts = {}
        for event in events:
            counts[event.risk_level] = counts.get(event.risk_level, 0) + 1
        return counts
    
    async def count_by_change_type(
        self, since: Optional[datetime] = None, source: Optional[DataSource] = None
    ) -> Dict[ChangeType, int]:
        events = list(self.events.values())
        if source:
            events = [e for e in events if e.source == source]
        
        counts = {}
        for event in events:
            counts[event.change_type] = counts.get(event.change_type, 0) + 1
        return counts
    
    async def find_by_risk_level(
        self, risk_level: RiskLevel, since: Optional[datetime] = None,
        limit: Optional[int] = None, offset: int = 0
    ) -> List[ChangeEventDomain]:
        results = [e for e in self.events.values() if e.risk_level == risk_level]
        if limit:
            results = results[offset:offset + limit]
        return results
    
    async def health_check(self) -> bool:
        return True

class FakeScraperRunRepository:
    """Fake scraper run repository for testing."""
    
    def __init__(self):
        self.runs: Dict[str, ScraperRunDomain] = {}
    
    async def create(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        self.runs[scraper_run.run_id] = scraper_run
        return scraper_run
    
    async def update(self, scraper_run: ScraperRunDomain) -> ScraperRunDomain:
        self.runs[scraper_run.run_id] = scraper_run
        return scraper_run
    
    async def get_by_run_id(self, run_id: str) -> Optional[ScraperRunDomain]:
        return self.runs.get(run_id)
    
    async def find_recent(
        self, hours: int = 24, source: Optional[DataSource] = None, limit: Optional[int] = None
    ) -> List[ScraperRunDomain]:
        results = list(self.runs.values())
        if source:
            results = [r for r in results if r.source == source]
        if limit:
            results = results[:limit]
        return results
    
    async def count_by_status(
        self, since: Optional[datetime] = None, source: Optional[DataSource] = None
    ) -> Dict[ScrapingStatus, int]:
        runs = list(self.runs.values())
        if source:
            runs = [r for r in runs if r.source == source]
        
        counts = {}
        for run in runs:
            counts[run.status] = counts.get(run.status, 0) + 1
        return counts
    
    async def get_run_statistics(
        self, source: Optional[DataSource] = None, days: int = 7
    ) -> Dict[str, Any]:
        runs = list(self.runs.values())
        if source:
            runs = [r for r in runs if r.source == source]
        
        total_runs = len(runs)
        successful_runs = len([r for r in runs if r.status == ScrapingStatus.SUCCESS])
        
        return {
            'total_runs': total_runs,
            'success_rate': (successful_runs / total_runs * 100) if total_runs > 0 else 0,
            'average_duration_seconds': 0,
            'by_status': {}
        }
    
    async def health_check(self) -> bool:
        return True

class FakeContentSnapshotRepository:
    """Fake content snapshot repository for testing."""
    
    def __init__(self):
        self.snapshots: Dict[UUID, ContentSnapshotDomain] = {}
    
    async def create(self, snapshot: ContentSnapshotDomain) -> ContentSnapshotDomain:
        self.snapshots[snapshot.snapshot_id] = snapshot
        return snapshot
    
    async def get_latest_snapshot(self, source: DataSource) -> Optional[ContentSnapshotDomain]:
        snapshots = [s for s in self.snapshots.values() if s.source == source]
        return snapshots[-1] if snapshots else None
    
    async def get_last_content_hash(self, source: DataSource) -> Optional[str]:
        latest = await self.get_latest_snapshot(source)
        return latest.content_hash if latest else None
    
    async def find_by_source(
        self, source: DataSource, limit: Optional[int] = None, offset: int = 0
    ) -> List[ContentSnapshotDomain]:
        results = [s for s in self.snapshots.values() if s.source == source]
        if limit:
            results = results[offset:offset + limit]
        return results
    
    async def health_check(self) -> bool:
        return True

# ======================== FAKE SERVICES ========================

class FakeChangeDetectionService:
    """Fake change detection service for testing."""
    
    async def detect_changes_for_source(
        self, source: DataSource, new_entities_data: List[Dict[str, Any]],
        scraper_run_id: str, old_content_hash: str = "", new_content_hash: str = ""
    ) -> ChangeDetectionResult:
        return ChangeDetectionResult(
            changes_detected=[],
            entities_added=len(new_entities_data),
            entities_modified=0,
            entities_removed=0,
            processing_time_ms=100,
            content_changed=True
        )
    
    async def get_change_summary(
        self, days: int = 7, source: Optional[DataSource] = None, 
        risk_level: Optional[RiskLevel] = None
    ) -> Dict[str, Any]:
        return {
            'period': {'days': days},
            'totals': {'total_changes': 0},
            'by_type': {},
            'by_risk_level': {}
        }
    
    async def get_critical_changes(
        self, hours: int = 24, source: Optional[DataSource] = None
    ) -> List[ChangeEventDomain]:
        return []
    
    async def health_check(self) -> Dict[str, Any]:
        return {'healthy': True, 'status': 'operational'}

class FakeScrapingService:
    """Fake scraping service for testing."""
    
    async def execute_scraping_request(self, request) -> Dict[str, Any]:
        return {
            'status': 'success',
            'scraper_run_id': 'fake_run_123',
            'source': request.source.value,
            'duration_seconds': 1.5,
            'scraping_result': {'entities': []},
            'change_detection_result': None,
            'notifications_triggered': False
        }
    
    async def get_scraping_status(
        self, source: Optional[DataSource] = None, hours: int = 24
    ) -> Dict[str, Any]:
        return {
            'metrics': {'total_runs': 0, 'success_rate_percent': 100},
            'recent_runs': []
        }
    
    async def health_check(self) -> Dict[str, Any]:
        return {'healthy': True, 'status': 'operational'}

class FakeNotificationService:
    """Fake notification service for testing."""
    
    async def dispatch_changes(self, changes: List, source: str) -> Dict[str, Any]:
        return {
            'status': 'success',
            'immediate_sent': 0,
            'high_priority_sent': 0,
            'low_priority_queued': 0,
            'failed': 0,
            'errors': []
        }
    
    async def health_check(self) -> Dict[str, Any]:
        return {'healthy': True, 'status': 'operational'}