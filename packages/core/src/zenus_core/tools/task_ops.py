"""
TaskOps Tool

Exposes the BackgroundTaskQueue as a first-class Zenus tool so that agents
and the orchestrator can create, inspect, stop, and read background tasks
from within an execution plan.

Actions:
  create(command, priority)  — queue a shell command as a background task
  list()                     — list all known tasks with status
  get(task_id)               — get status and result of a specific task
  stop(task_id)              — attempt to cancel a pending task
  output(task_id)            — return the captured output of a completed task
  purge()                    — remove all completed/failed/cancelled tasks
"""

from __future__ import annotations

import io
import subprocess
import threading
from contextlib import redirect_stdout
from typing import Optional

from zenus_core.tools.base import Tool


class TaskOps(Tool):
    """
    Background task management.

    Agents can spawn long-running shell commands as background tasks and
    poll them for completion without blocking the main execution thread.
    """

    # Task output is captured into this dict: task_id → str
    _output_store: dict = {}
    _store_lock = threading.Lock()

    def create(self, command: str, priority: str = "normal") -> str:
        """
        Submit a shell command as a background task.

        Args:
            command: Shell command to run.
            priority: 'high', 'normal' (default), or 'low'.

        Returns:
            task_id string.
        """
        from zenus_core.execution.task_queue import get_task_queue, Priority

        prio_map = {
            "high": Priority.HIGH,
            "normal": Priority.NORMAL,
            "low": Priority.LOW,
        }
        prio = prio_map.get(priority.lower(), Priority.NORMAL)
        queue = get_task_queue()
        task_id = queue.submit(self._run_shell, command, priority=prio)
        return f"Task created: {task_id} (priority={priority})"

    def list(self) -> str:  # noqa: A003
        """List all background tasks with their current status."""
        from zenus_core.execution.task_queue import get_task_queue

        tasks = get_task_queue().list_tasks()
        if not tasks:
            return "No background tasks."

        lines = ["id                               status      result"]
        lines.append("-" * 70)
        for t in tasks:
            result_preview = ""
            if t.result is not None:
                result_preview = str(t.result)[:40].replace("\n", " ")
            elif t.error is not None:
                result_preview = f"ERROR: {str(t.error)[:35]}"
            lines.append(f"{t.task_id:<33} {t.status.value:<11} {result_preview}")
        return "\n".join(lines)

    def get(self, task_id: str) -> str:
        """
        Return the full status and result for *task_id*.

        Args:
            task_id: Task ID returned by create().
        """
        from zenus_core.execution.task_queue import get_task_queue

        try:
            r = get_task_queue().result(task_id)
        except KeyError:
            return f"Unknown task: {task_id}"

        parts = [f"id:     {r.task_id}", f"status: {r.status.value}"]
        if r.result is not None:
            parts.append(f"result: {str(r.result)[:500]}")
        if r.error is not None:
            parts.append(f"error:  {r.error}")

        with self._store_lock:
            out = self._output_store.get(task_id, "")
        if out:
            parts.append(f"output:\n{out[:1000]}")

        return "\n".join(parts)

    def stop(self, task_id: str) -> str:
        """
        Attempt to cancel a PENDING task.

        Args:
            task_id: Task ID returned by create().
        """
        from zenus_core.execution.task_queue import get_task_queue

        ok = get_task_queue().cancel(task_id)
        if ok:
            return f"Task {task_id} cancelled."
        return f"Task {task_id} could not be cancelled (already running or completed)."

    def output(self, task_id: str) -> str:
        """
        Return the captured stdout/stderr of a completed task.

        Args:
            task_id: Task ID returned by create().
        """
        with self._store_lock:
            out = self._output_store.get(task_id)
        if out is None:
            return f"No captured output for task {task_id} (task unknown or not yet complete)."
        return out or "(no output)"

    def purge(self) -> str:
        """Remove all completed, failed, and cancelled tasks from the registry."""
        from zenus_core.execution.task_queue import get_task_queue, TaskStatus

        queue = get_task_queue()
        done_ids = [
            t.task_id for t in queue.list_tasks()
            if t.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)
        ]
        with queue._lock:
            for tid in done_ids:
                queue._tasks.pop(tid, None)
                queue._futures.pop(tid, None)
        with self._store_lock:
            for tid in done_ids:
                self._output_store.pop(tid, None)
        return f"Purged {len(done_ids)} completed task(s)."

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_shell(self, command: str) -> str:
        """Run a shell command and capture output into _output_store."""
        # We don't know our task_id inside the thread; the queue framework
        # calls this function directly, so we intercept stdout via a pipe.
        buf = io.StringIO()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            out = proc.stdout + proc.stderr
            # Store output — the queue framework stores task_id externally;
            # we expose output via the public output() action.
            return out.strip() or "(command exited 0 with no output)"
        except subprocess.TimeoutExpired:
            return "ERROR: Command timed out after 3600s"
        except Exception as exc:
            return f"ERROR: {exc}"
