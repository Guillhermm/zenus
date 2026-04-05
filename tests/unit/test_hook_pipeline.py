"""
Unit tests for Hook Pipeline (PreToolUse / PostToolUse).
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hook_entry(match: str, command: str, timeout: int = 5):
    from zenus_core.config.schema import HookEntry
    return HookEntry(match=match, command=command, timeout_seconds=timeout)


def _make_hooks_config(pre=None, post=None):
    from zenus_core.config.schema import HooksConfig
    return HooksConfig(pre_tool_use=pre or [], post_tool_use=post or [])


# ---------------------------------------------------------------------------
# _match helper
# ---------------------------------------------------------------------------

class TestMatch:
    def test_wildcard_matches_anything(self):
        from zenus_core.hooks.pipeline import _match
        assert _match("*", "FileOps", "read_file") is True
        assert _match("*", "ShellOps", "run") is True

    def test_tool_name_matches_any_action(self):
        from zenus_core.hooks.pipeline import _match
        assert _match("FileOps", "FileOps", "read_file") is True
        assert _match("FileOps", "FileOps", "delete_file") is True
        assert _match("FileOps", "ShellOps", "run") is False

    def test_exact_tool_action_match(self):
        from zenus_core.hooks.pipeline import _match
        assert _match("FileOps.delete_file", "FileOps", "delete_file") is True
        assert _match("FileOps.delete_file", "FileOps", "read_file") is False

    def test_fnmatch_wildcard(self):
        from zenus_core.hooks.pipeline import _match
        assert _match("FileOps.*", "FileOps", "read_file") is True
        assert _match("FileOps.*", "ShellOps", "run") is False


# ---------------------------------------------------------------------------
# HookPipeline.execute_pre
# ---------------------------------------------------------------------------

class TestExecutePre:
    def _make_pipeline_with_config(self, hooks_cfg):
        from zenus_core.hooks.pipeline import HookPipeline
        pipeline = HookPipeline()
        pipeline._get_hooks = MagicMock(return_value=hooks_cfg)
        return pipeline

    def test_no_hooks_returns_allowed(self):
        from zenus_core.hooks.pipeline import HookPipeline
        pipeline = HookPipeline()
        pipeline._get_hooks = MagicMock(return_value=None)
        result = pipeline.execute_pre("FileOps", "read_file")
        assert result.allowed is True

    def test_matching_hook_exit_zero_allows(self):
        hooks_cfg = _make_hooks_config(pre=[_make_hook_entry("*", "exit 0")])
        pipeline = self._make_pipeline_with_config(hooks_cfg)
        result = pipeline.execute_pre("FileOps", "read_file")
        assert result.allowed is True
        assert result.exit_code == 0

    def test_matching_hook_exit_nonzero_denies(self):
        hooks_cfg = _make_hooks_config(pre=[_make_hook_entry("*", "exit 1")])
        pipeline = self._make_pipeline_with_config(hooks_cfg)
        result = pipeline.execute_pre("FileOps", "delete_file")
        assert result.allowed is False
        assert result.exit_code == 1

    def test_non_matching_hook_does_not_deny(self):
        hooks_cfg = _make_hooks_config(pre=[_make_hook_entry("ShellOps", "exit 1")])
        pipeline = self._make_pipeline_with_config(hooks_cfg)
        # FileOps does NOT match ShellOps
        result = pipeline.execute_pre("FileOps", "read_file")
        assert result.allowed is True

    def test_first_denying_hook_short_circuits(self):
        """Second hook should not run once first denies."""
        call_log = []

        def _mock_run(cmd, tool, action, result_str, timeout):
            call_log.append(cmd)
            if cmd == "exit 1":
                return 1, "", "denied"
            return 0, "", ""

        hooks_cfg = _make_hooks_config(pre=[
            _make_hook_entry("*", "exit 1"),
            _make_hook_entry("*", "second_hook"),
        ])
        pipeline = self._make_pipeline_with_config(hooks_cfg)

        with patch("zenus_core.hooks.pipeline._run_hook", side_effect=_mock_run):
            result = pipeline.execute_pre("FileOps", "delete_file")

        assert result.allowed is False
        assert len(call_log) == 1  # only first hook ran

    def test_hook_timeout_denies(self):
        hooks_cfg = _make_hooks_config(pre=[_make_hook_entry("*", "sleep 99", timeout=1)])
        pipeline = self._make_pipeline_with_config(hooks_cfg)

        def _timeout_mock(cmd, tool, action, result_str, timeout):
            return 1, "", f"Hook timed out after {timeout}s"

        with patch("zenus_core.hooks.pipeline._run_hook", side_effect=_timeout_mock):
            result = pipeline.execute_pre("FileOps", "write_file")

        assert result.allowed is False


# ---------------------------------------------------------------------------
# HookPipeline.execute_post
# ---------------------------------------------------------------------------

class TestExecutePost:
    def test_post_hooks_run_in_daemon_thread(self):
        """Post hooks must not block and must fire asynchronously."""
        fired = threading.Event()

        def _mock_run(cmd, tool, action, result_str, timeout):
            fired.set()
            return 0, "", ""

        from zenus_core.config.schema import HooksConfig, HookEntry
        hooks_cfg = HooksConfig(post_tool_use=[HookEntry(match="*", command="echo hi")])

        from zenus_core.hooks.pipeline import HookPipeline
        pipeline = HookPipeline()
        pipeline._get_hooks = MagicMock(return_value=hooks_cfg)

        with patch("zenus_core.hooks.pipeline._run_hook", side_effect=_mock_run):
            pipeline.execute_post("FileOps", "read_file", "some result")

        # Allow daemon thread to run
        fired.wait(timeout=2.0)
        assert fired.is_set()

    def test_post_hook_non_matching_not_fired(self):
        call_count = []

        def _mock_run(cmd, tool, action, result_str, timeout):
            call_count.append(1)
            return 0, "", ""

        from zenus_core.config.schema import HooksConfig, HookEntry
        hooks_cfg = HooksConfig(post_tool_use=[HookEntry(match="ShellOps", command="echo hi")])

        from zenus_core.hooks.pipeline import HookPipeline
        pipeline = HookPipeline()
        pipeline._get_hooks = MagicMock(return_value=hooks_cfg)

        with patch("zenus_core.hooks.pipeline._run_hook", side_effect=_mock_run):
            pipeline.execute_post("FileOps", "read_file", "result")

        time.sleep(0.1)
        assert call_count == []


# ---------------------------------------------------------------------------
# list_hooks
# ---------------------------------------------------------------------------

class TestListHooks:
    def test_list_returns_pre_and_post(self):
        from zenus_core.config.schema import HooksConfig, HookEntry
        hooks_cfg = HooksConfig(
            pre_tool_use=[HookEntry(match="FileOps", command="echo pre")],
            post_tool_use=[HookEntry(match="*", command="echo post")],
        )
        from zenus_core.hooks.pipeline import HookPipeline
        pipeline = HookPipeline()
        pipeline._get_hooks = MagicMock(return_value=hooks_cfg)

        result = pipeline.list_hooks()
        assert len(result["pre"]) == 1
        assert result["pre"][0]["match"] == "FileOps"
        assert len(result["post"]) == 1
        assert result["post"][0]["match"] == "*"

    def test_list_empty_when_no_config(self):
        from zenus_core.hooks.pipeline import HookPipeline
        pipeline = HookPipeline()
        pipeline._get_hooks = MagicMock(return_value=None)
        result = pipeline.list_hooks()
        assert result == {"pre": [], "post": []}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_get_hook_pipeline_singleton():
    from zenus_core.hooks.pipeline import get_hook_pipeline, _pipeline_lock
    import zenus_core.hooks.pipeline as pm
    pm._pipeline = None  # reset

    p1 = get_hook_pipeline()
    p2 = get_hook_pipeline()
    assert p1 is p2
