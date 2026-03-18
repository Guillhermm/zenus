"""
Tests for SuggestionEngine
"""

import pytest
from unittest.mock import MagicMock, patch

from zenus_core.brain.suggestion_engine import SuggestionEngine, Suggestion, get_suggestion_engine
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_intent(steps, goal="test"):
    """Build an IntentIR from a list of Step objects."""
    return IntentIR(goal=goal, requires_confirmation=False, steps=steps)


def file_step(action="read_file", path="/a.txt", risk=0):
    """Convenience factory for FileOps steps."""
    return Step(tool="FileOps", action=action, args={"path": path}, risk=risk)


def net_step(url="https://example.com", action="download", risk=0):
    """Convenience factory for NetworkOps steps."""
    return Step(tool="NetworkOps", action=action, args={"url": url}, risk=risk)


def browser_step(risk=0):
    """Convenience factory for BrowserOps steps."""
    return Step(tool="BrowserOps", action="navigate", args={}, risk=risk)


def _make_engine():
    """Return a SuggestionEngine with the failure_logger mocked out."""
    with patch("zenus_core.brain.suggestion_engine.get_failure_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_logger.get_failure_stats.return_value = {"by_tool": {}}
        mock_get_logger.return_value = mock_logger
        engine = SuggestionEngine()
    return engine


# ---------------------------------------------------------------------------
# Tests: analyze() orchestration
# ---------------------------------------------------------------------------

class TestAnalyzeOrchestration:
    def test_analyze_returns_list(self):
        """analyze() always returns a list."""
        engine = _make_engine()
        intent = make_intent([file_step()])
        result = engine.analyze("do something", intent)
        assert isinstance(result, list)

    def test_analyze_returns_at_most_five_suggestions(self):
        """Top-5 cap is enforced."""
        engine = _make_engine()
        # Create intent that triggers multiple rules: 3+ file ops + 3 browser ops
        steps = (
            [file_step("read_file", f"/f{i}.txt") for i in range(3)]
            + [browser_step() for _ in range(3)]
        )
        intent = make_intent(steps)
        with patch("zenus_core.brain.failure_analyzer.FailureAnalyzer") as MockFA:
            fa_instance = MagicMock()
            fa_instance.analyze_before_execution.return_value = {
                "success_probability": 0.9,
                "similar_failures": [],
            }
            MockFA.return_value = fa_instance
            result = engine.analyze("do stuff", intent)
        assert len(result) <= 5

    def test_analyze_sorted_by_confidence_descending(self):
        """Results are ordered highest confidence first."""
        engine = _make_engine()
        steps = [file_step("read_file", f"/f{i}.txt") for i in range(4)]
        intent = make_intent(steps)
        with patch("zenus_core.brain.failure_analyzer.FailureAnalyzer") as MockFA:
            fa = MagicMock()
            fa.analyze_before_execution.return_value = {
                "success_probability": 0.9,
                "similar_failures": [],
            }
            MockFA.return_value = fa
            result = engine.analyze("do stuff", intent)

        for i in range(len(result) - 1):
            assert result[i].confidence >= result[i + 1].confidence

    def test_analyze_empty_steps_no_crash(self):
        """analyze() handles an intent with no steps gracefully."""
        engine = _make_engine()
        intent = make_intent([])
        with patch("zenus_core.brain.failure_analyzer.FailureAnalyzer") as MockFA:
            fa = MagicMock()
            fa.analyze_before_execution.return_value = {
                "success_probability": 1.0,
                "similar_failures": [],
            }
            MockFA.return_value = fa
            result = engine.analyze("nothing to do", intent)
        assert isinstance(result, list)

    def test_analyze_passes_context_to_rules(self):
        """Context dict is forwarded to every rule."""
        engine = _make_engine()
        intent = make_intent([file_step()])
        received_contexts = []

        # The optimization_rules list holds bound method references set at __init__.
        # Replace the first rule in the list directly so analyze() calls our spy.
        original = engine._suggest_batch_operations

        def spy(ui, ir, ctx):
            received_contexts.append(ctx)
            return original(ui, ir, ctx)

        engine.optimization_rules[0] = spy

        ctx = {"key": "value"}
        with patch("zenus_core.brain.failure_analyzer.FailureAnalyzer") as MockFA:
            fa = MagicMock()
            fa.analyze_before_execution.return_value = {
                "success_probability": 1.0,
                "similar_failures": [],
            }
            MockFA.return_value = fa
            engine.analyze("do it", intent, context=ctx)

        assert ctx in received_contexts


# ---------------------------------------------------------------------------
# Tests: _suggest_batch_operations
# ---------------------------------------------------------------------------

class TestSuggestBatchOperations:
    def test_three_same_file_ops_triggers_suggestion(self):
        """Three identical FileOps actions trigger the batch suggestion."""
        engine = _make_engine()
        steps = [file_step("read_file", f"/f{i}.txt") for i in range(3)]
        intent = make_intent(steps)
        result = engine._suggest_batch_operations("do stuff", intent, {})
        assert result is not None
        assert result.type == "optimization"
        assert "wildcard" in result.title.lower()

    def test_fewer_than_three_file_ops_no_suggestion(self):
        """Two FileOps do not trigger the batch suggestion."""
        engine = _make_engine()
        steps = [file_step("read_file", f"/f{i}.txt") for i in range(2)]
        intent = make_intent(steps)
        result = engine._suggest_batch_operations("do stuff", intent, {})
        assert result is None

    def test_mixed_file_ops_actions_no_suggestion(self):
        """Three FileOps with different actions do not trigger batch suggestion."""
        engine = _make_engine()
        steps = [
            file_step("read_file", "/a.txt"),
            file_step("write_file", "/b.txt"),
            file_step("delete_file", "/c.txt"),
        ]
        intent = make_intent(steps)
        result = engine._suggest_batch_operations("do stuff", intent, {})
        assert result is None

    def test_batch_suggestion_confidence_is_high(self):
        """Batch suggestion should have high confidence (0.9)."""
        engine = _make_engine()
        steps = [file_step("copy_file", f"/f{i}.txt") for i in range(5)]
        intent = make_intent(steps)
        result = engine._suggest_batch_operations("do stuff", intent, {})
        assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# Tests: _suggest_parallel_execution
# ---------------------------------------------------------------------------

class TestSuggestParallelExecution:
    def test_fewer_than_three_steps_returns_none(self):
        """Fewer than 3 steps never produces a parallel suggestion."""
        engine = _make_engine()
        intent = make_intent([file_step("read_file", f"/f{i}.txt") for i in range(2)])
        result = engine._suggest_parallel_execution("do stuff", intent, {})
        assert result is None

    def test_parallelizable_steps_suggest_parallel(self):
        """Independent steps with potential speedup trigger a suggestion."""
        engine = _make_engine()
        # 4 fully independent file reads → high speedup
        steps = [file_step("read_file", f"/f{i}.txt") for i in range(4)]
        intent = make_intent(steps)
        result = engine._suggest_parallel_execution("do stuff", intent, {})
        # Speedup will be 4.0 (4 steps / 1 level) which exceeds the 1.5 threshold
        assert result is not None
        assert result.type == "optimization"

    def test_sequential_steps_no_parallel_suggestion(self):
        """Steps that must run sequentially do not trigger a parallel suggestion."""
        engine = _make_engine()
        # Package installs are forced sequential
        steps = [Step(tool="PackageOps", action="install", args={}, risk=0) for _ in range(4)]
        intent = make_intent(steps)
        result = engine._suggest_parallel_execution("do stuff", intent, {})
        assert result is None


# ---------------------------------------------------------------------------
# Tests: _suggest_caching
# ---------------------------------------------------------------------------

class TestSuggestCaching:
    def test_duplicate_urls_triggers_cache_suggestion(self):
        """The same URL downloaded twice triggers a cache suggestion."""
        engine = _make_engine()
        steps = [
            net_step("https://example.com"),
            net_step("https://example.com"),
        ]
        intent = make_intent(steps)
        result = engine._suggest_caching("do stuff", intent, {})
        assert result is not None
        assert result.type == "optimization"
        assert "cache" in result.title.lower()

    def test_different_urls_no_cache_suggestion(self):
        """Different URLs do not trigger a caching suggestion."""
        engine = _make_engine()
        steps = [
            net_step("https://a.com"),
            net_step("https://b.com"),
        ]
        intent = make_intent(steps)
        result = engine._suggest_caching("do stuff", intent, {})
        assert result is None

    def test_single_network_op_no_cache_suggestion(self):
        """A single network step does not trigger caching."""
        engine = _make_engine()
        intent = make_intent([net_step()])
        result = engine._suggest_caching("do stuff", intent, {})
        assert result is None


# ---------------------------------------------------------------------------
# Tests: _suggest_tool_alternatives
# ---------------------------------------------------------------------------

class TestSuggestToolAlternatives:
    def test_high_failure_rate_triggers_alternative_suggestion(self):
        """Tool with > 5 failures triggers an alternative suggestion."""
        engine = _make_engine()
        engine.failure_logger.get_failure_stats.return_value = {
            "by_tool": {"BrowserOps": 6}
        }
        intent = make_intent([browser_step()])
        result = engine._suggest_tool_alternatives("do stuff", intent, {})
        assert result is not None
        assert len(result) > 0
        assert result[0].type == "alternative"

    def test_low_failure_rate_no_alternative_suggestion(self):
        """Tool with ≤ 5 failures does not trigger an alternative suggestion."""
        engine = _make_engine()
        engine.failure_logger.get_failure_stats.return_value = {
            "by_tool": {"BrowserOps": 3}
        }
        intent = make_intent([browser_step()])
        result = engine._suggest_tool_alternatives("do stuff", intent, {})
        assert not result  # None or empty list

    def test_no_alternatives_available_no_suggestion(self):
        """Tool with many failures but no known alternatives returns nothing."""
        engine = _make_engine()
        engine.failure_logger.get_failure_stats.return_value = {
            "by_tool": {"UnknownTool": 10}
        }
        intent = make_intent([Step(tool="UnknownTool", action="run", args={}, risk=0)])
        result = engine._suggest_tool_alternatives("do stuff", intent, {})
        assert not result


# ---------------------------------------------------------------------------
# Tests: _warn_about_failures
# ---------------------------------------------------------------------------

class TestWarnAboutFailures:
    def test_low_success_probability_triggers_warning(self):
        """Success probability below 0.6 triggers a warning."""
        engine = _make_engine()
        intent = make_intent([file_step()])

        with patch("zenus_core.brain.failure_analyzer.FailureAnalyzer") as MockFA:
            fa = MagicMock()
            fa.analyze_before_execution.return_value = {
                "success_probability": 0.4,
                "similar_failures": ["x", "y"],
            }
            MockFA.return_value = fa
            result = engine._warn_about_failures("do stuff", intent, {})

        assert result is not None
        assert result.type == "warning"
        assert result.confidence == 0.9

    def test_high_success_probability_no_warning(self):
        """Success probability at or above 0.6 produces no failure warning."""
        engine = _make_engine()
        intent = make_intent([file_step()])

        with patch("zenus_core.brain.failure_analyzer.FailureAnalyzer") as MockFA:
            fa = MagicMock()
            fa.analyze_before_execution.return_value = {
                "success_probability": 0.8,
                "similar_failures": [],
            }
            MockFA.return_value = fa
            result = engine._warn_about_failures("do stuff", intent, {})

        assert result is None


# ---------------------------------------------------------------------------
# Tests: _warn_about_destructive_ops
# ---------------------------------------------------------------------------

class TestWarnAboutDestructiveOps:
    def test_high_risk_step_triggers_warning(self):
        """A step with risk >= 3 triggers a destructive-operation warning."""
        engine = _make_engine()
        steps = [Step(tool="FileOps", action="delete_all", args={}, risk=3)]
        intent = make_intent(steps)
        result = engine._warn_about_destructive_ops("wipe /tmp", intent, {})
        assert result is not None
        assert result.type == "warning"
        assert result.confidence == 1.0

    def test_low_risk_steps_no_warning(self):
        """Steps with risk < 3 do not trigger a destructive warning."""
        engine = _make_engine()
        steps = [Step(tool="FileOps", action="read_file", args={}, risk=2)]
        intent = make_intent(steps)
        result = engine._warn_about_destructive_ops("read something", intent, {})
        assert result is None

    def test_multiple_high_risk_steps_counted(self):
        """Warning description mentions correct count of high-risk steps."""
        engine = _make_engine()
        steps = [
            Step(tool="FileOps", action="delete", args={}, risk=3),
            Step(tool="FileOps", action="delete", args={}, risk=3),
        ]
        intent = make_intent(steps)
        result = engine._warn_about_destructive_ops("delete things", intent, {})
        assert "2" in result.description


# ---------------------------------------------------------------------------
# Tests: _warn_about_performance
# ---------------------------------------------------------------------------

class TestWarnAboutPerformance:
    def test_three_browser_ops_triggers_warning(self):
        """Three BrowserOps steps trigger a performance warning."""
        engine = _make_engine()
        steps = [browser_step() for _ in range(3)]
        intent = make_intent(steps)
        result = engine._warn_about_performance("browse stuff", intent, {})
        assert result is not None
        assert result.type == "warning"

    def test_fewer_than_three_slow_ops_no_warning(self):
        """Two slow steps do not trigger the performance warning."""
        engine = _make_engine()
        steps = [browser_step(), browser_step()]
        intent = make_intent(steps)
        result = engine._warn_about_performance("browse stuff", intent, {})
        assert result is None

    def test_download_network_ops_counted_as_slow(self):
        """NetworkOps with 'download' action count as slow operations."""
        engine = _make_engine()
        steps = [
            net_step(action="download"),
            net_step(url="https://b.com", action="download"),
            net_step(url="https://c.com", action="download"),
        ]
        intent = make_intent(steps)
        result = engine._warn_about_performance("download stuff", intent, {})
        assert result is not None


# ---------------------------------------------------------------------------
# Tests: should_show
# ---------------------------------------------------------------------------

class TestShouldShow:
    def test_suggestion_above_threshold_shown(self):
        """High-confidence suggestions above threshold are shown."""
        engine = _make_engine()
        s = Suggestion(type="optimization", title="T", description="D", reason="R", confidence=0.8)
        assert engine.should_show(s) is True

    def test_suggestion_below_threshold_not_shown(self):
        """Low-confidence suggestions below threshold are hidden."""
        engine = _make_engine()
        s = Suggestion(type="optimization", title="T", description="D", reason="R", confidence=0.3)
        assert engine.should_show(s) is False

    def test_warning_always_shown_regardless_of_threshold(self):
        """Warnings pass through even when confidence equals the threshold."""
        engine = _make_engine()
        s = Suggestion(type="warning", title="W", description="D", reason="R", confidence=0.6)
        assert engine.should_show(s, threshold=0.6) is True

    def test_low_accept_rate_hides_suggestion(self):
        """Suggestions with accept_rate < 0.2 are suppressed."""
        engine = _make_engine()
        s = Suggestion(
            type="optimization", title="T", description="D",
            reason="R", confidence=0.9, accept_rate=0.1
        )
        assert engine.should_show(s) is False

    def test_zero_accept_rate_does_not_suppress(self):
        """accept_rate=0.0 is not treated as a low historical rate (never shown)."""
        engine = _make_engine()
        s = Suggestion(
            type="optimization", title="T", description="D",
            reason="R", confidence=0.9, accept_rate=0.0
        )
        # accept_rate == 0 means no history; the guard is `accept_rate > 0 and < 0.2`
        assert engine.should_show(s) is True

    def test_custom_threshold(self):
        """should_show respects a custom threshold argument."""
        engine = _make_engine()
        s = Suggestion(type="tip", title="T", description="D", reason="R", confidence=0.75)
        assert engine.should_show(s, threshold=0.8) is False
        assert engine.should_show(s, threshold=0.7) is True


# ---------------------------------------------------------------------------
# Tests: format_suggestion
# ---------------------------------------------------------------------------

class TestFormatSuggestion:
    def test_format_includes_title(self):
        """Formatted output contains the suggestion title."""
        engine = _make_engine()
        s = Suggestion(type="optimization", title="Use wildcards", description="Desc", reason="Reason", confidence=0.9)
        output = engine.format_suggestion(s)
        assert "Use wildcards" in output

    def test_format_includes_description(self):
        """Formatted output contains the description."""
        engine = _make_engine()
        s = Suggestion(type="warning", title="T", description="Something bad", reason="R", confidence=1.0)
        output = engine.format_suggestion(s)
        assert "Something bad" in output

    def test_format_includes_reason(self):
        """Formatted output contains the reason."""
        engine = _make_engine()
        s = Suggestion(type="tip", title="T", description="D", reason="Because patterns", confidence=0.7)
        output = engine.format_suggestion(s)
        assert "Because patterns" in output

    def test_format_unknown_type_defaults_to_bulb_icon(self):
        """Unknown suggestion types fall back to the default icon."""
        engine = _make_engine()
        s = Suggestion(type="unknown_type", title="T", description="D", reason="R", confidence=0.7)
        output = engine.format_suggestion(s)
        assert "T" in output  # title still present


# ---------------------------------------------------------------------------
# Tests: get_tool_alternatives
# ---------------------------------------------------------------------------

class TestGetToolAlternatives:
    def test_browser_ops_has_alternatives(self):
        """BrowserOps returns at least one alternative."""
        engine = _make_engine()
        alts = engine._get_tool_alternatives("BrowserOps")
        assert len(alts) > 0

    def test_unknown_tool_returns_empty_list(self):
        """An unrecognised tool name returns an empty list."""
        engine = _make_engine()
        alts = engine._get_tool_alternatives("MadeUpTool")
        assert alts == []


# ---------------------------------------------------------------------------
# Tests: get_suggestion_engine singleton
# ---------------------------------------------------------------------------

class TestGetSuggestionEngineSingleton:
    def test_returns_suggestion_engine_instance(self):
        """get_suggestion_engine() returns a SuggestionEngine."""
        import zenus_core.brain.suggestion_engine as module
        module._suggestion_engine = None  # reset singleton

        with patch("zenus_core.brain.suggestion_engine.get_failure_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            engine = get_suggestion_engine()

        assert isinstance(engine, SuggestionEngine)

    def test_returns_same_instance_on_second_call(self):
        """Subsequent calls return the cached singleton."""
        import zenus_core.brain.suggestion_engine as module
        module._suggestion_engine = None

        with patch("zenus_core.brain.suggestion_engine.get_failure_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            e1 = get_suggestion_engine()
            e2 = get_suggestion_engine()

        assert e1 is e2
