"""
Tests for Failure Logger
"""

import pytest
import tempfile
import os
from pathlib import Path
from zenus_core.memory.failure_logger import FailureLogger, Failure


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_failures.db")
        yield db_path


@pytest.fixture
def logger(temp_db):
    """Create logger instance with temp database"""
    return FailureLogger(db_path=temp_db)


def test_logger_initialization(logger, temp_db):
    """Test logger creates database and tables"""
    assert os.path.exists(temp_db)
    
    # Verify tables exist
    import sqlite3
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('failures', 'failure_patterns')
    """)
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    
    assert 'failures' in tables
    assert 'failure_patterns' in tables


def test_log_simple_failure(logger):
    """Test logging a basic failure"""
    failure_id = logger.log_failure(
        user_input="delete system32",
        intent_goal="Delete system files",
        tool="FileOps",
        error_type="permission_denied",
        error_message="Permission denied: /system32",
        context={"cwd": "/home/user"}
    )
    
    assert failure_id > 0


def test_log_failure_with_context(logger):
    """Test logging failure with full context"""
    context = {
        "directory": {"path": "~/projects", "project_name": "zenus"},
        "git": {"is_repo": True, "branch": "main", "status": "clean"},
        "time": {"time_of_day": "morning", "hour": 10}
    }
    
    failure_id = logger.log_failure(
        user_input="git push origin main",
        intent_goal="Push changes to remote",
        tool="GitOps",
        error_type="network_error",
        error_message="Connection refused: github.com:443",
        context=context
    )
    
    assert failure_id > 0


def test_get_similar_failures(logger):
    """Test retrieving similar failures"""
    # Log some failures
    for i in range(3):
        logger.log_failure(
            user_input=f"npm install package-{i}",
            intent_goal="Install npm package",
            tool="PackageOps",
            error_type="network_error",
            error_message=f"ECONNREFUSED: Connection refused at {i}",
            context={}
        )
    
    # Retrieve similar failures
    similar = logger.get_similar_failures(
        user_input="npm install another-package",
        tool="PackageOps",
        limit=2
    )
    
    assert len(similar) == 2
    assert all(isinstance(f, Failure) for f in similar)
    assert all(f.tool == "PackageOps" for f in similar)


def test_pattern_tracking(logger):
    """Test failure pattern tracking"""
    # Log the same error multiple times
    for i in range(3):
        logger.log_failure(
            user_input=f"read file-{i}.txt",
            intent_goal="Read file",
            tool="FileOps",
            error_type="permission_denied",
            error_message="Permission denied: /root/file.txt",
            context={}
        )
    
    # Pattern should be tracked
    import sqlite3
    conn = sqlite3.connect(logger.db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT count FROM failure_patterns WHERE count >= 3")
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None
    assert result[0] >= 3


def test_normalize_error(logger):
    """Test error normalization for pattern matching"""
    # Test path normalization
    assert "<path>" in logger._normalize_error("/usr/local/bin/file.txt")
    
    # Test number normalization (function uses <NUM> uppercase)
    normalized_line = logger._normalize_error("Error on line 42")
    assert "<n>" in normalized_line  # After lowercase conversion
    
    # Test case normalization
    normalized = logger._normalize_error("FILE NOT FOUND")
    assert normalized.islower()


def test_get_failure_stats(logger):
    """Test getting failure statistics"""
    # Log various failures
    logger.log_failure("test1", "goal1", "FileOps", "permission_denied", "Error 1", {})
    logger.log_failure("test2", "goal2", "FileOps", "file_not_found", "Error 2", {})
    logger.log_failure("test3", "goal3", "NetworkOps", "network_error", "Error 3", {})
    
    stats = logger.get_failure_stats()
    
    assert stats["total_failures"] == 3
    assert "FileOps" in stats["by_tool"]
    assert stats["by_tool"]["FileOps"] == 2
    assert "permission_denied" in stats["by_error_type"]


def test_pattern_suggestions(logger):
    """Test adding and retrieving pattern suggestions"""
    # Log a failure
    logger.log_failure(
        user_input="docker run image",
        intent_goal="Run container",
        tool="ContainerOps",
        error_type="permission_denied",
        error_message="Permission denied: /var/run/docker.sock",
        context={}
    )
    
    # This would normally be set by a human or learning system
    # For now, test the mechanism
    suggestion = logger.get_pattern_suggestions("ContainerOps", "Permission denied")
    
    # Initially no suggestion
    assert suggestion is None


def test_failure_with_resolution(logger):
    """Test logging failure with resolution"""
    failure_id = logger.log_failure(
        user_input="npm install",
        intent_goal="Install dependencies",
        tool="PackageOps",
        error_type="network_error",
        error_message="ECONNREFUSED",
        context={},
        resolution="Switched to yarn and succeeded"
    )
    
    assert failure_id > 0
    
    # Verify resolution was stored
    import sqlite3
    conn = sqlite3.connect(logger.db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT resolution FROM failures WHERE id = ?", (failure_id,))
    result = cursor.fetchone()
    conn.close()
    
    assert result[0] == "Switched to yarn and succeeded"


def test_recent_failures_only(logger):
    """Test filtering by recent failures"""
    # Log an old failure (would require manual DB manipulation in real test)
    # For now, just verify the stats tracking works
    
    logger.log_failure("test1", "goal1", "FileOps", "error1", "msg1", {})
    
    stats = logger.get_failure_stats()
    assert stats["recent_7_days"] >= 1


def test_multiple_patterns_same_tool(logger):
    """Test tracking multiple different patterns for the same tool"""
    # Log different error types for same tool
    logger.log_failure("test1", "goal1", "FileOps", "permission_denied", "Permission denied", {})
    logger.log_failure("test2", "goal2", "FileOps", "file_not_found", "File not found", {})
    logger.log_failure("test3", "goal3", "FileOps", "disk_full", "No space left", {})
    
    stats = logger.get_failure_stats()
    assert stats["total_failures"] == 3
    assert len(stats["by_error_type"]) == 3
