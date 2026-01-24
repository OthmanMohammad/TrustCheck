"""
TrustCheck Progress Tracking.

Real-time progress tracking for long-running operations like scraping.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a tracked task."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressUpdate:
    """A single progress update."""
    task_id: str
    task_name: str
    status: TaskStatus
    progress: float  # 0.0 to 1.0
    message: str
    current_step: int = 0
    total_steps: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class ProgressTracker:
    """
    Tracks progress of long-running tasks and notifies listeners.

    Implements a pub/sub pattern for real-time progress updates.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, ProgressUpdate] = {}
        self._listeners: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._task_by_name: dict[str, str] = {}  # task_name -> task_id for deduplication

    async def create_task(self, task_name: str, total_steps: int = 0, deduplicate: bool = True) -> str:
        """
        Create a new tracked task.

        Args:
            task_name: Human-readable name for the task
            total_steps: Total number of steps (0 if unknown)
            deduplicate: If True, cancel any existing task with the same name

        Returns:
            Task ID for tracking
        """
        async with self._lock:
            # Check for existing task with same name and cancel it
            if deduplicate and task_name in self._task_by_name:
                existing_id = self._task_by_name[task_name]
                if existing_id in self._tasks:
                    existing = self._tasks[existing_id]
                    # If existing task is still running, mark it as cancelled
                    if existing.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                        existing.status = TaskStatus.CANCELLED
                        existing.message = "Superseded by new task"
                        existing.timestamp = datetime.utcnow()
                        # Notify about cancellation
                        for queue in self._listeners:
                            try:
                                queue.put_nowait(existing)
                            except asyncio.QueueFull:
                                pass
                        logger.info(f"Cancelled duplicate task: {task_name} ({existing_id})")

            task_id = str(uuid4())
            update = ProgressUpdate(
                task_id=task_id,
                task_name=task_name,
                status=TaskStatus.PENDING,
                progress=0.0,
                message="Task created",
                total_steps=total_steps,
            )

            self._tasks[task_id] = update
            self._task_by_name[task_name] = task_id

        await self._notify(update)
        return task_id

    async def start_task(self, task_id: str, message: str = "Starting...") -> None:
        """Mark a task as started."""
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].status = TaskStatus.RUNNING
                self._tasks[task_id].message = message
                self._tasks[task_id].timestamp = datetime.utcnow()
                await self._notify(self._tasks[task_id])

    async def update_progress(
        self,
        task_id: str,
        progress: float | None = None,
        message: str | None = None,
        current_step: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Update task progress.

        Args:
            task_id: Task ID
            progress: Progress value (0.0 to 1.0)
            message: Status message
            current_step: Current step number
            details: Additional details
        """
        async with self._lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]

            if progress is not None:
                task.progress = min(1.0, max(0.0, progress))
            if message is not None:
                task.message = message
            if current_step is not None:
                task.current_step = current_step
                # Auto-calculate progress if total_steps is known
                if task.total_steps > 0:
                    task.progress = current_step / task.total_steps
            if details is not None:
                task.details.update(details)

            task.timestamp = datetime.utcnow()
            await self._notify(task)

    async def complete_task(
        self,
        task_id: str,
        success: bool = True,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Mark a task as completed.

        Args:
            task_id: Task ID
            success: Whether the task succeeded
            message: Final message
            details: Final details
        """
        async with self._lock:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]
            task.status = TaskStatus.SUCCESS if success else TaskStatus.FAILED
            task.progress = 1.0 if success else task.progress
            task.message = message or ("Completed successfully" if success else "Failed")
            if details is not None:
                task.details.update(details)
            task.timestamp = datetime.utcnow()
            await self._notify(task)

    async def get_task(self, task_id: str) -> ProgressUpdate | None:
        """Get current state of a task."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def get_active_tasks(self) -> list[ProgressUpdate]:
        """Get all active (pending or running) tasks."""
        async with self._lock:
            return [
                task for task in self._tasks.values()
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            ]

    async def get_all_tasks(self) -> list[ProgressUpdate]:
        """Get all tracked tasks."""
        async with self._lock:
            return list(self._tasks.values())

    async def subscribe(self) -> asyncio.Queue:
        """
        Subscribe to progress updates.

        Returns:
            Queue that will receive ProgressUpdate objects
        """
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._listeners.append(queue)

        # Send current state of all active tasks
        for task in await self.get_active_tasks():
            await queue.put(task)

        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from progress updates."""
        async with self._lock:
            if queue in self._listeners:
                self._listeners.remove(queue)

    async def _notify(self, update: ProgressUpdate) -> None:
        """Notify all listeners of an update."""
        for queue in self._listeners:
            try:
                queue.put_nowait(update)
            except asyncio.QueueFull:
                logger.warning("Progress queue full, dropping update")

    async def cleanup_old_tasks(self, max_age_seconds: int = 300) -> None:
        """Remove completed/failed/cancelled tasks older than max_age_seconds (default 5 min)."""
        cutoff = datetime.utcnow()
        async with self._lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    age = (cutoff - task.timestamp).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append((task_id, task.task_name))

            for task_id, task_name in to_remove:
                del self._tasks[task_id]
                # Also clean up the name lookup if it points to this task
                if self._task_by_name.get(task_name) == task_id:
                    del self._task_by_name[task_name]

            if to_remove:
                logger.debug(f"Cleaned up {len(to_remove)} old tasks")


# Global progress tracker instance
progress_tracker = ProgressTracker()
