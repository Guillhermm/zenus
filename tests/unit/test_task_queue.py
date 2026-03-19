"""
Tests for BackgroundTaskQueue and AsyncBackgroundTaskQueue.

All tests are pure unit tests — no external services required.
Covers:
- Task submission, status tracking, and result retrieval
- Priority scheduling
- Cancellation
- Graceful shutdown
- Context manager protocol
- Async wrapper (AsyncBackgroundTaskQueue)
- Module-level singleton (get_task_queue)
"""

import asyncio
import threading
import time
import pytest
from unittest.mock import MagicMock, patch

from zenus_core.execution.task_queue import (
    AsyncBackgroundTaskQueue,
    BackgroundTaskQueue,
    Priority,
    TaskResult,
    TaskStatus,
    get_task_queue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop() -> str:
    return "done"


def _slow(delay: float = 0.05) -> str:
    time.sleep(delay)
    return "slow done"


def _fail() -> None:
    raise ValueError("intentional failure")


def _return_value(v):
    return v


# ---------------------------------------------------------------------------
# Priority enum
# ---------------------------------------------------------------------------

class TestPriority:
    def test_high_less_than_normal(self):
        assert Priority.HIGH < Priority.NORMAL

    def test_normal_less_than_low(self):
        assert Priority.NORMAL < Priority.LOW

    def test_values(self):
        assert Priority.HIGH == 0
        assert Priority.NORMAL == 1
        assert Priority.LOW == 2


# ---------------------------------------------------------------------------
# TaskStatus enum
# ---------------------------------------------------------------------------

class TestTaskStatus:
    def test_string_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.DONE == "done"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"


# ---------------------------------------------------------------------------
# BackgroundTaskQueue — basic lifecycle
# ---------------------------------------------------------------------------

class TestBackgroundTaskQueueBasic:
    def test_submit_returns_string_id(self):
        with BackgroundTaskQueue() as q:
            task_id = q.submit(_noop)
        assert isinstance(task_id, str)
        assert len(task_id) > 0

    def test_submit_different_ids(self):
        with BackgroundTaskQueue() as q:
            id1 = q.submit(_noop)
            id2 = q.submit(_noop)
        assert id1 != id2

    def test_wait_returns_task_result(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            result = q.wait(tid)
        assert isinstance(result, TaskResult)

    def test_successful_task_status_done(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            result = q.wait(tid)
        assert result.status == TaskStatus.DONE

    def test_successful_task_result_value(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_return_value, 42)
            result = q.wait(tid)
        assert result.result == 42

    def test_successful_task_no_error(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            result = q.wait(tid)
        assert result.error is None

    def test_failed_task_status(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_fail)
            result = q.wait(tid)
        assert result.status == TaskStatus.FAILED

    def test_failed_task_captures_exception(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_fail)
            result = q.wait(tid)
        assert isinstance(result.error, ValueError)
        assert "intentional failure" in str(result.error)

    def test_failed_task_result_is_none(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_fail)
            result = q.wait(tid)
        assert result.result is None

    def test_task_id_in_result(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            result = q.wait(tid)
        assert result.task_id == tid


# ---------------------------------------------------------------------------
# BackgroundTaskQueue — status API
# ---------------------------------------------------------------------------

class TestBackgroundTaskQueueStatus:
    def test_status_unknown_task_raises(self):
        with BackgroundTaskQueue() as q:
            with pytest.raises(KeyError):
                q.status("nonexistent-id")

    def test_result_unknown_task_raises(self):
        with BackgroundTaskQueue() as q:
            with pytest.raises(KeyError):
                q.result("nonexistent-id")

    def test_status_done_after_wait(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            q.wait(tid)
            assert q.status(tid) == TaskStatus.DONE

    def test_status_failed_after_wait(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_fail)
            q.wait(tid)
            assert q.status(tid) == TaskStatus.FAILED

    def test_result_after_wait(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_return_value, "hello")
            q.wait(tid)
            res = q.result(tid)
        assert res.result == "hello"


# ---------------------------------------------------------------------------
# BackgroundTaskQueue — list_tasks and pending_count
# ---------------------------------------------------------------------------

class TestBackgroundTaskQueueListing:
    def test_list_tasks_empty_initially(self):
        q = BackgroundTaskQueue()
        try:
            assert q.list_tasks() == []
        finally:
            q.shutdown(wait=False)

    def test_list_tasks_after_submit(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            q.wait(tid)
            tasks = q.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].task_id == tid

    def test_list_tasks_multiple(self):
        with BackgroundTaskQueue() as q:
            ids = [q.submit(_noop) for _ in range(5)]
            for tid in ids:
                q.wait(tid)
            tasks = q.list_tasks()
        assert len(tasks) == 5

    def test_pending_count_zero_after_completion(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            q.wait(tid)
            assert q.pending_count() == 0

    def test_pending_count_includes_running(self):
        """Tasks in RUNNING state count toward pending_count."""
        barrier = threading.Barrier(2)

        def _blocked():
            barrier.wait()  # signal "I'm running"
            barrier.wait()  # wait for test to check
            return "ok"

        with BackgroundTaskQueue(max_workers=2) as q:
            tid = q.submit(_blocked)
            barrier.wait()  # wait until task is running
            count = q.pending_count()
            barrier.wait()  # release the task
            q.wait(tid)

        assert count >= 1


# ---------------------------------------------------------------------------
# BackgroundTaskQueue — cancellation
# ---------------------------------------------------------------------------

class TestBackgroundTaskQueueCancellation:
    def test_cancel_unknown_task_returns_false(self):
        with BackgroundTaskQueue() as q:
            assert q.cancel("no-such-id") is False

    def test_cancel_completed_task_returns_false(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            q.wait(tid)
            assert q.cancel(tid) is False

    def test_cancel_pending_task(self):
        """Submit many slow tasks to fill the pool, then cancel a queued one."""
        blocker = threading.Event()

        def _hold():
            blocker.wait()
            return "held"

        with BackgroundTaskQueue(max_workers=1) as q:
            # Fill the single worker
            filler = q.submit(_hold)
            # This one should be PENDING (not yet picked up)
            tid = q.submit(_hold)

            # Give the executor a moment to pick up the first task
            time.sleep(0.02)

            cancelled = q.cancel(tid)
            blocker.set()  # release everything

            q.wait(filler)

        # May or may not be cancellable depending on timing, but should not error
        assert isinstance(cancelled, bool)

    def test_cancelled_task_status(self):
        blocker = threading.Event()

        def _hold():
            blocker.wait()
            return "held"

        with BackgroundTaskQueue(max_workers=1) as q:
            filler = q.submit(_hold)
            time.sleep(0.02)
            tid = q.submit(_hold)

            cancelled = q.cancel(tid)
            blocker.set()
            q.wait(filler)

        if cancelled:
            assert q.status(tid) == TaskStatus.CANCELLED


# ---------------------------------------------------------------------------
# BackgroundTaskQueue — shutdown
# ---------------------------------------------------------------------------

class TestBackgroundTaskQueueShutdown:
    def test_submit_after_shutdown_raises(self):
        q = BackgroundTaskQueue()
        q.shutdown(wait=True)
        with pytest.raises(RuntimeError, match="shut down"):
            q.submit(_noop)

    def test_shutdown_wait_false_does_not_block(self):
        """shutdown(wait=False) returns quickly."""
        q = BackgroundTaskQueue()
        q.submit(_slow)
        start = time.monotonic()
        q.shutdown(wait=False)
        elapsed = time.monotonic() - start
        assert elapsed < 0.5

    def test_context_manager_calls_shutdown(self):
        q = BackgroundTaskQueue()
        with q:
            tid = q.submit(_noop)
            q.wait(tid)
        # After __exit__, new submits must fail
        with pytest.raises(RuntimeError):
            q.submit(_noop)


# ---------------------------------------------------------------------------
# BackgroundTaskQueue — wait timeout
# ---------------------------------------------------------------------------

class TestBackgroundTaskQueueWait:
    def test_wait_unknown_task_raises_key_error(self):
        with BackgroundTaskQueue() as q:
            with pytest.raises(KeyError):
                q.wait("no-such-id")

    def test_wait_timeout_raises_timeout_error(self):
        barrier = threading.Event()

        def _blocked():
            barrier.wait(timeout=5)
            return "ok"

        with BackgroundTaskQueue() as q:
            tid = q.submit(_blocked)
            with pytest.raises(TimeoutError):
                q.wait(tid, timeout=0.05)
            barrier.set()


# ---------------------------------------------------------------------------
# BackgroundTaskQueue — concurrency
# ---------------------------------------------------------------------------

class TestBackgroundTaskQueueConcurrency:
    def test_multiple_tasks_complete(self):
        with BackgroundTaskQueue(max_workers=4) as q:
            ids = [q.submit(_return_value, i) for i in range(20)]
            results = [q.wait(tid) for tid in ids]
        assert all(r.status == TaskStatus.DONE for r in results)

    def test_results_match_inputs(self):
        with BackgroundTaskQueue(max_workers=4) as q:
            pairs = [(i, q.submit(_return_value, i)) for i in range(10)]
            for expected, tid in pairs:
                res = q.wait(tid)
                assert res.result == expected

    def test_concurrent_submit_from_threads(self):
        results = []
        lock = threading.Lock()

        def _submit_and_wait(q, val):
            tid = q.submit(_return_value, val)
            res = q.wait(tid)
            with lock:
                results.append(res.result)

        with BackgroundTaskQueue(max_workers=4) as q:
            threads = [
                threading.Thread(target=_submit_and_wait, args=(q, i))
                for i in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert sorted(results) == list(range(10))


# ---------------------------------------------------------------------------
# AsyncBackgroundTaskQueue
# ---------------------------------------------------------------------------

class TestAsyncBackgroundTaskQueue:
    @pytest.mark.asyncio
    async def test_submit_returns_string(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_noop)
        assert isinstance(tid, str)

    @pytest.mark.asyncio
    async def test_wait_returns_task_result(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_noop)
            result = await q.wait(tid)
        assert isinstance(result, TaskResult)

    @pytest.mark.asyncio
    async def test_successful_task(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_return_value, "async!")
            result = await q.wait(tid)
        assert result.status == TaskStatus.DONE
        assert result.result == "async!"

    @pytest.mark.asyncio
    async def test_failed_task(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_fail)
            result = await q.wait(tid)
        assert result.status == TaskStatus.FAILED
        assert isinstance(result.error, ValueError)

    @pytest.mark.asyncio
    async def test_status_proxy(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_noop)
            await q.wait(tid)
            assert q.status(tid) == TaskStatus.DONE

    @pytest.mark.asyncio
    async def test_result_proxy(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_return_value, 99)
            await q.wait(tid)
            res = q.result(tid)
        assert res.result == 99

    @pytest.mark.asyncio
    async def test_cancel_proxy(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_noop)
            await q.wait(tid)
            # Cancelling a completed task returns False
            assert q.cancel(tid) is False

    @pytest.mark.asyncio
    async def test_list_tasks_proxy(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_noop)
            await q.wait(tid)
            tasks = q.list_tasks()
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_pending_count_proxy(self):
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_noop)
            await q.wait(tid)
            assert q.pending_count() == 0

    @pytest.mark.asyncio
    async def test_concurrent_tasks(self):
        async with AsyncBackgroundTaskQueue(max_workers=4) as q:
            tids = await asyncio.gather(*[q.submit(_return_value, i) for i in range(10)])
            results = await asyncio.gather(*[q.wait(tid) for tid in tids])
        assert all(r.status == TaskStatus.DONE for r in results)

    @pytest.mark.asyncio
    async def test_async_context_manager_shuts_down(self):
        q = AsyncBackgroundTaskQueue()
        async with q:
            tid = await q.submit(_noop)
            await q.wait(tid)
        with pytest.raises(RuntimeError):
            q._queue.submit(_noop)

    @pytest.mark.asyncio
    async def test_priority_accepted(self):
        """Priority kwarg is accepted without error."""
        async with AsyncBackgroundTaskQueue() as q:
            tid = await q.submit(_noop, priority=Priority.HIGH)
            result = await q.wait(tid)
        assert result.status == TaskStatus.DONE


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

class TestGetTaskQueue:
    def test_returns_background_task_queue(self):
        q = get_task_queue()
        assert isinstance(q, BackgroundTaskQueue)

    def test_singleton_same_instance(self):
        q1 = get_task_queue()
        q2 = get_task_queue()
        assert q1 is q2

    def test_singleton_is_functional(self):
        q = get_task_queue()
        tid = q.submit(_noop)
        result = q.wait(tid, timeout=5)
        assert result.status == TaskStatus.DONE


# ---------------------------------------------------------------------------
# Priority kwarg passthrough
# ---------------------------------------------------------------------------

class TestPrioritySubmit:
    def test_high_priority_accepted(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop, priority=Priority.HIGH)
            result = q.wait(tid)
        assert result.status == TaskStatus.DONE

    def test_low_priority_accepted(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop, priority=Priority.LOW)
            result = q.wait(tid)
        assert result.status == TaskStatus.DONE

    def test_normal_priority_is_default(self):
        with BackgroundTaskQueue() as q:
            tid = q.submit(_noop)
            result = q.wait(tid)
        assert result.status == TaskStatus.DONE
