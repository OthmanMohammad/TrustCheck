"""
TrustCheck Database Layer.

Database connection, models, and repositories.
"""

from trustcheck.database.connection import (
    check_db_connection,
    close_db,
    create_search_indexes,
    get_engine,
    get_session,
    get_session_context,
    get_session_factory,
    init_db,
)
from trustcheck.database.models import (
    AddressModel,
    Base,
    ChangeEventModel,
    EntityModel,
    EventModel,
    IdentifierModel,
    NameModel,
    ScraperRunModel,
    ScreeningResultModel,
    SourceRecordModel,
)
from trustcheck.database.repositories import (
    ChangeEventRepository,
    DashboardRepository,
    EntityRepository,
    EventRepository,
    ScraperRunRepository,
    SourceRecordRepository,
)

__all__ = [
    # Connection
    "check_db_connection",
    "close_db",
    "create_search_indexes",
    "get_engine",
    "get_session",
    "get_session_context",
    "get_session_factory",
    "init_db",
    # Models
    "AddressModel",
    "Base",
    "ChangeEventModel",
    "EntityModel",
    "EventModel",
    "IdentifierModel",
    "NameModel",
    "ScraperRunModel",
    "ScreeningResultModel",
    "SourceRecordModel",
    # Repositories
    "ChangeEventRepository",
    "DashboardRepository",
    "EntityRepository",
    "EventRepository",
    "ScraperRunRepository",
    "SourceRecordRepository",
]
