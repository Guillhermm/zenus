"""
Context Compactor

Summarises and compresses the conversation / session history as the context
window approaches its limit.  The compressed summary is written back as a
synthetic assistant turn so the LLM can continue without losing key state.

Two entry points:
  - ``compact_session(session_memory)`` — used by /compact command
  - ``maybe_compact(session_memory, token_count, max_tokens)`` — used by the
    orchestrator to auto-compact when threshold is crossed
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = """\
You are a session summariser.  Below is the history of a Zenus session.
Produce a concise summary that preserves:
- The original user goal
- Every tool that was called and its outcome
- Any errors or retries
- The current state after the last action

Output plain prose (no markdown headers), under 400 words.

SESSION HISTORY:
{history}
"""


def compact_session(session_memory) -> str:
    """
    Summarise ``session_memory`` and replace its intent list with the summary.

    Returns the summary text, or an empty string on failure.
    """
    try:
        intents = session_memory.intent_history[:]
        if not intents:
            return ""

        # Build raw history text
        parts = []
        for entry in intents:
            user_in = entry.get("user_input", "")
            goal = entry.get("intent", {}).get("goal", "")
            results = entry.get("results", [])
            parts.append(f"User: {user_in}")
            if goal:
                parts.append(f"Goal: {goal}")
            if results:
                parts.append("Results: " + "; ".join(str(r)[:100] for r in results))
        history_text = "\n".join(parts)

        # Ask LLM to summarise
        from zenus_core.brain.llm.factory import get_llm
        llm = get_llm()
        prompt = _SUMMARY_PROMPT.format(history=history_text)
        summary = llm.ask(prompt)

        # Replace history with synthetic summary entry
        session_memory.intent_history.clear()
        session_memory.intent_history.append(
            {
                "user_input": "[compacted session summary]",
                "intent": {"goal": "[summary]", "steps": []},
                "results": [summary],
                "compacted": True,
            }
        )

        logger.info("Session compacted: %d intents → 1 summary", len(intents))
        return summary

    except Exception as exc:
        logger.warning("Compaction failed: %s", exc)
        return ""


def maybe_compact(session_memory, token_count: int, max_tokens: int) -> bool:
    """
    Auto-compact if token usage exceeds the configured threshold.

    Returns True if compaction was performed.
    """
    try:
        from zenus_core.config.loader import get_config
        threshold = get_config().session.compact_threshold
    except Exception:
        threshold = 0.80

    if max_tokens <= 0 or (token_count / max_tokens) < threshold:
        return False

    from zenus_core.output.console import print_warning
    print_warning(
        f"Context window {token_count / max_tokens:.0%} full — auto-compacting session history."
    )
    result = compact_session(session_memory)
    if result:
        from zenus_core.output.console import print_info
        print_info("Session compacted. History replaced with a concise summary.")
        return True
    return False
