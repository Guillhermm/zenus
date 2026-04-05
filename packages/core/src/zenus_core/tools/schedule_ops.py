"""
ScheduleOps Tool

Allows agents to register recurring cron jobs and fire one-off remote
webhook triggers from within an execution plan.

Actions:
  schedule_cron(command, cron_expr, label)  — add a crontab entry
  list_cron(label_filter)                    — list registered Zenus cron entries
  remove_cron(label)                         — remove a crontab entry by label
  trigger_remote(url, payload, method)       — fire a webhook trigger
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Optional

import requests

from zenus_core.tools.base import Tool

# Sentinel comment added to every cron line managed by Zenus
_ZENUS_TAG = "# zenus-managed"


class ScheduleOps(Tool):
    """
    Schedule recurring cron jobs and fire remote webhook triggers.

    All cron entries managed by Zenus are tagged with a sentinel comment so
    they can be listed and removed without touching user-owned entries.
    """

    # ------------------------------------------------------------------
    # Cron management
    # ------------------------------------------------------------------

    def schedule_cron(
        self,
        command: str,
        cron_expr: str = "0 * * * *",
        label: str = "zenus-task",
    ) -> str:
        """
        Add a crontab entry that runs *command* on *cron_expr*.

        Args:
            command:   Shell command to run.
            cron_expr: Standard 5-field cron expression (default: every hour).
            label:     Human-readable label for later removal.

        Returns:
            Confirmation message with the full crontab line added.
        """
        if not self._valid_cron(cron_expr):
            return f"Invalid cron expression: {cron_expr!r}"

        line = f"{cron_expr} {command} {_ZENUS_TAG}:{label}"

        try:
            existing = self._read_crontab()
            updated = existing.rstrip("\n") + "\n" + line + "\n"
            self._write_crontab(updated)
            return f"Cron job registered:\n  {line}"
        except Exception as exc:
            return f"Failed to register cron job: {exc}"

    def list_cron(self, label_filter: str = "") -> str:
        """
        List all Zenus-managed cron entries.

        Args:
            label_filter: Optional substring filter on the label.
        """
        try:
            lines = [
                ln for ln in self._read_crontab().splitlines()
                if _ZENUS_TAG in ln
            ]
            if label_filter:
                lines = [ln for ln in lines if label_filter in ln]
            if not lines:
                return "No Zenus-managed cron jobs found."
            return "\n".join(lines)
        except Exception as exc:
            return f"Failed to list cron jobs: {exc}"

    def remove_cron(self, label: str) -> str:
        """
        Remove all Zenus-managed cron entries whose label matches *label*.

        Args:
            label: Label assigned when the cron job was created.
        """
        try:
            tag = f"{_ZENUS_TAG}:{label}"
            existing = self._read_crontab()
            filtered = "\n".join(
                ln for ln in existing.splitlines() if tag not in ln
            ) + "\n"
            removed = existing.count(tag)
            self._write_crontab(filtered)
            if removed:
                return f"Removed {removed} cron entry/entries with label '{label}'."
            return f"No cron entries found with label '{label}'."
        except Exception as exc:
            return f"Failed to remove cron job: {exc}"

    # ------------------------------------------------------------------
    # Remote trigger
    # ------------------------------------------------------------------

    def trigger_remote(
        self,
        url: str,
        payload: Optional[str] = None,
        method: str = "POST",
    ) -> str:
        """
        Fire a webhook / remote trigger.

        Args:
            url:     HTTP(S) endpoint to call.
            payload: Optional JSON string or plain text body.
            method:  HTTP method (default: POST).

        Returns:
            HTTP status code and truncated response body.
        """
        if not url.startswith(("http://", "https://")):
            return f"Invalid URL (must start with http:// or https://): {url!r}"

        headers = {"Content-Type": "application/json", "User-Agent": "Zenus/1.1"}
        body = None
        if payload:
            try:
                json.loads(payload)  # validate JSON
                body = payload
            except ValueError:
                body = json.dumps({"message": payload})

        try:
            resp = requests.request(
                method.upper(),
                url,
                data=body,
                headers=headers,
                timeout=15,
            )
            preview = resp.text[:200].replace("\n", " ") if resp.text else "(empty body)"
            return f"HTTP {resp.status_code}: {preview}"
        except requests.RequestException as exc:
            return f"Request failed: {exc}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _valid_cron(expr: str) -> bool:
        parts = expr.split()
        return len(parts) == 5

    @staticmethod
    def _read_crontab() -> str:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout
        # crontab -l exits 1 when there are no entries yet — that is not an error
        if "no crontab" in result.stderr.lower():
            return ""
        raise RuntimeError(result.stderr.strip())

    @staticmethod
    def _write_crontab(content: str) -> None:
        proc = subprocess.run(
            ["crontab", "-"],
            input=content,
            capture_output=True, text=True
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip())
