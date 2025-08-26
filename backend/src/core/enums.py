"""
Centralized Enums for TrustCheck

All application enums in one place for:
- Consistency across the application
- Easy maintenance and updates  
- Type safety and IDE support
- Clear documentation
"""

from enum import Enum, IntEnum
from typing import List

# ======================== APPLICATION ENUMS ========================

class Environment(str, Enum):
    """Application deployment environments."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging" 
    PRODUCTION = "production"

class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

# ======================== ENTITY ENUMS ========================

class EntityType(str, Enum):
    """Types of sanctioned entities."""
    PERSON = "PERSON"
    COMPANY = "COMPANY"
    VESSEL = "VESSEL"
    AIRCRAFT = "AIRCRAFT"
    OTHER = "OTHER"
    
    @classmethod
    def get_description(cls, entity_type: str) -> str:
        """Get human-readable description."""
        descriptions = {
            cls.PERSON: "Individual person",
            cls.COMPANY: "Business entity or organization", 
            cls.VESSEL: "Maritime vessel or ship",
            cls.AIRCRAFT: "Aircraft or aviation asset",
            cls.OTHER: "Other type of sanctioned entity"
        }
        return descriptions.get(entity_type, "Unknown entity type")

class SanctionsProgram(str, Enum):
    """Common sanctions programs."""
    # US OFAC Programs
    SDGT = "SDGT"  # Specially Designated Global Terrorists
    TERRORISM = "TERRORISM"
    PROLIFERATION = "PROLIFERATION" 
    NARCOTICS = "NARCOTICS"
    CYBER = "CYBER"
    MAGNITSKY = "MAGNITSKY"
    
    # Regional Programs  
    UKRAINE = "UKRAINE"
    IRAN = "IRAN"
    NORTH_KOREA = "NORTH_KOREA"
    RUSSIA = "RUSSIA"
    SYRIA = "SYRIA"
    VENEZUELA = "VENEZUELA"
    
    # Other Programs
    HUMAN_RIGHTS = "HUMAN_RIGHTS"
    CORRUPTION = "CORRUPTION"
    MONEY_LAUNDERING = "MONEY_LAUNDERING"

# ======================== CHANGE DETECTION ENUMS ========================

class ChangeType(str, Enum):
    """Types of changes detected in entities."""
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    REMOVED = "REMOVED"
    
    def get_description(self) -> str:
        """Get human-readable description."""
        return {
            self.ADDED: "Entity added to sanctions list",
            self.MODIFIED: "Entity information updated",
            self.REMOVED: "Entity removed from sanctions list"
        }[self]
    
    def get_action_verb(self) -> str:
        """Get action verb for notifications."""
        return {
            self.ADDED: "added to",
            self.MODIFIED: "modified in", 
            self.REMOVED: "removed from"
        }[self]

class RiskLevel(str, Enum):
    """Risk levels for changes and notifications."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH" 
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    
    def get_priority_score(self) -> int:
        """Get numeric priority score (higher = more urgent)."""
        return {
            self.CRITICAL: 4,
            self.HIGH: 3,
            self.MEDIUM: 2, 
            self.LOW: 1
        }[self]
    
    def get_notification_delay_minutes(self) -> int:
        """Get suggested notification delay in minutes."""
        return {
            self.CRITICAL: 0,      # Immediate
            self.HIGH: 30,         # 30 minutes
            self.MEDIUM: 240,      # 4 hours
            self.LOW: 1440         # 24 hours (daily digest)
        }[self]

class FieldImportance(str, Enum):
    """Importance levels for entity fields."""
    CRITICAL = "CRITICAL"   # name, programs, entity_type
    HIGH = "HIGH"          # addresses, aliases, nationalities  
    MEDIUM = "MEDIUM"      # dates_of_birth, places_of_birth
    LOW = "LOW"           # remarks, minor details
    
    @classmethod
    def get_field_importance(cls, field_name: str) -> 'FieldImportance':
        """Get importance level for a field."""
        field_mapping = {
            # Critical fields
            'name': cls.CRITICAL,
            'programs': cls.CRITICAL, 
            'entity_type': cls.CRITICAL,
            
            # High importance
            'addresses': cls.HIGH,
            'aliases': cls.HIGH,
            'nationalities': cls.HIGH,
            
            # Medium importance
            'dates_of_birth': cls.MEDIUM,
            'places_of_birth': cls.MEDIUM,
            
            # Low importance  
            'remarks': cls.LOW
        }
        
        return field_mapping.get(field_name, cls.LOW)

# ======================== SCRAPER ENUMS ========================

class DataSource(str, Enum):
    """Data sources for sanctions data."""
    OFAC = "OFAC"                    # US Treasury OFAC
    UN = "UN"                        # United Nations
    EU = "EU"                        # European Union
    UK_HMT = "UK_HMT"               # UK HM Treasury
    INTERPOL = "INTERPOL"           # Interpol
    
    def get_full_name(self) -> str:
        """Get full organization name."""
        return {
            self.OFAC: "US Treasury Office of Foreign Assets Control",
            self.UN: "United Nations Security Council",
            self.EU: "European Union",
            self.UK_HMT: "UK HM Treasury",
            self.INTERPOL: "International Criminal Police Organization"
        }[self]
    
    def get_update_frequency_hours(self) -> int:
        """Get typical update frequency in hours."""
        return {
            self.OFAC: 6,      # Every 6 hours
            self.UN: 24,       # Daily
            self.EU: 24,       # Daily
            self.UK_HMT: 24,   # Daily
            self.INTERPOL: 168  # Weekly
        }[self]

class ScrapingStatus(str, Enum):
    """Status of scraping operations."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    RUNNING = "RUNNING"
    SKIPPED = "SKIPPED"
    
    def is_terminal(self) -> bool:
        """Check if status is terminal (completed)."""
        return self in [self.SUCCESS, self.FAILED, self.PARTIAL, self.SKIPPED]
    
    def is_successful(self) -> bool:
        """Check if status indicates success."""
        return self in [self.SUCCESS, self.PARTIAL, self.SKIPPED]

class ScrapingTier(str, Enum):
    """Scraper priority tiers."""
    TIER1 = "tier1"    # Critical, frequent updates (OFAC, UN)
    TIER2 = "tier2"    # Important, regular updates (EU, UK)  
    TIER3 = "tier3"    # Lower priority, less frequent
    
    def get_max_runtime_minutes(self) -> int:
        """Get maximum allowed runtime."""
        return {
            self.TIER1: 30,   # 30 minutes
            self.TIER2: 60,   # 1 hour
            self.TIER3: 120   # 2 hours
        }[self]

class DataFormat(str, Enum):
    """Data formats for different sources."""
    XML = "XML"
    JSON = "JSON"
    CSV = "CSV"
    EXCEL = "EXCEL"
    PDF = "PDF"
    HTML = "HTML"

# ======================== API ENUMS ========================

class APIStatus(str, Enum):
    """API response status indicators."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class HTTPMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"

# ======================== NOTIFICATION ENUMS ========================

class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    SMS = "sms"
    LOG = "log"
    
    def requires_config(self) -> bool:
        """Check if channel requires configuration."""
        return self != self.LOG

class NotificationPriority(str, Enum):
    """Notification priority levels."""
    IMMEDIATE = "immediate"      # Send right away
    BATCH_HIGH = "batch_high"    # Batch within 30 minutes
    BATCH_LOW = "batch_low"      # Daily digest
    
    def get_delay_minutes(self) -> int:
        """Get notification delay in minutes."""
        return {
            self.IMMEDIATE: 0,
            self.BATCH_HIGH: 30,
            self.BATCH_LOW: 1440
        }[self]

# ======================== GEOGRAPHIC ENUMS ========================

class Region(str, Enum):
    """Geographic regions for scrapers."""
    US = "us"
    EUROPE = "europe" 
    ASIA_PACIFIC = "asia_pacific"
    INTERNATIONAL = "international"
    AMERICAS = "americas"
    AFRICA_MIDDLE_EAST = "africa_middle_east"
    
    def get_display_name(self) -> str:
        """Get display name for UI."""
        return {
            self.US: "United States",
            self.EUROPE: "Europe",
            self.ASIA_PACIFIC: "Asia Pacific", 
            self.INTERNATIONAL: "International",
            self.AMERICAS: "Americas",
            self.AFRICA_MIDDLE_EAST: "Africa & Middle East"
        }[self]

# ======================== DATABASE ENUMS ========================

class DatabaseOperation(str, Enum):
    """Database operation types for logging."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    BULK_INSERT = "bulk_insert"
    MIGRATION = "migration"
    BACKUP = "backup"

# ======================== UTILITY FUNCTIONS ========================

def get_all_enum_values(enum_class: type) -> List[str]:
    """Get all values from an enum class."""
    return [item.value for item in enum_class]

def validate_enum_value(enum_class: type, value: str) -> bool:
    """Validate if a value is valid for an enum."""
    try:
        enum_class(value)
        return True
    except ValueError:
        return False

def get_enum_choices_description(enum_class: type) -> str:
    """Get formatted string of enum choices for error messages."""
    choices = get_all_enum_values(enum_class)
    return f"Valid choices: {', '.join(choices)}"

# ======================== EXPORTS ========================

__all__ = [
    # Application
    'Environment',
    'LogLevel',
    
    # Entities
    'EntityType', 
    'SanctionsProgram',
    
    # Change Detection
    'ChangeType',
    'RiskLevel', 
    'FieldImportance',
    
    # Scraping
    'DataSource',
    'ScrapingStatus',
    'ScrapingTier',
    'DataFormat',
    
    # API
    'APIStatus',
    'HTTPMethod',
    
    # Notifications
    'NotificationChannel',
    'NotificationPriority',
    
    # Geography
    'Region',
    
    # Database
    'DatabaseOperation',
    
    # Utilities
    'get_all_enum_values',
    'validate_enum_value', 
    'get_enum_choices_description'
]