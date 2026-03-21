"""
Zenus MCP Server

Exposes every action of every tool in the Zenus registry as an individual
MCP tool, allowing Claude Code, Cline, Continue, and any other MCP-compatible
client to invoke Zenus capabilities directly.

Tool naming convention:  ``{ToolName}__{action_name}``
  e.g.  FileOps__read_file,  SystemOps__get_cpu_usage

Privilege tier:
  By default the server runs with PrivilegeTier.STANDARD, which excludes
  ShellOps and CodeExec.  Set ``mcp.server.allow_privileged: true`` in
  config.yaml (or MCP_ALLOW_PRIVILEGED=1) to expose those tools only in
  fully trusted, local environments.

Transports:
  stdio  — default; for Claude Code / Cline (direct subprocess spawn)
  sse    — HTTP Server-Sent Events; for web-based clients
"""

from __future__ import annotations

import inspect
import logging
import os
from typing import Any, Callable, Dict

from zenus_core.tools.registry import TOOLS
from zenus_core.tools.privilege import PRIVILEGED_TOOLS, PrivilegeTier, check_privilege

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKIP_ATTRS = frozenset({"name", "dry_run", "execute"})


def _public_actions(tool_instance: Any) -> list[tuple[str, Callable]]:
    """Return (action_name, bound_method) pairs for all public actions."""
    tool_cls = type(tool_instance)
    result = []
    for attr_name in sorted(dir(tool_cls)):
        if attr_name.startswith("_") or attr_name in _SKIP_ATTRS:
            continue
        # Skip properties to avoid triggering lazy side-effects
        is_prop = any(
            isinstance(klass.__dict__.get(attr_name), property)
            for klass in tool_cls.__mro__
            if attr_name in klass.__dict__
        )
        if is_prop:
            continue
        method = getattr(tool_instance, attr_name, None)
        if callable(method):
            result.append((attr_name, method))
    return result


def _build_description(tool_name: str, action_name: str, method: Callable) -> str:
    raw_doc = inspect.getdoc(method) or ""
    first_line = raw_doc.split("\n")[0].strip()
    privileged_note = " [PRIVILEGED — requires allow_privileged]" if tool_name in PRIVILEGED_TOOLS else ""
    return f"[Zenus/{tool_name}]{privileged_note} {first_line}" if first_line else f"[Zenus/{tool_name}]{privileged_note} {action_name}"


def _wrap_action(
    tool_name: str,
    action_name: str,
    method: Callable,
    tier: PrivilegeTier,
) -> Callable:
    """Return a wrapper function with a proper signature for FastMCP."""
    sig = inspect.signature(method)
    params = {
        name: param
        for name, param in sig.parameters.items()
        if name != "self"
    }

    # Build a wrapper with **kwargs so FastMCP can introspect the signature
    # via the original method's signature (FastMCP uses the function's __wrapped__
    # or __signature__ when available).
    def _handler(**kwargs: Any) -> str:
        try:
            check_privilege(tool_name, tier)
        except PermissionError as exc:
            return f"[error] {exc}"
        try:
            result = method(**kwargs)
            return str(result) if result is not None else "ok"
        except Exception as exc:
            logger.debug("[mcp-server] %s__%s raised %r", tool_name, action_name, exc)
            return f"[error] {exc}"

    # Give the handler the same signature as the original method (minus 'self')
    # so FastMCP can generate accurate input schemas.
    _handler.__name__ = f"{tool_name}__{action_name}"
    _handler.__doc__ = _build_description(tool_name, action_name, method)
    try:
        _handler.__signature__ = sig.replace(  # type: ignore[attr-defined]
            parameters=[p for n, p in sig.parameters.items() if n != "self"]
        )
    except (ValueError, TypeError):
        pass  # signature replacement is best-effort

    return _handler


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_server(allow_privileged: bool = False) -> "Any":
    """
    Construct and return a FastMCP server instance with all Zenus tools registered.

    Args:
        allow_privileged: When True, ShellOps and CodeExec are also exposed.

    Returns:
        A fully configured ``FastMCP`` instance ready to call ``.run()``.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "The 'mcp' package is required for MCP server mode.\n"
            "Install it with:  pip install 'zenus-core[mcp]'  or  pip install mcp"
        ) from exc

    tier = PrivilegeTier.PRIVILEGED if allow_privileged else PrivilegeTier.STANDARD

    mcp = FastMCP(
        "Zenus",
        instructions=(
            "You are talking to the Zenus intent-execution engine. "
            "Each tool maps to a Zenus action (FileOps, SystemOps, GitOps, …). "
            "All operations respect Zenus privilege tiers and safety policies."
        ),
    )

    registered = 0
    for tool_name, tool_instance in TOOLS.items():
        if tool_name in PRIVILEGED_TOOLS and not allow_privileged:
            logger.debug("[mcp-server] Skipping privileged tool %s (allow_privileged=False)", tool_name)
            continue

        for action_name, method in _public_actions(tool_instance):
            mcp_tool_name = f"{tool_name}__{action_name}"
            handler = _wrap_action(tool_name, action_name, method, tier)
            mcp.add_tool(
                handler,
                name=mcp_tool_name,
                description=_build_description(tool_name, action_name, method),
            )
            registered += 1

    logger.info("[mcp-server] Registered %d tools (privileged=%s)", registered, allow_privileged)
    return mcp


def run_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8765,
    allow_privileged: bool = False,
) -> None:
    """
    Build and start the Zenus MCP server.

    Args:
        transport:        'stdio' (default) or 'sse'.
        host:             SSE bind address (ignored for stdio).
        port:             SSE port (ignored for stdio).
        allow_privileged: Expose ShellOps and CodeExec.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # noqa: F401 — validate availability early
    except ImportError as exc:
        raise ImportError(
            "The 'mcp' package is required for MCP server mode.\n"
            "Install it with:  pip install 'zenus-core[mcp]'  or  pip install mcp"
        ) from exc

    # Allow env-var override for quick one-off privileged sessions
    if os.getenv("MCP_ALLOW_PRIVILEGED", "").lower() in ("1", "true", "yes"):
        allow_privileged = True

    server = build_server(allow_privileged=allow_privileged)

    if transport == "sse":
        server.settings.host = host
        server.settings.port = port
        server.run(transport="sse")
    else:
        server.run(transport="stdio")
