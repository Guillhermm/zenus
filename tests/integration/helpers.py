"""
Shared helpers for integration tests.

Kept in tests/integration/ so imports are unambiguous — no sys.path tricks needed.
"""

import os
from contextlib import contextmanager
from unittest.mock import patch, MagicMock


@contextmanager
def deepseek_env():
    """Force every config/factory/router call to use DeepSeek.

    Patches all layers that can override provider selection:
    - zenus_core.config.loader.get_config  — used by factory and model_router
    - zenus_core.brain.llm.factory.get_config — direct import in factory
    - ZENUS_LLM env var — last-resort fallback

    Usage::

        with deepseek_env():
            orch = Orchestrator(...)
            result = orch.execute_command("...", force_oneshot=True)
    """
    mock_config = MagicMock()
    mock_config.llm.provider = "deepseek"
    mock_config.llm.model = "deepseek-chat"
    mock_config.llm.max_tokens = 8192
    mock_config.fallback.enabled = False
    mock_config.fallback.providers = []

    with patch("zenus_core.brain.llm.factory.get_config", return_value=mock_config), \
         patch("zenus_core.config.loader.get_config", return_value=mock_config), \
         patch.dict(os.environ, {"ZENUS_LLM": "deepseek"}):
        yield
