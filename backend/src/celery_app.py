"""
Production Celery Application with comprehensive configuration.
"""

from celery import Celery, Task
from celery.signals import (
    setup_logging, worker_ready, worker_shutdown,
    task_prerun, task_postrun, task_failure, task_retry
)
from typing import Any, Dict
import logging
import asyncio
from datetime import datetime

from src.core.config import settings
from src.core.logging_config import get_logger

# Remove this line - it's not needed
# os.environ.setdefault('CELERY_CONFIG_MODULE', 'src.celery_config')

logger = get_logger(__name__)

# ======================== CUSTOM TASK CLASS ========================

class AsyncTask(Task):
    """
    Custom task class with async support and enhanced error handling.
    """
    
    def __init__(self):
        self._async_loop = None
    
    @property
    def loop(self):
        """Get or create event loop for async tasks."""
        if self._async_loop is None:
            try:
                self._async_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._async_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._async_loop)
        return self._async_loop
    
    def __call__(self, *args, **kwargs):
        """Execute task with async support."""
        try:
            # Check if task is async
            if asyncio.iscoroutinefunction(self.run):
                return self.loop.run_until_complete(
                    self.run(*args, **kwargs)
                )
            else:
                return self.run(*args, **kwargs)
        except Exception as exc:
            logger.error(
                f"Task {self.name} failed: {exc}",
                extra={
                    "task_id": self.request.id,
                    "task_name": self.name,
                    "args": args,
                    "kwargs": kwargs
                },
                exc_info=True
            )
            raise
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure with comprehensive logging."""
        logger.error(
            f"Task failed: {self.name}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "exception": str(exc),
                "args": args,
                "kwargs": kwargs,
                "traceback": str(einfo)
            }
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry with logging."""
        logger.warning(
            f"Task retrying: {self.name}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "exception": str(exc),
                "retry_count": self.request.retries
            }
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success with metrics."""
        logger.info(
            f"Task completed: {self.name}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "duration_ms": getattr(self.request, 'duration_ms', None)
            }
        )

# ======================== CREATE CELERY APP ========================

def create_celery_app() -> Celery:
    """
    Create and configure Celery application.
    """
    
    # Create Celery instance
    app = Celery(
        'trustcheck',
        task_cls=AsyncTask,
        include=[
            'src.tasks.scraping_tasks',
            'src.tasks.notification_tasks',
            'src.tasks.report_tasks',
            'src.tasks.maintenance_tasks'
        ]
    )
    
    # Load configuration from settings - FIX: use get_celery_config() method
    app.config_from_object(settings.celery.get_celery_config())
    
    # Additional production configurations
    app.conf.update(
        # Task execution
        task_track_started=True,
        task_send_sent_event=True,
        
        # Worker configuration
        worker_send_task_events=True,
        worker_disable_rate_limits=False,
        
        # Security
        worker_hijack_root_logger=False,
        
        # Monitoring
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        
        # Error handling
        task_eager_propagates=True,
        task_ignore_result=False,
        
        # Performance
        broker_connection_retry_on_startup=True,
        broker_pool_limit=10,
        result_backend_pool_limit=10,
        
        # Compression
        task_compression='gzip',
        result_compression='gzip'
    )
    
    return app

# Create the Celery app instance
app = create_celery_app()

# ======================== SIGNAL HANDLERS ========================

@setup_logging.connect
def configure_logging(**kwargs):
    """Configure Celery logging to use our logging config."""
    # Don't override our logging config
    pass

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker startup."""
    logger.info(
        "Celery worker ready",
        extra={
            "hostname": sender.hostname if sender else "unknown",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Handle worker shutdown."""
    logger.info(
        "Celery worker shutting down",
        extra={
            "hostname": sender.hostname if sender else "unknown",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Track task start time."""
    task.request.start_time = datetime.utcnow()

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Calculate task duration."""
    if hasattr(task.request, 'start_time'):
        duration = (datetime.utcnow() - task.request.start_time).total_seconds()
        task.request.duration_ms = int(duration * 1000)

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Handle task failures for monitoring."""
    logger.error(
        f"Task failed: {task_id}",
        extra={
            "task_id": task_id,
            "exception": str(exception),
            "task_name": sender.name if sender else "unknown"
        }
    )

# ======================== SCHEDULED TASKS CONFIGURATION ========================

from celery.schedules import crontab

app.conf.beat_schedule = {
    # Scraping tasks
    'scrape-ofac-every-6-hours': {
        'task': 'src.tasks.scraping_tasks.run_scraper_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'args': ('OFAC',),
        'options': {
            'queue': 'scraping',
            'priority': 9
        }
    },
    
    'scrape-un-daily': {
        'task': 'src.tasks.scraping_tasks.run_scraper_task',
        'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
        'args': ('UN',),
        'options': {
            'queue': 'scraping',
            'priority': 8
        }
    },
    
    # Notification tasks
    'send-daily-digest': {
        'task': 'src.tasks.notification_tasks.send_daily_digest_task',
        'schedule': crontab(minute=0, hour=9),  # Daily at 9 AM
        'options': {
            'queue': 'notifications',
            'priority': 5
        }
    },
    
    # Maintenance tasks
    'cleanup-old-data': {
        'task': 'src.tasks.maintenance_tasks.cleanup_old_data_task',
        'schedule': crontab(minute=0, hour=4),  # Daily at 4 AM
        'options': {
            'queue': 'maintenance',
            'priority': 1
        }
    },
    
    'health-check': {
        'task': 'src.tasks.maintenance_tasks.health_check_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {
            'queue': 'maintenance',
            'priority': 10
        }
    }
}

# ======================== EXPORTS ========================

__all__ = ['app', 'AsyncTask']