"""
Change Detection API Endpoints

RESTful API endpoints for accessing change detection data and metrics.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from src.database.connection import get_db
from src.database.models import ChangeEvent, ScraperRun, ContentSnapshot
from src.core.exceptions import TrustCheckError

# ======================== ROUTER SETUP ========================

router = APIRouter(prefix="/api/v1/change-detection", tags=["Change Detection"])
logger = logging.getLogger(__name__)

# ======================== CHANGE EVENTS ENDPOINTS ========================

@router.get("/changes")
async def get_change_events(
    source: Optional[str] = Query(None, description="Filter by source (e.g., 'us_ofac')"),
    change_type: Optional[str] = Query(None, description="Filter by change type (ADDED, MODIFIED, REMOVED)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (CRITICAL, HIGH, MEDIUM, LOW)"),
    days: int = Query(7, description="Number of days to look back", ge=1, le=90),
    limit: int = Query(50, description="Maximum results to return", ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get recent change events with filtering and pagination.
    
    Returns a list of detected changes in sanctions data.
    """
    try:
        # Build query with filters
        query = db.query(ChangeEvent)
        
        # Date filter
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(ChangeEvent.detected_at >= cutoff_date)
        
        # Source filter
        if source:
            query = query.filter(ChangeEvent.source == source.upper())
        
        # Change type filter
        if change_type:
            if change_type.upper() not in ['ADDED', 'MODIFIED', 'REMOVED']:
                raise HTTPException(status_code=400, detail="Invalid change_type")
            query = query.filter(ChangeEvent.change_type == change_type.upper())
        
        # Risk level filter
        if risk_level:
            if risk_level.upper() not in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                raise HTTPException(status_code=400, detail="Invalid risk_level")
            query = query.filter(ChangeEvent.risk_level == risk_level.upper())
        
        # Order and limit
        query = query.order_by(desc(ChangeEvent.detected_at))
        changes = query.limit(limit).all()
        
        # Format response
        result = []
        for change in changes:
            result.append({
                "event_id": str(change.event_id),
                "entity_uid": change.entity_uid,
                "entity_name": change.entity_name,
                "source": change.source,
                "change_type": change.change_type,
                "risk_level": change.risk_level,
                "change_summary": change.change_summary,
                "field_changes": change.field_changes or [],
                "detected_at": change.detected_at.isoformat(),
                "scraper_run_id": change.scraper_run_id,
                "notification_sent": change.notification_sent_at.isoformat() if change.notification_sent_at else None
            })
        
        return {
            "changes": result,
            "total_returned": len(result),
            "filters": {
                "source": source,
                "change_type": change_type,
                "risk_level": risk_level,
                "days": days
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching change events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch changes: {str(e)}")

@router.get("/changes/summary")
async def get_changes_summary(
    days: int = Query(7, description="Number of days to summarize", ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Get summary statistics of recent changes.
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Query for summary statistics
        summary_query = db.execute(text("""
            SELECT 
                source,
                change_type,
                risk_level,
                COUNT(*) as count
            FROM change_events 
            WHERE detected_at >= :cutoff_date
            GROUP BY source, change_type, risk_level
            ORDER BY source, change_type, risk_level
        """), {'cutoff_date': cutoff_date})
        
        # Process results
        by_source = {}
        by_risk = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        by_type = {'ADDED': 0, 'MODIFIED': 0, 'REMOVED': 0}
        total_changes = 0
        
        for row in summary_query:
            source, change_type, risk_level, count = row
            
            # By source
            if source not in by_source:
                by_source[source] = {'ADDED': 0, 'MODIFIED': 0, 'REMOVED': 0, 'total': 0}
            by_source[source][change_type] += count
            by_source[source]['total'] += count
            
            # By risk level
            by_risk[risk_level] += count
            
            # By change type
            by_type[change_type] += count
            
            total_changes += count
        
        return {
            "summary": {
                "total_changes": total_changes,
                "days": days,
                "period": f"{cutoff_date.strftime('%Y-%m-%d')} to {datetime.utcnow().strftime('%Y-%m-%d')}"
            },
            "by_source": by_source,
            "by_risk_level": by_risk,
            "by_change_type": by_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating changes summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

# ======================== SCRAPER RUN ENDPOINTS ========================

@router.get("/runs")
async def get_scraper_runs(
    source: Optional[str] = Query(None, description="Filter by source"),
    status: Optional[str] = Query(None, description="Filter by status (SUCCESS, FAILED, SKIPPED)"),
    limit: int = Query(20, description="Maximum results to return", ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get recent scraper runs with change detection metrics."""
    try:
        query = db.query(ScraperRun)
        
        if source:
            query = query.filter(ScraperRun.source == source.lower())
        
        if status:
            if status.upper() not in ['SUCCESS', 'FAILED', 'SKIPPED', 'RUNNING']:
                raise HTTPException(status_code=400, detail="Invalid status")
            query = query.filter(ScraperRun.status == status.upper())
        
        runs = query.order_by(desc(ScraperRun.started_at)).limit(limit).all()
        
        result = []
        for run in runs:
            result.append({
                "run_id": run.run_id,
                "source": run.source,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "duration_seconds": run.duration_seconds,
                "content_changed": run.content_changed,
                "entities_processed": run.entities_processed,
                "entities_added": run.entities_added,
                "entities_modified": run.entities_modified,
                "entities_removed": run.entities_removed,
                "change_summary": {
                    "critical": run.critical_changes,
                    "high": run.high_risk_changes,
                    "medium": run.medium_risk_changes,
                    "low": run.low_risk_changes
                },
                "performance": {
                    "download_ms": run.download_time_ms,
                    "parsing_ms": run.parsing_time_ms,
                    "diff_ms": run.diff_time_ms
                },
                "content_hash": run.content_hash,
                "error_message": run.error_message
            })
        
        return {
            "runs": result,
            "total_returned": len(result),
            "filters": {"source": source, "status": status},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching scraper runs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch runs: {str(e)}")

@router.get("/runs/{run_id}")
async def get_scraper_run_details(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific scraper run."""
    try:
        run = db.query(ScraperRun).filter(ScraperRun.run_id == run_id).first()
        
        if not run:
            raise HTTPException(status_code=404, detail="Scraper run not found")
        
        # Get associated changes
        changes = db.query(ChangeEvent).filter(
            ChangeEvent.scraper_run_id == run_id
        ).all()
        
        # Get content snapshot
        snapshot = db.query(ContentSnapshot).filter(
            ContentSnapshot.scraper_run_id == run_id
        ).first()
        
        return {
            "run_details": {
                "run_id": run.run_id,
                "source": run.source,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "duration_seconds": run.duration_seconds,
                "source_url": run.source_url,
                "content_changed": run.content_changed,
                "content_size_bytes": run.content_size_bytes,
                "content_hash": run.content_hash,
                "error_message": run.error_message,
                "retry_count": run.retry_count
            },
            "entity_metrics": {
                "processed": run.entities_processed,
                "added": run.entities_added,
                "modified": run.entities_modified,
                "removed": run.entities_removed
            },
            "change_metrics": {
                "critical": run.critical_changes,
                "high": run.high_risk_changes,
                "medium": run.medium_risk_changes,
                "low": run.low_risk_changes,
                "total": (run.critical_changes or 0) + (run.high_risk_changes or 0) + 
                        (run.medium_risk_changes or 0) + (run.low_risk_changes or 0)
            },
            "performance_metrics": {
                "download_ms": run.download_time_ms,
                "parsing_ms": run.parsing_time_ms,
                "diff_ms": run.diff_time_ms,
                "storage_ms": run.storage_time_ms
            },
            "changes": [
                {
                    "event_id": str(change.event_id),
                    "entity_name": change.entity_name,
                    "change_type": change.change_type,
                    "risk_level": change.risk_level,
                    "change_summary": change.change_summary,
                    "detected_at": change.detected_at.isoformat()
                }
                for change in changes
            ],
            "content_snapshot": {
                "snapshot_id": str(snapshot.snapshot_id) if snapshot else None,
                "content_hash": snapshot.content_hash if snapshot else None,
                "size_bytes": snapshot.content_size_bytes if snapshot else None
            } if snapshot else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching run details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch run details: {str(e)}")

# ======================== SYSTEM STATUS ENDPOINTS ========================

@router.get("/status")
async def get_change_detection_status(db: Session = Depends(get_db)):
    """Get overall change detection system status."""
    try:
        # Get recent activity
        last_24h = datetime.utcnow() - timedelta(hours=24)
        
        # Recent runs by source
        recent_runs_query = db.execute(text("""
            SELECT 
                source,
                status,
                COUNT(*) as count,
                MAX(started_at) as last_run
            FROM scraper_runs 
            WHERE started_at >= :since
            GROUP BY source, status
            ORDER BY source, status
        """), {'since': last_24h})
        
        # Recent changes count
        recent_changes_count = db.query(ChangeEvent).filter(
            ChangeEvent.detected_at >= last_24h
        ).count()
        
        # Critical changes in last 24h
        critical_changes = db.query(ChangeEvent).filter(
            ChangeEvent.detected_at >= last_24h,
            ChangeEvent.risk_level == 'CRITICAL'
        ).count()
        
        # Process run data
        sources_status = {}
        total_runs = 0
        
        for row in recent_runs_query:
            source, status, count, last_run = row
            
            if source not in sources_status:
                sources_status[source] = {'SUCCESS': 0, 'FAILED': 0, 'SKIPPED': 0, 'last_run': None}
            
            sources_status[source][status] = count
            sources_status[source]['last_run'] = last_run.isoformat() if last_run else None
            total_runs += count
        
        return {
            "system_status": "operational",
            "last_24_hours": {
                "total_runs": total_runs,
                "total_changes": recent_changes_count,
                "critical_changes": critical_changes
            },
            "sources": sources_status,
            "database": {
                "total_change_events": db.query(ChangeEvent).count(),
                "total_scraper_runs": db.query(ScraperRun).count(),
                "total_snapshots": db.query(ContentSnapshot).count()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")

# ======================== TRIGGER ENDPOINTS ========================

@router.post("/trigger/{source}")
async def trigger_change_detection(
    source: str,
    force: bool = Query(False, description="Force run even if content hasn't changed"),
    db: Session = Depends(get_db)
):
    """
    Manually trigger change detection for a specific source.
    
    This endpoint allows you to manually run change detection
    for testing or immediate updates.
    """
    try:
        from src.scrapers.registry import scraper_registry
        
        # Get scraper from registry
        scraper = scraper_registry.create_scraper(source.lower())
        if not scraper:
            available_scrapers = scraper_registry.list_available_scrapers()
            raise HTTPException(
                status_code=400,
                detail=f"Unknown scraper: {source}. Available: {available_scrapers}"
            )
        
        logger.info(f"Manually triggering change detection for {source} (force={force})")
        
        # For force mode, temporarily disable the hash check
        if force and hasattr(scraper, 'download_manager'):
            original_method = scraper.download_manager.should_skip_processing
            scraper.download_manager.should_skip_processing = lambda *args: False
        
        try:
            # Run the scraper with change detection
            result = scraper.scrape_and_store()
            
            return {
                "status": "completed",
                "source": source,
                "forced": force,
                "result": {
                    "status": result.status,
                    "entities_processed": result.entities_processed,
                    "entities_added": result.entities_added,
                    "entities_updated": result.entities_updated,
                    "entities_removed": result.entities_removed,
                    "duration_seconds": result.duration_seconds,
                    "error_message": result.error_message
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            # Restore original method if we modified it
            if force and hasattr(scraper, 'download_manager') and 'original_method' in locals():
                scraper.download_manager.should_skip_processing = original_method
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering change detection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger change detection: {str(e)}")