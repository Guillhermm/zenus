"""
Zenus MCP Client

Connects to one or more external MCP servers (configured in ``mcp.client.servers``)
and registers their tools into the Zenus tool registry so the orchestrator can
dispatch to them transparently alongside native Zenus tools.

Tool naming inside Zenus:  ``mcp__{server_name}__{remote_tool_name}``
  e.g.  mcp__filesystem__read_file

Usage is automatic when ``mcp.client.enabled: true`` in config.yaml.  The
registry is populated lazily on first call to ``MCPClientRegistry.initialise()``.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
from typing import Any, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

from zenus_core.tools.base import Tool

logger = logging.getLogger(__name__)


class MCPRemoteTool(Tool):
    """
    A Zenus Tool that proxies calls to a remote MCP server tool.

    Instances of this class are injected into TOOLS at startup when
    ``mcp.client.enabled`` is true.
    """

    def __init__(self, server_name: str, remote_name: str, description: str, input_schema: dict) -> None:
        self.name = f"mcp__{server_name}__{remote_name}"
        self._server_name = server_name
        self._remote_name = remote_name
        self._description = description
        self._input_schema = input_schema
        # Callback set by MCPClientRegistry after connection is established
        self._invoke: Optional[Any] = None

    def __doc__(self) -> str:  # type: ignore[override]
        return self._description

    def dry_run(self, **kwargs: Any) -> str:
        return f"[dry-run] Would call {self._server_name}/{self._remote_name}({kwargs})"

    def execute(self, **kwargs: Any) -> str:
        if self._invoke is None:
            return f"[error] MCP server '{self._server_name}' is not connected."
        try:
            return asyncio.get_event_loop().run_until_complete(self._invoke(**kwargs))
        except Exception as exc:
            return f"[error] {exc}"

    # Allow the orchestrator to call action methods dynamically.
    # Since MCP tools are single-action (the tool IS the action), we expose
    # a ``call`` method and also make the instance callable.
    def call(self, **kwargs: Any) -> str:
        """Invoke the remote MCP tool."""
        return self.execute(**kwargs)

    def __call__(self, **kwargs: Any) -> str:
        return self.execute(**kwargs)


class MCPClientRegistry:
    """
    Manages connections to external MCP servers and injects their tools into TOOLS.

    Lifecycle:
      1. ``MCPClientRegistry(config.mcp.client)``
      2. ``await registry.initialise()``  — connects, discovers tools, registers them
      3. Normal Zenus execution; tools are dispatched via TOOLS as usual
      4. ``await registry.shutdown()``    — closes all sessions
    """

    def __init__(self, client_config: Any) -> None:
        if not _MCP_AVAILABLE:
            raise ImportError(
                "The 'mcp' package is required for MCP client mode.\n"
                "Install it with:  pip install 'zenus-core[mcp]'  or  pip install mcp"
            )
        self._config = client_config
        self._sessions: Dict[str, Any] = {}   # name → ClientSession
        self._cm_stack: List[Any] = []        # context managers to clean up
        self._tools: Dict[str, MCPRemoteTool] = {}

    # ------------------------------------------------------------------
    # Async lifecycle
    # ------------------------------------------------------------------

    async def initialise(self) -> Dict[str, MCPRemoteTool]:
        """
        Connect to all configured servers and discover their tools.

        Returns:
            Mapping of Zenus tool name → MCPRemoteTool instance.
        """
        from zenus_core.tools.registry import TOOLS  # imported here to avoid circular

        for srv_cfg in self._config.servers:
            try:
                await self._connect(srv_cfg)
            except Exception as exc:
                logger.warning("[mcp-client] Could not connect to '%s': %s", srv_cfg.name, exc)

        # Inject discovered remote tools into the shared registry
        TOOLS.update(self._tools)
        logger.info("[mcp-client] Registered %d remote tools from %d server(s)",
                    len(self._tools), len(self._sessions))
        return self._tools

    async def shutdown(self) -> None:
        """Close all open MCP sessions."""
        for cm in reversed(self._cm_stack):
            try:
                await cm.__aexit__(None, None, None)
            except Exception as exc:
                logger.debug("[mcp-client] Error during shutdown: %s", exc)
        self._sessions.clear()
        self._cm_stack.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _connect(self, srv_cfg: Any) -> None:
        """Establish a session with one MCP server and discover its tools."""
        if srv_cfg.transport == "sse":
            if not srv_cfg.url:
                raise ValueError(f"Server '{srv_cfg.name}' has transport='sse' but no url configured.")
            cm = sse_client(srv_cfg.url)
        else:
            # stdio transport
            if not srv_cfg.command:
                raise ValueError(f"Server '{srv_cfg.name}' has transport='stdio' but no command configured.")
            cmd_parts = shlex.split(srv_cfg.command)
            params = StdioServerParameters(
                command=cmd_parts[0],
                args=cmd_parts[1:],
                env=srv_cfg.env or {},
            )
            cm = stdio_client(params)

        read, write = await cm.__aenter__()
        self._cm_stack.append(cm)

        session = ClientSession(read, write)
        await session.__aenter__()
        self._cm_stack.append(session)

        await session.initialize()
        self._sessions[srv_cfg.name] = session

        # Discover and register tools
        response = await session.list_tools()
        for tool_info in response.tools:
            remote_tool = MCPRemoteTool(
                server_name=srv_cfg.name,
                remote_name=tool_info.name,
                description=tool_info.description or tool_info.name,
                input_schema=tool_info.inputSchema or {},
            )
            # Close over session + tool_info.name
            remote_tool._invoke = _make_invoker(session, tool_info.name)
            zenus_name = f"mcp__{srv_cfg.name}__{tool_info.name}"
            self._tools[zenus_name] = remote_tool
            logger.debug("[mcp-client] Registered tool: %s", zenus_name)


def _make_invoker(session: Any, tool_name: str):
    """Return an async callable that invokes `tool_name` on `session`."""
    async def _invoke(**kwargs: Any) -> str:
        result = await session.call_tool(tool_name, arguments=kwargs)
        # result.content is a list of ContentBlock objects
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return _invoke


# ---------------------------------------------------------------------------
# Convenience: synchronous initialisation for non-async callers (CLI startup)
# ---------------------------------------------------------------------------

def register_mcp_servers_sync(client_config: Any) -> Dict[str, MCPRemoteTool]:
    """
    Synchronous wrapper around MCPClientRegistry.initialise().

    Suitable for use in synchronous CLI entry-points.  Returns the map of
    registered remote tools (empty dict on failure or if no servers configured).
    """
    if not client_config.enabled or not client_config.servers:
        return {}

    registry = MCPClientRegistry(client_config)
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(registry.initialise())
        finally:
            loop.run_until_complete(registry.shutdown())
            loop.close()
    except Exception as exc:
        logger.warning("[mcp-client] Startup registration failed: %s", exc)
        return {}
