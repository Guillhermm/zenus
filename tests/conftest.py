"""
Pytest configuration and shared fixtures
"""

import os
import sys
import pytest
from pathlib import Path

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
