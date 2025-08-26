import logging
import sys
from typing import Any, Dict, Optional
from datetime import datetime
import json
from contextlib import contextmanager

from src.core.config.settings import settings

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structure."""
        
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
        
        # Add extra fields from LogContext or direct extra
        if hasattr(record, 'extra') and record.extra:
            log_data.update(record.extra)
        
        # Add context fields
        for attr in ['request_id', 'user_id', 'entity_id', 'source']:
            if hasattr(record, attr):
                log_data[attr] = getattr(record, attr)
        
        if settings.DEBUG:
            # Human readable format for development
            extra_info = ""
            if any(hasattr(record, attr) for attr in ['request_id', 'user_id', 'entity_id']):
                context = []
                for attr in ['request_id', 'user_id', 'entity_id']:
                    if hasattr(record, attr):
                        context.append(f"{attr}={getattr(record, attr)}")
                if context:
                    extra_info = f" [{', '.join(context)}]"
            
            return f"{log_data['timestamp']} - {log_data['logger']} - {log_data['level']} - {log_data['message']}{extra_info}"
        else:
            # JSON format for production
            return json.dumps(log_data, ensure_ascii=False)

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
    formatter = StructuredFormatter()
    console_handler.setFormatter(formatter)
    
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