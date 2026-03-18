"""
Rollback pipeline integration tests.

Verifies that the RollbackEngine correctly undoes real file-system operations
by combining ActionTracker (isolated SQLite DB) + RollbackEngine.

No LLM required. All operations go through the real ActionTracker and
RollbackEngine so we prove end-to-end rollback correctness, not just mocks.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from zenus_core.memory.action_tracker import ActionTracker
from zenus_core.rollback import RollbackEngine, RollbackError


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tracker(tmp_path):
    """Isolated ActionTracker backed by a temp SQLite DB."""
    return ActionTracker(db_path=str(tmp_path / "test_actions.db"))


@pytest.fixture
def engine(tracker):
    """RollbackEngine wired to the isolated tracker."""
    with patch("zenus_core.rollback.get_action_tracker", return_value=tracker):
        return RollbackEngine()


# ---------------------------------------------------------------------------
# ActionTracker — core data model
# ---------------------------------------------------------------------------

class TestActionTrackerCore:

    def test_start_transaction_returns_id(self, tracker):
        txn_id = tracker.start_transaction("do thing", "test goal")
        assert isinstance(txn_id, str)
        assert len(txn_id) > 0

    def test_end_transaction_updates_status(self, tracker):
        txn_id = tracker.start_transaction("do thing", "goal")
        tracker.end_transaction(txn_id, "completed")
        recent = tracker.get_recent_transactions(limit=1)
        assert recent[0]["status"] == "completed"

    def test_track_action_returns_id(self, tracker):
        txn_id = tracker.start_transaction("create file", "goal")
        action_id = tracker.track_action(
            tool="FileOps",
            operation="create_file",
            params={"path": "/tmp/test.txt"},
            result="created",
            transaction_id=txn_id,
        )
        assert isinstance(action_id, int)

    def test_get_transaction_actions_returns_list(self, tracker):
        txn_id = tracker.start_transaction("scan", "goal")
        tracker.track_action("FileOps", "scan", {"path": "/tmp"},
                              "files", txn_id)
        tracker.end_transaction(txn_id)
        actions = tracker.get_transaction_actions(txn_id)
        assert len(actions) == 1
        assert actions[0].tool == "FileOps"
        assert actions[0].operation == "scan"

    def test_create_file_action_is_rollbackable(self, tracker):
        txn_id = tracker.start_transaction("create", "goal")
        tracker.track_action("FileOps", "create_file",
                              {"path": "/tmp/x.txt"}, "ok", txn_id)
        tracker.end_transaction(txn_id)
        actions = tracker.get_transaction_actions(txn_id)
        assert actions[0].rollback_possible is True
        assert actions[0].rollback_strategy == "delete"

    def test_delete_file_action_is_not_rollbackable(self, tracker):
        txn_id = tracker.start_transaction("delete", "goal")
        tracker.track_action("FileOps", "delete_file",
                              {"path": "/tmp/x.txt"}, "ok", txn_id)
        tracker.end_transaction(txn_id)
        actions = tracker.get_transaction_actions(txn_id)
        assert actions[0].rollback_possible is False

    def test_copy_file_action_is_rollbackable(self, tracker):
        txn_id = tracker.start_transaction("copy", "goal")
        tracker.track_action("FileOps", "copy_file",
                              {"source": "/a.txt", "dest": "/b.txt"}, "ok", txn_id)
        tracker.end_transaction(txn_id)
        actions = tracker.get_transaction_actions(txn_id)
        assert actions[0].rollback_possible is True
        assert actions[0].rollback_strategy == "delete_copy"

    def test_move_file_action_is_rollbackable(self, tracker):
        txn_id = tracker.start_transaction("move", "goal")
        tracker.track_action("FileOps", "move_file",
                              {"source": "/a.txt", "dest": "/b.txt"}, "ok", txn_id)
        tracker.end_transaction(txn_id)
        actions = tracker.get_transaction_actions(txn_id)
        assert actions[0].rollback_possible is True
        assert actions[0].rollback_strategy == "move_back"

    def test_multiple_actions_in_one_transaction(self, tracker):
        txn_id = tracker.start_transaction("multi", "goal")
        for i in range(3):
            tracker.track_action("FileOps", "scan", {"path": str(i)},
                                  f"result{i}", txn_id)
        tracker.end_transaction(txn_id)
        actions = tracker.get_transaction_actions(txn_id)
        assert len(actions) == 3

    def test_unknown_transaction_returns_empty(self, tracker):
        actions = tracker.get_transaction_actions("nonexistent_txn_id")
        assert actions == []


# ---------------------------------------------------------------------------
# RollbackEngine.analyze_feasibility
# ---------------------------------------------------------------------------

class TestAnalyzeFeasibility:

    def test_all_rollbackable_actions_are_feasible(self, tracker, engine):
        txn_id = tracker.start_transaction("create", "goal")
        tracker.track_action("FileOps", "create_file",
                              {"path": "/tmp/foo.txt"}, "ok", txn_id)
        tracker.end_transaction(txn_id)
        actions = tracker.get_transaction_actions(txn_id)

        result = engine.analyze_feasibility(actions)
        assert result["possible"] is True
        assert result["rollbackable_count"] == 1
        assert result["non_rollbackable_count"] == 0

    def test_non_rollbackable_action_marks_infeasible(self, tracker, engine):
        txn_id = tracker.start_transaction("delete", "goal")
        tracker.track_action("FileOps", "delete_file",
                              {"path": "/tmp/x.txt"}, "ok", txn_id)
        tracker.end_transaction(txn_id)
        actions = tracker.get_transaction_actions(txn_id)

        result = engine.analyze_feasibility(actions)
        assert result["possible"] is False
        assert result["non_rollbackable_count"] == 1

    def test_empty_actions_returns_feasible(self, engine):
        result = engine.analyze_feasibility([])
        assert result["possible"] is True
        assert result["rollbackable_count"] == 0


# ---------------------------------------------------------------------------
# RollbackEngine — real file-system rollback
# ---------------------------------------------------------------------------

class TestRollbackRealFilesystem:

    def test_create_file_rollback_removes_file(self, tmp_path, tracker, engine):
        """
        Sequence:
          1. Create a real file on disk.
          2. Track the action as FileOps.create_file.
          3. Call rollback_transaction.
          4. Verify the file is gone.
        """
        target = tmp_path / "to_rollback.txt"
        target.write_text("hello")
        assert target.exists()

        txn_id = tracker.start_transaction("create file", "goal")
        tracker.track_action(
            tool="FileOps",
            operation="create_file",
            params={"path": str(target)},
            result="created",
            transaction_id=txn_id,
        )
        tracker.end_transaction(txn_id)

        result = engine.rollback_transaction(txn_id)

        assert result["success"] is True
        assert result["actions_rolled_back"] == 1
        assert not target.exists(), "File should have been deleted by rollback"

    def test_copy_file_rollback_removes_copy(self, tmp_path, tracker, engine):
        """Rollback of copy_file must delete the destination copy."""
        src = tmp_path / "original.txt"
        dst = tmp_path / "copy.txt"
        src.write_text("content")
        import shutil
        shutil.copy2(str(src), str(dst))
        assert dst.exists()

        txn_id = tracker.start_transaction("copy file", "goal")
        tracker.track_action(
            tool="FileOps",
            operation="copy_file",
            params={"source": str(src), "dest": str(dst)},
            result="copied",
            transaction_id=txn_id,
        )
        tracker.end_transaction(txn_id)

        result = engine.rollback_transaction(txn_id)

        assert result["success"] is True
        assert not dst.exists(), "Copy should have been removed by rollback"
        assert src.exists(), "Source must still exist after rollback"

    def test_move_file_rollback_moves_back(self, tmp_path, tracker, engine):
        """Rollback of move_file must move the file back to its origin."""
        src = tmp_path / "original.txt"
        dst = tmp_path / "moved.txt"
        src.write_text("content")
        src.rename(dst)
        assert dst.exists()
        assert not src.exists()

        txn_id = tracker.start_transaction("move file", "goal")
        tracker.track_action(
            tool="FileOps",
            operation="move_file",
            params={"source": str(src), "dest": str(dst)},
            result="moved",
            transaction_id=txn_id,
        )
        tracker.end_transaction(txn_id)

        result = engine.rollback_transaction(txn_id)

        assert result["success"] is True
        assert src.exists(), "File should have been moved back to source"
        assert not dst.exists()

    def test_multi_step_rollback_reverses_all(self, tmp_path, tracker, engine):
        """Multiple create_file actions must all be undone."""
        files = [tmp_path / f"f{i}.txt" for i in range(3)]
        for f in files:
            f.write_text("data")

        txn_id = tracker.start_transaction("create files", "goal")
        for f in files:
            tracker.track_action("FileOps", "create_file",
                                  {"path": str(f)}, "ok", txn_id)
        tracker.end_transaction(txn_id)

        result = engine.rollback_transaction(txn_id)

        assert result["actions_rolled_back"] == 3
        for f in files:
            assert not f.exists(), f"{f} should have been deleted"

    def test_nonexistent_transaction_raises_rollback_error(self, engine):
        with pytest.raises(RollbackError, match="No actions found"):
            engine.rollback_transaction("nonexistent_id_xyz")

    def test_non_rollbackable_transaction_raises_rollback_error(
        self, tmp_path, tracker, engine
    ):
        """A transaction containing a non-rollbackable action must raise."""
        txn_id = tracker.start_transaction("delete", "goal")
        tracker.track_action("FileOps", "delete_file",
                              {"path": str(tmp_path / "gone.txt")}, "ok", txn_id)
        tracker.end_transaction(txn_id)

        with pytest.raises(RollbackError):
            engine.rollback_transaction(txn_id)


# ---------------------------------------------------------------------------
# RollbackEngine — dry-run mode
# ---------------------------------------------------------------------------

class TestRollbackDryRun:

    def test_dry_run_does_not_delete_file(self, tmp_path, tracker, engine):
        target = tmp_path / "keep_me.txt"
        target.write_text("I must survive")

        txn_id = tracker.start_transaction("create file", "goal")
        tracker.track_action("FileOps", "create_file",
                              {"path": str(target)}, "ok", txn_id)
        tracker.end_transaction(txn_id)

        result = engine.rollback_transaction(txn_id, dry_run=True)

        assert result["dry_run"] is True
        assert target.exists(), "dry_run must NOT modify the filesystem"

    def test_dry_run_returns_success_true(self, tmp_path, tracker, engine):
        target = tmp_path / "dry_target.txt"
        target.write_text("x")

        txn_id = tracker.start_transaction("create", "goal")
        tracker.track_action("FileOps", "create_file",
                              {"path": str(target)}, "ok", txn_id)
        tracker.end_transaction(txn_id)

        result = engine.rollback_transaction(txn_id, dry_run=True)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# RollbackEngine — rollback_last_n_actions
# ---------------------------------------------------------------------------

class TestRollbackLastN:

    def test_rollback_last_1_removes_most_recent_file(
        self, tmp_path, tracker, engine
    ):
        f1 = tmp_path / "first.txt"
        f2 = tmp_path / "second.txt"
        f1.write_text("first")
        f2.write_text("second")

        txn_id = tracker.start_transaction("multi create", "goal")
        tracker.track_action("FileOps", "create_file",
                              {"path": str(f1)}, "ok", txn_id)
        tracker.track_action("FileOps", "create_file",
                              {"path": str(f2)}, "ok", txn_id)
        tracker.end_transaction(txn_id)

        result = engine.rollback_last_n_actions(n=1)

        # Most recent (f2) should be gone; f1 may still be there
        assert not f2.exists()

    def test_no_recent_transactions_raises(self, tracker, engine):
        # Empty DB — no transactions exist
        with pytest.raises(RollbackError, match="No recent transactions"):
            engine.rollback_last_n_actions(n=1)
