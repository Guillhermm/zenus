"""
Execution Summary Builder

Produces a concise, human-readable summary of what Zenus did after executing
a plan — similar to how Cursor or Claude Code shows "Created 3 files, ran 2
commands" rather than a static "plan executed successfully" message.

The summary is built from the step results recorded in the action tracker,
without making an extra LLM call.  If the LLM already provided an
`action_summary` field in the IntentIR, that is used as-is.

Priority:
  1. intent.action_summary  (LLM-provided, already human-readable)
  2. Built from step results (cheaply derived, no LLM call)
  3. Fallback to intent.goal
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Verb mappings: (tool, action) → past-tense fragment
# ---------------------------------------------------------------------------

_VERB_MAP: Dict[tuple, str] = {
    ("FileOps",    "scan"):        "Scanned",
    ("FileOps",    "mkdir"):       "Created directory",
    ("FileOps",    "move"):        "Moved",
    ("FileOps",    "write_file"):  "Wrote",
    ("FileOps",    "touch"):       "Created",
    ("TextOps",    "read"):        "Read",
    ("TextOps",    "write"):       "Wrote",
    ("TextOps",    "append"):      "Appended to",
    ("TextOps",    "search"):      "Searched",
    ("PackageOps", "install"):     "Installed",
    ("PackageOps", "remove"):      "Removed",
    ("PackageOps", "update"):      "Updated",
    ("ServiceOps", "start"):       "Started",
    ("ServiceOps", "stop"):        "Stopped",
    ("ServiceOps", "restart"):     "Restarted",
    ("GitOps",     "clone"):       "Cloned",
    ("GitOps",     "commit"):      "Committed",
    ("GitOps",     "push"):        "Pushed",
    ("GitOps",     "pull"):        "Pulled",
    ("ProcessOps", "kill"):        "Killed process",
    ("ShellOps",   "run"):         "Ran",
    ("CodeExec",   "python"):      "Executed Python code",
    ("CodeExec",   "bash_script"): "Ran script",
    ("SystemOps",  "disk_usage"):  "Checked disk usage",
    ("SystemOps",  "cpu_info"):    "Checked CPU info",
    ("SystemOps",  "memory_info"): "Checked memory",
    ("NetworkOps", "curl"):        "Fetched",
    ("NetworkOps", "ping"):        "Pinged",
    ("ContainerOps","run"):        "Started container",
    ("ContainerOps","stop"):       "Stopped container",
    ("BrowserOps", "open"):        "Opened",
    ("BrowserOps", "screenshot"):  "Took screenshot",
    ("BrowserOps", "search"):      "Searched",
}

# Primary argument key per (tool, action) — used to name the target
_ARG_KEY: Dict[tuple, str] = {
    ("FileOps",    "scan"):        "path",
    ("FileOps",    "mkdir"):       "path",
    ("FileOps",    "move"):        "destination",
    ("FileOps",    "write_file"):  "path",
    ("FileOps",    "touch"):       "path",
    ("TextOps",    "read"):        "path",
    ("TextOps",    "write"):       "path",
    ("TextOps",    "append"):      "path",
    ("PackageOps", "install"):     "package",
    ("PackageOps", "remove"):      "package",
    ("ServiceOps", "start"):       "service",
    ("ServiceOps", "stop"):        "service",
    ("ServiceOps", "restart"):     "service",
    ("GitOps",     "clone"):       "url",
    ("ProcessOps", "kill"):        "name",
    ("ShellOps",   "run"):         "command",
    ("NetworkOps", "curl"):        "url",
    ("NetworkOps", "ping"):        "host",
    ("BrowserOps", "open"):        "url",
}


class ExecutionSummaryBuilder:
    """
    Builds a ≤2-sentence summary of what was done from step + result data.

    Usage::

        builder = ExecutionSummaryBuilder()
        text = builder.build(intent, step_results)
        # → "Moved 3 PDF files to ~/Documents/PDFs. Started nginx service."
    """

    def build(
        self,
        intent: IntentIR,
        step_results: List[Any],
    ) -> str:
        """
        Return a concise summary string.

        Falls through three levels:
        1. intent.action_summary (LLM-provided)
        2. Derived from steps + results
        3. intent.goal
        """
        # Level 1: LLM already produced a summary
        if intent.action_summary:
            return intent.action_summary.strip()

        # Level 2: derive from step/result pairs
        if intent.steps:
            derived = self._derive(intent.steps, step_results)
            if derived:
                return derived

        # Level 3: fallback to goal
        return intent.goal

    def _derive(self, steps: List[Step], results: List[Any]) -> str:
        """Build summary from step list without calling the LLM."""
        # Aggregate by verb to collapse repeated operations
        counts: Dict[str, int] = {}
        targets: Dict[str, List[str]] = {}

        for step in steps:
            key = (step.tool, step.action)
            verb = _VERB_MAP.get(key, f"Ran {step.tool}.{step.action}")
            arg_key = _ARG_KEY.get(key)
            target = ""
            if arg_key and step.args.get(arg_key):
                target = str(step.args[arg_key])
                target = _shorten(target)

            counts[verb] = counts.get(verb, 0) + 1
            if target:
                targets.setdefault(verb, []).append(target)

        parts = []
        for verb, count in counts.items():
            tgts = targets.get(verb, [])
            if tgts:
                if count == 1:
                    parts.append(f"{verb} {tgts[0]}")
                else:
                    parts.append(f"{verb} {count} items")
            else:
                if count > 1:
                    parts.append(f"{verb} ({count} times)")
                else:
                    parts.append(verb)

        if not parts:
            return ""

        # Join up to 3 parts cleanly
        text = "; ".join(parts[:3])
        if len(parts) > 3:
            text += f" (+{len(parts) - 3} more)"

        return text + "."


def _shorten(path: str) -> str:
    """Truncate long paths or commands to keep the summary readable."""
    if len(path) > 40:
        return "..." + path[-37:]
    return path


# ---------------------------------------------------------------------------
# Module-level convenience function used by the orchestrator
# ---------------------------------------------------------------------------

def build_execution_summary(intent: IntentIR, step_results: List[Any]) -> str:
    """Convenience wrapper for single-call use from the orchestrator."""
    return ExecutionSummaryBuilder().build(intent, step_results)
