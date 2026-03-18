"""
Tests for CodeExec — sandboxed Python/Bash code execution tool
"""

import subprocess
import pytest
from unittest.mock import Mock, patch, call

from zenus_core.tools.code_exec import CodeExec, _truncate, _MAX_OUTPUT_CHARS


# ---------------------------------------------------------------------------
# _truncate helper
# ---------------------------------------------------------------------------

class TestTruncate:
    """Tests for the _truncate output-capping helper"""

    def test_short_text_unchanged(self):
        """Text within limit is returned unchanged"""
        text = "hello"
        assert _truncate(text) == text

    def test_exact_limit_unchanged(self):
        """Text exactly at the limit is not truncated"""
        text = "x" * _MAX_OUTPUT_CHARS
        assert _truncate(text) == text

    def test_long_text_is_truncated(self):
        """Text beyond limit is shortened and contains truncation notice"""
        text = "a" * (_MAX_OUTPUT_CHARS + 1000)
        result = _truncate(text)
        assert len(result) < len(text)
        assert "truncated" in result

    def test_truncated_text_contains_both_ends(self):
        """Truncation keeps beginning and end of text"""
        start = "START" + "x" * 5000
        end = "y" * 5000 + "END"
        text = start + end
        result = _truncate(text)
        assert result.startswith("START")
        assert result.endswith("END")

    def test_truncation_reports_dropped_char_count(self):
        """Truncation notice contains the count of removed characters"""
        extra = 500
        text = "x" * (_MAX_OUTPUT_CHARS + extra)
        result = _truncate(text)
        assert str(extra) in result


# ---------------------------------------------------------------------------
# CodeExec.python
# ---------------------------------------------------------------------------

class TestCodeExecPython:
    """Tests for CodeExec.python snippet execution"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = CodeExec()

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_returns_stdout(self, mock_unlink, mock_run):
        """Successful snippet output is returned"""
        mock_run.return_value = Mock(stdout="42\n", stderr="", returncode=0)
        result = self.tool.python("print(42)")
        assert "42" in result

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_includes_stderr(self, mock_unlink, mock_run):
        """stderr is included with [stderr] prefix"""
        mock_run.return_value = Mock(stdout="out\n", stderr="warn\n", returncode=0)
        result = self.tool.python("import warnings; warnings.warn('x')")
        assert "[stderr] warn" in result

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_no_output_placeholder(self, mock_unlink, mock_run):
        """Empty output yields '(no output)' sentinel"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)
        result = self.tool.python("x = 1")
        assert result == "(no output)"

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_raises_on_nonzero_exit(self, mock_unlink, mock_run):
        """Non-zero exit raises RuntimeError"""
        mock_run.return_value = Mock(stdout="", stderr="SyntaxError\n", returncode=1)
        with pytest.raises(RuntimeError, match="Script failed"):
            self.tool.python("this is not valid python !!!")

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_raises_on_timeout(self, mock_unlink, mock_run):
        """TimeoutExpired is re-raised as RuntimeError"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=30)
        with pytest.raises(RuntimeError, match="timed out"):
            self.tool.python("while True: pass")

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_unlinks_script_on_success(self, mock_unlink, mock_run):
        """Temp script file is deleted after successful execution"""
        mock_run.return_value = Mock(stdout="ok\n", stderr="", returncode=0)
        self.tool.python("print('ok')")
        mock_unlink.assert_called_once()

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_unlinks_script_on_failure(self, mock_unlink, mock_run):
        """Temp script file is deleted even when the snippet fails"""
        mock_run.return_value = Mock(stdout="", stderr="err\n", returncode=1)
        with pytest.raises(RuntimeError):
            self.tool.python("raise ValueError('x')")
        mock_unlink.assert_called_once()

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_uses_sys_executable(self, mock_unlink, mock_run):
        """Python subprocess uses the same interpreter as Zenus"""
        import sys
        mock_run.return_value = Mock(stdout="ok\n", stderr="", returncode=0)
        self.tool.python("print('ok')")
        args, _ = mock_run.call_args
        assert args[0][0] == sys.executable

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_default_timeout_30(self, mock_unlink, mock_run):
        """Default timeout for Python snippets is 30 seconds"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.python("print('x')")
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 30

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_custom_timeout(self, mock_unlink, mock_run):
        """Custom timeout is forwarded to subprocess"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.python("print('x')", timeout=5)
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 5

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_working_dir_forwarded(self, mock_unlink, mock_run):
        """working_dir is forwarded as cwd"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.python("print('x')", working_dir="/tmp")
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == "/tmp"

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    def test_python_output_capped_at_8000(self, mock_unlink, mock_run):
        """Output exceeding 8000 chars is truncated"""
        big_output = "x" * 10_000
        mock_run.return_value = Mock(stdout=big_output, stderr="", returncode=0)
        result = self.tool.python("print('x' * 10000)")
        assert len(result) < 10_000
        assert "truncated" in result


# ---------------------------------------------------------------------------
# CodeExec.bash_script
# ---------------------------------------------------------------------------

class TestCodeExecBash:
    """Tests for CodeExec.bash_script execution"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = CodeExec()

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_returns_stdout(self, mock_chmod, mock_unlink, mock_run):
        """Successful script output is returned"""
        mock_run.return_value = Mock(stdout="hello\n", stderr="", returncode=0)
        result = self.tool.bash_script("echo hello")
        assert "hello" in result

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_raises_on_nonzero_exit(self, mock_chmod, mock_unlink, mock_run):
        """Non-zero exit raises RuntimeError"""
        mock_run.return_value = Mock(stdout="", stderr="error\n", returncode=1)
        with pytest.raises(RuntimeError, match="Script failed"):
            self.tool.bash_script("exit 1")

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_raises_on_timeout(self, mock_chmod, mock_unlink, mock_run):
        """TimeoutExpired is re-raised as RuntimeError"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bash", timeout=60)
        with pytest.raises(RuntimeError, match="timed out"):
            self.tool.bash_script("sleep 9999")

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_unlinks_script_on_success(self, mock_chmod, mock_unlink, mock_run):
        """Temp script file is deleted after successful execution"""
        mock_run.return_value = Mock(stdout="ok\n", stderr="", returncode=0)
        self.tool.bash_script("echo ok")
        mock_unlink.assert_called_once()

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_unlinks_script_on_failure(self, mock_chmod, mock_unlink, mock_run):
        """Temp script file is deleted even when script fails"""
        mock_run.return_value = Mock(stdout="", stderr="err\n", returncode=1)
        with pytest.raises(RuntimeError):
            self.tool.bash_script("exit 1")
        mock_unlink.assert_called_once()

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_uses_bash_interpreter(self, mock_chmod, mock_unlink, mock_run):
        """Script is invoked via bash"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.bash_script("echo x")
        args, _ = mock_run.call_args
        assert args[0][0] == "bash"

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_default_timeout_60(self, mock_chmod, mock_unlink, mock_run):
        """Default timeout for Bash scripts is 60 seconds"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.bash_script("echo x")
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 60

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_sets_executable_permission(self, mock_chmod, mock_unlink, mock_run):
        """Script temp file is made executable (chmod 0o700)"""
        mock_run.return_value = Mock(stdout="x\n", stderr="", returncode=0)
        self.tool.bash_script("echo x")
        mock_chmod.assert_called_once()
        assert mock_chmod.call_args[0][1] == 0o700

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_output_capped_at_8000(self, mock_chmod, mock_unlink, mock_run):
        """Output exceeding 8000 chars is truncated"""
        big_output = "y" * 10_000
        mock_run.return_value = Mock(stdout=big_output, stderr="", returncode=0)
        result = self.tool.bash_script("yes | head -10000")
        assert len(result) < 10_000
        assert "truncated" in result

    @patch("zenus_core.tools.code_exec.subprocess.run")
    @patch("zenus_core.tools.code_exec.os.unlink")
    @patch("zenus_core.tools.code_exec.os.chmod")
    def test_bash_no_output_placeholder(self, mock_chmod, mock_unlink, mock_run):
        """Empty output yields '(no output)' sentinel"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)
        result = self.tool.bash_script("true")
        assert result == "(no output)"


# ---------------------------------------------------------------------------
# CodeExec.dry_run
# ---------------------------------------------------------------------------

class TestCodeExecDryRun:
    """Tests for CodeExec.dry_run"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = CodeExec()

    def test_dry_run_contains_prefix(self):
        """dry_run output includes the dry-run marker"""
        result = self.tool.dry_run(code="print('hi')")
        assert "[dry-run]" in result

    def test_dry_run_includes_code_preview(self):
        """dry_run output includes the first part of the code"""
        result = self.tool.dry_run(code="print('hello')")
        assert "print" in result

    def test_dry_run_truncates_long_code(self):
        """Code longer than 200 chars is previewed with ellipsis"""
        long_code = "x = 1\n" * 100
        result = self.tool.dry_run(code=long_code)
        assert "..." in result

    def test_dry_run_does_not_execute(self):
        """dry_run never calls subprocess"""
        with patch("zenus_core.tools.code_exec.subprocess.run") as mock_run:
            self.tool.dry_run(code="print('x')")
            mock_run.assert_not_called()
