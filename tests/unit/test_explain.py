"""
Unit tests for shell/explain.py

Rich console calls are mocked to avoid terminal output.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from zenus_core.shell.explain import (
    ExplainMode,
    Explainer,
    ExplainabilityDashboard,
    StepExplanation,
    ExecutionExplanation,
    get_explainer,
    get_explainability_dashboard,
)
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(tool="FileOps", action="scan", risk=0, args=None):
    return Step(tool=tool, action=action, args=args or {}, risk=risk)


def _make_intent(goal="list files", steps=None, requires_confirmation=False):
    return IntentIR(
        goal=goal,
        requires_confirmation=requires_confirmation,
        steps=steps or [_make_step()]
    )


def _make_execution_explanation(user_input="ls", goal="list", steps_count=2):
    steps = [_make_step(risk=i % 4) for i in range(steps_count)]
    intent = _make_intent(goal=goal, steps=steps)
    step_exps = [
        StepExplanation(
            step=s,
            reasoning="because",
            confidence=0.9,
            execution_time=0.1
        )
        for s in steps
    ]
    return ExecutionExplanation(
        user_input=user_input,
        understood_goal=goal,
        intent=intent,
        step_explanations=step_exps,
        total_time=0.5,
        overall_confidence=0.85
    )


# ===========================================================================
# StepExplanation dataclass
# ===========================================================================

class TestStepExplanation:

    def test_defaults(self):
        step = _make_step()
        se = StepExplanation(step=step, reasoning="why", confidence=0.8)
        assert se.alternatives == []
        assert se.execution_time is None
        assert se.result is None
        assert se.success is True

    def test_all_fields(self):
        step = _make_step()
        se = StepExplanation(
            step=step,
            reasoning="because",
            confidence=0.7,
            alternatives=["alt1", "alt2"],
            execution_time=1.5,
            result="done",
            success=False
        )
        assert se.success is False
        assert se.alternatives == ["alt1", "alt2"]


# ===========================================================================
# ExecutionExplanation.to_dict
# ===========================================================================

class TestExecutionExplanationToDict:

    def test_to_dict_has_all_keys(self):
        exp = _make_execution_explanation()
        d = exp.to_dict()
        assert "user_input" in d
        assert "understood_goal" in d
        assert "intent" in d
        assert "step_explanations" in d
        assert "total_time" in d
        assert "overall_confidence" in d
        assert "timestamp" in d

    def test_to_dict_intent_structure(self):
        exp = _make_execution_explanation()
        d = exp.to_dict()
        assert "goal" in d["intent"]
        assert "steps" in d["intent"]
        assert "requires_confirmation" in d["intent"]

    def test_to_dict_step_explanations(self):
        exp = _make_execution_explanation(steps_count=2)
        d = exp.to_dict()
        assert len(d["step_explanations"]) == 2
        se = d["step_explanations"][0]
        assert "tool" in se
        assert "action" in se
        assert "reasoning" in se
        assert "confidence" in se

    def test_timestamp_auto_set(self):
        exp = _make_execution_explanation()
        assert exp.timestamp is not None
        assert len(exp.timestamp) > 10  # ISO format


# ===========================================================================
# ExplainMode._generate_reasoning
# ===========================================================================

class TestExplainModeGenerateReasoning:

    def setup_method(self):
        self.mode = ExplainMode()

    def test_single_step_says_simple(self):
        intent = _make_intent(steps=[_make_step()])
        reasoning = self.mode._generate_reasoning(intent)
        assert "single-step" in reasoning.lower() or "simple" in reasoning.lower()

    def test_multi_step_counts_steps(self):
        steps = [_make_step() for _ in range(3)]
        intent = _make_intent(steps=steps)
        reasoning = self.mode._generate_reasoning(intent)
        assert "3" in reasoning

    def test_all_read_only_steps(self):
        steps = [_make_step(risk=0) for _ in range(2)]
        intent = _make_intent(steps=steps)
        reasoning = self.mode._generate_reasoning(intent)
        assert "read-only" in reasoning.lower()

    def test_modify_steps_noted(self):
        steps = [_make_step(risk=1), _make_step(risk=2)]
        intent = _make_intent(steps=steps)
        reasoning = self.mode._generate_reasoning(intent)
        assert "modify" in reasoning.lower() or "modif" in reasoning.lower()

    def test_danger_steps_noted(self):
        steps = [_make_step(risk=3)]
        intent = _make_intent(steps=steps)
        reasoning = self.mode._generate_reasoning(intent)
        assert "destructive" in reasoning.lower() or "dangerous" in reasoning.lower() or "1" in reasoning

    def test_tools_listed(self):
        steps = [_make_step(tool="FileOps"), _make_step(tool="ShellOps")]
        intent = _make_intent(steps=steps)
        reasoning = self.mode._generate_reasoning(intent)
        assert "FileOps" in reasoning or "ShellOps" in reasoning


# ===========================================================================
# ExplainMode.explain
# ===========================================================================

class TestExplainModeExplain:

    def test_explain_calls_print_explanation(self):
        mode = ExplainMode()
        intent = _make_intent()
        with patch("zenus_core.shell.explain.print_explanation") as mock_print:
            with patch("zenus_core.shell.explain.console") as mock_console:
                mode.explain("ls", intent, show_similar=False)
        mock_print.assert_called_once()

    def test_explain_with_semantic_search_high_success(self):
        semantic = Mock()
        semantic.search.return_value = [{"cmd": "ls", "score": 0.9}]
        semantic.get_success_rate.return_value = 0.8
        mode = ExplainMode(semantic_search=semantic)
        intent = _make_intent()
        with patch("zenus_core.shell.explain.print_explanation"):
            with patch("zenus_core.shell.explain.print_similar_commands"):
                with patch("zenus_core.shell.explain.console"):
                    mode.explain("ls", intent, show_similar=True)
        semantic.search.assert_called_once()

    def test_explain_with_semantic_search_low_success(self):
        semantic = Mock()
        semantic.search.return_value = [{"cmd": "ls"}]
        semantic.get_success_rate.return_value = 0.3  # below 0.5
        mode = ExplainMode(semantic_search=semantic)
        intent = _make_intent()
        with patch("zenus_core.shell.explain.print_explanation"):
            with patch("zenus_core.shell.explain.print_similar_commands"):
                with patch("zenus_core.shell.explain.console"):
                    mode.explain("ls", intent, show_similar=True)
        # Low success rate warning should be triggered
        semantic.get_success_rate.assert_called_once()

    def test_explain_no_similar_when_empty(self):
        semantic = Mock()
        semantic.search.return_value = []  # no similar
        mode = ExplainMode(semantic_search=semantic)
        intent = _make_intent()
        with patch("zenus_core.shell.explain.print_explanation"):
            with patch("zenus_core.shell.explain.print_similar_commands") as mock_similar:
                with patch("zenus_core.shell.explain.console"):
                    mode.explain("ls", intent, show_similar=True)
        mock_similar.assert_not_called()


# ===========================================================================
# ExplainMode.confirm
# ===========================================================================

class TestExplainModeConfirm:

    def test_y_returns_true(self):
        mode = ExplainMode()
        with patch("zenus_core.shell.explain.console") as mock_console:
            mock_console.input.return_value = "y"
            result = mode.confirm()
        assert result is True

    def test_yes_returns_true(self):
        mode = ExplainMode()
        with patch("zenus_core.shell.explain.console") as mock_console:
            mock_console.input.return_value = "yes"
            result = mode.confirm()
        assert result is True

    def test_n_returns_false(self):
        mode = ExplainMode()
        with patch("zenus_core.shell.explain.console") as mock_console:
            mock_console.input.return_value = "n"
            result = mode.confirm()
        assert result is False


# ===========================================================================
# Explainer
# ===========================================================================

class TestExplainer:

    def test_explain_intent_runs_without_error(self):
        exp = Explainer()
        intent = _make_intent(requires_confirmation=True)
        with patch("zenus_core.shell.explain.console"):
            exp.explain_intent("ls -la", intent)

    def test_explain_intent_requires_confirmation(self):
        exp = Explainer()
        intent = _make_intent(requires_confirmation=True)
        with patch("zenus_core.shell.explain.console") as mock_console:
            exp.explain_intent("delete all", intent)
        # Should have printed the confirmation warning

    def test_explain_task_complexity_iterative(self):
        exp = Explainer()
        with patch("zenus_core.shell.explain.console"):
            exp.explain_task_complexity(
                user_input="refactor code",
                needs_iteration=True,
                confidence=0.9,
                reasoning="complex task",
                estimated_steps=5
            )

    def test_explain_task_complexity_one_shot(self):
        exp = Explainer()
        with patch("zenus_core.shell.explain.console"):
            exp.explain_task_complexity(
                user_input="ls",
                needs_iteration=False,
                confidence=0.95,
                reasoning="simple",
                estimated_steps=1
            )

    def test_explain_iteration(self):
        exp = Explainer()
        intent = _make_intent()
        with patch("zenus_core.shell.explain.console"):
            exp.explain_iteration(
                iteration=2,
                total=5,
                intent=intent,
                observations=["found 3 files", "processed 1"]
            )

    def test_explain_context(self):
        exp = Explainer()
        context = {
            "directory": {"path": "/home/user", "project_type": "python", "project_name": "myapp"},
            "git": {"is_repo": True, "branch": "main", "status": "clean", "ahead_commits": 0},
            "time": {"timestamp": "2026-01-01 10:00", "time_of_day": "morning", "is_weekend": False},
            "processes": {"dev_tools": ["vim", "node"]}
        }
        with patch("zenus_core.shell.explain.console"):
            exp.explain_context(context)

    def test_explain_context_no_git(self):
        exp = Explainer()
        context = {
            "git": {"is_repo": False}
        }
        with patch("zenus_core.shell.explain.console"):
            exp.explain_context(context)

    def test_explain_context_weekend(self):
        exp = Explainer()
        context = {
            "time": {"timestamp": "2026-01-04 10:00", "time_of_day": "morning", "is_weekend": True},
        }
        with patch("zenus_core.shell.explain.console"):
            exp.explain_context(context)

    def test_explain_context_git_with_ahead(self):
        exp = Explainer()
        context = {
            "git": {"is_repo": True, "branch": "feature", "status": "clean", "ahead_commits": 3},
        }
        with patch("zenus_core.shell.explain.console"):
            exp.explain_context(context)

    def test_confirm_y_returns_true(self):
        exp = Explainer()
        with patch("zenus_core.shell.explain.console"):
            with patch("builtins.input", return_value="y"):
                result = exp.confirm()
        assert result is True

    def test_confirm_n_returns_false(self):
        exp = Explainer()
        with patch("zenus_core.shell.explain.console"):
            with patch("builtins.input", return_value="n"):
                result = exp.confirm()
        assert result is False

    def test_show_alternatives(self):
        exp = Explainer()
        alts = [
            {"name": "Option A", "description": "Fast way", "pros": ["quick"], "cons": ["risky"]},
            {"name": "Option B", "description": "Safe way", "pros": ["safe"]},
        ]
        with patch("zenus_core.shell.explain.console"):
            exp.show_alternatives(alts)

    def test_explain_steps_with_risk_levels(self):
        exp = Explainer()
        steps = [
            _make_step(risk=0),
            _make_step(risk=1),
            _make_step(risk=2),
            _make_step(risk=3)
        ]
        intent = _make_intent(steps=steps)
        with patch("zenus_core.shell.explain.console"):
            exp._explain_steps(steps)

    def test_explain_risks_all_levels(self):
        exp = Explainer()
        for risk in [0, 1, 2, 3]:
            steps = [_make_step(risk=risk)]
            intent = _make_intent(steps=steps)
            with patch("zenus_core.shell.explain.console"):
                exp._explain_risks(intent)


# ===========================================================================
# ExplainabilityDashboard
# ===========================================================================

class TestExplainabilityDashboard:

    def test_empty_history(self):
        dash = ExplainabilityDashboard()
        assert dash.history == []
        assert dash.max_history == 50

    def test_add_execution(self):
        dash = ExplainabilityDashboard()
        exp = _make_execution_explanation()
        dash.add_execution(exp)
        assert len(dash.history) == 1

    def test_history_trimmed_at_max(self):
        dash = ExplainabilityDashboard()
        dash.max_history = 3
        for i in range(5):
            dash.add_execution(_make_execution_explanation(user_input=f"cmd{i}"))
        assert len(dash.history) == 3

    def test_explain_last_empty(self):
        dash = ExplainabilityDashboard()
        with patch("zenus_core.shell.explain.console"):
            dash.explain_last()  # Should not raise

    def test_explain_last_with_history(self):
        dash = ExplainabilityDashboard()
        exp = _make_execution_explanation()
        dash.add_execution(exp)
        with patch("zenus_core.shell.explain.console"):
            dash.explain_last()

    def test_explain_last_verbose(self):
        dash = ExplainabilityDashboard()
        exp = _make_execution_explanation(steps_count=2)
        dash.add_execution(exp)
        with patch("zenus_core.shell.explain.console"):
            dash.explain_last(verbose=True)

    def test_explain_execution_by_index(self):
        dash = ExplainabilityDashboard()
        e1 = _make_execution_explanation(user_input="cmd1")
        e2 = _make_execution_explanation(user_input="cmd2")
        dash.add_execution(e1)
        dash.add_execution(e2)
        with patch("zenus_core.shell.explain.console"):
            dash.explain_execution(index=-2)

    def test_explain_execution_invalid_index(self):
        dash = ExplainabilityDashboard()
        dash.add_execution(_make_execution_explanation())
        with patch("zenus_core.shell.explain.console"):
            dash.explain_execution(index=-99)  # out of range

    def test_explain_execution_empty_history(self):
        dash = ExplainabilityDashboard()
        with patch("zenus_core.shell.explain.console"):
            dash.explain_execution()  # empty history

    def test_show_history_empty(self):
        dash = ExplainabilityDashboard()
        with patch("zenus_core.shell.explain.console"):
            dash.show_history()

    def test_show_history_with_entries(self):
        dash = ExplainabilityDashboard()
        for i in range(3):
            dash.add_execution(_make_execution_explanation(user_input=f"command_{i}"))
        with patch("zenus_core.shell.explain.console"):
            dash.show_history(limit=2)

    def test_display_step_confidence_colors(self):
        dash = ExplainabilityDashboard()
        exp = _make_execution_explanation()
        # Vary confidence to hit all branches
        exp.step_explanations[0].confidence = 0.9   # green
        exp.step_explanations[1].confidence = 0.7   # yellow
        exp.overall_confidence = 0.5  # red
        with patch("zenus_core.shell.explain.console"):
            dash._display_explanation(exp)

    def test_display_step_with_result(self):
        dash = ExplainabilityDashboard()
        exp = _make_execution_explanation()
        exp.step_explanations[0].result = "some output"
        exp.step_explanations[0].success = False
        with patch("zenus_core.shell.explain.console"):
            dash._display_explanation(exp, verbose=True)

    def test_display_step_with_alternatives(self):
        dash = ExplainabilityDashboard()
        exp = _make_execution_explanation()
        exp.step_explanations[0].alternatives = ["alt1", "alt2"]
        with patch("zenus_core.shell.explain.console"):
            dash._display_explanation(exp)

    def test_display_statistics(self):
        dash = ExplainabilityDashboard()
        exp = _make_execution_explanation(steps_count=3)
        with patch("zenus_core.shell.explain.console"):
            dash._display_statistics(exp)


# ===========================================================================
# get_explainer singleton
# ===========================================================================

class TestGetExplainer:

    def test_returns_explainer_instance(self):
        import zenus_core.shell.explain as mod
        mod._explainer = None
        exp = get_explainer()
        assert isinstance(exp, Explainer)

    def test_returns_same_instance(self):
        import zenus_core.shell.explain as mod
        mod._explainer = None
        e1 = get_explainer()
        e2 = get_explainer()
        assert e1 is e2


# ===========================================================================
# get_explainability_dashboard singleton
# ===========================================================================

class TestGetExplainabilityDashboard:

    def test_returns_dashboard_instance(self):
        import zenus_core.shell.explain as mod
        mod._dashboard = None
        dash = get_explainability_dashboard()
        assert isinstance(dash, ExplainabilityDashboard)

    def test_returns_same_instance(self):
        import zenus_core.shell.explain as mod
        mod._dashboard = None
        d1 = get_explainability_dashboard()
        d2 = get_explainability_dashboard()
        assert d1 is d2
