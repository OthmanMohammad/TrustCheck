# backend/test_celery_simple.py
"""
Simple Celery test to verify basic functionality.
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.celery_app import app

# Test 1: Check if Celery app is created
print("✅ Celery app created")
print(f"   Broker: {app.conf.broker_url}")
print(f"   Backend: {app.conf.result_backend}")

# Test 2: Create a simple task
@app.task
def add(x, y):
    return x + y

print("✅ Simple task created")

# Test 3: Check registered tasks
print(f"✅ Registered tasks: {len(app.tasks)}")
for task_name in list(app.tasks.keys())[:5]:
    print(f"   - {task_name}")

print("\n✨ Basic Celery configuration is working!")
print("\nNow try running the worker:")
print("  celery -A src.celery_app.app worker --loglevel=info")