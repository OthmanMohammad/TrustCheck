"""
Production Celery Application.
"""
from celery import Celery, Task
from celery.signals import setup_logging, worker_ready, worker_shutdown, task_prerun, task_postrun, task_failure
import logging
import asyncio
from datetime import datetime
from typing import Any

from src.core.celery_config import CeleryConfig
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class AsyncTask(Task):
    """Custom task class with async support."""
    
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
        """Handle task failure."""
        logger.error(
            f"Task failed: {self.name}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "exception": str(exc),
                "traceback": str(einfo)
            }
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
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
        """Handle task success."""
        logger.info(
            f"Task completed: {self.name}",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "duration_ms": getattr(self.request, 'duration_ms', None)
            }
        )

def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    
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
    
    # Load configuration from CeleryConfig class
    app.config_from_object(CeleryConfig)
    
    # Additional settings
    app.conf.update(
        broker_connection_retry_on_startup=True,
        broker_pool_limit=10,
        result_backend_pool_limit=10,
        task_compression='gzip',
        result_compression='gzip',
        worker_hijack_root_logger=False,
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    )
    
    return app

# Create the Celery app instance
app = create_celery_app()

# Signal handlers
@setup_logging.connect
def configure_logging(**kwargs):
    """Configure logging."""
    pass  # Use our custom logging

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
    """Handle task failures."""
    logger.error(
        f"Task failed: {task_id}",
        extra={
            "task_id": task_id,
            "exception": str(exception),
            "task_name": sender.name if sender else "unknown"
        }
    )

__all__ = ['app', 'AsyncTask']