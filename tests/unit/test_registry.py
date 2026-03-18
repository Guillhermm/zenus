"""
Tests for the tool registry: describe() and describe_compact()
"""

import pytest
from unittest.mock import patch

from zenus_core.tools.registry import TOOLS, describe, describe_compact
from zenus_core.tools.privilege import PRIVILEGED_TOOLS


class TestToolsDict:
    """Tests for the TOOLS registry dictionary"""

    def test_tools_is_not_empty(self):
        """TOOLS must contain at least one entry"""
        assert len(TOOLS) > 0

    def test_shell_ops_registered(self):
        """ShellOps is present in the registry"""
        assert "ShellOps" in TOOLS

    def test_code_exec_registered(self):
        """CodeExec is present in the registry"""
        assert "CodeExec" in TOOLS

    def test_file_ops_registered(self):
        """FileOps is present in the registry"""
        assert "FileOps" in TOOLS

    def test_network_ops_registered(self):
        """NetworkOps is present in the registry"""
        assert "NetworkOps" in TOOLS

    def test_process_ops_registered(self):
        """ProcessOps is present in the registry"""
        assert "ProcessOps" in TOOLS

    def test_package_ops_registered(self):
        """PackageOps is present in the registry"""
        assert "PackageOps" in TOOLS

    def test_all_values_are_tool_instances(self):
        """Every registry value is a non-None object with callable methods"""
        for name, instance in TOOLS.items():
            assert instance is not None, f"{name} has None instance"
            assert isinstance(instance, object), f"{name} is not an object"

    def test_lookup_by_name(self):
        """Tools can be retrieved by string key"""
        shell = TOOLS["ShellOps"]
        assert shell is not None

    def test_missing_tool_raises_key_error(self):
        """Looking up an unregistered tool raises KeyError"""
        with pytest.raises(KeyError):
            _ = TOOLS["NonExistentTool"]


class TestDescribe:
    """Tests for describe() registry introspection"""

    def setup_method(self):
        """Compute describe() once per test class"""
        self.registry = describe()

    def test_returns_dict(self):
        """describe() returns a dictionary"""
        assert isinstance(self.registry, dict)

    def test_contains_known_tools(self):
        """describe() includes known tools"""
        assert "ShellOps" in self.registry
        assert "CodeExec" in self.registry
        assert "FileOps" in self.registry

    def test_each_entry_has_doc(self):
        """Every tool entry has a 'doc' key"""
        for name, info in self.registry.items():
            assert "doc" in info, f"{name} missing 'doc'"

    def test_each_entry_has_privileged_flag(self):
        """Every tool entry has a boolean 'privileged' key"""
        for name, info in self.registry.items():
            assert "privileged" in info, f"{name} missing 'privileged'"
            assert isinstance(info["privileged"], bool)

    def test_each_entry_has_actions_list(self):
        """Every tool entry has an 'actions' list"""
        for name, info in self.registry.items():
            assert "actions" in info, f"{name} missing 'actions'"
            assert isinstance(info["actions"], list)

    def test_shell_ops_marked_privileged(self):
        """ShellOps is flagged as privileged in describe()"""
        assert self.registry["ShellOps"]["privileged"] is True

    def test_code_exec_marked_privileged(self):
        """CodeExec is flagged as privileged in describe()"""
        assert self.registry["CodeExec"]["privileged"] is True

    def test_file_ops_not_privileged(self):
        """FileOps is not flagged as privileged"""
        assert self.registry["FileOps"]["privileged"] is False

    def test_actions_have_name_doc_params(self):
        """Each action entry contains name, doc, and params keys"""
        for tool_name, info in self.registry.items():
            for action in info["actions"]:
                assert "name" in action, f"{tool_name} action missing 'name'"
                assert "doc" in action, f"{tool_name} action missing 'doc'"
                assert "params" in action, f"{tool_name} action missing 'params'"

    def test_shell_ops_has_run_action(self):
        """ShellOps expose a 'run' action"""
        actions = {a["name"] for a in self.registry["ShellOps"]["actions"]}
        assert "run" in actions

    def test_code_exec_has_python_action(self):
        """CodeExec exposes a 'python' action"""
        actions = {a["name"] for a in self.registry["CodeExec"]["actions"]}
        assert "python" in actions

    def test_code_exec_has_bash_script_action(self):
        """CodeExec exposes a 'bash_script' action"""
        actions = {a["name"] for a in self.registry["CodeExec"]["actions"]}
        assert "bash_script" in actions

    def test_private_methods_excluded(self):
        """Actions starting with _ are not exposed"""
        for tool_name, info in self.registry.items():
            for action in info["actions"]:
                assert not action["name"].startswith("_"), (
                    f"{tool_name} exposes private method {action['name']!r}"
                )

    def test_dry_run_excluded(self):
        """dry_run is not included in actions"""
        for tool_name, info in self.registry.items():
            action_names = {a["name"] for a in info["actions"]}
            assert "dry_run" not in action_names, (
                f"{tool_name} should not expose dry_run as an action"
            )

    def test_execute_excluded(self):
        """execute is not included in actions"""
        for tool_name, info in self.registry.items():
            action_names = {a["name"] for a in info["actions"]}
            assert "execute" not in action_names, (
                f"{tool_name} should not expose execute as an action"
            )

    def test_privileged_flag_consistent_with_privileged_tools(self):
        """privileged flag in describe() matches PRIVILEGED_TOOLS set"""
        for tool_name, info in self.registry.items():
            expected = tool_name in PRIVILEGED_TOOLS
            assert info["privileged"] == expected, (
                f"{tool_name}: describe() privileged={info['privileged']}, "
                f"but PRIVILEGED_TOOLS says {expected}"
            )


class TestDescribeCompact:
    """Tests for describe_compact() text summary"""

    def setup_method(self):
        """Compute describe_compact() once per test class"""
        self.text = describe_compact()

    def test_returns_string(self):
        """describe_compact() returns a string"""
        assert isinstance(self.text, str)

    def test_not_empty(self):
        """describe_compact() result is not empty"""
        assert len(self.text) > 0

    def test_contains_tool_names(self):
        """Known tool names appear in the compact description"""
        assert "ShellOps" in self.text
        assert "CodeExec" in self.text
        assert "FileOps" in self.text

    def test_privileged_tools_tagged(self):
        """Privileged tools are annotated with [privileged]"""
        assert "[privileged]" in self.text

    def test_shell_ops_line_has_privileged_tag(self):
        """ShellOps line contains [privileged]"""
        for line in self.text.splitlines():
            if line.startswith("ShellOps"):
                assert "[privileged]" in line
                break
        else:
            pytest.fail("ShellOps line not found in compact description")

    def test_non_privileged_tool_has_no_privileged_tag(self):
        """FileOps line does not contain [privileged]"""
        for line in self.text.splitlines():
            if line.startswith("FileOps"):
                assert "[privileged]" not in line
                break
        else:
            pytest.fail("FileOps line not found in compact description")

    def test_actions_indented_with_dash(self):
        """Action lines start with '  -'"""
        action_lines = [l for l in self.text.splitlines() if l.startswith("  -")]
        assert len(action_lines) > 0

    def test_action_lines_contain_em_dash(self):
        """Action lines contain the — doc separator"""
        action_lines = [l for l in self.text.splitlines() if l.startswith("  -")]
        for line in action_lines:
            assert "—" in line
