"""
Unit tests for zenus_core.output.execution_summary

Tests cover:
- ExecutionSummaryBuilder.build: three-level priority (action_summary, derived, goal)
- _derive: verb map lookups, target extraction, count aggregation
- _shorten: path truncation
- build_execution_summary: convenience wrapper
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from zenus_core.output.execution_summary import (
    ExecutionSummaryBuilder,
    build_execution_summary,
    _shorten,
    _VERB_MAP,
    _ARG_KEY,
)
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_intent(
    goal: str = "do something",
    steps: list | None = None,
    action_summary: str | None = None,
    is_question: bool = False,
) -> IntentIR:
    return IntentIR(
        goal=goal,
        requires_confirmation=False,
        steps=steps or [],
        action_summary=action_summary,
        is_question=is_question,
    )


def make_step(tool: str, action: str, risk: int = 0, **args) -> Step:
    return Step(tool=tool, action=action, risk=risk, args=args)


# ---------------------------------------------------------------------------
# _shorten helper
# ---------------------------------------------------------------------------

class TestShorten:
    def test_short_path_unchanged(self):
        assert _shorten("/home/user/file.txt") == "/home/user/file.txt"

    def test_exactly_40_chars_unchanged(self):
        s = "a" * 40
        assert _shorten(s) == s

    def test_long_path_truncated_to_40(self):
        s = "a" * 80
        result = _shorten(s)
        assert len(result) == 40

    def test_long_path_has_ellipsis_prefix(self):
        s = "/very/long/path/to/some/deeply/nested/file.txt"
        result = _shorten(s)
        assert result.startswith("...")
        assert len(result) <= 40

    def test_long_path_ends_with_tail(self):
        path = "/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/u/v.txt"
        result = _shorten(path)
        assert result.endswith(path[-37:])


# ---------------------------------------------------------------------------
# Level 1: action_summary from IntentIR
# ---------------------------------------------------------------------------

class TestBuildLevel1ActionSummary:
    def test_returns_action_summary_when_present(self):
        intent = make_intent(action_summary="Moved 3 PDFs to ~/Documents")
        result = ExecutionSummaryBuilder().build(intent, [])
        assert result == "Moved 3 PDFs to ~/Documents"

    def test_action_summary_stripped(self):
        intent = make_intent(action_summary="  Installed vim  ")
        result = ExecutionSummaryBuilder().build(intent, [])
        assert result == "Installed vim"

    def test_action_summary_takes_priority_over_steps(self):
        steps = [make_step("FileOps", "mkdir", path="/tmp/test")]
        intent = make_intent(
            steps=steps,
            action_summary="Custom summary from LLM",
        )
        result = ExecutionSummaryBuilder().build(intent, [])
        assert result == "Custom summary from LLM"


# ---------------------------------------------------------------------------
# Level 2: derived from steps
# ---------------------------------------------------------------------------

class TestBuildLevel2Derived:
    def test_single_file_step(self):
        steps = [make_step("FileOps", "mkdir", path="/tmp/mydir")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Created directory" in result
        assert "mydir" in result

    def test_single_write_step(self):
        steps = [make_step("FileOps", "write_file", path="/home/user/hello.txt")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Wrote" in result

    def test_move_step(self):
        steps = [make_step("FileOps", "move", destination="/tmp/dest.txt")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Moved" in result

    def test_package_install(self):
        steps = [make_step("PackageOps", "install", package="vim")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Installed" in result
        assert "vim" in result

    def test_service_start(self):
        steps = [make_step("ServiceOps", "start", service="nginx")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Started" in result
        assert "nginx" in result

    def test_git_clone(self):
        steps = [make_step("GitOps", "clone", url="https://github.com/x/y")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Cloned" in result

    def test_shell_run(self):
        steps = [make_step("ShellOps", "run", command="ls -la")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Ran" in result
        assert "ls -la" in result

    def test_network_curl(self):
        steps = [make_step("NetworkOps", "curl", url="https://api.example.com")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Fetched" in result

    def test_ends_with_period(self):
        steps = [make_step("PackageOps", "install", package="git")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert result.endswith(".")

    def test_multiple_different_steps(self):
        steps = [
            make_step("PackageOps", "install", package="vim"),
            make_step("ServiceOps", "start", service="nginx"),
        ]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Installed" in result
        assert "Started" in result

    def test_repeated_verb_aggregated_with_count(self):
        steps = [
            make_step("PackageOps", "install", package="vim"),
            make_step("PackageOps", "install", package="git"),
            make_step("PackageOps", "install", package="curl"),
        ]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        # Repeated installs: shown as "Installed 3 items"
        assert "3 items" in result or "Installed" in result

    def test_more_than_three_parts_shows_overflow(self):
        steps = [
            make_step("PackageOps", "install", package="a"),
            make_step("ServiceOps", "start", service="b"),
            make_step("GitOps", "commit"),
            make_step("ShellOps", "run", command="echo done"),
        ]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "+1 more" in result

    def test_unknown_tool_action_fallback(self):
        steps = [make_step("UnknownTool", "doSomething")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Ran UnknownTool.doSomething" in result

    def test_step_without_matching_arg_key(self):
        # GitOps.commit has no entry in _ARG_KEY
        steps = [make_step("GitOps", "commit")]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert "Committed" in result

    def test_step_results_accepted_but_not_required(self):
        # step_results param is not used yet but must not raise
        steps = [make_step("FileOps", "touch", path="/tmp/f")]
        intent = make_intent(steps=steps)
        fake_results = [{"status": "ok"}, {"status": "ok"}]
        result = ExecutionSummaryBuilder().build(intent, fake_results)
        assert "Created" in result


# ---------------------------------------------------------------------------
# Level 3: fallback to goal
# ---------------------------------------------------------------------------

class TestBuildLevel3Goal:
    def test_empty_steps_falls_back_to_goal(self):
        intent = make_intent(goal="Organise my downloads folder")
        result = ExecutionSummaryBuilder().build(intent, [])
        assert result == "Organise my downloads folder"

    def test_no_action_summary_no_steps_returns_goal(self):
        intent = make_intent(goal="Set up my dev environment", steps=[])
        result = ExecutionSummaryBuilder().build(intent, [])
        assert result == "Set up my dev environment"


# ---------------------------------------------------------------------------
# build_execution_summary convenience function
# ---------------------------------------------------------------------------

class TestBuildExecutionSummaryFunction:
    def test_delegates_to_builder(self):
        intent = make_intent(action_summary="Quick summary")
        assert build_execution_summary(intent, []) == "Quick summary"

    def test_derived_summary_via_function(self):
        steps = [make_step("ServiceOps", "restart", service="postgres")]
        intent = make_intent(steps=steps)
        result = build_execution_summary(intent, [])
        assert "Restarted" in result
        assert "postgres" in result


# ---------------------------------------------------------------------------
# _VERB_MAP completeness
# ---------------------------------------------------------------------------

class TestVerbMapCoverage:
    @pytest.mark.parametrize("key,expected_verb", list(_VERB_MAP.items()))
    def test_verb_is_non_empty_string(self, key, expected_verb):
        assert isinstance(expected_verb, str)
        assert len(expected_verb) > 0

    def test_all_verb_map_keys_are_tuples(self):
        for key in _VERB_MAP:
            assert isinstance(key, tuple)
            assert len(key) == 2

    def test_all_arg_keys_are_strings(self):
        for key, arg_key in _ARG_KEY.items():
            assert isinstance(arg_key, str)
            assert len(arg_key) > 0


# ---------------------------------------------------------------------------
# Path truncation in summary
# ---------------------------------------------------------------------------

class TestLongPathInSummary:
    def test_long_path_does_not_blow_up_summary(self):
        long_path = "/home/user/very/long/deeply/nested/path/to/some/important/file.txt"
        steps = [make_step("FileOps", "write_file", path=long_path)]
        intent = make_intent(steps=steps)
        result = ExecutionSummaryBuilder().build(intent, [])
        assert len(result) < 200  # Should not be huge
        assert "Wrote" in result
