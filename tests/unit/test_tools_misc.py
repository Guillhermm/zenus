"""
Tests for NetworkOps, ProcessOps, and PackageOps tools
"""

import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock, call

from zenus_core.tools.network_ops import NetworkOps
from zenus_core.tools.process_ops import ProcessOps
from zenus_core.tools.package_ops import PackageOps


# ===========================================================================
# NetworkOps
# ===========================================================================

class TestNetworkOpsCurl:
    """Tests for NetworkOps.curl"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = NetworkOps()

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_curl_get_returns_stdout(self, mock_run):
        """GET request returns response body"""
        mock_run.return_value = Mock(stdout='{"ok": true}', stderr="", returncode=0)
        result = self.tool.curl("https://example.com")
        assert '{"ok": true}' in result

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_curl_uses_silent_mode_without_output(self, mock_run):
        """curl uses -s (silent) when no output file is specified"""
        mock_run.return_value = Mock(stdout="body", stderr="", returncode=0)
        self.tool.curl("https://example.com")
        args = mock_run.call_args[0][0]
        assert "-s" in args

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_curl_post_with_data(self, mock_run):
        """POST request includes -d flag with body data"""
        mock_run.return_value = Mock(stdout="created", stderr="", returncode=0)
        self.tool.curl("https://example.com", method="POST", data='{"x":1}')
        args = mock_run.call_args[0][0]
        assert "-d" in args
        assert '{"x":1}' in args

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_curl_with_headers(self, mock_run):
        """Custom headers are passed with -H flag"""
        mock_run.return_value = Mock(stdout="ok", stderr="", returncode=0)
        self.tool.curl("https://example.com", headers={"Authorization": "Bearer token"})
        args = mock_run.call_args[0][0]
        assert "-H" in args
        assert any("Authorization: Bearer token" in a for a in args)

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_curl_with_output_file_returns_saved_message(self, mock_run):
        """curl with output path returns 'Saved to ...' message"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)
        result = self.tool.curl("https://example.com", output="/tmp/out.html")
        assert "Saved to" in result

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_curl_exception_returns_error_string(self, mock_run):
        """Network exception returns an 'Error: ...' string"""
        mock_run.side_effect = Exception("connection refused")
        result = self.tool.curl("https://bad-host.invalid")
        assert result.startswith("Error:")

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_curl_uses_x_flag_for_method(self, mock_run):
        """HTTP method is passed via -X flag"""
        mock_run.return_value = Mock(stdout="deleted", stderr="", returncode=0)
        self.tool.curl("https://example.com", method="DELETE")
        args = mock_run.call_args[0][0]
        assert "-X" in args
        assert "DELETE" in args


class TestNetworkOpsWget:
    """Tests for NetworkOps.wget"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = NetworkOps()

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_wget_returns_output(self, mock_run):
        """wget returns combined stdout+stderr"""
        mock_run.return_value = Mock(stdout="Saving to: file\n", stderr="100%\n", returncode=0)
        result = self.tool.wget("https://example.com/file.tar.gz")
        assert "Saving" in result or "100%" in result

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_wget_with_output_file(self, mock_run):
        """wget passes -O flag when output path is specified"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)
        self.tool.wget("https://example.com/file", output="/tmp/file")
        args = mock_run.call_args[0][0]
        assert "-O" in args

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_wget_exception_returns_error_string(self, mock_run):
        """Network exception returns an 'Error: ...' string"""
        mock_run.side_effect = Exception("no such host")
        result = self.tool.wget("https://bad.invalid")
        assert result.startswith("Error:")


class TestNetworkOpsPing:
    """Tests for NetworkOps.ping"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = NetworkOps()

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_ping_returns_stdout(self, mock_run):
        """ping output is returned as-is"""
        mock_run.return_value = Mock(stdout="4 packets transmitted\n", stderr="", returncode=0)
        result = self.tool.ping("localhost")
        assert "4 packets" in result

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_ping_default_count_4(self, mock_run):
        """Default ping count is 4"""
        mock_run.return_value = Mock(stdout="ok", stderr="", returncode=0)
        self.tool.ping("localhost")
        args = mock_run.call_args[0][0]
        assert "-c" in args
        assert "4" in args

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_ping_custom_count(self, mock_run):
        """Custom count is forwarded"""
        mock_run.return_value = Mock(stdout="ok", stderr="", returncode=0)
        self.tool.ping("localhost", count=10)
        args = mock_run.call_args[0][0]
        assert "10" in args

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_ping_exception_returns_error_string(self, mock_run):
        """Exception returns an 'Error: ...' string"""
        mock_run.side_effect = Exception("unreachable")
        result = self.tool.ping("10.255.255.255")
        assert result.startswith("Error:")


class TestNetworkOpsTraceroute:
    """Tests for NetworkOps.traceroute"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = NetworkOps()

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_traceroute_returns_stdout(self, mock_run):
        """traceroute output is returned"""
        mock_run.return_value = Mock(stdout="1  192.168.1.1\n", stderr="", returncode=0)
        result = self.tool.traceroute("example.com")
        assert "192.168.1.1" in result

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_traceroute_falls_back_to_tracepath(self, mock_run):
        """Falls back to tracepath when traceroute fails"""
        fail = Mock(stdout="", stderr="", returncode=1)
        success = Mock(stdout="tracepath output\n", stderr="", returncode=0)
        mock_run.side_effect = [fail, success]
        result = self.tool.traceroute("example.com")
        assert mock_run.call_count == 2

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_traceroute_exception_returns_error_string(self, mock_run):
        """Exception returns an 'Error: ...' string"""
        mock_run.side_effect = Exception("no traceroute")
        result = self.tool.traceroute("example.com")
        assert result.startswith("Error:")


class TestNetworkOpsSsh:
    """Tests for NetworkOps.ssh"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = NetworkOps()

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_ssh_with_command_returns_stdout(self, mock_run):
        """SSH with a command returns remote stdout"""
        mock_run.return_value = Mock(stdout="remote output\n", stderr="", returncode=0)
        result = self.tool.ssh("host.example.com", command="uptime")
        assert "remote output" in result

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_ssh_with_user(self, mock_run):
        """user@host format is used when user is provided"""
        mock_run.return_value = Mock(stdout="ok\n", stderr="", returncode=0)
        self.tool.ssh("host.example.com", command="id", user="admin")
        args = mock_run.call_args[0][0]
        assert "admin@host.example.com" in args

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_ssh_custom_port(self, mock_run):
        """Custom port is passed via -p flag"""
        mock_run.return_value = Mock(stdout="ok\n", stderr="", returncode=0)
        self.tool.ssh("host.example.com", command="id", port=2222)
        args = mock_run.call_args[0][0]
        assert "-p" in args
        assert "2222" in args

    def test_ssh_without_command_returns_error(self):
        """Interactive SSH (no command) returns an error string"""
        result = self.tool.ssh("host.example.com")
        assert "Error" in result or "not supported" in result

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_ssh_exception_returns_error_string(self, mock_run):
        """Exception returns an 'Error: ...' string"""
        mock_run.side_effect = Exception("connection refused")
        result = self.tool.ssh("host.example.com", command="id")
        assert result.startswith("Error:")


class TestNetworkOpsNetstat:
    """Tests for NetworkOps.netstat"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = NetworkOps()

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_netstat_returns_stdout(self, mock_run):
        """netstat returns connection table"""
        mock_run.return_value = Mock(stdout="Netid  State\n", stderr="", returncode=0)
        result = self.tool.netstat()
        assert "Netid" in result or result != ""

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_netstat_listening_uses_tuln(self, mock_run):
        """listening=True uses -tuln flags"""
        mock_run.return_value = Mock(stdout="ok", stderr="", returncode=0)
        self.tool.netstat(listening=True)
        args = mock_run.call_args[0][0]
        assert "-tuln" in args

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_netstat_falls_back_to_netstat_command(self, mock_run):
        """Falls back to netstat when ss fails"""
        fail = Mock(stdout="", stderr="", returncode=1)
        success = Mock(stdout="netstat output\n", stderr="", returncode=0)
        mock_run.side_effect = [fail, success]
        result = self.tool.netstat()
        assert mock_run.call_count == 2

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_netstat_exception_returns_error_string(self, mock_run):
        """Exception returns an 'Error: ...' string"""
        mock_run.side_effect = Exception("no ss")
        result = self.tool.netstat()
        assert result.startswith("Error:")


class TestNetworkOpsNslookup:
    """Tests for NetworkOps.nslookup"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = NetworkOps()

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_nslookup_returns_stdout(self, mock_run):
        """nslookup returns DNS answer"""
        mock_run.return_value = Mock(stdout="Address: 1.2.3.4\n", stderr="", returncode=0)
        result = self.tool.nslookup("example.com")
        assert "1.2.3.4" in result

    @patch("zenus_core.tools.network_ops.subprocess.run")
    def test_nslookup_exception_returns_error_string(self, mock_run):
        """Exception returns an 'Error: ...' string"""
        mock_run.side_effect = Exception("no nslookup")
        result = self.tool.nslookup("bad.invalid")
        assert result.startswith("Error:")


# ===========================================================================
# ProcessOps
# ===========================================================================

class TestProcessOpsFindByName:
    """Tests for ProcessOps.find_by_name"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = ProcessOps()

    @patch("zenus_core.tools.process_ops.psutil.process_iter")
    def test_find_returns_matching_process(self, mock_iter):
        """Matching processes are returned with PID and name"""
        proc = Mock()
        proc.info = {"pid": 42, "name": "python3", "cmdline": ["python3", "app.py"]}
        mock_iter.return_value = [proc]

        result = self.tool.find_by_name("python")
        assert "42" in result
        assert "python3" in result

    @patch("zenus_core.tools.process_ops.psutil.process_iter")
    def test_find_case_insensitive(self, mock_iter):
        """Name search is case-insensitive"""
        proc = Mock()
        proc.info = {"pid": 1, "name": "Python3", "cmdline": []}
        mock_iter.return_value = [proc]

        result = self.tool.find_by_name("python")
        assert "Python3" in result

    @patch("zenus_core.tools.process_ops.psutil.process_iter")
    def test_find_no_match_returns_message(self, mock_iter):
        """No matching processes returns a descriptive 'No processes found' message"""
        mock_iter.return_value = []
        result = self.tool.find_by_name("xyzzy_nonexistent")
        assert "No processes found" in result

    @patch("zenus_core.tools.process_ops.psutil.process_iter")
    def test_find_skips_no_such_process(self, mock_iter):
        """NoSuchProcess during iteration is silently skipped"""
        import psutil

        good_proc = Mock()
        good_proc.info = {"pid": 99, "name": "python3", "cmdline": []}

        # This proc will raise NoSuchProcess when .info is accessed inside the loop
        gone = Mock()
        type(gone).info = property(
            lambda self: (_ for _ in ()).throw(psutil.NoSuchProcess(pid=100))
        )

        mock_iter.return_value = [good_proc, gone]
        result = self.tool.find_by_name("python")
        # Should still return the good proc
        assert "99" in result

    @patch("zenus_core.tools.process_ops.psutil.process_iter")
    def test_find_multiple_matches(self, mock_iter):
        """Multiple matching processes are all returned"""
        procs = []
        for pid in [10, 20, 30]:
            p = Mock()
            p.info = {"pid": pid, "name": "python3", "cmdline": []}
            procs.append(p)
        mock_iter.return_value = procs

        result = self.tool.find_by_name("python")
        assert "10" in result
        assert "20" in result
        assert "30" in result


class TestProcessOpsInfo:
    """Tests for ProcessOps.info"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = ProcessOps()

    @patch("zenus_core.tools.process_ops.psutil.Process")
    def test_info_returns_process_details(self, mock_process_cls):
        """info returns PID, name, status, cpu, memory, and command"""
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.name.return_value = "python3"
        mock_proc.status.return_value = "running"
        mock_proc.cpu_percent.return_value = 1.5
        mock_proc.memory_percent.return_value = 2.3
        mock_proc.cmdline.return_value = ["python3", "main.py"]
        mock_proc.oneshot.return_value.__enter__ = Mock(return_value=None)
        mock_proc.oneshot.return_value.__exit__ = Mock(return_value=False)
        mock_process_cls.return_value = mock_proc

        result = self.tool.info(42)
        assert "42" in result
        assert "python3" in result
        assert "running" in result

    @patch("zenus_core.tools.process_ops.psutil.Process")
    def test_info_no_such_process(self, mock_process_cls):
        """NoSuchProcess returns a descriptive 'not found' message"""
        import psutil
        mock_process_cls.side_effect = psutil.NoSuchProcess(pid=9999)
        result = self.tool.info(9999)
        assert "not found" in result or "9999" in result

    @patch("zenus_core.tools.process_ops.psutil.Process")
    def test_info_access_denied(self, mock_process_cls):
        """AccessDenied returns a descriptive 'Access denied' message"""
        import psutil
        mock_process_cls.side_effect = psutil.AccessDenied(pid=1)
        result = self.tool.info(1)
        assert "denied" in result.lower() or "1" in result


class TestProcessOpsKill:
    """Tests for ProcessOps.kill"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = ProcessOps()

    @patch("zenus_core.tools.process_ops.psutil.Process")
    def test_kill_terminate_sends_sigterm(self, mock_process_cls):
        """kill without force sends SIGTERM (terminate)"""
        mock_proc = Mock()
        mock_proc.name.return_value = "python3"
        mock_process_cls.return_value = mock_proc

        result = self.tool.kill(42, force=False)
        mock_proc.terminate.assert_called_once()
        assert "Terminated" in result or "42" in result

    @patch("zenus_core.tools.process_ops.psutil.Process")
    def test_kill_force_sends_sigkill(self, mock_process_cls):
        """kill with force=True sends SIGKILL"""
        mock_proc = Mock()
        mock_proc.name.return_value = "python3"
        mock_process_cls.return_value = mock_proc

        result = self.tool.kill(42, force=True)
        mock_proc.kill.assert_called_once()
        assert "Force killed" in result or "42" in result

    @patch("zenus_core.tools.process_ops.psutil.Process")
    def test_kill_no_such_process(self, mock_process_cls):
        """NoSuchProcess returns a descriptive message"""
        import psutil
        mock_process_cls.side_effect = psutil.NoSuchProcess(pid=9999)
        result = self.tool.kill(9999)
        assert "not found" in result or "9999" in result

    @patch("zenus_core.tools.process_ops.psutil.Process")
    def test_kill_access_denied(self, mock_process_cls):
        """AccessDenied returns a descriptive message"""
        import psutil
        mock_proc = Mock()
        mock_proc.name.return_value = "systemd"
        mock_proc.terminate.side_effect = psutil.AccessDenied(pid=1)
        mock_process_cls.return_value = mock_proc

        result = self.tool.kill(1)
        assert "denied" in result.lower() or "1" in result


# ===========================================================================
# PackageOps
# ===========================================================================

class TestPackageOpsDetect:
    """Tests for PackageOps._detect_package_manager"""

    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_detects_apt(self, mock_exists):
        """apt is detected when /usr/bin/apt exists"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        assert ops.package_manager == "apt"

    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_detects_dnf(self, mock_exists):
        """dnf is detected when apt is absent but dnf is present"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/dnf"
        ops = PackageOps()
        assert ops.package_manager == "dnf"

    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_detects_pacman(self, mock_exists):
        """pacman is detected when only /usr/bin/pacman is present"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/pacman"
        ops = PackageOps()
        assert ops.package_manager == "pacman"

    @patch("zenus_core.tools.package_ops.os.path.exists", return_value=False)
    def test_unknown_when_none_found(self, mock_exists):
        """Returns 'unknown' when no supported package manager is found"""
        ops = PackageOps()
        assert ops.package_manager == "unknown"


class TestPackageOpsInstall:
    """Tests for PackageOps.install"""

    @patch("zenus_core.tools.package_ops.os.path.exists")
    def _make_ops(self, manager: str, mock_exists):
        """Helper: create PackageOps with a specific package manager"""
        paths = {
            "apt": "/usr/bin/apt",
            "dnf": "/usr/bin/dnf",
            "pacman": "/usr/bin/pacman",
        }
        mock_exists.side_effect = lambda p: p == paths.get(manager, "")
        return PackageOps()

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="installed")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_install(self, mock_exists, mock_exec):
        """apt install builds correct command"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        ops.install("vim")
        call_args = mock_exec.call_args[0][0]
        assert "apt" in call_args
        assert "install" in call_args
        assert "vim" in call_args

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="installed")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_install_confirm_adds_y(self, mock_exists, mock_exec):
        """apt install with confirm=True appends -y"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        ops.install("vim", confirm=True)
        call_args = mock_exec.call_args[0][0]
        assert "-y" in call_args

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="installed")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_dnf_install(self, mock_exists, mock_exec):
        """dnf install builds correct command"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/dnf"
        ops = PackageOps()
        ops.install("vim")
        call_args = mock_exec.call_args[0][0]
        assert "dnf" in call_args
        assert "install" in call_args

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="installed")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_pacman_install(self, mock_exists, mock_exec):
        """pacman install uses -S flag"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/pacman"
        ops = PackageOps()
        ops.install("vim")
        call_args = mock_exec.call_args[0][0]
        assert "pacman" in call_args
        assert "-S" in call_args

    @patch("zenus_core.tools.package_ops.os.path.exists", return_value=False)
    def test_install_unsupported_manager(self, mock_exists):
        """Unsupported package manager returns error string"""
        ops = PackageOps()
        result = ops.install("vim")
        assert "not supported" in result


class TestPackageOpsRemove:
    """Tests for PackageOps.remove"""

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="removed")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_remove(self, mock_exists, mock_exec):
        """apt remove builds correct command"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        ops.remove("vim")
        call_args = mock_exec.call_args[0][0]
        assert "apt" in call_args
        assert "remove" in call_args
        assert "vim" in call_args

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="removed")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_pacman_remove_uses_R_flag(self, mock_exists, mock_exec):
        """pacman remove uses -R flag"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/pacman"
        ops = PackageOps()
        ops.remove("vim")
        call_args = mock_exec.call_args[0][0]
        assert "-R" in call_args

    @patch("zenus_core.tools.package_ops.os.path.exists", return_value=False)
    def test_remove_unsupported_manager(self, mock_exists):
        """Unsupported manager returns error string"""
        ops = PackageOps()
        result = ops.remove("vim")
        assert "not supported" in result


class TestPackageOpsUpdate:
    """Tests for PackageOps.update"""

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="updated")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_update_without_upgrade(self, mock_exists, mock_exec):
        """apt update without upgrade calls 'apt update'"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        ops.update(upgrade=False)
        call_args = mock_exec.call_args[0][0]
        assert "apt" in call_args
        assert "update" in call_args

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="upgraded")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_update_with_upgrade_calls_both(self, mock_exists, mock_exec):
        """apt update with upgrade=True calls both 'apt update' and 'apt upgrade'"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        ops.update(upgrade=True)
        assert mock_exec.call_count == 2

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="updated")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_dnf_update(self, mock_exists, mock_exec):
        """dnf update calls 'dnf check-update'"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/dnf"
        ops = PackageOps()
        ops.update(upgrade=False)
        call_args = mock_exec.call_args[0][0]
        assert "dnf" in call_args

    @patch("zenus_core.tools.package_ops.os.path.exists", return_value=False)
    def test_update_unsupported_manager(self, mock_exists):
        """Unsupported manager returns error string"""
        ops = PackageOps()
        result = ops.update()
        assert "not supported" in result


class TestPackageOpsSearch:
    """Tests for PackageOps.search"""

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="vim - Vi IMproved")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_search(self, mock_exists, mock_exec):
        """apt search builds correct command"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        result = ops.search("vim")
        call_args = mock_exec.call_args[0][0]
        assert "apt" in call_args
        assert "search" in call_args
        assert "vim" in call_args

    @patch("zenus_core.tools.package_ops.os.path.exists", return_value=False)
    def test_search_unsupported_manager(self, mock_exists):
        """Unsupported manager returns error string"""
        ops = PackageOps()
        result = ops.search("vim")
        assert "not supported" in result


class TestPackageOpsListInstalled:
    """Tests for PackageOps.list_installed"""

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="vim/stable 9.0\ncurl/stable 7.88")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_list_all(self, mock_exists, mock_exec):
        """apt list --installed returns full package list"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        result = ops.list_installed()
        assert "vim" in result or "curl" in result

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="vim/stable 9.0\ncurl/stable 7.88")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_list_with_pattern_filters(self, mock_exists, mock_exec):
        """pattern argument filters the package list"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        result = ops.list_installed(pattern="vim")
        assert "vim" in result
        assert "curl" not in result

    @patch("zenus_core.tools.package_ops.os.path.exists", return_value=False)
    def test_list_unsupported_manager(self, mock_exists):
        """Unsupported manager returns error string"""
        ops = PackageOps()
        result = ops.list_installed()
        assert "not supported" in result


class TestPackageOpsClean:
    """Tests for PackageOps.clean"""

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="cleaned")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_clean(self, mock_exists, mock_exec):
        """apt clean builds correct command"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        ops.clean()
        call_args = mock_exec.call_args[0][0]
        assert "apt" in call_args
        assert "clean" in call_args

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="cleaned")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_dnf_clean_all(self, mock_exists, mock_exec):
        """dnf clean uses 'all' argument"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/dnf"
        ops = PackageOps()
        ops.clean()
        call_args = mock_exec.call_args[0][0]
        assert "all" in call_args

    @patch("zenus_core.tools.package_ops.os.path.exists", return_value=False)
    def test_clean_unsupported_manager(self, mock_exists):
        """Unsupported manager returns error string"""
        ops = PackageOps()
        result = ops.clean()
        assert "not supported" in result


class TestPackageOpsInfo:
    """Tests for PackageOps.info"""

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="Package: vim")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_apt_info(self, mock_exists, mock_exec):
        """apt show builds correct command"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        ops = PackageOps()
        result = ops.info("vim")
        call_args = mock_exec.call_args[0][0]
        assert "apt" in call_args
        assert "show" in call_args
        assert "vim" in call_args

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="Name: vim")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_dnf_info(self, mock_exists, mock_exec):
        """dnf info builds correct command"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/dnf"
        ops = PackageOps()
        result = ops.info("vim")
        call_args = mock_exec.call_args[0][0]
        assert "dnf" in call_args
        assert "info" in call_args

    @patch("zenus_core.tools.package_ops.execute_shell_command", return_value="Name: vim")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_pacman_info_uses_Si(self, mock_exists, mock_exec):
        """pacman info uses -Si flag"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/pacman"
        ops = PackageOps()
        ops.info("vim")
        call_args = mock_exec.call_args[0][0]
        assert "-Si" in call_args

    @patch("zenus_core.tools.package_ops.os.path.exists", return_value=False)
    def test_info_unsupported_manager(self, mock_exists):
        """Unsupported manager returns error string"""
        ops = PackageOps()
        result = ops.info("vim")
        assert "not supported" in result


class TestPackageOpsRuntimeError:
    """Tests for PackageOps._run_command error conversion"""

    @patch("zenus_core.tools.package_ops.execute_shell_command")
    @patch("zenus_core.tools.package_ops.os.path.exists")
    def test_runtime_error_converted_to_string(self, mock_exists, mock_exec):
        """RuntimeError from execute_shell_command is converted to a string result"""
        mock_exists.side_effect = lambda p: p == "/usr/bin/apt"
        mock_exec.side_effect = RuntimeError("Command failed (exit 1): error")
        ops = PackageOps()
        result = ops.install("vim")
        assert "Command failed" in result
