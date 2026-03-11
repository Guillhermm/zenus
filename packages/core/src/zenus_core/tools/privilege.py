"""
Privilege Tiers

Controls which tools are available in a given execution context.

Tiers (ascending privilege):
    RESTRICTED  — read-only file/system inspection, no mutations
    STANDARD    — full tool registry except ShellOps and CodeExec
    PRIVILEGED  — everything, including ShellOps and CodeExec

The orchestrator sets the tier when constructing an execution context.
Interactive sessions default to PRIVILEGED.
Automated pipelines (API, cron, hooks) default to STANDARD.
"""

from enum import Enum


class PrivilegeTier(str, Enum):
    RESTRICTED = "restricted"
    STANDARD   = "standard"
    PRIVILEGED = "privileged"


# Tools that require PRIVILEGED tier
PRIVILEGED_TOOLS = {"ShellOps", "CodeExec"}


def check_privilege(tool_name: str, tier: PrivilegeTier) -> None:
    """
    Raise PermissionError if `tool_name` is not allowed at `tier`.

    Args:
        tool_name: Name of the tool being dispatched.
        tier:      Current execution tier.

    Raises:
        PermissionError: If the tool requires a higher tier.
    """
    if tool_name in PRIVILEGED_TOOLS and tier != PrivilegeTier.PRIVILEGED:
        raise PermissionError(
            f"{tool_name} requires PRIVILEGED tier (current: {tier.value}). "
            "This tool is only available in interactive sessions. "
            "Start Zenus interactively or explicitly grant privileged access."
        )
