"""
TrustCheck Domain Layer.

Contains domain models, enums, and exceptions.
"""

from trustcheck.domain.enums import (
    ChangeType,
    DataSource,
    EntityType,
    EventType,
    IdentifierType,
    MatchType,
    NameType,
    ScraperStatus,
    Script,
)
from trustcheck.domain.exceptions import (
    ConfigurationError,
    DatabaseError,
    DataSourceError,
    EntityNotFoundError,
    ScraperError,
    ScreeningError,
    TrustCheckError,
    ValidationError,
)
from trustcheck.domain.models import (
    Address,
    ChangeEvent,
    DashboardStats,
    Event,
    Identifier,
    MatchedField,
    Name,
    SanctionedEntity,
    ScraperRun,
    ScreeningMatch,
    ScreeningRequest,
    ScreeningResult,
    SourceRecord,
)

__all__ = [
    # Enums
    "ChangeType",
    "DataSource",
    "EntityType",
    "EventType",
    "IdentifierType",
    "MatchType",
    "NameType",
    "ScraperStatus",
    "Script",
    # Models
    "Address",
    "ChangeEvent",
    "DashboardStats",
    "Event",
    "Identifier",
    "MatchedField",
    "Name",
    "SanctionedEntity",
    "ScraperRun",
    "ScreeningMatch",
    "ScreeningRequest",
    "ScreeningResult",
    "SourceRecord",
    # Exceptions
    "ConfigurationError",
    "DatabaseError",
    "DataSourceError",
    "EntityNotFoundError",
    "ScraperError",
    "ScreeningError",
    "TrustCheckError",
    "ValidationError",
]
