"""
Tests for Zenus MCP integration (server and client).

All tests are fully offline — no real MCP connections are made.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

class _FakeTool:
    """Minimal fake Zenus tool for injection tests."""

    def read_stuff(self, path: str, encoding: str = "utf-8") -> str:
        """Read some stuff from path."""
        return f"content of {path}"

    def write_stuff(self, path: str, content: str) -> str:
        """Write content to path."""
        return f"wrote {len(content)} bytes to {path}"


# ---------------------------------------------------------------------------
# Config schema tests
# ---------------------------------------------------------------------------

class TestMCPConfigSchema:
    def test_defaults(self):
        from zenus_core.config.schema import MCPConfig
        cfg = MCPConfig()
        assert cfg.server.enabled is False
        assert cfg.server.allow_privileged is False
        assert cfg.server.transport == "stdio"
        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 8765
        assert cfg.client.enabled is False
        assert cfg.client.servers == []

    def test_external_server_model(self):
        from zenus_core.config.schema import MCPExternalServer
        s = MCPExternalServer(name="fs", transport="stdio", command="uvx mcp-fs /tmp")
        assert s.name == "fs"
        assert s.command == "uvx mcp-fs /tmp"

    def test_sse_server_model(self):
        from zenus_core.config.schema import MCPExternalServer
        s = MCPExternalServer(name="remote", transport="sse", url="http://localhost:9000/sse")
        assert s.url == "http://localhost:9000/sse"

    def test_zenus_config_has_mcp_field(self):
        from zenus_core.config.schema import ZenusConfig
        cfg = ZenusConfig()
        assert hasattr(cfg, "mcp")
        from zenus_core.config.schema import MCPConfig
        assert isinstance(cfg.mcp, MCPConfig)


# ---------------------------------------------------------------------------
# Server: build_server
# ---------------------------------------------------------------------------

class TestBuildServer:
    def test_build_server_returns_fastmcp(self):
        from mcp.server.fastmcp import FastMCP
        from zenus_core.mcp.server import build_server
        server = build_server(allow_privileged=False)
        assert isinstance(server, FastMCP)

    def test_build_server_registers_tools(self):
        from zenus_core.mcp.server import build_server
        from zenus_core.tools.registry import TOOLS
        from zenus_core.tools.privilege import PRIVILEGED_TOOLS

        server = build_server(allow_privileged=False)
        # Get registered tool names from the server
        tool_names = {t.name for t in server._tool_manager.list_tools()}

        # FileOps__read_file should be present (FileOps is not privileged)
        non_privileged = [n for n in TOOLS if n not in PRIVILEGED_TOOLS]
        assert len(non_privileged) > 0, "Expected at least one non-privileged tool"

        # At least some tools from non-privileged set should be registered
        registered_prefixes = {name.split("__")[0] for name in tool_names}
        for tname in non_privileged:
            assert tname in registered_prefixes, f"{tname} not found in registered tools"

    def test_privileged_tools_excluded_by_default(self):
        from zenus_core.mcp.server import build_server
        from zenus_core.tools.privilege import PRIVILEGED_TOOLS

        server = build_server(allow_privileged=False)
        tool_names = {t.name for t in server._tool_manager.list_tools()}

        for ptool in PRIVILEGED_TOOLS:
            for name in tool_names:
                assert not name.startswith(f"{ptool}__"), (
                    f"Privileged tool {name} should not be registered when allow_privileged=False"
                )

    def test_privileged_tools_included_when_allowed(self):
        from zenus_core.mcp.server import build_server
        from zenus_core.tools.privilege import PRIVILEGED_TOOLS

        server = build_server(allow_privileged=True)
        tool_names = {t.name for t in server._tool_manager.list_tools()}
        prefixes = {name.split("__")[0] for name in tool_names}

        for ptool in PRIVILEGED_TOOLS:
            assert ptool in prefixes, f"Privileged tool {ptool} should be registered when allow_privileged=True"

    def test_tool_descriptions_contain_tool_name(self):
        from zenus_core.mcp.server import build_server

        server = build_server(allow_privileged=False)
        for tool in server._tool_manager.list_tools():
            # description should reference the Zenus tool namespace
            assert "[Zenus/" in tool.description, (
                f"Tool {tool.name!r} description missing [Zenus/...] prefix: {tool.description!r}"
            )

    def test_tool_name_format(self):
        from zenus_core.mcp.server import build_server

        server = build_server(allow_privileged=False)
        for tool in server._tool_manager.list_tools():
            assert "__" in tool.name, f"Tool name {tool.name!r} should contain '__'"
            parts = tool.name.split("__")
            assert len(parts) == 2, f"Expected exactly two parts in {tool.name!r}"


# ---------------------------------------------------------------------------
# Server: _wrap_action
# ---------------------------------------------------------------------------

class TestWrapAction:
    def _make_tool_instance(self):
        return _FakeTool()

    def test_handler_returns_string_result(self):
        from zenus_core.mcp.server import _wrap_action
        from zenus_core.tools.privilege import PrivilegeTier

        tool = self._make_tool_instance()
        handler = _wrap_action("FakeTool", "read_stuff", tool.read_stuff, PrivilegeTier.STANDARD)
        result = handler(path="/tmp/x.txt")
        assert result == "content of /tmp/x.txt"

    def test_handler_returns_error_string_on_exception(self):
        from zenus_core.mcp.server import _wrap_action
        from zenus_core.tools.privilege import PrivilegeTier

        def bad_method(**kwargs):
            raise RuntimeError("something went wrong")

        handler = _wrap_action("FakeTool", "bad_action", bad_method, PrivilegeTier.STANDARD)
        result = handler()
        assert result.startswith("[error]")
        assert "something went wrong" in result

    def test_handler_blocks_privileged_tool_at_standard_tier(self):
        from zenus_core.mcp.server import _wrap_action
        from zenus_core.tools.privilege import PrivilegeTier

        def priv_method(**kwargs):  # pragma: no cover
            return "should not reach here"

        # Patch PRIVILEGED_TOOLS in the privilege module (where check_privilege reads it)
        with patch("zenus_core.tools.privilege.PRIVILEGED_TOOLS", {"PrivTool"}):
            handler = _wrap_action("PrivTool", "action", priv_method, PrivilegeTier.STANDARD)
            result = handler()
        assert "[error]" in result
        assert "PRIVILEGED" in result

    def test_handler_name_matches_convention(self):
        from zenus_core.mcp.server import _wrap_action
        from zenus_core.tools.privilege import PrivilegeTier

        tool = self._make_tool_instance()
        handler = _wrap_action("FakeTool", "read_stuff", tool.read_stuff, PrivilegeTier.STANDARD)
        assert handler.__name__ == "FakeTool__read_stuff"

    def test_handler_has_docstring(self):
        from zenus_core.mcp.server import _wrap_action
        from zenus_core.tools.privilege import PrivilegeTier

        tool = self._make_tool_instance()
        handler = _wrap_action("FakeTool", "read_stuff", tool.read_stuff, PrivilegeTier.STANDARD)
        assert handler.__doc__ is not None
        assert "FakeTool" in handler.__doc__


# ---------------------------------------------------------------------------
# Server: _build_description
# ---------------------------------------------------------------------------

class TestBuildDescription:
    def test_includes_tool_name(self):
        from zenus_core.mcp.server import _build_description

        def my_method():
            """Do the thing."""

        desc = _build_description("MyTool", "my_method", my_method)
        assert "[Zenus/MyTool]" in desc
        assert "Do the thing." in desc

    def test_privileged_note_for_privileged_tool(self):
        from zenus_core.mcp.server import _build_description

        def shell_method():
            """Execute shell command."""

        with patch("zenus_core.mcp.server.PRIVILEGED_TOOLS", {"ShellOps"}):
            desc = _build_description("ShellOps", "run", shell_method)
        assert "PRIVILEGED" in desc

    def test_no_privileged_note_for_standard_tool(self):
        from zenus_core.mcp.server import _build_description

        def normal_method():
            """Normal action."""

        with patch("zenus_core.mcp.server.PRIVILEGED_TOOLS", {"ShellOps"}):
            desc = _build_description("FileOps", "read", normal_method)
        assert "PRIVILEGED" not in desc

    def test_fallback_to_action_name_when_no_docstring(self):
        from zenus_core.mcp.server import _build_description

        def no_doc():
            pass

        desc = _build_description("MyTool", "no_doc", no_doc)
        assert "no_doc" in desc


# ---------------------------------------------------------------------------
# Client: MCPRemoteTool
# ---------------------------------------------------------------------------

class TestMCPRemoteTool:
    def _make_tool(self):
        from zenus_core.mcp.client import MCPRemoteTool
        return MCPRemoteTool(
            server_name="myserver",
            remote_name="do_thing",
            description="Does a thing",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        )

    def test_name_format(self):
        tool = self._make_tool()
        assert tool.name == "mcp__myserver__do_thing"

    def test_dry_run(self):
        tool = self._make_tool()
        result = tool.dry_run(x="hello")
        assert "dry-run" in result
        assert "do_thing" in result

    def test_execute_without_invoke_returns_error(self):
        tool = self._make_tool()
        result = tool.execute(x="hello")
        assert "[error]" in result
        assert "myserver" in result

    def test_execute_with_invoke(self):
        tool = self._make_tool()

        async def _fake_invoke(**kwargs):
            return f"got x={kwargs.get('x')}"

        tool._invoke = _fake_invoke
        result = tool.execute(x="world")
        assert result == "got x=world"

    def test_call_delegates_to_execute(self):
        tool = self._make_tool()

        async def _fake_invoke(**kwargs):
            return "ok"

        tool._invoke = _fake_invoke
        assert tool.call() == "ok"
        assert tool() == "ok"


# ---------------------------------------------------------------------------
# Client: register_mcp_servers_sync — disabled path
# ---------------------------------------------------------------------------

class TestRegisterMCPServersSyncDisabled:
    def test_returns_empty_when_disabled(self):
        from zenus_core.mcp.client import register_mcp_servers_sync
        from zenus_core.config.schema import MCPClientConfig
        cfg = MCPClientConfig(enabled=False, servers=[])
        result = register_mcp_servers_sync(cfg)
        assert result == {}

    def test_returns_empty_when_no_servers(self):
        from zenus_core.mcp.client import register_mcp_servers_sync
        from zenus_core.config.schema import MCPClientConfig
        cfg = MCPClientConfig(enabled=True, servers=[])
        result = register_mcp_servers_sync(cfg)
        assert result == {}


# ---------------------------------------------------------------------------
# Client: MCPClientRegistry — mocked session
# ---------------------------------------------------------------------------

class TestMCPClientRegistryMocked:
    def _make_mock_tool_info(self, name: str, description: str = "A tool"):
        ti = MagicMock()
        ti.name = name
        ti.description = description
        ti.inputSchema = {"type": "object", "properties": {}}
        return ti

    def _make_mock_session(self, tool_names: list[str]):
        session = AsyncMock()
        session.initialize = AsyncMock()
        tools_response = MagicMock()
        tools_response.tools = [self._make_mock_tool_info(n) for n in tool_names]
        session.list_tools = AsyncMock(return_value=tools_response)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        return session

    @pytest.mark.asyncio
    async def test_initialise_registers_tools(self):
        from zenus_core.mcp.client import MCPClientRegistry
        from zenus_core.config.schema import MCPClientConfig, MCPExternalServer

        cfg = MCPClientConfig(
            enabled=True,
            servers=[MCPExternalServer(name="myserver", transport="stdio", command="fake-cmd")],
        )
        registry = MCPClientRegistry(cfg)

        mock_session = self._make_mock_session(["list_files", "read_file"])

        # Patch stdio_client to return a mock (read, write) pair and session
        mock_rw = (AsyncMock(), AsyncMock())
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_rw)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("zenus_core.mcp.client.stdio_client", return_value=mock_cm), \
             patch("zenus_core.mcp.client.ClientSession", return_value=mock_session):
            tools = await registry.initialise()

        assert "mcp__myserver__list_files" in tools
        assert "mcp__myserver__read_file" in tools

    @pytest.mark.asyncio
    async def test_initialise_warns_on_connection_failure(self):
        from zenus_core.mcp.client import MCPClientRegistry
        from zenus_core.config.schema import MCPClientConfig, MCPExternalServer

        cfg = MCPClientConfig(
            enabled=True,
            servers=[MCPExternalServer(name="broken", transport="stdio", command="bad-cmd")],
        )
        registry = MCPClientRegistry(cfg)

        failing_cm = AsyncMock()
        failing_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("spawn failed"))

        # Should not raise — connection failure is caught and logged as a warning
        with patch("zenus_core.mcp.client.stdio_client", return_value=failing_cm):
            tools = await registry.initialise()

        # Registry should be empty (connection failed) rather than crashing the process
        assert len(registry._tools) == 0
        assert tools == {}

    @pytest.mark.asyncio
    async def test_invoke_calls_session(self):
        from zenus_core.mcp.client import MCPRemoteTool, _make_invoker

        content_block = MagicMock()
        content_block.text = "hello from remote"
        call_result = MagicMock()
        call_result.content = [content_block]

        session = AsyncMock()
        session.call_tool = AsyncMock(return_value=call_result)

        invoker = _make_invoker(session, "remote_tool")
        result = await invoker(x="value")
        assert result == "hello from remote"
        session.call_tool.assert_called_once_with("remote_tool", arguments={"x": "value"})


# ---------------------------------------------------------------------------
# CLI router tests
# ---------------------------------------------------------------------------

class TestMCPRouter:
    def _router(self):
        from zenus_cli.router import CommandRouter
        return CommandRouter()

    def test_parse_mcp_server_default(self):
        cmd = self._router().parse(["mcp-server"])
        assert cmd.mode == "mcp_server"
        assert cmd.flags == {}

    def test_parse_mcp_server_transport_sse(self):
        cmd = self._router().parse(["mcp-server", "--transport", "sse"])
        assert cmd.mode == "mcp_server"
        assert cmd.flags["transport"] == "sse"

    def test_parse_mcp_server_transport_eq(self):
        cmd = self._router().parse(["mcp-server", "--transport=sse"])
        assert cmd.flags["transport"] == "sse"

    def test_parse_mcp_server_host_port(self):
        cmd = self._router().parse(["mcp-server", "--host", "0.0.0.0", "--port", "9000"])
        assert cmd.flags["host"] == "0.0.0.0"
        assert cmd.flags["port"] == 9000

    def test_parse_mcp_server_allow_privileged(self):
        cmd = self._router().parse(["mcp-server", "--allow-privileged"])
        assert cmd.flags.get("allow_privileged") is True

    def test_parse_mcp_server_combined_flags(self):
        cmd = self._router().parse(["mcp-server", "--transport=sse", "--port=8888", "--allow-privileged"])
        assert cmd.flags["transport"] == "sse"
        assert cmd.flags["port"] == 8888
        assert cmd.flags["allow_privileged"] is True
