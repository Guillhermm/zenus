"""
Tests for PatternDetector and PatternMemory
"""

import os
import pytest
from datetime import datetime, timedelta

from zenus_core.brain.pattern_detector import (
    PatternDetector,
    DetectedPattern,
    get_pattern_detector,
)
from zenus_core.brain.pattern_memory import (
    PatternMemory,
    get_pattern_memory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(dt: datetime) -> str:
    """Format a datetime as an ISO timestamp string."""
    return dt.isoformat()


def _record(user_input: str, dt: datetime, intent_steps=None) -> dict:
    """Build a minimal history record."""
    record = {"user_input": user_input, "timestamp": _ts(dt)}
    if intent_steps is not None:
        record["intent"] = {"steps": intent_steps}
    return record


def _daily_records(command: str, base: datetime, count: int) -> list:
    """Return `count` records spaced ~24 h apart."""
    return [_record(command, base + timedelta(hours=24 * i)) for i in range(count)]


def _weekly_records(command: str, base: datetime, count: int) -> list:
    """Return `count` records spaced ~7 days apart."""
    return [_record(command, base + timedelta(hours=168 * i)) for i in range(count)]


def _monthly_records(command: str, base: datetime, count: int) -> list:
    """Return `count` records spaced ~30 days (720 h) apart."""
    return [_record(command, base + timedelta(hours=720 * i)) for i in range(count)]


# ---------------------------------------------------------------------------
# Tests: PatternDetector.detect_patterns — general
# ---------------------------------------------------------------------------

class TestDetectPatternsGeneral:
    def test_empty_history_returns_empty_list(self):
        """No history produces no patterns."""
        pd = PatternDetector()
        assert pd.detect_patterns([]) == []

    def test_below_min_occurrences_returns_empty(self):
        """Fewer than min_occurrences records in lookback period yields nothing."""
        pd = PatternDetector()
        now = datetime.now()
        history = [_record("backup files", now - timedelta(days=1)) for _ in range(2)]
        assert pd.detect_patterns(history) == []

    def test_results_sorted_by_confidence_descending(self):
        """Returned patterns are sorted highest confidence first."""
        pd = PatternDetector()
        now = datetime.now()
        history = _daily_records("backup files", now - timedelta(days=40), 10)
        patterns = pd.detect_patterns(history, lookback_days=30)
        confidences = [p.confidence for p in patterns]
        assert confidences == sorted(confidences, reverse=True)

    def test_records_outside_lookback_are_excluded(self):
        """Records older than lookback_days are ignored."""
        pd = PatternDetector()
        now = datetime.now()
        old_history = [_record("old command", now - timedelta(days=60)) for _ in range(5)]
        assert pd.detect_patterns(old_history, lookback_days=30) == []

    def test_invalid_timestamps_are_skipped(self):
        """Records with unparseable timestamps do not cause errors."""
        pd = PatternDetector()
        now = datetime.now()
        good = _daily_records("backup files", now - timedelta(days=2), 3)
        bad = [{"user_input": "bad record", "timestamp": "NOT_A_DATE"}]
        # Should not raise; bad record is simply ignored
        pd.detect_patterns(good + bad)


# ---------------------------------------------------------------------------
# Tests: _detect_recurring_commands
# ---------------------------------------------------------------------------

class TestDetectRecurringCommands:
    def test_daily_pattern_detected(self):
        """Commands spaced ~24 h apart are labelled 'daily'."""
        pd = PatternDetector()
        now = datetime.now()
        history = _daily_records("backup files", now - timedelta(days=9), 10)
        patterns = pd._detect_recurring_commands(history)
        daily = [p for p in patterns if p.frequency == "daily"]
        assert len(daily) > 0

    def test_weekly_pattern_detected(self):
        """Commands spaced ~7 days apart are labelled 'weekly'."""
        pd = PatternDetector()
        now = datetime.now()
        history = _weekly_records("weekly report", now - timedelta(days=70), 10)
        patterns = pd._detect_recurring_commands(history)
        weekly = [p for p in patterns if p.frequency == "weekly"]
        assert len(weekly) > 0

    def test_monthly_pattern_detected(self):
        """Commands spaced ~30 days apart are labelled 'monthly'."""
        pd = PatternDetector()
        now = datetime.now()
        history = _monthly_records("monthly cleanup", now - timedelta(days=10 * 30), 10)
        patterns = pd._detect_recurring_commands(history)
        monthly = [p for p in patterns if p.frequency == "monthly"]
        assert len(monthly) > 0

    def test_recurring_pattern_has_cron_expression(self):
        """A detected recurring pattern includes a non-empty cron expression."""
        pd = PatternDetector()
        now = datetime.now()
        history = _daily_records("backup", now - timedelta(days=9), 10)
        patterns = pd._detect_recurring_commands(history)
        assert any(p.suggested_cron for p in patterns)

    def test_irregular_intervals_no_frequency(self):
        """Randomly spaced commands do not produce a frequency classification."""
        pd = PatternDetector()
        now = datetime.now()
        # Intervals of 1h, 50h, 5h, … – irregular
        offsets = [0, 1, 51, 56, 200, 201, 250]
        history = [_record("random cmd", now - timedelta(hours=h)) for h in offsets]
        patterns = pd._detect_recurring_commands(history)
        assert len(patterns) == 0

    def test_fewer_than_min_occurrences_not_detected(self):
        """Commands appearing only twice are below the threshold."""
        pd = PatternDetector()
        now = datetime.now()
        history = _daily_records("backup", now - timedelta(days=1), 2)
        patterns = pd._detect_recurring_commands(history)
        assert len(patterns) == 0

    def test_confidence_increases_with_occurrences(self):
        """More occurrences of the same command yield higher confidence."""
        pd = PatternDetector()
        now = datetime.now()
        history_3 = _daily_records("backup", now - timedelta(days=2), 3)
        history_8 = _daily_records("backup", now - timedelta(days=7), 8)

        p3 = pd._detect_recurring_commands(history_3)
        p8 = pd._detect_recurring_commands(history_8)

        if p3 and p8:
            assert p8[0].confidence >= p3[0].confidence

    def test_pattern_type_is_recurring(self):
        """Detected patterns carry pattern_type='recurring'."""
        pd = PatternDetector()
        now = datetime.now()
        history = _daily_records("backup", now - timedelta(days=9), 10)
        patterns = pd._detect_recurring_commands(history)
        assert all(p.pattern_type == "recurring" for p in patterns)


# ---------------------------------------------------------------------------
# Tests: _detect_workflows
# ---------------------------------------------------------------------------

class TestDetectWorkflows:
    def test_workflow_detected_for_repeated_sequence(self):
        """A sequence of commands repeated ≥ min_occurrences is a workflow."""
        pd = PatternDetector()
        now = datetime.now()

        history = []
        for i in range(5):
            base = now - timedelta(days=i * 2)
            history += [
                _record("git pull", base),
                _record("npm install", base + timedelta(minutes=5)),
                _record("npm test", base + timedelta(minutes=10)),
            ]

        # Sort history chronologically so time-window grouping works correctly
        history.sort(key=lambda r: r["timestamp"])

        patterns = pd._detect_workflows(history)
        workflow_patterns = [p for p in patterns if p.pattern_type == "workflow"]
        assert len(workflow_patterns) > 0

    def test_single_session_no_repeated_workflow(self):
        """A sequence executed only once is not flagged as a workflow."""
        pd = PatternDetector()
        now = datetime.now()
        history = [
            _record("git pull", now),
            _record("npm install", now + timedelta(minutes=5)),
            _record("npm test", now + timedelta(minutes=10)),
        ]
        patterns = pd._detect_workflows(history)
        # Only one occurrence — below min_occurrences=3
        assert len(patterns) == 0

    def test_large_time_gap_breaks_sequence(self):
        """Commands more than 30 min apart are placed in separate sequences."""
        pd = PatternDetector()
        now = datetime.now()
        history = [
            _record("cmd_a", now),
            _record("cmd_b", now + timedelta(hours=2)),  # gap > 30 min
        ]
        # Only one-element sequences on either side → no workflow
        patterns = pd._detect_workflows(history)
        assert len(patterns) == 0

    def test_workflow_pattern_type_label(self):
        """Detected workflow patterns carry pattern_type='workflow'."""
        pd = PatternDetector()
        now = datetime.now()
        history = []
        for i in range(5):
            base = now - timedelta(days=i)
            history += [
                _record("step_a", base),
                _record("step_b", base + timedelta(minutes=1)),
            ]
        patterns = pd._detect_workflows(history)
        assert all(p.pattern_type == "workflow" for p in patterns)


# ---------------------------------------------------------------------------
# Tests: _detect_time_patterns
# ---------------------------------------------------------------------------

class TestDetectTimePatterns:
    def test_commands_at_same_hour_detected(self):
        """Commands consistently run at the same hour produce a time pattern."""
        pd = PatternDetector()
        now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        history = [
            _record("morning backup", now - timedelta(days=i))
            for i in range(5)
        ]
        patterns = pd._detect_time_patterns(history)
        assert any(p.pattern_type == "time-based" for p in patterns)

    def test_time_pattern_description_includes_hour(self):
        """Time-based pattern description mentions the hour."""
        pd = PatternDetector()
        now = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
        history = [_record("afternoon sync", now - timedelta(days=i)) for i in range(5)]
        patterns = pd._detect_time_patterns(history)
        assert any("14:" in p.description for p in patterns)

    def test_commands_at_random_hours_no_time_pattern(self):
        """Commands spread across many hours do not produce a time pattern."""
        pd = PatternDetector()
        now = datetime.now()
        history = [
            _record("random cmd", now.replace(hour=h % 24) - timedelta(days=d))
            for d, h in enumerate(range(0, 10))
        ]
        patterns = pd._detect_time_patterns(history)
        # Each command appears only once at a given hour — below threshold
        assert len(patterns) == 0


# ---------------------------------------------------------------------------
# Tests: _detect_preferences
# ---------------------------------------------------------------------------

class TestDetectPreferences:
    def test_dominant_tool_detected_as_preference(self):
        """A tool used in >30 % of operations is flagged as a preference."""
        pd = PatternDetector()
        now = datetime.now()
        history = []
        for i in range(10):
            history.append(_record(
                "use file tool",
                now - timedelta(hours=i),
                intent_steps=[{"tool": "FileOps"}, {"tool": "FileOps"}, {"tool": "FileOps"}]
            ))
            history.append(_record(
                "other op",
                now - timedelta(hours=i, minutes=30),
                intent_steps=[{"tool": "NetworkOps"}]
            ))

        patterns = pd._detect_preferences(history)
        pref = [p for p in patterns if p.pattern_type == "preference"]
        assert len(pref) > 0
        assert any("FileOps" in p.description for p in pref)

    def test_no_intent_steps_no_preference(self):
        """History without intent steps produces no preference patterns."""
        pd = PatternDetector()
        now = datetime.now()
        history = [_record("some cmd", now - timedelta(hours=i)) for i in range(5)]
        patterns = pd._detect_preferences(history)
        assert len(patterns) == 0


# ---------------------------------------------------------------------------
# Tests: _normalize_command
# ---------------------------------------------------------------------------

class TestNormalizeCommand:
    def test_paths_replaced_with_placeholder(self):
        """Absolute paths are normalised to <path>."""
        pd = PatternDetector()
        assert "<path>" in pd._normalize_command("ls /home/user/docs")

    def test_numbers_replaced_with_placeholder(self):
        """Numeric tokens are normalised to <number>."""
        pd = PatternDetector()
        assert "<number>" in pd._normalize_command("retry 3 times")

    def test_lowercased(self):
        """Output is always lower-case."""
        pd = PatternDetector()
        result = pd._normalize_command("Backup FILES")
        assert result == result.lower()

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace is stripped."""
        pd = PatternDetector()
        result = pd._normalize_command("  do stuff  ")
        assert result == result.strip()


# ---------------------------------------------------------------------------
# Tests: _detect_frequency
# ---------------------------------------------------------------------------

class TestDetectFrequency:
    def test_single_timestamp_returns_none(self):
        """One timestamp is not enough to detect a frequency."""
        pd = PatternDetector()
        result = pd._detect_frequency([datetime.now()])
        assert result == (None, None)

    def test_daily_interval_returns_daily(self):
        """~24-hour intervals are classified as daily."""
        pd = PatternDetector()
        base = datetime(2026, 1, 1, 9, 0, 0)
        timestamps = [base + timedelta(hours=24 * i) for i in range(5)]
        freq, cron = pd._detect_frequency(timestamps)
        assert freq == "daily"
        assert cron is not None

    def test_weekly_interval_returns_weekly(self):
        """~7-day intervals are classified as weekly."""
        pd = PatternDetector()
        base = datetime(2026, 1, 1, 9, 0, 0)
        timestamps = [base + timedelta(hours=168 * i) for i in range(5)]
        freq, cron = pd._detect_frequency(timestamps)
        assert freq == "weekly"

    def test_monthly_interval_returns_monthly(self):
        """~30-day intervals are classified as monthly."""
        pd = PatternDetector()
        base = datetime(2026, 1, 1, 9, 0, 0)
        timestamps = [base + timedelta(hours=720 * i) for i in range(5)]
        freq, cron = pd._detect_frequency(timestamps)
        assert freq == "monthly"

    def test_unclassifiable_interval_returns_none(self):
        """Intervals outside known bands return (None, None)."""
        pd = PatternDetector()
        base = datetime(2026, 1, 1, 9, 0, 0)
        # ~2-hour intervals — not daily/weekly/monthly
        timestamps = [base + timedelta(hours=2 * i) for i in range(5)]
        freq, cron = pd._detect_frequency(timestamps)
        assert freq is None
        assert cron is None

    def test_daily_cron_expression_format(self):
        """Daily cron expression matches '0 <hour> * * *' format."""
        pd = PatternDetector()
        base = datetime(2026, 1, 1, 9, 0, 0)
        timestamps = [base + timedelta(hours=24 * i) for i in range(5)]
        _, cron = pd._detect_frequency(timestamps)
        # Pattern: "0 9 * * *"
        parts = cron.split()
        assert len(parts) == 5
        assert parts[0] == "0"
        assert parts[2] == "*"
        assert parts[3] == "*"


# ---------------------------------------------------------------------------
# Tests: _parse_timestamp
# ---------------------------------------------------------------------------

class TestParseTimestamp:
    def test_valid_iso_timestamp(self):
        """Standard ISO format parses correctly."""
        pd = PatternDetector()
        dt = pd._parse_timestamp("2026-01-15T09:00:00")
        assert isinstance(dt, datetime)
        assert dt.year == 2026

    def test_timestamp_with_z_suffix(self):
        """ISO timestamp with 'Z' is normalised and parsed."""
        pd = PatternDetector()
        dt = pd._parse_timestamp("2026-01-15T09:00:00Z")
        assert dt is not None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        pd = PatternDetector()
        assert pd._parse_timestamp("") is None

    def test_invalid_format_returns_none(self):
        """Garbage string returns None without raising."""
        pd = PatternDetector()
        assert pd._parse_timestamp("not-a-date") is None


# ---------------------------------------------------------------------------
# Tests: get_pattern_detector singleton
# ---------------------------------------------------------------------------

class TestGetPatternDetectorSingleton:
    def test_returns_pattern_detector_instance(self):
        """get_pattern_detector() returns a PatternDetector."""
        import zenus_core.brain.pattern_detector as module
        module._pattern_detector = None
        detector = get_pattern_detector()
        assert isinstance(detector, PatternDetector)

    def test_returns_same_instance_on_repeated_calls(self):
        """Subsequent calls return the cached singleton."""
        import zenus_core.brain.pattern_detector as module
        module._pattern_detector = None
        d1 = get_pattern_detector()
        d2 = get_pattern_detector()
        assert d1 is d2


# ---------------------------------------------------------------------------
# Tests: PatternMemory
# ---------------------------------------------------------------------------

class TestPatternMemory:
    def test_new_pattern_not_suggested(self, tmp_path):
        """A pattern that was never suggested returns False from has_suggested."""
        mem = PatternMemory(memory_file=str(tmp_path / "patterns.json"))
        assert mem.has_suggested("backup::daily") is False

    def test_mark_suggested_persists(self, tmp_path):
        """mark_suggested saves the key and has_suggested returns True."""
        f = str(tmp_path / "patterns.json")
        mem = PatternMemory(memory_file=f)
        mem.mark_suggested("backup::daily")
        assert mem.has_suggested("backup::daily") is True

    def test_clear_removes_all_entries(self, tmp_path):
        """clear() empties the suggestion memory."""
        mem = PatternMemory(memory_file=str(tmp_path / "patterns.json"))
        mem.mark_suggested("key_a")
        mem.mark_suggested("key_b")
        mem.clear()
        assert mem.has_suggested("key_a") is False
        assert mem.has_suggested("key_b") is False

    def test_persistence_across_instances(self, tmp_path):
        """Suggestions saved by one instance are readable by a new instance."""
        f = str(tmp_path / "patterns.json")
        mem1 = PatternMemory(memory_file=f)
        mem1.mark_suggested("workflow::git-npm")

        mem2 = PatternMemory(memory_file=f)
        assert mem2.has_suggested("workflow::git-npm") is True

    def test_missing_file_loads_empty_set(self, tmp_path):
        """PatternMemory initialised without an existing file starts empty."""
        mem = PatternMemory(memory_file=str(tmp_path / "nonexistent.json"))
        assert len(mem.suggested_patterns) == 0

    def test_corrupt_file_loads_empty_set(self, tmp_path):
        """Corrupt JSON file causes PatternMemory to start with an empty set."""
        bad_file = str(tmp_path / "corrupt.json")
        with open(bad_file, "w") as f_:
            f_.write("{{{not valid json")
        mem = PatternMemory(memory_file=bad_file)
        assert len(mem.suggested_patterns) == 0

    def test_clear_persists_empty_state(self, tmp_path):
        """After clear() a new instance also sees the memory as empty."""
        f = str(tmp_path / "patterns.json")
        mem = PatternMemory(memory_file=f)
        mem.mark_suggested("some_key")
        mem.clear()

        mem2 = PatternMemory(memory_file=f)
        assert mem2.has_suggested("some_key") is False

    def test_multiple_marks_do_not_duplicate(self, tmp_path):
        """Marking the same key twice results in only one entry."""
        mem = PatternMemory(memory_file=str(tmp_path / "patterns.json"))
        mem.mark_suggested("dup_key")
        mem.mark_suggested("dup_key")
        assert len(mem.suggested_patterns) == 1

    def test_save_failure_is_silent(self, tmp_path):
        """If the file cannot be written, no exception is raised."""
        mem = PatternMemory(memory_file=str(tmp_path / "patterns.json"))
        mem.mark_suggested("key1")
        # Make the file read-only so save will fail silently
        os.chmod(str(tmp_path / "patterns.json"), 0o444)
        try:
            mem.mark_suggested("key2")  # Should not raise
        finally:
            os.chmod(str(tmp_path / "patterns.json"), 0o644)


# ---------------------------------------------------------------------------
# Tests: get_pattern_memory singleton
# ---------------------------------------------------------------------------

class TestGetPatternMemorySingleton:
    def test_returns_pattern_memory_instance(self):
        """get_pattern_memory() returns a PatternMemory."""
        import zenus_core.brain.pattern_memory as module
        module._pattern_memory = None
        mem = get_pattern_memory()
        assert isinstance(mem, PatternMemory)

    def test_returns_same_instance_on_repeated_calls(self):
        """Subsequent calls return the cached singleton."""
        import zenus_core.brain.pattern_memory as module
        module._pattern_memory = None
        m1 = get_pattern_memory()
        m2 = get_pattern_memory()
        assert m1 is m2
