"""
DevOps Tool

Developer-experience utilities available to agents and users:

  ToolSearch  — search available tool registry by name or description
  AskUserQuestion — pause execution and prompt the user for structured input
  SleepTool   — wait for N seconds (polling, rate-limit back-off)

These are separate conceptually but grouped here to avoid file proliferation.
"""

from __future__ import annotations

import time
from typing import Optional

from zenus_core.tools.base import Tool


class ToolSearch(Tool):
    """Search the tool registry by name or description at runtime."""

    def search(self, query: str, limit: int = 10) -> str:
        """
        Search available tools and actions by name or description.

        Args:
            query: Search term (case-insensitive substring match).
            limit: Maximum number of results to return (default 10).

        Returns:
            Formatted list of matching tools and actions.
        """
        from zenus_core.tools.registry import describe

        query_lower = query.lower()
        registry = describe()
        matches = []

        for tool_name, info in registry.items():
            tool_doc = info.get("doc", "")
            if query_lower in tool_name.lower() or query_lower in tool_doc.lower():
                priv = " [privileged]" if info.get("privileged") else ""
                matches.append(f"  {tool_name}{priv}: {tool_doc}")
                if len(matches) >= limit:
                    break
                continue

            # Search at action level
            for action in info.get("actions", []):
                action_name = action.get("name", "")
                action_doc = action.get("doc", "")
                if query_lower in action_name.lower() or query_lower in action_doc.lower():
                    matches.append(f"  {tool_name}.{action_name}: {action_doc}")
                    if len(matches) >= limit:
                        break

            if len(matches) >= limit:
                break

        if not matches:
            return f"No tools or actions matching '{query}'."
        return f"Results for '{query}' ({len(matches)} match(es)):\n" + "\n".join(matches)


class AskUserQuestion(Tool):
    """
    Pause execution and ask the user a question, returning their answer.

    This makes user prompts first-class within an agent's execution plan,
    giving agents explicit control over when and how they request input.
    """

    def ask(
        self,
        question: str,
        options: Optional[str] = None,
        default: Optional[str] = None,
    ) -> str:
        """
        Display a question to the user and return their typed answer.

        Args:
            question: The question to display.
            options:  Comma-separated list of valid options (e.g. "y,n,skip").
                      If provided, the user's answer is validated against these.
            default:  Default answer if the user presses Enter without typing.

        Returns:
            The user's answer as a string.
        """
        from zenus_core.output.console import console

        console.print()
        console.print(f"[bold cyan]❓ {question}[/bold cyan]")

        if options:
            opts = [o.strip() for o in options.split(",")]
            opts_display = " / ".join(opts)
            if default and default in opts:
                opts_display = " / ".join(
                    f"[bold]{o}[/bold]" if o == default else o for o in opts
                )
            console.print(f"[dim]Options: {opts_display}[/dim]")

        if default:
            prompt_str = f"[dim](default: {default})[/dim] > "
        else:
            prompt_str = "> "

        console.print(prompt_str, end="")
        try:
            answer = input().strip()
        except (EOFError, KeyboardInterrupt):
            answer = default or ""

        if not answer and default:
            answer = default

        if options:
            valid = [o.strip().lower() for o in options.split(",")]
            if answer.lower() not in valid:
                console.print(
                    f"[yellow]Invalid option '{answer}'. Expected one of: {', '.join(valid)}[/yellow]"
                )
                return self.ask(question, options, default)

        return answer


class SleepTool(Tool):
    """Pause execution for a specified number of seconds."""

    def sleep(self, seconds: float) -> str:
        """
        Wait for *seconds* before continuing.

        Useful for polling loops, rate-limit back-off, and timed retries.

        Args:
            seconds: Number of seconds to sleep (max 300).

        Returns:
            Confirmation of how long it slept.
        """
        seconds = min(float(seconds), 300.0)
        time.sleep(seconds)
        return f"Slept for {seconds:.1f} second(s)."
