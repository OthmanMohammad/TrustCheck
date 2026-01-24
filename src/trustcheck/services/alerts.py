"""
TrustCheck Alert Service.

Handles watchlists, alerts, webhooks, and email notifications.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx

from trustcheck.database import get_session_context
from trustcheck.database.models import AlertModel, WatchlistEntryModel, WatchlistModel
from trustcheck.matching import normalize_name
from trustcheck.services.screening import ScreeningService

logger = logging.getLogger(__name__)


class AlertService:
    """Service for watchlist and alert operations."""

    def __init__(self) -> None:
        """Initialize alert service."""
        self.screening_service = ScreeningService()
        self.webhook_timeout = 30  # seconds

    # ==================== Watchlist Management ====================

    async def create_watchlist(
        self,
        name: str,
        description: str | None = None,
        webhook_url: str | None = None,
        email_recipients: list[str] | None = None,
        threshold: float = 0.80,
    ) -> str:
        """Create a new watchlist. Returns the watchlist ID."""
        watchlist_id = str(uuid4())

        async with get_session_context() as session:
            watchlist = WatchlistModel(
                id=watchlist_id,
                name=name,
                description=description,
                webhook_url=webhook_url,
                email_recipients=json.dumps(email_recipients) if email_recipients else None,
                threshold=threshold,
            )
            session.add(watchlist)
            await session.commit()

        logger.info(f"Created watchlist {watchlist_id}: {name}")
        return watchlist_id

    async def update_watchlist(
        self,
        watchlist_id: str,
        name: str | None = None,
        description: str | None = None,
        webhook_url: str | None = None,
        email_recipients: list[str] | None = None,
        threshold: float | None = None,
        is_active: bool | None = None,
    ) -> bool:
        """Update a watchlist. Returns True if updated."""
        from sqlalchemy import update

        async with get_session_context() as session:
            values = {}
            if name is not None:
                values["name"] = name
            if description is not None:
                values["description"] = description
            if webhook_url is not None:
                values["webhook_url"] = webhook_url
            if email_recipients is not None:
                values["email_recipients"] = json.dumps(email_recipients)
            if threshold is not None:
                values["threshold"] = threshold
            if is_active is not None:
                values["is_active"] = is_active

            if values:
                values["updated_at"] = datetime.utcnow()
                await session.execute(
                    update(WatchlistModel)
                    .where(WatchlistModel.id == watchlist_id)
                    .values(**values)
                )
                await session.commit()
                return True

        return False

    async def get_watchlist(self, watchlist_id: str) -> dict[str, Any] | None:
        """Get watchlist details."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async with get_session_context() as session:
            result = await session.execute(
                select(WatchlistModel)
                .options(selectinload(WatchlistModel.entries))
                .where(WatchlistModel.id == watchlist_id)
            )
            watchlist = result.scalar_one_or_none()

            if not watchlist:
                return None

            return {
                "id": watchlist.id,
                "name": watchlist.name,
                "description": watchlist.description,
                "is_active": watchlist.is_active,
                "webhook_url": watchlist.webhook_url,
                "email_recipients": json.loads(watchlist.email_recipients) if watchlist.email_recipients else [],
                "threshold": watchlist.threshold,
                "entry_count": len(watchlist.entries),
                "created_at": watchlist.created_at.isoformat() if watchlist.created_at else None,
                "updated_at": watchlist.updated_at.isoformat() if watchlist.updated_at else None,
            }

    async def list_watchlists(
        self,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List watchlists."""
        from sqlalchemy import select, func

        async with get_session_context() as session:
            stmt = select(WatchlistModel)

            if active_only:
                stmt = stmt.where(WatchlistModel.is_active.is_(True))

            # Count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0

            # Get results
            stmt = stmt.order_by(WatchlistModel.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            watchlists = result.scalars().all()

            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "is_active": w.is_active,
                    "threshold": w.threshold,
                    "created_at": w.created_at.isoformat() if w.created_at else None,
                }
                for w in watchlists
            ], total

    async def delete_watchlist(self, watchlist_id: str) -> bool:
        """Delete a watchlist and all its entries/alerts."""
        from sqlalchemy import delete

        async with get_session_context() as session:
            result = await session.execute(
                delete(WatchlistModel).where(WatchlistModel.id == watchlist_id)
            )
            await session.commit()
            return result.rowcount > 0

    # ==================== Watchlist Entries ====================

    async def add_watchlist_entry(
        self,
        watchlist_id: str,
        name: str,
        date_of_birth: str | None = None,
        country: str | None = None,
        reference_id: str | None = None,
    ) -> str:
        """Add an entry to a watchlist. Returns entry ID."""
        entry_id = str(uuid4())

        async with get_session_context() as session:
            entry = WatchlistEntryModel(
                id=entry_id,
                watchlist_id=watchlist_id,
                name=name,
                name_normalized=normalize_name(name),
                date_of_birth=date_of_birth,
                country=country,
                reference_id=reference_id,
            )
            session.add(entry)
            await session.commit()

        return entry_id

    async def add_watchlist_entries_bulk(
        self,
        watchlist_id: str,
        entries: list[dict[str, str]],
    ) -> int:
        """Add multiple entries to a watchlist. Returns count added."""
        async with get_session_context() as session:
            models = []
            for e in entries:
                if not e.get("name"):
                    continue
                models.append(WatchlistEntryModel(
                    id=str(uuid4()),
                    watchlist_id=watchlist_id,
                    name=e["name"],
                    name_normalized=normalize_name(e["name"]),
                    date_of_birth=e.get("dob") or e.get("date_of_birth"),
                    country=e.get("country"),
                    reference_id=e.get("reference_id") or e.get("id"),
                ))

            session.add_all(models)
            await session.commit()

            return len(models)

    async def get_watchlist_entries(
        self,
        watchlist_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get entries for a watchlist."""
        from sqlalchemy import select, func

        async with get_session_context() as session:
            stmt = select(WatchlistEntryModel).where(
                WatchlistEntryModel.watchlist_id == watchlist_id,
                WatchlistEntryModel.is_active.is_(True),
            )

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = stmt.order_by(WatchlistEntryModel.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            entries = result.scalars().all()

            return [
                {
                    "id": e.id,
                    "name": e.name,
                    "date_of_birth": e.date_of_birth,
                    "country": e.country,
                    "reference_id": e.reference_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ], total

    async def delete_watchlist_entry(self, entry_id: str) -> bool:
        """Delete a watchlist entry."""
        from sqlalchemy import delete

        async with get_session_context() as session:
            result = await session.execute(
                delete(WatchlistEntryModel).where(WatchlistEntryModel.id == entry_id)
            )
            await session.commit()
            return result.rowcount > 0

    # ==================== Alert Generation ====================

    async def check_watchlists_against_new_entities(
        self,
        entity_ids: list[str],
    ) -> list[str]:
        """
        Check new/modified entities against all active watchlists.
        Returns list of alert IDs created.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        alert_ids = []

        async with get_session_context() as session:
            # Get active watchlists with entries
            result = await session.execute(
                select(WatchlistModel)
                .options(selectinload(WatchlistModel.entries))
                .where(WatchlistModel.is_active.is_(True))
            )
            watchlists = result.scalars().all()

            if not watchlists:
                return []

            # Get entity names
            from trustcheck.database import EntityRepository
            repo = EntityRepository(session)

            for entity_id in entity_ids:
                entity = await repo.get_by_id(entity_id)
                if not entity:
                    continue

                # Check against each watchlist
                for watchlist in watchlists:
                    for entry in watchlist.entries:
                        if not entry.is_active:
                            continue

                        # Screen the watchlist entry against this entity
                        matches = await self.screening_service.screen_name(
                            name=entry.name,
                            date_of_birth=entry.date_of_birth,
                            country=entry.country,
                            threshold=watchlist.threshold,
                            max_results=1,
                        )

                        # Check if this entity matched
                        for match in matches:
                            if str(match.entity.id) == entity_id:
                                # Create alert
                                alert_id = await self._create_alert(
                                    watchlist_id=watchlist.id,
                                    entry_id=entry.id,
                                    entity_id=entity_id,
                                    entity_name=entity.primary_name,
                                    score=match.score,
                                    match_type=match.match_type.value,
                                    alert_type="NEW_MATCH",
                                )
                                alert_ids.append(alert_id)
                                break

        return alert_ids

    async def _create_alert(
        self,
        watchlist_id: str,
        entry_id: str,
        entity_id: str,
        entity_name: str,
        score: float,
        match_type: str,
        alert_type: str,
    ) -> str:
        """Create an alert record."""
        alert_id = str(uuid4())

        async with get_session_context() as session:
            alert = AlertModel(
                id=alert_id,
                watchlist_id=watchlist_id,
                watchlist_entry_id=entry_id,
                matched_entity_id=entity_id,
                matched_entity_name=entity_name,
                match_score=score,
                match_type=match_type,
                alert_type=alert_type,
                status="PENDING",
            )
            session.add(alert)
            await session.commit()

        logger.info(f"Created alert {alert_id} for watchlist {watchlist_id}")
        return alert_id

    # ==================== Alert Management ====================

    async def get_alerts(
        self,
        watchlist_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get alerts with optional filtering."""
        from sqlalchemy import select, func

        async with get_session_context() as session:
            stmt = select(AlertModel)

            if watchlist_id:
                stmt = stmt.where(AlertModel.watchlist_id == watchlist_id)
            if status:
                stmt = stmt.where(AlertModel.status == status)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = stmt.order_by(AlertModel.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            alerts = result.scalars().all()

            return [
                {
                    "id": a.id,
                    "watchlist_id": a.watchlist_id,
                    "watchlist_entry_id": a.watchlist_entry_id,
                    "matched_entity_id": a.matched_entity_id,
                    "matched_entity_name": a.matched_entity_name,
                    "match_score": a.match_score,
                    "match_type": a.match_type,
                    "alert_type": a.alert_type,
                    "status": a.status,
                    "webhook_sent": a.webhook_sent,
                    "email_sent": a.email_sent,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "notified_at": a.notified_at.isoformat() if a.notified_at else None,
                }
                for a in alerts
            ], total

    async def dismiss_alert(self, alert_id: str) -> bool:
        """Dismiss an alert."""
        from sqlalchemy import update

        async with get_session_context() as session:
            result = await session.execute(
                update(AlertModel)
                .where(AlertModel.id == alert_id)
                .values(status="DISMISSED", dismissed_at=datetime.utcnow())
            )
            await session.commit()
            return result.rowcount > 0

    # ==================== Notifications ====================

    async def send_pending_notifications(self) -> dict[str, int]:
        """Send notifications for pending alerts. Returns counts."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        webhook_count = 0
        email_count = 0

        async with get_session_context() as session:
            # Get pending alerts with watchlist info
            result = await session.execute(
                select(AlertModel)
                .options(selectinload(AlertModel.watchlist))
                .where(AlertModel.status == "PENDING")
                .limit(100)
            )
            alerts = result.scalars().all()

            for alert in alerts:
                watchlist = alert.watchlist

                # Send webhook if configured
                if watchlist.webhook_url and not alert.webhook_sent:
                    success = await self._send_webhook(watchlist.webhook_url, alert)
                    if success:
                        alert.webhook_sent = True
                        webhook_count += 1

                # TODO: Send email if configured
                # if watchlist.email_recipients and not alert.email_sent:
                #     success = await self._send_email(watchlist.email_recipients, alert)
                #     if success:
                #         alert.email_sent = True
                #         email_count += 1

                # Update alert status
                alert.status = "NOTIFIED"
                alert.notified_at = datetime.utcnow()

            await session.commit()

        return {"webhooks_sent": webhook_count, "emails_sent": email_count}

    async def _send_webhook(self, url: str, alert: AlertModel) -> bool:
        """Send webhook notification for an alert."""
        try:
            payload = {
                "alert_id": alert.id,
                "alert_type": alert.alert_type,
                "watchlist_id": alert.watchlist_id,
                "watchlist_entry_id": alert.watchlist_entry_id,
                "matched_entity": {
                    "id": alert.matched_entity_id,
                    "name": alert.matched_entity_name,
                },
                "match_score": alert.match_score,
                "match_type": alert.match_type,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            }

            async with httpx.AsyncClient(timeout=self.webhook_timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

            logger.info(f"Webhook sent for alert {alert.id} to {url}")
            return True

        except Exception as e:
            logger.error(f"Webhook failed for alert {alert.id}: {e}")
            return False

    async def get_daily_digest(
        self,
        watchlist_id: str | None = None,
    ) -> dict[str, Any]:
        """Get digest of alerts from the last 24 hours."""
        from sqlalchemy import select, func

        since = datetime.utcnow() - timedelta(days=1)

        async with get_session_context() as session:
            stmt = select(AlertModel).where(AlertModel.created_at >= since)

            if watchlist_id:
                stmt = stmt.where(AlertModel.watchlist_id == watchlist_id)

            result = await session.execute(stmt)
            alerts = result.scalars().all()

            # Group by status
            by_status = {}
            for a in alerts:
                by_status[a.status] = by_status.get(a.status, 0) + 1

            # Group by watchlist
            by_watchlist: dict[str, list] = {}
            for a in alerts:
                if a.watchlist_id not in by_watchlist:
                    by_watchlist[a.watchlist_id] = []
                by_watchlist[a.watchlist_id].append({
                    "id": a.id,
                    "matched_entity_name": a.matched_entity_name,
                    "match_score": a.match_score,
                    "alert_type": a.alert_type,
                })

            return {
                "period": "24h",
                "total_alerts": len(alerts),
                "by_status": by_status,
                "by_watchlist": by_watchlist,
                "since": since.isoformat(),
            }


# Global service instance
_alert_service: AlertService | None = None


def get_alert_service() -> AlertService:
    """Get the global alert service instance."""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service
