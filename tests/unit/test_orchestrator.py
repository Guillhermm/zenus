"""
Tests for zenus_core.orchestrator
"""

import pytest
from contextlib import contextmanager, ExitStack
from unittest.mock import Mock, MagicMock, patch, call

from zenus_core.brain.llm.schemas import IntentIR, Step

MODULE = "zenus_core.orchestrator"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(tool="FileOps", action="scan", risk=0):
    return Step(tool=tool, action=action, args={}, risk=risk)


def _make_intent(goal="do something", steps=None):
    if steps is None:
        steps = [_make_step()]
    return IntentIR(goal=goal, requires_confirmation=False, steps=steps)


@contextmanager
def _orchestrator_ctx(**orch_kwargs):
    """
    Yields (orchestrator, mocks_dict) with all external dependencies mocked.
    Defaults create a minimal no-feature orchestrator.
    """
    defaults = dict(
        adaptive=False,
        use_memory=False,
        show_progress=False,
        enable_parallel=False,
        enable_tree_of_thoughts=False,
        enable_prompt_evolution=False,
        enable_goal_inference=False,
        enable_multi_agent=False,
        enable_proactive_monitoring=False,
        enable_self_reflection=False,
        enable_visualization=False,
    )
    defaults.update(orch_kwargs)

    with ExitStack() as stack:
        mocks = {}
        for name in [
            "get_llm", "get_logger",
            "AdaptivePlanner", "SandboxedAdaptivePlanner",
            "TaskAnalyzer", "FailureAnalyzer", "DependencyAnalyzer",
            "get_suggestion_engine", "get_router",
            "get_tree_of_thoughts", "get_prompt_evolution", "get_goal_inference",
            "get_multi_agent_system", "get_self_reflection", "get_proactive_monitor",
            "get_action_tracker", "get_parallel_executor", "get_intent_cache",
            "get_feedback_collector", "get_metrics_collector", "get_formatter",
            "SessionMemory", "WorldModel", "IntentHistory",
            "ProgressIndicator", "ResponseGenerator", "ExplainMode",
            "get_context_manager",
            "console", "print_success", "print_error", "print_goal", "print_step",
        ]:
            mocks[name] = stack.enter_context(patch(f"{MODULE}.{name}"))

        stack.enter_context(patch(f"{MODULE}.VISUALIZATION_AVAILABLE", False))

        # ---- logger ----
        mock_logger = Mock()
        mocks["get_logger"].return_value = mock_logger

        # ---- router ----
        mock_router = Mock()
        mock_router.route.return_value = ("claude-3-haiku", Mock(score=0.3))
        mock_router.track_tokens = Mock()
        mock_router.get_stats.return_value = {
            "session": {"tokens_used": 0, "estimated_cost": 0.0}
        }
        mocks["get_router"].return_value = mock_router

        # ---- suggestion engine ----
        mock_suggestions = Mock()
        mock_suggestions.analyze.return_value = []
        mocks["get_suggestion_engine"].return_value = mock_suggestions

        # ---- action tracker ----
        mock_tracker = Mock()
        mock_tracker.start_transaction.return_value = "txn-1"
        mocks["get_action_tracker"].return_value = mock_tracker

        # ---- intent cache (miss by default) ----
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mocks["get_intent_cache"].return_value = mock_cache

        # ---- failure analyzer (no warnings) ----
        mock_fa = Mock()
        mock_fa.analyze_before_execution.return_value = {
            "has_warnings": False,
            "warnings": [],
            "suggestions": [],
            "success_probability": 1.0,
        }
        mock_fa.analyze_failure.return_value = {
            "suggestions": [],
            "is_recurring": False,
            "similar_failures": [],
        }
        mock_fa.generate_recovery_plan.return_value = None
        mocks["FailureAnalyzer"].return_value = mock_fa

        # ---- task analyzer (no iteration needed) ----
        mock_ta = Mock()
        mock_ta.analyze.return_value = Mock(needs_iteration=False)
        mocks["TaskAnalyzer"].return_value = mock_ta

        # ---- context manager ----
        mock_ctx = Mock()
        mock_ctx.get_contextual_prompt.return_value = ""
        mock_ctx.get_full_context.return_value = {}
        mocks["get_context_manager"].return_value = mock_ctx

        from zenus_core.orchestrator import Orchestrator
        orch = Orchestrator(**defaults)

        # Expose easy references
        mocks["_logger"] = mock_logger
        mocks["_router"] = mock_router
        mocks["_cache"] = mock_cache
        mocks["_tracker"] = mock_tracker
        mocks["_fa"] = mock_fa
        mocks["_ta"] = mock_ta
        mocks["_ctx"] = mock_ctx

        yield orch, mocks


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------

class TestExceptions:

    def test_intent_translation_error_is_exception(self):
        from zenus_core.orchestrator import IntentTranslationError
        e = IntentTranslationError("oops")
        assert isinstance(e, Exception)
        assert str(e) == "oops"

    def test_orchestrator_error_is_exception(self):
        from zenus_core.orchestrator import OrchestratorError
        e = OrchestratorError("fail")
        assert isinstance(e, Exception)


# ---------------------------------------------------------------------------
# Orchestrator.__init__
# ---------------------------------------------------------------------------

class TestOrchestratorInit:

    def test_default_privilege_tier(self):
        with _orchestrator_ctx() as (orch, _):
            from zenus_core.tools.privilege import PrivilegeTier
            assert orch.privilege_tier == PrivilegeTier.STANDARD

    def test_adaptive_false_sets_no_planner(self):
        with _orchestrator_ctx(adaptive=False) as (orch, _):
            assert not hasattr(orch, "adaptive_planner")

    def test_adaptive_true_sandbox_creates_sandboxed_planner(self):
        with _orchestrator_ctx(adaptive=True, use_sandbox=True) as (orch, mocks):
            mocks["SandboxedAdaptivePlanner"].assert_called_once()

    def test_adaptive_true_no_sandbox_creates_basic_planner(self):
        with _orchestrator_ctx(adaptive=True, use_sandbox=False) as (orch, mocks):
            mocks["AdaptivePlanner"].assert_called_once()

    def test_use_memory_false_no_session_memory(self):
        with _orchestrator_ctx(use_memory=False) as (orch, _):
            assert not hasattr(orch, "session_memory")

    def test_use_memory_true_creates_memory(self):
        with _orchestrator_ctx(use_memory=True) as (orch, mocks):
            mocks["SessionMemory"].assert_called_once()
            mocks["WorldModel"].assert_called_once()
            mocks["IntentHistory"].assert_called_once()

    def test_show_progress_false_no_progress(self):
        with _orchestrator_ctx(show_progress=False) as (orch, _):
            assert orch.progress is None

    def test_enable_parallel_false_no_executor(self):
        with _orchestrator_ctx(enable_parallel=False) as (orch, _):
            assert orch.parallel_executor is None
            assert orch.dependency_analyzer is None

    def test_visualization_disabled_no_visualizer(self):
        with _orchestrator_ctx(enable_visualization=False) as (orch, _):
            assert orch.visualizer is None

    def test_flags_stored(self):
        with _orchestrator_ctx(
            enable_tree_of_thoughts=False,
            enable_prompt_evolution=False,
            enable_goal_inference=False,
            enable_multi_agent=False,
            enable_proactive_monitoring=False,
            enable_self_reflection=False,
        ) as (orch, _):
            assert orch.enable_tree_of_thoughts is False
            assert orch.enable_multi_agent is False
            assert orch.enable_proactive_monitoring is False


# ---------------------------------------------------------------------------
# _format_dry_run
# ---------------------------------------------------------------------------

class TestFormatDryRun:

    def test_contains_goal(self):
        with _orchestrator_ctx() as (orch, _):
            intent = _make_intent(goal="list files")
            result = orch._format_dry_run(intent)
            assert "list files" in result

    def test_contains_dry_run_marker(self):
        with _orchestrator_ctx() as (orch, _):
            intent = _make_intent()
            result = orch._format_dry_run(intent)
            assert "DRY RUN" in result

    def test_lists_all_steps(self):
        with _orchestrator_ctx() as (orch, _):
            steps = [
                _make_step("FileOps", "scan", risk=0),
                _make_step("ShellOps", "run", risk=2),
            ]
            intent = _make_intent(steps=steps)
            result = orch._format_dry_run(intent)
            assert "FileOps" in result
            assert "ShellOps" in result

    def test_includes_risk_level(self):
        with _orchestrator_ctx() as (orch, _):
            intent = _make_intent(steps=[_make_step(risk=3)])
            result = orch._format_dry_run(intent)
            assert "risk=3" in result

    def test_empty_steps(self):
        with _orchestrator_ctx() as (orch, _):
            intent = _make_intent(goal="nothing", steps=[])
            result = orch._format_dry_run(intent)
            assert "DRY RUN" in result
            assert "nothing" in result


# ---------------------------------------------------------------------------
# visualize_result
# ---------------------------------------------------------------------------

class TestVisualizeResult:

    def test_disabled_returns_str_data(self):
        with _orchestrator_ctx(enable_visualization=False) as (orch, _):
            result = orch.visualize_result([1, 2, 3])
            assert result == "[1, 2, 3]"

    def test_no_visualizer_returns_str_data(self):
        with _orchestrator_ctx(enable_visualization=True) as (orch, _):
            orch.visualizer = None
            result = orch.visualize_result({"key": "val"})
            assert "key" in result

    def test_visualizer_called_with_title(self):
        with _orchestrator_ctx(enable_visualization=True) as (orch, _):
            mock_viz = Mock()
            mock_viz.visualize.return_value = "chart!"
            orch.visualizer = mock_viz
            orch.enable_visualization = True
            result = orch.visualize_result([1, 2], title="Numbers")
            mock_viz.visualize.assert_called_once_with([1, 2], title="Numbers")
            assert result == "chart!"

    def test_visualizer_exception_returns_str_data(self):
        with _orchestrator_ctx(enable_visualization=True) as (orch, _):
            mock_viz = Mock()
            mock_viz.visualize.side_effect = RuntimeError("render error")
            orch.visualizer = mock_viz
            orch.enable_visualization = True
            result = orch.visualize_result("my data")
            assert result == "my data"


# ---------------------------------------------------------------------------
# run_health_check
# ---------------------------------------------------------------------------

class TestRunHealthCheck:

    def test_disabled_returns_disabled_status(self):
        with _orchestrator_ctx(enable_proactive_monitoring=False) as (orch, _):
            result = orch.run_health_check()
            assert result["status"] == "disabled"

    def test_enabled_no_alerts(self):
        with _orchestrator_ctx(enable_proactive_monitoring=True) as (orch, _):
            mock_monitor = Mock()
            mock_monitor.run_checks.return_value = []
            mock_monitor.get_status.return_value = {"ok": True}
            orch.proactive_monitor = mock_monitor
            orch.enable_proactive_monitoring = True

            result = orch.run_health_check()
            assert result["status"] == "ok"
            assert result["alerts"] == 0

    def test_enabled_with_alerts(self):
        with _orchestrator_ctx(enable_proactive_monitoring=True) as (orch, _):
            alert = Mock()
            alert.level = Mock(value="warning")
            alert.message = "disk filling up"
            alert.auto_remediated = False
            alert.remediation_result = None

            mock_monitor = Mock()
            mock_monitor.run_checks.return_value = [alert]
            mock_monitor.get_status.return_value = {}
            orch.proactive_monitor = mock_monitor
            orch.enable_proactive_monitoring = True

            result = orch.run_health_check()
            assert result["alerts"] == 1

    def test_enabled_with_auto_remediated_alert(self):
        with _orchestrator_ctx(enable_proactive_monitoring=True) as (orch, _):
            alert = Mock()
            alert.level = Mock(value="critical")
            alert.message = "memory exhausted"
            alert.auto_remediated = True
            alert.remediation_result = "cleared cache"

            mock_monitor = Mock()
            mock_monitor.run_checks.return_value = [alert]
            mock_monitor.get_status.return_value = {}
            orch.proactive_monitor = mock_monitor
            orch.enable_proactive_monitoring = True

            result = orch.run_health_check()
            assert result["auto_remediated"] == 1

    def test_exception_returns_error_status(self):
        with _orchestrator_ctx(enable_proactive_monitoring=True) as (orch, _):
            mock_monitor = Mock()
            mock_monitor.run_checks.side_effect = RuntimeError("monitor crashed")
            orch.proactive_monitor = mock_monitor
            orch.enable_proactive_monitoring = True

            result = orch.run_health_check()
            assert result["status"] == "error"
            assert "monitor crashed" in result["message"]


# ---------------------------------------------------------------------------
# execute_with_multi_agent
# ---------------------------------------------------------------------------

class TestExecuteWithMultiAgent:

    def test_disabled_returns_not_enabled_message(self):
        with _orchestrator_ctx(enable_multi_agent=False) as (orch, _):
            result = orch.execute_with_multi_agent("do something")
            assert "not enabled" in result

    def test_success_returns_final_result(self):
        with _orchestrator_ctx(enable_multi_agent=True) as (orch, _):
            session = Mock()
            session.success = True
            session.final_result = "task done"
            session.session_id = "sess-1"
            session.agents_involved = [Mock(value="planner")]
            session.total_duration = 1.2
            session.results = []

            mock_multi = Mock()
            mock_multi.collaborate.return_value = session
            orch.multi_agent = mock_multi
            orch.enable_multi_agent = True

            result = orch.execute_with_multi_agent("build something")
            assert result == "task done"

    def test_failure_returns_error_message(self):
        with _orchestrator_ctx(enable_multi_agent=True) as (orch, _):
            session = Mock()
            session.success = False
            session.final_result = "agents disagreed"
            session.session_id = "sess-2"
            session.agents_involved = []
            session.total_duration = 0.5
            session.results = []

            mock_multi = Mock()
            mock_multi.collaborate.return_value = session
            orch.multi_agent = mock_multi
            orch.enable_multi_agent = True

            result = orch.execute_with_multi_agent("build something")
            assert "Error" in result

    def test_exception_returns_error_string(self):
        with _orchestrator_ctx(enable_multi_agent=True) as (orch, _):
            mock_multi = Mock()
            mock_multi.collaborate.side_effect = RuntimeError("network timeout")
            orch.multi_agent = mock_multi
            orch.enable_multi_agent = True

            result = orch.execute_with_multi_agent("build something")
            assert "network timeout" in result


# ---------------------------------------------------------------------------
# _build_context
# ---------------------------------------------------------------------------

class TestBuildContext:

    def test_no_memory_no_env_empty_string(self):
        with _orchestrator_ctx(use_memory=False) as (orch, mocks):
            mocks["_ctx"].get_contextual_prompt.return_value = ""
            result = orch._build_context("list files")
            assert result == ""

    def test_env_context_included(self):
        with _orchestrator_ctx(use_memory=False) as (orch, mocks):
            mocks["_ctx"].get_contextual_prompt.return_value = "cwd=/home/ana"
            result = orch._build_context("what is here")
            assert "cwd=/home/ana" in result

    def test_with_memory_calls_session_summary(self):
        with _orchestrator_ctx(use_memory=True) as (orch, mocks):
            mocks["_ctx"].get_contextual_prompt.return_value = ""
            orch.session_memory = Mock()
            orch.session_memory.get_context_summary.return_value = "recent: scan /tmp"
            orch.world_model = Mock()
            orch.world_model.get_frequent_paths.return_value = []

            result = orch._build_context("check logs")
            assert "recent: scan /tmp" in result

    def test_file_keyword_triggers_frequent_paths(self):
        with _orchestrator_ctx(use_memory=True) as (orch, mocks):
            mocks["_ctx"].get_contextual_prompt.return_value = ""
            orch.session_memory = Mock()
            orch.session_memory.get_context_summary.return_value = ""
            orch.world_model = Mock()
            orch.world_model.get_frequent_paths.return_value = ["/home/ana/projects"]

            result = orch._build_context("list all files")
            assert "/home/ana/projects" in result

    def test_non_file_keyword_skips_frequent_paths(self):
        with _orchestrator_ctx(use_memory=True) as (orch, mocks):
            mocks["_ctx"].get_contextual_prompt.return_value = ""
            orch.session_memory = Mock()
            orch.session_memory.get_context_summary.return_value = ""
            orch.world_model = Mock()

            orch._build_context("run npm install")

            orch.world_model.get_frequent_paths.assert_not_called()


# ---------------------------------------------------------------------------
# execute_command — dry run
# ---------------------------------------------------------------------------

class TestExecuteCommandDryRun:

    def test_dry_run_returns_dry_run_string(self):
        intent = _make_intent(goal="scan /tmp")

        with _orchestrator_ctx() as (orch, mocks):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("list files", None, None)):
                result = orch.execute_command("list files", dry_run=True)

            assert "DRY RUN" in result
            assert "scan /tmp" in result


# ---------------------------------------------------------------------------
# execute_command — intent translation error
# ---------------------------------------------------------------------------

class TestExecuteCommandIntentError:

    def test_llm_exception_returns_error_string(self):
        with _orchestrator_ctx() as (orch, mocks):
            mock_llm = Mock()
            mock_llm.translate_intent.side_effect = RuntimeError("LLM down")
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("run tests", None, None)):
                result = orch.execute_command("run tests")

            assert "Error" in result or "error" in result.lower()


# ---------------------------------------------------------------------------
# execute_command — cache hit
# ---------------------------------------------------------------------------

class TestExecuteCommandCache:

    def test_cache_hit_skips_llm(self):
        intent = _make_intent(goal="cached goal", steps=[_make_step()])

        with _orchestrator_ctx() as (orch, mocks):
            mocks["_cache"].get.return_value = intent

            mock_llm = Mock()
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("do cached thing", None, None)):
                with patch("zenus_core.orchestrator.execute_plan", return_value=["done"]):
                    orch.execute_command("do cached thing")

            mock_llm.translate_intent.assert_not_called()


# ---------------------------------------------------------------------------
# execute_command — successful execution
# ---------------------------------------------------------------------------

class TestExecuteCommandSuccess:

    def test_success_returns_string(self):
        intent = _make_intent(goal="scan tmp", steps=[_make_step()])

        with _orchestrator_ctx() as (orch, mocks):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("scan tmp", None, None)):
                with patch("zenus_core.orchestrator.execute_plan", return_value=["file1.txt"]):
                    result = orch.execute_command("scan tmp")

            assert isinstance(result, str)

    def test_success_logs_intent(self):
        intent = _make_intent(goal="test goal")

        with _orchestrator_ctx() as (orch, mocks):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("test goal", None, None)):
                with patch("zenus_core.orchestrator.execute_plan", return_value=["ok"]):
                    orch.execute_command("test goal")

            mocks["_logger"].log_intent.assert_called_once()

    def test_action_tracker_transaction_completed(self):
        intent = _make_intent(goal="track this", steps=[_make_step()])

        with _orchestrator_ctx() as (orch, mocks):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("track this", None, None)):
                with patch("zenus_core.orchestrator.execute_plan", return_value=["result"]):
                    orch.execute_command("track this")

            mocks["_tracker"].end_transaction.assert_called_once_with("txn-1", "completed")


# ---------------------------------------------------------------------------
# execute_command — execution failure
# ---------------------------------------------------------------------------

class TestExecuteCommandFailure:

    def test_execution_exception_returns_error_message(self):
        intent = _make_intent(goal="risky", steps=[_make_step()])

        with _orchestrator_ctx() as (orch, mocks):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("risky", None, None)):
                with patch("zenus_core.orchestrator.execute_plan",
                           side_effect=RuntimeError("disk full")):
                    result = orch.execute_command("risky")

            assert "disk full" in result or "error" in result.lower()

    def test_execution_failure_ends_transaction_as_failed(self):
        intent = _make_intent(goal="fail", steps=[_make_step()])

        with _orchestrator_ctx() as (orch, mocks):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("fail", None, None)):
                with patch("zenus_core.orchestrator.execute_plan",
                           side_effect=RuntimeError("crash")):
                    orch.execute_command("fail")

            mocks["_tracker"].end_transaction.assert_called_once_with("txn-1", "failed")


# ---------------------------------------------------------------------------
# execute_command — iterative detection
# ---------------------------------------------------------------------------

class TestExecuteCommandIterativeDetection:

    def test_complex_task_delegates_to_execute_iterative(self):
        with _orchestrator_ctx() as (orch, mocks):
            mocks["_ta"].analyze.return_value = Mock(
                needs_iteration=True,
                confidence=0.9,
                reasoning="complex multi-step task",
                estimated_steps=5,
            )
            orch.execute_iterative = Mock(return_value="iterative result")

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("complex task", None, None)):
                result = orch.execute_command("complex task")

            orch.execute_iterative.assert_called_once()
            assert result == "iterative result"

    def test_force_oneshot_skips_iterative_detection(self):
        intent = _make_intent(goal="force one shot")

        with _orchestrator_ctx() as (orch, mocks):
            mocks["_ta"].analyze.return_value = Mock(needs_iteration=True)
            orch.execute_iterative = Mock(return_value="should not be called")
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mocks["get_llm"].return_value = mock_llm

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("force one shot", None, None)):
                with patch("zenus_core.orchestrator.execute_plan", return_value=["ok"]):
                    result = orch.execute_command("force one shot", force_oneshot=True)

            orch.execute_iterative.assert_not_called()


# ---------------------------------------------------------------------------
# execute_command — adaptive planner path
# ---------------------------------------------------------------------------

class TestExecuteCommandAdaptive:

    def test_adaptive_planner_used_when_enabled(self):
        intent = _make_intent(goal="adaptive", steps=[_make_step()])

        with _orchestrator_ctx(adaptive=True, use_sandbox=False) as (orch, mocks):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mocks["get_llm"].return_value = mock_llm

            mock_planner = Mock()
            mock_planner.execute_with_retry.return_value = ["adapted result"]
            orch.adaptive_planner = mock_planner

            with patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("adaptive", None, None)):
                result = orch.execute_command("adaptive")

            mock_planner.execute_with_retry.assert_called_once()
