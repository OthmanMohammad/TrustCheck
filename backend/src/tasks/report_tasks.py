"""Report generation tasks (placeholder)."""
from celery import shared_task

@shared_task(name='src.tasks.report_tasks.generate_weekly_report_task')
def generate_weekly_report_task():
    """Placeholder for weekly report generation."""
    return {"status": "not_implemented"}