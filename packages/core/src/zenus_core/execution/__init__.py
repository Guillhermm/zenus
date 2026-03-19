"""
Execution module

Parallel and optimized execution capabilities.
"""

from zenus_core.execution.parallel_executor import ParallelExecutor, get_parallel_executor, ResourceLimiter
from zenus_core.execution.task_queue import (
    BackgroundTaskQueue,
    AsyncBackgroundTaskQueue,
    Priority,
    TaskStatus,
    TaskResult,
    get_task_queue,
)
from zenus_core.execution.connection_pool import ConnectionPool, get_connection_pool

__all__ = [
    "ParallelExecutor",
    "get_parallel_executor",
    "ResourceLimiter",
    "BackgroundTaskQueue",
    "AsyncBackgroundTaskQueue",
    "Priority",
    "TaskStatus",
    "TaskResult",
    "get_task_queue",
    "ConnectionPool",
    "get_connection_pool",
]
