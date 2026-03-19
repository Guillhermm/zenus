"""
Provider contract and factory tests.

Verifies:
  - LLM factory creates the right adapter based on config / env
  - Credential validation fires before network calls
  - Every adapter fulfils the LLM base-class interface
  - get_available_providers() reflects which keys are set
  - Unknown / missing provider raises the expected exceptions
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import deepseek_env as _deepseek_env  # noqa: E402

from zenus_core.brain.llm.factory import get_llm, get_available_providers
from zenus_core.brain.llm.deepseek_llm import DeepSeekLLM
from zenus_core.brain.llm.schemas import IntentIR


# ---------------------------------------------------------------------------
# Factory — provider selection
# ---------------------------------------------------------------------------

class TestLLMFactory:

    def test_force_deepseek_returns_deepseek(self):
        with patch("zenus_core.brain.llm.factory.DeepSeekLLM") as mock:
            mock.return_value = MagicMock(spec=DeepSeekLLM)
            llm = get_llm(force_provider="deepseek")
            mock.assert_called_once()

    def test_missing_provider_raises_environment_error(self):
        with patch("zenus_core.brain.llm.factory.get_config", side_effect=Exception):
            with patch.dict(os.environ, {}, clear=True):
                clean = {k: v for k, v in os.environ.items()
                         if k not in ("ZENUS_LLM", "ANTHROPIC_API_KEY",
                                      "DEEPSEEK_API_KEY", "OPENAI_API_KEY")}
                with patch.dict(os.environ, clean, clear=True):
                    with pytest.raises(EnvironmentError):
                        get_llm()

    def test_unknown_provider_raises_value_error(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-fake"}):
            with pytest.raises((ValueError, EnvironmentError)):
                get_llm(force_provider="nonexistent_provider_xyz")

    def test_missing_credentials_raises_environment_error(self):
        """Factory must raise before touching the network."""
        env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError, match="DEEPSEEK_API_KEY"):
                get_llm(force_provider="deepseek")

    def test_config_provider_takes_effect(self):
        """Config-level provider is respected when no force_provider given."""
        mock_config = MagicMock()
        mock_config.llm.provider = "deepseek"
        mock_config.llm.model = "deepseek-chat"

        with patch("zenus_core.brain.llm.factory.get_config", return_value=mock_config):
            with patch("zenus_core.brain.llm.factory.DeepSeekLLM") as mock_cls:
                mock_cls.return_value = MagicMock(spec=DeepSeekLLM)
                with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
                    get_llm()
                mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# get_available_providers
# ---------------------------------------------------------------------------

class TestGetAvailableProviders:

    def test_deepseek_present_when_key_set(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-fake"}):
            providers = get_available_providers()
            assert "deepseek" in providers

    def test_anthropic_present_when_key_set(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-fake"}):
            providers = get_available_providers()
            assert "anthropic" in providers

    def test_deepseek_absent_when_key_missing(self):
        env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            providers = get_available_providers()
            assert "deepseek" not in providers

    def test_returns_list(self):
        providers = get_available_providers()
        assert isinstance(providers, list)

    def test_no_keys_returns_default(self):
        """With no keys configured, list falls back gracefully."""
        clean = {k: v for k, v in os.environ.items()
                 if k not in ("ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY")}
        with patch.dict(os.environ, clean, clear=True):
            providers = get_available_providers()
            assert isinstance(providers, list)
            assert len(providers) >= 1


# ---------------------------------------------------------------------------
# DeepSeek interface compliance (mocked — no network)
# ---------------------------------------------------------------------------

class TestDeepSeekInterfaceCompliance:
    """Verify DeepSeekLLM satisfies the LLM base contract without real calls."""

    @pytest.fixture
    def llm(self):
        mock_config = MagicMock()
        mock_config.llm.provider = "deepseek"
        mock_config.llm.model = "deepseek-chat"
        mock_config.llm.max_tokens = 8192
        with patch("openai.OpenAI") as mock_openai, \
             patch("zenus_core.config.loader.get_config", return_value=mock_config):
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
                return DeepSeekLLM()

    def test_has_translate_intent(self, llm):
        assert callable(getattr(llm, "translate_intent", None))

    def test_has_reflect_on_goal(self, llm):
        assert callable(getattr(llm, "reflect_on_goal", None))

    def test_has_generate(self, llm):
        assert callable(getattr(llm, "generate", None))

    def test_translate_intent_returns_intentir_from_valid_json(self, llm):
        raw_json = (
            '{"goal": "scan tmp", "requires_confirmation": false, '
            '"steps": [{"tool": "FileOps", "action": "scan", '
            '"args": {"path": "/tmp"}, "risk": 0}]}'
        )
        llm.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=raw_json))]
        )
        result = llm.translate_intent("list files in /tmp")
        assert isinstance(result, IntentIR)
        assert result.goal == "scan tmp"
        assert len(result.steps) == 1
        assert result.steps[0].tool == "FileOps"

    def test_generate_returns_string(self, llm):
        llm.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Hello!"))]
        )
        result = llm.generate("say hello")
        assert isinstance(result, str)
        assert result == "Hello!"

    def test_reflect_on_goal_non_stream_returns_string(self, llm):
        llm.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="ACHIEVED: YES"))]
        )
        result = llm.reflect_on_goal("did we finish?", "finish task", ["done"])
        assert isinstance(result, str)
        assert "ACHIEVED" in result

    def test_translate_intent_bad_json_raises_runtime_error(self, llm):
        llm.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="I cannot do that."))]
        )
        with pytest.raises(RuntimeError):
            llm.translate_intent("do something")

    def test_default_model_is_deepseek_chat(self, llm):
        assert llm.model == "deepseek-chat"

    def test_max_tokens_positive(self, llm):
        assert llm.max_tokens > 0


# ---------------------------------------------------------------------------
# Live provider round-trip (real API)
# ---------------------------------------------------------------------------

@pytest.mark.requires_deepseek
@pytest.mark.integration
class TestDeepSeekLiveRoundTrip:

    def test_factory_creates_deepseek_that_can_translate(self):
        """Factory → DeepSeekLLM → translate_intent round-trip."""
        with _deepseek_env():
            llm = get_llm(force_provider="deepseek")
            assert isinstance(llm, DeepSeekLLM)
            intent = llm.translate_intent("show disk usage of /tmp")
        assert isinstance(intent, IntentIR)
        assert len(intent.goal) > 0
