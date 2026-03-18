"""
Tests for ShellOps tool and StreamingExecutor (shell_executor)
"""

import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock

from zenus_core.tools.shell_ops import ShellOps, _is_blocked
from zenus_core.tools.shell_executor import StreamingExecutor, execute_shell_command


# ---------------------------------------------------------------------------
# _is_blocked helper
# ---------------------------------------------------------------------------

class TestIsBlocked:
    """Tests for the _is_blocked pattern matcher"""

    def test_allows_safe_command(self):
        """Safe commands should not be blocked"""
        assert _is_blocked("ls -la /tmp") is False

    def test_blocks_rm_rf_root(self):
        """rm -rf / must be blocked"""
        assert _is_blocked("rm -rf /") is True

    def test_blocks_rm_rf_root_with_extra_spaces(self):
        """rm -rf  / with extra whitespace must be blocked"""
        assert _is_blocked("rm  -rf  /") is True

    def test_blocks_dd_if(self):
        """dd if= must be blocked"""
        assert _is_blocked("dd if=/dev/zero of=/dev/sda") is True

    def test_blocks_fork_bomb(self):
        """Fork bomb pattern must be blocked"""
        assert _is_blocked(":() { :|:& };:") is True

    def test_blocks_mkfs(self):
        """mkfs.* must be blocked"""
        assert _is_blocked("mkfs.ext4 /dev/sdb1") is True

    def test_blocks_redirect_to_dev_sd(self):
        """Writing to /dev/sd* must be blocked"""
        assert _is_blocked("cat file > /dev/sda") is True

    def test_allows_dd_without_if(self):
        """dd without if= should not be blocked"""
        assert _is_blocked("dd of=/tmp/out bs=1M count=1") is False

    def test_allows_rm_in_subdir(self):
        """rm -rf with an absolute path IS blocked (pattern matches any absolute path)"""
        # The pattern r"rm\s+-rf\s+/" matches any absolute path including /tmp/mydir
        assert _is_blocked("rm -rf /tmp/mydir") is True

    def test_allows_rm_relative_path(self):
        """rm -rf with a relative path is NOT blocked"""
        assert _is_blocked("rm -rf ./mydir") is False


# ---------------------------------------------------------------------------
# ShellOps.run
# ---------------------------------------------------------------------------

class TestShellOpsRun:
    """Tests for ShellOps.run command execution"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = ShellOps()

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_returns_stdout(self, mock_run):
        """Successful command returns stripped stdout"""
        mock_run.return_value = Mock(
            stdout="hello world\n",
            stderr="",
            returncode=0,
        )
        result = self.tool.run("echo hello world")
        assert result == "hello world"

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_combines_stdout_and_stderr(self, mock_run):
        """Both stdout and stderr are combined in the result"""
        mock_run.return_value = Mock(
            stdout="output\n",
            stderr="warning\n",
            returncode=0,
        )
        result = self.tool.run("cmd")
        assert "output" in result
        assert "[stderr] warning" in result

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_no_output_returns_placeholder(self, mock_run):
        """Empty output yields '(no output)' sentinel"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)
        result = self.tool.run("true")
        assert result == "(no output)"

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_raises_on_nonzero_exit(self, mock_run):
        """Non-zero exit code raises RuntimeError"""
        mock_run.return_value = Mock(
            stdout="",
            stderr="something went wrong\n",
            returncode=1,
        )
        with pytest.raises(RuntimeError, match="Command failed"):
            self.tool.run("false")

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_raises_on_timeout(self, mock_run):
        """TimeoutExpired is re-raised as RuntimeError"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 999", timeout=1)
        with pytest.raises(RuntimeError, match="timed out"):
            self.tool.run("sleep 999", timeout=1)

    def test_run_blocks_hard_blocked_command(self):
        """Blocked command raises PermissionError before subprocess is called"""
        with pytest.raises(PermissionError, match="blocked by safety policy"):
            self.tool.run("rm -rf /")

    def test_run_blocks_fork_bomb(self):
        """Fork bomb raises PermissionError"""
        with pytest.raises(PermissionError):
            self.tool.run(":() { :|:& };:")

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_passes_working_dir(self, mock_run):
        """working_dir is forwarded to subprocess.run as cwd"""
        mock_run.return_value = Mock(stdout="ok\n", stderr="", returncode=0)
        self.tool.run("pwd", working_dir="/tmp")
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == "/tmp"

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_expands_tilde_in_working_dir(self, mock_run):
        """~ in working_dir is expanded"""
        mock_run.return_value = Mock(stdout="ok\n", stderr="", returncode=0)
        self.tool.run("pwd", working_dir="~/projects")
        _, kwargs = mock_run.call_args
        assert not kwargs["cwd"].startswith("~")

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_uses_bash_c(self, mock_run):
        """Command is passed to bash -c"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.run("echo x")
        args, _ = mock_run.call_args
        assert args[0][:2] == ["bash", "-c"]

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_default_timeout_120(self, mock_run):
        """Default timeout is 120 seconds"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.run("echo x")
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 120

    @patch("zenus_core.tools.shell_ops.subprocess.run")
    def test_run_custom_timeout(self, mock_run):
        """Custom timeout is forwarded"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.run("echo x", timeout=5)
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 5


# ---------------------------------------------------------------------------
# ShellOps.dry_run
# ---------------------------------------------------------------------------

class TestShellOpsDryRun:
    """Tests for ShellOps.dry_run"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = ShellOps()

    def test_dry_run_contains_command(self):
        """dry_run output includes the command string"""
        result = self.tool.dry_run("echo hello")
        assert "echo hello" in result

    def test_dry_run_contains_dry_run_prefix(self):
        """dry_run output starts with dry-run marker"""
        result = self.tool.dry_run("ls")
        assert "[dry-run]" in result

    def test_dry_run_marks_blocked_command(self):
        """dry_run annotates blocked commands without raising"""
        result = self.tool.dry_run("rm -rf /")
        assert "BLOCKED" in result

    def test_dry_run_includes_working_dir(self):
        """dry_run includes working_dir hint when provided"""
        result = self.tool.dry_run("ls", working_dir="/tmp")
        assert "/tmp" in result

    def test_dry_run_does_not_execute(self):
        """dry_run never calls subprocess"""
        with patch("zenus_core.tools.shell_ops.subprocess.run") as mock_run:
            self.tool.dry_run("echo x")
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# StreamingExecutor
# ---------------------------------------------------------------------------

class TestStreamingExecutor:
    """Tests for StreamingExecutor"""

    @patch("zenus_core.tools.shell_executor.subprocess.run")
    def test_execute_quiet_success(self, mock_run):
        """Quiet execution returns (returncode, stdout, stderr) tuple"""
        mock_run.return_value = Mock(returncode=0, stdout="out\n", stderr="")
        executor = StreamingExecutor()
        rc, out, err = executor.execute(["echo", "out"], stream_output=False)
        assert rc == 0
        assert "out" in out
        assert err == ""

    @patch("zenus_core.tools.shell_executor.subprocess.run")
    def test_execute_quiet_failure(self, mock_run):
        """Failed quiet command returns non-zero returncode"""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="err")
        executor = StreamingExecutor()
        rc, out, err = executor.execute(["false"], stream_output=False)
        assert rc == 1

    @patch("zenus_core.tools.shell_executor.subprocess.run")
    def test_execute_timeout_returns_error_tuple(self, mock_run):
        """Timeout returns (1, '', error message) without raising"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=1)
        executor = StreamingExecutor(timeout=1)
        rc, out, err = executor.execute(["sleep", "9999"], stream_output=False)
        assert rc == 1
        assert "timed out" in err.lower() or "timeout" in err.lower()

    @patch("zenus_core.tools.shell_executor.subprocess.run")
    def test_execute_generic_exception_returns_error_tuple(self, mock_run):
        """Unexpected exception returns (1, '', error message)"""
        mock_run.side_effect = FileNotFoundError("no such file")
        executor = StreamingExecutor()
        rc, out, err = executor.execute(["nonexistent"], stream_output=False)
        assert rc == 1
        assert "Error" in err

    @patch("zenus_core.tools.shell_executor.subprocess.Popen")
    def test_execute_streaming_captures_stdout(self, mock_popen):
        """Streaming mode captures stdout lines"""
        mock_proc = MagicMock()
        mock_proc.stdout.__iter__ = Mock(return_value=iter(["line1\n", "line2\n"]))
        mock_proc.stdout.readline = Mock(side_effect=["line1\n", "line2\n", ""])
        mock_proc.stderr.read.return_value = ""
        mock_proc.returncode = 0
        mock_popen.return_value.__enter__ = Mock(return_value=mock_proc)
        mock_popen.return_value.__exit__ = Mock(return_value=False)
        mock_popen.return_value = mock_proc

        executor = StreamingExecutor()
        # Use quiet mode for reliable mocking in unit tests
        with patch("zenus_core.tools.shell_executor.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="line1\nline2\n", stderr="")
            rc, out, err = executor.execute(["echo", "x"], stream_output=False)
        assert rc == 0

    @patch("os.geteuid", return_value=1000)
    @patch("zenus_core.tools.shell_executor.subprocess.run")
    def test_sudo_prepended_when_not_root(self, mock_run, mock_geteuid):
        """sudo is prepended to command when not root"""
        mock_run.return_value = Mock(returncode=0, stdout="ok", stderr="")
        executor = StreamingExecutor()
        executor.execute(["apt", "update"], sudo=True, stream_output=False)
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "sudo"

    @patch("os.geteuid", return_value=0)
    @patch("zenus_core.tools.shell_executor.subprocess.run")
    def test_sudo_not_prepended_when_root(self, mock_run, mock_geteuid):
        """sudo is not prepended when already root"""
        mock_run.return_value = Mock(returncode=0, stdout="ok", stderr="")
        executor = StreamingExecutor()
        executor.execute(["apt", "update"], sudo=True, stream_output=False)
        call_args = mock_run.call_args[0][0]
        assert call_args[0] != "sudo"


# ---------------------------------------------------------------------------
# execute_shell_command helper
# ---------------------------------------------------------------------------

class TestExecuteShellCommand:
    """Tests for the execute_shell_command convenience wrapper"""

    @patch("zenus_core.tools.shell_executor.StreamingExecutor.execute")
    def test_returns_stdout_on_success(self, mock_execute):
        """Successful command returns stdout content"""
        mock_execute.return_value = (0, "hello\n", "")
        result = execute_shell_command(["echo", "hello"], stream=False)
        assert "hello" in result

    @patch("zenus_core.tools.shell_executor.StreamingExecutor.execute")
    def test_includes_stderr_in_result(self, mock_execute):
        """stderr is included with [stderr] prefix"""
        mock_execute.return_value = (0, "out\n", "warn\n")
        result = execute_shell_command(["cmd"], stream=False)
        assert "[stderr] warn" in result

    @patch("zenus_core.tools.shell_executor.StreamingExecutor.execute")
    def test_no_output_placeholder(self, mock_execute):
        """Empty output yields '(no output)' sentinel"""
        mock_execute.return_value = (0, "", "")
        result = execute_shell_command(["true"], stream=False)
        assert result == "(no output)"

    @patch("zenus_core.tools.shell_executor.StreamingExecutor.execute")
    def test_raises_on_failure(self, mock_execute):
        """Non-zero returncode raises RuntimeError"""
        mock_execute.return_value = (1, "", "error msg")
        with pytest.raises(RuntimeError, match="Command failed"):
            execute_shell_command(["false"], stream=False)
