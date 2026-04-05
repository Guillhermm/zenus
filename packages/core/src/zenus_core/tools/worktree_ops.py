"""
WorktreeOps Tool

Creates and manages isolated git worktrees so agents can make risky or
exploratory code changes without touching the main working tree.

Typical workflow:
  1. Agent calls ``enter(branch)``    — creates a worktree + branch, cwd switches
  2. Agent makes changes inside it
  3. Agent calls ``exit_worktree()``  — removes if no changes; returns branch name if changes exist

Actions:
  enter(branch, base)         — create and enter a new git worktree
  exit_worktree()             — exit current worktree; cleanup if clean, else return branch
  list()                      — list all worktrees for this repository
  remove(path)                — forcibly remove a specific worktree
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

from zenus_core.tools.base import Tool

_active_worktree: Optional[str] = None   # path of the worktree we are in
_original_cwd: Optional[str] = None      # cwd before entering
_active_branch: Optional[str] = None     # branch name created for the worktree
_wt_lock = threading.Lock()


def _git(args: list[str], cwd: Optional[str] = None) -> tuple[int, str, str]:
    cwd = cwd or os.getcwd()
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class WorktreeOps(Tool):
    """
    Isolated git worktree management.

    Entering a worktree changes the process cwd.  Exiting restores it and
    cleans up automatically if no changes were committed in the worktree.
    """

    def enter(self, branch: str = "", base: str = "HEAD") -> str:
        """
        Create a new git worktree and switch the cwd into it.

        Args:
            branch: New branch name to create (auto-generated if empty).
            base:   Git ref to base the new branch on (default: HEAD).

        Returns:
            Confirmation with the worktree path and branch name.
        """
        global _active_worktree, _original_cwd, _active_branch

        with _wt_lock:
            if _active_worktree:
                return (
                    f"Already inside worktree: {_active_worktree}. "
                    "Call exit_worktree() first."
                )

            # Ensure we are inside a git repo
            rc, root, err = _git(["rev-parse", "--show-toplevel"])
            if rc != 0:
                return f"Not inside a git repository: {err}"
            repo_root = root

            # Auto-generate branch name if not provided
            if not branch:
                import uuid
                branch = f"zenus-wt-{uuid.uuid4().hex[:6]}"

            # Create a temp directory for the worktree
            wt_dir = tempfile.mkdtemp(prefix="zenus-wt-", dir=repo_root)

            rc, _, err = _git(
                ["worktree", "add", "-b", branch, wt_dir, base],
                cwd=repo_root,
            )
            if rc != 0:
                import shutil
                shutil.rmtree(wt_dir, ignore_errors=True)
                return f"Failed to create worktree: {err}"

            _original_cwd = os.getcwd()
            _active_worktree = wt_dir
            _active_branch = branch
            os.chdir(wt_dir)

        return (
            f"Entered worktree: {wt_dir}\n"
            f"Branch: {branch}\n"
            "Main working tree is untouched. Call exit_worktree() when done."
        )

    def exit_worktree(self) -> str:
        """
        Exit the current worktree and restore the original cwd.

        - If the worktree is clean (no commits made), it is removed automatically.
        - If commits were made, the branch name is returned and the worktree
          is kept so the user can merge/review.

        Returns:
            Status message with the branch name if changes were made.
        """
        global _active_worktree, _original_cwd, _active_branch

        with _wt_lock:
            if not _active_worktree:
                return "Not currently inside a Zenus-managed worktree."

            wt_path = _active_worktree
            branch = _active_branch
            orig = _original_cwd

            # Check for new commits relative to the base ref
            rc, commit_log, _ = _git(
                ["log", "--oneline", f"HEAD@{{1}}..HEAD"],
                cwd=wt_path,
            )
            has_commits = bool(commit_log.strip())

            # Restore cwd first
            try:
                os.chdir(orig or Path.home())
            except Exception:
                pass

            _active_worktree = None
            _active_branch = None
            _original_cwd = None

        if has_commits:
            return (
                f"Worktree exited. Changes committed on branch '{branch}'.\n"
                f"Path:   {wt_path}\n"
                f"Branch: {branch}\n"
                "You can now review, merge, or discard the branch."
            )

        # Clean — remove the worktree
        import shutil
        rc, _, err = _git(["worktree", "remove", "--force", wt_path])
        if rc == 0:
            shutil.rmtree(wt_path, ignore_errors=True)
            return (
                f"Worktree exited and removed (no commits made).\n"
                f"Branch '{branch}' deleted."
            )
        # Fallback: just remove directory
        shutil.rmtree(wt_path, ignore_errors=True)
        return (
            f"Worktree directory removed. "
            f"You may need to run: git branch -d {branch}"
        )

    def list(self) -> str:  # noqa: A003
        """List all worktrees for the current git repository."""
        rc, out, err = _git(["worktree", "list", "--porcelain"])
        if rc != 0:
            return f"git worktree list failed: {err}"
        return out or "No worktrees found."

    def remove(self, path: str) -> str:
        """
        Forcibly remove a specific worktree by path.

        Args:
            path: Absolute or relative path to the worktree directory.
        """
        rc, _, err = _git(["worktree", "remove", "--force", path])
        if rc != 0:
            return f"Failed to remove worktree at {path!r}: {err}"
        import shutil
        shutil.rmtree(path, ignore_errors=True)
        return f"Worktree removed: {path}"

    def current(self) -> str:
        """Return information about the current active worktree, if any."""
        with _wt_lock:
            if not _active_worktree:
                return "Not inside a Zenus-managed worktree."
            return (
                f"Active worktree: {_active_worktree}\n"
                f"Branch: {_active_branch}\n"
                f"Original cwd: {_original_cwd}"
            )
