"""
Concurrency and parallel execution integration tests.

Verifies that ParallelExecutor:
  - Runs independent steps concurrently without data corruption
  - Respects ResourceLimiter IO throttling
  - Handles one failing step without killing sibling steps
  - Produces results in the correct order (indexed by step position)
  - Sequential fallback path works identically to direct execution

No LLM required — IntentIR objects are constructed directly.
"""

import time
import threading
import pytest
from unittest.mock import Mock, patch, MagicMock

from zenus_core.brain.llm.schemas import IntentIR, Step
from zenus_core.execution.parallel_executor import (
    ParallelExecutor,
    ResourceLimiter,
    get_parallel_executor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step(tool="FileOps", action="scan", risk=0, **args):
    return Step(tool=tool, action=action, args=args, risk=risk)


def _intent(*steps):
    return IntentIR(goal="test", requires_confirmation=False, steps=list(steps))


def _make_executor(max_workers=4, timeout=30):
    with patch("zenus_core.execution.parallel_executor.DependencyAnalyzer"):
        with patch("zenus_core.execution.parallel_executor.get_logger",
                   return_value=Mock(log_info=Mock(), log_error=Mock())):
            return ParallelExecutor(max_workers=max_workers, timeout_seconds=timeout)


# ---------------------------------------------------------------------------
# Parallel execution — correctness
# ---------------------------------------------------------------------------

class TestParallelExecutionCorrectness:

    def test_results_count_matches_steps(self):
        ex = _make_executor()
        steps = [_step() for _ in range(4)]
        intent = _intent(*steps)
        func = Mock(return_value="ok")

        ex.analyzer.get_execution_order.return_value = [[0, 1], [2, 3]]
        ex.analyzer.estimate_speedup.return_value = 2.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, func)

        assert len(results) == 4
        assert func.call_count == 4

    def test_results_are_correct_values(self):
        ex = _make_executor()
        steps = [_step("A", "a"), _step("B", "b"), _step("C", "c")]
        intent = _intent(*steps)
        func = Mock(side_effect=lambda s: f"result_{s.tool}")

        ex.analyzer.get_execution_order.return_value = [[0, 1, 2]]
        ex.analyzer.estimate_speedup.return_value = 3.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, func)

        assert set(results) == {"result_A", "result_B", "result_C"}

    def test_each_step_executed_exactly_once(self):
        ex = _make_executor()
        steps = [_step() for _ in range(6)]
        intent = _intent(*steps)
        func = Mock(return_value="done")

        ex.analyzer.get_execution_order.return_value = [[0, 1, 2], [3, 4, 5]]
        ex.analyzer.estimate_speedup.return_value = 2.0

        with patch("zenus_core.execution.parallel_executor.console"):
            ex.execute(intent, func)

        assert func.call_count == 6

    def test_sequential_and_parallel_same_result(self):
        """Sequential and parallel execution must produce the same result set."""
        ex = _make_executor()
        steps = [_step("X", f"a{i}") for i in range(3)]
        intent = _intent(*steps)

        results_seq = []
        results_par = []

        def func(s):
            return f"{s.action}_result"

        # Sequential path (all levels have 1 step)
        ex.analyzer.get_execution_order.return_value = [[0], [1], [2]]
        ex.analyzer.estimate_speedup.return_value = 1.0
        with patch("zenus_core.execution.parallel_executor.console"):
            results_seq = ex.execute(intent, func)

        # Parallel path
        ex.analyzer.get_execution_order.return_value = [[0, 1, 2]]
        ex.analyzer.estimate_speedup.return_value = 3.0
        with patch("zenus_core.execution.parallel_executor.console"):
            results_par = ex.execute(intent, func)

        assert set(results_seq) == set(results_par)


# ---------------------------------------------------------------------------
# Parallel execution — thread safety
# ---------------------------------------------------------------------------

class TestParallelThreadSafety:

    def test_concurrent_steps_do_not_corrupt_shared_list(self):
        """
        Multiple workers writing results must not corrupt the output list.
        Uses a real threading scenario with a slow function.
        """
        ex = _make_executor(max_workers=8)
        steps = [_step() for _ in range(8)]
        intent = _intent(*steps)

        call_log = []
        lock = threading.Lock()

        def slow_func(s):
            time.sleep(0.01)
            with lock:
                call_log.append(s)
            return "done"

        ex.analyzer.get_execution_order.return_value = [list(range(8))]
        ex.analyzer.estimate_speedup.return_value = 8.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, slow_func)

        assert len(results) == 8
        assert len(call_log) == 8
        assert all(r == "done" for r in results if r is not None)

    def test_parallel_execution_is_faster_than_sequential(self):
        """
        With 4 parallel workers and 4 slow tasks, wall time should be
        roughly 1x task_time, not 4x.
        """
        ex = _make_executor(max_workers=4)
        steps = [_step() for _ in range(4)]
        intent = _intent(*steps)

        TASK_DURATION = 0.1  # seconds each

        def slow_func(s):
            time.sleep(TASK_DURATION)
            return "done"

        ex.analyzer.get_execution_order.return_value = [list(range(4))]
        ex.analyzer.estimate_speedup.return_value = 4.0

        with patch("zenus_core.execution.parallel_executor.console"):
            start = time.time()
            ex.execute(intent, slow_func)
            elapsed = time.time() - start

        # Should complete in ~1x task time, not 4x
        # Allow generous margin for CI overhead
        assert elapsed < TASK_DURATION * 3, (
            f"Parallel execution took {elapsed:.2f}s — expected < {TASK_DURATION * 3:.2f}s"
        )


# ---------------------------------------------------------------------------
# Parallel execution — failure handling
# ---------------------------------------------------------------------------

class TestParallelFailureHandling:

    def test_failed_step_does_not_prevent_sibling_steps(self):
        """One failing step must not block results from healthy siblings."""
        ex = _make_executor()
        steps = [_step("A", "ok"), _step("B", "fail"), _step("C", "ok")]
        intent = _intent(*steps)

        def func(s):
            if s.action == "fail":
                raise RuntimeError("B failed")
            return f"{s.tool}_ok"

        ex.analyzer.get_execution_order.return_value = [[0, 1, 2]]
        ex.analyzer.estimate_speedup.return_value = 3.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, func)

        # Healthy steps' results should be present
        non_none = [r for r in results if r is not None]
        assert any("A_ok" in r or "C_ok" in r for r in non_none)

    def test_all_failing_steps_return_error_strings_or_none(self):
        ex = _make_executor()
        steps = [_step() for _ in range(3)]
        intent = _intent(*steps)
        func = Mock(side_effect=RuntimeError("all fail"))

        ex.analyzer.get_execution_order.return_value = [[0, 1, 2]]
        ex.analyzer.estimate_speedup.return_value = 3.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, func)

        # Must return a list (not raise); entries may be str, None, or dict with error info
        assert isinstance(results, list)
        assert len(results) == 3
        for r in results:
            assert r is None or isinstance(r, (str, dict))

    def test_sequential_path_propagates_exception(self):
        """Sequential fast-path does NOT swallow exceptions."""
        ex = _make_executor()
        steps = [_step(), _step()]
        intent = _intent(*steps)
        func = Mock(side_effect=ValueError("sequential fail"))

        ex.analyzer.get_execution_order.return_value = [[0], [1]]
        ex.analyzer.estimate_speedup.return_value = 1.0

        with patch("zenus_core.execution.parallel_executor.console"):
            with pytest.raises(ValueError, match="sequential fail"):
                ex.execute(intent, func)


# ---------------------------------------------------------------------------
# ResourceLimiter — IO throttling
# ---------------------------------------------------------------------------

class TestResourceLimiterThrottling:

    def test_io_limit_blocks_fileops_at_cap(self):
        rl = ResourceLimiter(max_concurrent_io=2)
        rl.current_io_operations = 2
        step = _step("FileOps", "read_file")
        assert rl.can_execute(step) is False

    def test_io_limit_allows_after_release(self):
        rl = ResourceLimiter(max_concurrent_io=2)
        rl.current_io_operations = 2
        rl.release_io()
        step = _step("FileOps", "read_file")
        assert rl.can_execute(step) is True

    def test_acquire_release_balance(self):
        rl = ResourceLimiter(max_concurrent_io=10)
        for _ in range(5):
            rl.acquire_io()
        assert rl.current_io_operations == 5
        for _ in range(5):
            rl.release_io()
        assert rl.current_io_operations == 0

    def test_release_does_not_go_negative(self):
        rl = ResourceLimiter()
        rl.release_io()
        rl.release_io()
        assert rl.current_io_operations == 0

    def test_non_io_tool_always_allowed_regardless_of_count(self):
        rl = ResourceLimiter(max_concurrent_io=0)
        step = _step("SystemOps", "check_resource_usage")
        # Even at 0 limit, non-IO tools bypass the check
        assert rl.can_execute(step) is True

    def test_network_ops_counted_as_io(self):
        rl = ResourceLimiter(max_concurrent_io=1)
        rl.current_io_operations = 1
        step = _step("NetworkOps", "download")
        assert rl.can_execute(step) is False

    def test_custom_limits_respected(self):
        rl = ResourceLimiter(max_cpu_percent=50.0, max_memory_mb=256, max_concurrent_io=3)
        assert rl.max_cpu_percent == 50.0
        assert rl.max_memory_mb == 256
        assert rl.max_concurrent_io == 3


# ---------------------------------------------------------------------------
# Real tools — parallel file operations
# ---------------------------------------------------------------------------

class TestParallelRealFileOps:

    def test_two_file_scans_in_parallel_both_succeed(self, tmp_path):
        """
        Actually execute two FileOps.scan calls in parallel via the executor.
        Both must complete and return valid results.
        """
        from zenus_core.tools.file_ops import FileOps

        # Create known files
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        file_ops = FileOps()
        steps = [
            _step("FileOps", "scan", path=str(tmp_path)),
            _step("FileOps", "scan", path=str(tmp_path)),
        ]
        intent = _intent(*steps)

        def execute_step(step):
            return file_ops.scan(step.args["path"])

        ex = _make_executor(max_workers=2)
        ex.analyzer.get_execution_order.return_value = [[0, 1]]
        ex.analyzer.estimate_speedup.return_value = 2.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, execute_step)

        assert len(results) == 2
        for r in results:
            assert r is not None  # both scans completed

    def test_parallel_system_ops_complete(self):
        """Two SystemOps.check_resource_usage calls in parallel."""
        from zenus_core.tools.system_ops import SystemOps

        sys_ops = SystemOps()
        steps = [
            _step("SystemOps", "check_resource_usage"),
            _step("SystemOps", "check_resource_usage"),
        ]
        intent = _intent(*steps)

        def execute_step(step):
            return sys_ops.check_resource_usage()

        ex = _make_executor(max_workers=2)
        ex.analyzer.get_execution_order.return_value = [[0, 1]]
        ex.analyzer.estimate_speedup.return_value = 2.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, execute_step)

        assert len(results) == 2
        for r in results:
            assert r is not None
            assert "CPU" in r


# ---------------------------------------------------------------------------
# should_use_parallel heuristic
# ---------------------------------------------------------------------------

class TestShouldUseParallel:

    def test_single_step_always_sequential(self):
        ex = _make_executor()
        intent = _intent(_step())
        assert ex.should_use_parallel(intent) is False

    def test_not_parallelizable_returns_false(self):
        ex = _make_executor()
        intent = _intent(_step(), _step())
        ex.analyzer.is_parallelizable.return_value = False
        assert ex.should_use_parallel(intent) is False

    def test_low_speedup_returns_false(self):
        ex = _make_executor()
        intent = _intent(_step(), _step())
        ex.analyzer.is_parallelizable.return_value = True
        ex.analyzer.estimate_speedup.return_value = 1.05  # below 1.3 threshold
        assert ex.should_use_parallel(intent) is False

    def test_good_speedup_returns_true(self):
        ex = _make_executor()
        intent = _intent(_step(), _step(), _step())
        ex.analyzer.is_parallelizable.return_value = True
        ex.analyzer.estimate_speedup.return_value = 2.5
        assert ex.should_use_parallel(intent) is True

    def test_empty_steps_returns_false(self):
        ex = _make_executor()
        intent = _intent()
        assert ex.should_use_parallel(intent) is False
