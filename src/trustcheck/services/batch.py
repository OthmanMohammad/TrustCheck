"""
TrustCheck Batch Screening Service.

Handles batch screening of names from CSV/Excel files with background processing.
"""

import asyncio
import csv
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from trustcheck.database import get_session_context
from trustcheck.database.models import BatchJobModel, BatchResultModel
from trustcheck.matching import normalize_name
from trustcheck.progress import progress_tracker
from trustcheck.services.screening import ScreeningService

logger = logging.getLogger(__name__)


class BatchScreeningService:
    """Service for batch screening operations."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize batch service."""
        self.data_dir = data_dir or Path("data/batch")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def create_batch_job(
        self,
        file_content: bytes,
        filename: str,
        threshold: float = 0.80,
    ) -> str:
        """
        Create a new batch screening job from uploaded file.

        Returns the job ID.
        """
        job_id = str(uuid4())

        # Parse the file to count records
        records = self._parse_file(file_content, filename)
        total_records = len(records)

        if total_records == 0:
            raise ValueError("No valid records found in file")

        # Save the file
        input_path = self.data_dir / f"{job_id}_input.csv"
        self._save_as_csv(records, input_path)

        # Create job record
        async with get_session_context() as session:
            job = BatchJobModel(
                id=job_id,
                filename=filename,
                status="PENDING",
                total_records=total_records,
                threshold=threshold,
            )
            session.add(job)
            await session.commit()

        logger.info(f"Created batch job {job_id} with {total_records} records")
        return job_id

    def _parse_file(self, content: bytes, filename: str) -> list[dict[str, str]]:
        """Parse CSV or Excel file into list of records."""
        records = []

        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            # Excel file
            try:
                import pandas as pd
                df = pd.read_excel(io.BytesIO(content))
                df.columns = [str(c).strip().lower() for c in df.columns]
                for _, row in df.iterrows():
                    record = self._extract_record(row)
                    if record:
                        records.append(record)
            except Exception as e:
                logger.error(f"Error parsing Excel file: {e}")
                raise ValueError(f"Failed to parse Excel file: {e}")

        elif filename.endswith(".csv"):
            # CSV file
            try:
                text = content.decode("utf-8-sig")  # Handle BOM
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    # Normalize column names
                    row = {k.strip().lower(): v for k, v in row.items()}
                    record = self._extract_record(row)
                    if record:
                        records.append(record)
            except UnicodeDecodeError:
                # Try latin-1
                text = content.decode("latin-1")
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    row = {k.strip().lower(): v for k, v in row.items()}
                    record = self._extract_record(row)
                    if record:
                        records.append(record)
        else:
            raise ValueError(f"Unsupported file format: {filename}")

        return records

    def _extract_record(self, row: dict[str, Any]) -> dict[str, str] | None:
        """Extract screening record from row."""
        # Find name column (try various common names)
        name_cols = ["name", "full_name", "fullname", "party_name", "customer_name", "entity_name", "person_name"]
        name = None
        for col in name_cols:
            if col in row and row[col]:
                val = str(row[col]).strip()
                if val and val.lower() not in ["nan", "none", "null", ""]:
                    name = val
                    break

        if not name:
            return None

        # Find DOB column
        dob_cols = ["dob", "date_of_birth", "dateofbirth", "birth_date", "birthdate"]
        dob = None
        for col in dob_cols:
            if col in row and row[col]:
                val = str(row[col]).strip()
                if val and val.lower() not in ["nan", "none", "null", ""]:
                    dob = val
                    break

        # Find country column
        country_cols = ["country", "nationality", "country_code", "nation"]
        country = None
        for col in country_cols:
            if col in row and row[col]:
                val = str(row[col]).strip()
                if val and val.lower() not in ["nan", "none", "null", ""]:
                    country = val
                    break

        # Find reference ID
        ref_cols = ["id", "reference", "ref", "customer_id", "party_id", "row_id"]
        ref = None
        for col in ref_cols:
            if col in row and row[col]:
                val = str(row[col]).strip()
                if val and val.lower() not in ["nan", "none", "null", ""]:
                    ref = val
                    break

        return {
            "name": name,
            "dob": dob or "",
            "country": country or "",
            "reference": ref or "",
        }

    def _save_as_csv(self, records: list[dict[str, str]], path: Path) -> None:
        """Save records to CSV file."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "dob", "country", "reference"])
            writer.writeheader()
            writer.writerows(records)

    async def process_batch_job(self, job_id: str, task_id: str | None = None) -> None:
        """Process a batch screening job in the background."""
        logger.info(f"Starting batch job processing: {job_id}")

        try:
            # Update status to PROCESSING
            async with get_session_context() as session:
                from sqlalchemy import select, update
                stmt = (
                    update(BatchJobModel)
                    .where(BatchJobModel.id == job_id)
                    .values(status="PROCESSING", started_at=datetime.utcnow())
                )
                await session.execute(stmt)
                await session.commit()

                # Get job details
                result = await session.execute(
                    select(BatchJobModel).where(BatchJobModel.id == job_id)
                )
                job = result.scalar_one()
                threshold = job.threshold
                total_records = job.total_records

            # Read input file
            input_path = self.data_dir / f"{job_id}_input.csv"
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            records = []
            with open(input_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                records = list(reader)

            # Process records
            screening_service = ScreeningService()
            results: list[BatchResultModel] = []
            matched_count = 0

            for i, record in enumerate(records):
                try:
                    # Update progress
                    if task_id:
                        progress = (i + 1) / total_records
                        await progress_tracker.update_progress(
                            task_id,
                            progress=progress,
                            message=f"Processing {i + 1}/{total_records}: {record['name'][:30]}...",
                        )

                    # Screen this record
                    matches = await screening_service.screen_name(
                        name=record["name"],
                        date_of_birth=record.get("dob") or None,
                        country=record.get("country") or None,
                        threshold=threshold,
                        max_results=10,
                    )

                    has_match = len(matches) > 0
                    if has_match:
                        matched_count += 1

                    best_match = matches[0] if matches else None

                    result = BatchResultModel(
                        id=str(uuid4()),
                        batch_job_id=job_id,
                        row_number=i + 1,
                        input_name=record["name"],
                        input_dob=record.get("dob") or None,
                        input_country=record.get("country") or None,
                        has_match=has_match,
                        best_match_score=best_match.score if best_match else None,
                        best_match_entity_id=str(best_match.entity.id) if best_match else None,
                        best_match_name=best_match.entity.primary_name if best_match else None,
                        match_count=len(matches),
                        all_matches=json.dumps([
                            {
                                "entity_id": str(m.entity.id),
                                "name": m.entity.primary_name,
                                "score": m.score,
                                "match_type": m.match_type.value,
                                "sources": [s.value for s in m.sources],
                            }
                            for m in matches
                        ]) if matches else None,
                    )
                    results.append(result)

                    # Batch save every 100 records
                    if len(results) >= 100:
                        async with get_session_context() as session:
                            session.add_all(results)
                            await session.execute(
                                update(BatchJobModel)
                                .where(BatchJobModel.id == job_id)
                                .values(
                                    processed_records=i + 1,
                                    matched_records=matched_count,
                                )
                            )
                            await session.commit()
                        results = []

                except Exception as e:
                    logger.warning(f"Error processing record {i}: {e}")
                    results.append(BatchResultModel(
                        id=str(uuid4()),
                        batch_job_id=job_id,
                        row_number=i + 1,
                        input_name=record["name"],
                        has_match=False,
                        match_count=0,
                    ))

            # Save remaining results
            if results:
                async with get_session_context() as session:
                    session.add_all(results)
                    await session.commit()

            # Generate result file
            result_path = await self._generate_result_file(job_id)

            # Update job as completed
            async with get_session_context() as session:
                await session.execute(
                    update(BatchJobModel)
                    .where(BatchJobModel.id == job_id)
                    .values(
                        status="COMPLETED",
                        completed_at=datetime.utcnow(),
                        processed_records=total_records,
                        matched_records=matched_count,
                        result_file=str(result_path),
                    )
                )
                await session.commit()

            if task_id:
                await progress_tracker.complete_task(
                    task_id,
                    success=True,
                    message=f"Completed: {matched_count}/{total_records} matches found",
                )

            logger.info(f"Batch job {job_id} completed: {matched_count}/{total_records} matches")

        except Exception as e:
            logger.error(f"Batch job {job_id} failed: {e}")
            async with get_session_context() as session:
                from sqlalchemy import update
                await session.execute(
                    update(BatchJobModel)
                    .where(BatchJobModel.id == job_id)
                    .values(
                        status="FAILED",
                        completed_at=datetime.utcnow(),
                        error_message=str(e),
                    )
                )
                await session.commit()

            if task_id:
                await progress_tracker.complete_task(
                    task_id,
                    success=False,
                    message=f"Failed: {e}",
                )

    async def _generate_result_file(self, job_id: str) -> Path:
        """Generate CSV result file for a completed batch job."""
        result_path = self.data_dir / f"{job_id}_results.csv"

        async with get_session_context() as session:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            result = await session.execute(
                select(BatchResultModel)
                .where(BatchResultModel.batch_job_id == job_id)
                .order_by(BatchResultModel.row_number)
            )
            results = result.scalars().all()

        with open(result_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Row",
                "Input Name",
                "Input DOB",
                "Input Country",
                "Has Match",
                "Match Count",
                "Best Match Score",
                "Best Match Name",
                "Best Match Entity ID",
                "All Matches (JSON)",
            ])

            for r in results:
                writer.writerow([
                    r.row_number,
                    r.input_name,
                    r.input_dob or "",
                    r.input_country or "",
                    "YES" if r.has_match else "NO",
                    r.match_count,
                    f"{r.best_match_score:.2%}" if r.best_match_score else "",
                    r.best_match_name or "",
                    r.best_match_entity_id or "",
                    r.all_matches or "",
                ])

        return result_path

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get status of a batch job."""
        async with get_session_context() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(BatchJobModel).where(BatchJobModel.id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                return None

            return {
                "id": job.id,
                "filename": job.filename,
                "status": job.status,
                "total_records": job.total_records,
                "processed_records": job.processed_records,
                "matched_records": job.matched_records,
                "threshold": job.threshold,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error_message": job.error_message,
                "result_file": job.result_file,
                "progress": job.processed_records / job.total_records if job.total_records > 0 else 0,
            }

    async def get_result_file_path(self, job_id: str) -> Path | None:
        """Get the path to the result file for a completed job."""
        async with get_session_context() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(BatchJobModel).where(BatchJobModel.id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job or job.status != "COMPLETED" or not job.result_file:
                return None

            return Path(job.result_file)

    async def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List batch jobs with optional filtering."""
        async with get_session_context() as session:
            from sqlalchemy import select, func

            stmt = select(BatchJobModel)

            if status:
                stmt = stmt.where(BatchJobModel.status == status)

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0

            # Get paginated results
            stmt = stmt.order_by(BatchJobModel.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            jobs = result.scalars().all()

            return [
                {
                    "id": j.id,
                    "filename": j.filename,
                    "status": j.status,
                    "total_records": j.total_records,
                    "processed_records": j.processed_records,
                    "matched_records": j.matched_records,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                    "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                }
                for j in jobs
            ], total


# Global service instance
_batch_service: BatchScreeningService | None = None


def get_batch_service() -> BatchScreeningService:
    """Get the global batch service instance."""
    global _batch_service
    if _batch_service is None:
        _batch_service = BatchScreeningService()
    return _batch_service
