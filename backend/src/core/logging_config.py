"""
Production Logging Configuration

Features:
- Structured JSON logging for production
- Request ID correlation
- Context-aware logging
- Performance logging
- Log level management
"""

import logging
import logging.config
import sys
import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from contextvars import ContextVar
import json
import traceback

from src.core.config import settings

# Context variables for request correlation
REQUEST_ID_VAR: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
USER_ID_VAR: ContextVar[Optional[str]] = ContextVar('user_id', default=None)

class ContextualFilter(logging.Filter):
    """Add contextual information to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Add request ID if available
        record.request_id = REQUEST_ID_VAR.get()
        record.user_id = USER_ID_VAR.get()
        
        # Add correlation fields
        record.service_name = settings.project_name
        record.service_version = settings.version
        record.environment = settings.environment.value
        
        return True

class JSONFormatter(logging.Formatter):
    """Production JSON formatter with structured output."""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log structure
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line_number": record.lineno,
            "thread_id": record.thread,
            "process_id": record.process,
        }
        
        # Add service context
        if hasattr(record, 'service_name'):
            log_entry["service"] = {
                "name": record.service_name,
                "version": record.service_version,
                "environment": record.environment
            }
        
        # Add request context if available
        if hasattr(record, 'request_id') and record.request_id:
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, 'user_id') and record.user_id:
            log_entry["user_id"] = record.user_id
        
        # Add exception information
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields from LoggerAdapter or direct calls
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'message', 'exc_info', 'exc_text',
                    'stack_info', 'request_id', 'user_id', 'service_name',
                    'service_version', 'environment'
                }:
                    try:
                        # Ensure JSON serializable
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False)

class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for development."""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with colors and context for development."""
        
        # Add request ID to message if available
        original_format = super().format(record)
        
        if hasattr(record, 'request_id') and record.request_id:
            original_format = f"[{record.request_id}] {original_format}"
        
        return original_format

class ProductionFilter(logging.Filter):
    """Filter logs for production environment."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter based on production requirements."""
        
        # Block debug logs in production
        if settings.environment.value == "production" and record.levelno < logging.INFO:
            return False
        
        # Filter noisy third-party logs
        noisy_loggers = [
            'urllib3.connectionpool',
            'asyncio',
            'multipart.multipart',
            'httpcore',
        ]
        
        for noisy_logger in noisy_loggers:
            if (record.name.startswith(noisy_logger) and 
                record.levelno < logging.WARNING):
                return False
        
        return True

class PerformanceLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for performance tracking."""
    
    def process(self, msg: Any, kwargs: Dict[str, Any]) -> tuple:
        """Add performance context to log messages."""
        extra = kwargs.get('extra', {})
        
        # Add performance context from adapter
        if hasattr(self, 'extra'):
            extra.update(self.extra)
        
        kwargs['extra'] = extra
        return msg, kwargs

def setup_logging() -> None:
    """Configure production logging system."""
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Set root level
    root_logger.setLevel(logging.DEBUG)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Choose formatter based on environment
    if settings.observability.log_format == "json" or settings.is_production:
        formatter = JSONFormatter(include_extra=True)
    else:
        formatter = DevelopmentFormatter()
    
    console_handler.setFormatter(formatter)
    
    # Add filters
    console_handler.addFilter(ContextualFilter())
    console_handler.addFilter(ProductionFilter())
    
    # Set handler level
    handler_level = getattr(logging, settings.observability.log_level.value)
    console_handler.setLevel(handler_level)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    configure_third_party_loggers()
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging system initialized",
        extra={
            "log_level": settings.observability.log_level.value,
            "log_format": settings.observability.log_format,
            "environment": settings.environment.value
        }
    )

def configure_third_party_loggers() -> None:
    """Configure third-party library loggers."""
    
    # SQLAlchemy logging
    if settings.debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    
    # HTTP client logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Uvicorn logging
    if not settings.debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """Get configured logger instance."""
    return logging.getLogger(name)

def get_performance_logger(name: str, **context) -> PerformanceLoggerAdapter:
    """Get performance logger with context."""
    logger = get_logger(name)
    return PerformanceLoggerAdapter(logger, context)

class LoggingContext:
    """Context manager for adding context to logs."""
    
    def __init__(self, request_id: Optional[str] = None, user_id: Optional[str] = None, **extra):
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id
        self.extra = extra
        self._request_id_token = None
        self._user_id_token = None
    
    def __enter__(self) -> 'LoggingContext':
        self._request_id_token = REQUEST_ID_VAR.set(self.request_id)
        if self.user_id:
            self._user_id_token = USER_ID_VAR.set(self.user_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._request_id_token:
            REQUEST_ID_VAR.reset(self._request_id_token)
        if self._user_id_token:
            USER_ID_VAR.reset(self._user_id_token)

def log_exception(logger: logging.Logger, exc: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """Log exception with full context."""
    
    extra_context = context or {}
    extra_context.update({
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": traceback.format_exc()
    })
    
    logger.error(
        f"Exception occurred: {type(exc).__name__}: {exc}",
        extra=extra_context,
        exc_info=True
    )

def log_performance(
    logger: logging.Logger,
    operation: str,
    duration_ms: float,
    success: bool = True,
    **context
) -> None:
    """Log performance metrics."""
    
    level = logging.INFO if success else logging.WARNING
    
    logger.log(
        level,
        f"Performance: {operation}",
        extra={
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
            "performance_metric": True,
            **context
        }
    )

# Initialize logging on module import
setup_logging()

# Export commonly used functions
__all__ = [
    'setup_logging',
    'get_logger', 
    'get_performance_logger',
    'LoggingContext',
    'log_exception',
    'log_performance',
    'REQUEST_ID_VAR',
    'USER_ID_VAR'
]