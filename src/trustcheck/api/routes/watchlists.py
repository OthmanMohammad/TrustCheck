"""
TrustCheck Watchlist and Alert API Routes.

Endpoints for managing watchlists, entries, and alerts.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from trustcheck.services.alerts import get_alert_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlists", tags=["Watchlists"])


# ==================== Request/Response Models ====================

class CreateWatchlistRequest(BaseModel):
    """Request to create a watchlist."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    webhook_url: str | None = None
    email_recipients: list[str] | None = None
    threshold: float = Field(0.80, ge=0.0, le=1.0)


class UpdateWatchlistRequest(BaseModel):
    """Request to update a watchlist."""
    name: str | None = None
    description: str | None = None
    webhook_url: str | None = None
    email_recipients: list[str] | None = None
    threshold: float | None = Field(None, ge=0.0, le=1.0)
    is_active: bool | None = None


class AddEntryRequest(BaseModel):
    """Request to add a watchlist entry."""
    name: str = Field(..., min_length=1, max_length=500)
    date_of_birth: str | None = None
    country: str | None = None
    reference_id: str | None = None


class BulkAddEntriesRequest(BaseModel):
    """Request to add multiple watchlist entries."""
    entries: list[AddEntryRequest]


# ==================== Watchlist Endpoints ====================

@router.post("")
async def create_watchlist(request: CreateWatchlistRequest) -> dict[str, Any]:
    """Create a new watchlist."""
    service = get_alert_service()

    watchlist_id = await service.create_watchlist(
        name=request.name,
        description=request.description,
        webhook_url=request.webhook_url,
        email_recipients=request.email_recipients,
        threshold=request.threshold,
    )

    return {
        "success": True,
        "watchlist_id": watchlist_id,
        "message": "Watchlist created",
    }


@router.get("")
async def list_watchlists(
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List watchlists."""
    service = get_alert_service()

    watchlists, total = await service.list_watchlists(
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "data": watchlists,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "returned": len(watchlists),
        },
    }


@router.get("/{watchlist_id}")
async def get_watchlist(watchlist_id: str) -> dict[str, Any]:
    """Get watchlist details."""
    service = get_alert_service()

    watchlist = await service.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return {
        "success": True,
        "data": watchlist,
    }


@router.put("/{watchlist_id}")
async def update_watchlist(
    watchlist_id: str,
    request: UpdateWatchlistRequest,
) -> dict[str, Any]:
    """Update a watchlist."""
    service = get_alert_service()

    updated = await service.update_watchlist(
        watchlist_id=watchlist_id,
        name=request.name,
        description=request.description,
        webhook_url=request.webhook_url,
        email_recipients=request.email_recipients,
        threshold=request.threshold,
        is_active=request.is_active,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return {
        "success": True,
        "message": "Watchlist updated",
    }


@router.delete("/{watchlist_id}")
async def delete_watchlist(watchlist_id: str) -> dict[str, Any]:
    """Delete a watchlist."""
    service = get_alert_service()

    deleted = await service.delete_watchlist(watchlist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return {
        "success": True,
        "message": "Watchlist deleted",
    }


# ==================== Entry Endpoints ====================

@router.post("/{watchlist_id}/entries")
async def add_watchlist_entry(
    watchlist_id: str,
    request: AddEntryRequest,
) -> dict[str, Any]:
    """Add an entry to a watchlist."""
    service = get_alert_service()

    # Verify watchlist exists
    watchlist = await service.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    entry_id = await service.add_watchlist_entry(
        watchlist_id=watchlist_id,
        name=request.name,
        date_of_birth=request.date_of_birth,
        country=request.country,
        reference_id=request.reference_id,
    )

    return {
        "success": True,
        "entry_id": entry_id,
        "message": "Entry added",
    }


@router.post("/{watchlist_id}/entries/bulk")
async def add_watchlist_entries_bulk(
    watchlist_id: str,
    request: BulkAddEntriesRequest,
) -> dict[str, Any]:
    """Add multiple entries to a watchlist."""
    service = get_alert_service()

    # Verify watchlist exists
    watchlist = await service.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    entries = [
        {
            "name": e.name,
            "date_of_birth": e.date_of_birth,
            "country": e.country,
            "reference_id": e.reference_id,
        }
        for e in request.entries
    ]

    count = await service.add_watchlist_entries_bulk(
        watchlist_id=watchlist_id,
        entries=entries,
    )

    return {
        "success": True,
        "entries_added": count,
        "message": f"Added {count} entries",
    }


@router.get("/{watchlist_id}/entries")
async def get_watchlist_entries(
    watchlist_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Get entries for a watchlist."""
    service = get_alert_service()

    # Verify watchlist exists
    watchlist = await service.get_watchlist(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    entries, total = await service.get_watchlist_entries(
        watchlist_id=watchlist_id,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "data": entries,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "returned": len(entries),
        },
    }


@router.delete("/{watchlist_id}/entries/{entry_id}")
async def delete_watchlist_entry(
    watchlist_id: str,
    entry_id: str,
) -> dict[str, Any]:
    """Delete a watchlist entry."""
    service = get_alert_service()

    deleted = await service.delete_watchlist_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")

    return {
        "success": True,
        "message": "Entry deleted",
    }


# ==================== Alert Endpoints ====================

alerts_router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@alerts_router.get("")
async def list_alerts(
    watchlist_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List alerts with optional filtering."""
    service = get_alert_service()

    alerts, total = await service.get_alerts(
        watchlist_id=watchlist_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "data": alerts,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "returned": len(alerts),
        },
    }


@alerts_router.post("/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str) -> dict[str, Any]:
    """Dismiss an alert."""
    service = get_alert_service()

    dismissed = await service.dismiss_alert(alert_id)
    if not dismissed:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {
        "success": True,
        "message": "Alert dismissed",
    }


@alerts_router.post("/send-notifications")
async def send_pending_notifications() -> dict[str, Any]:
    """Send notifications for pending alerts (webhooks, emails)."""
    service = get_alert_service()

    result = await service.send_pending_notifications()

    return {
        "success": True,
        "webhooks_sent": result["webhooks_sent"],
        "emails_sent": result["emails_sent"],
    }


@alerts_router.get("/digest")
async def get_alerts_digest(
    watchlist_id: str | None = Query(None),
) -> dict[str, Any]:
    """Get daily digest of alerts."""
    service = get_alert_service()

    digest = await service.get_daily_digest(watchlist_id=watchlist_id)

    return {
        "success": True,
        "data": digest,
    }
