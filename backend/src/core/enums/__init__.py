"""
Core Enums Package

Centralized enumerations for type safety and consistency.
"""

from enum import Enum, IntEnum
from typing import List


# ======================== ENTITY ENUMS ========================

class EntityType(str, Enum):
    """Types of sanctioned entities."""
    PERSON = "PERSON"
    COMPANY = "COMPANY"
    VESSEL = "VESSEL"
    AIRCRAFT = "AIRCRAFT"
    OTHER = "OTHER"

    @classmethod
    def list_values(cls) -> List[str]:
        """Get all enum values as list."""
        return [item.value for item in cls]


class EntityStatus(str, Enum):
    """Status of entities in the system."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"
    PENDING_REVIEW = "PENDING_REVIEW"


# ======================== CHANGE DETECTION ENUMS ========================

class ChangeType(str, Enum):
    """Types of changes detected in entities."""
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    REMOVED = "REMOVED"

    def __str__(self) -> str:
        return self.value


class RiskLevel(str, Enum):
    """Risk levels for changes and entities."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def priority_score(self) -> int:
        """Numeric priority for sorting."""
        scores = {
            self.CRITICAL: 4,
            self.HIGH: 3,
            self.MEDIUM: 2,
            self.LOW: 1
        }
        return scores[self]


class FieldChangeType(str, Enum):
    """Types of field-level changes."""
    FIELD_ADDED = "FIELD_ADDED"
    FIELD_REMOVED = "FIELD_REMOVED" 
    FIELD_MODIFIED = "FIELD_MODIFIED"
    LIST_ITEM_ADDED = "LIST_ITEM_ADDED"
    LIST_ITEM_REMOVED = "LIST_ITEM_REMOVED"


# ======================== SCRAPER ENUMS ========================

class ScraperStatus(str, Enum):
    """Status of scraper runs."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    PARTIAL = "PARTIAL"

    @property
    def is_final_state(self) -> bool:
        """Check if status represents a final state."""
        return self in [self.SUCCESS, self.FAILED, self.SKIPPED, self.PARTIAL]


class ScraperTier(str, Enum):
    """Scraper tiers by importance."""
    TIER1 = "TIER1"  # Critical, daily
    TIER2 = "TIER2"  # Important, weekly  
    TIER3 = "TIER3"  # Regional, monthly

    @property
    def update_frequency_hours(self) -> int:
        """Recommended update frequency in hours."""
        frequencies = {
            self.TIER1: 6,   # Every 6 hours
            self.TIER2: 24,  # Daily
            self.TIER3: 168  # Weekly
        }
        return frequencies[self]


class Region(str, Enum):
    """Geographic regions for scrapers."""
    GLOBAL = "GLOBAL"
    US = "US"
    EUROPE = "EUROPE"
    ASIA_PACIFIC = "ASIA_PACIFIC"
    AMERICAS = "AMERICAS"
    AFRICA_MIDDLE_EAST = "AFRICA_MIDDLE_EAST"


class DataFormat(str, Enum):
    """Data formats for scraper sources."""
    XML = "XML"
    JSON = "JSON"
    CSV = "CSV"
    EXCEL = "EXCEL"
    PDF = "PDF"
    HTML = "HTML"


# ======================== SANCTIONS SOURCE ENUMS ========================

class SanctionsSource(str, Enum):
    """Official sanctions sources."""
    US_OFAC = "US_OFAC"
    UN_CONSOLIDATED = "UN_CONSOLIDATED"
    EU_CONSOLIDATED = "EU_CONSOLIDATED" 
    UK_HMT = "UK_HMT"
    CANADA_OSFI = "CANADA_OSFI"
    AUSTRALIA_DFAT = "AUSTRALIA_DFAT"
    INTERPOL = "INTERPOL"

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        names = {
            self.US_OFAC: "US Treasury OFAC",
            self.UN_CONSOLIDATED: "UN Consolidated List",
            self.EU_CONSOLIDATED: "EU Consolidated List",
            self.UK_HMT: "UK HM Treasury",
            self.CANADA_OSFI: "Canada OSFI",
            self.AUSTRALIA_DFAT: "Australia DFAT",
            self.INTERPOL: "INTERPOL"
        }
        return names[self]

    @property
    def official_url(self) -> str:
        """Official source URL."""
        urls = {
            self.US_OFAC: "https://www.treasury.gov/ofac/downloads/sdn.xml",
            self.UN_CONSOLIDATED: "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
            self.EU_CONSOLIDATED: "https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList/content",
            self.UK_HMT: "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1178224/UK_Sanctions_List.xlsx"
        }
        return urls.get(self, "")


# ======================== NOTIFICATION ENUMS ========================

class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"
    SLACK = "SLACK"
    TEAMS = "TEAMS"
    SMS = "SMS"
    LOG = "LOG"


class NotificationPriority(str, Enum):
    """Notification priorities."""
    IMMEDIATE = "IMMEDIATE"     # Send right away
    BATCH_HIGH = "BATCH_HIGH"   # Batch within 30 minutes
    BATCH_DAILY = "BATCH_DAILY" # Daily digest
    DISABLED = "DISABLED"       # Don't send


# ======================== FIELD MAPPINGS ========================

class CriticalFields(str, Enum):
    """Fields considered critical for compliance."""
    NAME = "name"
    ENTITY_TYPE = "entity_type"
    PROGRAMS = "programs"
    UID = "uid"


class HighRiskFields(str, Enum):
    """Fields considered high-risk for compliance."""
    ADDRESSES = "addresses"
    ALIASES = "aliases"
    NATIONALITIES = "nationalities"
    DATES_OF_BIRTH = "dates_of_birth"


class MediumRiskFields(str, Enum):
    """Fields considered medium-risk for compliance."""
    PLACES_OF_BIRTH = "places_of_birth"
    REMARKS = "remarks"
    SANCTIONS_PROGRAMS = "sanctions_programs"


# ======================== API ENUMS ========================

class APIResponseStatus(str, Enum):
    """API response status codes."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PARTIAL = "partial"


class SortOrder(str, Enum):
    """Sort order for API responses."""
    ASC = "asc"
    DESC = "desc"


# ======================== UTILITY FUNCTIONS ========================

def get_all_entity_types() -> List[str]:
    """Get all entity types as strings."""
    return EntityType.list_values()


def get_critical_field_names() -> List[str]:
    """Get all critical field names."""
    return [field.value for field in CriticalFields]


def get_high_risk_field_names() -> List[str]:
    """Get all high-risk field names."""
    return [field.value for field in HighRiskFields]


def is_critical_field(field_name: str) -> bool:
    """Check if field is considered critical."""
    return field_name in get_critical_field_names()


def get_risk_level_from_fields(changed_fields: List[str]) -> RiskLevel:
    """Determine risk level based on changed fields."""
    critical_fields = get_critical_field_names()
    high_risk_fields = get_high_risk_field_names()
    
    if any(field in critical_fields for field in changed_fields):
        return RiskLevel.CRITICAL
    elif any(field in high_risk_fields for field in changed_fields):
        return RiskLevel.HIGH
    elif len(changed_fields) >= 3:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


# ======================== EXPORTS ========================

__all__ = [
    # Entity enums
    "EntityType",
    "EntityStatus", 
    
    # Change detection enums
    "ChangeType",
    "RiskLevel",
    "FieldChangeType",
    
    # Scraper enums
    "ScraperStatus",
    "ScraperTier", 
    "Region",
    "DataFormat",
    
    # Source enums
    "SanctionsSource",
    
    # Notification enums
    "NotificationChannel",
    "NotificationPriority",
    
    # Field enums
    "CriticalFields",
    "HighRiskFields",
    "MediumRiskFields",
    
    # API enums
    "APIResponseStatus",
    "SortOrder",
    
    # Utility functions
    "get_all_entity_types",
    "get_critical_field_names", 
    "get_high_risk_field_names",
    "is_critical_field",
    "get_risk_level_from_fields"
]