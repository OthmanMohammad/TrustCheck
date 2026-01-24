"""
TrustCheck Batch Screening API Routes.

Endpoints for batch screening operations (upload, status, download).
"""

import asyncio
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from trustcheck.progress import progress_tracker
from trustcheck.services.batch import get_batch_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch", tags=["Batch Screening"])


@router.post("/upload")
async def upload_batch(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    threshold: float = Query(0.80, ge=0.0, le=1.0, description="Match threshold"),
    start_processing: bool = Query(True, description="Start processing immediately"),
) -> dict[str, Any]:
    """
    Upload a CSV or Excel file for batch screening.

    The file should contain at minimum a 'name' column. Optional columns:
    - dob / date_of_birth: Date of birth
    - country / nationality: Country code
    - id / reference: Your reference ID

    Returns the job ID for status tracking.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    valid_extensions = [".csv", ".xlsx", ".xls"]
    if not any(file.filename.lower().endswith(ext) for ext in valid_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Supported: {', '.join(valid_extensions)}",
        )

    # Check file size (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB.")

    try:
        batch_service = get_batch_service()
        job_id = await batch_service.create_batch_job(
            file_content=content,
            filename=file.filename,
            threshold=threshold,
        )

        if start_processing:
            # Create progress task
            task_id = f"batch_{job_id}"
            await progress_tracker.create_task(task_id, f"Batch screening: {file.filename}")

            # Start background processing
            background_tasks.add_task(
                batch_service.process_batch_job,
                job_id=job_id,
                task_id=task_id,
            )

        return {
            "success": True,
            "job_id": job_id,
            "message": "Batch job created" + (" and processing started" if start_processing else ""),
            "status_url": f"/api/batch/{job_id}/status",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating batch job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create batch job")


@router.post("/{job_id}/start")
async def start_batch_processing(
    job_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Start processing a pending batch job."""
    batch_service = get_batch_service()

    status = await batch_service.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    if status["status"] != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be started (current status: {status['status']})",
        )

    # Create progress task
    task_id = f"batch_{job_id}"
    await progress_tracker.create_task(task_id, f"Batch screening: {status['filename']}")

    # Start background processing
    background_tasks.add_task(
        batch_service.process_batch_job,
        job_id=job_id,
        task_id=task_id,
    )

    return {
        "success": True,
        "message": "Processing started",
        "status_url": f"/api/batch/{job_id}/status",
    }


@router.get("/{job_id}/status")
async def get_batch_status(job_id: str) -> dict[str, Any]:
    """Get the status of a batch screening job."""
    batch_service = get_batch_service()

    status = await batch_service.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "success": True,
        "data": status,
    }


@router.get("/{job_id}/download")
async def download_batch_results(job_id: str) -> FileResponse:
    """Download the results CSV for a completed batch job."""
    batch_service = get_batch_service()

    result_path = await batch_service.get_result_file_path(job_id)
    if not result_path:
        raise HTTPException(
            status_code=404,
            detail="Results not available. Job may not be completed.",
        )

    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found")

    return FileResponse(
        path=str(result_path),
        filename=f"screening_results_{job_id}.csv",
        media_type="text/csv",
    )


@router.get("")
async def list_batch_jobs(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List batch screening jobs."""
    batch_service = get_batch_service()

    jobs, total = await batch_service.list_jobs(
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "data": jobs,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "returned": len(jobs),
        },
    }


@router.delete("/{job_id}")
async def delete_batch_job(job_id: str) -> dict[str, Any]:
    """Delete a batch job and its results."""
    batch_service = get_batch_service()

    status = await batch_service.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    # Don't allow deleting running jobs
    if status["status"] == "PROCESSING":
        raise HTTPException(status_code=400, detail="Cannot delete a running job")

    # Delete from database
    from trustcheck.database import get_session_context
    from trustcheck.database.models import BatchJobModel
    from sqlalchemy import delete

    async with get_session_context() as session:
        await session.execute(
            delete(BatchJobModel).where(BatchJobModel.id == job_id)
        )
        await session.commit()

    # Delete files
    import os
    for suffix in ["_input.csv", "_results.csv"]:
        filepath = batch_service.data_dir / f"{job_id}{suffix}"
        if filepath.exists():
            os.remove(filepath)

    return {
        "success": True,
        "message": "Batch job deleted",
    }
