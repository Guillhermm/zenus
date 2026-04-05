"""
Hook Pipeline

Executes configurable shell callbacks before and after every tool action.

PreToolUse hooks that exit non-zero deny the tool call — the action is aborted
and the non-zero exit + stderr are returned as the tool result.

PostToolUse hooks observe the result; their exit code is logged but does not
alter the result already returned to the caller.

Hooks receive three environment variables:
  ZENUS_TOOL    — tool class name (e.g. "FileOps")
  ZENUS_ACTION  — action name     (e.g. "delete_file")
  ZENUS_RESULT  — tool result (PostToolUse only, truncated to 2048 chars)

Match patterns (fnmatch-style):
  "*"                     matches everything
  "ShellOps"              matches any ShellOps action
  "FileOps.delete_file"   matches that specific action only
"""

from __future__ import annotations

import fnmatch
import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from typing import List, Optional

from zenus_core.debug import get_debug_flags
from zenus_core.output.console import console

logger = logging.getLogger(__name__)


@dataclass
class HookResult:
    """Result of running a single hook command."""

    allowed: bool
    """False only for PreToolUse hooks that exited non-zero."""

    exit_code: int
    stdout: str
    stderr: str
    hook_match: str
    """The pattern that triggered this hook."""


def _match(pattern: str, tool: str, action: str) -> bool:
    """Return True if *pattern* matches the *tool*/*action* pair."""
    if pattern == "*":
        return True
    target = f"{tool}.{action}"
    # Try exact "Tool.action" match first, then "Tool" wildcard
    return fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(tool, pattern)


def _run_hook(
    command: str,
    tool: str,
    action: str,
    result: Optional[str],
    timeout: int,
) -> tuple[int, str, str]:
    """Run a single hook shell command and return (exit_code, stdout, stderr)."""
    env = {**os.environ, "ZENUS_TOOL": tool, "ZENUS_ACTION": action}
    if result is not None:
        env["ZENUS_RESULT"] = result[:2048]

    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", f"Hook timed out after {timeout}s"
    except Exception as exc:
        return 1, "", str(exc)


class HookPipeline:
    """
    Manages and executes pre- and post-tool-use hook pipelines.

    Built from the ``hooks`` section of config.yaml; re-reads config on every
    execute_pre / execute_post call so hot-reload works automatically.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _get_hooks(self):
        """Load hooks config (honours hot-reload)."""
        try:
            from zenus_core.config.loader import get_config
            cfg = get_config()
            return cfg.hooks
        except Exception:
            return None

    def execute_pre(self, tool: str, action: str) -> HookResult:
        """
        Run all matching PreToolUse hooks for *tool*.*action*.

        Returns HookResult with allowed=False if any hook exits non-zero.
        The first denying hook short-circuits the rest.
        """
        hooks_cfg = self._get_hooks()
        if hooks_cfg is None or not hooks_cfg.pre_tool_use:
            return HookResult(allowed=True, exit_code=0, stdout="", stderr="", hook_match="")

        dbg = get_debug_flags()

        for entry in hooks_cfg.pre_tool_use:
            if not _match(entry.match, tool, action):
                continue

            if dbg.orchestrator:
                console.print(
                    f"[dim cyan]↳ pre-hook [{entry.match}] → {entry.command}[/dim cyan]"
                )

            exit_code, stdout, stderr = _run_hook(
                entry.command, tool, action, None, entry.timeout_seconds
            )

            logger.debug(
                "PreToolUse hook match=%s exit=%d stdout=%r stderr=%r",
                entry.match, exit_code, stdout, stderr,
            )

            if exit_code != 0:
                return HookResult(
                    allowed=False,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    hook_match=entry.match,
                )

        return HookResult(allowed=True, exit_code=0, stdout="", stderr="", hook_match="")

    def execute_post(self, tool: str, action: str, result: str) -> None:
        """
        Run all matching PostToolUse hooks for *tool*.*action*.

        Runs asynchronously in a daemon thread so the result is not delayed.
        Exit codes are logged but never alter the tool result.
        """
        hooks_cfg = self._get_hooks()
        if hooks_cfg is None or not hooks_cfg.post_tool_use:
            return

        matching = [e for e in hooks_cfg.post_tool_use if _match(e.match, tool, action)]
        if not matching:
            return

        def _run_all() -> None:
            for entry in matching:
                exit_code, stdout, stderr = _run_hook(
                    entry.command, tool, action, result, entry.timeout_seconds
                )
                logger.debug(
                    "PostToolUse hook match=%s exit=%d stdout=%r stderr=%r",
                    entry.match, exit_code, stdout, stderr,
                )
                if exit_code != 0:
                    logger.warning(
                        "PostToolUse hook [%s] exited %d — stderr: %s",
                        entry.match, exit_code, stderr,
                    )

        t = threading.Thread(target=_run_all, daemon=True, name=f"hook-post-{tool}.{action}")
        t.start()

    def list_hooks(self) -> dict:
        """Return a dict with 'pre' and 'post' lists for display."""
        hooks_cfg = self._get_hooks()
        if hooks_cfg is None:
            return {"pre": [], "post": []}
        return {
            "pre": [{"match": e.match, "command": e.command} for e in hooks_cfg.pre_tool_use],
            "post": [{"match": e.match, "command": e.command} for e in hooks_cfg.post_tool_use],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_pipeline: Optional[HookPipeline] = None
_pipeline_lock = threading.Lock()


def get_hook_pipeline() -> HookPipeline:
    """Return the global HookPipeline singleton."""
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            _pipeline = HookPipeline()
    return _pipeline
