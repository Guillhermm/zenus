"""
Tests for Rollback Engine
"""

import pytest
import tempfile
import os
import sqlite3
import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from zenus_core.memory.action_tracker import ActionTracker
from zenus_core.rollback import RollbackEngine, RollbackError


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_actions.db")
        yield db_path


@pytest.fixture
def tracker(temp_db):
    """Create tracker with temp database"""
    return ActionTracker(db_path=temp_db)


@pytest.fixture
def rollback_engine(tracker):
    """Create rollback engine with test tracker"""
    engine = RollbackEngine()
    engine.tracker = tracker
    return engine


def test_analyze_feasibility_all_rollbackable(tracker, rollback_engine):
    """Test feasibility analysis with all rollbackable actions"""
    tx_id = tracker.start_transaction("test", "test goal")
    
    tracker.track_action("FileOps", "create_file", {"path": "/tmp/a.txt"}, {}, tx_id)
    tracker.track_action("FileOps", "create_file", {"path": "/tmp/b.txt"}, {}, tx_id)
    
    actions = tracker.get_transaction_actions(tx_id)
    feasibility = rollback_engine.analyze_feasibility(actions)
    
    assert feasibility["possible"] is True
    assert feasibility["rollbackable_count"] == 2
    assert feasibility["non_rollbackable_count"] == 0


def test_analyze_feasibility_with_non_rollbackable(tracker, rollback_engine):
    """Test feasibility analysis with non-rollbackable actions"""
    tx_id = tracker.start_transaction("test", "test goal")
    
    tracker.track_action("FileOps", "create_file", {"path": "/tmp/a.txt"}, {}, tx_id)
    tracker.track_action("GitOps", "push", {"remote": "origin"}, {}, tx_id)
    
    actions = tracker.get_transaction_actions(tx_id)
    feasibility = rollback_engine.analyze_feasibility(actions)
    
    assert feasibility["possible"] is False
    assert feasibility["non_rollbackable_count"] == 1
    assert "GitOps.push" in feasibility["non_rollbackable"]


def test_describe_rollback_delete(rollback_engine, tracker):
    """Test rollback description for delete strategy"""
    from zenus_core.memory.action_tracker import Action
    
    action = Action(
        id=1,
        transaction_id="test",
        timestamp="2024-01-01T00:00:00",
        tool="FileOps",
        operation="create_file",
        params={},
        result={},
        rollback_possible=True,
        rollback_strategy="delete",
        rollback_data={"path": "/tmp/test.txt"}
    )
    
    description = rollback_engine._describe_rollback(action)
    assert "Delete" in description
    assert "/tmp/test.txt" in description


def test_describe_rollback_move_back(rollback_engine, tracker):
    """Test rollback description for move_back strategy"""
    from zenus_core.memory.action_tracker import Action
    
    action = Action(
        id=1,
        transaction_id="test",
        timestamp="2024-01-01T00:00:00",
        tool="FileOps",
        operation="move_file",
        params={},
        result={},
        rollback_possible=True,
        rollback_strategy="move_back",
        rollback_data={"from": "/tmp/new.txt", "to": "/tmp/old.txt"}
    )
    
    description = rollback_engine._describe_rollback(action)
    assert "Move" in description
    assert "/tmp/new.txt" in description
    assert "/tmp/old.txt" in description


def test_rollback_file_creation(tracker, rollback_engine):
    """Test rolling back file creation"""
    # Create a temporary file
    test_file = Path(tempfile.gettempdir()) / "rollback_test.txt"
    test_file.write_text("test content")
    
    try:
        # Track the creation
        tx_id = tracker.start_transaction("create file", "Create test file")
        tracker.track_action(
            "FileOps",
            "create_file",
            {"path": str(test_file)},
            {"success": True},
            tx_id
        )
        tracker.end_transaction(tx_id, "completed")
        
        # File should exist
        assert test_file.exists()
        
        # Rollback
        result = rollback_engine.rollback_transaction(tx_id, dry_run=False)
        
        assert result["success"] is True
        assert result["actions_rolled_back"] == 1
        assert not test_file.exists()  # File should be deleted
    
    finally:
        test_file.unlink(missing_ok=True)


def test_rollback_dry_run(tracker, rollback_engine):
    """Test rollback dry run mode"""
    test_file = Path(tempfile.gettempdir()) / "dry_run_test.txt"
    test_file.write_text("test")
    
    try:
        tx_id = tracker.start_transaction("test", "test goal")
        tracker.track_action(
            "FileOps",
            "create_file",
            {"path": str(test_file)},
            {},
            tx_id
        )
        
        result = rollback_engine.rollback_transaction(tx_id, dry_run=True)
        
        assert result["dry_run"] is True
        assert test_file.exists()  # File should still exist
    
    finally:
        test_file.unlink(missing_ok=True)


def test_rollback_with_non_rollbackable_action(tracker, rollback_engine):
    """Test rollback fails with non-rollbackable actions"""
    tx_id = tracker.start_transaction("test", "test goal")
    
    tracker.track_action("GitOps", "push", {"remote": "origin"}, {}, tx_id)
    tracker.end_transaction(tx_id, "completed")
    
    with pytest.raises(RollbackError) as exc_info:
        rollback_engine.rollback_transaction(tx_id, dry_run=False)
    
    assert "Cannot rollback" in str(exc_info.value)


def test_rollback_last_n_actions(tracker, rollback_engine):
    """Test rolling back last N actions"""
    # Create test files
    test_files = [Path(tempfile.gettempdir()) / f"test_{i}.txt" for i in range(3)]
    for f in test_files:
        f.write_text("test")
    
    try:
        # Track actions
        tx_id = tracker.start_transaction("create files", "Create multiple files")
        for f in test_files:
            tracker.track_action(
                "FileOps",
                "create_file",
                {"path": str(f)},
                {},
                tx_id
            )
        tracker.end_transaction(tx_id, "completed")
        
        # All files should exist
        assert all(f.exists() for f in test_files)
        
        # Rollback last 2 actions
        result = rollback_engine.rollback_last_n_actions(2, dry_run=False)
        
        assert result["success"] is True
        assert result["actions_rolled_back"] == 2
        
        # Last 2 files should be deleted
        assert test_files[0].exists()  # First file still exists
        assert not test_files[1].exists()  # Rolled back
        assert not test_files[2].exists()  # Rolled back
    
    finally:
        for f in test_files:
            f.unlink(missing_ok=True)


def test_rollback_empty_transaction(tracker, rollback_engine):
    """Test rollback fails on empty transaction"""
    tx_id = tracker.start_transaction("empty", "Empty transaction")
    tracker.end_transaction(tx_id, "completed")
    
    with pytest.raises(RollbackError) as exc_info:
        rollback_engine.rollback_transaction(tx_id)
    
    assert "No actions found" in str(exc_info.value)


def test_rollback_updates_transaction_status(tracker, rollback_engine):
    """Test that rollback updates transaction rollback status"""
    test_file = Path(tempfile.gettempdir()) / "status_test.txt"
    test_file.write_text("test")
    
    try:
        tx_id = tracker.start_transaction("test", "test goal")
        tracker.track_action(
            "FileOps",
            "create_file",
            {"path": str(test_file)},
            {},
            tx_id
        )
        tracker.end_transaction(tx_id, "completed")
        
        # Rollback
        rollback_engine.rollback_transaction(tx_id, dry_run=False)
        
        # Check transaction status
        transactions = tracker.get_recent_transactions(limit=1)
        assert transactions[0]["rollback_status"] == "completed"
    
    finally:
        test_file.unlink(missing_ok=True)


def test_rollback_marks_actions_as_rolled_back(tracker, rollback_engine):
    """Test that rolled back actions are marked"""
    test_file = Path(tempfile.gettempdir()) / "mark_test.txt"
    test_file.write_text("test")
    
    try:
        tx_id = tracker.start_transaction("test", "test goal")
        action_id = tracker.track_action(
            "FileOps",
            "create_file",
            {"path": str(test_file)},
            {},
            tx_id
        )
        tracker.end_transaction(tx_id, "completed")
        
        # Rollback
        rollback_engine.rollback_transaction(tx_id, dry_run=False)
        
        # Check action is marked as rolled back
        import sqlite3
        conn = sqlite3.connect(tracker.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT rolled_back FROM actions WHERE id = ?", (action_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result[0] == 1
    
    finally:
        test_file.unlink(missing_ok=True)


def test_rollback_file_move(tracker, rollback_engine):
    """Test rolling back file move operation"""
    # Create source file
    src_file = Path(tempfile.gettempdir()) / "move_src.txt"
    dest_file = Path(tempfile.gettempdir()) / "move_dest.txt"
    
    src_file.write_text("test content")
    
    try:
        # Track move operation
        tx_id = tracker.start_transaction("move file", "Move test file")
        tracker.track_action(
            "FileOps",
            "move_file",
            {"source": str(src_file), "dest": str(dest_file)},
            {"success": True},
            tx_id
        )
        
        # Simulate the move
        src_file.rename(dest_file)
        
        tracker.end_transaction(tx_id, "completed")
        
        # Dest should exist, src should not
        assert dest_file.exists()
        assert not src_file.exists()
        
        # Rollback
        result = rollback_engine.rollback_transaction(tx_id, dry_run=False)
        
        assert result["success"] is True
        assert src_file.exists()  # Moved back
        assert not dest_file.exists()
    
    finally:
        src_file.unlink(missing_ok=True)
        dest_file.unlink(missing_ok=True)


def test_rollback_partial_failure(tracker, rollback_engine):
    """Test rollback with some actions failing"""
    # Create one real file and one fake action
    test_file = Path(tempfile.gettempdir()) / "partial_test.txt"
    test_file.write_text("test")
    
    try:
        tx_id = tracker.start_transaction("test", "test goal")
        
        # Real action
        tracker.track_action(
            "FileOps",
            "create_file",
            {"path": str(test_file)},
            {},
            tx_id
        )
        
        # Action with non-existent file (will fail to rollback)
        tracker.track_action(
            "FileOps",
            "create_file",
            {"path": "/nonexistent/path/file.txt"},
            {},
            tx_id
        )
        
        tracker.end_transaction(tx_id, "completed")
        
        # Rollback - should partially succeed
        result = rollback_engine.rollback_transaction(tx_id, dry_run=False)
        
        # Should have some failures
        assert result["actions_failed"] > 0
        assert len(result["errors"]) > 0
    
    finally:
        test_file.unlink(missing_ok=True)


# ===========================================================================
# rollback_last_n_actions edge cases
# ===========================================================================

def test_rollback_last_n_no_transactions(rollback_engine):
    """rollback_last_n_actions raises when no transactions exist."""
    with pytest.raises(RollbackError, match="No recent transactions"):
        rollback_engine.rollback_last_n_actions(1)


def test_rollback_last_n_fewer_than_requested(tracker, rollback_engine):
    """rollback_last_n_actions clamps n to available action count."""
    test_file = Path(tempfile.gettempdir()) / "clamp_test.txt"
    test_file.write_text("content")
    try:
        tx_id = tracker.start_transaction("t", "g")
        tracker.track_action("FileOps", "create_file", {"path": str(test_file)}, {}, tx_id)
        tracker.end_transaction(tx_id, "completed")
        result = rollback_engine.rollback_last_n_actions(3, dry_run=False)
        assert result["actions_rolled_back"] == 1
    finally:
        test_file.unlink(missing_ok=True)


def test_rollback_last_n_dry_run(tracker, rollback_engine):
    """rollback_last_n_actions dry_run returns plan without executing."""
    test_file = Path(tempfile.gettempdir()) / "lastn_dry.txt"
    test_file.write_text("content")
    try:
        tx_id = tracker.start_transaction("t", "g")
        tracker.track_action("FileOps", "create_file", {"path": str(test_file)}, {}, tx_id)
        tracker.end_transaction(tx_id, "completed")
        result = rollback_engine.rollback_last_n_actions(1, dry_run=True)
        assert result["dry_run"] is True
        assert test_file.exists()
    finally:
        test_file.unlink(missing_ok=True)


def test_rollback_last_n_skips_non_rollbackable(tracker, rollback_engine):
    """rollback_last_n_actions skips non-rollbackable actions."""
    tx_id = tracker.start_transaction("t", "g")
    tracker.track_action("GitOps", "push", {"remote": "origin"}, {}, tx_id)
    tracker.end_transaction(tx_id, "completed")
    result = rollback_engine.rollback_last_n_actions(1, dry_run=False)
    assert result["actions_rolled_back"] == 0


# ===========================================================================
# _execute_rollback strategies
# ===========================================================================

def _make_action(strategy, data=None, rollback_possible=True):
    from zenus_core.memory.action_tracker import Action
    return Action(
        id=99,
        transaction_id="tx_test",
        timestamp="2026-03-18T17:00:00",
        tool="TestTool",
        operation="test_op",
        params={},
        result={},
        rollback_possible=rollback_possible,
        rollback_strategy=strategy,
        rollback_data=data or {},
    )


def test_execute_rollback_delete_file(rollback_engine):
    """delete strategy removes the file."""
    test_file = Path(tempfile.gettempdir()) / "rb_delete.txt"
    test_file.write_text("x")
    action = _make_action("delete", {"path": str(test_file)})
    rollback_engine._execute_rollback(action)
    assert not test_file.exists()


def test_execute_rollback_delete_directory(rollback_engine):
    """delete strategy removes a directory."""
    test_dir = Path(tempfile.gettempdir()) / "rb_delete_dir"
    test_dir.mkdir(exist_ok=True)
    (test_dir / "file.txt").write_text("x")
    action = _make_action("delete", {"path": str(test_dir)})
    rollback_engine._execute_rollback(action)
    assert not test_dir.exists()


def test_execute_rollback_delete_raises_when_missing(rollback_engine):
    """delete strategy raises RollbackError when path doesn't exist."""
    action = _make_action("delete", {"path": "/nonexistent/path/xyz_file.txt"})
    with pytest.raises(RollbackError, match="no longer exists"):
        rollback_engine._execute_rollback(action)


def test_execute_rollback_delete_raises_when_no_path(rollback_engine):
    """delete strategy raises RollbackError when path is not in data."""
    action = _make_action("delete", {})
    with pytest.raises(RollbackError):
        rollback_engine._execute_rollback(action)


def test_execute_rollback_delete_copy(rollback_engine):
    """delete_copy strategy deletes existing file."""
    test_file = Path(tempfile.gettempdir()) / "rb_delete_copy.txt"
    test_file.write_text("x")
    action = _make_action("delete_copy", {"path": str(test_file)})
    rollback_engine._execute_rollback(action)
    assert not test_file.exists()


def test_execute_rollback_delete_copy_missing_is_ok(rollback_engine):
    """delete_copy strategy is a no-op when file is already gone."""
    action = _make_action("delete_copy", {"path": "/tmp/already_gone_xyz_abc.txt"})
    rollback_engine._execute_rollback(action)  # should not raise


def test_execute_rollback_move_back(rollback_engine):
    """move_back strategy moves file to original location."""
    src = Path(tempfile.gettempdir()) / "rb_move_from.txt"
    dst = Path(tempfile.gettempdir()) / "rb_move_to.txt"
    src.write_text("x")
    dst.unlink(missing_ok=True)
    try:
        action = _make_action("move_back", {"from": str(src), "to": str(dst)})
        rollback_engine._execute_rollback(action)
        assert not src.exists()
        assert dst.exists()
    finally:
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)


def test_execute_rollback_restore_raises(rollback_engine):
    """restore strategy raises RollbackError (not implemented)."""
    action = _make_action("restore", {})
    with pytest.raises(RollbackError, match="checkpoint"):
        rollback_engine._execute_rollback(action)


def test_execute_rollback_restore_content_raises(rollback_engine):
    """restore_content strategy raises RollbackError (not implemented)."""
    action = _make_action("restore_content", {})
    with pytest.raises(RollbackError, match="checkpoint"):
        rollback_engine._execute_rollback(action)


def test_execute_rollback_uninstall(rollback_engine):
    """uninstall strategy calls _execute_package_op with 'uninstall'."""
    action = _make_action("uninstall", {"package": "vim"})
    with patch.object(rollback_engine, "_execute_package_op") as mock_pkg:
        rollback_engine._execute_rollback(action)
    mock_pkg.assert_called_once_with("uninstall", "vim")


def test_execute_rollback_reinstall(rollback_engine):
    """reinstall strategy calls _execute_package_op with 'install'."""
    action = _make_action("reinstall", {"package": "vim"})
    with patch.object(rollback_engine, "_execute_package_op") as mock_pkg:
        rollback_engine._execute_rollback(action)
    mock_pkg.assert_called_once_with("install", "vim")


def test_execute_rollback_git_reset(rollback_engine):
    """git_reset strategy calls git reset --hard."""
    action = _make_action("git_reset", {"commit": "abc123"})
    with patch("subprocess.run") as mock_run:
        rollback_engine._execute_rollback(action)
    cmd = mock_run.call_args[0][0]
    assert "git" in cmd and "reset" in cmd


def test_execute_rollback_stop(rollback_engine):
    """stop strategy calls systemctl stop."""
    action = _make_action("stop", {"service": "nginx"})
    with patch("subprocess.run") as mock_run:
        rollback_engine._execute_rollback(action)
    cmd = mock_run.call_args[0][0]
    assert "systemctl" in cmd and "stop" in cmd


def test_execute_rollback_start(rollback_engine):
    """start strategy calls systemctl start."""
    action = _make_action("start", {"service": "nginx"})
    with patch("subprocess.run") as mock_run:
        rollback_engine._execute_rollback(action)
    cmd = mock_run.call_args[0][0]
    assert "systemctl" in cmd and "start" in cmd


def test_execute_rollback_stop_and_remove(rollback_engine):
    """stop_and_remove strategy calls docker stop and docker rm."""
    action = _make_action("stop_and_remove", {"container_id": "abc123"})
    with patch("subprocess.run") as mock_run:
        rollback_engine._execute_rollback(action)
    assert mock_run.call_count == 2


def test_execute_rollback_requires_manual_raises(rollback_engine):
    """requires_manual strategy raises RollbackError."""
    action = _make_action("requires_manual", {})
    with pytest.raises(RollbackError, match="manual"):
        rollback_engine._execute_rollback(action)


def test_execute_rollback_unknown_strategy_raises(rollback_engine):
    """Unknown strategy raises RollbackError."""
    action = _make_action("foobar_strategy", {})
    with pytest.raises(RollbackError, match="Unknown rollback strategy"):
        rollback_engine._execute_rollback(action)


def test_execute_rollback_called_process_error(rollback_engine):
    """CalledProcessError in strategy is re-raised as RollbackError."""
    import subprocess as sp
    action = _make_action("git_reset", {"commit": "abc"})
    with patch("subprocess.run", side_effect=sp.CalledProcessError(1, "git")):
        with pytest.raises(RollbackError, match="Command failed"):
            rollback_engine._execute_rollback(action)


# ===========================================================================
# _execute_package_op
# ===========================================================================

def test_execute_package_op_apt_install(rollback_engine):
    """_execute_package_op installs with apt when apt is available."""
    with patch("shutil.which", side_effect=lambda x: "/usr/bin/apt" if x == "apt" else None):
        with patch("subprocess.run") as mock_run:
            rollback_engine._execute_package_op("install", "vim")
    cmd = mock_run.call_args[0][0]
    assert "apt" in cmd and "install" in cmd


def test_execute_package_op_apt_remove(rollback_engine):
    """_execute_package_op removes with apt."""
    with patch("shutil.which", side_effect=lambda x: "/usr/bin/apt" if x == "apt" else None):
        with patch("subprocess.run") as mock_run:
            rollback_engine._execute_package_op("uninstall", "vim")
    cmd = mock_run.call_args[0][0]
    assert "apt" in cmd and "remove" in cmd


def test_execute_package_op_dnf(rollback_engine):
    """_execute_package_op uses dnf when apt is not found."""
    def which(x):
        return "/usr/bin/dnf" if x == "dnf" else None
    with patch("shutil.which", side_effect=which):
        with patch("subprocess.run") as mock_run:
            rollback_engine._execute_package_op("install", "vim")
    cmd = mock_run.call_args[0][0]
    assert "dnf" in cmd


def test_execute_package_op_pacman(rollback_engine):
    """_execute_package_op uses pacman when neither apt nor dnf found."""
    def which(x):
        return "/usr/bin/pacman" if x == "pacman" else None
    with patch("shutil.which", side_effect=which):
        with patch("subprocess.run") as mock_run:
            rollback_engine._execute_package_op("install", "vim")
    cmd = mock_run.call_args[0][0]
    assert "pacman" in cmd


def test_execute_package_op_no_manager_raises(rollback_engine):
    """_execute_package_op raises RollbackError when no package manager found."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(RollbackError, match="package manager"):
            rollback_engine._execute_package_op("install", "vim")


# ===========================================================================
# restore_checkpoint
# ===========================================================================

def test_restore_checkpoint_not_found(rollback_engine):
    """restore_checkpoint raises RollbackError when checkpoint doesn't exist."""
    with pytest.raises(RollbackError, match="not found"):
        rollback_engine.restore_checkpoint("nonexistent_cp_xyz")


def test_restore_checkpoint_dry_run(tracker, rollback_engine):
    """restore_checkpoint dry_run returns plan without restoring files."""
    conn = sqlite3.connect(tracker.db_path)
    conn.execute(
        "INSERT INTO checkpoints (checkpoint_name, transaction_id, timestamp, description, backup_paths_json) VALUES (?, ?, ?, ?, ?)",
        ("my_checkpoint", "tx_1", "2026-03-18T00:00:00", "test checkpoint", json.dumps({"/original": "/backup"}))
    )
    conn.commit()
    conn.close()

    result = rollback_engine.restore_checkpoint("my_checkpoint", dry_run=True)
    assert result["dry_run"] is True
    assert result["files_count"] == 1


def test_restore_checkpoint_backup_not_found(tracker, rollback_engine, tmp_path):
    """restore_checkpoint reports error when backup file doesn't exist."""
    conn = sqlite3.connect(tracker.db_path)
    conn.execute(
        "INSERT INTO checkpoints (checkpoint_name, transaction_id, timestamp, description, backup_paths_json) VALUES (?, ?, ?, ?, ?)",
        ("cp2", "tx_2", "2026-03-18T00:00:00", "desc", json.dumps({str(tmp_path / "orig.txt"): "/missing_backup_xyz.txt"}))
    )
    conn.commit()
    conn.close()

    result = rollback_engine.restore_checkpoint("cp2", dry_run=False)
    assert result["files_restored"] == 0
    assert len(result["errors"]) == 1


def test_restore_checkpoint_success(tracker, rollback_engine, tmp_path):
    """restore_checkpoint copies backup files to original paths."""
    original = tmp_path / "original.txt"
    backup = tmp_path / "backup.txt"
    backup.write_text("restored content")

    conn = sqlite3.connect(tracker.db_path)
    conn.execute(
        "INSERT INTO checkpoints (checkpoint_name, transaction_id, timestamp, description, backup_paths_json) VALUES (?, ?, ?, ?, ?)",
        ("cp3", "tx_3", "2026-03-18T00:00:00", "desc", json.dumps({str(original): str(backup)}))
    )
    conn.commit()
    conn.close()

    result = rollback_engine.restore_checkpoint("cp3", dry_run=False)
    assert result["success"] is True
    assert result["files_restored"] == 1
    assert original.read_text() == "restored content"


# ===========================================================================
# get_rollback_engine singleton
# ===========================================================================

def test_get_rollback_engine_singleton():
    """get_rollback_engine returns same instance on repeated calls."""
    from zenus_core.rollback import get_rollback_engine
    import zenus_core.rollback as rb_mod
    rb_mod._rollback_engine = None
    a = get_rollback_engine()
    b = get_rollback_engine()
    assert a is b
    rb_mod._rollback_engine = None


# ===========================================================================
# _describe_rollback coverage
# ===========================================================================

def test_describe_rollback_all_strategies(rollback_engine):
    """_describe_rollback returns sensible strings for all known strategies."""
    cases = [
        ("delete", {"path": "/tmp/f.txt"}, "Delete"),
        ("delete_copy", {"path": "/tmp/c.txt"}, "Delete"),
        ("move_back", {"from": "/new", "to": "/old"}, "Move"),
        ("uninstall", {"package": "vim"}, "Uninstall"),
        ("reinstall", {"package": "vim"}, "Reinstall"),
        ("git_reset", {"commit": "abc"}, "Reset"),
        ("stop", {"service": "nginx"}, "Stop"),
        ("start", {"service": "nginx"}, "Start"),
        ("stop_and_remove", {"container_id": "c1"}, "Stop"),
    ]
    for strategy, data, expected in cases:
        action = _make_action(strategy, data)
        desc = rollback_engine._describe_rollback(action)
        assert expected in desc, f"Expected '{expected}' in '{desc}' for {strategy}"


def test_describe_rollback_unknown_strategy(rollback_engine):
    """_describe_rollback returns fallback for unknown strategy."""
    action = _make_action("exotic_strategy", {})
    desc = rollback_engine._describe_rollback(action)
    assert "Rollback" in desc or "TestTool" in desc
