"""
CodeExec — Sandboxed Code Execution Tool

Lets the LLM write and run small Python or Bash scripts as IntentIR steps.
Code runs in a subprocess (isolated from the Zenus process) so side-effects
are contained.  stdout/stderr are captured and returned as the step result,
which feeds back into the ReAct observation loop.

Actions:
    python      — execute a Python snippet
    bash_script — execute a multi-line Bash script
"""

import os
import sys
import subprocess
import tempfile
from typing import Optional

from zenus_core.tools.base import Tool

# Max output size returned to the LLM (truncated beyond this)
_MAX_OUTPUT_CHARS = 8_000


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    half = _MAX_OUTPUT_CHARS // 2
    return text[:half] + f"\n... [truncated {len(text) - _MAX_OUTPUT_CHARS} chars] ...\n" + text[-half:]


class CodeExec(Tool):
    """
    Sandboxed code execution.

    Python snippets run in a fresh subprocess using the same interpreter as
    Zenus itself (sys.executable).  Bash scripts run via bash.

    Both actions accept an optional `reason` argument for audit purposes.
    """

    name = "CodeExec"

    def python(
        self,
        code: str,
        timeout: int = 30,
        working_dir: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> str:
        """
        Execute a Python snippet and return its output.

        Args:
            code:        Python source code to execute.
            timeout:     Max seconds (default 30).
            working_dir: Working directory for the subprocess.
            reason:      Rationale recorded in the audit log.

        Returns:
            Combined stdout + stderr, truncated to 8 000 chars.

        Raises:
            RuntimeError: If the snippet exits with a non-zero code.
        """
        cwd = os.path.expanduser(working_dir) if working_dir else None

        fd = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd[0], "w", encoding="utf-8") as f:
                f.write(code)
            script_path = fd[1]
        except Exception:
            os.unlink(fd[1])
            raise

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Python snippet timed out after {timeout}s")
        finally:
            os.unlink(script_path)

        return self._format_result(result)

    def bash_script(
        self,
        code: str,
        timeout: int = 60,
        working_dir: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> str:
        """
        Execute a multi-line Bash script and return its output.

        Args:
            code:        Bash script source.
            timeout:     Max seconds (default 60).
            working_dir: Working directory.
            reason:      Rationale recorded in the audit log.

        Returns:
            Combined stdout + stderr, truncated to 8 000 chars.

        Raises:
            RuntimeError: If the script exits with a non-zero code.
        """
        cwd = os.path.expanduser(working_dir) if working_dir else None

        fd = tempfile.mkstemp(suffix=".sh")
        try:
            with os.fdopen(fd[0], "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env bash\nset -euo pipefail\n")
                f.write(code)
            script_path = fd[1]
        except Exception:
            os.unlink(fd[1])
            raise

        os.chmod(script_path, 0o700)

        try:
            result = subprocess.run(
                ["bash", script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Bash script timed out after {timeout}s")
        finally:
            os.unlink(script_path)

        return self._format_result(result)

    def dry_run(self, code: str = "", **_) -> str:
        """Show the code that would be executed without running it."""
        preview = code[:200] + ("..." if len(code) > 200 else "")
        return f"[dry-run] Would execute:\n{preview}"

    # ------------------------------------------------------------------ #

    def _format_result(self, result: subprocess.CompletedProcess) -> str:
        parts = []
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"[stderr] {result.stderr.strip()}")

        combined = "\n".join(parts) if parts else "(no output)"
        combined = _truncate(combined)

        if result.returncode != 0:
            raise RuntimeError(
                f"Script failed (exit {result.returncode}):\n{combined}"
            )

        return combined
