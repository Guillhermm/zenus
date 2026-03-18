"""
Tests for privilege tier system
"""

import pytest

from zenus_core.tools.privilege import PrivilegeTier, PRIVILEGED_TOOLS, check_privilege


class TestPrivilegeTierValues:
    """Tests for PrivilegeTier enum values"""

    def test_restricted_value(self):
        """RESTRICTED tier has the correct string value"""
        assert PrivilegeTier.RESTRICTED.value == "restricted"

    def test_standard_value(self):
        """STANDARD tier has the correct string value"""
        assert PrivilegeTier.STANDARD.value == "standard"

    def test_privileged_value(self):
        """PRIVILEGED tier has the correct string value"""
        assert PrivilegeTier.PRIVILEGED.value == "privileged"

    def test_tier_is_str_subclass(self):
        """PrivilegeTier values compare equal to plain strings"""
        assert PrivilegeTier.STANDARD == "standard"
        assert PrivilegeTier.PRIVILEGED == "privileged"
        assert PrivilegeTier.RESTRICTED == "restricted"

    def test_all_three_tiers_exist(self):
        """Exactly three tiers are defined"""
        assert len(PrivilegeTier) == 3


class TestPrivilegedToolsSet:
    """Tests for the PRIVILEGED_TOOLS constant"""

    def test_shell_ops_is_privileged(self):
        """ShellOps requires PRIVILEGED tier"""
        assert "ShellOps" in PRIVILEGED_TOOLS

    def test_code_exec_is_privileged(self):
        """CodeExec requires PRIVILEGED tier"""
        assert "CodeExec" in PRIVILEGED_TOOLS

    def test_file_ops_is_not_privileged(self):
        """FileOps does not require PRIVILEGED tier"""
        assert "FileOps" not in PRIVILEGED_TOOLS

    def test_system_ops_is_not_privileged(self):
        """SystemOps does not require PRIVILEGED tier"""
        assert "SystemOps" not in PRIVILEGED_TOOLS


class TestCheckPrivilege:
    """Tests for check_privilege enforcement logic"""

    # --- Privileged tools allowed at PRIVILEGED tier ---

    def test_shell_ops_allowed_at_privileged(self):
        """ShellOps is allowed when tier is PRIVILEGED"""
        check_privilege("ShellOps", PrivilegeTier.PRIVILEGED)  # must not raise

    def test_code_exec_allowed_at_privileged(self):
        """CodeExec is allowed when tier is PRIVILEGED"""
        check_privilege("CodeExec", PrivilegeTier.PRIVILEGED)  # must not raise

    # --- Privileged tools blocked at lower tiers ---

    def test_shell_ops_blocked_at_standard(self):
        """ShellOps raises PermissionError at STANDARD tier"""
        with pytest.raises(PermissionError, match="PRIVILEGED"):
            check_privilege("ShellOps", PrivilegeTier.STANDARD)

    def test_code_exec_blocked_at_standard(self):
        """CodeExec raises PermissionError at STANDARD tier"""
        with pytest.raises(PermissionError, match="PRIVILEGED"):
            check_privilege("CodeExec", PrivilegeTier.STANDARD)

    def test_shell_ops_blocked_at_restricted(self):
        """ShellOps raises PermissionError at RESTRICTED tier"""
        with pytest.raises(PermissionError):
            check_privilege("ShellOps", PrivilegeTier.RESTRICTED)

    def test_code_exec_blocked_at_restricted(self):
        """CodeExec raises PermissionError at RESTRICTED tier"""
        with pytest.raises(PermissionError):
            check_privilege("CodeExec", PrivilegeTier.RESTRICTED)

    # --- Non-privileged tools allowed at all tiers ---

    def test_file_ops_allowed_at_standard(self):
        """FileOps is allowed at STANDARD tier"""
        check_privilege("FileOps", PrivilegeTier.STANDARD)  # must not raise

    def test_file_ops_allowed_at_restricted(self):
        """FileOps is allowed at RESTRICTED tier"""
        check_privilege("FileOps", PrivilegeTier.RESTRICTED)  # must not raise

    def test_network_ops_allowed_at_standard(self):
        """NetworkOps is allowed at STANDARD tier"""
        check_privilege("NetworkOps", PrivilegeTier.STANDARD)  # must not raise

    def test_unknown_tool_allowed_at_restricted(self):
        """An unknown tool name does not trigger a privilege error"""
        check_privilege("SomeFutureTool", PrivilegeTier.RESTRICTED)  # must not raise

    # --- Error message content ---

    def test_error_mentions_current_tier(self):
        """PermissionError message includes the current tier value"""
        with pytest.raises(PermissionError, match="standard"):
            check_privilege("ShellOps", PrivilegeTier.STANDARD)

    def test_error_mentions_tool_name(self):
        """PermissionError message includes the tool name"""
        with pytest.raises(PermissionError, match="ShellOps"):
            check_privilege("ShellOps", PrivilegeTier.STANDARD)
