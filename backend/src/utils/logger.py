"""
Logging Configuration

Structured logging with:
- JSON formatting for production
- Context enrichment
- Performance monitoring
- Error tracking
"""

import logging
import sys
from typing import Any, Dict, Optional
from datetime import datetime
import json

from src.core.config import settings

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'extra') and record.extra:
            log_data.update(record.extra)
        
        # Add request context if available
        for attr in ['user_id', 'request_id', 'ip_address', 'user_agent']:
            if hasattr(record, attr):
                log_data[attr] = getattr(record, attr)
        
        return json.dumps(log_data, ensure_ascii=False)

class ProductionFilter(logging.Filter):
    """Filter for production logging."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records based on production criteria."""
        
        # Don't log debug messages in production
        if not settings.DEBUG and record.levelno == logging.DEBUG:
            return False
        
        # Filter out noisy third-party logs
        noisy_loggers = [
            'urllib3.connectionpool',
            'asyncio',
        ]
        
        for noisy_logger in noisy_loggers:
            if record.name.startswith(noisy_logger) and record.levelno < logging.WARNING:
                return False
        
        return True

def setup_logging():
    """Set up production logging configuration."""
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if settings.DEBUG:
        # Simple format for development
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # JSON format for production
        formatter = JSONFormatter()
    
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ProductionFilter())
    
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    
    if not settings.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance with production configuration.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)

class LogContext:
    """Context manager for adding context to log messages."""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, *args):
        logging.setLogRecordFactory(self.old_factory)

# Initialize logging on import
setup_logging()