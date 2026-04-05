"""
Plan Mode

When active, Zenus translates user intent into a full step-by-step plan and
presents it for user approval *before* executing any step.  Side-effectful tool
actions (risk > 0) are blocked until the user types 'y' / 'yes' / 'approve'.

The gate is implemented as a module-level singleton so the orchestrator,
CLI router, and TUI can all share the same state without circular imports.

Usage (programmatic)::

    from zenus_core.brain.plan_mode import get_plan_mode_manager, PlanDecision

    mgr = get_plan_mode_manager()
    mgr.enable()

    # Inside orchestrator, before execute_plan():
    decision = mgr.gate(intent)
    if decision == PlanDecision.DENIED:
        return  # user rejected
    # else: proceed to execute_plan()

CLI / TUI users toggle via ``/plan`` command.
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from zenus_core.brain.llm.schemas import IntentIR


class PlanDecision(Enum):
    """Result of gating a plan through plan mode."""

    APPROVED = "approved"
    """User approved — proceed with execution."""

    DENIED = "denied"
    """User rejected — abort execution."""

    BYPASSED = "bypassed"
    """Plan mode is disabled; execution can proceed without user approval."""


class PlanModeManager:
    """
    Manages plan-mode state and gating logic.

    Thread-safe so background tasks and TUI can check the flag without races.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enabled = self._load_from_config()

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _load_from_config(self) -> bool:
        try:
            from zenus_core.config.loader import get_config
            return get_config().plan_mode.enabled
        except Exception:
            return False

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def enable(self) -> None:
        """Activate plan mode."""
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        """Deactivate plan mode."""
        with self._lock:
            self._enabled = False

    def toggle(self) -> bool:
        """Flip plan mode; returns new state."""
        with self._lock:
            self._enabled = not self._enabled
            return self._enabled

    # ------------------------------------------------------------------
    # Gate logic
    # ------------------------------------------------------------------

    def gate(self, intent: "IntentIR") -> PlanDecision:
        """
        Present the plan to the user and wait for approval.

        Returns BYPASSED immediately when plan mode is disabled.
        Returns APPROVED / DENIED based on user input.
        """
        if not self.enabled:
            return PlanDecision.BYPASSED

        from zenus_core.output.console import console
        from rich.table import Table
        from rich.panel import Panel

        # Check auto-approve logic
        try:
            from zenus_core.config.loader import get_config
            auto_approve_low_risk = get_config().plan_mode.auto_approve_low_risk
        except Exception:
            auto_approve_low_risk = False

        all_low_risk = all(s.risk == 0 for s in intent.steps)
        if auto_approve_low_risk and all_low_risk:
            console.print("[dim cyan]↳ [plan mode] All steps are READ-only — auto-approving[/dim cyan]")
            return PlanDecision.APPROVED

        # Display the plan
        console.print()
        console.print(
            Panel.fit(
                f"[bold cyan]Plan Mode — Proposed Plan[/bold cyan]\n"
                f"[dim]Goal: {intent.goal}[/dim]",
                border_style="cyan",
            )
        )

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("#", style="dim", width=3)
        table.add_column("Tool.Action", style="cyan", no_wrap=True)
        table.add_column("Risk", width=8)
        table.add_column("Summary")

        RISK_LABELS = {0: "[green]READ[/green]", 1: "[cyan]CREATE[/cyan]",
                       2: "[yellow]MODIFY[/yellow]", 3: "[red]DELETE[/red]"}

        for i, step in enumerate(intent.steps, 1):
            risk_label = RISK_LABELS.get(step.risk, str(step.risk))
            args_summary = ", ".join(f"{k}={v!r}" for k, v in (step.args or {}).items())[:60]
            table.add_row(str(i), f"{step.tool}.{step.action}", risk_label, args_summary)

        console.print(table)
        console.print()
        console.print("[bold]Approve this plan?[/bold] [dim](y / yes / approve — anything else aborts)[/dim]")

        try:
            answer = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("[yellow]Plan rejected (interrupted)[/yellow]")
            return PlanDecision.DENIED

        if answer in ("y", "yes", "approve", "ok", "go"):
            console.print("[green]✓ Plan approved — executing…[/green]\n")
            return PlanDecision.APPROVED

        console.print("[yellow]✗ Plan rejected — execution aborted.[/yellow]\n")
        return PlanDecision.DENIED


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: Optional[PlanModeManager] = None
_manager_lock = threading.Lock()


def get_plan_mode_manager() -> PlanModeManager:
    """Return the global PlanModeManager singleton."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = PlanModeManager()
    return _manager
