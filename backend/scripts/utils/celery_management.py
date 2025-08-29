#!/usr/bin/env python
"""
Celery management utilities for production operations.
"""

import click
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from src.celery_app import app
from src.core.logging_config import get_logger

logger = get_logger(__name__)

@click.group()
def cli():
    """Celery management CLI."""
    pass

@cli.command()
@click.option('--queue', '-q', default='default', help='Queue name')
def inspect_queue(queue: str):
    """Inspect queue status."""
    inspector = app.control.inspect()
    
    # Active tasks
    active = inspector.active()
    if active:
        click.echo(f"\nActive tasks in queue '{queue}':")
        for worker, tasks in active.items():
            for task in tasks:
                if task.get('delivery_info', {}).get('routing_key') == queue:
                    click.echo(f"  - {task['id']}: {task['name']}")
    
    # Reserved tasks
    reserved = inspector.reserved()
    if reserved:
        click.echo(f"\nReserved tasks in queue '{queue}':")
        for worker, tasks in reserved.items():
            click.echo(f"  Worker: {worker} - {len(tasks)} tasks")
    
    # Stats
    stats = inspector.stats()
    if stats:
        click.echo("\nWorker statistics:")
        for worker, stat in stats.items():
            click.echo(f"  {worker}:")
            click.echo(f"    - Total tasks: {stat.get('total', {})}")
            click.echo(f"    - Pool: {stat.get('pool', {})}")

@cli.command()
@click.argument('task_id')
def cancel_task(task_id: str):
    """Cancel a specific task."""
    try:
        app.control.revoke(task_id, terminate=True)
        click.echo(f"Task {task_id} cancelled")
    except Exception as e:
        click.echo(f"Error cancelling task: {e}", err=True)

@cli.command()
@click.option('--source', '-s', help='Data source')
def trigger_scraping(source: Optional[str]):
    """Manually trigger scraping."""
    from src.tasks.scraping_tasks import run_scraper_task, scrape_all_sources_task
    
    if source:
        result = run_scraper_task.delay(source)
        click.echo(f"Scraping task queued for {source}: {result.id}")
    else:
        result = scrape_all_sources_task.delay()
        click.echo(f"Scraping all sources: {result.id}")

@cli.command()
def purge_queues():
    """Purge all queues (dangerous!)."""
    if click.confirm("This will delete ALL pending tasks. Continue?"):
        app.control.purge()
        click.echo("All queues purged")

@cli.command()
@click.option('--days', '-d', default=30, help='Days to keep')
def cleanup_results(days: int):
    """Clean up old task results."""
    # This would connect to Redis and clean old results
    click.echo(f"Cleaning results older than {days} days...")
    # Implementation depends on your result backend configuration

if __name__ == '__main__':
    cli()