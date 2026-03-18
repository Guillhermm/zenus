"""
Tests for Session Memory
"""

import pytest
from unittest.mock import Mock
from zenus_core.memory.session_memory import SessionMemory


class TestSessionMemoryInit:
    def test_default_max_history(self):
        """Default max_history is 10."""
        sm = SessionMemory()
        assert sm.max_history == 10

    def test_custom_max_history(self):
        """Custom max_history is stored correctly."""
        sm = SessionMemory(max_history=5)
        assert sm.max_history == 5

    def test_initial_state_empty(self):
        """Fresh instance has empty intents, history, and context refs."""
        sm = SessionMemory()
        assert sm.intents == []
        assert sm.intent_history == []
        assert sm.context_refs == {}

    def test_session_start_is_set(self):
        """session_start is set on construction."""
        sm = SessionMemory()
        assert sm.session_start is not None


class TestAddIntent:
    def test_add_intent_with_goal_and_steps(self):
        """Records entry with goal and step count from intent object."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "organize files"
        intent.steps = [1, 2, 3]

        sm.add_intent(intent, user_input="organize my files", result="done")

        assert len(sm.intent_history) == 1
        entry = sm.intent_history[0]
        assert entry["goal"] == "organize files"
        assert entry["steps_count"] == 3
        assert entry["user_input"] == "organize my files"
        assert entry["result"] == "done"

    def test_add_intent_stores_intent_object(self):
        """The actual intent object is stored in intents list."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "g"
        intent.steps = []

        sm.add_intent(intent)

        assert sm.intents[0] is intent

    def test_add_intent_without_goal_attribute(self):
        """Falls back to str(intent) when intent has no goal attribute."""
        sm = SessionMemory()

        class PlainIntent:
            def __str__(self):
                return "plain intent string"

        intent = PlainIntent()
        sm.add_intent(intent)

        assert sm.intent_history[0]["goal"] == "plain intent string"

    def test_add_intent_without_steps_attribute(self):
        """steps_count defaults to 0 when intent has no steps."""
        sm = SessionMemory()

        class NoSteps:
            goal = "some goal"

        sm.add_intent(NoSteps())
        assert sm.intent_history[0]["steps_count"] == 0

    def test_add_intent_default_user_input_and_result(self):
        """user_input and result default to empty string."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "g"
        intent.steps = []

        sm.add_intent(intent)

        entry = sm.intent_history[0]
        assert entry["user_input"] == ""
        assert entry["result"] == ""

    def test_add_intent_timestamp_is_set(self):
        """Recorded entry has a non-empty timestamp string."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "g"
        intent.steps = []

        sm.add_intent(intent)

        assert sm.intent_history[0]["timestamp"] != ""

    def test_history_enforces_max_history_limit(self):
        """intent_history is capped at max_history entries."""
        sm = SessionMemory(max_history=3)

        for i in range(5):
            intent = Mock()
            intent.goal = f"goal {i}"
            intent.steps = []
            sm.add_intent(intent)

        assert len(sm.intent_history) == 3

    def test_history_keeps_most_recent_on_overflow(self):
        """Oldest entries are dropped when limit is reached."""
        sm = SessionMemory(max_history=2)

        for i in range(4):
            intent = Mock()
            intent.goal = f"goal {i}"
            intent.steps = []
            sm.add_intent(intent)

        goals = [e["goal"] for e in sm.intent_history]
        assert goals == ["goal 2", "goal 3"]

    def test_intents_list_not_trimmed(self):
        """The raw intents list is not subject to the max_history cap."""
        sm = SessionMemory(max_history=2)

        for i in range(4):
            intent = Mock()
            intent.goal = f"g{i}"
            intent.steps = []
            sm.add_intent(intent)

        assert len(sm.intents) == 4


class TestContextRefs:
    def test_add_and_get_context_ref(self):
        """Stored context reference can be retrieved by key."""
        sm = SessionMemory()
        sm.add_context_ref("last_directory", "/home/user/Downloads")
        assert sm.get_context_ref("last_directory") == "/home/user/Downloads"

    def test_get_missing_context_ref_returns_none(self):
        """Retrieving a non-existent key returns None."""
        sm = SessionMemory()
        assert sm.get_context_ref("nonexistent") is None

    def test_overwrite_context_ref(self):
        """Adding the same key twice overwrites the previous value."""
        sm = SessionMemory()
        sm.add_context_ref("that_file", "/old/path.txt")
        sm.add_context_ref("that_file", "/new/path.txt")
        assert sm.get_context_ref("that_file") == "/new/path.txt"

    def test_multiple_context_refs(self):
        """Multiple distinct keys can coexist."""
        sm = SessionMemory()
        sm.add_context_ref("key_a", "val_a")
        sm.add_context_ref("key_b", "val_b")
        assert sm.get_context_ref("key_a") == "val_a"
        assert sm.get_context_ref("key_b") == "val_b"


class TestGetRecentIntents:
    def test_get_recent_returns_last_n(self):
        """get_recent_intents returns at most the requested count."""
        sm = SessionMemory(max_history=10)

        for i in range(8):
            intent = Mock()
            intent.goal = f"goal {i}"
            intent.steps = []
            sm.add_intent(intent)

        recent = sm.get_recent_intents(count=3)
        assert len(recent) == 3

    def test_get_recent_are_most_recent(self):
        """get_recent_intents returns the most recent entries."""
        sm = SessionMemory(max_history=10)

        for i in range(5):
            intent = Mock()
            intent.goal = f"goal {i}"
            intent.steps = []
            sm.add_intent(intent)

        recent = sm.get_recent_intents(count=2)
        goals = [e["goal"] for e in recent]
        assert goals == ["goal 3", "goal 4"]

    def test_get_recent_fewer_than_requested(self):
        """Returns all entries when fewer than count exist."""
        sm = SessionMemory()

        intent = Mock()
        intent.goal = "only one"
        intent.steps = []
        sm.add_intent(intent)

        recent = sm.get_recent_intents(count=5)
        assert len(recent) == 1

    def test_get_recent_empty_history(self):
        """Returns empty list when no intents recorded."""
        sm = SessionMemory()
        assert sm.get_recent_intents() == []


class TestGetContextSummary:
    def test_summary_no_history(self):
        """Returns no-activity message when history is empty."""
        sm = SessionMemory()
        summary = sm.get_context_summary()
        assert summary == "No recent activity in this session."

    def test_summary_with_intents(self):
        """Summary includes goal and result lines for recorded intents."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "move files"
        intent.steps = []
        sm.add_intent(intent, result="success")

        summary = sm.get_context_summary()
        assert "Recent session context:" in summary
        assert "move files" in summary
        assert "success" in summary

    def test_summary_shows_context_refs(self):
        """Summary includes context references section when present."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "g"
        intent.steps = []
        sm.add_intent(intent)
        sm.add_context_ref("last_directory", "/tmp")

        summary = sm.get_context_summary()
        assert "Context references:" in summary
        assert "last_directory" in summary
        assert "/tmp" in summary

    def test_summary_no_context_refs_section_when_empty(self):
        """Summary omits context references section when none recorded."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "g"
        intent.steps = []
        sm.add_intent(intent)

        summary = sm.get_context_summary()
        assert "Context references:" not in summary

    def test_summary_limits_to_three_most_recent_intents(self):
        """Summary shows at most 3 most recent intents."""
        sm = SessionMemory(max_history=10)

        for i in range(5):
            intent = Mock()
            intent.goal = f"goal {i}"
            intent.steps = []
            sm.add_intent(intent)

        summary = sm.get_context_summary()
        # Only last 3 goals should appear
        assert "goal 4" in summary
        assert "goal 3" in summary
        assert "goal 2" in summary
        assert "goal 1" not in summary
        assert "goal 0" not in summary


class TestClear:
    def test_clear_removes_intent_history(self):
        """clear() empties intent_history."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "g"
        intent.steps = []
        sm.add_intent(intent)

        sm.clear()
        assert sm.intent_history == []

    def test_clear_removes_context_refs(self):
        """clear() empties context_refs."""
        sm = SessionMemory()
        sm.add_context_ref("k", "v")

        sm.clear()
        assert sm.context_refs == {}

    def test_clear_does_not_reset_intents_list(self):
        """clear() does not empty the raw intents object list."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "g"
        intent.steps = []
        sm.add_intent(intent)

        sm.clear()
        # intents list is NOT cleared by clear()
        assert len(sm.intents) == 1


class TestGetSessionStats:
    def test_stats_structure(self):
        """get_session_stats returns expected keys."""
        sm = SessionMemory()
        stats = sm.get_session_stats()
        assert "session_duration_seconds" in stats
        assert "total_intents" in stats
        assert "context_refs" in stats

    def test_stats_counts_intents(self):
        """total_intents reflects number of recorded intents."""
        sm = SessionMemory()

        for _ in range(3):
            intent = Mock()
            intent.goal = "g"
            intent.steps = []
            sm.add_intent(intent)

        stats = sm.get_session_stats()
        assert stats["total_intents"] == 3

    def test_stats_counts_context_refs(self):
        """context_refs count reflects stored references."""
        sm = SessionMemory()
        sm.add_context_ref("a", "1")
        sm.add_context_ref("b", "2")

        stats = sm.get_session_stats()
        assert stats["context_refs"] == 2

    def test_stats_duration_is_non_negative(self):
        """session_duration_seconds is a non-negative number."""
        sm = SessionMemory()
        stats = sm.get_session_stats()
        assert stats["session_duration_seconds"] >= 0

    def test_stats_after_clear(self):
        """Stats reflect zeroed counts after clearing."""
        sm = SessionMemory()
        intent = Mock()
        intent.goal = "g"
        intent.steps = []
        sm.add_intent(intent)
        sm.add_context_ref("k", "v")
        sm.clear()

        stats = sm.get_session_stats()
        assert stats["total_intents"] == 0
        assert stats["context_refs"] == 0
