"""
Unit tests for execution/parallel_executor.py

DependencyAnalyzer is mocked to control execution order.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from zenus_core.execution.parallel_executor import (
    ParallelExecutor,
    ResourceLimiter,
    StepExecutionResult,
    get_parallel_executor,
)
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(tool="FileOps", action="scan", risk=0):
    return Step(tool=tool, action=action, args={}, risk=risk)


def _make_intent(steps=None):
    if steps is None:
        steps = [_make_step()]
    return IntentIR(
        goal="test",
        requires_confirmation=False,
        steps=steps
    )


def _make_executor(max_workers=4, timeout=30):
    with patch("zenus_core.execution.parallel_executor.DependencyAnalyzer"):
        with patch("zenus_core.execution.parallel_executor.get_logger", return_value=Mock(log_info=Mock(), log_error=Mock())):
            return ParallelExecutor(max_workers=max_workers, timeout_seconds=timeout)


# ===========================================================================
# StepExecutionResult
# ===========================================================================

class TestStepExecutionResult:

    def test_defaults(self):
        r = StepExecutionResult(step_index=0, success=True, result="ok")
        assert r.error is None
        assert r.duration_ms == 0

    def test_all_fields(self):
        r = StepExecutionResult(
            step_index=2,
            success=False,
            result=None,
            error=RuntimeError("fail"),
            duration_ms=500
        )
        assert r.step_index == 2
        assert r.success is False
        assert r.duration_ms == 500


# ===========================================================================
# ParallelExecutor init
# ===========================================================================

class TestParallelExecutorInit:

    def test_default_workers(self):
        ex = _make_executor()
        assert ex.max_workers == 4

    def test_custom_workers(self):
        ex = _make_executor(max_workers=8)
        assert ex.max_workers == 8

    def test_default_timeout(self):
        ex = _make_executor(timeout=60)
        assert ex.timeout_seconds == 60


# ===========================================================================
# ParallelExecutor.execute – empty / single step
# ===========================================================================

class TestParallelExecutorExecuteBasic:

    def test_empty_intent_returns_empty(self):
        ex = _make_executor()
        intent = _make_intent(steps=[])
        func = Mock()
        results = ex.execute(intent, func)
        assert results == []
        func.assert_not_called()

    def test_single_step_calls_func_once(self):
        ex = _make_executor()
        step = _make_step()
        intent = _make_intent(steps=[step])
        func = Mock(return_value="result")
        results = ex.execute(intent, func)
        func.assert_called_once_with(step)
        assert results == ["result"]


# ===========================================================================
# ParallelExecutor.execute – sequential fallback
# ===========================================================================

class TestParallelExecutorSequential:

    def test_all_sequential_executes_in_order(self):
        ex = _make_executor()
        steps = [_make_step("FileOps", "scan"), _make_step("ShellOps", "run")]
        intent = _make_intent(steps=steps)
        func = Mock(side_effect=["r1", "r2"])

        # No parallel levels (each level has 1 step)
        ex.analyzer.get_execution_order.return_value = [[0], [1]]
        ex.analyzer.estimate_speedup.return_value = 1.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, func)

        assert len(results) == 2
        assert func.call_count == 2

    def test_sequential_fast_path_propagates_error(self):
        # The all-sequential fast path does NOT swallow exceptions
        ex = _make_executor()
        steps = [_make_step(), _make_step()]
        intent = _make_intent(steps=steps)
        func = Mock(side_effect=Exception("step failed"))

        ex.analyzer.get_execution_order.return_value = [[0], [1]]
        ex.analyzer.estimate_speedup.return_value = 1.0

        with patch("zenus_core.execution.parallel_executor.console"):
            with pytest.raises(Exception, match="step failed"):
                ex.execute(intent, func)


# ===========================================================================
# ParallelExecutor.execute – parallel levels
# ===========================================================================

class TestParallelExecutorParallel:

    def test_parallel_level_executes_multiple(self):
        ex = _make_executor()
        steps = [_make_step("A", "a"), _make_step("B", "b"), _make_step("C", "c")]
        intent = _make_intent(steps=steps)
        func = Mock(side_effect=["ra", "rb", "rc"])

        # Level 0: steps 0 and 1 in parallel; Level 1: step 2 sequential
        ex.analyzer.get_execution_order.return_value = [[0, 1], [2]]
        ex.analyzer.estimate_speedup.return_value = 1.8

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, func)

        assert func.call_count == 3
        assert len(results) == 3

    def test_parallel_error_handled_gracefully(self):
        ex = _make_executor()
        steps = [_make_step(), _make_step()]
        intent = _make_intent(steps=steps)
        func = Mock(side_effect=Exception("all fail"))

        ex.analyzer.get_execution_order.return_value = [[0, 1]]
        ex.analyzer.estimate_speedup.return_value = 2.0

        with patch("zenus_core.execution.parallel_executor.console"):
            results = ex.execute(intent, func)

        # Both results should have error info
        for r in results:
            if r is not None:
                assert "error" in r


# ===========================================================================
# ParallelExecutor._execute_step_safe
# ===========================================================================

class TestExecuteStepSafe:

    def test_success_returns_result(self):
        ex = _make_executor()
        step = _make_step()
        func = Mock(return_value="done")
        result = ex._execute_step_safe(step, func)
        assert result == "done"

    def test_exception_re_raised(self):
        ex = _make_executor()
        step = _make_step()
        func = Mock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError):
            ex._execute_step_safe(step, func)

    def test_logs_completion(self):
        ex = _make_executor()
        step = _make_step()
        func = Mock(return_value="ok")
        ex._execute_step_safe(step, func)
        ex.logger.log_info.assert_called_once()

    def test_logs_error_on_failure(self):
        ex = _make_executor()
        step = _make_step()
        func = Mock(side_effect=RuntimeError("fail"))
        with pytest.raises(RuntimeError):
            ex._execute_step_safe(step, func)
        ex.logger.log_error.assert_called_once()


# ===========================================================================
# ParallelExecutor.should_use_parallel
# ===========================================================================

class TestShouldUseParallel:

    def test_single_step_returns_false(self):
        ex = _make_executor()
        intent = _make_intent(steps=[_make_step()])
        assert ex.should_use_parallel(intent) is False

    def test_not_parallelizable_returns_false(self):
        ex = _make_executor()
        steps = [_make_step(), _make_step()]
        intent = _make_intent(steps=steps)
        ex.analyzer.is_parallelizable.return_value = False
        assert ex.should_use_parallel(intent) is False

    def test_low_speedup_returns_false(self):
        ex = _make_executor()
        steps = [_make_step(), _make_step()]
        intent = _make_intent(steps=steps)
        ex.analyzer.is_parallelizable.return_value = True
        ex.analyzer.estimate_speedup.return_value = 1.1  # less than 1.3
        assert ex.should_use_parallel(intent) is False

    def test_high_speedup_returns_true(self):
        ex = _make_executor()
        steps = [_make_step(), _make_step()]
        intent = _make_intent(steps=steps)
        ex.analyzer.is_parallelizable.return_value = True
        ex.analyzer.estimate_speedup.return_value = 2.0
        assert ex.should_use_parallel(intent) is True


# ===========================================================================
# ParallelExecutor.visualize_execution_plan
# ===========================================================================

class TestVisualizeExecutionPlan:

    def test_delegates_to_analyzer(self):
        ex = _make_executor()
        intent = _make_intent()
        ex.analyzer.visualize.return_value = "Level 1: [step 0]"
        result = ex.visualize_execution_plan(intent)
        assert result == "Level 1: [step 0]"
        ex.analyzer.visualize.assert_called_once_with(intent)


# ===========================================================================
# ResourceLimiter
# ===========================================================================

class TestResourceLimiter:

    def test_defaults(self):
        rl = ResourceLimiter()
        assert rl.max_cpu_percent == 80.0
        assert rl.max_memory_mb == 1024
        assert rl.max_concurrent_io == 5
        assert rl.current_io_operations == 0

    def test_custom_params(self):
        rl = ResourceLimiter(max_cpu_percent=60.0, max_memory_mb=512, max_concurrent_io=3)
        assert rl.max_cpu_percent == 60.0
        assert rl.max_memory_mb == 512
        assert rl.max_concurrent_io == 3

    def test_can_execute_non_io_step(self):
        rl = ResourceLimiter()
        step = _make_step("ShellOps", "run_command")
        assert rl.can_execute(step) is True

    def test_can_execute_io_step_within_limit(self):
        rl = ResourceLimiter(max_concurrent_io=5)
        rl.current_io_operations = 3
        step = _make_step("FileOps", "read_file")
        assert rl.can_execute(step) is True

    def test_cannot_execute_io_step_at_limit(self):
        rl = ResourceLimiter(max_concurrent_io=2)
        rl.current_io_operations = 2
        step = _make_step("FileOps", "write_file")
        assert rl.can_execute(step) is False

    def test_acquire_io_increments(self):
        rl = ResourceLimiter()
        rl.acquire_io()
        rl.acquire_io()
        assert rl.current_io_operations == 2

    def test_release_io_decrements(self):
        rl = ResourceLimiter()
        rl.current_io_operations = 3
        rl.release_io()
        assert rl.current_io_operations == 2

    def test_release_io_does_not_go_below_zero(self):
        rl = ResourceLimiter()
        rl.release_io()  # already 0
        assert rl.current_io_operations == 0

    def test_io_intensive_file_ops(self):
        rl = ResourceLimiter()
        for action in ["read_file", "write_file", "copy_file", "move_file"]:
            step = _make_step("FileOps", action)
            assert rl._is_io_intensive(step) is True

    def test_io_intensive_network_ops(self):
        rl = ResourceLimiter()
        for action in ["download", "upload", "curl"]:
            step = _make_step("NetworkOps", action)
            assert rl._is_io_intensive(step) is True

    def test_io_intensive_browser_ops(self):
        rl = ResourceLimiter()
        for action in ["screenshot", "download"]:
            step = _make_step("BrowserOps", action)
            assert rl._is_io_intensive(step) is True

    def test_not_io_intensive_shell_ops(self):
        rl = ResourceLimiter()
        step = _make_step("ShellOps", "run_command")
        assert rl._is_io_intensive(step) is False

    def test_not_io_intensive_unknown_tool(self):
        rl = ResourceLimiter()
        step = _make_step("UnknownTool", "some_action")
        assert rl._is_io_intensive(step) is False


# ===========================================================================
# get_parallel_executor factory
# ===========================================================================

class TestGetParallelExecutor:

    def test_default_workers(self):
        with patch("zenus_core.execution.parallel_executor.DependencyAnalyzer"):
            with patch("zenus_core.execution.parallel_executor.get_logger", return_value=Mock(log_info=Mock())):
                ex = get_parallel_executor()
        assert ex.max_workers == 4
        assert ex.timeout_seconds == 300

    def test_custom_workers(self):
        with patch("zenus_core.execution.parallel_executor.DependencyAnalyzer"):
            with patch("zenus_core.execution.parallel_executor.get_logger", return_value=Mock(log_info=Mock())):
                ex = get_parallel_executor(max_workers=8, timeout_seconds=60)
        assert ex.max_workers == 8
        assert ex.timeout_seconds == 60

    def test_returns_parallel_executor_instance(self):
        with patch("zenus_core.execution.parallel_executor.DependencyAnalyzer"):
            with patch("zenus_core.execution.parallel_executor.get_logger", return_value=Mock(log_info=Mock())):
                ex = get_parallel_executor()
        assert isinstance(ex, ParallelExecutor)
