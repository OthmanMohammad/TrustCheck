# test_task.py
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

# Apply patch
import importlib.metadata as importlib_metadata
original_entry_points = importlib_metadata.entry_points

def patched_entry_points():
    eps = original_entry_points()
    class FakeDict:
        def get(self, name, default=None):
            try:
                return list(eps.select(group=name))
            except:
                return default
    return FakeDict()

importlib_metadata.entry_points = patched_entry_points

# Set broker configuration BEFORE importing Celery app
os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/1'

# Now import and configure
from celery import Celery

# Create a test app with proper config
app = Celery('test')
app.config_from_object({
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/1',
})

# Import the task
from src.tasks.maintenance_tasks import health_check_task

# Send task
result = health_check_task.delay()
print(f"Task ID: {result.id}")
print(f"Result: {result.get(timeout=10)}")