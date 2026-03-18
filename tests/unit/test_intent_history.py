"""
Tests for Intent History
"""

import json
import pytest
from unittest.mock import Mock
from zenus_core.memory.intent_history import IntentHistory


@pytest.fixture
def history(tmp_path):
    """Create IntentHistory backed by a temp directory."""
    return IntentHistory(history_dir=str(tmp_path))


def _make_intent(goal="do something", steps=None):
    """Build a minimal mock intent object."""
    intent = Mock()
    intent.goal = goal
    intent.steps = steps if steps is not None else []
    return intent


class TestIntentHistoryInit:
    def test_creates_history_dir(self, tmp_path):
        """Constructor creates the history directory when it does not exist."""
        new_dir = tmp_path / "brand_new_dir"
        ih = IntentHistory(history_dir=str(new_dir))
        assert new_dir.exists()

    def test_current_file_is_daily(self, history):
        """Current file name contains today's date."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in history.current_file.name

    def test_current_file_is_jsonl(self, history):
        """Current file has .jsonl extension."""
        assert history.current_file.suffix == ".jsonl"


class TestRecord:
    def test_record_creates_file(self, history):
        """First record call creates the JSONL file on disk."""
        intent = _make_intent()
        history.record("do something", intent, results=["ok"], success=True)
        assert history.current_file.exists()

    def test_record_appends_valid_json_line(self, history):
        """Each recorded entry is a valid JSON line."""
        intent = _make_intent(goal="list files")
        history.record("list files", intent, results=["file1"], success=True)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())

        assert entry["goal"] == "list files"

    def test_record_stores_user_input(self, history):
        """user_input field is stored verbatim."""
        intent = _make_intent()
        history.record("my command", intent, results=[], success=True)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())
        assert entry["user_input"] == "my command"

    def test_record_stores_success_true(self, history):
        """success=True is stored correctly."""
        intent = _make_intent()
        history.record("cmd", intent, results=[], success=True)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())
        assert entry["success"] is True

    def test_record_stores_success_false(self, history):
        """success=False is stored correctly."""
        intent = _make_intent()
        history.record("cmd", intent, results=[], success=False)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())
        assert entry["success"] is False

    def test_record_stores_results(self, history):
        """results list is stored verbatim."""
        intent = _make_intent()
        history.record("cmd", intent, results=["step1 done", "step2 done"], success=True)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())
        assert entry["results"] == ["step1 done", "step2 done"]

    def test_record_stores_steps_count(self, history):
        """steps_count reflects the number of steps on the intent."""
        intent = _make_intent(steps=["a", "b", "c"])
        history.record("cmd", intent, results=[], success=True)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())
        assert entry["steps_count"] == 3

    def test_record_intent_without_goal_attribute(self, history):
        """Falls back to str() when intent has no goal attribute."""
        class Bare:
            def __str__(self):
                return "bare intent"

        history.record("cmd", Bare(), results=[], success=True)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())
        assert entry["goal"] == "bare intent"

    def test_record_intent_without_steps_attribute(self, history):
        """steps_count is 0 when intent has no steps attribute."""
        class NoSteps:
            goal = "goal"

        history.record("cmd", NoSteps(), results=[], success=True)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())
        assert entry["steps_count"] == 0

    def test_record_multiple_entries_appended(self, history):
        """Multiple records append multiple lines to the file."""
        for i in range(3):
            intent = _make_intent(goal=f"goal {i}")
            history.record(f"cmd {i}", intent, results=[], success=True)

        with open(history.current_file) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 3

    def test_record_has_timestamp(self, history):
        """Recorded entry includes a non-empty timestamp."""
        intent = _make_intent()
        history.record("cmd", intent, results=[], success=True)

        with open(history.current_file) as f:
            entry = json.loads(f.readline())
        assert entry["timestamp"] != ""


class TestGetRecent:
    def test_get_recent_empty_when_no_file(self, history):
        """Returns empty list when no file has been written yet."""
        assert history.get_recent() == []

    def test_get_recent_returns_all_when_fewer_than_limit(self, history):
        """Returns all entries when fewer than limit exist."""
        for i in range(3):
            intent = _make_intent(goal=f"goal {i}")
            history.record(f"cmd {i}", intent, results=[], success=True)

        results = history.get_recent(limit=10)
        assert len(results) == 3

    def test_get_recent_respects_limit(self, history):
        """Returns at most limit entries."""
        for i in range(8):
            intent = _make_intent(goal=f"goal {i}")
            history.record(f"cmd {i}", intent, results=[], success=True)

        results = history.get_recent(limit=3)
        assert len(results) == 3

    def test_get_recent_returns_most_recent(self, history):
        """Returned entries are the most recently written ones."""
        for i in range(5):
            intent = _make_intent(goal=f"goal {i}")
            history.record(f"cmd {i}", intent, results=[], success=True)

        results = history.get_recent(limit=2)
        goals = [r["goal"] for r in results]
        assert "goal 4" in goals
        assert "goal 3" in goals


class TestSearch:
    def test_search_matches_user_input(self, history):
        """Search finds entries matching user_input text."""
        intent = _make_intent(goal="move photos")
        history.record("move my photos to backup", intent, results=[], success=True)

        matches = history.search("photos")
        assert len(matches) == 1

    def test_search_matches_goal(self, history):
        """Search finds entries matching goal text."""
        intent = _make_intent(goal="organize downloads")
        history.record("sort stuff", intent, results=[], success=True)

        matches = history.search("organize downloads")
        assert len(matches) == 1

    def test_search_is_case_insensitive(self, history):
        """Search is case-insensitive."""
        intent = _make_intent(goal="Delete Temp Files")
        history.record("cmd", intent, results=[], success=True)

        matches = history.search("delete temp files")
        assert len(matches) == 1

    def test_search_returns_empty_for_no_match(self, history):
        """Search returns empty list when nothing matches."""
        intent = _make_intent(goal="compile project")
        history.record("build it", intent, results=[], success=True)

        matches = history.search("nonexistent-xyz-query")
        assert matches == []

    def test_search_respects_limit(self, history):
        """Search returns at most limit entries."""
        for i in range(5):
            intent = _make_intent(goal="common goal")
            history.record("common user input", intent, results=[], success=True)

        matches = history.search("common", limit=2)
        assert len(matches) == 2

    def test_search_across_multiple_files(self, history, tmp_path):
        """Search scans all history files, not just today's."""
        # Manually write a file with a different date name
        old_file = history.history_dir / "intents_2020-01-01.jsonl"
        entry = {
            "timestamp": "2020-01-01T12:00:00",
            "user_input": "archive old logs",
            "goal": "archive logs",
            "steps_count": 1,
            "success": True,
            "duration_seconds": 0,
            "results": []
        }
        old_file.write_text(json.dumps(entry) + "\n")

        matches = history.search("archive")
        assert any("archive" in m["goal"] for m in matches)

    def test_search_no_files_returns_empty(self, history):
        """Search on a fresh directory returns empty list."""
        assert history.search("anything") == []


class TestGetSuccessRate:
    def test_success_rate_no_files(self, history):
        """Returns 0.0 when no history files exist."""
        assert history.get_success_rate() == 0.0

    def test_success_rate_all_success(self, history):
        """Returns 1.0 when all recorded intents succeeded."""
        for _ in range(3):
            intent = _make_intent()
            history.record("cmd", intent, results=[], success=True)

        rate = history.get_success_rate()
        assert rate == 1.0

    def test_success_rate_all_failure(self, history):
        """Returns 0.0 when all recorded intents failed."""
        for _ in range(3):
            intent = _make_intent()
            history.record("cmd", intent, results=[], success=False)

        rate = history.get_success_rate()
        assert rate == 0.0

    def test_success_rate_mixed(self, history):
        """Returns correct ratio for mixed success/failure."""
        for i in range(4):
            intent = _make_intent()
            success = i < 3  # 3 successes, 1 failure
            history.record("cmd", intent, results=[], success=success)

        rate = history.get_success_rate()
        assert rate == pytest.approx(0.75)


class TestGetPopularGoals:
    def test_popular_goals_empty_dir(self, history):
        """Returns empty list when no history files exist."""
        assert history.get_popular_goals() == []

    def test_popular_goals_sorted_by_count(self, history):
        """Goals are sorted by occurrence count descending."""
        for _ in range(3):
            intent = _make_intent(goal="frequent goal")
            history.record("cmd", intent, results=[], success=True)

        intent = _make_intent(goal="rare goal")
        history.record("cmd", intent, results=[], success=True)

        popular = history.get_popular_goals()
        assert popular[0]["goal"] == "frequent goal"
        assert popular[0]["count"] == 3
        assert popular[1]["goal"] == "rare goal"
        assert popular[1]["count"] == 1

    def test_popular_goals_respects_limit(self, history):
        """Returns at most limit goal entries."""
        for i in range(5):
            intent = _make_intent(goal=f"goal {i}")
            history.record("cmd", intent, results=[], success=True)

        popular = history.get_popular_goals(limit=2)
        assert len(popular) == 2

    def test_popular_goals_entry_structure(self, history):
        """Each entry has goal and count keys."""
        intent = _make_intent(goal="structured goal")
        history.record("cmd", intent, results=[], success=True)

        popular = history.get_popular_goals()
        assert "goal" in popular[0]
        assert "count" in popular[0]


class TestAnalyzeFailures:
    def test_analyze_failures_empty_dir(self, history):
        """Returns empty list when no history files exist."""
        assert history.analyze_failures() == []

    def test_analyze_failures_returns_only_failures(self, history):
        """Only entries with success=False are returned."""
        intent_ok = _make_intent(goal="success goal")
        history.record("ok cmd", intent_ok, results=[], success=True)

        intent_fail = _make_intent(goal="failure goal")
        history.record("fail cmd", intent_fail, results=[], success=False)

        failures = history.analyze_failures()
        assert len(failures) == 1
        assert failures[0]["goal"] == "failure goal"

    def test_analyze_failures_respects_limit(self, history):
        """Returns at most limit failure entries."""
        for _ in range(5):
            intent = _make_intent(goal="fail goal")
            history.record("cmd", intent, results=[], success=False)

        failures = history.analyze_failures(limit=2)
        assert len(failures) == 2

    def test_analyze_failures_no_failures(self, history):
        """Returns empty list when all intents succeeded."""
        for _ in range(3):
            intent = _make_intent()
            history.record("cmd", intent, results=[], success=True)

        assert history.analyze_failures() == []
