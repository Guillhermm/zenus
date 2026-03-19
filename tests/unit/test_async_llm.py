"""
Tests for async LLM methods and async orchestrator execution.

All LLM calls are mocked — no real API calls are made.
Tests verify:
- LLM base class async fallback via asyncio.to_thread
- AnthropicLLM has native async methods
- Orchestrator.async_execute_command delegates correctly
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from zenus_core.brain.llm.base import LLM
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_intent(goal: str = "test goal") -> IntentIR:
    return IntentIR(
        goal=goal,
        requires_confirmation=False,
        steps=[Step(tool="file_ops", action="scan", args={}, risk=0)],
    )


class _SyncLLM(LLM):
    """Minimal concrete LLM that only has sync methods."""

    def __init__(self):
        self.call_count = 0

    def translate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        self.call_count += 1
        return _make_intent(user_input)

    def reflect_on_goal(self, reflection_prompt, user_goal, observations):
        return "ACHIEVED: yes"

    def generate(self, prompt: str) -> str:
        return f"response to: {prompt}"

    def ask(self, question: str, context: str = "") -> str:
        return f"answer to: {question}"


# ---------------------------------------------------------------------------
# LLM base class async fallback
# ---------------------------------------------------------------------------

class TestLLMAsyncFallback:
    @pytest.mark.asyncio
    async def test_atranslate_intent_calls_sync_under_the_hood(self):
        llm = _SyncLLM()
        result = await llm.atranslate_intent("list files")
        assert isinstance(result, IntentIR)
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_atranslate_intent_returns_intentir(self):
        llm = _SyncLLM()
        result = await llm.atranslate_intent("show disk usage")
        assert result.goal == "show disk usage"

    @pytest.mark.asyncio
    async def test_areflect_on_goal_calls_sync(self):
        llm = _SyncLLM()
        result = await llm.areflect_on_goal("prompt", "goal", ["obs1"])
        assert result == "ACHIEVED: yes"

    @pytest.mark.asyncio
    async def test_agenerate_calls_sync(self):
        llm = _SyncLLM()
        result = await llm.agenerate("hello")
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_concurrent_atranslate_intent(self):
        """Multiple concurrent calls must all complete and not interfere."""
        llm = _SyncLLM()
        inputs = [f"command {i}" for i in range(10)]
        results = await asyncio.gather(*[llm.atranslate_intent(inp) for inp in inputs])
        assert len(results) == 10
        assert all(isinstance(r, IntentIR) for r in results)
        assert llm.call_count == 10

    @pytest.mark.asyncio
    async def test_async_methods_present_on_base(self):
        llm = _SyncLLM()
        assert callable(getattr(llm, "atranslate_intent", None))
        assert callable(getattr(llm, "areflect_on_goal", None))
        assert callable(getattr(llm, "agenerate", None))


# ---------------------------------------------------------------------------
# AnthropicLLM — native async methods exist
# ---------------------------------------------------------------------------

class TestAnthropicLLMAsyncMethods:
    def _make_anthropic_llm(self):
        """Build AnthropicLLM with fully mocked clients."""
        with patch("zenus_core.brain.llm.anthropic_llm.Anthropic") as mock_sync, \
             patch("zenus_core.brain.llm.anthropic_llm.AsyncAnthropic") as mock_async, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):

            mock_sync_instance = MagicMock()
            mock_sync.return_value = mock_sync_instance

            mock_async_instance = MagicMock()
            mock_async.return_value = mock_async_instance

            from zenus_core.brain.llm.anthropic_llm import AnthropicLLM
            llm = AnthropicLLM()
            llm.async_client = mock_async_instance

        return llm, mock_async_instance

    def test_atranslate_intent_method_exists(self):
        from zenus_core.brain.llm.anthropic_llm import AnthropicLLM
        assert hasattr(AnthropicLLM, "atranslate_intent")

    def test_areflect_on_goal_method_exists(self):
        from zenus_core.brain.llm.anthropic_llm import AnthropicLLM
        assert hasattr(AnthropicLLM, "areflect_on_goal")

    def test_agenerate_method_exists(self):
        from zenus_core.brain.llm.anthropic_llm import AnthropicLLM
        assert hasattr(AnthropicLLM, "agenerate")

    @pytest.mark.asyncio
    async def test_atranslate_intent_calls_async_client(self):
        llm, mock_async = self._make_anthropic_llm()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"goal":"test","requires_confirmation":false,"steps":[]}')]
        mock_async.messages.create = AsyncMock(return_value=mock_response)

        result = await llm.atranslate_intent("test command")
        assert isinstance(result, IntentIR)
        mock_async.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_agenerate_calls_async_client(self):
        llm, mock_async = self._make_anthropic_llm()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="async response")]
        mock_async.messages.create = AsyncMock(return_value=mock_response)

        result = await llm.agenerate("hello async")
        assert result == "async response"
        mock_async.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_areflect_on_goal_calls_async_client(self):
        llm, mock_async = self._make_anthropic_llm()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ACHIEVED: yes")]
        mock_async.messages.create = AsyncMock(return_value=mock_response)

        result = await llm.areflect_on_goal("prompt", "goal", [])
        assert result == "ACHIEVED: yes"


# ---------------------------------------------------------------------------
# Orchestrator async_execute_command
# ---------------------------------------------------------------------------

class TestOrchestratorAsyncExecute:
    def _make_orchestrator(self) -> "Orchestrator":
        """Build a minimal Orchestrator with mocked LLM and components."""
        with patch("zenus_core.orchestrator.get_llm") as mock_get_llm, \
             patch("zenus_core.orchestrator.get_logger"), \
             patch("zenus_core.orchestrator.get_action_tracker"), \
             patch("zenus_core.orchestrator.get_parallel_executor"), \
             patch("zenus_core.orchestrator.get_intent_cache"), \
             patch("zenus_core.orchestrator.get_feedback_collector"), \
             patch("zenus_core.orchestrator.get_metrics_collector"), \
             patch("zenus_core.orchestrator.get_formatter"), \
             patch("zenus_core.orchestrator.get_suggestion_engine"), \
             patch("zenus_core.orchestrator.get_router"), \
             patch("zenus_core.orchestrator.get_context_manager"), \
             patch("zenus_core.orchestrator.get_tree_of_thoughts"), \
             patch("zenus_core.orchestrator.get_prompt_evolution"), \
             patch("zenus_core.orchestrator.get_goal_inference"), \
             patch("zenus_core.orchestrator.get_self_reflection"), \
             patch("zenus_core.orchestrator.get_proactive_monitor"), \
             patch("zenus_core.orchestrator.get_multi_agent_system"):
            mock_get_llm.return_value = _SyncLLM()
            from zenus_core.orchestrator import Orchestrator
            orch = Orchestrator(
                enable_tree_of_thoughts=False,
                enable_prompt_evolution=False,
                enable_goal_inference=False,
                enable_multi_agent=False,
                enable_proactive_monitoring=False,
                enable_self_reflection=False,
                enable_visualization=False,
                show_progress=False,
                use_memory=False,
                adaptive=False,
            )
        return orch

    @pytest.mark.asyncio
    async def test_async_execute_returns_string(self):
        orch = self._make_orchestrator()
        orch.execute_command = MagicMock(return_value="done")
        result = await orch.async_execute_command("list files")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_async_execute_delegates_to_sync(self):
        orch = self._make_orchestrator()
        orch.execute_command = MagicMock(return_value="sync result")
        result = await orch.async_execute_command("test input")
        orch.execute_command.assert_called_once()
        assert result == "sync result"

    @pytest.mark.asyncio
    async def test_async_execute_passes_dry_run(self):
        orch = self._make_orchestrator()
        orch.execute_command = MagicMock(return_value="dry run done")
        await orch.async_execute_command("delete files", dry_run=True)
        call_kwargs = orch.execute_command.call_args
        assert call_kwargs[0][1] is True  # dry_run positional arg

    @pytest.mark.asyncio
    async def test_async_execute_concurrent_calls(self):
        orch = self._make_orchestrator()
        orch.execute_command = MagicMock(side_effect=lambda *a, **kw: f"result:{a[0]}")
        results = await asyncio.gather(
            orch.async_execute_command("cmd1"),
            orch.async_execute_command("cmd2"),
            orch.async_execute_command("cmd3"),
        )
        assert len(results) == 3
        assert all("result:" in r for r in results)

    @pytest.mark.asyncio
    async def test_async_execute_propagates_exception(self):
        orch = self._make_orchestrator()
        orch.execute_command = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError, match="boom"):
            await orch.async_execute_command("bad command")

    def test_async_execute_method_is_coroutine(self):
        orch = self._make_orchestrator()
        import inspect
        assert inspect.iscoroutinefunction(orch.async_execute_command)
