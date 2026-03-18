"""
Tests for sandbox module: SandboxConstraints, SandboxExecutor, ToolSandboxWrapper
"""

import os
import time
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


# ===========================================================================
# SandboxConstraints
# ===========================================================================

class TestSandboxConstraintsInit:
    """Test SandboxConstraints initialisation and path normalisation"""

    def test_empty_constraints_have_no_read_paths(self):
        """SandboxConstraints with no read paths has empty allowed_read_paths"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc.allowed_read_paths == set()

    def test_empty_constraints_have_no_write_paths(self):
        """SandboxConstraints with no write paths has empty allowed_write_paths"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc.allowed_write_paths == set()

    def test_paths_normalised_to_absolute(self):
        """Paths are expanded and resolved to absolute form"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_write_paths={"~/tmp"})
        assert all(p.startswith("/") for p in sc.allowed_write_paths)

    def test_tilde_expanded(self):
        """Tilde (~) in paths is expanded to home directory"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        home = os.path.expanduser("~")
        sc = SandboxConstraints(allowed_write_paths={"~"})
        assert home in sc.allowed_write_paths

    def test_forbidden_paths_normalised(self):
        """Forbidden paths are also normalised"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(forbidden_paths={"/etc"})
        assert "/etc" in sc.forbidden_paths

    def test_default_max_execution_time(self):
        """Default max_execution_time is 30 seconds"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc.max_execution_time == 30

    def test_network_disabled_by_default(self):
        """Network access is disabled by default"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc.allow_network is False

    def test_subprocess_disabled_by_default(self):
        """Subprocess execution is disabled by default"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc.allow_subprocess is False


class TestSandboxConstraintsCanRead:
    """Test SandboxConstraints.can_read"""

    def test_can_read_anywhere_with_no_allow_list(self):
        """can_read returns True for any path when allowed_read_paths is empty"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc.can_read("/some/random/path") is True

    def test_cannot_read_forbidden_path(self):
        """can_read returns False for forbidden paths"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(forbidden_paths={"/etc"})
        assert sc.can_read("/etc/passwd") is False

    def test_can_read_within_allowed_path(self):
        """can_read returns True for paths under allowed_read_paths"""
        home = os.path.expanduser("~")
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_read_paths={home})
        assert sc.can_read(os.path.join(home, "file.txt")) is True

    def test_cannot_read_outside_allowed_path(self):
        """can_read returns False for paths outside allowed_read_paths"""
        home = os.path.expanduser("~")
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_read_paths={home})
        assert sc.can_read("/var/log/syslog") is False

    def test_forbidden_takes_priority_over_allowed(self):
        """Forbidden paths override allowed_read_paths"""
        home = os.path.expanduser("~")
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(
            allowed_read_paths={home},
            forbidden_paths={home}
        )
        assert sc.can_read(home) is False


class TestSandboxConstraintsCanWrite:
    """Test SandboxConstraints.can_write"""

    def test_cannot_write_without_explicit_permission(self):
        """can_write returns False when no allowed_write_paths configured"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc.can_write("/tmp/test.txt") is False

    def test_can_write_within_allowed_write_path(self):
        """can_write returns True for paths under allowed_write_paths"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_write_paths={"/tmp"})
        assert sc.can_write("/tmp/testfile.txt") is True

    def test_cannot_write_outside_allowed_write_path(self):
        """can_write returns False for paths outside allowed_write_paths"""
        home = os.path.expanduser("~")
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_write_paths={home})
        assert sc.can_write("/etc/passwd") is False

    def test_cannot_write_to_forbidden_path(self):
        """can_write returns False for forbidden paths even if in allowed_write_paths"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(
            allowed_write_paths={"/tmp"},
            forbidden_paths={"/tmp"}
        )
        assert sc.can_write("/tmp/test.txt") is False

    def test_can_write_to_home_subdirectory(self):
        """can_write returns True for paths under home when home is allowed"""
        home = os.path.expanduser("~")
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_write_paths={home})
        assert sc.can_write(os.path.join(home, "docs", "file.txt")) is True


class TestSandboxConstraintsIsUnderAny:
    """Test SandboxConstraints._is_under_any helper"""

    def test_exact_match_returns_true(self):
        """_is_under_any returns True for exact path match"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc._is_under_any("/tmp", {"/tmp"}) is True

    def test_subpath_returns_true(self):
        """_is_under_any returns True for paths under a parent"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc._is_under_any("/tmp/foo/bar", {"/tmp"}) is True

    def test_unrelated_path_returns_false(self):
        """_is_under_any returns False for unrelated paths"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc._is_under_any("/var/log", {"/tmp"}) is False

    def test_empty_parents_returns_false(self):
        """_is_under_any returns False when parent_paths is empty"""
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()
        assert sc._is_under_any("/tmp/file", set()) is False


# ===========================================================================
# Preset profiles
# ===========================================================================

class TestPresetProfiles:
    """Test constraint preset factory functions"""

    def test_get_safe_defaults_has_write_to_home_and_tmp(self):
        """get_safe_defaults allows writing to home and /tmp"""
        from zenus_core.sandbox.constraints import get_safe_defaults
        home = os.path.expanduser("~")
        sc = get_safe_defaults()
        assert sc.can_write(os.path.join(home, "file.txt"))
        assert sc.can_write("/tmp/file.txt")

    def test_get_safe_defaults_blocks_network(self):
        """get_safe_defaults disallows network"""
        from zenus_core.sandbox.constraints import get_safe_defaults
        sc = get_safe_defaults()
        assert sc.allow_network is False

    def test_get_safe_defaults_blocks_etc(self):
        """get_safe_defaults forbids /etc"""
        from zenus_core.sandbox.constraints import get_safe_defaults
        sc = get_safe_defaults()
        assert sc.can_write("/etc/passwd") is False

    def test_get_restricted_has_limited_read(self):
        """get_restricted only allows reading from home"""
        from zenus_core.sandbox.constraints import get_restricted
        home = os.path.expanduser("~")
        sc = get_restricted()
        # /var should be blocked
        assert sc.can_read("/var/log/syslog") is False
        # Home should be readable
        assert sc.can_read(os.path.join(home, "file.txt")) is True

    def test_get_restricted_max_time_ten_seconds(self):
        """get_restricted sets max_execution_time to 10 seconds"""
        from zenus_core.sandbox.constraints import get_restricted
        sc = get_restricted()
        assert sc.max_execution_time == 10

    def test_get_permissive_allows_network(self):
        """get_permissive allows network access"""
        from zenus_core.sandbox.constraints import get_permissive
        sc = get_permissive()
        assert sc.allow_network is True

    def test_get_permissive_allows_subprocess(self):
        """get_permissive allows subprocess execution"""
        from zenus_core.sandbox.constraints import get_permissive
        sc = get_permissive()
        assert sc.allow_subprocess is True

    def test_get_filesystem_only_no_network(self):
        """get_filesystem_only disallows network"""
        from zenus_core.sandbox.constraints import get_filesystem_only
        sc = get_filesystem_only()
        assert sc.allow_network is False

    def test_get_filesystem_only_no_subprocess(self):
        """get_filesystem_only disallows subprocess"""
        from zenus_core.sandbox.constraints import get_filesystem_only
        sc = get_filesystem_only()
        assert sc.allow_subprocess is False


# ===========================================================================
# SandboxExecutor
# ===========================================================================

class TestSandboxExecutorInit:
    """Test SandboxExecutor initialisation"""

    def test_uses_safe_defaults_when_no_constraints(self):
        """SandboxExecutor uses safe defaults when no constraints provided"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        executor = SandboxExecutor()
        assert isinstance(executor.constraints, SandboxConstraints)

    def test_uses_provided_constraints(self):
        """SandboxExecutor stores provided constraints"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(max_execution_time=60)
        executor = SandboxExecutor(sc)
        assert executor.constraints is sc


class TestSandboxExecutorValidatePaths:
    """Test SandboxExecutor.validate_path_access"""

    def test_read_allowed_path_no_raise(self):
        """validate_path_access does not raise for allowed read path"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints()  # no read restriction
        executor = SandboxExecutor(sc)
        # Should not raise
        executor.validate_path_access("/tmp/file.txt", is_write=False)

    def test_write_denied_raises_sandbox_violation(self):
        """validate_path_access raises SandboxViolation for disallowed write path"""
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_write_paths={"/tmp"})
        executor = SandboxExecutor(sc)
        with pytest.raises(SandboxViolation):
            executor.validate_path_access("/etc/passwd", is_write=True)

    def test_write_allowed_path_no_raise(self):
        """validate_path_access does not raise for allowed write path"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_write_paths={"/tmp"})
        executor = SandboxExecutor(sc)
        executor.validate_path_access("/tmp/output.txt", is_write=True)

    def test_read_forbidden_path_raises(self):
        """validate_path_access raises SandboxViolation for forbidden read path"""
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints
        home = os.path.expanduser("~")
        sc = SandboxConstraints(
            allowed_read_paths={home},
            forbidden_paths={"/etc"}
        )
        executor = SandboxExecutor(sc)
        with pytest.raises(SandboxViolation):
            executor.validate_path_access("/etc/shadow", is_write=False)


class TestSandboxExecutorValidateNetwork:
    """Test SandboxExecutor.validate_network_access"""

    def test_network_disabled_raises(self):
        """validate_network_access raises SandboxViolation when network not allowed"""
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allow_network=False)
        executor = SandboxExecutor(sc)
        with pytest.raises(SandboxViolation):
            executor.validate_network_access()

    def test_network_enabled_no_raise(self):
        """validate_network_access does not raise when network allowed"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allow_network=True)
        executor = SandboxExecutor(sc)
        executor.validate_network_access()

    def test_host_not_in_allowed_list_raises(self):
        """validate_network_access raises SandboxViolation for disallowed host"""
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allow_network=True, allowed_hosts={"example.com"})
        executor = SandboxExecutor(sc)
        with pytest.raises(SandboxViolation):
            executor.validate_network_access(host="evil.com")

    def test_host_in_allowed_list_no_raise(self):
        """validate_network_access does not raise for allowed host"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allow_network=True, allowed_hosts={"example.com"})
        executor = SandboxExecutor(sc)
        executor.validate_network_access(host="example.com")


class TestSandboxExecutorValidateSubprocess:
    """Test SandboxExecutor.validate_subprocess"""

    def test_subprocess_disabled_raises(self):
        """validate_subprocess raises SandboxViolation when not allowed"""
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allow_subprocess=False)
        executor = SandboxExecutor(sc)
        with pytest.raises(SandboxViolation):
            executor.validate_subprocess()

    def test_subprocess_enabled_no_raise(self):
        """validate_subprocess does not raise when subprocess is allowed"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allow_subprocess=True)
        executor = SandboxExecutor(sc)
        executor.validate_subprocess()


class TestSandboxExecutorExecute:
    """Test SandboxExecutor.execute"""

    def test_executes_function_and_returns_result(self):
        """execute() calls the function and returns its result"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(max_execution_time=None)
        executor = SandboxExecutor(sc)
        result = executor.execute(lambda: 42)
        assert result == 42

    def test_passes_args_to_function(self):
        """execute() passes positional args to the wrapped function"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(max_execution_time=None)
        executor = SandboxExecutor(sc)
        result = executor.execute(lambda x, y: x + y, 3, 4)
        assert result == 7

    def test_passes_kwargs_to_function(self):
        """execute() passes keyword args to the wrapped function"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(max_execution_time=None)
        executor = SandboxExecutor(sc)
        result = executor.execute(lambda x=0, y=0: x * y, x=3, y=4, check_paths=False)
        assert result == 12

    def test_raises_sandbox_violation_on_write_to_forbidden(self):
        """execute() raises SandboxViolation when write kwargs reference forbidden path"""
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_write_paths={"/tmp"})
        executor = SandboxExecutor(sc)
        with pytest.raises(SandboxViolation):
            executor.execute(lambda destination="/etc": None, destination="/etc/evil")

    def test_check_paths_false_skips_validation(self):
        """execute() with check_paths=False skips path validation"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(allowed_write_paths={"/tmp"})
        executor = SandboxExecutor(sc)
        # Would normally fail, but check_paths=False bypasses it
        result = executor.execute(lambda: "ok", check_paths=False)
        assert result == "ok"

    def test_function_exceptions_propagate(self):
        """execute() lets exceptions from the wrapped function propagate"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(max_execution_time=None)
        executor = SandboxExecutor(sc)
        with pytest.raises(ValueError):
            executor.execute(lambda: (_ for _ in ()).throw(ValueError("boom")))


class TestSandboxExecutorTimeout:
    """Test SandboxExecutor timeout behaviour"""

    def test_timeout_raises_sandbox_timeout(self):
        """execute() raises SandboxTimeout when operation exceeds limit"""
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxTimeout
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(max_execution_time=1)
        executor = SandboxExecutor(sc)

        def slow():
            time.sleep(5)

        with pytest.raises(SandboxTimeout):
            executor.execute(slow, check_paths=False)

    def test_fast_operation_no_timeout(self):
        """execute() completes without timeout for fast operations"""
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints
        sc = SandboxConstraints(max_execution_time=5)
        executor = SandboxExecutor(sc)
        result = executor.execute(lambda: "fast", check_paths=False)
        assert result == "fast"


class TestSandboxViolationHierarchy:
    """Test SandboxViolation exception hierarchy"""

    def test_sandbox_violation_is_exception(self):
        """SandboxViolation is a subclass of Exception"""
        from zenus_core.sandbox.executor import SandboxViolation
        with pytest.raises(SandboxViolation):
            raise SandboxViolation("test")

    def test_sandbox_timeout_is_sandbox_violation(self):
        """SandboxTimeout is a subclass of SandboxViolation"""
        from zenus_core.sandbox.executor import SandboxTimeout, SandboxViolation
        with pytest.raises(SandboxViolation):
            raise SandboxTimeout("timed out")


class TestSandboxedToolBase:
    """Test SandboxedToolBase mixin"""

    def test_execute_safe_calls_method(self):
        """execute_safe calls the provided method and returns result"""
        from zenus_core.sandbox.executor import SandboxedToolBase
        from zenus_core.sandbox.constraints import SandboxConstraints

        class MyTool(SandboxedToolBase):
            def my_method(self, x):
                return x * 2

        sc = SandboxConstraints(max_execution_time=None)
        tool = MyTool(sc)
        result = tool.execute_safe(tool.my_method, 5)
        assert result == 10

    def test_execute_safe_has_sandbox_attribute(self):
        """SandboxedToolBase has a sandbox attribute of type SandboxExecutor"""
        from zenus_core.sandbox.executor import SandboxedToolBase, SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints

        class MyTool(SandboxedToolBase):
            pass

        tool = MyTool()
        assert isinstance(tool.sandbox, SandboxExecutor)


# ===========================================================================
# ToolSandboxWrapper
# ===========================================================================

class TestToolSandboxWrapperInit:
    """Test ToolSandboxWrapper initialisation"""

    def test_stores_tool_and_sandbox(self):
        """ToolSandboxWrapper stores tool and sandbox on init"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxWrapper
        from zenus_core.sandbox.executor import SandboxExecutor

        mock_tool = Mock()
        mock_sandbox = Mock(spec=SandboxExecutor)
        wrapper = ToolSandboxWrapper(mock_tool, mock_sandbox)
        assert wrapper.tool is mock_tool
        assert wrapper.sandbox is mock_sandbox


class TestToolSandboxWrapperExecute:
    """Test ToolSandboxWrapper.execute"""

    def _make_step(self, tool="FileOps", action="scan", args=None):
        """Build a mock Step."""
        from zenus_core.brain.llm.schemas import Step
        return Step(tool=tool, action=action, args=args or {"path": "/tmp"}, risk=0)

    def test_execute_calls_tool_action(self):
        """execute() calls the corresponding action method on the tool"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxWrapper
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints

        mock_tool = Mock()
        mock_tool.scan.return_value = "files listed"
        sc = SandboxConstraints(max_execution_time=None)
        executor = SandboxExecutor(sc)
        wrapper = ToolSandboxWrapper(mock_tool, executor)

        step = self._make_step(action="scan", args={"path": "/tmp"})
        result = wrapper.execute(step)
        assert result == "files listed"
        mock_tool.scan.assert_called_once_with(path="/tmp")

    def test_execute_raises_sandbox_violation_for_forbidden_write(self):
        """execute() raises SandboxViolation when step writes to forbidden path"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxWrapper
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints

        mock_tool = Mock()
        sc = SandboxConstraints(allowed_write_paths={"/tmp"})
        executor = SandboxExecutor(sc)
        wrapper = ToolSandboxWrapper(mock_tool, executor)

        step = self._make_step(action="write_file", args={"path": "/etc/evil.txt"})
        with pytest.raises(SandboxViolation):
            wrapper.execute(step)

    def test_execute_wraps_permission_denied_as_sandbox_violation(self):
        """Permission denied exception from tool is re-raised as SandboxViolation"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxWrapper
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints

        mock_tool = Mock()
        mock_tool.scan.side_effect = PermissionError("Permission denied: /root")
        sc = SandboxConstraints(max_execution_time=None)
        executor = SandboxExecutor(sc)
        wrapper = ToolSandboxWrapper(mock_tool, executor)

        step = self._make_step(action="scan", args={"path": "/tmp"})
        with pytest.raises(SandboxViolation):
            wrapper.execute(step)

    def test_execute_propagates_other_exceptions(self):
        """Non-permission exceptions from the tool propagate unchanged"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxWrapper
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints

        mock_tool = Mock()
        mock_tool.scan.side_effect = RuntimeError("unexpected failure")
        sc = SandboxConstraints(max_execution_time=None)
        executor = SandboxExecutor(sc)
        wrapper = ToolSandboxWrapper(mock_tool, executor)

        step = self._make_step(action="scan", args={"path": "/tmp"})
        with pytest.raises(RuntimeError):
            wrapper.execute(step)


class TestToolSandboxWrapperValidateStepPaths:
    """Test ToolSandboxWrapper._validate_step_paths"""

    def _make_step(self, action="scan", args=None):
        """Build a mock Step."""
        from zenus_core.brain.llm.schemas import Step
        return Step(tool="FileOps", action=action, args=args or {}, risk=0)

    def test_write_action_checks_write_permission(self):
        """Write actions trigger write permission check"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxWrapper
        from zenus_core.sandbox.executor import SandboxExecutor, SandboxViolation
        from zenus_core.sandbox.constraints import SandboxConstraints

        mock_tool = Mock()
        sc = SandboxConstraints(allowed_write_paths={"/tmp"})
        executor = SandboxExecutor(sc)
        wrapper = ToolSandboxWrapper(mock_tool, executor)

        step = self._make_step(action="mkdir", args={"path": "/etc/new_dir"})
        with pytest.raises(SandboxViolation):
            wrapper._validate_step_paths(step)

    def test_read_action_with_safe_path_no_raise(self):
        """Read action with safe path does not raise"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxWrapper
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints

        mock_tool = Mock()
        sc = SandboxConstraints()  # no read restriction
        executor = SandboxExecutor(sc)
        wrapper = ToolSandboxWrapper(mock_tool, executor)

        step = self._make_step(action="scan", args={"path": "/tmp"})
        wrapper._validate_step_paths(step)  # should not raise

    def test_step_with_no_path_args_no_raise(self):
        """Step with no recognised path arguments does not raise"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxWrapper
        from zenus_core.sandbox.executor import SandboxExecutor
        from zenus_core.sandbox.constraints import SandboxConstraints

        mock_tool = Mock()
        sc = SandboxConstraints()
        executor = SandboxExecutor(sc)
        wrapper = ToolSandboxWrapper(mock_tool, executor)

        step = self._make_step(action="scan", args={"query": "text search"})
        wrapper._validate_step_paths(step)  # should not raise


# ===========================================================================
# ToolSandboxRegistry
# ===========================================================================

class TestToolSandboxRegistry:
    """Test ToolSandboxRegistry"""

    def _make_tools(self):
        """Return a minimal dict of mock tools."""
        return {"FileOps": Mock(), "ShellOps": Mock()}

    def test_registry_wraps_all_tools(self):
        """ToolSandboxRegistry wraps every tool in ToolSandboxWrapper"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxRegistry, ToolSandboxWrapper

        tools = self._make_tools()
        registry = ToolSandboxRegistry(tools)
        for name in tools:
            wrapped = registry.get(name)
            assert isinstance(wrapped, ToolSandboxWrapper)

    def test_registry_get_returns_none_for_unknown(self):
        """ToolSandboxRegistry.get returns None for unknown tool name"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxRegistry

        registry = ToolSandboxRegistry(self._make_tools())
        assert registry.get("NonExistentTool") is None

    def test_registry_keys_returns_all_tool_names(self):
        """ToolSandboxRegistry.keys() returns all registered tool names"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxRegistry

        tools = self._make_tools()
        registry = ToolSandboxRegistry(tools)
        assert set(registry.keys()) == set(tools.keys())

    def test_registry_uses_provided_constraints(self):
        """ToolSandboxRegistry uses provided constraints for sandbox"""
        from zenus_core.sandbox.tool_wrapper import ToolSandboxRegistry
        from zenus_core.sandbox.constraints import SandboxConstraints

        tools = self._make_tools()
        sc = SandboxConstraints(allow_network=True)
        registry = ToolSandboxRegistry(tools, constraints=sc)
        assert registry.sandbox.constraints.allow_network is True
