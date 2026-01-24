"""
TrustCheck Scheduler Module.

APScheduler-based background job scheduling with:
- Configurable intervals per data source
- Job execution history and tracking
- Pause/resume capabilities
- Health monitoring
"""

from trustcheck.scheduler.jobs import (
    clear_screening_cache,
    get_job_history,
    get_job_status,
    get_scheduler,
    get_scheduler_health,
    job_history,
    pause_job,
    reschedule_job,
    resume_job,
    scrape_all,
    scrape_eu,
    scrape_ofac,
    scrape_uk,
    scrape_un,
    setup_scheduler,
    start_scheduler,
    stop_scheduler,
    trigger_job_now,
)

__all__ = [
    "clear_screening_cache",
    "get_job_history",
    "get_job_status",
    "get_scheduler",
    "get_scheduler_health",
    "job_history",
    "pause_job",
    "reschedule_job",
    "resume_job",
    "scrape_all",
    "scrape_eu",
    "scrape_ofac",
    "scrape_uk",
    "scrape_un",
    "setup_scheduler",
    "start_scheduler",
    "stop_scheduler",
    "trigger_job_now",
]
