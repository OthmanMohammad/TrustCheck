"""
TrustCheck Domain Enums.

Centralized enum definitions for type safety across the application.
"""

from enum import Enum


class DataSource(str, Enum):
    """Sanctions data source identifiers."""

    OFAC_SDN = "OFAC_SDN"
    OFAC_CONSOLIDATED = "OFAC_CONSOLIDATED"
    UN = "UN"
    EU = "EU"
    UK = "UK"

    @property
    def display_name(self) -> str:
        """Human-readable name for the data source."""
        names = {
            "OFAC_SDN": "OFAC SDN List",
            "OFAC_CONSOLIDATED": "OFAC Consolidated List",
            "UN": "UN Consolidated Sanctions",
            "EU": "EU Financial Sanctions",
            "UK": "UK Sanctions List",
        }
        return names.get(self.value, self.value)


class EntityType(str, Enum):
    """Types of sanctioned entities."""

    INDIVIDUAL = "INDIVIDUAL"
    ORGANIZATION = "ORGANIZATION"
    VESSEL = "VESSEL"
    AIRCRAFT = "AIRCRAFT"
    UNKNOWN = "UNKNOWN"


class NameType(str, Enum):
    """Types of entity names."""

    PRIMARY = "PRIMARY"
    ALIAS = "ALIAS"
    AKA = "AKA"  # Also Known As
    FKA = "FKA"  # Formerly Known As
    MAIDEN = "MAIDEN"
    NICKNAME = "NICKNAME"


class IdentifierType(str, Enum):
    """Types of entity identifiers."""

    PASSPORT = "PASSPORT"
    NATIONAL_ID = "NATIONAL_ID"
    TAX_ID = "TAX_ID"
    DRIVER_LICENSE = "DRIVER_LICENSE"
    SSN = "SSN"
    REGISTRATION_NUMBER = "REGISTRATION_NUMBER"
    IMO = "IMO"  # International Maritime Organization number
    MMSI = "MMSI"  # Maritime Mobile Service Identity
    CALL_SIGN = "CALL_SIGN"
    AIRCRAFT_TAIL = "AIRCRAFT_TAIL"
    BIC = "BIC"  # Bank Identifier Code
    SWIFT = "SWIFT"
    LEI = "LEI"  # Legal Entity Identifier
    OTHER = "OTHER"


class ChangeType(str, Enum):
    """Types of changes detected in sanctions data."""

    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    REMOVED = "REMOVED"
    REACTIVATED = "REACTIVATED"


class EventType(str, Enum):
    """Types of system events for audit logging."""

    # Entity events
    ENTITY_ADDED = "ENTITY_ADDED"
    ENTITY_MODIFIED = "ENTITY_MODIFIED"
    ENTITY_REMOVED = "ENTITY_REMOVED"
    ENTITY_REACTIVATED = "ENTITY_REACTIVATED"

    # Scraper events
    SCRAPE_STARTED = "SCRAPE_STARTED"
    SCRAPE_COMPLETED = "SCRAPE_COMPLETED"
    SCRAPE_FAILED = "SCRAPE_FAILED"

    # Screening events
    SCREENING_PERFORMED = "SCREENING_PERFORMED"
    BATCH_SCREENING_STARTED = "BATCH_SCREENING_STARTED"
    BATCH_SCREENING_COMPLETED = "BATCH_SCREENING_COMPLETED"


class ScraperStatus(str, Enum):
    """Status of a scraper run."""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MatchType(str, Enum):
    """Types of name matches in screening."""

    EXACT = "EXACT"
    NORMALIZED = "NORMALIZED"
    PHONETIC = "PHONETIC"
    FUZZY = "FUZZY"
    PARTIAL = "PARTIAL"
    VARIANT = "VARIANT"  # Nickname/variant match (Bob/Robert)
    NONE = "NONE"  # Informational field, not a match


class Script(str, Enum):
    """Writing scripts for names."""

    LATIN = "LATIN"
    CYRILLIC = "CYRILLIC"
    ARABIC = "ARABIC"
    CJK = "CJK"  # Chinese, Japanese, Korean
    HEBREW = "HEBREW"
    GREEK = "GREEK"
    OTHER = "OTHER"
