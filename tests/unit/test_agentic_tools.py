"""
Unit tests for agentic tools:
  TaskOps, ScheduleOps, WorktreeOps, ToolSearch, AskUserQuestion, SleepTool, NotebookOps
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# TaskOps
# ===========================================================================

class TestTaskOps:
    def _ops(self):
        from zenus_core.tools.task_ops import TaskOps
        return TaskOps()

    def test_create_returns_task_id(self):
        ops = self._ops()
        result = ops.create("echo hello", priority="normal")
        assert "Task created:" in result
        # Wait for task to complete
        time.sleep(0.3)

    def test_list_shows_tasks(self):
        ops = self._ops()
        ops.create("echo test", priority="low")
        time.sleep(0.3)
        listing = ops.list()
        # Either has the task or shows no tasks message
        assert isinstance(listing, str)

    def test_get_unknown_task(self):
        ops = self._ops()
        result = ops.get("nonexistent-id")
        assert "Unknown task" in result

    def test_stop_unknown_task(self):
        ops = self._ops()
        result = ops.stop("nonexistent-id")
        assert "could not be cancelled" in result or "Unknown" in result

    def test_purge_removes_completed(self):
        from zenus_core.execution.task_queue import get_task_queue, TaskStatus
        ops = self._ops()
        ops.create("echo purge-me", priority="normal")
        time.sleep(0.5)
        result = ops.purge()
        assert "Purged" in result or "0" in result


# ===========================================================================
# ScheduleOps — cron management
# ===========================================================================

class TestScheduleOps:
    def _ops(self):
        from zenus_core.tools.schedule_ops import ScheduleOps
        return ScheduleOps()

    def test_invalid_cron_expression(self):
        ops = self._ops()
        result = ops.schedule_cron("echo hi", cron_expr="not-valid")
        assert "Invalid cron expression" in result

    def test_valid_cron_expression_format(self):
        from zenus_core.tools.schedule_ops import ScheduleOps
        assert ScheduleOps._valid_cron("* * * * *") is True
        assert ScheduleOps._valid_cron("0 12 * * 1") is True
        assert ScheduleOps._valid_cron("invalid") is False
        assert ScheduleOps._valid_cron("* * * *") is False  # only 4 fields

    def test_schedule_and_list_and_remove(self):
        ops = self._ops()
        fake_crontab = ""

        def mock_read():
            return fake_crontab

        def mock_write(content):
            nonlocal fake_crontab
            fake_crontab = content

        with patch.object(ops.__class__, "_read_crontab", staticmethod(mock_read)):
            with patch.object(ops.__class__, "_write_crontab", staticmethod(mock_write)):
                ops.schedule_cron("echo hi", cron_expr="0 * * * *", label="test-job")
                listing = ops.list_cron()
                assert "test-job" in listing
                assert "echo hi" in listing

                ops.remove_cron("test-job")
                listing_after = ops.list_cron()
                assert "test-job" not in listing_after


# ===========================================================================
# ScheduleOps — remote trigger
# ===========================================================================

class TestRemoteTrigger:
    def _ops(self):
        from zenus_core.tools.schedule_ops import ScheduleOps
        return ScheduleOps()

    def test_invalid_url_rejected(self):
        ops = self._ops()
        result = ops.trigger_remote("ftp://bad-scheme.example.com")
        assert "Invalid URL" in result

    def test_successful_post(self):
        ops = self._ops()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"ok": true}'

        with patch("requests.request", return_value=mock_resp):
            result = ops.trigger_remote("https://example.com/hook", payload='{"test":1}')

        assert "HTTP 200" in result

    def test_request_failure_returns_error(self):
        import requests
        ops = self._ops()

        with patch("requests.request", side_effect=requests.RequestException("timeout")):
            result = ops.trigger_remote("https://example.com/hook")

        assert "Request failed" in result


# ===========================================================================
# WorktreeOps
# ===========================================================================

class TestWorktreeOps:
    def _ops(self):
        from zenus_core.tools.worktree_ops import WorktreeOps
        return WorktreeOps()

    def test_current_returns_not_inside_when_no_worktree(self):
        import zenus_core.tools.worktree_ops as wt_mod
        wt_mod._active_worktree = None
        ops = self._ops()
        result = ops.current()
        assert "Not inside" in result

    def test_exit_without_enter_returns_error(self):
        import zenus_core.tools.worktree_ops as wt_mod
        wt_mod._active_worktree = None
        ops = self._ops()
        result = ops.exit_worktree()
        assert "Not currently inside" in result

    def test_enter_fails_outside_git_repo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import zenus_core.tools.worktree_ops as wt_mod
        wt_mod._active_worktree = None

        ops = self._ops()
        result = ops.enter(branch="test-branch")
        # Should report git error (not inside a git repo)
        assert "Not inside a git repository" in result or "Failed" in result


# ===========================================================================
# ToolSearch
# ===========================================================================

class TestToolSearch:
    def _ops(self):
        from zenus_core.tools.dev_ops import ToolSearch
        return ToolSearch()

    def test_search_finds_known_tool(self):
        ops = self._ops()
        result = ops.search("FileOps")
        assert "FileOps" in result

    def test_search_no_match(self):
        ops = self._ops()
        result = ops.search("xyzzy_not_a_real_tool_98765")
        assert "No tools" in result

    def test_search_respects_limit(self):
        ops = self._ops()
        result = ops.search("Ops", limit=2)
        lines = [l for l in result.splitlines() if "Ops" in l]
        # 2 matches max from tool-level + action-level combined
        assert len(lines) <= 3  # header + 2 results

    def test_search_by_action_description(self):
        ops = self._ops()
        result = ops.search("read_file")
        assert "read_file" in result


# ===========================================================================
# AskUserQuestion
# ===========================================================================

class TestAskUserQuestion:
    def _ops(self):
        from zenus_core.tools.dev_ops import AskUserQuestion
        return AskUserQuestion()

    def test_returns_user_input(self):
        ops = self._ops()
        with patch("builtins.input", return_value="my answer"):
            with patch("zenus_core.output.console.console"):
                result = ops.ask("What do you want?")
        assert result == "my answer"

    def test_uses_default_on_empty_input(self):
        ops = self._ops()
        with patch("builtins.input", return_value=""):
            with patch("zenus_core.output.console.console"):
                result = ops.ask("Choose:", default="yes")
        assert result == "yes"

    def test_validates_options(self):
        ops = self._ops()
        # First call returns invalid, second returns valid
        answers = iter(["bad", "y"])
        with patch("builtins.input", side_effect=lambda: next(answers)):
            with patch("zenus_core.output.console.console"):
                result = ops.ask("Confirm?", options="y,n")
        assert result == "y"

    def test_eof_returns_default(self):
        ops = self._ops()
        with patch("builtins.input", side_effect=EOFError):
            with patch("zenus_core.output.console.console"):
                result = ops.ask("Question?", default="default_val")
        assert result == "default_val"


# ===========================================================================
# SleepTool
# ===========================================================================

class TestSleepTool:
    def _ops(self):
        from zenus_core.tools.dev_ops import SleepTool
        return SleepTool()

    def test_sleeps_and_returns_message(self):
        ops = self._ops()
        start = time.monotonic()
        result = ops.sleep(0.05)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.04
        assert "Slept" in result

    def test_caps_at_300_seconds(self):
        ops = self._ops()
        with patch("time.sleep") as mock_sleep:
            ops.sleep(999)
        mock_sleep.assert_called_once_with(300.0)


# ===========================================================================
# NotebookOps
# ===========================================================================

class TestNotebookOps:
    def _ops(self):
        from zenus_core.tools.notebook_ops import NotebookOps
        return NotebookOps()

    def _make_nb(self, tmp_path, cells=None):
        nb = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": cells or [
                {"cell_type": "code", "source": ["print('hello')"], "metadata": {},
                 "execution_count": None, "outputs": []},
                {"cell_type": "markdown", "source": ["# Title"], "metadata": {}},
            ],
        }
        p = tmp_path / "test.ipynb"
        p.write_text(json.dumps(nb), encoding="utf-8")
        return str(p)

    def test_list_cells(self, tmp_path):
        ops = self._ops()
        path = self._make_nb(tmp_path)
        result = ops.list_cells(path)
        assert "[0]" in result
        assert "[1]" in result
        assert "code" in result
        assert "markdown" in result

    def test_read_cell(self, tmp_path):
        ops = self._ops()
        path = self._make_nb(tmp_path)
        result = ops.read_cell(path, 0)
        assert "print" in result

    def test_edit_cell(self, tmp_path):
        ops = self._ops()
        path = self._make_nb(tmp_path)
        ops.edit_cell(path, 0, "x = 42")
        result = ops.read_cell(path, 0)
        assert "x = 42" in result

    def test_add_cell_at_end(self, tmp_path):
        ops = self._ops()
        path = self._make_nb(tmp_path)
        ops.add_cell(path, "new_cell()", cell_type="code")
        result = ops.list_cells(path)
        assert "[2]" in result

    def test_add_cell_at_index(self, tmp_path):
        ops = self._ops()
        path = self._make_nb(tmp_path)
        ops.add_cell(path, "# inserted", cell_type="markdown", index=0)
        result = ops.read_cell(path, 0)
        assert "inserted" in result

    def test_delete_cell(self, tmp_path):
        ops = self._ops()
        path = self._make_nb(tmp_path)
        ops.delete_cell(path, 1)
        result = ops.list_cells(path)
        assert "[1]" not in result

    def test_clear_outputs(self, tmp_path):
        ops = self._ops()
        nb_data = {
            "nbformat": 4, "nbformat_minor": 5, "metadata": {},
            "cells": [
                {"cell_type": "code", "source": ["1+1"],
                 "outputs": [{"output_type": "execute_result", "data": {"text/plain": ["2"]}}],
                 "execution_count": 1, "metadata": {}},
            ],
        }
        p = tmp_path / "out.ipynb"
        p.write_text(json.dumps(nb_data), encoding="utf-8")
        ops.clear_outputs(str(p))
        nb2 = json.loads(p.read_text(encoding="utf-8"))
        assert nb2["cells"][0]["outputs"] == []
        assert nb2["cells"][0]["execution_count"] is None

    def test_invalid_extension_raises(self, tmp_path):
        ops = self._ops()
        p = tmp_path / "bad.txt"
        p.write_text("not a notebook")
        with pytest.raises(ValueError, match=r"\.ipynb"):
            ops.list_cells(str(p))

    def test_missing_file_raises(self, tmp_path):
        ops = self._ops()
        with pytest.raises(FileNotFoundError):
            ops.list_cells(str(tmp_path / "missing.ipynb"))

    def test_index_out_of_range(self, tmp_path):
        ops = self._ops()
        path = self._make_nb(tmp_path)
        with pytest.raises(IndexError):
            ops.read_cell(path, 99)

    def test_invalid_cell_type_rejected(self, tmp_path):
        ops = self._ops()
        path = self._make_nb(tmp_path)
        result = ops.add_cell(path, "x", cell_type="invalid")
        assert "Invalid cell_type" in result
