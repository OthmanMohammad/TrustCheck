"""
Celery configuration module.
"""
import os
from celery.schedules import crontab
from src.core.config import settings

class CeleryConfig:
    # Broker settings
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
    
    # Serialization
    task_serializer = 'json'
    accept_content = ['json']
    result_serializer = 'json'
    
    # Timezone
    timezone = 'UTC'
    enable_utc = True
    
    # Task execution
    task_track_started = True
    task_send_sent_event = True
    task_acks_late = True
    task_reject_on_worker_lost = True
    task_time_limit = 3600  # 1 hour hard limit
    task_soft_time_limit = 3000  # 50 min soft limit
    
    # Worker
    worker_prefetch_multiplier = 4
    worker_max_tasks_per_child = 1000
    worker_disable_rate_limits = False
    worker_send_task_events = True
    
    # Beat schedule
    beat_schedule = {
        'scrape-ofac-every-6-hours': {
            'task': 'src.tasks.scraping_tasks.run_scraper_task',
            'schedule': crontab(minute=0, hour='*/6'),
            'args': ('OFAC',),
            'options': {'queue': 'scraping', 'priority': 9}
        },
        'scrape-un-daily': {
            'task': 'src.tasks.scraping_tasks.run_scraper_task',
            'schedule': crontab(minute=0, hour=2),
            'args': ('UN',),
            'options': {'queue': 'scraping', 'priority': 8}
        },
        'health-check-every-5-min': {
            'task': 'src.tasks.maintenance_tasks.health_check_task',
            'schedule': crontab(minute='*/5'),
            'options': {'queue': 'maintenance', 'priority': 10}
        },
        'cleanup-old-data-daily': {
            'task': 'src.tasks.maintenance_tasks.cleanup_old_data_task',
            'schedule': crontab(minute=0, hour=4),
            'options': {'queue': 'maintenance', 'priority': 1}
        },
        'send-daily-digest': {
            'task': 'src.tasks.notification_tasks.send_daily_digest_task',
            'schedule': crontab(minute=0, hour=9),
            'options': {'queue': 'notifications', 'priority': 5}
        }
    }
    
    # Queue routing
    task_routes = {
        'src.tasks.scraping_tasks.*': {'queue': 'scraping'},
        'src.tasks.notification_tasks.*': {'queue': 'notifications'},
        'src.tasks.maintenance_tasks.*': {'queue': 'maintenance'},
    }
    
    # Queue configuration
    task_default_queue = 'celery'
    task_queues = {
        'celery': {'routing_key': 'celery'},
        'scraping': {'routing_key': 'scraping'},
        'notifications': {'routing_key': 'notifications'},
        'maintenance': {'routing_key': 'maintenance'},
    }