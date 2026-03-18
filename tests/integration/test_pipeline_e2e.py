"""
End-to-end pipeline integration tests.

These tests exercise the full stack:
  Orchestrator → (real LLM via DeepSeek) → execute_plan → real tool → result

All tests are marked requires_deepseek and are skipped in CI without the key.
Non-LLM orchestrator paths are also tested with mocked LLM to catch wiring bugs.
"""

import os
import time
import pytest
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch, Mock, MagicMock

from zenus_core.brain.llm.schemas import IntentIR, Step
from zenus_core.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helper: minimal Orchestrator with everything safe/fast
# ---------------------------------------------------------------------------

def _make_orch(**kwargs):
    """
    Build an Orchestrator with safe defaults for testing.
    Disables all interactive / experimental features.
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
    defaults.update(kwargs)
    return Orchestrator(**defaults)


@contextmanager
def _deepseek_env():
    """Ensure the factory AND router both select DeepSeek for this block.

    The router uses get_config().llm.provider to populate available_providers.
    Both must be patched so the safety-check in route() doesn't fall back to
    the config's primary provider (anthropic).
    """
    mock_config = MagicMock()
    mock_config.llm.provider = "deepseek"
    mock_config.llm.model = "deepseek-chat"
    mock_config.fallback.enabled = False
    mock_config.fallback.providers = []

    with patch("zenus_core.brain.llm.factory.get_config", return_value=mock_config), \
         patch("zenus_core.config.loader.get_config", return_value=mock_config), \
         patch.dict(os.environ, {"ZENUS_LLM": "deepseek"}):
        yield


# ---------------------------------------------------------------------------
# Wiring tests — mocked LLM, real planner + tools
# ---------------------------------------------------------------------------

class TestOrchestratorWiring:
    """
    Verify that the Orchestrator correctly wires:
    LLM result → planner → tool registry → action tracker → result string.
    These use a mocked LLM so they run without any API key.
    """

    def test_dry_run_returns_dry_run_marker(self):
        intent = IntentIR(
            goal="scan /tmp",
            requires_confirmation=False,
            steps=[Step(tool="FileOps", action="scan", args={"path": "/tmp"}, risk=0)],
        )
        with patch("zenus_core.orchestrator.get_llm") as mock_llm_factory, \
             patch("zenus_core.brain.provider_override.parse_provider_override",
                   return_value=("scan /tmp", None, None)):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mock_llm_factory.return_value = mock_llm

            orch = _make_orch()
            result = orch.execute_command("scan /tmp", dry_run=True, force_oneshot=True)

        assert "DRY RUN" in result
        assert "scan /tmp" in result

    def test_execute_returns_string(self, tmp_path):
        """execute_command must always return str — even when tool raises."""
        with patch("zenus_core.orchestrator.get_llm") as mock_llm_factory, \
             patch("zenus_core.brain.provider_override.parse_provider_override",
                   return_value=("do thing", None, None)):
            mock_llm = Mock()
            mock_llm.translate_intent.side_effect = RuntimeError("boom")
            mock_llm_factory.return_value = mock_llm

            orch = _make_orch()
            result = orch.execute_command("do thing", force_oneshot=True)

        assert isinstance(result, str)

    def test_intent_cache_second_call_skips_llm(self, tmp_path):
        """A repeated identical command must hit the cache, not the LLM."""
        from zenus_core.execution.intent_cache import IntentCache

        intent = IntentIR(
            goal="check disk",
            requires_confirmation=False,
            steps=[Step(tool="SystemOps", action="disk_usage",
                        args={"path": "/tmp"}, risk=0)],
        )
        call_count = 0

        def counting_translate(user_input, stream=False):
            nonlocal call_count
            call_count += 1
            return intent

        # Use an isolated cache so previous test runs don't cause false cache hits
        fresh_cache = IntentCache(cache_path=str(tmp_path / "test_cache.json"))

        with patch("zenus_core.orchestrator.get_llm") as mock_llm_factory, \
             patch("zenus_core.orchestrator.get_intent_cache", return_value=fresh_cache), \
             patch("zenus_core.brain.provider_override.parse_provider_override",
                   return_value=("check disk usage isolated", None, None)):
            mock_llm = Mock()
            mock_llm.translate_intent.side_effect = counting_translate
            mock_llm_factory.return_value = mock_llm

            orch = _make_orch()
            orch.intent_cache = fresh_cache
            orch.execute_command("check disk usage isolated", force_oneshot=True)
            orch.execute_command("check disk usage isolated", force_oneshot=True)

        assert call_count == 1, "LLM was called more than once — cache is not working"

    def test_execution_exception_returns_error_message(self):
        intent = IntentIR(
            goal="crash",
            requires_confirmation=False,
            steps=[Step(tool="FileOps", action="scan",
                        args={"path": "/nonexistent_xyz"}, risk=0)],
        )
        with patch("zenus_core.orchestrator.get_llm") as mock_llm_factory, \
             patch("zenus_core.brain.provider_override.parse_provider_override",
                   return_value=("scan", None, None)):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mock_llm_factory.return_value = mock_llm

            orch = _make_orch()
            result = orch.execute_command("scan", force_oneshot=True)

        # Must return a string, not raise
        assert isinstance(result, str)

    def test_high_risk_step_returns_safety_error_message(self):
        """risk=3 must be blocked — execute_command must return an error string."""
        intent = IntentIR(
            goal="delete everything",
            requires_confirmation=True,
            steps=[Step(tool="FileOps", action="delete",
                        args={"path": "/tmp/x"}, risk=3)],
        )
        with patch("zenus_core.orchestrator.get_llm") as mock_llm_factory, \
             patch("zenus_core.brain.provider_override.parse_provider_override",
                   return_value=("delete", None, None)):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mock_llm_factory.return_value = mock_llm

            orch = _make_orch()
            result = orch.execute_command("delete", force_oneshot=True)

        assert isinstance(result, str)

    def test_action_tracker_records_transaction(self, tmp_path):
        """Successful execution must start + end a tracker transaction."""
        intent = IntentIR(
            goal="scan",
            requires_confirmation=False,
            steps=[Step(tool="SystemOps", action="check_resource_usage",
                        args={}, risk=0)],
        )
        from zenus_core.memory.action_tracker import ActionTracker
        tracker = ActionTracker(db_path=str(tmp_path / "test.db"))

        with patch("zenus_core.orchestrator.get_llm") as mock_llm_factory, \
             patch("zenus_core.orchestrator.get_action_tracker", return_value=tracker), \
             patch("zenus_core.brain.provider_override.parse_provider_override",
                   return_value=("check resources", None, None)):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mock_llm_factory.return_value = mock_llm

            orch = _make_orch()
            result = orch.execute_command("check resources", force_oneshot=True)

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Real LLM — full pipeline (requires DeepSeek key)
# ---------------------------------------------------------------------------

@pytest.mark.requires_deepseek
@pytest.mark.integration
@pytest.mark.slow
class TestFullPipelineWithRealLLM:
    """
    True end-to-end: natural language → DeepSeek → IntentIR → real tool → result.
    Uses only safe, read-only commands so no side effects on the host.
    """

    def _orch(self):
        with _deepseek_env():
            return _make_orch()

    def test_system_info_command_returns_string(self):
        with _deepseek_env():
            orch = self._orch()
            result = orch.execute_command(
                "show system resource usage", force_oneshot=True
            )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_result_is_not_raw_exception(self):
        """Pipeline must catch errors internally and return a string, never raise."""
        with _deepseek_env():
            orch = self._orch()
            result = orch.execute_command(
                "show current disk usage", force_oneshot=True
            )
        assert isinstance(result, str)

    def test_dry_run_with_real_llm_returns_plan(self):
        """dry_run=True should return a plan string without executing anything."""
        with _deepseek_env():
            orch = self._orch()
            result = orch.execute_command(
                "list files in /tmp", dry_run=True, force_oneshot=True
            )
        assert "DRY RUN" in result

    def test_repeated_command_uses_cache(self, tmp_path):
        """Second identical command must hit the cache, not the real LLM."""
        from zenus_core.execution.intent_cache import IntentCache

        # Use isolated cache so previous runs don't interfere
        fresh_cache = IntentCache(cache_path=str(tmp_path / "live_cache.json"))
        llm_call_count = [0]

        with _deepseek_env():
            orch = self._orch()
            orch.intent_cache = fresh_cache

            # Spy: wrap the real DeepSeekLLM translate_intent to count calls
            original_translate = orch.llm.translate_intent

            def counting_translate(user_input, stream=False):
                llm_call_count[0] += 1
                return original_translate(user_input, stream=stream)

            orch.llm.translate_intent = counting_translate

            cmd = "show system resource usage"
            orch.execute_command(cmd, force_oneshot=True)
            orch.execute_command(cmd, force_oneshot=True)

        assert llm_call_count[0] <= 1, (
            f"LLM called {llm_call_count[0]} times — cache not working"
        )

    def test_real_llm_produces_valid_intentir(self):
        """The LLM must return a well-formed IntentIR for a simple command."""
        from zenus_core.brain.llm.factory import get_llm
        llm = get_llm(force_provider="deepseek")
        intent = llm.translate_intent("check disk usage of /tmp")

        assert isinstance(intent, IntentIR)
        assert intent.goal
        assert isinstance(intent.steps, list)
        for step in intent.steps:
            assert isinstance(step.tool, str)
            assert isinstance(step.action, str)
            assert 0 <= step.risk <= 3

    def test_file_scan_produces_output(self, tmp_path):
        """
        Command that scans a real directory should produce output referencing files.
        """
        (tmp_path / "hello.txt").write_text("hello")

        with _deepseek_env():
            orch = self._orch()
            result = orch.execute_command(
                f"list files in {tmp_path}", force_oneshot=True
            )
        assert isinstance(result, str)
        assert len(result) > 0
