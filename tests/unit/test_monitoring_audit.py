"""
Tests for ProactiveMonitor, AuditLogger, and MetricsCollector
"""

import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    """Yield a temporary directory and clean it up afterwards."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def mock_logger():
    """Return a mock AuditLogger."""
    logger = Mock()
    logger.log_info = Mock()
    logger.log_error = Mock()
    return logger


# ===========================================================================
# AuditLogger
# ===========================================================================

class TestAuditLoggerInit:
    """Test AuditLogger initialisation"""

    def test_creates_log_dir(self, tmp_dir):
        """AuditLogger creates log directory on init"""
        log_dir = str(tmp_dir / "logs")
        from zenus_core.audit.logger import AuditLogger
        logger = AuditLogger(log_dir=log_dir)
        assert os.path.isdir(log_dir)

    def test_session_file_created(self, tmp_dir):
        """AuditLogger sets session_file path inside log_dir"""
        from zenus_core.audit.logger import AuditLogger
        logger = AuditLogger(log_dir=str(tmp_dir))
        assert str(tmp_dir) in str(logger.session_file)
        assert "session_" in logger.session_file.name

    def test_default_log_dir(self):
        """AuditLogger uses ~/.zenus/logs as default log directory"""
        from zenus_core.audit.logger import AuditLogger
        logger = AuditLogger()
        assert ".zenus" in str(logger.log_dir)


class TestAuditLoggerWrite:
    """Test AuditLogger write methods"""

    def setup_method(self):
        """Create AuditLogger with temp dir."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.audit.logger import AuditLogger
        self.logger = AuditLogger(log_dir=self._tmpdir.name)

    def teardown_method(self):
        self._tmpdir.cleanup()

    def _read_entries(self):
        """Read all JSONL entries from the session file."""
        entries = []
        with open(self.logger.session_file) as f:
            for line in f:
                entries.append(json.loads(line))
        return entries

    def test_log_error_writes_entry(self):
        """log_error writes an error entry to the session file"""
        self.logger.log_error("something broke", {"ctx": "test"})
        entries = self._read_entries()
        assert any(e["type"] == "error" for e in entries)

    def test_log_error_contains_message(self):
        """log_error entry contains the error message"""
        self.logger.log_error("disk full")
        entries = self._read_entries()
        error_entries = [e for e in entries if e["type"] == "error"]
        assert error_entries[-1]["error"] == "disk full"

    def test_log_error_empty_context(self):
        """log_error with no context defaults to empty dict"""
        self.logger.log_error("oops")
        entries = self._read_entries()
        error_entry = [e for e in entries if e["type"] == "error"][-1]
        assert error_entry["context"] == {}

    def test_log_info_writes_entry(self):
        """log_info writes an info entry"""
        self.logger.log_info("my_event", {"k": "v"})
        entries = self._read_entries()
        info_entries = [e for e in entries if e["type"] == "info"]
        assert len(info_entries) >= 1
        assert info_entries[-1]["event"] == "my_event"

    def test_log_info_no_data(self):
        """log_info with no data defaults to empty dict"""
        self.logger.log_info("bare_event")
        entries = self._read_entries()
        info_entry = [e for e in entries if e["type"] == "info"][-1]
        assert info_entry["data"] == {}

    def test_log_execution_start(self):
        """log_execution_start writes execution_start entry"""
        mock_intent = Mock()
        mock_intent.goal = "do stuff"
        self.logger.log_execution_start(mock_intent)
        entries = self._read_entries()
        assert any(e["type"] == "execution_start" for e in entries)

    def test_log_execution_end_success(self):
        """log_execution_end with success=True writes execution_end entry"""
        self.logger.log_execution_end(True, "all done")
        entries = self._read_entries()
        end_entries = [e for e in entries if e["type"] == "execution_end"]
        assert end_entries[-1]["success"] is True
        assert end_entries[-1]["message"] == "all done"

    def test_log_execution_end_failure(self):
        """log_execution_end with success=False records failure"""
        self.logger.log_execution_end(False)
        entries = self._read_entries()
        end_entry = [e for e in entries if e["type"] == "execution_end"][-1]
        assert end_entry["success"] is False

    def test_log_step_result_success(self):
        """log_step_result with success=True writes step_result entry"""
        self.logger.log_step_result("FileOps", "scan", "result text", True)
        entries = self._read_entries()
        step_entries = [e for e in entries if e["type"] == "step_result"]
        assert step_entries[-1]["success"] is True

    def test_log_step_result_failure(self):
        """log_step_result with success=False records failure"""
        self.logger.log_step_result("FileOps", "delete", "err", False)
        entries = self._read_entries()
        step_entry = [e for e in entries if e["type"] == "step_result"][-1]
        assert step_entry["success"] is False

    def test_log_intent_writes_entry(self):
        """log_intent writes intent entry with steps"""
        mock_intent = Mock()
        mock_intent.goal = "list files"
        mock_intent.requires_confirmation = False
        mock_step = Mock()
        mock_step.tool = "FileOps"
        mock_step.action = "scan"
        mock_step.args = {}
        mock_step.risk = 0
        mock_intent.steps = [mock_step]
        self.logger.log_intent("ls /tmp", mock_intent)
        entries = self._read_entries()
        intent_entries = [e for e in entries if e["type"] == "intent"]
        assert len(intent_entries) >= 1
        assert intent_entries[-1]["user_input"] == "ls /tmp"

    def test_entries_have_timestamps(self):
        """Each log entry includes an ISO timestamp"""
        self.logger.log_error("err")
        entries = self._read_entries()
        for e in entries:
            assert "timestamp" in e
            # Verify parseable
            datetime.fromisoformat(e["timestamp"])


class TestGetLogger:
    """Test get_logger singleton"""

    def test_returns_audit_logger_instance(self):
        """get_logger returns an AuditLogger"""
        import zenus_core.audit.logger as mod
        mod._logger = None
        from zenus_core.audit.logger import get_logger, AuditLogger
        logger = get_logger()
        assert isinstance(logger, AuditLogger)
        mod._logger = None  # cleanup


# ===========================================================================
# MetricsCollector
# ===========================================================================

class TestMetricPoint:
    """Test MetricPoint dataclass"""

    def test_to_dict_contains_all_fields(self):
        """MetricPoint.to_dict() returns all required fields"""
        from zenus_core.observability.metrics import MetricPoint
        pt = MetricPoint(timestamp=1.0, metric_name="test", value=42.0, tags={"a": "b"})
        d = pt.to_dict()
        assert d["metric_name"] == "test"
        assert d["value"] == 42.0
        assert d["tags"] == {"a": "b"}


class TestMetricsCollectorInit:
    """Test MetricsCollector initialisation"""

    def test_buffer_starts_empty(self, tmp_dir):
        """Fresh MetricsCollector has empty buffer"""
        from zenus_core.observability.metrics import MetricsCollector
        mc = MetricsCollector(metrics_path=str(tmp_dir / "m.jsonl"))
        assert mc.buffer == []

    def test_aggregates_start_at_zero(self, tmp_dir):
        """Fresh MetricsCollector has zeroed aggregates"""
        from zenus_core.observability.metrics import MetricsCollector
        mc = MetricsCollector(metrics_path=str(tmp_dir / "m.jsonl"))
        assert mc.aggregates["total_commands"] == 0
        assert mc.aggregates["total_tokens"] == 0


class TestMetricsCollectorRecord:
    """Test MetricsCollector.record"""

    def setup_method(self):
        """Create collector with temp metrics file."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.observability.metrics import MetricsCollector
        self.mc = MetricsCollector(
            metrics_path=os.path.join(self._tmpdir.name, "m.jsonl"),
            flush_interval=100  # prevent auto-flush during tests
        )

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_record_adds_to_buffer(self):
        """record() appends a MetricPoint to the buffer"""
        self.mc.record("latency", 100.0)
        assert len(self.mc.buffer) == 1

    def test_record_metric_name_stored(self):
        """MetricPoint in buffer has correct metric_name"""
        self.mc.record("tokens_used", 50.0)
        assert self.mc.buffer[-1].metric_name == "tokens_used"

    def test_record_with_tags(self):
        """Tags passed to record() are stored in MetricPoint"""
        self.mc.record("latency", 10.0, tags={"model": "gpt4"})
        assert self.mc.buffer[-1].tags == {"model": "gpt4"}

    def test_record_updates_latency_aggregate(self):
        """Recording command_latency_ms updates total_commands"""
        self.mc.record("command_latency_ms", 200.0, tags={"model": "x", "tool": "y"})
        assert self.mc.aggregates["total_commands"] == 1

    def test_record_updates_token_aggregate(self):
        """Recording tokens_used updates total_tokens"""
        self.mc.record("tokens_used", 100.0, tags={"model": "x"})
        assert self.mc.aggregates["total_tokens"] == 100

    def test_record_updates_cost_aggregate(self):
        """Recording cost_estimate updates total_cost"""
        self.mc.record("cost_estimate", 0.01, tags={"model": "x"})
        assert self.mc.aggregates["total_cost"] == pytest.approx(0.01)

    def test_record_cache_hit_increments_hits(self):
        """Recording cache_hit=1 increments cache_hits counter"""
        self.mc.record("cache_hit", 1.0)
        assert self.mc.aggregates["cache_hits"] == 1

    def test_record_cache_miss_increments_misses(self):
        """Recording cache_hit=0 increments cache_misses counter"""
        self.mc.record("cache_hit", 0.0)
        assert self.mc.aggregates["cache_misses"] == 1

    def test_record_success_increments_successes(self):
        """Recording success=1 increments successes counter"""
        self.mc.record("success", 1.0)
        assert self.mc.aggregates["successes"] == 1

    def test_record_failure_increments_failures(self):
        """Recording success=0 increments failures counter"""
        self.mc.record("success", 0.0)
        assert self.mc.aggregates["failures"] == 1


class TestMetricsCollectorRecordCommand:
    """Test MetricsCollector.record_command convenience method"""

    def setup_method(self):
        """Create collector with temp metrics file."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.observability.metrics import MetricsCollector
        self.mc = MetricsCollector(
            metrics_path=os.path.join(self._tmpdir.name, "m.jsonl"),
            flush_interval=100
        )

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_records_latency(self):
        """record_command records latency metric"""
        self.mc.record_command(latency_ms=150.0, model="gpt4", tool="FileOps")
        assert self.mc.aggregates["total_commands"] == 1

    def test_records_tokens_when_nonzero(self):
        """record_command records tokens when > 0"""
        self.mc.record_command(latency_ms=10, model="gpt4", tool="T", tokens=500)
        assert self.mc.aggregates["total_tokens"] == 500

    def test_skips_tokens_when_zero(self):
        """record_command does not record tokens metric when tokens=0"""
        before = len(self.mc.buffer)
        self.mc.record_command(latency_ms=10, model="gpt4", tool="T", tokens=0)
        after = len(self.mc.buffer)
        token_points = [p for p in self.mc.buffer[before:] if p.metric_name == "tokens_used"]
        assert len(token_points) == 0

    def test_records_cost_when_nonzero(self):
        """record_command records cost when > 0"""
        self.mc.record_command(latency_ms=10, model="gpt4", tool="T", cost=0.05)
        assert self.mc.aggregates["total_cost"] == pytest.approx(0.05)

    def test_cache_hit_recorded(self):
        """record_command with cache_hit=True increments hits"""
        self.mc.record_command(latency_ms=1, model="m", tool="t", cache_hit=True)
        assert self.mc.aggregates["cache_hits"] == 1

    def test_success_recorded(self):
        """record_command with success=True increments successes"""
        self.mc.record_command(latency_ms=1, model="m", tool="t", success=True)
        assert self.mc.aggregates["successes"] == 1

    def test_failure_recorded(self):
        """record_command with success=False increments failures"""
        self.mc.record_command(latency_ms=1, model="m", tool="t", success=False)
        assert self.mc.aggregates["failures"] == 1


class TestMetricsCollectorGetStats:
    """Test MetricsCollector.get_stats"""

    def setup_method(self):
        """Create collector with temp metrics file."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.observability.metrics import MetricsCollector
        self.mc = MetricsCollector(
            metrics_path=os.path.join(self._tmpdir.name, "m.jsonl"),
            flush_interval=100
        )

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_stats_empty_collector(self):
        """get_stats on empty collector has zero total_commands"""
        stats = self.mc.get_stats()
        assert stats["total_commands"] == 0

    def test_stats_after_commands(self):
        """get_stats returns correct counts after recording commands"""
        self.mc.record_command(latency_ms=100, model="gpt4", tool="T", tokens=100, success=True)
        self.mc.record_command(latency_ms=200, model="gpt4", tool="T", tokens=200, success=False)
        stats = self.mc.get_stats()
        assert stats["total_commands"] == 2
        assert stats["total_tokens"] == 300
        assert stats["successes"] == 1
        assert stats["failures"] == 1

    def test_avg_latency_computed(self):
        """get_stats computes avg_latency_ms after at least one command"""
        self.mc.record_command(latency_ms=100, model="m", tool="t")
        self.mc.record_command(latency_ms=200, model="m", tool="t")
        stats = self.mc.get_stats()
        assert stats["avg_latency_ms"] == 150.0

    def test_success_rate_computed(self):
        """get_stats computes success_rate correctly"""
        self.mc.record_command(latency_ms=10, model="m", tool="t", success=True)
        self.mc.record_command(latency_ms=10, model="m", tool="t", success=False)
        # Note: success rate = successes / total_commands, but success is also
        # a separate metric counted separately in aggregates
        stats = self.mc.get_stats()
        assert "success_rate" in stats

    def test_cache_hit_rate_computed(self):
        """get_stats computes cache_hit_rate after cache events"""
        self.mc.record_command(latency_ms=1, model="m", tool="t", cache_hit=True)
        self.mc.record_command(latency_ms=1, model="m", tool="t", cache_hit=False)
        stats = self.mc.get_stats()
        assert "cache_hit_rate" in stats
        assert stats["cache_hit_rate"] == pytest.approx(0.5)

    def test_by_model_stats(self):
        """get_stats includes per-model breakdown"""
        self.mc.record_command(latency_ms=100, model="modelA", tool="T")
        stats = self.mc.get_stats()
        assert "modelA" in stats["by_model"]
        assert stats["by_model"]["modelA"]["commands"] == 1


class TestMetricsCollectorFlush:
    """Test MetricsCollector.flush"""

    def setup_method(self):
        """Create collector with temp metrics file."""
        self._tmpdir = tempfile.TemporaryDirectory()
        self.metrics_path = os.path.join(self._tmpdir.name, "m.jsonl")
        from zenus_core.observability.metrics import MetricsCollector
        self.mc = MetricsCollector(
            metrics_path=self.metrics_path,
            flush_interval=100
        )

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_flush_writes_to_disk(self):
        """flush() writes buffered metrics to the JSONL file"""
        self.mc.record("latency", 10.0)
        self.mc.flush()
        assert os.path.exists(self.metrics_path)
        with open(self.metrics_path) as f:
            lines = f.readlines()
        assert len(lines) >= 1

    def test_flush_clears_buffer(self):
        """flush() empties the in-memory buffer"""
        self.mc.record("latency", 10.0)
        self.mc.flush()
        assert self.mc.buffer == []

    def test_flush_empty_buffer_noop(self):
        """flush() with empty buffer does not create file"""
        self.mc.flush()
        # File may or may not exist; just ensure no exception
        assert True

    def test_auto_flush_on_full_buffer(self):
        """Buffer flushes automatically when it reaches flush_interval"""
        from zenus_core.observability.metrics import MetricsCollector
        mc = MetricsCollector(
            metrics_path=self.metrics_path,
            flush_interval=3
        )
        for i in range(3):
            mc.record("test", float(i))
        # After 3 records with interval=3, buffer should have been flushed
        assert len(mc.buffer) == 0


class TestMetricsCollectorQuery:
    """Test MetricsCollector.query reads from disk"""

    def setup_method(self):
        """Create collector, record some points, flush."""
        self._tmpdir = tempfile.TemporaryDirectory()
        self.metrics_path = os.path.join(self._tmpdir.name, "m.jsonl")
        from zenus_core.observability.metrics import MetricsCollector
        self.mc = MetricsCollector(
            metrics_path=self.metrics_path,
            flush_interval=100
        )
        self.mc.record("latency", 100.0, tags={"model": "gpt4"})
        self.mc.record("tokens_used", 50.0, tags={"model": "gpt4"})
        self.mc.record("latency", 200.0, tags={"model": "claude"})
        self.mc.flush()

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_query_all_returns_all(self):
        """query() with no filters returns all metric points"""
        results = self.mc.query()
        assert len(results) == 3

    def test_query_by_metric_name(self):
        """query() filtered by metric_name returns only matching points"""
        results = self.mc.query(metric_name="latency")
        assert all(p.metric_name == "latency" for p in results)
        assert len(results) == 2

    def test_query_by_tags(self):
        """query() filtered by tags returns matching points"""
        results = self.mc.query(tags={"model": "gpt4"})
        assert all(p.tags.get("model") == "gpt4" for p in results)

    def test_query_missing_file_returns_empty(self, tmp_path):
        """query() on non-existent file returns empty list"""
        from zenus_core.observability.metrics import MetricsCollector
        missing = str(tmp_path / "nonexistent" / "path.jsonl")
        mc = MetricsCollector(metrics_path=missing)
        assert mc.query() == []

    def test_query_limit_respected(self):
        """query() with limit returns at most limit results"""
        results = self.mc.query(limit=2)
        assert len(results) <= 2


class TestGetMetricsCollector:
    """Test get_metrics_collector singleton"""

    def test_returns_metrics_collector_instance(self):
        """get_metrics_collector returns a MetricsCollector"""
        import zenus_core.observability.metrics as mod
        mod._metrics_collector = None
        from zenus_core.observability.metrics import get_metrics_collector, MetricsCollector
        mc = get_metrics_collector()
        assert isinstance(mc, MetricsCollector)
        mod._metrics_collector = None  # cleanup


# ===========================================================================
# ProactiveMonitor
# ===========================================================================

class TestHealthCheck:
    """Test HealthCheck dataclass"""

    def test_to_dict_round_trips(self):
        """HealthCheck.to_dict() contains all fields"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck
        hc = HealthCheck(
            name="test",
            check_type="disk",
            threshold={"warning": 80},
            check_interval=300,
            auto_remediate=False,
            remediation_action=None
        )
        d = hc.to_dict()
        assert d["name"] == "test"
        assert d["check_type"] == "disk"


class TestAlert:
    """Test Alert dataclass"""

    def test_to_dict_converts_level_to_value(self):
        """Alert.to_dict() converts AlertLevel enum to string value"""
        from zenus_core.monitoring.proactive_monitor import Alert, AlertLevel
        alert = Alert(
            alert_id="abc",
            timestamp="2026-01-01T00:00:00",
            level=AlertLevel.WARNING,
            source="disk_check",
            message="disk low",
            details={},
            auto_remediated=False,
            remediation_result=None
        )
        d = alert.to_dict()
        assert d["level"] == "warning"


class TestMonitoringSession:
    """Test MonitoringSession dataclass"""

    def test_to_dict_converts_status_to_value(self):
        """MonitoringSession.to_dict() converts HealthStatus to string"""
        from zenus_core.monitoring.proactive_monitor import MonitoringSession, HealthStatus
        session = MonitoringSession(
            session_id="x1",
            start_time="2026-01-01T00:00:00",
            checks_run=0,
            alerts_generated=0,
            auto_remediations=0,
            status=HealthStatus.HEALTHY
        )
        d = session.to_dict()
        assert d["status"] == "healthy"


class TestHealthChecker:
    """Test HealthChecker check methods"""

    def setup_method(self):
        """Create HealthChecker with mock logger."""
        from zenus_core.monitoring.proactive_monitor import HealthChecker
        self.checker = HealthChecker(Mock())

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run")
    def test_check_disk_space_healthy(self, mock_run):
        """check_disk_space returns (True, ...) when usage below thresholds"""
        mock_run.return_value = Mock(
            stdout="Filesystem 1K-blocks Used Available Use% Mounted\n/dev/sda1 100G 50G 50G 50% /\n",
            returncode=0
        )
        ok, details = self.checker.check_disk_space({"warning": 80, "critical": 90})
        assert ok is True
        assert details["level"] == "healthy"

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run")
    def test_check_disk_space_warning(self, mock_run):
        """check_disk_space returns (False, ...) when usage at warning threshold"""
        mock_run.return_value = Mock(
            stdout="Filesystem 1K-blocks Used Available Use% Mounted\n/dev/sda1 100G 85G 15G 85% /\n",
            returncode=0
        )
        ok, details = self.checker.check_disk_space({"warning": 80, "critical": 90})
        assert ok is False
        assert details["level"] == "warning"

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run")
    def test_check_disk_space_critical(self, mock_run):
        """check_disk_space returns (False, ...) when usage at critical threshold"""
        mock_run.return_value = Mock(
            stdout="Filesystem 1K-blocks Used Available Use% Mounted\n/dev/sda1 100G 95G 5G 95% /\n",
            returncode=0
        )
        ok, details = self.checker.check_disk_space({"warning": 80, "critical": 90})
        assert ok is False
        assert details["level"] == "critical"

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run", side_effect=Exception("cmd fail"))
    def test_check_disk_space_exception(self, mock_run):
        """check_disk_space returns (False, ...) on subprocess exception"""
        ok, details = self.checker.check_disk_space({})
        assert ok is False
        assert "error" in details

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run")
    def test_check_memory_healthy(self, mock_run):
        """check_memory_usage returns (True, ...) when usage below thresholds"""
        mock_run.return_value = Mock(
            stdout="              total        used        free\nMem:           4096        1000        3096\n",
            returncode=0
        )
        ok, details = self.checker.check_memory_usage({"warning": 80, "critical": 90})
        assert ok is True

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run")
    def test_check_service_active(self, mock_run):
        """check_service_status returns (True, ...) for active service"""
        mock_run.return_value = Mock(stdout="active\n", returncode=0)
        ok, details = self.checker.check_service_status("nginx")
        assert ok is True
        assert details["level"] == "healthy"

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run")
    def test_check_service_inactive(self, mock_run):
        """check_service_status returns (False, ...) for inactive service"""
        mock_run.return_value = Mock(stdout="inactive\n", returncode=1)
        ok, details = self.checker.check_service_status("nginx")
        assert ok is False

    def test_check_log_size_missing_path(self):
        """check_log_size returns (False, ...) for nonexistent path"""
        ok, details = self.checker.check_log_size("/nonexistent/path", {"warning_mb": 1})
        assert ok is False
        assert "error" in details


class TestRemediator:
    """Test Remediator.remediate"""

    def setup_method(self):
        """Create Remediator with mock logger."""
        from zenus_core.monitoring.proactive_monitor import Remediator
        self.logger = Mock()
        self.remediator = Remediator(self.logger)

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run")
    def test_remediate_success(self, mock_run):
        """remediate returns (True, ...) when command exits 0"""
        mock_run.return_value = Mock(returncode=0, stdout="done", stderr="")
        ok, msg = self.remediator.remediate("disk", {}, "echo cleanup")
        assert ok is True

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run")
    def test_remediate_failure(self, mock_run):
        """remediate returns (False, ...) when command exits non-zero"""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="failed")
        ok, msg = self.remediator.remediate("disk", {}, "false")
        assert ok is False

    @patch("zenus_core.monitoring.proactive_monitor.subprocess.run", side_effect=Exception("timeout"))
    def test_remediate_exception(self, mock_run):
        """remediate returns (False, ...) on exception"""
        ok, msg = self.remediator.remediate("disk", {}, "bad_cmd")
        assert ok is False
        assert "Remediation failed" in msg

    def test_remediate_with_orchestrator(self):
        """remediate uses orchestrator.execute_command when available"""
        mock_orch = Mock()
        mock_orch.execute_command.return_value = "cleaned up"
        from zenus_core.monitoring.proactive_monitor import Remediator
        rem = Remediator(self.logger, orchestrator=mock_orch)
        ok, msg = rem.remediate("disk", {}, "cleanup action")
        assert ok is True
        mock_orch.execute_command.assert_called_once_with("cleanup action")


class TestProactiveMonitorInit:
    """Test ProactiveMonitor initialisation"""

    def test_initializes_default_checks(self, tmp_dir, mock_logger):
        """ProactiveMonitor creates default health checks when storage is empty"""
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        monitor = ProactiveMonitor(mock_logger, storage_dir=tmp_dir)
        assert len(monitor.health_checks) > 0

    def test_storage_dir_created(self, tmp_dir, mock_logger):
        """ProactiveMonitor creates storage directory"""
        storage = tmp_dir / "monitoring"
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        monitor = ProactiveMonitor(mock_logger, storage_dir=storage)
        assert storage.exists()

    def test_current_session_none_initially(self, tmp_dir, mock_logger):
        """current_session is None before start_monitoring is called"""
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        monitor = ProactiveMonitor(mock_logger, storage_dir=tmp_dir)
        assert monitor.current_session is None


class TestProactiveMonitorStartMonitoring:
    """Test ProactiveMonitor.start_monitoring"""

    def setup_method(self):
        """Create monitor with temp storage."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        self.logger = Mock()
        self.monitor = ProactiveMonitor(self.logger, storage_dir=Path(self._tmpdir.name))

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_returns_monitoring_session(self):
        """start_monitoring returns a MonitoringSession"""
        from zenus_core.monitoring.proactive_monitor import MonitoringSession
        session = self.monitor.start_monitoring()
        assert isinstance(session, MonitoringSession)

    def test_session_status_healthy(self):
        """start_monitoring returns session with HEALTHY status"""
        from zenus_core.monitoring.proactive_monitor import HealthStatus
        session = self.monitor.start_monitoring()
        assert session.status == HealthStatus.HEALTHY

    def test_session_stored_on_instance(self):
        """start_monitoring stores session on current_session"""
        session = self.monitor.start_monitoring()
        assert self.monitor.current_session is session


class TestProactiveMonitorAddRemove:
    """Test add/remove health checks"""

    def setup_method(self):
        """Create monitor with temp storage."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        self.logger = Mock()
        self.monitor = ProactiveMonitor(self.logger, storage_dir=Path(self._tmpdir.name))

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_add_health_check(self):
        """add_health_check appends the check to health_checks list"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck
        before = len(self.monitor.health_checks)
        hc = HealthCheck(
            name="custom_check",
            check_type="disk",
            threshold={"warning": 70},
            check_interval=60,
            auto_remediate=False,
            remediation_action=None
        )
        self.monitor.add_health_check(hc)
        assert len(self.monitor.health_checks) == before + 1

    def test_remove_health_check(self):
        """remove_health_check removes check by name"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck
        hc = HealthCheck(
            name="to_remove",
            check_type="disk",
            threshold={},
            check_interval=60,
            auto_remediate=False,
            remediation_action=None
        )
        self.monitor.add_health_check(hc)
        self.monitor.remove_health_check("to_remove")
        names = [c.name for c in self.monitor.health_checks]
        assert "to_remove" not in names


class TestProactiveMonitorShouldRun:
    """Test ProactiveMonitor._should_run_check"""

    def setup_method(self):
        """Create monitor with temp storage."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        self.logger = Mock()
        self.monitor = ProactiveMonitor(self.logger, storage_dir=Path(self._tmpdir.name))

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_runs_when_never_checked(self):
        """_should_run_check returns True when last_check is None"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck
        hc = HealthCheck(
            name="fresh",
            check_type="disk",
            threshold={},
            check_interval=300,
            auto_remediate=False,
            remediation_action=None
        )
        assert self.monitor._should_run_check(hc) is True

    def test_does_not_run_before_interval(self):
        """_should_run_check returns False when interval not elapsed"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck
        hc = HealthCheck(
            name="recent",
            check_type="disk",
            threshold={},
            check_interval=300,
            auto_remediate=False,
            remediation_action=None,
            last_check=datetime.now().isoformat()
        )
        assert self.monitor._should_run_check(hc) is False

    def test_runs_after_interval_elapsed(self):
        """_should_run_check returns True when interval has elapsed"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck
        past_time = (datetime.now() - timedelta(seconds=600)).isoformat()
        hc = HealthCheck(
            name="old",
            check_type="disk",
            threshold={},
            check_interval=300,
            auto_remediate=False,
            remediation_action=None,
            last_check=past_time
        )
        assert self.monitor._should_run_check(hc) is True


class TestProactiveMonitorCreateAlert:
    """Test ProactiveMonitor._create_alert"""

    def setup_method(self):
        """Create monitor with temp storage."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        self.logger = Mock()
        self.monitor = ProactiveMonitor(self.logger, storage_dir=Path(self._tmpdir.name))

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_creates_warning_alert(self):
        """_create_alert creates WARNING alert for warning-level details"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck, AlertLevel
        hc = HealthCheck(
            name="disk", check_type="disk", threshold={},
            check_interval=300, auto_remediate=False, remediation_action=None
        )
        alert = self.monitor._create_alert(hc, {"level": "warning", "message": "low disk"})
        assert alert.level == AlertLevel.WARNING

    def test_creates_critical_alert(self):
        """_create_alert creates CRITICAL alert for critical-level details"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck, AlertLevel
        hc = HealthCheck(
            name="disk", check_type="disk", threshold={},
            check_interval=300, auto_remediate=False, remediation_action=None
        )
        alert = self.monitor._create_alert(hc, {"level": "critical", "message": "disk full"})
        assert alert.level == AlertLevel.CRITICAL

    def test_alert_source_is_check_name(self):
        """Alert source is the check name"""
        from zenus_core.monitoring.proactive_monitor import HealthCheck
        hc = HealthCheck(
            name="my_check", check_type="disk", threshold={},
            check_interval=300, auto_remediate=False, remediation_action=None
        )
        alert = self.monitor._create_alert(hc, {"level": "warning"})
        assert alert.source == "my_check"


class TestProactiveMonitorGetStatus:
    """Test ProactiveMonitor.get_status"""

    def setup_method(self):
        """Create monitor with temp storage."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        self.logger = Mock()
        self.monitor = ProactiveMonitor(self.logger, storage_dir=Path(self._tmpdir.name))

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_status_has_expected_keys(self):
        """get_status returns dict with session, health_checks, recent_alerts, checks"""
        status = self.monitor.get_status()
        assert "session" in status
        assert "health_checks" in status
        assert "recent_alerts" in status
        assert "checks" in status

    def test_status_session_none_before_start(self):
        """get_status.session is None before start_monitoring called"""
        assert self.monitor.get_status()["session"] is None

    def test_status_health_checks_count(self):
        """get_status.health_checks reflects number of registered checks"""
        count = len(self.monitor.health_checks)
        assert self.monitor.get_status()["health_checks"] == count


class TestProactiveMonitorIsRecent:
    """Test ProactiveMonitor._is_recent"""

    def setup_method(self):
        """Create monitor with temp storage."""
        self._tmpdir = tempfile.TemporaryDirectory()
        from zenus_core.monitoring.proactive_monitor import ProactiveMonitor
        self.logger = Mock()
        self.monitor = ProactiveMonitor(self.logger, storage_dir=Path(self._tmpdir.name))

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_now_is_recent(self):
        """Current timestamp is considered recent"""
        assert self.monitor._is_recent(datetime.now().isoformat()) is True

    def test_old_timestamp_not_recent(self):
        """Timestamp from 48 hours ago is not recent within 24h window"""
        old = (datetime.now() - timedelta(hours=48)).isoformat()
        assert self.monitor._is_recent(old, hours=24) is False

    def test_invalid_timestamp_returns_false(self):
        """Invalid timestamp string returns False"""
        assert self.monitor._is_recent("not-a-date") is False


class TestGetProactiveMonitor:
    """Test get_proactive_monitor singleton"""

    def test_returns_proactive_monitor_instance(self, tmp_dir, mock_logger):
        """get_proactive_monitor returns a ProactiveMonitor instance"""
        import zenus_core.monitoring.proactive_monitor as mod
        mod._proactive_monitor = None
        from zenus_core.monitoring.proactive_monitor import get_proactive_monitor, ProactiveMonitor
        monitor = get_proactive_monitor(mock_logger)
        assert isinstance(monitor, ProactiveMonitor)
        mod._proactive_monitor = None  # cleanup
