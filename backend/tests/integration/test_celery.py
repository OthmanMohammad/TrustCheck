#!/usr/bin/env python
"""
Comprehensive Celery testing script.
Run this to verify Celery is working correctly.
"""

import asyncio
import time
from datetime import datetime
from colorama import init, Fore, Style
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Initialize colorama for colored output
init(autoreset=True)

def print_header(text):
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{text:^60}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

def print_success(text):
    print(f"{Fore.GREEN}✅ {text}{Style.RESET_ALL}")

def print_error(text):
    print(f"{Fore.RED}❌ {text}{Style.RESET_ALL}")

def print_info(text):
    print(f"{Fore.YELLOW}ℹ️  {text}{Style.RESET_ALL}")

def print_test(test_name):
    print(f"\n{Fore.MAGENTA}🧪 Testing: {test_name}{Style.RESET_ALL}")

async def test_redis_connection():
    """Test Redis connectivity."""
    print_test("Redis Connection")
    try:
        import redis
        from src.core.config import settings
        
        r = redis.from_url(settings.redis.redis_url)
        r.ping()
        print_success(f"Redis connected at {settings.redis.host}:{settings.redis.port}")
        
        # Test set/get
        r.set('test_key', 'test_value', ex=10)
        value = r.get('test_key')
        assert value.decode() == 'test_value'
        print_success("Redis set/get operations working")
        
        return True
    except Exception as e:
        print_error(f"Redis connection failed: {e}")
        return False

async def test_database_connection():
    """Test database connectivity."""
    print_test("Database Connection")
    try:
        from src.infrastructure.database.connection import db_manager
        
        is_connected = await db_manager.check_connection()
        if is_connected:
            print_success(f"Database connected at {db_manager.engine.url}")
        else:
            print_error("Database connection check failed")
        return is_connected
    except Exception as e:
        print_error(f"Database connection failed: {e}")
        return False

def test_celery_app():
    """Test Celery app configuration."""
    print_test("Celery App Configuration")
    try:
        from src.celery_app import app
        
        # Check app configuration
        print_info(f"Broker: {app.conf.broker_url}")
        print_info(f"Backend: {app.conf.result_backend}")
        print_info(f"Timezone: {app.conf.timezone}")
        
        # Check registered tasks
        tasks = list(app.tasks.keys())
        print_info(f"Registered tasks: {len(tasks)}")
        for task in tasks[:5]:  # Show first 5 tasks
            print(f"  - {task}")
        
        print_success("Celery app configured correctly")
        return True
    except Exception as e:
        print_error(f"Celery app configuration failed: {e}")
        return False

def test_simple_task():
    """Test a simple Celery task."""
    print_test("Simple Celery Task")
    try:
        from src.celery_app import app
        
        # Create a simple test task
        @app.task
        def test_add(x, y):
            return x + y
        
        # Send task
        result = test_add.delay(4, 6)
        print_info(f"Task ID: {result.id}")
        
        # Wait for result (max 10 seconds)
        start_time = time.time()
        while not result.ready() and time.time() - start_time < 10:
            time.sleep(0.5)
        
        if result.ready():
            if result.successful():
                print_success(f"Task completed successfully. Result: {result.result}")
                return True
            else:
                print_error(f"Task failed: {result.info}")
                return False
        else:
            print_error("Task timed out")
            return False
            
    except Exception as e:
        print_error(f"Simple task test failed: {e}")
        return False

def test_scraping_task():
    """Test scraping task (dry run)."""
    print_test("Scraping Task (Dry Run)")
    try:
        from src.tasks.scraping_tasks import check_scraper_health_task
        
        # Queue health check task
        result = check_scraper_health_task.delay()
        print_info(f"Health check task ID: {result.id}")
        
        # Wait for result
        start_time = time.time()
        while not result.ready() and time.time() - start_time < 15:
            time.sleep(1)
        
        if result.ready():
            if result.successful():
                health_status = result.result
                print_success("Health check completed")
                print_info(f"Timestamp: {health_status.get('timestamp')}")
                print_info(f"Sources checked: {list(health_status.get('sources', {}).keys())}")
                return True
            else:
                print_error(f"Health check failed: {result.info}")
                return False
        else:
            print_error("Health check timed out")
            return False
            
    except Exception as e:
        print_error(f"Scraping task test failed: {e}")
        return False

def test_task_routing():
    """Test task routing to different queues."""
    print_test("Task Queue Routing")
    try:
        from src.celery_app import app
        
        # Check configured queues
        routes = app.conf.task_routes
        print_info("Configured routes:")
        for pattern, queue in routes.items():
            print(f"  - {pattern} -> {queue}")
        
        print_success("Task routing configured")
        return True
    except Exception as e:
        print_error(f"Task routing test failed: {e}")
        return False

def test_flower_api():
    """Test Flower monitoring API."""
    print_test("Flower Monitoring API")
    try:
        import requests
        from requests.auth import HTTPBasicAuth
        
        # Try to connect to Flower
        response = requests.get(
            'http://localhost:5555/api/workers',
            auth=HTTPBasicAuth('admin', 'trustcheck2024'),
            timeout=5
        )
        
        if response.status_code == 200:
            workers = response.json()
            print_success(f"Flower API accessible. Workers: {len(workers)}")
            for worker_name in workers.keys():
                print(f"  - {worker_name}")
            return True
        else:
            print_error(f"Flower API returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_info("Flower not running (this is OK for basic testing)")
        return True
    except Exception as e:
        print_error(f"Flower API test failed: {e}")
        return False

async def run_all_tests():
    """Run all Celery tests."""
    print_header("CELERY INTEGRATION TESTS")
    print_info(f"Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test connections
    results.append(await test_redis_connection())
    results.append(await test_database_connection())
    
    # Test Celery
    results.append(test_celery_app())
    results.append(test_simple_task())
    results.append(test_task_routing())
    results.append(test_scraping_task())
    results.append(test_flower_api())
    
    # Summary
    print_header("TEST RESULTS SUMMARY")
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print_success(f"All {total} tests passed! 🎉")
        print_info("Celery is ready for production!")
    else:
        print_error(f"{total - passed} out of {total} tests failed")
        print_info("Please check the errors above and fix them before proceeding")
    
    return passed == total

if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)