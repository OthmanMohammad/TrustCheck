"""
TrustCheck WebSocket Routes.

Provides real-time updates via WebSocket connections.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from trustcheck.progress import progress_tracker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/progress")
async def progress_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time progress updates.

    Clients connect to receive updates about scraping tasks
    and other long-running operations.
    """
    await websocket.accept()
    logger.info("WebSocket client connected for progress updates")

    queue = await progress_tracker.subscribe()

    try:
        while True:
            # Wait for progress updates
            try:
                update = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(update.to_dict())
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await progress_tracker.unsubscribe(queue)


@router.get("/api/progress/active")
async def get_active_tasks() -> dict:
    """Get all active (running) tasks."""
    tasks = await progress_tracker.get_active_tasks()
    return {
        "success": True,
        "tasks": [task.to_dict() for task in tasks],
    }


@router.get("/api/progress/{task_id}")
async def get_task_status(task_id: str) -> dict:
    """Get status of a specific task."""
    task = await progress_tracker.get_task(task_id)
    if task:
        return {
            "success": True,
            "task": task.to_dict(),
        }
    return {
        "success": False,
        "error": "Task not found",
    }
