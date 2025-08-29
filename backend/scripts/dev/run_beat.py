# run_beat.py
import sys
import os

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

# Import and run beat
from src.celery_app import app

if __name__ == '__main__':
    # Correct command - no 'celery' prefix needed
    app.start(['beat', '--loglevel=info'])