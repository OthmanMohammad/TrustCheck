"""
TrustCheck Audit API Routes.

Endpoints for audit logs, compliance reports, and statistics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from trustcheck.services.audit import get_audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["Audit & Compliance"])


@router.get("/logs")
async def get_audit_logs(
    action: str | None = Query(None, description="Filter by action type"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    start_date: str | None = Query(None, description="Start date (ISO format)"),
    end_date: str | None = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Get audit logs with optional filtering."""
    service = get_audit_service()

    # Parse dates
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    logs, total = await service.get_audit_logs(
        action=action,
        resource_type=resource_type,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "data": logs,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "returned": len(logs),
        },
    }


@router.get("/stats")
async def get_screening_stats(
    start_date: str | None = Query(None, description="Start date (ISO format)"),
    end_date: str | None = Query(None, description="End date (ISO format)"),
) -> dict[str, Any]:
    """Get screening activity statistics."""
    service = get_audit_service()

    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    stats = await service.get_screening_stats(
        start_date=start_dt,
        end_date=end_dt,
    )

    return {
        "success": True,
        "data": stats,
    }


@router.post("/reports/screening")
async def generate_screening_report(
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)"),
    format: str = Query("csv", description="Output format (csv or json)"),
) -> dict[str, Any]:
    """
    Generate a screening activity report for a date range.

    Returns the path to download the generated report.
    """
    service = get_audit_service()

    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")

    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    filepath = await service.generate_screening_report(
        start_date=start_dt,
        end_date=end_dt,
        format=format,
    )

    return {
        "success": True,
        "message": "Report generated",
        "download_url": f"/api/audit/reports/download/{filepath.name}",
        "filename": filepath.name,
    }


@router.post("/reports/audit")
async def generate_audit_report(
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)"),
    format: str = Query("csv", description="Output format (csv or json)"),
) -> dict[str, Any]:
    """Generate an audit log report for a date range."""
    service = get_audit_service()

    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")

    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    filepath = await service.generate_audit_report(
        start_date=start_dt,
        end_date=end_dt,
        format=format,
    )

    return {
        "success": True,
        "message": "Report generated",
        "download_url": f"/api/audit/reports/download/{filepath.name}",
        "filename": filepath.name,
    }


@router.get("/reports/download/{filename}")
async def download_report(filename: str) -> FileResponse:
    """Download a generated report file."""
    service = get_audit_service()

    # Security: only allow alphanumeric, underscore, dash, and dot
    import re
    if not re.match(r"^[\w\-\.]+$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = service.export_dir / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    # Determine media type
    if filename.endswith(".csv"):
        media_type = "text/csv"
    elif filename.endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type=media_type,
    )


@router.get("/actions")
async def list_action_types() -> dict[str, Any]:
    """List available audit action types."""
    return {
        "success": True,
        "data": {
            "actions": [
                {"code": "SCREENING_SINGLE", "description": "Single name screening"},
                {"code": "SCREENING_BATCH", "description": "Batch screening job"},
                {"code": "ENTITY_VIEW", "description": "Entity detail viewed"},
                {"code": "ENTITY_SEARCH", "description": "Entity search performed"},
                {"code": "WATCHLIST_CREATE", "description": "Watchlist created"},
                {"code": "WATCHLIST_UPDATE", "description": "Watchlist updated"},
                {"code": "WATCHLIST_DELETE", "description": "Watchlist deleted"},
                {"code": "ALERT_DISMISS", "description": "Alert dismissed"},
                {"code": "EXPORT_GENERATE", "description": "Export file generated"},
            ],
            "resource_types": [
                "SCREENING",
                "ENTITY",
                "WATCHLIST",
                "ALERT",
                "REPORT",
                "BATCH_JOB",
            ],
        },
    }
