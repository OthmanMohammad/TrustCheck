# test_full_system.py
# (include patch code first)

from src.tasks.scraping_tasks import run_scraper_task

# Queue a scraping task
result = run_scraper_task.delay('OFAC', force_update=True)
print(f"Scraping task queued: {result.id}")

# Watch it in Flower dashboard
print("Check http://localhost:5555 to see the task running")