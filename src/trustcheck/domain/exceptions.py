"""
TrustCheck Domain Exceptions.

Custom exception hierarchy for the application.
"""


class TrustCheckError(Exception):
    """Base exception for all TrustCheck errors."""

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code or "TRUSTCHECK_ERROR"
        super().__init__(self.message)


class ValidationError(TrustCheckError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR")


class EntityNotFoundError(TrustCheckError):
    """Raised when an entity is not found."""

    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id
        super().__init__(f"Entity not found: {entity_id}", code="ENTITY_NOT_FOUND")


class ScraperError(TrustCheckError):
    """Raised when a scraper encounters an error."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"Scraper error for {source}: {message}", code="SCRAPER_ERROR")


class DataSourceError(TrustCheckError):
    """Raised when there's an issue with a data source."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(
            f"Data source error for {source}: {message}", code="DATA_SOURCE_ERROR"
        )


class DatabaseError(TrustCheckError):
    """Raised when a database operation fails."""

    def __init__(self, message: str, operation: str | None = None) -> None:
        self.operation = operation
        super().__init__(message, code="DATABASE_ERROR")


class ScreeningError(TrustCheckError):
    """Raised when screening operation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="SCREENING_ERROR")


class ConfigurationError(TrustCheckError):
    """Raised when there's a configuration issue."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="CONFIGURATION_ERROR")
