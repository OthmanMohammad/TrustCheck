"""
Domain Entities

Business entities.
These represent core business concepts and rules.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

from src.core.enums import EntityType, ChangeType, RiskLevel, DataSource, ScrapingStatus

# ======================== VALUE OBJECTS ========================

@dataclass(frozen=True)
class Address:
    """Immutable address value object."""
    street: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    
    def __str__(self) -> str:
        """Format address as string."""
        parts = [
            self.street, self.city, self.state_province, 
            self.postal_code, self.country
        ]
        return ', '.join(part for part in parts if part)
    
    @property
    def is_complete(self) -> bool:
        """Check if address has minimum required information."""
        return bool(self.city and self.country)

@dataclass(frozen=True)
class PersonalInfo:
    """Personal information value object."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        """Get full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.last_name or self.first_name or ""

@dataclass(frozen=True)
class FieldChange:
    """Represents a change in a specific field."""
    field_name: str
    old_value: Any
    new_value: Any
    change_type: str  # 'field_added', 'field_removed', 'field_modified'
    
    @property
    def is_significant(self) -> bool:
        """Determine if this field change is significant."""
        from src.core.enums import FieldImportance
        importance = FieldImportance.get_field_importance(self.field_name)
        return importance in [FieldImportance.CRITICAL, FieldImportance.HIGH]

# ======================== CORE ENTITIES ========================

@dataclass
class SanctionedEntityDomain:
    """
    Core business entity representing a sanctioned individual or organization.
    
    This is a pure domain object with business logic but no persistence concerns.
    """
    
    # Identity
    uid: str
    name: str
    entity_type: EntityType
    source: DataSource
    
    # Core sanctions data
    programs: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    addresses: List[Address] = field(default_factory=list)
    
    # Personal information (for persons)
    personal_info: Optional[PersonalInfo] = None
    
    # Additional data
    nationalities: List[str] = field(default_factory=list)
    remarks: Optional[str] = None
    
    # Metadata
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: Optional[datetime] = None
    content_hash: Optional[str] = None
    
    def __post_init__(self):
        """Validate entity after creation."""
        if not self.uid:
            raise ValueError("Entity UID is required")
        if not self.name:
            raise ValueError("Entity name is required")
        if len(self.name) < 2:
            raise ValueError("Entity name must be at least 2 characters")
    
    # ======================== BUSINESS LOGIC METHODS ========================
    
    def add_alias(self, alias: str) -> None:
        """Add alias with validation."""
        alias = alias.strip()
        if alias and alias not in self.aliases and alias != self.name:
            self.aliases.append(alias)
            self.mark_updated()
    
    def add_program(self, program: str) -> None:
        """Add sanctions program."""
        program = program.strip().upper()
        if program and program not in self.programs:
            self.programs.append(program)
            self.mark_updated()
    
    def add_address(self, address: Address) -> None:
        """Add address if valid and not duplicate."""
        if address.is_complete and address not in self.addresses:
            self.addresses.append(address)
            self.mark_updated()
    
    def mark_updated(self) -> None:
        """Mark entity as updated."""
        self.updated_at = datetime.utcnow()
    
    def mark_seen(self) -> None:
        """Mark entity as seen in latest scraping."""
        self.last_seen = datetime.utcnow()
    
    def deactivate(self) -> None:
        """Deactivate entity (soft delete)."""
        self.is_active = False
        self.mark_updated()
    
    # ======================== COMPUTED PROPERTIES ========================
    
    @property
    def is_person(self) -> bool:
        """Check if entity is a person."""
        return self.entity_type == EntityType.PERSON
    
    @property
    def is_high_risk(self) -> bool:
        """Check if entity is high risk based on programs."""
        high_risk_programs = {'SDGT', 'TERRORISM', 'PROLIFERATION', 'CYBER'}
        return any(program in high_risk_programs for program in self.programs)
    
    @property
    def display_name(self) -> str:
        """Get primary display name."""
        return self.name
    
    @property
    def all_names(self) -> List[str]:
        """Get all names including aliases."""
        return [self.name] + self.aliases
    
    # ======================== COMPARISON METHODS ========================
    
    def calculate_content_hash(self) -> str:
        """Calculate content hash for change detection."""
        import hashlib
        
        content = f"{self.name}{self.entity_type}{sorted(self.programs)}{sorted(self.aliases)}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get_changes_from(self, other: 'SanctionedEntityDomain') -> List[FieldChange]:
        """Compare with another entity and return list of changes."""
        changes = []
        
        # Compare each tracked field
        field_comparisons = {
            'name': (other.name, self.name),
            'entity_type': (other.entity_type, self.entity_type), 
            'programs': (set(other.programs), set(self.programs)),
            'aliases': (set(other.aliases), set(self.aliases)),
            'nationalities': (set(other.nationalities), set(self.nationalities)),
            'remarks': (other.remarks, self.remarks)
        }
        
        for field_name, (old_value, new_value) in field_comparisons.items():
            if old_value != new_value:
                change_type = self._determine_change_type(old_value, new_value)
                changes.append(FieldChange(
                    field_name=field_name,
                    old_value=old_value,
                    new_value=new_value,
                    change_type=change_type
                ))
        
        return changes
    
    def _determine_change_type(self, old_value: Any, new_value: Any) -> str:
        """Determine type of field change."""
        if old_value is None:
            return 'field_added'
        elif new_value is None:
            return 'field_removed'
        else:
            return 'field_modified'

@dataclass
class ChangeEventDomain:
    """
    Domain entity representing a detected change in sanctions data.
    """
    
    # Identity
    event_id: UUID = field(default_factory=uuid4)
    entity_uid: str = ""
    entity_name: str = ""
    source: DataSource = DataSource.OFAC
    
    # Change details
    change_type: ChangeType = ChangeType.MODIFIED
    risk_level: RiskLevel = RiskLevel.MEDIUM
    field_changes: List[FieldChange] = field(default_factory=list)
    change_summary: str = ""
    
    # Content tracking
    old_content_hash: Optional[str] = None
    new_content_hash: Optional[str] = None
    
    # Timing
    detected_at: datetime = field(default_factory=datetime.utcnow)
    scraper_run_id: str = ""
    processing_time_ms: Optional[int] = None
    
    # Notification tracking
    notification_sent_at: Optional[datetime] = None
    notification_channels: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate change event after creation."""
        if not self.entity_uid:
            raise ValueError("Entity UID is required")
        if not self.entity_name:
            raise ValueError("Entity name is required")
        if not self.change_summary:
            self.change_summary = self._generate_summary()
    
    # ======================== BUSINESS LOGIC ========================
    
    def _generate_summary(self) -> str:
        """Generate human-readable change summary."""
        action = self.change_type.get_action_verb()
        return f"{self.entity_name} {action} {self.source.value} sanctions list"
    
    def mark_notification_sent(self, channels: List[str]) -> None:
        """Mark notification as sent."""
        self.notification_sent_at = datetime.utcnow()
        self.notification_channels = channels
    
    @property
    def is_critical(self) -> bool:
        """Check if change is critical."""
        return self.risk_level == RiskLevel.CRITICAL
    
    @property
    def requires_immediate_notification(self) -> bool:
        """Check if change requires immediate notification."""
        return self.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
    
    def get_notification_priority(self) -> str:
        """Get notification priority based on risk level."""
        if self.risk_level == RiskLevel.CRITICAL:
            return "immediate"
        elif self.risk_level == RiskLevel.HIGH:
            return "batch_high"
        else:
            return "batch_low"

@dataclass  
class ScraperRunDomain:
    """
    Domain entity representing a scraper execution.
    """
    
    # Identity
    run_id: str
    source: DataSource
    
    # Execution timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: ScrapingStatus = ScrapingStatus.RUNNING
    
    # Content analysis
    source_url: Optional[str] = None
    content_hash: Optional[str] = None
    content_size_bytes: Optional[int] = None
    content_changed: bool = False
    
    # Entity processing results
    entities_processed: int = 0
    entities_added: int = 0
    entities_modified: int = 0
    entities_removed: int = 0
    
    # Change classification
    critical_changes: int = 0
    high_risk_changes: int = 0
    medium_risk_changes: int = 0
    low_risk_changes: int = 0
    
    # Performance metrics
    download_time_ms: Optional[int] = None
    parsing_time_ms: Optional[int] = None
    diff_time_ms: Optional[int] = None
    storage_time_ms: Optional[int] = None
    
    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        """Validate scraper run after creation."""
        if not self.run_id:
            raise ValueError("Run ID is required")
    
    # ======================== BUSINESS LOGIC ========================
    
    def mark_started(self) -> None:
        """Mark run as started."""
        self.started_at = datetime.utcnow()
        self.status = ScrapingStatus.RUNNING
    
    def mark_completed(self, status: ScrapingStatus) -> None:
        """Mark run as completed with status."""
        self.completed_at = datetime.utcnow()
        self.status = status
    
    def mark_failed(self, error_message: str) -> None:
        """Mark run as failed."""
        self.status = ScrapingStatus.FAILED
        self.error_message = error_message
        self.mark_completed(ScrapingStatus.FAILED)
    
    def mark_skipped(self, reason: str = "Content unchanged") -> None:
        """Mark run as skipped."""
        self.status = ScrapingStatus.SKIPPED
        self.error_message = reason
        self.mark_completed(ScrapingStatus.SKIPPED)
    
    def add_performance_metric(self, metric_name: str, value_ms: int) -> None:
        """Add performance metric."""
        setattr(self, f"{metric_name}_time_ms", value_ms)
    
    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
    
    # ======================== COMPUTED PROPERTIES ========================
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate run duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_successful(self) -> bool:
        """Check if run was successful."""
        return self.status == ScrapingStatus.SUCCESS
    
    @property
    def is_running(self) -> bool:
        """Check if run is still running."""
        return self.status == ScrapingStatus.RUNNING
    
    @property
    def total_changes(self) -> int:
        """Get total number of changes detected."""
        return (self.critical_changes + self.high_risk_changes + 
                self.medium_risk_changes + self.low_risk_changes)
    
    @property
    def has_critical_changes(self) -> bool:
        """Check if run detected critical changes."""
        return self.critical_changes > 0
    
    @property
    def change_summary(self) -> Dict[str, int]:
        """Get change summary by risk level."""
        return {
            'critical': self.critical_changes,
            'high': self.high_risk_changes,
            'medium': self.medium_risk_changes,
            'low': self.low_risk_changes,
            'total': self.total_changes
        }

@dataclass
class ContentSnapshotDomain:
    """
    Domain entity representing a content snapshot for change detection.
    """
    
    # Identity
    snapshot_id: UUID = field(default_factory=uuid4)
    source: DataSource = DataSource.OFAC
    
    # Content identification
    content_hash: str = ""
    content_size_bytes: int = 0
    
    # Timing
    snapshot_time: datetime = field(default_factory=datetime.utcnow)
    scraper_run_id: str = ""
    
    # Optional archive reference
    s3_archive_path: Optional[str] = None
    
    def __post_init__(self):
        """Validate snapshot after creation."""
        if not self.content_hash:
            raise ValueError("Content hash is required")
        if not self.scraper_run_id:
            raise ValueError("Scraper run ID is required")
        if self.content_size_bytes <= 0:
            raise ValueError("Content size must be positive")
    
    # ======================== BUSINESS LOGIC ========================
    
    @property
    def is_archived(self) -> bool:
        """Check if content is archived to S3."""
        return bool(self.s3_archive_path)
    
    def archive_to_s3(self, s3_path: str) -> None:
        """Mark content as archived to S3."""
        self.s3_archive_path = s3_path
    
    @property
    def content_size_mb(self) -> float:
        """Get content size in MB."""
        return self.content_size_bytes / (1024 * 1024)
    
    @property
    def age_hours(self) -> float:
        """Get snapshot age in hours."""
        return (datetime.utcnow() - self.snapshot_time).total_seconds() / 3600

# ======================== DOMAIN SERVICE OBJECTS ========================

@dataclass
class ChangeDetectionResult:
    """Result of change detection process."""
    
    changes_detected: List[ChangeEventDomain] = field(default_factory=list)
    entities_added: int = 0
    entities_modified: int = 0
    entities_removed: int = 0
    processing_time_ms: int = 0
    content_changed: bool = False
    
    @property
    def has_changes(self) -> bool:
        """Check if any changes were detected."""
        return len(self.changes_detected) > 0
    
    @property
    def has_critical_changes(self) -> bool:
        """Check if any critical changes were detected."""
        return any(change.is_critical for change in self.changes_detected)
    
    @property
    def total_changes(self) -> int:
        """Get total number of changes."""
        return len(self.changes_detected)
    
    def get_changes_by_risk(self, risk_level: RiskLevel) -> List[ChangeEventDomain]:
        """Get changes filtered by risk level."""
        return [change for change in self.changes_detected if change.risk_level == risk_level]

@dataclass
class ScrapingRequest:
    """Request to scrape a specific source."""
    
    source: DataSource
    force_update: bool = False
    timeout_seconds: int = 120
    requested_by: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid4()))
    
    def __post_init__(self):
        """Validate scraping request."""
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if self.timeout_seconds > 3600:  # 1 hour max
            raise ValueError("Timeout cannot exceed 1 hour")

# ======================== FACTORY FUNCTIONS ========================

def create_sanctioned_entity(
    uid: str,
    name: str, 
    entity_type: EntityType,
    source: DataSource,
    **kwargs
) -> SanctionedEntityDomain:
    """Factory function to create sanctioned entity with validation."""
    
    # Extract personal info for persons
    personal_info = None
    if entity_type == EntityType.PERSON:
        personal_info = PersonalInfo(
            first_name=kwargs.get('first_name'),
            last_name=kwargs.get('last_name'),
            date_of_birth=kwargs.get('date_of_birth'),
            place_of_birth=kwargs.get('place_of_birth'),
            nationality=kwargs.get('primary_nationality')
        )
    
    # Convert address data to Address objects
    address_objects = []
    raw_addresses = kwargs.get('addresses', [])
    for addr_str in raw_addresses:
        if isinstance(addr_str, str):
            # Parse simple address string
            parts = addr_str.split(', ')
            address = Address(
                street=parts[0] if len(parts) > 0 else None,
                city=parts[1] if len(parts) > 1 else None,
                country=parts[-1] if len(parts) > 2 else None
            )
            address_objects.append(address)
    
    return SanctionedEntityDomain(
        uid=uid,
        name=name,
        entity_type=entity_type,
        source=source,
        programs=kwargs.get('programs', []),
        aliases=kwargs.get('aliases', []),
        addresses=address_objects,
        personal_info=personal_info,
        nationalities=kwargs.get('nationalities', []),
        remarks=kwargs.get('remarks'),
        content_hash=kwargs.get('content_hash')
    )

def create_change_event(
    entity_uid: str,
    entity_name: str,
    change_type: ChangeType,
    field_changes: List[FieldChange],
    source: DataSource,
    scraper_run_id: str
) -> ChangeEventDomain:
    """Factory function to create change event with risk assessment."""
    
    from src.core.enums import FieldImportance
    
    # Assess risk level based on changed fields
    risk_level = RiskLevel.LOW
    
    for field_change in field_changes:
        field_importance = FieldImportance.get_field_importance(field_change.field_name)
        
        if field_importance == FieldImportance.CRITICAL:
            risk_level = RiskLevel.CRITICAL
            break
        elif field_importance == FieldImportance.HIGH and risk_level != RiskLevel.CRITICAL:
            risk_level = RiskLevel.HIGH
        elif field_importance == FieldImportance.MEDIUM and risk_level == RiskLevel.LOW:
            risk_level = RiskLevel.MEDIUM
    
    # Special cases
    if change_type == ChangeType.REMOVED:
        risk_level = RiskLevel.CRITICAL  # Removals always critical
    elif change_type == ChangeType.ADDED:
        risk_level = max(risk_level, RiskLevel.MEDIUM)  # Additions at least medium
    
    return ChangeEventDomain(
        entity_uid=entity_uid,
        entity_name=entity_name,
        change_type=change_type,
        risk_level=risk_level,
        field_changes=field_changes,
        source=source,
        scraper_run_id=scraper_run_id
    )

# ======================== EXPORTS ========================

__all__ = [
    # Value Objects
    'Address',
    'PersonalInfo', 
    'FieldChange',
    
    # Core Entities
    'SanctionedEntityDomain',
    'ChangeEventDomain',
    'ScraperRunDomain',
    'ContentSnapshotDomain',
    
    # Service Objects
    'ChangeDetectionResult',
    'ScrapingRequest',
    
    # Factory Functions
    'create_sanctioned_entity',
    'create_change_event'
]