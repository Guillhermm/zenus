"""
Tests for the Orchestrator class
"""

import pytest
from contextlib import ExitStack
from unittest.mock import Mock, patch, MagicMock, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(tool="FileOps", action="scan", args=None, risk=0):
    """Return a minimal mock Step."""
    step = Mock()
    step.tool = tool
    step.action = action
    step.args = args or {"path": "/tmp"}
    step.risk = risk
    return step


def _make_intent(goal="test goal", steps=None, requires_confirmation=False):
    """Return a minimal mock IntentIR."""
    intent = Mock()
    intent.goal = goal
    intent.requires_confirmation = requires_confirmation
    intent.steps = steps or [_make_step()]
    intent.to_dict = Mock(return_value={"goal": goal, "steps": []})
    return intent


# ---------------------------------------------------------------------------
# Patch targets – everything the Orchestrator __init__ wires up
# ---------------------------------------------------------------------------

PATCH_TARGETS = [
    "zenus_core.orchestrator.get_llm",
    "zenus_core.orchestrator.get_logger",
    "zenus_core.orchestrator.AdaptivePlanner",
    "zenus_core.orchestrator.SandboxedAdaptivePlanner",
    "zenus_core.orchestrator.SessionMemory",
    "zenus_core.orchestrator.WorldModel",
    "zenus_core.orchestrator.IntentHistory",
    "zenus_core.orchestrator.ProgressIndicator",
    "zenus_core.orchestrator.ResponseGenerator",
    "zenus_core.orchestrator.FailureAnalyzer",
    "zenus_core.orchestrator.get_action_tracker",
    "zenus_core.orchestrator.DependencyAnalyzer",
    "zenus_core.orchestrator.get_parallel_executor",
    "zenus_core.orchestrator.get_suggestion_engine",
    "zenus_core.orchestrator.get_router",
    "zenus_core.orchestrator.get_intent_cache",
    "zenus_core.orchestrator.get_feedback_collector",
    "zenus_core.orchestrator.get_metrics_collector",
    "zenus_core.orchestrator.get_formatter",
    "zenus_core.orchestrator.TaskAnalyzer",
    "zenus_core.orchestrator.get_tree_of_thoughts",
    "zenus_core.orchestrator.get_prompt_evolution",
    "zenus_core.orchestrator.get_goal_inference",
    "zenus_core.orchestrator.get_multi_agent_system",
    "zenus_core.orchestrator.get_proactive_monitor",
    "zenus_core.orchestrator.get_self_reflection",
    "zenus_core.orchestrator.get_visualizer",
    "zenus_core.orchestrator.ExplainMode",
]


def _make_orchestrator(**kwargs):
    """Instantiate Orchestrator with all dependencies mocked out using ExitStack."""
    from zenus_core.orchestrator import Orchestrator

    with ExitStack() as stack:
        patches = {t: stack.enter_context(patch(t)) for t in PATCH_TARGETS}

        mock_router = patches["zenus_core.orchestrator.get_router"]
        mock_cache = patches["zenus_core.orchestrator.get_intent_cache"]

        mock_router.return_value.route.return_value = ("anthropic", Mock(score=0.3))
        mock_router.return_value.get_stats.return_value = {
            "session": {"tokens_used": 0, "estimated_cost": 0.0}
        }
        mock_cache.return_value.get.return_value = None

        orch = Orchestrator(**kwargs)
        orch.logger = Mock()
        orch.adaptive_planner = Mock()
        orch.adaptive_planner.execute_with_retry.return_value = ["result1"]
        orch.action_tracker = Mock()
        orch.action_tracker.start_transaction.return_value = "txn-1"

    return orch


# ===========================================================================
# Orchestrator Initialisation
# ===========================================================================

class TestOrchestratorInit:
    """Test Orchestrator initialisation"""

    def test_initializes_with_defaults(self):
        """Orchestrator initialises without raising any exceptions"""
        orch = _make_orchestrator()
        assert orch is not None

    def test_adaptive_flag_stored(self):
        """adaptive flag is stored on instance"""
        orch = _make_orchestrator(adaptive=True)
        assert orch.adaptive is True

    def test_use_memory_flag_stored(self):
        """use_memory flag is stored on instance"""
        orch = _make_orchestrator(use_memory=True)
        assert orch.use_memory is True

    def test_use_sandbox_flag_stored(self):
        """use_sandbox flag is stored on instance"""
        orch = _make_orchestrator(use_sandbox=True)
        assert orch.use_sandbox is True

    def test_show_progress_flag_stored(self):
        """show_progress flag is stored on instance"""
        orch = _make_orchestrator(show_progress=False)
        assert orch.show_progress is False

    def test_non_adaptive_has_no_adaptive_planner(self):
        """adaptive=False means no adaptive_planner is created"""
        from zenus_core.orchestrator import Orchestrator

        with ExitStack() as stack:
            patches = {t: stack.enter_context(patch(t)) for t in PATCH_TARGETS}
            mock_ap = patches["zenus_core.orchestrator.AdaptivePlanner"]
            mock_sp = patches["zenus_core.orchestrator.SandboxedAdaptivePlanner"]
            mock_router = patches["zenus_core.orchestrator.get_router"]
            mock_router.return_value.route.return_value = ("anthropic", Mock(score=0.3))

            orch = Orchestrator(adaptive=False)
            mock_ap.assert_not_called()
            mock_sp.assert_not_called()


# ===========================================================================
# _format_dry_run
# ===========================================================================

class TestFormatDryRun:
    """Test Orchestrator._format_dry_run"""

    def setup_method(self):
        """Create Orchestrator."""
        self.orch = _make_orchestrator()

    def test_includes_goal(self):
        """_format_dry_run output mentions the intent goal"""
        intent = _make_intent(goal="list all files")
        result = self.orch._format_dry_run(intent)
        assert "list all files" in result

    def test_includes_dry_run_label(self):
        """_format_dry_run output is labelled as DRY RUN"""
        intent = _make_intent()
        result = self.orch._format_dry_run(intent)
        assert "DRY RUN" in result

    def test_includes_step_info(self):
        """_format_dry_run includes tool and action names"""
        step = _make_step(tool="FileOps", action="scan")
        intent = _make_intent(steps=[step])
        result = self.orch._format_dry_run(intent)
        assert "FileOps" in result
        assert "scan" in result

    def test_numbers_steps(self):
        """_format_dry_run numbers each step"""
        intent = _make_intent(steps=[_make_step(), _make_step(action="mkdir")])
        result = self.orch._format_dry_run(intent)
        assert "1." in result
        assert "2." in result


# ===========================================================================
# visualize_result
# ===========================================================================

class TestVisualizeResult:
    """Test Orchestrator.visualize_result"""

    def setup_method(self):
        """Create Orchestrator with mocked visualizer."""
        self.orch = _make_orchestrator(enable_visualization=True)
        self.orch.visualizer = Mock()
        self.orch.enable_visualization = True
        self.orch.visualizer.visualize.return_value = "chart output"

    def test_delegates_to_visualizer(self):
        """visualize_result calls visualizer.visualize and returns result"""
        result = self.orch.visualize_result({"a": 1}, title="Test")
        self.orch.visualizer.visualize.assert_called_once_with({"a": 1}, title="Test")
        assert result == "chart output"

    def test_returns_str_when_visualizer_disabled(self):
        """visualize_result falls back to str() when visualization disabled"""
        self.orch.enable_visualization = False
        self.orch.visualizer = None
        result = self.orch.visualize_result(42)
        assert result == "42"

    def test_returns_str_on_visualizer_exception(self):
        """visualize_result falls back to str() on exception"""
        self.orch.visualizer.visualize.side_effect = RuntimeError("render error")
        result = self.orch.visualize_result("data")
        assert isinstance(result, str)


# ===========================================================================
# run_health_check
# ===========================================================================

class TestRunHealthCheck:
    """Test Orchestrator.run_health_check"""

    def setup_method(self):
        """Create Orchestrator."""
        self.orch = _make_orchestrator()

    def test_returns_disabled_when_monitoring_off(self):
        """run_health_check returns disabled status when monitoring not enabled"""
        self.orch.enable_proactive_monitoring = False
        self.orch.proactive_monitor = None
        result = self.orch.run_health_check()
        assert result["status"] == "disabled"

    def test_returns_ok_with_no_alerts(self):
        """run_health_check returns ok status when no alerts"""
        self.orch.enable_proactive_monitoring = True
        mock_monitor = Mock()
        mock_monitor.run_checks.return_value = []
        mock_monitor.get_status.return_value = {"checks": []}
        self.orch.proactive_monitor = mock_monitor
        result = self.orch.run_health_check()
        assert result["status"] == "ok"
        assert result["alerts"] == 0

    def test_returns_alert_count(self):
        """run_health_check includes count of alerts found"""
        self.orch.enable_proactive_monitoring = True
        mock_alert = Mock()
        mock_alert.auto_remediated = False
        mock_alert.remediation_result = None
        mock_alert.level.value = "warning"
        mock_alert.message = "disk low"
        mock_monitor = Mock()
        mock_monitor.run_checks.return_value = [mock_alert]
        mock_monitor.get_status.return_value = {"checks": []}
        self.orch.proactive_monitor = mock_monitor
        result = self.orch.run_health_check()
        assert result["alerts"] == 1

    def test_returns_error_on_exception(self):
        """run_health_check returns error status when exception occurs"""
        self.orch.enable_proactive_monitoring = True
        mock_monitor = Mock()
        mock_monitor.run_checks.side_effect = RuntimeError("check failed")
        self.orch.proactive_monitor = mock_monitor
        result = self.orch.run_health_check()
        assert result["status"] == "error"

    def test_counts_auto_remediated_alerts(self):
        """run_health_check counts auto-remediated alerts"""
        self.orch.enable_proactive_monitoring = True
        mock_alert = Mock()
        mock_alert.auto_remediated = True
        mock_alert.remediation_result = "cleaned"
        mock_alert.level.value = "warning"
        mock_alert.message = "fixed"
        mock_monitor = Mock()
        mock_monitor.run_checks.return_value = [mock_alert]
        mock_monitor.get_status.return_value = {}
        self.orch.proactive_monitor = mock_monitor
        result = self.orch.run_health_check()
        assert result["auto_remediated"] == 1


# ===========================================================================
# execute_with_multi_agent
# ===========================================================================

class TestExecuteWithMultiAgent:
    """Test Orchestrator.execute_with_multi_agent"""

    def setup_method(self):
        """Create Orchestrator."""
        self.orch = _make_orchestrator()

    def test_returns_disabled_when_not_enabled(self):
        """execute_with_multi_agent returns disabled message when not enabled"""
        self.orch.enable_multi_agent = False
        self.orch.multi_agent = None
        result = self.orch.execute_with_multi_agent("do something")
        assert "not enabled" in result

    def test_returns_final_result_on_success(self):
        """execute_with_multi_agent returns final_result from successful session"""
        self.orch.enable_multi_agent = True
        mock_session = Mock()
        mock_session.success = True
        mock_session.final_result = "mission accomplished"
        mock_session.session_id = "abc"
        mock_session.agents_involved = []
        mock_session.total_duration = 1.0
        mock_session.results = []
        mock_mas = Mock()
        mock_mas.collaborate.return_value = mock_session
        self.orch.multi_agent = mock_mas
        result = self.orch.execute_with_multi_agent("complex task")
        assert result == "mission accomplished"

    def test_returns_error_on_failed_session(self):
        """execute_with_multi_agent returns error string on failed session"""
        self.orch.enable_multi_agent = True
        mock_session = Mock()
        mock_session.success = False
        mock_session.final_result = "could not complete"
        mock_session.session_id = "abc"
        mock_session.agents_involved = []
        mock_session.total_duration = 1.0
        mock_session.results = []
        mock_mas = Mock()
        mock_mas.collaborate.return_value = mock_session
        self.orch.multi_agent = mock_mas
        result = self.orch.execute_with_multi_agent("hard task")
        assert "Error" in result

    def test_returns_error_on_exception(self):
        """execute_with_multi_agent returns error message on exception"""
        self.orch.enable_multi_agent = True
        mock_mas = Mock()
        mock_mas.collaborate.side_effect = RuntimeError("agents crashed")
        self.orch.multi_agent = mock_mas
        result = self.orch.execute_with_multi_agent("task")
        assert "failed" in result.lower()


# ===========================================================================
# execute_command (dry_run)
# ===========================================================================

class TestExecuteCommandDryRun:
    """Test Orchestrator.execute_command with dry_run=True"""

    def setup_method(self):
        """Create Orchestrator with LLM translate_intent mocked."""
        self.orch = _make_orchestrator(
            enable_tree_of_thoughts=False,
            enable_goal_inference=False,
            enable_multi_agent=False,
            enable_proactive_monitoring=False,
            enable_self_reflection=False,
            enable_prompt_evolution=False,
            show_progress=False,
        )
        self.intent = _make_intent()
        self.orch.llm = Mock()
        self.orch.llm.translate_intent.return_value = self.intent
        self.orch.task_analyzer = Mock()
        self.orch.task_analyzer.analyze.return_value = Mock(needs_iteration=False)
        self.orch.router = Mock()
        self.orch.router.route.return_value = ("anthropic", Mock(score=0.3))
        self.orch.intent_cache = Mock()
        self.orch.intent_cache.get.return_value = None
        self.orch.failure_analyzer = Mock()
        self.orch.failure_analyzer.analyze_before_execution.return_value = {
            "has_warnings": False, "warnings": [], "suggestions": [], "success_probability": 1.0
        }
        self.orch.suggestion_engine = Mock()
        self.orch.suggestion_engine.analyze.return_value = []

    @patch("zenus_core.orchestrator.get_llm")
    @patch("zenus_core.orchestrator.get_context_manager")
    def test_dry_run_returns_dry_run_string(self, mock_ctx, mock_get_llm):
        """execute_command with dry_run=True returns DRY RUN output"""
        mock_get_llm.return_value = self.orch.llm
        mock_ctx.return_value.get_contextual_prompt.return_value = ""
        mock_ctx.return_value.get_full_context.return_value = {}
        result = self.orch.execute_command("list files", dry_run=True, force_oneshot=True)
        assert "DRY RUN" in result

    @patch("zenus_core.orchestrator.get_llm")
    @patch("zenus_core.orchestrator.get_context_manager")
    def test_dry_run_does_not_execute_plan(self, mock_ctx, mock_get_llm):
        """execute_command with dry_run=True does not call adaptive_planner"""
        mock_get_llm.return_value = self.orch.llm
        mock_ctx.return_value.get_contextual_prompt.return_value = ""
        mock_ctx.return_value.get_full_context.return_value = {}
        self.orch.execute_command("list files", dry_run=True, force_oneshot=True)
        self.orch.adaptive_planner.execute_with_retry.assert_not_called()

    @patch("zenus_core.orchestrator.get_llm")
    @patch("zenus_core.orchestrator.get_context_manager")
    def test_intent_logged_before_dry_run(self, mock_ctx, mock_get_llm):
        """execute_command logs intent even in dry_run mode"""
        mock_get_llm.return_value = self.orch.llm
        mock_ctx.return_value.get_contextual_prompt.return_value = ""
        mock_ctx.return_value.get_full_context.return_value = {}
        self.orch.execute_command("list files", dry_run=True, force_oneshot=True)
        self.orch.logger.log_intent.assert_called()


# ===========================================================================
# execute_command (error paths)
# ===========================================================================

class TestExecuteCommandErrors:
    """Test Orchestrator.execute_command error handling"""

    def setup_method(self):
        """Create Orchestrator."""
        self.orch = _make_orchestrator(
            enable_tree_of_thoughts=False,
            enable_goal_inference=False,
            enable_multi_agent=False,
            enable_proactive_monitoring=False,
            enable_self_reflection=False,
            enable_prompt_evolution=False,
            show_progress=False,
        )
        self.orch.task_analyzer = Mock()
        self.orch.task_analyzer.analyze.return_value = Mock(needs_iteration=False)
        self.orch.router = Mock()
        self.orch.router.route.return_value = ("anthropic", Mock(score=0.3))
        self.orch.intent_cache = Mock()
        self.orch.intent_cache.get.return_value = None
        self.orch.suggestion_engine = Mock()
        self.orch.suggestion_engine.analyze.return_value = []

    @patch("zenus_core.orchestrator.get_llm")
    @patch("zenus_core.orchestrator.get_context_manager")
    def test_returns_error_on_translation_failure(self, mock_ctx, mock_get_llm):
        """execute_command returns error string when LLM translate_intent raises"""
        mock_ctx.return_value.get_contextual_prompt.return_value = ""
        mock_ctx.return_value.get_full_context.return_value = {}
        failing_llm = Mock()
        failing_llm.translate_intent.side_effect = Exception("LLM timeout")
        mock_get_llm.return_value = failing_llm
        self.orch.llm = failing_llm
        result = self.orch.execute_command("do stuff", force_oneshot=True)
        assert "Error" in result or "error" in result.lower()

    @patch("zenus_core.orchestrator.get_llm")
    @patch("zenus_core.orchestrator.get_context_manager")
    def test_logs_error_on_translation_failure(self, mock_ctx, mock_get_llm):
        """execute_command logs error when translation fails"""
        mock_ctx.return_value.get_contextual_prompt.return_value = ""
        mock_ctx.return_value.get_full_context.return_value = {}
        failing_llm = Mock()
        failing_llm.translate_intent.side_effect = Exception("timeout")
        mock_get_llm.return_value = failing_llm
        self.orch.llm = failing_llm
        self.orch.execute_command("do stuff", force_oneshot=True)
        self.orch.logger.log_error.assert_called()


# ===========================================================================
# IntentTranslationError / OrchestratorError
# ===========================================================================

class TestOrchestratorExceptions:
    """Test custom exception classes"""

    def test_intent_translation_error_is_exception(self):
        """IntentTranslationError is a subclass of Exception"""
        from zenus_core.orchestrator import IntentTranslationError
        with pytest.raises(IntentTranslationError):
            raise IntentTranslationError("bad")

    def test_orchestrator_error_is_exception(self):
        """OrchestratorError is a subclass of Exception"""
        from zenus_core.orchestrator import OrchestratorError
        with pytest.raises(OrchestratorError):
            raise OrchestratorError("oops")
