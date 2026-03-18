"""
Tests for AdaptivePlanner and SandboxedAdaptivePlanner
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call

from zenus_core.brain.llm.schemas import IntentIR, Step
from zenus_core.brain.adaptive_planner import AdaptivePlanner, ExecutionResult
from zenus_core.brain.sandboxed_planner import SandboxedAdaptivePlanner
from zenus_core.safety.policy import SafetyError
from zenus_core.sandbox.executor import SandboxViolation


def make_step(tool="FileOps", action="scan", args=None, risk=0) -> Step:
    """Build a Step with sensible defaults."""
    return Step(tool=tool, action=action, args=args or {"path": "/tmp"}, risk=risk)


def make_intent(steps=None, goal="Test goal") -> IntentIR:
    """Build a minimal IntentIR."""
    if steps is None:
        steps = [make_step()]
    return IntentIR(goal=goal, requires_confirmation=False, steps=steps)


class TestExecutionResult:
    """Test ExecutionResult data structure"""

    def test_success_result(self):
        """ExecutionResult with success=True sets attributes correctly"""
        r = ExecutionResult(success=True, output="done", error=None)
        assert r.success is True
        assert r.output == "done"
        assert r.error is None

    def test_failure_result(self):
        """ExecutionResult with success=False records error"""
        r = ExecutionResult(success=False, output="", error="something broke")
        assert r.success is False
        assert r.error == "something broke"


class TestAdaptivePlannerInit:
    """Test AdaptivePlanner initialization"""

    @patch("zenus_core.brain.adaptive_planner.get_llm")
    def test_initializes_empty_history(self, mock_get_llm):
        """Fresh AdaptivePlanner starts with empty execution_history"""
        planner = AdaptivePlanner()
        assert planner.execution_history == []

    @patch("zenus_core.brain.adaptive_planner.get_llm")
    def test_logger_stored(self, mock_get_llm):
        """Logger passed to constructor is stored on instance"""
        mock_logger = Mock()
        planner = AdaptivePlanner(logger=mock_logger)
        assert planner.logger is mock_logger


class TestAdaptivePlannerExecuteSingleStep:
    """Test _execute_single_step with mocked tool registry"""

    def setup_method(self):
        """Create AdaptivePlanner with mocked LLM and tool registry."""
        with patch("zenus_core.brain.adaptive_planner.get_llm"):
            self.planner = AdaptivePlanner()
        self.planner.logger = Mock()

    def _register_mock_tool(self, tool_name, action_name, return_value="ok"):
        """Inject a mock tool into the registry for a test."""
        mock_tool = Mock()
        getattr_side = lambda attr: (lambda **kw: return_value) if attr == action_name else None
        mock_tool_obj = Mock()
        setattr(mock_tool_obj, action_name, Mock(return_value=return_value))
        return mock_tool_obj

    @patch("zenus_core.brain.adaptive_planner.check_step")
    @patch("zenus_core.brain.adaptive_planner.TOOLS")
    def test_returns_success_on_valid_step(self, mock_tools, mock_check):
        """Valid step execution returns ExecutionResult with success=True"""
        mock_tool = Mock()
        mock_tool.scan.return_value = "file list"
        mock_tools.get.return_value = mock_tool
        mock_check.return_value = None

        step = make_step(action="scan")
        result = self.planner._execute_single_step(step, 1)
        assert result.success is True
        assert result.output == "file list"

    @patch("zenus_core.brain.adaptive_planner.check_step")
    @patch("zenus_core.brain.adaptive_planner.TOOLS")
    def test_returns_failure_when_tool_not_found(self, mock_tools, mock_check):
        """Missing tool returns ExecutionResult with success=False"""
        mock_tools.get.return_value = None
        mock_check.return_value = None

        step = make_step(tool="NonExistentTool")
        result = self.planner._execute_single_step(step, 1)
        assert result.success is False
        assert "Tool not found" in result.error

    @patch("zenus_core.brain.adaptive_planner.check_step")
    @patch("zenus_core.brain.adaptive_planner.TOOLS")
    def test_returns_failure_when_action_not_found(self, mock_tools, mock_check):
        """Missing action on tool returns ExecutionResult with success=False"""
        mock_tool = Mock(spec=[])  # No attributes
        mock_tools.get.return_value = mock_tool
        mock_check.return_value = None

        step = make_step(action="nonexistent_action")
        result = self.planner._execute_single_step(step, 1)
        assert result.success is False
        assert "Action not found" in result.error

    @patch("zenus_core.brain.adaptive_planner.check_step", side_effect=SafetyError("blocked"))
    @patch("zenus_core.brain.adaptive_planner.TOOLS")
    def test_returns_failure_on_safety_error(self, mock_tools, mock_check):
        """SafetyError from check_step results in failed ExecutionResult"""
        step = make_step(risk=3)
        result = self.planner._execute_single_step(step, 1)
        assert result.success is False
        assert "Safety check failed" in result.error

    @patch("zenus_core.brain.adaptive_planner.check_step")
    @patch("zenus_core.brain.adaptive_planner.TOOLS")
    def test_returns_failure_on_generic_exception(self, mock_tools, mock_check):
        """Unexpected exception results in failed ExecutionResult"""
        mock_tool = Mock()
        mock_tool.scan.side_effect = RuntimeError("explosion")
        mock_tools.get.return_value = mock_tool
        mock_check.return_value = None

        step = make_step(action="scan")
        result = self.planner._execute_single_step(step, 1)
        assert result.success is False
        assert "Execution failed" in result.error

    @patch("zenus_core.brain.adaptive_planner.check_step")
    @patch("zenus_core.brain.adaptive_planner.TOOLS")
    def test_logs_step_result_on_success(self, mock_tools, mock_check):
        """Logger.log_step_result is called with success=True on success"""
        mock_tool = Mock()
        mock_tool.scan.return_value = "output"
        mock_tools.get.return_value = mock_tool
        mock_check.return_value = None

        step = make_step(action="scan")
        self.planner._execute_single_step(step, 1)
        self.planner.logger.log_step_result.assert_called_once()
        call_args = self.planner.logger.log_step_result.call_args[0]
        assert call_args[3] is True

    @patch("zenus_core.brain.adaptive_planner.check_step", side_effect=SafetyError("blocked"))
    @patch("zenus_core.brain.adaptive_planner.TOOLS")
    def test_logs_step_result_on_failure(self, mock_tools, mock_check):
        """Logger.log_step_result is called with success=False on safety error"""
        step = make_step()
        self.planner._execute_single_step(step, 1)
        call_args = self.planner.logger.log_step_result.call_args[0]
        assert call_args[3] is False


class TestAdaptivePlannerExecuteAdaptive:
    """Test execute_adaptive loop, retry logic, and history"""

    def setup_method(self):
        """Create AdaptivePlanner with execution mocked at single-step level."""
        with patch("zenus_core.brain.adaptive_planner.get_llm"):
            self.planner = AdaptivePlanner()
        self.planner.logger = Mock()

    def _patch_single_step(self, results):
        """Patch _execute_single_step to return items from results list in order."""
        self.planner._execute_single_step = Mock(side_effect=results)

    def test_returns_true_when_all_steps_succeed(self):
        """execute_adaptive returns True when every step succeeds"""
        self._patch_single_step([ExecutionResult(True, "ok")])
        intent = make_intent(steps=[make_step()])
        assert self.planner.execute_adaptive(intent) is True

    def test_returns_false_when_step_fails_all_retries(self):
        """execute_adaptive returns False after exhausting retries"""
        self._patch_single_step([
            ExecutionResult(False, "", "error"),
            ExecutionResult(False, "", "error"),
            ExecutionResult(False, "", "error"),
        ])
        # Allow retries to continue by returning the step from _adapt_on_failure
        self.planner._adapt_on_failure = Mock(return_value=make_step())
        intent = make_intent(steps=[make_step()])
        assert self.planner.execute_adaptive(intent, max_retries=2) is False

    def test_retries_up_to_max_retries(self):
        """Failed step is retried exactly max_retries additional times"""
        self._patch_single_step([
            ExecutionResult(False, "", "err"),
            ExecutionResult(False, "", "err"),
            ExecutionResult(True, "ok"),
        ])
        # _adapt_on_failure returns None by default which breaks the retry loop.
        # Mock it to return the original step so retries actually continue.
        self.planner._adapt_on_failure = Mock(return_value=make_step())
        intent = make_intent(steps=[make_step()])
        result = self.planner.execute_adaptive(intent, max_retries=2)
        assert result is True
        assert self.planner._execute_single_step.call_count == 3

    def test_clears_execution_history_at_start(self):
        """execute_adaptive resets execution_history before running"""
        self.planner.execution_history = [{"leftover": True}]
        self._patch_single_step([ExecutionResult(True, "ok")])
        intent = make_intent(steps=[make_step()])
        self.planner.execute_adaptive(intent)
        # Should not contain the leftover entry
        assert all("leftover" not in e for e in self.planner.execution_history)

    def test_successful_steps_appended_to_history(self):
        """Successful steps are appended to execution_history"""
        self._patch_single_step([
            ExecutionResult(True, "ok1"),
            ExecutionResult(True, "ok2"),
        ])
        intent = make_intent(steps=[make_step(), make_step(action="mkdir")])
        self.planner.execute_adaptive(intent)
        assert len(self.planner.execution_history) == 2

    def test_history_records_attempt_number(self):
        """execution_history records the attempt number for each step"""
        self._patch_single_step([ExecutionResult(True, "ok")])
        intent = make_intent(steps=[make_step()])
        self.planner.execute_adaptive(intent)
        assert self.planner.execution_history[0]["attempt"] == 0

    def test_on_failure_callback_called(self):
        """on_failure callback is invoked when a step fails"""
        callback = Mock()
        self._patch_single_step([
            ExecutionResult(False, "", "err"),
            ExecutionResult(False, "", "err"),
            ExecutionResult(False, "", "err"),
        ])
        # Allow retries to continue so callback is actually triggered
        self.planner._adapt_on_failure = Mock(return_value=make_step())
        intent = make_intent(steps=[make_step()])
        self.planner.execute_adaptive(intent, max_retries=2, on_failure=callback)
        assert callback.called

    def test_logs_execution_start(self):
        """logger.log_execution_start is called at the beginning"""
        self._patch_single_step([ExecutionResult(True, "ok")])
        intent = make_intent()
        self.planner.execute_adaptive(intent)
        self.planner.logger.log_execution_start.assert_called_once_with(intent)

    def test_logs_execution_end_on_success(self):
        """logger.log_execution_end is called with True on success"""
        self._patch_single_step([ExecutionResult(True, "ok")])
        intent = make_intent()
        self.planner.execute_adaptive(intent)
        self.planner.logger.log_execution_end.assert_called_once_with(True)

    def test_logs_execution_end_on_failure(self):
        """logger.log_execution_end is called with False on failure"""
        self._patch_single_step([
            ExecutionResult(False, "", "err"),
            ExecutionResult(False, "", "err"),
            ExecutionResult(False, "", "err"),
        ])
        # Allow retries to continue so all 3 attempts are consumed
        self.planner._adapt_on_failure = Mock(return_value=make_step())
        intent = make_intent()
        self.planner.execute_adaptive(intent, max_retries=2)
        call_args = self.planner.logger.log_execution_end.call_args[0]
        assert call_args[0] is False


class TestAdaptivePlannerGetExecutionSummary:
    """Test get_execution_summary reporting"""

    def setup_method(self):
        """Create AdaptivePlanner."""
        with patch("zenus_core.brain.adaptive_planner.get_llm"):
            self.planner = AdaptivePlanner()

    def test_summary_empty_history(self):
        """Summary with no history reports zero steps and 0.0 success rate"""
        summary = self.planner.get_execution_summary()
        assert summary["total_steps"] == 0
        assert summary["success_rate"] == 0.0

    def test_summary_counts_total_steps(self):
        """Summary total_steps matches number of history entries"""
        step = make_step()
        self.planner.execution_history = [
            {"step": step, "result": ExecutionResult(True, "ok"), "attempt": 0},
            {"step": step, "result": ExecutionResult(True, "ok"), "attempt": 0},
        ]
        summary = self.planner.get_execution_summary()
        assert summary["total_steps"] == 2

    def test_summary_counts_retried_steps(self):
        """Summary retried_steps counts entries where attempt > 0"""
        step = make_step()
        self.planner.execution_history = [
            {"step": step, "result": ExecutionResult(True, "ok"), "attempt": 0},
            {"step": step, "result": ExecutionResult(True, "ok"), "attempt": 1},
        ]
        summary = self.planner.get_execution_summary()
        assert summary["retried_steps"] == 1

    def test_summary_success_rate_one_when_steps_present(self):
        """Success rate is 1.0 when execution_history has entries"""
        step = make_step()
        self.planner.execution_history = [
            {"step": step, "result": ExecutionResult(True, "ok"), "attempt": 0},
        ]
        summary = self.planner.get_execution_summary()
        assert summary["success_rate"] == 1.0


class TestAdaptPlannerAdaptOnFailure:
    """Test _adapt_on_failure (currently returns None)"""

    @patch("zenus_core.brain.adaptive_planner.get_llm")
    def test_returns_none_currently(self, mock_get_llm):
        """_adapt_on_failure returns None in current implementation"""
        planner = AdaptivePlanner()
        step = make_step()
        result = ExecutionResult(False, "", "error")
        adapted = planner._adapt_on_failure(step, result, [])
        assert adapted is None


class TestSandboxedAdaptivePlannerInit:
    """Test SandboxedAdaptivePlanner initialization"""

    @patch("zenus_core.brain.adaptive_planner.get_llm")
    def test_inherits_adaptive_planner(self, mock_get_llm):
        """SandboxedAdaptivePlanner is an AdaptivePlanner subclass"""
        planner = SandboxedAdaptivePlanner()
        assert isinstance(planner, AdaptivePlanner)

    @patch("zenus_core.brain.adaptive_planner.get_llm")
    def test_tools_registry_available(self, mock_get_llm):
        """SandboxedAdaptivePlanner has a tools attribute"""
        planner = SandboxedAdaptivePlanner()
        assert hasattr(planner, "tools")


class TestSandboxedExecuteSingleStep:
    """Test SandboxedAdaptivePlanner._execute_single_step sandbox enforcement"""

    def setup_method(self):
        """Create SandboxedAdaptivePlanner with mocked dependencies."""
        with patch("zenus_core.brain.adaptive_planner.get_llm"):
            self.planner = SandboxedAdaptivePlanner()
        self.planner.logger = Mock()

    @patch("zenus_core.safety.policy.check_step")
    def test_returns_success_on_valid_step(self, mock_check):
        """Valid step returns ExecutionResult with success=True"""
        mock_tool = Mock()
        mock_tool.scan.return_value = "result"
        self.planner.tools = {"FileOps": mock_tool}
        mock_check.return_value = None

        step = make_step(action="scan")
        result = self.planner._execute_single_step(step, 1)
        assert result.success is True

    @patch("zenus_core.safety.policy.check_step")
    def test_returns_failure_on_sandbox_violation(self, mock_check):
        """SandboxViolation is caught and returns failed ExecutionResult"""
        mock_tool = Mock()
        mock_tool.scan.side_effect = SandboxViolation("forbidden path")
        self.planner.tools = {"FileOps": mock_tool}
        mock_check.return_value = None

        step = make_step(action="scan")
        result = self.planner._execute_single_step(step, 1)
        assert result.success is False
        assert "Sandbox violation" in result.error

    @patch("zenus_core.safety.policy.check_step")
    def test_returns_failure_when_tool_not_found(self, mock_check):
        """Missing tool returns failed ExecutionResult"""
        self.planner.tools = {}
        mock_check.return_value = None

        step = make_step(tool="GhostTool")
        result = self.planner._execute_single_step(step, 1)
        assert result.success is False
        assert "Tool not found" in result.error

    @patch("zenus_core.safety.policy.check_step")
    def test_returns_failure_when_action_not_found(self, mock_check):
        """Missing action returns failed ExecutionResult"""
        self.planner.tools = {"FileOps": Mock(spec=[])}
        mock_check.return_value = None

        step = make_step(action="ghost_action")
        result = self.planner._execute_single_step(step, 1)
        assert result.success is False
        assert "Action not found" in result.error

    @patch("zenus_core.safety.policy.check_step")
    def test_logs_on_sandbox_violation(self, mock_check):
        """Logger records sandbox violation failure"""
        mock_tool = Mock()
        mock_tool.scan.side_effect = SandboxViolation("blocked")
        self.planner.tools = {"FileOps": mock_tool}
        mock_check.return_value = None

        step = make_step(action="scan")
        self.planner._execute_single_step(step, 1)
        call_args = self.planner.logger.log_step_result.call_args[0]
        assert call_args[3] is False


class TestSandboxedExecuteWithRetry:
    """Test SandboxedAdaptivePlanner.execute_with_retry"""

    def setup_method(self):
        """Create SandboxedAdaptivePlanner with mocked parent execute_adaptive."""
        with patch("zenus_core.brain.adaptive_planner.get_llm"):
            self.planner = SandboxedAdaptivePlanner()
        self.planner.logger = Mock()

    def test_returns_list_of_step_outputs(self):
        """execute_with_retry returns list of output strings from history"""
        step = make_step()
        self.planner.execute_adaptive = Mock(return_value=True)
        self.planner.execution_history = [
            {"result": ExecutionResult(True, "step output"), "step": step, "attempt": 0}
        ]
        results = self.planner.execute_with_retry(make_intent())
        assert results == ["step output"]

    def test_failed_steps_prefixed_with_failed(self):
        """Failed steps in history produce 'Failed: ...' entries in results"""
        step = make_step()
        self.planner.execute_adaptive = Mock(return_value=False)
        self.planner.execution_history = [
            {"result": ExecutionResult(False, "", "boom"), "step": step, "attempt": 1}
        ]
        results = self.planner.execute_with_retry(make_intent())
        assert results[0].startswith("Failed:")

    def test_calls_execute_adaptive_with_intent(self):
        """execute_with_retry delegates to execute_adaptive"""
        self.planner.execute_adaptive = Mock(return_value=True)
        self.planner.execution_history = []
        intent = make_intent()
        self.planner.execute_with_retry(intent, max_retries=1)
        self.planner.execute_adaptive.assert_called_once_with(intent, max_retries=1)
