"""
Unit tests for ContainerOps (Docker/Podman wrapper)

subprocess.run is fully mocked — no real container runtime required.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool(runtime="docker"):
    """Return a ContainerOps with a preset runtime."""
    from zenus_core.tools.container_ops import ContainerOps
    with patch("subprocess.run"):  # suppress _detect_runtime
        tool = ContainerOps()
    tool.runtime = runtime
    return tool


def _subprocess_ok(stdout="ok\n", returncode=0):
    result = Mock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = ""
    return result


def _subprocess_err(stderr="some error", returncode=1):
    result = Mock()
    result.returncode = returncode
    result.stdout = ""
    result.stderr = stderr
    return result


# ===========================================================================
# _detect_runtime
# ===========================================================================

class TestDetectRuntime:

    def test_detects_docker(self):
        """docker is returned when docker --version succeeds."""
        from zenus_core.tools.container_ops import ContainerOps
        with patch("subprocess.run", return_value=_subprocess_ok()) as mock_run:
            tool = ContainerOps()
        assert tool.runtime == "docker"

    def test_falls_back_to_podman(self):
        """podman is returned when docker is unavailable but podman is."""
        from zenus_core.tools.container_ops import ContainerOps

        call_count = [0]
        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            if cmd[0] == "docker":
                raise FileNotFoundError("no docker")
            return _subprocess_ok()

        with patch("subprocess.run", side_effect=side_effect):
            tool = ContainerOps()
        assert tool.runtime == "podman"

    def test_returns_none_when_no_runtime(self):
        """runtime is 'none' when neither docker nor podman is available."""
        from zenus_core.tools.container_ops import ContainerOps
        with patch("subprocess.run", side_effect=FileNotFoundError("none")):
            tool = ContainerOps()
        assert tool.runtime == "none"


# ===========================================================================
# _run
# ===========================================================================

class TestRun:

    def test_no_runtime_returns_error(self):
        """_run returns error message when runtime is 'none'."""
        tool = _make_tool(runtime="none")
        result = tool._run(["ps"])
        assert "Error" in result

    def test_success_returns_stdout(self):
        """_run returns stdout on success."""
        tool = _make_tool()
        with patch("subprocess.run", return_value=_subprocess_ok("CONTAINER ID\nabc123\n")):
            result = tool._run(["ps"])
        assert "CONTAINER" in result or "abc123" in result

    def test_nonzero_returncode_returns_stderr(self):
        """_run returns stderr when command exits non-zero."""
        tool = _make_tool()
        with patch("subprocess.run", return_value=_subprocess_err("permission denied")):
            result = tool._run(["ps"])
        assert "Error" in result or "permission denied" in result

    def test_exception_returns_error(self):
        """_run returns error string when subprocess raises."""
        tool = _make_tool()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 300)):
            result = tool._run(["ps"])
        assert "Error" in result


# ===========================================================================
# run (container)
# ===========================================================================

class TestContainerRun:

    def test_basic_run(self):
        """run() passes image to docker run."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="container id") as mock_run:
            result = tool.run("nginx")
        args = mock_run.call_args[0][0]
        assert "run" in args
        assert "nginx" in args

    def test_run_with_detach(self):
        """run() with detach=True adds -d flag."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.run("nginx", detach=True)
        args = mock_run.call_args[0][0]
        assert "-d" in args

    def test_run_with_name(self):
        """run() with name adds --name flag."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.run("nginx", name="my-nginx")
        args = mock_run.call_args[0][0]
        assert "--name" in args
        assert "my-nginx" in args

    def test_run_with_ports(self):
        """run() with ports adds -p flag."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.run("nginx", ports="8080:80")
        args = mock_run.call_args[0][0]
        assert "-p" in args
        assert "8080:80" in args

    def test_run_with_volumes(self):
        """run() with volumes adds -v flag."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.run("nginx", volumes="/host:/container")
        args = mock_run.call_args[0][0]
        assert "-v" in args

    def test_run_with_command(self):
        """run() with command appends it to args."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.run("ubuntu", command="bash -c ls")
        args = mock_run.call_args[0][0]
        assert "bash" in args


# ===========================================================================
# ps
# ===========================================================================

class TestPs:

    def test_ps_basic(self):
        """ps() calls _run with ['ps']."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="output") as mock_run:
            result = tool.ps()
        mock_run.assert_called_once_with(["ps"])

    def test_ps_all(self):
        """ps(all=True) adds -a flag."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="output") as mock_run:
            result = tool.ps(all=True)
        args = mock_run.call_args[0][0]
        assert "-a" in args


# ===========================================================================
# stop / remove
# ===========================================================================

class TestStopRemove:

    def test_stop(self):
        """stop() calls _run with ['stop', container]."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.stop("abc123")
        mock_run.assert_called_once_with(["stop", "abc123"])

    def test_remove_basic(self):
        """remove() calls _run with ['rm', container]."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.remove("abc123")
        args = mock_run.call_args[0][0]
        assert "rm" in args
        assert "abc123" in args
        assert "-f" not in args

    def test_remove_force(self):
        """remove(force=True) adds -f flag."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.remove("abc123", force=True)
        args = mock_run.call_args[0][0]
        assert "-f" in args


# ===========================================================================
# logs / exec
# ===========================================================================

class TestLogsExec:

    def test_logs(self):
        """logs() calls _run with ['logs', '--tail', N, container]."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="log output") as mock_run:
            tool.logs("abc123", lines=100)
        args = mock_run.call_args[0][0]
        assert "logs" in args
        assert "--tail" in args
        assert "100" in args

    def test_exec(self):
        """exec() calls _run with ['exec', container, ...command]."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="ok") as mock_run:
            tool.exec("abc123", "ls -la")
        args = mock_run.call_args[0][0]
        assert "exec" in args
        assert "abc123" in args
        assert "ls" in args


# ===========================================================================
# images / pull / build / rmi
# ===========================================================================

class TestImageOps:

    def test_images(self):
        """images() calls _run with ['images']."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="images") as mock_run:
            tool.images()
        mock_run.assert_called_once_with(["images"])

    def test_pull(self):
        """pull() calls _run with ['pull', image]."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="pulled") as mock_run:
            tool.pull("nginx:latest")
        mock_run.assert_called_once_with(["pull", "nginx:latest"])

    def test_build(self):
        """build() calls _run with ['build', '-t', tag, path]."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="built") as mock_run:
            tool.build("/app", "myapp:1.0")
        args = mock_run.call_args[0][0]
        assert "build" in args
        assert "-t" in args
        assert "myapp:1.0" in args
        assert "/app" in args

    def test_rmi_basic(self):
        """rmi() calls _run with ['rmi', image]."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="removed") as mock_run:
            tool.rmi("nginx:latest")
        args = mock_run.call_args[0][0]
        assert "rmi" in args
        assert "nginx:latest" in args
        assert "-f" not in args

    def test_rmi_force(self):
        """rmi(force=True) adds -f flag."""
        tool = _make_tool()
        with patch.object(tool, "_run", return_value="removed") as mock_run:
            tool.rmi("nginx:latest", force=True)
        args = mock_run.call_args[0][0]
        assert "-f" in args
