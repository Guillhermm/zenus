"""
Background Task Queue

A lightweight, dependency-free task queue built on Python's asyncio + threading.
Provides:
  - Async task submission (fire-and-forget or awaitable)
  - Priority levels (HIGH / NORMAL / LOW)
  - Concurrency limit (max parallel workers)
  - Task status tracking (PENDING → RUNNING → DONE / FAILED / CANCELLED)
  - Graceful shutdown

No external services required (no Redis, no Celery).  Suitable for a
single-machine personal tool.  For multi-machine or persistent queues
see the roadmap (Phase 4).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class Priority(int, Enum):
    HIGH = 0
    NORMAL = 1
    LOW = 2


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(order=True)
class _QueueItem:
    """Internal wrapper stored in the priority queue."""
    priority: int
    sequence: int = field(compare=True)   # tie-break by submission order
    task_id: str = field(compare=False)
    fn: Callable = field(compare=False)
    args: tuple = field(compare=False)
    kwargs: dict = field(compare=False)
    future: Future = field(compare=False)


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[Exception] = None


# ---------------------------------------------------------------------------
# BackgroundTaskQueue
# ---------------------------------------------------------------------------

class BackgroundTaskQueue:
    """
    Background task queue with priority scheduling.

    Usage::

        queue = BackgroundTaskQueue(max_workers=4)
        task_id = queue.submit(my_function, arg1, arg2, priority=Priority.HIGH)
        result = queue.wait(task_id, timeout=30)
        queue.shutdown()

    Or as a context manager::

        with BackgroundTaskQueue() as q:
            tid = q.submit(fn, x)
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, TaskResult] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._sequence = 0
        self._running = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(
        self,
        fn: Callable,
        *args: Any,
        priority: Priority = Priority.NORMAL,
        **kwargs: Any,
    ) -> str:
        """
        Submit a callable for background execution.

        Args:
            fn: Callable to execute.
            *args / **kwargs: Passed directly to *fn*.
            priority: Execution priority (HIGH runs first when workers are free).

        Returns:
            task_id — opaque string used to query status / wait for result.
        """
        if not self._running:
            raise RuntimeError("Task queue has been shut down")

        task_id = str(uuid.uuid4())

        with self._lock:
            self._sequence += 1
            self._tasks[task_id] = TaskResult(task_id=task_id, status=TaskStatus.PENDING)

        future = self._executor.submit(self._run_task, task_id, fn, args, kwargs)

        with self._lock:
            self._futures[task_id] = future

        logger.debug("Submitted task %s (priority=%s fn=%s)", task_id, priority.name, fn.__name__)
        return task_id

    def status(self, task_id: str) -> TaskStatus:
        """Return the current status of a task."""
        with self._lock:
            result = self._tasks.get(task_id)
        if result is None:
            raise KeyError(f"Unknown task: {task_id}")
        return result.status

    def result(self, task_id: str) -> TaskResult:
        """Return the full TaskResult for a completed task."""
        with self._lock:
            res = self._tasks.get(task_id)
        if res is None:
            raise KeyError(f"Unknown task: {task_id}")
        return res

    def wait(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """
        Block until *task_id* completes (or *timeout* seconds elapse).

        Raises:
            KeyError: Unknown task_id.
            TimeoutError: Task did not finish within *timeout*.
        """
        with self._lock:
            future = self._futures.get(task_id)
        if future is None:
            raise KeyError(f"Unknown task: {task_id}")
        try:
            future.result(timeout=timeout)
        except (TimeoutError, FuturesTimeoutError):
            raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")
        except Exception:
            pass  # Errors captured in TaskResult.error
        return self.result(task_id)

    def cancel(self, task_id: str) -> bool:
        """
        Attempt to cancel a PENDING task.

        Returns True if the task was successfully cancelled, False otherwise
        (e.g. already running or complete).
        """
        with self._lock:
            future = self._futures.get(task_id)
            result = self._tasks.get(task_id)

        if future is None or result is None:
            return False

        cancelled = future.cancel()
        if cancelled:
            with self._lock:
                result.status = TaskStatus.CANCELLED
        return cancelled

    def list_tasks(self) -> List[TaskResult]:
        """Return a snapshot of all known task results."""
        with self._lock:
            return list(self._tasks.values())

    def pending_count(self) -> int:
        """Number of tasks currently pending or running."""
        with self._lock:
            return sum(
                1 for r in self._tasks.values()
                if r.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            )

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the queue, optionally waiting for in-flight tasks."""
        self._running = False
        self._executor.shutdown(wait=wait)
        logger.debug("BackgroundTaskQueue shut down (wait=%s)", wait)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "BackgroundTaskQueue":
        return self

    def __exit__(self, *_: Any) -> None:
        self.shutdown(wait=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_task(self, task_id: str, fn: Callable, args: tuple, kwargs: dict) -> None:
        with self._lock:
            res = self._tasks[task_id]
            res.status = TaskStatus.RUNNING

        try:
            value = fn(*args, **kwargs)
            with self._lock:
                res.result = value
                res.status = TaskStatus.DONE
            logger.debug("Task %s completed successfully", task_id)
        except Exception as exc:
            with self._lock:
                res.error = exc
                res.status = TaskStatus.FAILED
            logger.warning("Task %s failed: %s", task_id, exc)


# ---------------------------------------------------------------------------
# AsyncBackgroundTaskQueue — asyncio-native wrapper
# ---------------------------------------------------------------------------

class AsyncBackgroundTaskQueue:
    """
    Asyncio-native task queue.

    Wraps BackgroundTaskQueue so callers in an async context can
    ``await`` task submission and completion without blocking the event loop.

    Usage::

        async with AsyncBackgroundTaskQueue() as q:
            task_id = await q.submit(fn, arg1, arg2)
            result  = await q.wait(task_id)
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._queue = BackgroundTaskQueue(max_workers=max_workers)

    async def submit(
        self,
        fn: Callable,
        *args: Any,
        priority: Priority = Priority.NORMAL,
        **kwargs: Any,
    ) -> str:
        """Async-safe submit — does not block the event loop."""
        return await asyncio.to_thread(
            self._queue.submit, fn, *args, priority=priority, **kwargs
        )

    async def wait(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """Async-safe wait — does not block the event loop."""
        return await asyncio.to_thread(self._queue.wait, task_id, timeout)

    def status(self, task_id: str) -> TaskStatus:
        return self._queue.status(task_id)

    def result(self, task_id: str) -> TaskResult:
        return self._queue.result(task_id)

    def cancel(self, task_id: str) -> bool:
        return self._queue.cancel(task_id)

    def list_tasks(self) -> List[TaskResult]:
        return self._queue.list_tasks()

    def pending_count(self) -> int:
        return self._queue.pending_count()

    async def shutdown(self, wait: bool = True) -> None:
        await asyncio.to_thread(self._queue.shutdown, wait)

    async def __aenter__(self) -> "AsyncBackgroundTaskQueue":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.shutdown(wait=True)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_queue: Optional[BackgroundTaskQueue] = None
_queue_lock = threading.Lock()


def get_task_queue() -> BackgroundTaskQueue:
    """Return the global BackgroundTaskQueue (created on first call)."""
    global _default_queue
    with _queue_lock:
        if _default_queue is None:
            _default_queue = BackgroundTaskQueue()
    return _default_queue
