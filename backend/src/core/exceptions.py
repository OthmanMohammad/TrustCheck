"""
Exception Hierarchy

Features:
- Structured exception hierarchy
- Error codes and categories
- Context preservation
- Logging integration
- User-friendly error messages
- Debugging information
"""

from typing import Any, Dict, Optional, List
from enum import Enum
import traceback
from datetime import datetime

class ErrorCategory(str, Enum):
    """High-level error categories for monitoring."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    RATE_LIMIT = "rate_limit"

class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# ======================== BASE EXCEPTION ========================

class TrustCheckError(Exception):
    """
    Base exception for all TrustCheck errors.
    
    Provides structured error handling with:
    - Error codes and categories
    - Context preservation  
    - User-friendly messages
    - Debugging information
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "GENERIC_ERROR",
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.user_message = user_message or message
        self.suggestions = suggestions or []
        self.cause = cause
        self.timestamp = datetime.utcnow()
        self.traceback_str = traceback.format_exc() if cause else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "user_message": self.user_message,
                "category": self.category.value,
                "severity": self.severity.value,
                "timestamp": self.timestamp.isoformat(),
                "context": self.context,
                "suggestions": self.suggestions,
                "cause": str(self.cause) if self.cause else None
            }
        }
    
    def __str__(self) -> str:
        """String representation with error code."""
        return f"[{self.error_code}] {self.message}"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"{self.__class__.__name__}("
            f"message='{self.message}', "
            f"error_code='{self.error_code}', "
            f"category='{self.category.value}', "
            f"severity='{self.severity.value}'"
            f")"
        )

# ======================== VALIDATION EXCEPTIONS ========================

class ValidationError(TrustCheckError):
    """Data validation errors."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        context = kwargs.pop('context', {})
        if field:
            context['field'] = field
        if value is not None:
            context['invalid_value'] = str(value)
        
        super().__init__(
            message=message,
            error_code=kwargs.pop('error_code', 'VALIDATION_ERROR'),
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            context=context,
            user_message=kwargs.pop('user_message', f"Invalid input: {message}"),
            **kwargs
        )

class SchemaValidationError(ValidationError):
    """JSON schema validation errors."""
    
    def __init__(self, schema_errors: List[Dict[str, Any]], **kwargs):
        error_details = "; ".join([
            f"{err.get('field', 'unknown')}: {err.get('message', 'validation failed')}"
            for err in schema_errors
        ])
        
        super().__init__(
            message=f"Schema validation failed: {error_details}",
            error_code="SCHEMA_VALIDATION_ERROR",
            context={"schema_errors": schema_errors},
            user_message="The provided data format is invalid",
            suggestions=["Check the API documentation for correct data format"],
            **kwargs
        )

# ======================== AUTHENTICATION & AUTHORIZATION ========================

class AuthenticationError(TrustCheckError):
    """Authentication failures."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.pop('error_code', 'AUTHENTICATION_FAILED'),
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.MEDIUM,
            user_message="Authentication required. Please provide valid credentials.",
            suggestions=["Check your API key or authentication token"],
            **kwargs
        )

class AuthorizationError(TrustCheckError):
    """Authorization/permission errors."""
    
    def __init__(self, resource: str, action: str, **kwargs):
        super().__init__(
            message=f"Access denied: insufficient permissions for {action} on {resource}",
            error_code=kwargs.pop('error_code', 'ACCESS_DENIED'),
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.MEDIUM,
            context={"resource": resource, "action": action},
            user_message="You don't have permission to perform this action.",
            suggestions=["Contact your administrator for access permissions"],
            **kwargs
        )

class InvalidTokenError(AuthenticationError):
    """Invalid or expired token errors."""
    
    def __init__(self, token_type: str = "access", **kwargs):
        super().__init__(
            message=f"Invalid or expired {token_type} token",
            error_code="INVALID_TOKEN",
            context={"token_type": token_type},
            user_message="Your session has expired. Please log in again.",
            **kwargs
        )

# ======================== RESOURCE EXCEPTIONS ========================

class ResourceNotFoundError(TrustCheckError):
    """Resource not found errors."""
    
    def __init__(self, resource_type: str, identifier: str, **kwargs):
        super().__init__(
            message=f"{resource_type} not found: {identifier}",
            error_code=kwargs.pop('error_code', 'RESOURCE_NOT_FOUND'),
            category=ErrorCategory.NOT_FOUND,
            severity=ErrorSeverity.LOW,
            context={"resource_type": resource_type, "identifier": identifier},
            user_message=f"The requested {resource_type.lower()} was not found.",
            suggestions=[f"Check that the {resource_type.lower()} ID is correct"],
            **kwargs
        )

class ResourceConflictError(TrustCheckError):
    """Resource conflict errors (duplicates, etc.)."""
    
    def __init__(self, resource_type: str, conflict_reason: str, **kwargs):
        super().__init__(
            message=f"{resource_type} conflict: {conflict_reason}",
            error_code=kwargs.pop('error_code', 'RESOURCE_CONFLICT'),
            category=ErrorCategory.CONFLICT,
            severity=ErrorSeverity.MEDIUM,
            context={"resource_type": resource_type, "conflict_reason": conflict_reason},
            user_message=f"Cannot create/update {resource_type.lower()}: {conflict_reason}",
            **kwargs
        )

# ======================== EXTERNAL SERVICE EXCEPTIONS ========================

class ExternalServiceError(TrustCheckError):
    """External service integration errors."""
    
    def __init__(
        self,
        service_name: str,
        operation: str,
        status_code: Optional[int] = None,
        **kwargs
    ):
        context = kwargs.pop('context', {})
        context.update({
            "service": service_name,
            "operation": operation,
            "status_code": status_code
        })
        
        super().__init__(
            message=f"{service_name} service error during {operation}",
            error_code=kwargs.pop('error_code', 'EXTERNAL_SERVICE_ERROR'),
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            context=context,
            user_message="External service is temporarily unavailable.",
            suggestions=["Please try again later", "Contact support if the issue persists"],
            **kwargs
        )

class ScrapingError(ExternalServiceError):
    """Web scraping specific errors."""
    
    def __init__(self, source: str, url: str, **kwargs):
        super().__init__(
            service_name="Web Scraper",
            operation=f"scraping {source}",
            error_code=kwargs.pop('error_code', 'SCRAPING_ERROR'),
            context={**kwargs.pop('context', {}), "source": source, "url": url},
            user_message=f"Failed to retrieve data from {source}.",
            **kwargs
        )

class DataSourceUnavailableError(ScrapingError):
    """Data source unavailable or unreachable."""
    
    def __init__(self, source: str, url: str, **kwargs):
        super().__init__(
            source=source,
            url=url,
            error_code="DATA_SOURCE_UNAVAILABLE",
            severity=ErrorSeverity.CRITICAL,
            user_message=f"The {source} data source is currently unavailable.",
            suggestions=[
                f"Check if {url} is accessible",
                "Verify network connectivity",
                "Contact the data source provider"
            ],
            **kwargs
        )

# ======================== DATABASE EXCEPTIONS ========================

class DatabaseError(TrustCheckError):
    """Database operation errors."""
    
    def __init__(self, operation: str, **kwargs):
        super().__init__(
            message=f"Database error during {operation}",
            error_code=kwargs.pop('error_code', 'DATABASE_ERROR'),
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            context={"operation": operation},
            user_message="A database error occurred. Please try again.",
            suggestions=["Contact support if the issue persists"],
            **kwargs
        )

class DatabaseConnectionError(DatabaseError):
    """Database connection errors."""
    
    def __init__(self, **kwargs):
        super().__init__(
            operation="connection",
            error_code="DATABASE_CONNECTION_ERROR",
            severity=ErrorSeverity.CRITICAL,
            user_message="Database is temporarily unavailable.",
            **kwargs
        )

class TransactionError(DatabaseError):
    """Database transaction errors."""
    
    def __init__(self, transaction_type: str, **kwargs):
        super().__init__(
            operation=f"{transaction_type} transaction",
            error_code="TRANSACTION_ERROR",
            context={"transaction_type": transaction_type},
            user_message="Transaction failed. Changes were not saved.",
            **kwargs
        )

# ======================== BUSINESS LOGIC EXCEPTIONS ========================

class BusinessLogicError(TrustCheckError):
    """Business rule violations."""
    
    def __init__(self, rule: str, **kwargs):
        super().__init__(
            message=f"Business rule violation: {rule}",
            error_code=kwargs.pop('error_code', 'BUSINESS_LOGIC_ERROR'),
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            context={"rule": rule},
            user_message=f"Operation failed: {rule}",
            **kwargs
        )

class ChangeDetectionError(BusinessLogicError):
    """Change detection specific errors."""
    
    def __init__(self, source: str, stage: str, **kwargs):
        super().__init__(
            rule=f"Change detection failed for {source} during {stage}",
            error_code="CHANGE_DETECTION_ERROR",
            context={**kwargs.pop('context', {}), "source": source, "stage": stage},
            user_message=f"Failed to detect changes in {source} data.",
            **kwargs
        )

class ComplianceViolationError(BusinessLogicError):
    """Compliance rule violations."""
    
    def __init__(self, violation: str, entity: Optional[str] = None, **kwargs):
        context = kwargs.pop('context', {})
        if entity:
            context['entity'] = entity
        
        super().__init__(
            rule=f"Compliance violation: {violation}",
            error_code="COMPLIANCE_VIOLATION",
            severity=ErrorSeverity.HIGH,
            context=context,
            user_message=f"Compliance issue detected: {violation}",
            **kwargs
        )

# ======================== SYSTEM EXCEPTIONS ========================

class ConfigurationError(TrustCheckError):
    """Configuration errors."""
    
    def __init__(self, setting: str, **kwargs):
        super().__init__(
            message=f"Configuration error: {setting}",
            error_code="CONFIGURATION_ERROR",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            context={"setting": setting},
            user_message="System configuration error.",
            suggestions=["Check environment variables and configuration files"],
            **kwargs
        )

class RateLimitError(TrustCheckError):
    """Rate limiting errors."""
    
    def __init__(self, limit: int, window: str, **kwargs):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            error_code="RATE_LIMIT_EXCEEDED",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.LOW,
            context={"limit": limit, "window": window},
            user_message="Too many requests. Please slow down.",
            suggestions=[f"Wait before making more requests", f"Limit to {limit} requests per {window}"],
            **kwargs
        )

# ======================== UTILITY FUNCTIONS ========================

def handle_exception(
    exc: Exception,
    logger,
    default_error_code: str = "UNEXPECTED_ERROR",
    context: Optional[Dict[str, Any]] = None
) -> TrustCheckError:
    """
    Convert any exception to a TrustCheckError with proper logging.
    
    Args:
        exc: The original exception
        logger: Logger instance
        default_error_code: Error code if not a TrustCheckError
        context: Additional context
        
    Returns:
        TrustCheckError instance
    """
    
    # If already a TrustCheckError, just log and return
    if isinstance(exc, TrustCheckError):
        logger.error(
            exc.message,
            extra={
                "error_code": exc.error_code,
                "category": exc.category.value,
                "severity": exc.severity.value,
                "context": exc.context
            },
            exc_info=True
        )
        return exc
    
    # Convert generic exception to TrustCheckError
    trustcheck_error = TrustCheckError(
        message=f"Unexpected error: {str(exc)}",
        error_code=default_error_code,
        category=ErrorCategory.SYSTEM,
        severity=ErrorSeverity.HIGH,
        context=context or {},
        cause=exc
    )
    
    logger.error(
        trustcheck_error.message,
        extra={
            "error_code": trustcheck_error.error_code,
            "original_exception": type(exc).__name__,
            "context": trustcheck_error.context
        },
        exc_info=True
    )
    
    return trustcheck_error

def create_error_response(error: TrustCheckError) -> Dict[str, Any]:
    """Create standardized error response for APIs."""
    return {
        "success": False,
        "error": {
            "code": error.error_code,
            "message": error.user_message,
            "category": error.category.value,
            "timestamp": error.timestamp.isoformat(),
            "suggestions": error.suggestions
        }
    }

# Export all exception types
__all__ = [
    # Base
    'TrustCheckError',
    'ErrorCategory',
    'ErrorSeverity',
    
    # Validation
    'ValidationError',
    'SchemaValidationError',
    
    # Auth
    'AuthenticationError',
    'AuthorizationError', 
    'InvalidTokenError',
    
    # Resources
    'ResourceNotFoundError',
    'ResourceConflictError',
    
    # External
    'ExternalServiceError',
    'ScrapingError',
    'DataSourceUnavailableError',
    
    # Database
    'DatabaseError',
    'DatabaseConnectionError',
    'TransactionError',
    
    # Business Logic
    'BusinessLogicError',
    'ChangeDetectionError',
    'ComplianceViolationError',
    
    # System
    'ConfigurationError',
    'RateLimitError',
    
    # Utilities
    'handle_exception',
    'create_error_response'
]