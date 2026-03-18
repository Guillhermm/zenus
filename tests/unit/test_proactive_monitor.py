"""
Unit tests for monitoring/proactive_monitor.py

subprocess.run is fully mocked — no real system calls.
"""

import json
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from zenus_core.monitoring.proactive_monitor import (
    AlertLevel,
    HealthStatus,
    HealthCheck,
    Alert,
    MonitoringSession,
    HealthChecker,
    Remediator,
    ProactiveMonitor,
    get_proactive_monitor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger():
    logger = Mock()
    logger.log_info = Mock()
    logger.log_error = Mock()
    return logger


def _make_monitor(tmp_path):
    logger = _make_logger()
    return ProactiveMonitor(logger=logger, storage_dir=tmp_path)


def _disk_ok():
    m = Mock()
    m.returncode = 0
    m.stdout = "Filesystem   Size Used Avail Use% Mounted\n/dev/sda1    50G  20G   30G  40% /"
    return m


def _disk_warning():
    m = Mock()
    m.returncode = 0
    m.stdout = "Filesystem   Size Used Avail Use% Mounted\n/dev/sda1    50G  42G    8G  85% /"
    return m


def _disk_critical():
    m = Mock()
    m.returncode = 0
    m.stdout = "Filesystem   Size Used Avail Use% Mounted\n/dev/sda1    50G  46G    4G  92% /"
    return m


def _mem_ok():
    m = Mock()
    m.returncode = 0
    m.stdout = "              total        used        free\nMem:            1000         500         500"
    return m


def _mem_warning():
    m = Mock()
    m.returncode = 0
    m.stdout = "              total        used        free\nMem:            1000         850         150"
    return m


def _mem_critical():
    m = Mock()
    m.returncode = 0
    m.stdout = "              total        used        free\nMem:            1000         950          50"
    return m


# ===========================================================================
# Enums
# ===========================================================================

class TestEnums:

    def test_alert_level_values(self):
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.CRITICAL.value == "critical"

    def test_health_status_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.CRITICAL.value == "critical"


# ===========================================================================
# HealthCheck dataclass
# ===========================================================================

class TestHealthCheck:

    def test_to_dict(self):
        check = HealthCheck(
            name="disk",
            check_type="disk",
            threshold={"warning": 80},
            check_interval=300,
            auto_remediate=True,
            remediation_action="rm -rf /tmp/*"
        )
        d = check.to_dict()
        assert d["name"] == "disk"
        assert d["check_type"] == "disk"
        assert d["auto_remediate"] is True

    def test_default_optional_fields(self):
        check = HealthCheck(
            name="mem",
            check_type="memory",
            threshold={},
            check_interval=60,
            auto_remediate=False,
            remediation_action=None
        )
        assert check.last_check is None
        assert check.last_status == "unknown"
        assert check.consecutive_failures == 0


# ===========================================================================
# Alert dataclass
# ===========================================================================

class TestAlert:

    def test_to_dict_converts_level(self):
        alert = Alert(
            alert_id="abc123",
            timestamp="2026-01-01T00:00:00",
            level=AlertLevel.WARNING,
            source="disk",
            message="Disk usage high",
            details={"usage": 85},
            auto_remediated=False,
            remediation_result=None
        )
        d = alert.to_dict()
        assert d["level"] == "warning"
        assert d["alert_id"] == "abc123"


# ===========================================================================
# MonitoringSession dataclass
# ===========================================================================

class TestMonitoringSession:

    def test_to_dict_converts_status(self):
        session = MonitoringSession(
            session_id="s1",
            start_time="2026-01-01T00:00:00",
            checks_run=5,
            alerts_generated=1,
            auto_remediations=0,
            status=HealthStatus.DEGRADED
        )
        d = session.to_dict()
        assert d["status"] == "degraded"
        assert d["checks_run"] == 5


# ===========================================================================
# HealthChecker
# ===========================================================================

class TestHealthCheckerDisk:

    def setup_method(self):
        self.checker = HealthChecker(_make_logger())

    def test_disk_healthy(self):
        with patch("subprocess.run", return_value=_disk_ok()):
            ok, details = self.checker.check_disk_space({"warning": 80, "critical": 90})
        assert ok is True
        assert details["level"] == "healthy"
        assert details["usage"] == 40

    def test_disk_warning(self):
        with patch("subprocess.run", return_value=_disk_warning()):
            ok, details = self.checker.check_disk_space({"warning": 80, "critical": 90})
        assert ok is False
        assert details["level"] == "warning"
        assert details["usage"] == 85

    def test_disk_critical(self):
        with patch("subprocess.run", return_value=_disk_critical()):
            ok, details = self.checker.check_disk_space({"warning": 80, "critical": 90})
        assert ok is False
        assert details["level"] == "critical"
        assert details["usage"] == 92

    def test_disk_subprocess_error(self):
        with patch("subprocess.run", side_effect=Exception("df not found")):
            ok, details = self.checker.check_disk_space({})
        assert ok is False
        assert "error" in details


class TestHealthCheckerMemory:

    def setup_method(self):
        self.checker = HealthChecker(_make_logger())

    def test_memory_healthy(self):
        with patch("subprocess.run", return_value=_mem_ok()):
            ok, details = self.checker.check_memory_usage({"warning": 80, "critical": 90})
        assert ok is True
        assert details["level"] == "healthy"
        assert details["usage"] == 50

    def test_memory_warning(self):
        with patch("subprocess.run", return_value=_mem_warning()):
            ok, details = self.checker.check_memory_usage({"warning": 80, "critical": 90})
        assert ok is False
        assert details["level"] == "warning"

    def test_memory_critical(self):
        with patch("subprocess.run", return_value=_mem_critical()):
            ok, details = self.checker.check_memory_usage({"warning": 80, "critical": 90})
        assert ok is False
        assert details["level"] == "critical"

    def test_memory_subprocess_error(self):
        with patch("subprocess.run", side_effect=Exception("free not found")):
            ok, details = self.checker.check_memory_usage({})
        assert ok is False
        assert "error" in details


class TestHealthCheckerService:

    def setup_method(self):
        self.checker = HealthChecker(_make_logger())

    def test_service_active(self):
        result = Mock(returncode=0, stdout="active")
        with patch("subprocess.run", return_value=result):
            ok, details = self.checker.check_service_status("nginx")
        assert ok is True
        assert details["level"] == "healthy"

    def test_service_inactive(self):
        result = Mock(returncode=1, stdout="inactive")
        with patch("subprocess.run", return_value=result):
            ok, details = self.checker.check_service_status("nginx")
        assert ok is False
        assert details["level"] == "critical"

    def test_service_error(self):
        with patch("subprocess.run", side_effect=Exception("systemctl not found")):
            ok, details = self.checker.check_service_status("nginx")
        assert ok is False
        assert "error" in details


class TestHealthCheckerLogSize:

    def setup_method(self):
        self.checker = HealthChecker(_make_logger())

    def test_log_file_healthy(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_bytes(b"x" * 1024)  # 1 KB
        ok, details = self.checker.check_log_size(str(log_file), {"warning_mb": 100, "critical_mb": 500})
        assert ok is True

    def test_log_path_not_found(self):
        ok, details = self.checker.check_log_size("/nonexistent/path", {})
        assert ok is False
        assert "error" in details

    def test_log_directory(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_bytes(b"x" * 1024)
        ok, details = self.checker.check_log_size(str(log_dir), {"warning_mb": 100, "critical_mb": 500})
        assert ok is True

    def test_log_warning_threshold(self, tmp_path):
        log_file = tmp_path / "big.log"
        log_file.write_bytes(b"x" * int(150 * 1024 * 1024))  # 150 MB
        ok, details = self.checker.check_log_size(
            str(log_file), {"warning_mb": 100, "critical_mb": 500}
        )
        assert ok is False
        assert details["level"] == "warning"

    def test_log_critical_threshold(self, tmp_path):
        log_file = tmp_path / "huge.log"
        log_file.write_bytes(b"x" * int(600 * 1024 * 1024))  # 600 MB
        ok, details = self.checker.check_log_size(
            str(log_file), {"warning_mb": 100, "critical_mb": 500}
        )
        assert ok is False
        assert details["level"] == "critical"


class TestHealthCheckerSSL:

    def setup_method(self):
        self.checker = HealthChecker(_make_logger())

    def test_ssl_valid(self):
        result = Mock(stdout="Verify return code: 0 (ok)")
        with patch("subprocess.run", return_value=result):
            ok, details = self.checker.check_ssl_certificate("example.com", {})
        assert ok is True

    def test_ssl_invalid(self):
        result = Mock(stdout="Verify return code: 18 (self signed)")
        with patch("subprocess.run", return_value=result):
            ok, details = self.checker.check_ssl_certificate("example.com", {})
        assert ok is False

    def test_ssl_error(self):
        with patch("subprocess.run", side_effect=Exception("openssl not found")):
            ok, details = self.checker.check_ssl_certificate("example.com", {})
        assert ok is False
        assert "error" in details


# ===========================================================================
# Remediator
# ===========================================================================

class TestRemediator:

    def test_remediate_direct_command_success(self):
        logger = _make_logger()
        remediator = Remediator(logger)
        result = Mock(returncode=0, stdout="cleaned", stderr="")
        with patch("subprocess.run", return_value=result):
            success, msg = remediator.remediate("disk", {"usage": 90}, "rm /tmp/*.log")
        assert success is True
        assert "cleaned" in msg

    def test_remediate_direct_command_failure(self):
        logger = _make_logger()
        remediator = Remediator(logger)
        result = Mock(returncode=1, stdout="", stderr="permission denied")
        with patch("subprocess.run", return_value=result):
            success, msg = remediator.remediate("disk", {"usage": 90}, "rm /tmp/*.log")
        assert success is False

    def test_remediate_exception(self):
        logger = _make_logger()
        remediator = Remediator(logger)
        with patch("subprocess.run", side_effect=Exception("cmd not found")):
            success, msg = remediator.remediate("disk", {}, "bad_cmd")
        assert success is False
        assert "Remediation failed" in msg

    def test_remediate_with_orchestrator(self):
        logger = _make_logger()
        orchestrator = Mock()
        orchestrator.execute_command.return_value = "done"
        remediator = Remediator(logger, orchestrator)
        success, msg = remediator.remediate("disk", {}, "clean logs")
        assert success is True
        orchestrator.execute_command.assert_called_once_with("clean logs")


# ===========================================================================
# ProactiveMonitor
# ===========================================================================

class TestProactiveMonitorInit:

    def test_creates_storage_dir(self, tmp_path):
        subdir = tmp_path / "monitor"
        logger = _make_logger()
        monitor = ProactiveMonitor(logger=logger, storage_dir=subdir)
        assert subdir.exists()

    def test_initializes_default_checks(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        assert len(monitor.health_checks) > 0

    def test_health_checks_file_created(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        assert monitor.health_checks_file.exists()

    def test_no_session_initially(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        assert monitor.current_session is None


class TestProactiveMonitorStartMonitoring:

    def test_start_monitoring_creates_session(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        session = monitor.start_monitoring()
        assert isinstance(session, MonitoringSession)
        assert session.status == HealthStatus.HEALTHY
        assert session.checks_run == 0

    def test_start_monitoring_sets_current_session(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        session = monitor.start_monitoring()
        assert monitor.current_session is session


class TestProactiveMonitorChecks:

    def test_add_health_check(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        initial_count = len(monitor.health_checks)
        new_check = HealthCheck(
            name="custom_check",
            check_type="disk",
            threshold={"warning": 70},
            check_interval=60,
            auto_remediate=False,
            remediation_action=None
        )
        monitor.add_health_check(new_check)
        assert len(monitor.health_checks) == initial_count + 1

    def test_remove_health_check(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        # Add a custom check first
        check = HealthCheck(
            name="to_remove",
            check_type="disk",
            threshold={},
            check_interval=60,
            auto_remediate=False,
            remediation_action=None
        )
        monitor.add_health_check(check)
        assert any(c.name == "to_remove" for c in monitor.health_checks)
        monitor.remove_health_check("to_remove")
        assert not any(c.name == "to_remove" for c in monitor.health_checks)

    def test_get_status_no_session(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        status = monitor.get_status()
        assert status["session"] is None
        assert status["health_checks"] > 0

    def test_get_status_with_session(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        monitor.start_monitoring()
        status = monitor.get_status()
        assert status["session"] is not None


class TestProactiveMonitorRunChecks:

    def test_run_checks_no_issues(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        monitor.start_monitoring()
        # All checks pass
        with patch.object(monitor.checker, "check_disk_space", return_value=(True, {"level": "healthy"})):
            with patch.object(monitor.checker, "check_memory_usage", return_value=(True, {"level": "healthy"})):
                with patch.object(monitor.checker, "check_log_size", return_value=(True, {"level": "healthy"})):
                    alerts = monitor.run_checks()
        assert len(alerts) == 0

    def test_run_checks_generates_alert_on_failure(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        monitor.start_monitoring()
        with patch.object(monitor.checker, "check_disk_space", return_value=(False, {"level": "critical", "message": "Disk full", "usage": 95})):
            with patch.object(monitor.checker, "check_memory_usage", return_value=(True, {"level": "healthy"})):
                with patch.object(monitor.checker, "check_log_size", return_value=(True, {"level": "healthy"})):
                    alerts = monitor.run_checks()
        assert len(alerts) >= 1

    def test_run_checks_updates_session_count(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        monitor.start_monitoring()
        with patch.object(monitor.checker, "check_disk_space", return_value=(True, {"level": "healthy"})):
            with patch.object(monitor.checker, "check_memory_usage", return_value=(True, {"level": "healthy"})):
                with patch.object(monitor.checker, "check_log_size", return_value=(True, {"level": "healthy"})):
                    monitor.run_checks()
        assert monitor.current_session.checks_run == 3  # 3 default checks

    def test_run_checks_updates_status_on_warning(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        monitor.start_monitoring()
        with patch.object(monitor.checker, "check_disk_space", return_value=(False, {"level": "warning", "message": "Disk high", "usage": 85})):
            with patch.object(monitor.checker, "check_memory_usage", return_value=(True, {"level": "healthy"})):
                with patch.object(monitor.checker, "check_log_size", return_value=(True, {"level": "healthy"})):
                    monitor.run_checks()
        assert monitor.current_session.status == HealthStatus.DEGRADED

    def test_run_checks_updates_status_on_critical(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        monitor.start_monitoring()
        with patch.object(monitor.checker, "check_disk_space", return_value=(False, {"level": "critical", "message": "Disk full", "usage": 95})):
            with patch.object(monitor.checker, "check_memory_usage", return_value=(True, {"level": "healthy"})):
                with patch.object(monitor.checker, "check_log_size", return_value=(True, {"level": "healthy"})):
                    monitor.run_checks()
        assert monitor.current_session.status == HealthStatus.CRITICAL

    def test_run_checks_auto_remediation(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        monitor.start_monitoring()
        # disk_space_root has auto_remediate=True
        with patch.object(monitor.checker, "check_disk_space", return_value=(False, {"level": "critical", "message": "full", "usage": 95})):
            with patch.object(monitor.remediator, "remediate", return_value=(True, "cleaned")):
                with patch.object(monitor.checker, "check_memory_usage", return_value=(True, {"level": "healthy"})):
                    with patch.object(monitor.checker, "check_log_size", return_value=(True, {"level": "healthy"})):
                        alerts = monitor.run_checks()
        assert monitor.current_session.auto_remediations >= 1


class TestProactiveMonitorShouldRunCheck:

    def test_should_run_when_never_checked(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        check = HealthCheck(
            name="test",
            check_type="disk",
            threshold={},
            check_interval=300,
            auto_remediate=False,
            remediation_action=None,
            last_check=None
        )
        assert monitor._should_run_check(check) is True

    def test_should_not_run_when_recently_checked(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        check = HealthCheck(
            name="test",
            check_type="disk",
            threshold={},
            check_interval=300,
            auto_remediate=False,
            remediation_action=None,
            last_check=datetime.now().isoformat()
        )
        assert monitor._should_run_check(check) is False

    def test_should_run_when_overdue(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        past = (datetime.now() - timedelta(seconds=400)).isoformat()
        check = HealthCheck(
            name="test",
            check_type="disk",
            threshold={},
            check_interval=300,
            auto_remediate=False,
            remediation_action=None,
            last_check=past
        )
        assert monitor._should_run_check(check) is True


class TestProactiveMonitorCreateAlert:

    def test_creates_alert_with_correct_level(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        check = HealthCheck("c", "disk", {}, 300, False, None)
        alert = monitor._create_alert(check, {"level": "critical", "message": "disk full"})
        assert alert.level == AlertLevel.CRITICAL
        assert alert.source == "c"

    def test_creates_warning_alert(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        check = HealthCheck("c", "disk", {}, 300, False, None)
        alert = monitor._create_alert(check, {"level": "warning", "message": "disk high"})
        assert alert.level == AlertLevel.WARNING

    def test_alert_has_unique_id(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        check = HealthCheck("c", "disk", {}, 300, False, None)
        a1 = monitor._create_alert(check, {"level": "warning", "message": "high"})
        a2 = monitor._create_alert(check, {"level": "warning", "message": "high"})
        assert a1.alert_id != a2.alert_id


class TestProactiveMonitorIsRecent:

    def test_recent_timestamp(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        now = datetime.now().isoformat()
        assert monitor._is_recent(now) is True

    def test_old_timestamp(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        old = (datetime.now() - timedelta(hours=25)).isoformat()
        assert monitor._is_recent(old) is False

    def test_invalid_timestamp(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        assert monitor._is_recent("not-a-date") is False


class TestProactiveMonitorPersistence:

    def test_loads_saved_checks(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        count = len(monitor.health_checks)
        # Reload
        monitor2 = ProactiveMonitor(logger=_make_logger(), storage_dir=tmp_path)
        assert len(monitor2.health_checks) == count

    def test_saves_and_loads_alerts(self, tmp_path):
        monitor = _make_monitor(tmp_path)
        monitor.start_monitoring()
        with patch.object(monitor.checker, "check_disk_space", return_value=(False, {"level": "warning", "message": "high", "usage": 85})):
            with patch.object(monitor.checker, "check_memory_usage", return_value=(True, {"level": "healthy"})):
                with patch.object(monitor.checker, "check_log_size", return_value=(True, {"level": "healthy"})):
                    alerts = monitor.run_checks()
        assert monitor.alerts_file.exists()


# ===========================================================================
# get_proactive_monitor singleton
# ===========================================================================

class TestGetProactiveMonitor:

    def test_returns_instance(self, tmp_path):
        import zenus_core.monitoring.proactive_monitor as mod
        mod._proactive_monitor = None
        monitor = get_proactive_monitor(_make_logger())
        assert isinstance(monitor, ProactiveMonitor)

    def test_returns_same_instance(self, tmp_path):
        import zenus_core.monitoring.proactive_monitor as mod
        mod._proactive_monitor = None
        m1 = get_proactive_monitor(_make_logger())
        m2 = get_proactive_monitor(_make_logger())
        assert m1 is m2
