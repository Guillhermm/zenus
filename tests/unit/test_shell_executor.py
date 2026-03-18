"""
Unit tests for StreamingExecutor and execute_shell_command

subprocess.Popen and subprocess.run are fully mocked.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO


# ===========================================================================
# StreamingExecutor._execute_quiet
# ===========================================================================

class TestStreamingExecutorQuiet:

    def _make_executor(self, timeout=None):
        from zenus_core.tools.shell_executor import StreamingExecutor
        return StreamingExecutor(timeout=timeout)

    def test_quiet_returns_tuple(self):
        """_execute_quiet returns (returncode, stdout, stderr)."""
        executor = self._make_executor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            rc, out, err = executor._execute_quiet(["echo", "hello"])
        assert rc == 0
        assert "hello" in out
        assert err == ""

    def test_quiet_passes_timeout(self):
        """_execute_quiet passes timeout to subprocess.run."""
        executor = self._make_executor(timeout=30)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            executor._execute_quiet(["ls"])
        kwargs = mock_run.call_args[1]
        assert kwargs.get("timeout") == 30

    def test_quiet_nonzero_returncode(self):
        """_execute_quiet returns nonzero code on failure."""
        executor = self._make_executor()
        mock_result = Mock()
        mock_result.returncode = 127
        mock_result.stdout = ""
        mock_result.stderr = "command not found"
        with patch("subprocess.run", return_value=mock_result):
            rc, out, err = executor._execute_quiet(["notacmd"])
        assert rc == 127
        assert "not found" in err


# ===========================================================================
# StreamingExecutor._execute_streaming
# ===========================================================================

class TestStreamingExecutorStreaming:

    def _make_executor(self, timeout=None):
        from zenus_core.tools.shell_executor import StreamingExecutor
        return StreamingExecutor(timeout=timeout)

    def _make_process(self, stdout_lines=None, stderr="", returncode=0):
        """Build a mock subprocess.Popen process."""
        process = Mock()
        process.returncode = returncode
        lines = (stdout_lines or []) + [""]  # empty string signals EOF
        process.stdout = Mock()
        process.stdout.readline = Mock(side_effect=lines)
        process.stderr = Mock()
        process.stderr.read = Mock(return_value=stderr)
        process.stdout.close = Mock()
        process.stderr.close = Mock()
        process.wait = Mock()
        return process

    def test_streaming_returns_stdout(self):
        """_execute_streaming returns captured stdout lines."""
        executor = self._make_executor()
        process = self._make_process(stdout_lines=["line one\n", "line two\n"])
        with patch("subprocess.Popen", return_value=process):
            with patch("zenus_core.tools.shell_executor.console"):
                rc, out, err = executor._execute_streaming(["echo", "test"], capture=True)
        assert "line one" in out
        assert "line two" in out

    def test_streaming_capture_false_does_not_accumulate(self):
        """_execute_streaming with capture=False returns empty stdout."""
        executor = self._make_executor()
        process = self._make_process(stdout_lines=["output\n"])
        with patch("subprocess.Popen", return_value=process):
            with patch("zenus_core.tools.shell_executor.console"):
                rc, out, err = executor._execute_streaming(["cmd"], capture=False)
        assert out == ""

    def test_streaming_stderr_captured(self):
        """_execute_streaming captures stderr."""
        executor = self._make_executor()
        process = self._make_process(stdout_lines=[], stderr="warning: something\n")
        with patch("subprocess.Popen", return_value=process):
            with patch("zenus_core.tools.shell_executor.console"):
                rc, out, err = executor._execute_streaming(["cmd"], capture=True)
        assert "warning" in err

    def test_streaming_returncode_propagated(self):
        """_execute_streaming propagates process returncode."""
        executor = self._make_executor()
        process = self._make_process(returncode=1)
        with patch("subprocess.Popen", return_value=process):
            with patch("zenus_core.tools.shell_executor.console"):
                rc, out, err = executor._execute_streaming(["cmd"], capture=True)
        assert rc == 1

    def test_streaming_closes_pipes(self):
        """_execute_streaming closes stdout and stderr pipes in finally."""
        executor = self._make_executor()
        process = self._make_process()
        with patch("subprocess.Popen", return_value=process):
            with patch("zenus_core.tools.shell_executor.console"):
                executor._execute_streaming(["cmd"], capture=True)
        process.stdout.close.assert_called_once()
        process.stderr.close.assert_called_once()


# ===========================================================================
# StreamingExecutor.execute
# ===========================================================================

class TestStreamingExecutorExecute:

    def _make_executor(self):
        from zenus_core.tools.shell_executor import StreamingExecutor
        return StreamingExecutor()

    def test_execute_streaming_by_default(self):
        """execute() calls _execute_streaming when stream_output=True."""
        executor = self._make_executor()
        with patch.object(executor, "_execute_streaming", return_value=(0, "out", "")) as mock_stream:
            rc, out, err = executor.execute(["ls"])
        mock_stream.assert_called_once()

    def test_execute_quiet_when_not_streaming(self):
        """execute() calls _execute_quiet when stream_output=False."""
        executor = self._make_executor()
        with patch.object(executor, "_execute_quiet", return_value=(0, "out", "")) as mock_quiet:
            rc, out, err = executor.execute(["ls"], stream_output=False)
        mock_quiet.assert_called_once()

    def test_execute_timeout_returns_error(self):
        """execute() returns error tuple on TimeoutExpired."""
        import subprocess
        executor = self._make_executor()
        with patch.object(executor, "_execute_streaming", side_effect=subprocess.TimeoutExpired("ls", 10)):
            rc, out, err = executor.execute(["ls"])
        assert rc == 1
        assert "timed out" in err.lower()

    def test_execute_exception_returns_error(self):
        """execute() returns error tuple on generic exception."""
        executor = self._make_executor()
        with patch.object(executor, "_execute_streaming", side_effect=OSError("no such file")):
            rc, out, err = executor.execute(["badcmd"])
        assert rc == 1
        assert "Error" in err

    def test_execute_sudo_prepends_sudo(self):
        """execute() prepends sudo when sudo=True and not root."""
        executor = self._make_executor()
        with patch("os.geteuid", return_value=1000):
            with patch.object(executor, "_execute_streaming", return_value=(0, "", "")) as mock_stream:
                executor.execute(["ls"], sudo=True)
        cmd_used = mock_stream.call_args[0][0]
        assert cmd_used[0] == "sudo"

    def test_execute_no_sudo_when_root(self):
        """execute() does not prepend sudo when already root."""
        executor = self._make_executor()
        with patch("os.geteuid", return_value=0):
            with patch.object(executor, "_execute_streaming", return_value=(0, "", "")) as mock_stream:
                executor.execute(["ls"], sudo=True)
        cmd_used = mock_stream.call_args[0][0]
        assert cmd_used[0] != "sudo"


# ===========================================================================
# execute_shell_command (high-level wrapper)
# ===========================================================================

class TestExecuteShellCommand:

    def test_returns_stdout_on_success(self):
        """execute_shell_command returns combined stdout on success."""
        from zenus_core.tools.shell_executor import execute_shell_command
        with patch("zenus_core.tools.shell_executor.StreamingExecutor") as mock_cls:
            mock_exec = Mock()
            mock_exec.execute.return_value = (0, "hello world\n", "")
            mock_cls.return_value = mock_exec
            result = execute_shell_command(["echo", "hello"])
        assert "hello world" in result

    def test_includes_stderr_in_output(self):
        """execute_shell_command includes stderr with [stderr] prefix."""
        from zenus_core.tools.shell_executor import execute_shell_command
        with patch("zenus_core.tools.shell_executor.StreamingExecutor") as mock_cls:
            mock_exec = Mock()
            mock_exec.execute.return_value = (0, "", "a warning\n")
            mock_cls.return_value = mock_exec
            result = execute_shell_command(["cmd"])
        assert "[stderr]" in result
        assert "a warning" in result

    def test_returns_no_output_placeholder(self):
        """execute_shell_command returns '(no output)' when both streams empty."""
        from zenus_core.tools.shell_executor import execute_shell_command
        with patch("zenus_core.tools.shell_executor.StreamingExecutor") as mock_cls:
            mock_exec = Mock()
            mock_exec.execute.return_value = (0, "", "")
            mock_cls.return_value = mock_exec
            result = execute_shell_command(["cmd"])
        assert result == "(no output)"

    def test_raises_on_nonzero_exit(self):
        """execute_shell_command raises RuntimeError on non-zero exit."""
        from zenus_core.tools.shell_executor import execute_shell_command
        with patch("zenus_core.tools.shell_executor.StreamingExecutor") as mock_cls:
            mock_exec = Mock()
            mock_exec.execute.return_value = (1, "", "something failed")
            mock_cls.return_value = mock_exec
            with pytest.raises(RuntimeError, match="Command failed"):
                execute_shell_command(["bad"])

    def test_passes_timeout_to_executor(self):
        """execute_shell_command passes timeout to StreamingExecutor."""
        from zenus_core.tools.shell_executor import execute_shell_command
        with patch("zenus_core.tools.shell_executor.StreamingExecutor") as mock_cls:
            mock_exec = Mock()
            mock_exec.execute.return_value = (0, "ok", "")
            mock_cls.return_value = mock_exec
            execute_shell_command(["cmd"], timeout=60)
        mock_cls.assert_called_once_with(timeout=60)

    def test_combines_stdout_and_stderr(self):
        """execute_shell_command combines both when present."""
        from zenus_core.tools.shell_executor import execute_shell_command
        with patch("zenus_core.tools.shell_executor.StreamingExecutor") as mock_cls:
            mock_exec = Mock()
            mock_exec.execute.return_value = (0, "stdout line\n", "stderr line\n")
            mock_cls.return_value = mock_exec
            result = execute_shell_command(["cmd"])
        assert "stdout line" in result
        assert "stderr line" in result
