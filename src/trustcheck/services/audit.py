"""
TrustCheck Audit Service.

Handles audit logging, compliance reporting, and data export.
"""

import csv
import io
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from trustcheck.database import get_session_context
from trustcheck.database.models import AuditLogModel, ScreeningResultModel

logger = logging.getLogger(__name__)


class AuditService:
    """Service for audit logging and compliance reporting."""

    def __init__(self, export_dir: Path | None = None) -> None:
        """Initialize audit service."""
        self.export_dir = export_dir or Path("data/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)

    # ==================== Audit Logging ====================

    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_data: dict[str, Any] | None = None,
        response_summary: dict[str, Any] | None = None,
        status_code: int | None = None,
        duration_ms: float | None = None,
    ) -> str:
        """
        Log an audit action.

        Common actions:
        - SCREENING_SINGLE: Single name screening
        - SCREENING_BATCH: Batch screening job
        - ENTITY_VIEW: Entity detail viewed
        - ENTITY_SEARCH: Entity search performed
        - WATCHLIST_CREATE/UPDATE/DELETE: Watchlist operations
        - ALERT_DISMISS: Alert dismissed
        - EXPORT_GENERATE: Export file generated
        """
        log_id = str(uuid4())

        async with get_session_context() as session:
            log = AuditLogModel(
                id=log_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_data=json.dumps(request_data) if request_data else None,
                response_summary=json.dumps(response_summary) if response_summary else None,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            session.add(log)
            await session.commit()

        return log_id

    async def log_screening(
        self,
        request_id: str,
        query_name: str,
        query_normalized: str,
        matches: list[dict[str, Any]],
        processing_time_ms: float,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log a screening request and its results."""
        async with get_session_context() as session:
            # Log the screening request
            for match in matches:
                result = ScreeningResultModel(
                    id=str(uuid4()),
                    request_id=request_id,
                    query_name=query_name,
                    query_normalized=query_normalized,
                    matched_entity_id=match.get("entity_id"),
                    match_score=match.get("score", 0),
                    match_type=match.get("match_type", "UNKNOWN"),
                    matched_fields=json.dumps(match.get("matched_fields")),
                    processing_time_ms=processing_time_ms,
                )
                session.add(result)

            # Also create audit log entry
            audit = AuditLogModel(
                id=str(uuid4()),
                action="SCREENING_SINGLE",
                resource_type="SCREENING",
                resource_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_data=json.dumps({"query": query_name}),
                response_summary=json.dumps({
                    "match_count": len(matches),
                    "highest_score": max((m.get("score", 0) for m in matches), default=0),
                }),
                duration_ms=processing_time_ms,
            )
            session.add(audit)

            await session.commit()

    async def get_audit_logs(
        self,
        action: str | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get audit logs with filtering."""
        from sqlalchemy import select, func

        async with get_session_context() as session:
            stmt = select(AuditLogModel)

            if action:
                stmt = stmt.where(AuditLogModel.action == action)
            if resource_type:
                stmt = stmt.where(AuditLogModel.resource_type == resource_type)
            if start_date:
                stmt = stmt.where(AuditLogModel.created_at >= start_date)
            if end_date:
                stmt = stmt.where(AuditLogModel.created_at <= end_date)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = stmt.order_by(AuditLogModel.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            return [
                {
                    "id": log.id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "user_id": log.user_id,
                    "ip_address": log.ip_address,
                    "status_code": log.status_code,
                    "duration_ms": log.duration_ms,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ], total

    # ==================== Compliance Reports ====================

    async def generate_screening_report(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = "csv",
    ) -> Path:
        """
        Generate a screening activity report for a date range.

        Returns path to the generated file.
        """
        from sqlalchemy import select

        async with get_session_context() as session:
            # Get screening results in date range
            stmt = (
                select(ScreeningResultModel)
                .where(
                    ScreeningResultModel.screened_at >= start_date,
                    ScreeningResultModel.screened_at <= end_date,
                )
                .order_by(ScreeningResultModel.screened_at.desc())
            )
            result = await session.execute(stmt)
            results = result.scalars().all()

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"screening_report_{timestamp}.{format}"
        filepath = self.export_dir / filename

        if format == "csv":
            await self._write_screening_csv(results, filepath)
        elif format == "json":
            await self._write_screening_json(results, filepath)
        else:
            raise ValueError(f"Unsupported format: {format}")

        # Log the export
        await self.log_action(
            action="EXPORT_GENERATE",
            resource_type="REPORT",
            resource_id=str(filepath),
            response_summary={
                "report_type": "screening",
                "format": format,
                "record_count": len(results),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )

        return filepath

    async def _write_screening_csv(
        self,
        results: list[ScreeningResultModel],
        filepath: Path,
    ) -> None:
        """Write screening results to CSV."""
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Request ID",
                "Screened At",
                "Query Name",
                "Query Normalized",
                "Match Score",
                "Match Type",
                "Matched Entity ID",
                "Processing Time (ms)",
            ])

            for r in results:
                writer.writerow([
                    r.request_id,
                    r.screened_at.isoformat() if r.screened_at else "",
                    r.query_name,
                    r.query_normalized,
                    f"{r.match_score:.4f}",
                    r.match_type,
                    r.matched_entity_id or "",
                    f"{r.processing_time_ms:.2f}",
                ])

    async def _write_screening_json(
        self,
        results: list[ScreeningResultModel],
        filepath: Path,
    ) -> None:
        """Write screening results to JSON."""
        data = {
            "report_type": "screening_activity",
            "generated_at": datetime.utcnow().isoformat(),
            "total_records": len(results),
            "results": [
                {
                    "request_id": r.request_id,
                    "screened_at": r.screened_at.isoformat() if r.screened_at else None,
                    "query_name": r.query_name,
                    "query_normalized": r.query_normalized,
                    "match_score": r.match_score,
                    "match_type": r.match_type,
                    "matched_entity_id": r.matched_entity_id,
                    "processing_time_ms": r.processing_time_ms,
                }
                for r in results
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def generate_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = "csv",
    ) -> Path:
        """Generate an audit log report for a date range."""
        logs, _ = await self.get_audit_logs(
            start_date=start_date,
            end_date=end_date,
            limit=100000,  # Get all
        )

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_report_{timestamp}.{format}"
        filepath = self.export_dir / filename

        if format == "csv":
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ID",
                    "Timestamp",
                    "Action",
                    "Resource Type",
                    "Resource ID",
                    "User ID",
                    "IP Address",
                    "Status Code",
                    "Duration (ms)",
                ])

                for log in logs:
                    writer.writerow([
                        log["id"],
                        log["created_at"],
                        log["action"],
                        log["resource_type"],
                        log["resource_id"] or "",
                        log["user_id"] or "",
                        log["ip_address"] or "",
                        log["status_code"] or "",
                        log["duration_ms"] or "",
                    ])

        elif format == "json":
            data = {
                "report_type": "audit_log",
                "generated_at": datetime.utcnow().isoformat(),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_records": len(logs),
                "logs": logs,
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        return filepath

    async def get_screening_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Get screening activity statistics."""
        from sqlalchemy import select, func

        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        async with get_session_context() as session:
            # Total screenings
            total_stmt = (
                select(func.count(func.distinct(ScreeningResultModel.request_id)))
                .where(
                    ScreeningResultModel.screened_at >= start_date,
                    ScreeningResultModel.screened_at <= end_date,
                )
            )
            total_screenings = (await session.execute(total_stmt)).scalar() or 0

            # Total matches
            matches_stmt = (
                select(func.count())
                .where(
                    ScreeningResultModel.screened_at >= start_date,
                    ScreeningResultModel.screened_at <= end_date,
                    ScreeningResultModel.matched_entity_id.isnot(None),
                )
            )
            total_matches = (await session.execute(matches_stmt)).scalar() or 0

            # Average score
            avg_stmt = (
                select(func.avg(ScreeningResultModel.match_score))
                .where(
                    ScreeningResultModel.screened_at >= start_date,
                    ScreeningResultModel.screened_at <= end_date,
                    ScreeningResultModel.matched_entity_id.isnot(None),
                )
            )
            avg_score = (await session.execute(avg_stmt)).scalar() or 0

            # By match type
            type_stmt = (
                select(
                    ScreeningResultModel.match_type,
                    func.count(),
                )
                .where(
                    ScreeningResultModel.screened_at >= start_date,
                    ScreeningResultModel.screened_at <= end_date,
                )
                .group_by(ScreeningResultModel.match_type)
            )
            type_result = await session.execute(type_stmt)
            by_type = {row[0]: row[1] for row in type_result.all()}

            # Daily counts (last 7 days)
            daily_counts = []
            for i in range(7):
                day_start = (datetime.utcnow() - timedelta(days=i)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                day_end = day_start + timedelta(days=1)

                day_stmt = (
                    select(func.count(func.distinct(ScreeningResultModel.request_id)))
                    .where(
                        ScreeningResultModel.screened_at >= day_start,
                        ScreeningResultModel.screened_at < day_end,
                    )
                )
                count = (await session.execute(day_stmt)).scalar() or 0
                daily_counts.append({
                    "date": day_start.strftime("%Y-%m-%d"),
                    "count": count,
                })

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_screenings": total_screenings,
            "total_matches": total_matches,
            "average_match_score": round(avg_score, 4) if avg_score else 0,
            "by_match_type": by_type,
            "daily_counts": list(reversed(daily_counts)),
        }


# Global service instance
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """Get the global audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
