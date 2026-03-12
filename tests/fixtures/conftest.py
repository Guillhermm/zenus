"""
Shared test fixtures for Zenus tests
"""

import os
import tempfile
import shutil
import subprocess
import pytest
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    test_dir = tempfile.mkdtemp()
    yield test_dir
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


@pytest.fixture
def temp_cwd(temp_dir):
    """Change to temporary directory and restore after"""
    original_cwd = os.getcwd()
    os.chdir(temp_dir)
    yield temp_dir
    os.chdir(original_cwd)


@pytest.fixture
def git_repo(temp_cwd):
    """Create a temporary git repository"""
    # Initialize git repo
    subprocess.run(["git", "init"], capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], capture_output=True, check=True)
    
    # Create initial commit
    readme = Path(temp_cwd) / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(["git", "add", "."], capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], capture_output=True, check=True)
    
    yield temp_cwd


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing"""
    files = {
        "doc1.txt": "This is document 1",
        "doc2.txt": "This is document 2",
        "image1.jpg": b"\xFF\xD8\xFF\xE0",  # Fake JPEG header
        "data.csv": "name,age,city\nAlice,30,NYC\nBob,25,LA"
    }
    
    file_paths = {}
    for filename, content in files.items():
        file_path = Path(temp_dir) / filename
        
        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content)
        
        file_paths[filename] = file_path
    
    yield file_paths


@pytest.fixture
def sample_project_structure(temp_dir):
    """Create a sample project structure"""
    project_path = Path(temp_dir) / "sample-project"
    
    # Create directories
    dirs = [
        project_path / "src",
        project_path / "tests",
        project_path / "docs",
        project_path / "config"
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    # Create files
    (project_path / "README.md").write_text("# Sample Project\n")
    (project_path / ".gitignore").write_text("*.pyc\n__pycache__/\n")
    (project_path / "src" / "__init__.py").touch()
    (project_path / "tests" / "__init__.py").touch()
    (project_path / "src" / "main.py").write_text("def main():\n    pass\n")
    
    yield project_path


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing"""
    def _mock_response(prompt: str) -> str:
        """Return canned response based on prompt"""
        if "error" in prompt.lower():
            return "Mock error analysis: Connection timeout"
        elif "plan" in prompt.lower():
            return """Goal: Test goal
Steps:
1. Tool: FileOps, Action: scan, Args: {"path": "."}
2. Tool: SystemOps, Action: check_resource_usage, Args: {}"""
        else:
            return "Mock LLM response for testing"
    
    return _mock_response


@pytest.fixture
def mock_tool_registry():
    """Mock tool registry for testing"""
    from zenus_core.tools.registry import ToolRegistry
    from zenus_core.tools.file_ops import FileOps
    from zenus_core.tools.system_ops import SystemOps
    
    registry = ToolRegistry()
    registry.register_tool("FileOps", FileOps())
    registry.register_tool("SystemOps", SystemOps())
    
    return registry


@pytest.fixture(scope="session")
def test_config():
    """Test configuration"""
    return {
        "test_timeout": 30,
        "slow_test_timeout": 60,
        "temp_dir_prefix": "zenus_test_",
        "max_file_size_mb": 100,
        "enable_slow_tests": True
    }


@pytest.fixture
def clean_environment():
    """Clean environment variables for tests"""
    # Save original environment
    original_env = os.environ.copy()
    
    # Clear Zenus-specific env vars
    zenus_vars = [k for k in os.environ if k.startswith("ZENUS_")]
    for var in zenus_vars:
        os.environ.pop(var, None)
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def capture_logs(caplog):
    """Capture logs for testing"""
    import logging
    caplog.set_level(logging.DEBUG)
    yield caplog
