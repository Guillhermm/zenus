"""
Pytest configuration and shared fixtures
"""

import os
import sys
import pytest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add package src directories to path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root / "packages" / "core" / "src"))
sys.path.insert(0, str(root / "packages" / "cli" / "src"))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_deepseek: skip if DEEPSEEK_API_KEY is not set"
    )


def pytest_runtest_setup(item):
    """Auto-skip tests that need a real DeepSeek API key."""
    if item.get_closest_marker("requires_deepseek"):
        if not os.environ.get("DEEPSEEK_API_KEY"):
            pytest.skip("DEEPSEEK_API_KEY not set — skipping live LLM test")


@pytest.fixture(autouse=True)
def restore_cwd():
    """Restore the working directory after each test to prevent leakage."""
    original = os.getcwd()
    yield
    os.chdir(original)


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load .env from the project root so API keys are available in all tests."""
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))


@contextmanager
def deepseek_env():
    """Context manager that forces every config/factory/router call to use DeepSeek.

    Patches all three layers that can override provider selection:
    - zenus_core.config.loader.get_config  → used by factory and model_router
    - zenus_core.brain.llm.factory.get_config → direct import in factory
    - ZENUS_LLM env var → last-resort fallback

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


@pytest.fixture
def deepseek_llm():
    """Provide a real DeepSeek LLM instance (requires DEEPSEEK_API_KEY)."""
    from zenus_core.brain.llm.deepseek_llm import DeepSeekLLM
    return DeepSeekLLM()


@pytest.fixture
def isolated_tracker(tmp_path):
    """ActionTracker backed by a temp SQLite DB — safe for parallel tests."""
    from zenus_core.memory.action_tracker import ActionTracker
    return ActionTracker(db_path=str(tmp_path / "test_actions.db"))
