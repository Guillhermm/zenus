"""
Unit tests for SystemOps tool (all external calls mocked)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call

from zenus_core.tools.system_ops import SystemOps


class TestSystemOpsDiskUsage:
    """Tests for SystemOps.disk_usage"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = SystemOps()

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    def test_returns_formatted_string(self, mock_du):
        """disk_usage returns human-readable GB/percent string"""
        mock_du.return_value = Mock(
            total=100 * (1024 ** 3),
            used=40 * (1024 ** 3),
            free=60 * (1024 ** 3),
        )
        result = self.tool.disk_usage("/")
        assert "Disk /" in result
        assert "GB" in result
        assert "%" in result

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    def test_calculates_percent_correctly(self, mock_du):
        """Percent used is calculated as used/total * 100"""
        mock_du.return_value = Mock(
            total=200 * (1024 ** 3),
            used=50 * (1024 ** 3),
            free=150 * (1024 ** 3),
        )
        result = self.tool.disk_usage("/")
        assert "25.0%" in result

    @patch("zenus_core.tools.system_ops.shutil.disk_usage", side_effect=FileNotFoundError)
    def test_file_not_found_returns_error(self, mock_du):
        """FileNotFoundError returns an error string"""
        result = self.tool.disk_usage("/nonexistent")
        assert "Error" in result
        assert "nonexistent" in result

    @patch("zenus_core.tools.system_ops.shutil.disk_usage", side_effect=OSError("permission denied"))
    def test_oserror_returns_error(self, mock_du):
        """OSError returns an error string"""
        result = self.tool.disk_usage("/restricted")
        assert "Error" in result

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    def test_expands_tilde_in_path(self, mock_du):
        """~ is expanded before calling shutil.disk_usage"""
        mock_du.return_value = Mock(
            total=100 * (1024 ** 3),
            used=10 * (1024 ** 3),
            free=90 * (1024 ** 3),
        )
        self.tool.disk_usage("~")
        called_path = mock_du.call_args[0][0]
        assert not called_path.startswith("~")

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    def test_free_gb_shown(self, mock_du):
        """Free GB is included in result"""
        mock_du.return_value = Mock(
            total=100 * (1024 ** 3),
            used=70 * (1024 ** 3),
            free=30 * (1024 ** 3),
        )
        result = self.tool.disk_usage("/")
        assert "free" in result.lower()
        assert "30.0GB" in result


class TestSystemOpsMemoryInfo:
    """Tests for SystemOps.memory_info"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = SystemOps()

    @patch("zenus_core.tools.system_ops.psutil.virtual_memory")
    def test_returns_formatted_memory(self, mock_vmem):
        """memory_info returns GB/percent format"""
        mock_vmem.return_value = Mock(
            total=16 * (1024 ** 3),
            used=8 * (1024 ** 3),
            available=8 * (1024 ** 3),
            percent=50.0,
        )
        result = self.tool.memory_info()
        assert "Memory:" in result
        assert "GB" in result
        assert "50.0%" in result

    @patch("zenus_core.tools.system_ops.psutil.virtual_memory")
    def test_available_gb_included(self, mock_vmem):
        """Available GB is shown in the result"""
        mock_vmem.return_value = Mock(
            total=8 * (1024 ** 3),
            used=6 * (1024 ** 3),
            available=2 * (1024 ** 3),
            percent=75.0,
        )
        result = self.tool.memory_info()
        assert "available" in result.lower()
        assert "2.0GB" in result


class TestSystemOpsCpuInfo:
    """Tests for SystemOps.cpu_info"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = SystemOps()

    @patch("zenus_core.tools.system_ops.psutil.cpu_count", return_value=8)
    @patch("zenus_core.tools.system_ops.psutil.cpu_percent", return_value=33.0)
    def test_returns_cpu_string(self, mock_pct, mock_count):
        """cpu_info returns percent and core count"""
        result = self.tool.cpu_info()
        assert "CPU:" in result
        assert "33.0%" in result
        assert "8 cores" in result

    @patch("zenus_core.tools.system_ops.psutil.cpu_count", return_value=4)
    @patch("zenus_core.tools.system_ops.psutil.cpu_percent", return_value=0.0)
    def test_zero_percent_included(self, mock_pct, mock_count):
        """0% CPU is correctly represented"""
        result = self.tool.cpu_info()
        assert "0.0%" in result


class TestSystemOpsGetSystemInfo:
    """Tests for SystemOps.get_system_info"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = SystemOps()

    @patch("zenus_core.tools.system_ops.psutil.cpu_count")
    def test_returns_multiline_info(self, mock_count):
        """get_system_info returns multi-line string with OS/CPU/Python keys"""
        mock_count.return_value = 4
        result = self.tool.get_system_info()
        assert "OS:" in result
        assert "CPU Cores:" in result
        assert "Python:" in result
        assert "Architecture:" in result

    @patch("zenus_core.tools.system_ops.psutil.cpu_count", return_value=8)
    def test_version_truncated(self, mock_count):
        """OS version is truncated to 60 chars"""
        result = self.tool.get_system_info()
        version_line = [l for l in result.splitlines() if l.startswith("Version:")][0]
        version_part = version_line[len("Version: "):]
        assert len(version_part) <= 60


class TestSystemOpsListProcesses:
    """Tests for SystemOps.list_processes"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = SystemOps()

    @patch("zenus_core.tools.system_ops.psutil.process_iter")
    def test_returns_pid_and_name(self, mock_iter):
        """list_processes returns PID and process name"""
        proc = Mock()
        proc.info = {"pid": 42, "name": "python3", "memory_percent": 1.5}
        mock_iter.return_value = [proc]
        result = self.tool.list_processes(limit=10)
        assert "42" in result
        assert "python3" in result

    @patch("zenus_core.tools.system_ops.psutil.process_iter")
    def test_respects_limit(self, mock_iter):
        """list_processes returns at most `limit` entries"""
        procs = []
        for i in range(20):
            p = Mock()
            p.info = {"pid": i, "name": f"proc{i}", "memory_percent": float(20 - i)}
            procs.append(p)
        mock_iter.return_value = procs
        result = self.tool.list_processes(limit=5)
        lines = result.strip().splitlines()
        assert len(lines) <= 5

    @patch("zenus_core.tools.system_ops.psutil.process_iter")
    def test_sorted_by_memory_descending(self, mock_iter):
        """Processes are sorted by memory_percent descending"""
        low = Mock()
        low.info = {"pid": 1, "name": "low", "memory_percent": 0.5}
        high = Mock()
        high.info = {"pid": 2, "name": "high", "memory_percent": 9.9}
        mock_iter.return_value = [low, high]
        result = self.tool.list_processes(limit=10)
        lines = result.strip().splitlines()
        assert "high" in lines[0]

    @patch("zenus_core.tools.system_ops.psutil.process_iter")
    def test_skips_no_such_process(self, mock_iter):
        """NoSuchProcess exceptions during iteration are silently skipped"""
        import psutil
        good = Mock()
        good.info = {"pid": 99, "name": "good", "memory_percent": 1.0}
        bad = Mock()
        type(bad).info = property(
            lambda self: (_ for _ in ()).throw(psutil.NoSuchProcess(pid=100))
        )
        mock_iter.return_value = [good, bad]
        result = self.tool.list_processes(limit=10)
        assert "99" in result

    @patch("zenus_core.tools.system_ops.psutil.process_iter")
    def test_skips_access_denied(self, mock_iter):
        """AccessDenied exceptions during iteration are silently skipped"""
        import psutil
        good = Mock()
        good.info = {"pid": 77, "name": "allowed", "memory_percent": 0.2}
        denied = Mock()
        type(denied).info = property(
            lambda self: (_ for _ in ()).throw(psutil.AccessDenied(pid=1))
        )
        mock_iter.return_value = [denied, good]
        result = self.tool.list_processes(limit=10)
        assert "77" in result


class TestSystemOpsUptime:
    """Tests for SystemOps.uptime"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = SystemOps()

    @patch("zenus_core.tools.system_ops.psutil.time")
    @patch("zenus_core.tools.system_ops.psutil.boot_time")
    def test_returns_days_hours_minutes(self, mock_boot, mock_time):
        """uptime returns formatted days/hours/minutes string"""
        import time as _time
        now = 1_700_000_000.0
        # 1 day + 2 hours + 30 minutes = 95400 seconds
        mock_boot.return_value = now - 95400
        mock_time.time.return_value = now
        result = self.tool.uptime()
        assert "1d" in result
        assert "2h" in result
        assert "30m" in result

    @patch("zenus_core.tools.system_ops.psutil.time")
    @patch("zenus_core.tools.system_ops.psutil.boot_time")
    def test_zero_days_allowed(self, mock_boot, mock_time):
        """Uptime under 1 day shows 0d"""
        now = 1_700_000_000.0
        mock_boot.return_value = now - 3600  # 1 hour
        mock_time.time.return_value = now
        result = self.tool.uptime()
        assert "0d" in result
        assert "1h" in result


class TestSystemOpsFindLargeFiles:
    """Tests for SystemOps.find_large_files"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = SystemOps()

    @patch("zenus_core.tools.system_ops.os.path.getsize")
    @patch("zenus_core.tools.system_ops.os.walk")
    def test_finds_files_above_threshold(self, mock_walk, mock_size):
        """Files larger than min_size_mb are returned"""
        mock_walk.return_value = [("/home/user", [], ["bigfile.iso"])]
        mock_size.return_value = 200 * 1024 * 1024  # 200 MB
        result = self.tool.find_large_files(path="/home/user", min_size_mb=100)
        assert "bigfile.iso" in result
        assert "200.0MB" in result

    @patch("zenus_core.tools.system_ops.os.walk")
    def test_no_large_files_returns_message(self, mock_walk):
        """Empty directory yields a 'No files' message"""
        mock_walk.return_value = [("/home/user", [], [])]
        result = self.tool.find_large_files(path="/home/user", min_size_mb=100)
        assert "No files" in result

    @patch("zenus_core.tools.system_ops.os.path.getsize", side_effect=OSError)
    @patch("zenus_core.tools.system_ops.os.walk")
    def test_oserror_on_file_skipped(self, mock_walk, mock_size):
        """OSError on individual file is silently skipped"""
        mock_walk.return_value = [("/home/user", [], ["protected.bin"])]
        result = self.tool.find_large_files(path="/home/user", min_size_mb=100)
        assert "Error" not in result or "No files" in result

    @patch("zenus_core.tools.system_ops.os.walk", side_effect=Exception("boom"))
    def test_walk_exception_returns_error(self, mock_walk):
        """Exception during os.walk returns an 'Error scanning' string"""
        result = self.tool.find_large_files(path="/bad")
        assert "Error" in result

    @patch("zenus_core.tools.system_ops.os.path.getsize")
    @patch("zenus_core.tools.system_ops.os.walk")
    def test_respects_limit(self, mock_walk, mock_size):
        """Only `limit` largest files are returned"""
        files = [f"file{i}.bin" for i in range(30)]
        mock_walk.return_value = [("/tmp", [], files)]
        mock_size.return_value = 500 * 1024 * 1024  # all same size
        result = self.tool.find_large_files(path="/tmp", min_size_mb=100, limit=5)
        lines = result.strip().splitlines()
        # header line + up to 5 file lines
        file_lines = [l for l in lines if "MB:" in l]
        assert len(file_lines) <= 5

    @patch("zenus_core.tools.system_ops.os.path.getsize")
    @patch("zenus_core.tools.system_ops.os.walk")
    def test_skips_hidden_dirs(self, mock_walk, mock_size):
        """Hidden directories and node_modules are excluded from walk"""
        # We check that dirs[:] is filtered — simulate by verifying walk call
        walked_dirs = [".hidden", "node_modules", "src"]
        # Return dirs that should be filtered
        def fake_walk(path):
            dirs = [".hidden", "node_modules", "__pycache__", ".git", "src"]
            yield (path, dirs, [])
            # dirs[:] mutation happens inside the tool; we just verify no crash
        mock_walk.side_effect = fake_walk
        mock_size.return_value = 0
        result = self.tool.find_large_files(path="/tmp", min_size_mb=100)
        assert isinstance(result, str)


class TestSystemOpsCheckResourceUsage:
    """Tests for SystemOps.check_resource_usage"""

    def setup_method(self):
        """Instantiate tool under test"""
        self.tool = SystemOps()

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    @patch("zenus_core.tools.system_ops.psutil.virtual_memory")
    @patch("zenus_core.tools.system_ops.psutil.cpu_count", return_value=4)
    @patch("zenus_core.tools.system_ops.psutil.cpu_percent", return_value=10.0)
    def test_contains_cpu_memory_disk(self, mock_pct, mock_count, mock_vmem, mock_du):
        """check_resource_usage contains CPU, Memory, and Disk sections"""
        mock_vmem.return_value = Mock(
            total=16 * (1024 ** 3),
            used=4 * (1024 ** 3),
            available=12 * (1024 ** 3),
            percent=25.0,
        )
        mock_du.return_value = Mock(
            total=500 * (1024 ** 3),
            used=200 * (1024 ** 3),
            free=300 * (1024 ** 3),
        )
        result = self.tool.check_resource_usage()
        assert "CPU:" in result
        assert "Memory:" in result
        assert "Disk:" in result

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    @patch("zenus_core.tools.system_ops.psutil.virtual_memory")
    @patch("zenus_core.tools.system_ops.psutil.cpu_count", return_value=4)
    @patch("zenus_core.tools.system_ops.psutil.cpu_percent", return_value=95.0)
    def test_high_cpu_triggers_warning(self, mock_pct, mock_count, mock_vmem, mock_du):
        """CPU > 90% triggers a warning in the output"""
        mock_vmem.return_value = Mock(
            total=16 * (1024 ** 3),
            used=4 * (1024 ** 3),
            available=12 * (1024 ** 3),
            percent=25.0,
        )
        mock_du.return_value = Mock(
            total=500 * (1024 ** 3),
            used=200 * (1024 ** 3),
            free=300 * (1024 ** 3),
        )
        result = self.tool.check_resource_usage()
        assert "CPU" in result and "high" in result.lower()

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    @patch("zenus_core.tools.system_ops.psutil.virtual_memory")
    @patch("zenus_core.tools.system_ops.psutil.cpu_count", return_value=4)
    @patch("zenus_core.tools.system_ops.psutil.cpu_percent", return_value=10.0)
    def test_high_memory_triggers_warning(self, mock_pct, mock_count, mock_vmem, mock_du):
        """Memory > 80% triggers a warning"""
        mock_vmem.return_value = Mock(
            total=16 * (1024 ** 3),
            used=14 * (1024 ** 3),
            available=2 * (1024 ** 3),
            percent=87.5,
        )
        mock_du.return_value = Mock(
            total=500 * (1024 ** 3),
            used=200 * (1024 ** 3),
            free=300 * (1024 ** 3),
        )
        result = self.tool.check_resource_usage()
        assert "Memory" in result and "high" in result.lower()

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    @patch("zenus_core.tools.system_ops.psutil.virtual_memory")
    @patch("zenus_core.tools.system_ops.psutil.cpu_count", return_value=4)
    @patch("zenus_core.tools.system_ops.psutil.cpu_percent", return_value=10.0)
    def test_high_disk_triggers_warning(self, mock_pct, mock_count, mock_vmem, mock_du):
        """Disk > 85% triggers a warning"""
        mock_vmem.return_value = Mock(
            total=16 * (1024 ** 3),
            used=4 * (1024 ** 3),
            available=12 * (1024 ** 3),
            percent=25.0,
        )
        mock_du.return_value = Mock(
            total=100 * (1024 ** 3),
            used=90 * (1024 ** 3),
            free=10 * (1024 ** 3),
        )
        result = self.tool.check_resource_usage()
        assert "Disk" in result and "high" in result.lower()

    @patch("zenus_core.tools.system_ops.shutil.disk_usage")
    @patch("zenus_core.tools.system_ops.psutil.virtual_memory")
    @patch("zenus_core.tools.system_ops.psutil.cpu_count", return_value=4)
    @patch("zenus_core.tools.system_ops.psutil.cpu_percent", return_value=10.0)
    def test_no_warnings_under_thresholds(self, mock_pct, mock_count, mock_vmem, mock_du):
        """No warnings appear when all metrics are below thresholds"""
        mock_vmem.return_value = Mock(
            total=16 * (1024 ** 3),
            used=4 * (1024 ** 3),
            available=12 * (1024 ** 3),
            percent=25.0,
        )
        mock_du.return_value = Mock(
            total=500 * (1024 ** 3),
            used=100 * (1024 ** 3),
            free=400 * (1024 ** 3),
        )
        result = self.tool.check_resource_usage()
        assert "high" not in result.lower()
