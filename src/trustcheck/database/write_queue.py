"""
TrustCheck Database Write Queue.

Serializes write operations to avoid SQLite locking issues.
SQLite only allows one writer at a time - this queue ensures writes don't conflict.

NOTE: For production, use PostgreSQL instead of SQLite!
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class WriteQueue:
    """
    Serializes database write operations.

    SQLite has a single-writer limitation. This queue ensures only one
    write operation happens at a time, preventing "database is locked" errors.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[tuple[Callable[..., Awaitable[Any]], tuple, dict]] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the write queue worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Database write queue started")

    async def stop(self) -> None:
        """Stop the write queue worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Database write queue stopped")

    async def _worker(self) -> None:
        """Process queued write operations."""
        while self._running:
            try:
                func, args, kwargs = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                try:
                    await func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Write queue operation failed: {e}")
                finally:
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def enqueue(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Enqueue a write operation (fire and forget).

        Use this for operations where you don't need the result.
        """
        await self._queue.put((func, args, kwargs))

    @asynccontextmanager
    async def write_lock(self):
        """
        Context manager for exclusive write access.

        Use this when you need to ensure your write completes before continuing.
        """
        async with self._lock:
            yield


# Global write queue instance
_write_queue: WriteQueue | None = None


def get_write_queue() -> WriteQueue:
    """Get the global write queue instance."""
    global _write_queue
    if _write_queue is None:
        _write_queue = WriteQueue()
    return _write_queue


async def init_write_queue() -> None:
    """Initialize and start the write queue."""
    queue = get_write_queue()
    await queue.start()


async def close_write_queue() -> None:
    """Stop the write queue."""
    global _write_queue
    if _write_queue:
        await _write_queue.stop()
        _write_queue = None
