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


@pytest.fixture(autouse=True)
def restore_cwd():
    """Restore the working directory after each test to prevent leakage."""
    original = os.getcwd()
    yield
    os.chdir(original)
