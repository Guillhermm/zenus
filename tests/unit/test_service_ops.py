"""
Unit tests for ServiceOps tool (systemctl and journalctl fully mocked)
"""

import pytest
from unittest.mock import Mock, patch

from zenus_core.tools.service_ops import ServiceOps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(stdout="", stderr="", returncode=0):
    """Build a fake subprocess.CompletedProcess"""
    return Mock(stdout=stdout, stderr=stderr, returncode=returncode)


# ---------------------------------------------------------------------------
# _run_systemctl internal helper
# ---------------------------------------------------------------------------

class TestRunSystemctl:
    """Tests for ServiceOps._run_systemctl internal helper"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_returns_combined_stdout_stderr(self, mock_run):
        """Output is stdout + stderr combined"""
        mock_run.return_value = _make_proc(stdout="active\n", stderr="warning\n")
        result = self.tool._run_systemctl(["status", "nginx"])
        assert "active" in result
        assert "warning" in result

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_sudo_prepended_when_requested(self, mock_run):
        """sudo is prepended when sudo=True"""
        mock_run.return_value = _make_proc()
        self.tool._run_systemctl(["start", "nginx"], sudo=True)
        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"
        assert "systemctl" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_no_sudo_by_default(self, mock_run):
        """sudo is not prepended when sudo=False"""
        mock_run.return_value = _make_proc()
        self.tool._run_systemctl(["status", "nginx"], sudo=False)
        args = mock_run.call_args[0][0]
        assert args[0] == "systemctl"

    @patch("zenus_core.tools.service_ops.subprocess.run", side_effect=Exception("binary not found"))
    def test_exception_returns_error_string(self, mock_run):
        """Exceptions are caught and returned as 'Error: ...'"""
        result = self.tool._run_systemctl(["status", "nginx"])
        assert result.startswith("Error:")
        assert "binary not found" in result

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_systemctl_is_in_command(self, mock_run):
        """'systemctl' is always in the command"""
        mock_run.return_value = _make_proc()
        self.tool._run_systemctl(["is-active", "nginx"])
        args = mock_run.call_args[0][0]
        assert "systemctl" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_timeout_is_30(self, mock_run):
        """Timeout is set to 30 seconds"""
        mock_run.return_value = _make_proc()
        self.tool._run_systemctl(["status", "nginx"])
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 30


# ---------------------------------------------------------------------------
# Individual service actions
# ---------------------------------------------------------------------------

class TestServiceStart:
    """Tests for ServiceOps.start"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_start_calls_systemctl_start(self, mock_run):
        """start calls 'systemctl start <service>'"""
        mock_run.return_value = _make_proc()
        self.tool.start("nginx")
        args = mock_run.call_args[0][0]
        assert "start" in args
        assert "nginx" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_start_uses_sudo(self, mock_run):
        """start uses sudo"""
        mock_run.return_value = _make_proc()
        self.tool.start("nginx")
        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"

    @patch("zenus_core.tools.service_ops.subprocess.run", side_effect=Exception("no binary"))
    def test_start_exception_returns_error(self, mock_run):
        """Exception during start returns error string"""
        result = self.tool.start("nginx")
        assert result.startswith("Error:")


class TestServiceStop:
    """Tests for ServiceOps.stop"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_stop_calls_systemctl_stop(self, mock_run):
        """stop calls 'systemctl stop <service>'"""
        mock_run.return_value = _make_proc()
        self.tool.stop("nginx")
        args = mock_run.call_args[0][0]
        assert "stop" in args
        assert "nginx" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_stop_uses_sudo(self, mock_run):
        """stop uses sudo"""
        mock_run.return_value = _make_proc()
        self.tool.stop("nginx")
        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"


class TestServiceRestart:
    """Tests for ServiceOps.restart"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_restart_calls_systemctl_restart(self, mock_run):
        """restart calls 'systemctl restart <service>'"""
        mock_run.return_value = _make_proc()
        self.tool.restart("nginx")
        args = mock_run.call_args[0][0]
        assert "restart" in args
        assert "nginx" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_restart_uses_sudo(self, mock_run):
        """restart uses sudo"""
        mock_run.return_value = _make_proc()
        self.tool.restart("postgresql")
        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"


class TestServiceStatus:
    """Tests for ServiceOps.status"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_status_calls_systemctl_status(self, mock_run):
        """status calls 'systemctl status <service>'"""
        mock_run.return_value = _make_proc(stdout="● nginx.service - active")
        result = self.tool.status("nginx")
        args = mock_run.call_args[0][0]
        assert "status" in args
        assert "nginx" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_status_does_not_use_sudo(self, mock_run):
        """status does not require sudo"""
        mock_run.return_value = _make_proc()
        self.tool.status("nginx")
        args = mock_run.call_args[0][0]
        assert args[0] != "sudo"
        assert args[0] == "systemctl"

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_status_returns_output(self, mock_run):
        """status returns the combined output"""
        mock_run.return_value = _make_proc(stdout="● nginx.service\n   Active: active\n")
        result = self.tool.status("nginx")
        assert "nginx.service" in result or "active" in result


class TestServiceEnable:
    """Tests for ServiceOps.enable"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_enable_calls_systemctl_enable(self, mock_run):
        """enable calls 'systemctl enable <service>'"""
        mock_run.return_value = _make_proc()
        self.tool.enable("nginx")
        args = mock_run.call_args[0][0]
        assert "enable" in args
        assert "nginx" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_enable_uses_sudo(self, mock_run):
        """enable uses sudo"""
        mock_run.return_value = _make_proc()
        self.tool.enable("nginx")
        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"


class TestServiceDisable:
    """Tests for ServiceOps.disable"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_disable_calls_systemctl_disable(self, mock_run):
        """disable calls 'systemctl disable <service>'"""
        mock_run.return_value = _make_proc()
        self.tool.disable("nginx")
        args = mock_run.call_args[0][0]
        assert "disable" in args
        assert "nginx" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_disable_uses_sudo(self, mock_run):
        """disable uses sudo"""
        mock_run.return_value = _make_proc()
        self.tool.disable("nginx")
        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"


# ---------------------------------------------------------------------------
# list_services
# ---------------------------------------------------------------------------

class TestServiceListServices:
    """Tests for ServiceOps.list_services"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_list_includes_type_service(self, mock_run):
        """list_services always filters by --type=service"""
        mock_run.return_value = _make_proc(stdout="UNIT   LOAD   ACTIVE\n")
        self.tool.list_services()
        args = mock_run.call_args[0][0]
        assert "--type=service" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_list_no_state_no_filter(self, mock_run):
        """list_services without state filter omits --state flag"""
        mock_run.return_value = _make_proc(stdout="")
        self.tool.list_services()
        args = mock_run.call_args[0][0]
        assert not any(a.startswith("--state=") for a in args)

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_list_with_state_filter(self, mock_run):
        """list_services with state passes --state=<value>"""
        mock_run.return_value = _make_proc(stdout="")
        self.tool.list_services(state="failed")
        args = mock_run.call_args[0][0]
        assert "--state=failed" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_list_does_not_use_sudo(self, mock_run):
        """list_services does not require sudo"""
        mock_run.return_value = _make_proc()
        self.tool.list_services()
        args = mock_run.call_args[0][0]
        assert args[0] == "systemctl"

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_list_active_state(self, mock_run):
        """list_services with state='active' passes correct filter"""
        mock_run.return_value = _make_proc(stdout="nginx.service loaded active running")
        result = self.tool.list_services(state="active")
        args = mock_run.call_args[0][0]
        assert "--state=active" in args


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------

class TestServiceLogs:
    """Tests for ServiceOps.logs"""

    def setup_method(self):
        self.tool = ServiceOps()

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_logs_calls_journalctl(self, mock_run):
        """logs calls journalctl with -u <service>"""
        mock_run.return_value = _make_proc(stdout="Mar 18 12:00:01 nginx[1234]: started")
        result = self.tool.logs("nginx")
        args = mock_run.call_args[0][0]
        assert "journalctl" in args
        assert "-u" in args
        assert "nginx" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_logs_default_50_lines(self, mock_run):
        """logs defaults to 50 lines"""
        mock_run.return_value = _make_proc(stdout="")
        self.tool.logs("nginx")
        args = mock_run.call_args[0][0]
        assert "-n" in args
        n_idx = args.index("-n")
        assert args[n_idx + 1] == "50"

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_logs_custom_lines(self, mock_run):
        """logs with custom lines passes the correct -n value"""
        mock_run.return_value = _make_proc(stdout="")
        self.tool.logs("nginx", lines=100)
        args = mock_run.call_args[0][0]
        assert "-n" in args
        n_idx = args.index("-n")
        assert args[n_idx + 1] == "100"

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_logs_uses_no_pager(self, mock_run):
        """logs uses --no-pager flag"""
        mock_run.return_value = _make_proc(stdout="")
        self.tool.logs("nginx")
        args = mock_run.call_args[0][0]
        assert "--no-pager" in args

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_logs_returns_stdout(self, mock_run):
        """logs returns journalctl stdout"""
        mock_run.return_value = _make_proc(stdout="log line 1\nlog line 2\n")
        result = self.tool.logs("nginx")
        assert "log line 1" in result
        assert "log line 2" in result

    @patch("zenus_core.tools.service_ops.subprocess.run", side_effect=Exception("journalctl not found"))
    def test_logs_exception_returns_error(self, mock_run):
        """Exception during logs returns 'Error: ...'"""
        result = self.tool.logs("nginx")
        assert result.startswith("Error:")
        assert "journalctl not found" in result

    @patch("zenus_core.tools.service_ops.subprocess.run")
    def test_logs_timeout_is_10(self, mock_run):
        """journalctl timeout is set to 10 seconds"""
        mock_run.return_value = _make_proc(stdout="")
        self.tool.logs("nginx")
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 10
