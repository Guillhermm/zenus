"""
Zenus MCP Integration

Provides both server and client support for the Model Context Protocol (MCP):

  Server mode  — expose Zenus tool implementations to any MCP-compatible client
                 (Claude Code, Cline, Continue, …).  Start with ``zenus mcp-server``.

  Client mode  — connect to external MCP servers at startup and make their tools
                 available inside the Zenus orchestrator alongside native tools.
"""

from __future__ import annotations

__all__ = ["build_server", "MCPClientRegistry"]
