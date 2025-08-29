# run_celery.py
import sys
import os

# CRITICAL: Monkey-patch BEFORE any imports
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

# NOW import Celery
from src.celery_app import app

if __name__ == '__main__':
    # Run worker directly without CLI
    app.worker_main([
        'worker',
        '--loglevel=info',
        '--pool=solo',  # For Windows
        '--concurrency=1',
    ])