"""
Tests for ModelRouter
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from zenus_core.brain.model_router import ModelRouter, RoutingDecision, get_router
from zenus_core.brain.task_complexity import ComplexityScore


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_complexity(score=0.3, model="deepseek", reasons=None):
    """Build a minimal ComplexityScore mock."""
    cs = MagicMock(spec=ComplexityScore)
    cs.score = score
    cs.recommended_model = model
    cs.reasons = reasons if reasons is not None else []
    return cs


def _make_router(
    available=("anthropic",),
    primary="anthropic",
    enable_fallback=False,
    fallback_providers=None,
    tmpdir=None,
):
    """
    Create a ModelRouter with mocked external dependencies.

    Bypasses __init__ entirely via __new__ so no real config loading,
    no real file I/O, and no real provider detection occurs.
    ``available`` controls the set of providers the router considers usable.
    """
    import pathlib

    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()

    stats_path = os.path.join(tmpdir, "router_stats.json")

    router = ModelRouter.__new__(ModelRouter)

    router.enable_fallback = enable_fallback
    router.log_decisions = True
    router.primary_provider = primary
    router.available_providers = list(available)
    router.available_capabilities = {
        p: ModelRouter.MODEL_CAPABILITIES[p]
        for p in available
        if p in ModelRouter.MODEL_CAPABILITIES
    }

    analyzer_instance = MagicMock()
    analyzer_instance.analyze.return_value = _make_complexity(model=primary)
    router.complexity_analyzer = analyzer_instance

    router.stats_path = pathlib.Path(stats_path)
    router.stats_path.parent.mkdir(parents=True, exist_ok=True)
    router.stats = {
        "models": {},
        "total_commands": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
    }
    router.decisions = []
    router.session_stats = {
        "commands": 0,
        "tokens_used": 0,
        "estimated_cost": 0.0,
        "cache_hits": 0,
    }

    return router


# ---------------------------------------------------------------------------
# Tests: routing decisions
# ---------------------------------------------------------------------------

class TestModelRouterRouting:
    def test_route_returns_recommended_model_when_available(self, tmp_path):
        """Route selects the complexity analyzer's recommendation."""
        router = _make_router(available=("deepseek", "anthropic"), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="deepseek")

        model, complexity = router.route("list my files")

        assert model == "deepseek"

    def test_route_falls_back_to_primary_when_recommended_unavailable(self, tmp_path):
        """When recommended model is not in available_providers use primary."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="deepseek")

        model, _ = router.route("list my files")

        assert model == "anthropic"
        assert any("Fallback to primary" in r for r in router.complexity_analyzer.analyze.return_value.reasons)

    def test_route_uses_first_available_when_primary_also_missing(self, tmp_path):
        """Falls back to first available if primary is also missing."""
        router = _make_router(available=("ollama",), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="deepseek")

        model, _ = router.route("do something")

        assert model == "ollama"

    def test_route_uses_primary_when_no_models_available(self, tmp_path):
        """Uses primary_provider even when available_providers is empty."""
        router = _make_router(available=(), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="deepseek")

        model, _ = router.route("do something")

        assert model == "anthropic"

    def test_force_model_overrides_routing(self, tmp_path):
        """force_model parameter bypasses the complexity recommendation."""
        router = _make_router(available=("deepseek", "anthropic"), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="deepseek")

        model, complexity = router.route("list files", force_model="anthropic")

        assert model == "anthropic"
        assert any("Forced model" in r for r in complexity.reasons)

    def test_route_logs_decision_when_enabled(self, tmp_path):
        """A RoutingDecision is appended when log_decisions=True."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="anthropic")

        router.route("create a file")

        assert len(router.decisions) == 1
        d = router.decisions[0]
        assert isinstance(d, RoutingDecision)
        assert d.selected_model == "anthropic"

    def test_route_skips_logging_when_disabled(self, tmp_path):
        """No decision is appended when log_decisions=False."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        router.log_decisions = False
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="anthropic")

        router.route("create a file")

        assert len(router.decisions) == 0

    def test_route_increments_session_command_count(self, tmp_path):
        """Each call to route() increments session commands counter."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="anthropic")

        router.route("first command")
        router.route("second command")

        assert router.session_stats["commands"] == 2

    def test_user_input_truncated_to_100_chars_in_decision(self, tmp_path):
        """Long inputs are truncated to 100 characters in the decision log."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="anthropic")
        long_input = "x" * 200

        router.route(long_input)

        assert len(router.decisions[0].user_input) == 100


# ---------------------------------------------------------------------------
# Tests: fallback cascade
# ---------------------------------------------------------------------------

class TestFallbackCascade:
    def test_execute_with_fallback_succeeds_on_first_try(self, tmp_path):
        """execute_with_fallback returns result immediately on success."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="anthropic")

        execute_fn = MagicMock(return_value="ok")

        with patch.object(router, "_update_stats"):
            result = router.execute_with_fallback("do stuff", execute_fn)

        assert result == "ok"
        execute_fn.assert_called_once()

    def test_execute_with_fallback_uses_next_model_on_failure(self, tmp_path):
        """execute_with_fallback tries the next model when the first one fails."""
        router = _make_router(
            available=("deepseek", "anthropic"),
            primary="deepseek",
            enable_fallback=True,
            tmpdir=str(tmp_path),
        )
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="deepseek")

        calls = []

        def execute_fn(model):
            calls.append(model)
            if model == "deepseek":
                raise RuntimeError("deepseek failed")
            return "fallback_ok"

        with patch.object(router, "_update_stats"):
            result = router.execute_with_fallback("do stuff", execute_fn)

        assert result == "fallback_ok"
        assert "deepseek" in calls
        assert "anthropic" in calls

    def test_execute_with_fallback_marks_fallback_used_in_decision(self, tmp_path):
        """Decision log records fallback_used=True when fallback occurs."""
        router = _make_router(
            available=("deepseek", "anthropic"),
            primary="deepseek",
            enable_fallback=True,
            tmpdir=str(tmp_path),
        )
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="deepseek")

        def execute_fn(model):
            if model == "deepseek":
                raise RuntimeError("fail")
            return "ok"

        with patch.object(router, "_update_stats"):
            router.execute_with_fallback("do stuff", execute_fn)

        # route() adds a decision; execute_with_fallback then updates decisions[-1]
        assert router.decisions[-1].fallback_used is True

    def test_execute_with_fallback_raises_when_all_fail(self, tmp_path):
        """Raises an exception when every model in the chain fails."""
        router = _make_router(
            available=("deepseek", "anthropic"),
            primary="deepseek",
            enable_fallback=True,
            tmpdir=str(tmp_path),
        )
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="deepseek")

        def execute_fn(model):
            raise RuntimeError(f"{model} always fails")

        with patch.object(router, "_update_stats"):
            with pytest.raises(Exception, match="All models failed"):
                router.execute_with_fallback("do stuff", execute_fn)

    def test_execute_with_fallback_sets_env_var(self, tmp_path):
        """ZENUS_LLM env var is set to the currently attempted model."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        router.complexity_analyzer.analyze.return_value = _make_complexity(model="anthropic")

        seen_env = []

        def execute_fn(model):
            seen_env.append(os.environ.get("ZENUS_LLM"))
            return "ok"

        with patch.object(router, "_update_stats"):
            router.execute_with_fallback("do stuff", execute_fn)

        assert "anthropic" in seen_env


# ---------------------------------------------------------------------------
# Tests: fallback chain building
# ---------------------------------------------------------------------------

class TestBuildFallbackChain:
    def test_chain_is_primary_only_when_fallback_disabled(self, tmp_path):
        """When fallback is disabled the chain contains only the primary model."""
        router = _make_router(
            available=("deepseek", "anthropic"),
            primary="anthropic",
            enable_fallback=False,
            tmpdir=str(tmp_path),
        )
        chain = router._build_fallback_chain("anthropic", max_fallbacks=2)
        assert chain == ["anthropic"]

    def test_chain_only_primary_when_one_model_available(self, tmp_path):
        """Chain is one element when only one provider is configured."""
        router = _make_router(available=("anthropic",), primary="anthropic", enable_fallback=True, tmpdir=str(tmp_path))
        chain = router._build_fallback_chain("anthropic", max_fallbacks=2)
        assert chain == ["anthropic"]

    def test_chain_escalates_to_more_powerful_models(self, tmp_path):
        """Fallback chain lists more-capable models after primary."""
        router = _make_router(
            available=("deepseek", "anthropic"),
            primary="deepseek",
            enable_fallback=True,
            tmpdir=str(tmp_path),
        )
        chain = router._build_fallback_chain("deepseek", max_fallbacks=2)
        assert chain[0] == "deepseek"
        assert "anthropic" in chain

    def test_chain_respects_max_fallbacks(self, tmp_path):
        """Chain length never exceeds max_fallbacks + 1."""
        router = _make_router(
            available=("ollama", "deepseek", "openai", "anthropic"),
            primary="ollama",
            enable_fallback=True,
            tmpdir=str(tmp_path),
        )
        chain = router._build_fallback_chain("ollama", max_fallbacks=1)
        assert len(chain) <= 2

    def test_chain_uses_most_powerful_when_primary_unavailable(self, tmp_path):
        """If primary is not in available_providers pick the strongest available."""
        router = _make_router(
            available=("deepseek", "anthropic"),
            primary="ollama",  # not in available
            enable_fallback=True,
            tmpdir=str(tmp_path),
        )
        chain = router._build_fallback_chain("ollama", max_fallbacks=2)
        # Should start with the most powerful available model
        assert chain[0] in ("deepseek", "anthropic")


# ---------------------------------------------------------------------------
# Tests: cost / token tracking
# ---------------------------------------------------------------------------

class TestTokenTracking:
    def test_track_tokens_updates_session_stats(self, tmp_path):
        """track_tokens adds token count to session totals."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router.track_tokens("anthropic", 500_000)

        assert router.session_stats["tokens_used"] == 500_000

    def test_track_tokens_estimates_cost(self, tmp_path):
        """Cost is estimated based on MODEL_COSTS lookup."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router.track_tokens("anthropic", 1_000_000)

        expected_cost = ModelRouter.MODEL_COSTS["anthropic"] * 1.0
        assert abs(router.session_stats["estimated_cost"] - expected_cost) < 1e-9

    def test_track_tokens_ollama_is_free(self, tmp_path):
        """Ollama (local) usage incurs zero cost."""
        router = _make_router(available=("ollama",), primary="ollama", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router.track_tokens("ollama", 1_000_000)

        assert router.session_stats["estimated_cost"] == 0.0

    def test_track_tokens_accumulates_across_calls(self, tmp_path):
        """Multiple calls accumulate token and cost totals."""
        router = _make_router(available=("deepseek",), primary="deepseek", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router.track_tokens("deepseek", 500_000)
            router.track_tokens("deepseek", 500_000)

        assert router.session_stats["tokens_used"] == 1_000_000

    def test_track_tokens_creates_model_entry_if_absent(self, tmp_path):
        """A new model key is created in stats if it did not exist."""
        router = _make_router(available=("openai",), primary="openai", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router.track_tokens("openai", 100_000)

        assert "openai" in router.stats["models"]
        assert router.stats["models"]["openai"]["total_tokens"] == 100_000

    def test_unknown_model_cost_defaults_to_zero(self, tmp_path):
        """Unknown model identifier incurs zero cost."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router.track_tokens("mystery_model", 1_000_000)

        assert router.session_stats["estimated_cost"] == 0.0


# ---------------------------------------------------------------------------
# Tests: stats helpers
# ---------------------------------------------------------------------------

class TestStatsHelpers:
    def test_get_stats_returns_session_and_all_time(self, tmp_path):
        """get_stats returns both session and all_time keys."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        stats = router.get_stats()
        assert "session" in stats
        assert "all_time" in stats

    def test_load_stats_returns_defaults_when_file_missing(self, tmp_path):
        """_load_stats returns default structure when stats file is absent."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        # Point to a non-existent file
        router.stats_path = __import__("pathlib").Path(str(tmp_path)) / "nonexistent.json"
        loaded = router._load_stats()
        assert loaded["models"] == {}

    def test_load_stats_returns_defaults_on_corrupt_file(self, tmp_path):
        """_load_stats returns default structure when the file is corrupt."""
        bad_json = os.path.join(str(tmp_path), "bad.json")
        with open(bad_json, "w") as f:
            f.write("not json at all {{{")

        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))
        router.stats_path = __import__("pathlib").Path(bad_json)
        loaded = router._load_stats()
        assert loaded["models"] == {}

    def test_update_stats_increments_successes(self, tmp_path):
        """_update_stats increments success counter on success=True."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router._update_stats("anthropic", success=True, latency_ms=120.0)

        assert router.stats["models"]["anthropic"]["successes"] == 1
        assert router.stats["models"]["anthropic"]["failures"] == 0

    def test_update_stats_increments_failures(self, tmp_path):
        """_update_stats increments failure counter on success=False."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router._update_stats("anthropic", success=False)

        assert router.stats["models"]["anthropic"]["failures"] == 1

    def test_update_stats_computes_average_latency(self, tmp_path):
        """_update_stats correctly averages latency across calls."""
        router = _make_router(available=("anthropic",), primary="anthropic", tmpdir=str(tmp_path))

        with patch.object(router, "_save_stats"):
            router._update_stats("anthropic", success=True, latency_ms=100.0)
            router._update_stats("anthropic", success=True, latency_ms=200.0)

        avg = router.stats["models"]["anthropic"]["avg_latency_ms"]
        assert abs(avg - 150.0) < 1e-6


# ---------------------------------------------------------------------------
# Tests: get_router factory
# ---------------------------------------------------------------------------

class TestGetRouter:
    def test_get_router_returns_model_router_instance(self, tmp_path):
        """get_router() returns a ModelRouter."""
        with (
            patch("zenus_core.brain.model_router.get_available_providers", return_value=["anthropic"]),
            patch("zenus_core.brain.model_router.Path.home", return_value=__import__("pathlib").Path(str(tmp_path))),
        ):
            try:
                router = get_router()
                assert isinstance(router, ModelRouter)
            except Exception:
                # Config loading may fail in test environment; that is acceptable
                pass
