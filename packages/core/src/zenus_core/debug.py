"""
Debug flags for Zenus.

Every subsystem has its own flag so developers can enable only the noise
they care about.  A master switch (``debug.enabled`` / ``ZENUS_DEBUG``)
turns everything on at once.

Priority for each flag (first truthy value wins):
    1. config.yaml  ``debug.<name>: true``
    2. Environment variable ``ZENUS_DEBUG_<NAME>=1``
    3. Master env var ``ZENUS_DEBUG=1``   (enables all subsystems)

Subsystems
----------
orchestrator  Routing decisions, complexity scores, Tree of Thoughts paths,
              provider/model override notices, cache hits.
brain         Prompt-evolution promotions and internal brain module events.
execution     Per-step execution output, parallel-fallback notices.
voice         TTS/STT initialisation messages and pipeline internals.
search        Search query category, source breakdown, raw result snippets.
              Also honours legacy ``search.debug`` config key and
              ``ZENUS_SEARCH_DEBUG`` env var for backwards compatibility.

Usage
-----
    from zenus_core.debug import get_debug_flags

    if get_debug_flags().orchestrator:
        console.print("[dim]Task complexity: ...[/dim]")
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DebugFlags:
    """Per-subsystem debug flags.  All ``False`` by default — clean output."""

    enabled: bool = False       # master switch
    orchestrator: bool = False  # routing, complexity, ToT, provider notices, cache hits
    brain: bool = False         # prompt evolution, model internals
    execution: bool = False     # step-by-step execution, parallel fallback
    voice: bool = False         # TTS/STT init messages and pipeline internals
    search: bool = False        # search decisions, query type, result breakdown


_flags: Optional[DebugFlags] = None


def get_debug_flags() -> DebugFlags:
    """Return the cached debug flags, loading them on first call."""
    global _flags
    if _flags is None:
        _flags = _load_flags()
    return _flags


def reset_debug_flags() -> None:
    """Invalidate the cache so flags are reloaded on next access.

    Useful in tests and after a config reload.
    """
    global _flags
    _flags = None


# ---------------------------------------------------------------------------
# Internal loader — never call directly; use get_debug_flags()
# ---------------------------------------------------------------------------

def _env_bool(name: str) -> bool:
    return bool(os.environ.get(name))


def _load_flags() -> DebugFlags:
    """Build DebugFlags from config + environment."""
    d = None
    try:
        from zenus_core.config.loader import get_config  # local import — avoids cycles
        cfg = get_config()
        if hasattr(cfg, "debug"):
            d = cfg.debug
    except Exception:
        pass

    master = (d.enabled if d else False) or _env_bool("ZENUS_DEBUG")

    def _flag(attr: str, env_var: str) -> bool:
        specific = (getattr(d, attr, False) if d else False) or _env_bool(env_var)
        return master or specific

    # search: also check legacy search.debug config key and ZENUS_SEARCH_DEBUG
    search_flag = _flag("search", "ZENUS_DEBUG_SEARCH") or _env_bool("ZENUS_SEARCH_DEBUG")
    if not search_flag:
        try:
            from zenus_core.config.loader import get_config
            cfg = get_config()
            if hasattr(cfg, "search") and getattr(cfg.search, "debug", False):
                search_flag = True
        except Exception:
            pass

    return DebugFlags(
        enabled=master,
        orchestrator=_flag("orchestrator", "ZENUS_DEBUG_ORCHESTRATOR"),
        brain=_flag("brain", "ZENUS_DEBUG_BRAIN"),
        execution=_flag("execution", "ZENUS_DEBUG_EXECUTION"),
        voice=_flag("voice", "ZENUS_DEBUG_VOICE"),
        search=search_flag,
    )
