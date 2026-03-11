"""
ShellOps — Privileged Shell Meta-Tool

The "execve()" of Zenus. Allows the LLM to run arbitrary shell commands while
keeping every operation inside the IntentIR contract: logged, attributed, and
rollback-aware where possible.

This tool is gated behind the PRIVILEGED tier. It is enabled in interactive
sessions and disabled in restricted/automated contexts.

Actions:
    run   — execute a shell command and return combined stdout/stderr
"""

import os
import re
import subprocess
from typing import Optional

from zenus_core.tools.base import Tool


# Commands that are always blocked, regardless of privilege tier.
# This is a last-resort guard — the LLM should never attempt these.
_HARD_BLOCKED: list[str] = [
    r"rm\s+-rf\s+/",
    r"dd\s+if=",
    r":\(\)\s*\{",          # fork bomb
    r"mkfs\.",
    r">\s*/dev/sd",
]
_BLOCKED_RE = re.compile("|".join(_HARD_BLOCKED))


def _is_blocked(command: str) -> bool:
    return bool(_BLOCKED_RE.search(command))


class ShellOps(Tool):
    """
    Privileged shell meta-tool.

    Executes arbitrary shell commands as IntentIR steps.  Every invocation is
    logged by the planner exactly like any other tool action, making it auditable
    and (where possible) rollback-aware.

    Privilege requirement: PRIVILEGED tier.
    Interactive sessions are privileged by default; automated pipelines are not.
    """

    name = "ShellOps"

    def run(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: int = 120,
        reason: Optional[str] = None,
    ) -> str:
        """
        Execute a shell command.

        Args:
            command:     Shell command string (passed to bash -c).
            working_dir: Directory to run in (default: cwd).
            timeout:     Max seconds before the process is killed (default 120).
            reason:      Human-readable rationale recorded in the audit log.

        Returns:
            Combined stdout + stderr output string.

        Raises:
            PermissionError: If the command matches a hard-blocked pattern.
            RuntimeError:    If the command exits with a non-zero code.
        """
        if _is_blocked(command):
            raise PermissionError(
                f"Command blocked by safety policy: {command!r}"
            )

        cwd = os.path.expanduser(working_dir) if working_dir else None

        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Command timed out after {timeout}s: {command!r}"
            )

        output_parts = []
        if result.stdout.strip():
            output_parts.append(result.stdout.strip())
        if result.stderr.strip():
            output_parts.append(f"[stderr] {result.stderr.strip()}")

        combined = "\n".join(output_parts) if output_parts else "(no output)"

        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed (exit {result.returncode}): {combined}"
            )

        return combined

    def dry_run(self, command: str, working_dir: Optional[str] = None, **_) -> str:
        """Describe what would be executed without running it."""
        blocked = " [BLOCKED by safety policy]" if _is_blocked(command) else ""
        cwd_hint = f" in {working_dir}" if working_dir else ""
        return f"[dry-run] Would run{cwd_hint}: {command!r}{blocked}"
