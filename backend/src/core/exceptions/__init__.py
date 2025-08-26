"""
TrustCheck Exception System

Production-grade exception hierarchy with proper error codes,
logging integration, and API error responses.
"""

import logging
from typing import Any, Dict, Optional, List
from enum import Enum
from datetime import datetime

from src.utils.logging import get_logger


# ======================== ERROR CODES ========================

class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""
    
    # General errors (1000-1999)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    
    # Database errors (2000-2999)
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_INTEGRITY_ERROR = "DATABASE_INTEGRITY_ERROR"
    DATABASE_OPERATION_ERROR = "DATABASE_OPERATION_ERROR"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    ENTITY_ALREADY_EXISTS = "ENTITY_ALREADY_EXISTS"
    
    # Scraping errors (3000-3999)
    SCRAPER_NOT_FOUND = "SCRAPER_NOT_FOUND"
    SCRAPER_EXECUTION_ERROR = "SCRAPER_EXECUTION_ERROR"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    PARSING_ERROR = "PARSING_ERROR"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    INVALID_SOURCE_DATA = "INVALID_SOURCE_DATA"
    
    # Change detection errors (4000-4999)
    CHANGE_DETECTION_ERROR = "CHANGE_DETECTION_ERROR"
    NOTIFICATION_ERROR = "NOTIFICATION_ERROR"
    CONTENT_HASH_ERROR = "CONTENT_HASH_ERROR"
    
    # External service errors (5000-5999)
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"


# ======================== BASE EXCEPTION ========================

class TrustCheckError(Exception):
    """
    Base exception for all TrustCheck errors.
    
    Features:
    - Structured error information
    - Automatic logging
    - API serialization support
    - Error tracking integration
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message)
        
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.user_message = user_message or self._generate_user_message()
        self.timestamp = datetime.utcnow()
        self.error_id = self._generate_error_id()
        
        # Auto-logging
        self.logger = get_logger(f"exception.{self.__class__.__name__.lower()}")
        self._log_error()
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly error message."""
        user_messages = {
            ErrorCode.VALIDATION_ERROR: "The provided data is invalid. Please check your input.",
            ErrorCode.ENTITY_NOT_FOUND: "The requested entity was not found.",
            ErrorCode.DATABASE_CONNECTION_ERROR: "Service temporarily unavailable. Please try again later.",
            ErrorCode.SCRAPER_EXECUTION_ERROR: "Unable to retrieve the latest data. Please try again.",
            ErrorCode.RATE_LIMIT_ERROR: "Too many requests. Please wait before trying again.",
        }
        return user_messages.get(self.error_code, "An unexpected error occurred. Please try again.")
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID for tracking."""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _log_error(self) -> None:
        """Log the error with appropriate level."""
        log_data = {
            "error_id": self.error_id,
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }
        
        if self.cause:
            log_data["cause"] = str(self.cause)
        
        # Log at appropriate level
        if self.error_code in [ErrorCode.INTERNAL_ERROR, ErrorCode.DATABASE_CONNECTION_ERROR]:
            self.logger.error(f"Critical error: {self.message}", extra=log_data, exc_info=self.cause)
        elif self.error_code in [ErrorCode.VALIDATION_ERROR, ErrorCode.ENTITY_NOT_FOUND]:
            self.logger.info(f"User error: {self.message}", extra=log_data)
        else:
            self.logger.warning(f"Application error: {self.message}", extra=log_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.user_message,
                "details": self.details,
                "error_id": self.error_id,
                "timestamp": self.timestamp.isoformat()
            }
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code.value}] {self.message}"
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message='{self.message}', "
            f"error_code={self.error_code.value}, "
            f"error_id={self.error_id})"
        )


# ======================== VALIDATION EXCEPTIONS ========================

class ValidationError(TrustCheckError):
    """Validation errors for user input."""
    
    def __init__(
        self,
        message: str,
        field_errors: Optional[Dict[str, List[str]]] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details={"field_errors": field_errors or {}},
            **kwargs
        )
        self.field_errors = field_errors or {}


class EntityValidationError(ValidationError):
    """Entity-specific validation errors."""
    
    def __init__(self, entity_type: str, field_errors: Dict[str, List[str]], **kwargs):
        message = f"Validation failed for {entity_type}"
        super().__init__(
            message=message,
            field_errors=field_errors,
            details={"entity_type": entity_type, "field_errors": field_errors},
            **kwargs
        )


# ======================== DATABASE EXCEPTIONS ========================

class DatabaseError(TrustCheckError):
    """Base database error."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_OPERATION_ERROR,
            **kwargs
        )


class DatabaseConnectionError(DatabaseError):
    """Database connection errors."""
    
    def __init__(self, message: str = "Database connection failed", **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_CONNECTION_ERROR,
            **kwargs
        )


class DatabaseIntegrityError(DatabaseError):
    """Database integrity constraint violations."""
    
    def __init__(self, message: str, constraint: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_INTEGRITY_ERROR,
            details={"constraint": constraint},
            **kwargs
        )


class EntityNotFoundError(DatabaseError):
    """Entity not found in database."""
    
    def __init__(self, entity_type: str, entity_id: Any, **kwargs):
        message = f"{entity_type} with ID '{entity_id}' not found"
        super().__init__(
            message=message,
            error_code=ErrorCode.ENTITY_NOT_FOUND,
            details={"entity_type": entity_type, "entity_id": str(entity_id)},
            **kwargs
        )


class EntityAlreadyExistsError(DatabaseError):
    """Entity already exists in database."""
    
    def __init__(self, entity_type: str, identifier: str, **kwargs):
        message = f"{entity_type} with identifier '{identifier}' already exists"
        super().__init__(
            message=message,
            error_code=ErrorCode.ENTITY_ALREADY_EXISTS,
            details={"entity_type": entity_type, "identifier": identifier},
            **kwargs
        )


# ======================== SCRAPING EXCEPTIONS ========================

class ScrapingError(TrustCheckError):
    """Base scraping error."""
    
    def __init__(self, message: str, source: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.SCRAPER_EXECUTION_ERROR,
            details={"source": source},
            **kwargs
        )


class ScraperNotFoundError(ScrapingError):
    """Scraper not found or not registered."""
    
    def __init__(self, scraper_name: str, available_scrapers: Optional[List[str]] = None, **kwargs):
        message = f"Scraper '{scraper_name}' not found"
        super().__init__(
            message=message,
            error_code=ErrorCode.SCRAPER_NOT_FOUND,
            details={"scraper_name": scraper_name, "available_scrapers": available_scrapers or []},
            **kwargs
        )


class DownloadError(ScrapingError):
    """Content download errors."""
    
    def __init__(self, url: str, status_code: Optional[int] = None, **kwargs):
        message = f"Failed to download content from {url}"
        super().__init__(
            message=message,
            error_code=ErrorCode.DOWNLOAD_ERROR,
            details={"url": url, "status_code": status_code},
            **kwargs
        )


class ParsingError(ScrapingError):
    """Data parsing errors."""
    
    def __init__(self, source: str, data_format: str, line_number: Optional[int] = None, **kwargs):
        message = f"Failed to parse {data_format} data from {source}"
        super().__init__(
            message=message,
            error_code=ErrorCode.PARSING_ERROR,
            details={"source": source, "data_format": data_format, "line_number": line_number},
            **kwargs
        )


class SourceUnavailableError(ScrapingError):
    """External source unavailable."""
    
    def __init__(self, source: str, retry_after: Optional[int] = None, **kwargs):
        message = f"Source {source} is currently unavailable"
        super().__init__(
            message=message,
            error_code=ErrorCode.SOURCE_UNAVAILABLE,
            details={"source": source, "retry_after_seconds": retry_after},
            **kwargs
        )


class InvalidSourceDataError(ScrapingError):
    """Source data is invalid or corrupted."""
    
    def __init__(self, source: str, reason: str, **kwargs):
        message = f"Invalid data from {source}: {reason}"
        super().__init__(
            message=message,
            error_code=ErrorCode.INVALID_SOURCE_DATA,
            details={"source": source, "reason": reason},
            **kwargs
        )


# ======================== CHANGE DETECTION EXCEPTIONS ========================

class ChangeDetectionError(TrustCheckError):
    """Change detection errors."""
    
    def __init__(self, message: str, source: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.CHANGE_DETECTION_ERROR,
            details={"source": source},
            **kwargs
        )


class NotificationError(TrustCheckError):
    """Notification delivery errors."""
    
    def __init__(self, message: str, channel: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.NOTIFICATION_ERROR,
            details={"channel": channel},
            **kwargs
        )


class ContentHashError(ChangeDetectionError):
    """Content hash calculation or comparison errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.CONTENT_HASH_ERROR,
            **kwargs
        )


# ======================== EXTERNAL SERVICE EXCEPTIONS ========================

class ExternalServiceError(TrustCheckError):
    """External service integration errors."""
    
    def __init__(self, service: str, message: str, **kwargs):
        super().__init__(
            message=f"External service error ({service}): {message}",
            error_code=ErrorCode.EXTERNAL_API_ERROR,
            details={"service": service},
            **kwargs
        )


class NetworkError(ExternalServiceError):
    """Network connectivity errors."""
    
    def __init__(self, url: str, message: str = "Network connection failed", **kwargs):
        super().__init__(
            service="network",
            message=f"Network error accessing {url}: {message}",
            error_code=ErrorCode.NETWORK_ERROR,
            details={"url": url},
            **kwargs
        )


class TimeoutError(ExternalServiceError):
    """Request timeout errors."""
    
    def __init__(self, operation: str, timeout_seconds: int, **kwargs):
        super().__init__(
            service="timeout",
            message=f"Operation '{operation}' timed out after {timeout_seconds} seconds",
            error_code=ErrorCode.TIMEOUT_ERROR,
            details={"operation": operation, "timeout_seconds": timeout_seconds},
            **kwargs
        )


# ======================== AUTHENTICATION/AUTHORIZATION ========================

class AuthenticationError(TrustCheckError):
    """Authentication errors."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            user_message="Authentication failed. Please check your credentials.",
            **kwargs
        )


class AuthorizationError(TrustCheckError):
    """Authorization errors."""
    
    def __init__(self, resource: str, action: str, **kwargs):
        message = f"Access denied for {action} on {resource}"
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHORIZATION_ERROR,
            details={"resource": resource, "action": action},
            user_message="You don't have permission to perform this action.",
            **kwargs
        )


class RateLimitError(TrustCheckError):
    """Rate limiting errors."""
    
    def __init__(self, limit: int, window_seconds: int, retry_after: int, **kwargs):
        message = f"Rate limit exceeded: {limit} requests per {window_seconds} seconds"
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_ERROR,
            details={
                "limit": limit,
                "window_seconds": window_seconds,
                "retry_after_seconds": retry_after
            },
            user_message=f"Rate limit exceeded. Please wait {retry_after} seconds before trying again.",
            **kwargs
        )


# ======================== UTILITY FUNCTIONS ========================

def handle_exception(exc: Exception, context: Optional[str] = None) -> TrustCheckError:
    """
    Convert generic exceptions to TrustCheckError.
    
    Args:
        exc: The original exception
        context: Optional context information
        
    Returns:
        TrustCheckError with appropriate classification
    """
    if isinstance(exc, TrustCheckError):
        return exc
    
    # Map common exception types
    import sqlalchemy.exc
    
    if isinstance(exc, sqlalchemy.exc.IntegrityError):
        return DatabaseIntegrityError(
            message="Database integrity constraint violation",
            cause=exc,
            details={"context": context}
        )
    elif isinstance(exc, sqlalchemy.exc.OperationalError):
        return DatabaseConnectionError(
            message="Database connection or operation error",
            cause=exc,
            details={"context": context}
        )
    elif isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return NetworkError(
            url=getattr(exc.request, 'url', 'unknown') if hasattr(exc, 'request') else 'unknown',
            message=str(exc),
            cause=exc,
            details={"context": context}
        )
    elif isinstance(exc, ValueError):
        return ValidationError(
            message=str(exc),
            cause=exc,
            details={"context": context}
        )
    else:
        # Generic internal error
        return TrustCheckError(
            message=f"Unexpected error: {str(exc)}",
            error_code=ErrorCode.INTERNAL_ERROR,
            cause=exc,
            details={"context": context, "exception_type": type(exc).__name__}
        )


# ======================== EXPORTS ========================

__all__ = [
    # Error codes
    "ErrorCode",
    
    # Base exception
    "TrustCheckError",
    
    # Validation exceptions
    "ValidationError",
    "EntityValidationError",
    
    # Database exceptions
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseIntegrityError", 
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    
    # Scraping exceptions
    "ScrapingError",
    "ScraperNotFoundError",
    "DownloadError",
    "ParsingError",
    "SourceUnavailableError",
    "InvalidSourceDataError",
    
    # Change detection exceptions
    "ChangeDetectionError",
    "NotificationError",
    "ContentHashError",
    
    # External service exceptions
    "ExternalServiceError",
    "NetworkError", 
    "TimeoutError",
    
    # Auth exceptions
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    
    # Utilities
    "handle_exception"
]