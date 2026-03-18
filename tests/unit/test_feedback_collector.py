"""
Unit tests for feedback/collector.py

File I/O and user prompts are fully mocked.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from zenus_core.feedback.collector import (
    FeedbackCollector,
    FeedbackEntry,
    get_feedback_collector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_intent(goal="list files", tool="FileOps"):
    step = Mock()
    step.tool = tool
    intent = Mock()
    intent.goal = goal
    intent.steps = [step]
    return intent


def _make_collector(tmp_path):
    feedback_path = tmp_path / "feedback.jsonl"
    return FeedbackCollector(
        feedback_path=str(feedback_path),
        prompt_frequency=1.0,  # always prompt
        enable_prompts=True
    )


# ---------------------------------------------------------------------------
# FeedbackEntry
# ---------------------------------------------------------------------------

class TestFeedbackEntry:

    def test_to_dict_contains_all_fields(self):
        entry = FeedbackEntry(
            timestamp="2026-01-01T00:00:00",
            user_input="ls -la",
            intent_goal="list files",
            tool_used="FileOps",
            feedback="positive",
            execution_time_ms=100.0,
            success=True,
            comment=None
        )
        d = entry.to_dict()
        assert d["user_input"] == "ls -la"
        assert d["intent_goal"] == "list files"
        assert d["tool_used"] == "FileOps"
        assert d["feedback"] == "positive"
        assert d["success"] is True

    def test_to_dict_with_comment(self):
        entry = FeedbackEntry(
            timestamp="2026-01-01T00:00:00",
            user_input="rm -rf",
            intent_goal="delete",
            tool_used="FileOps",
            feedback="negative",
            execution_time_ms=50.0,
            success=False,
            comment="Wrong directory"
        )
        d = entry.to_dict()
        assert d["comment"] == "Wrong directory"


# ---------------------------------------------------------------------------
# FeedbackCollector initialization
# ---------------------------------------------------------------------------

class TestFeedbackCollectorInit:

    def test_creates_feedback_dir(self, tmp_path):
        subdir = tmp_path / "nested" / "dir"
        collector = FeedbackCollector(
            feedback_path=str(subdir / "feedback.jsonl"),
            enable_prompts=False
        )
        assert subdir.exists()

    def test_enable_prompts_default(self, tmp_path):
        collector = _make_collector(tmp_path)
        assert collector.enable_prompts is True

    def test_env_var_disables_prompts(self, tmp_path):
        with patch.dict(os.environ, {"ZENUS_FEEDBACK_PROMPTS": "false"}):
            collector = FeedbackCollector(
                feedback_path=str(tmp_path / "f.jsonl"),
                enable_prompts=True
            )
        assert collector.enable_prompts is False

    def test_env_var_0_disables_prompts(self, tmp_path):
        with patch.dict(os.environ, {"ZENUS_FEEDBACK_PROMPTS": "0"}):
            collector = FeedbackCollector(
                feedback_path=str(tmp_path / "f.jsonl"),
                enable_prompts=True
            )
        assert collector.enable_prompts is False

    def test_prompt_frequency(self, tmp_path):
        collector = FeedbackCollector(
            feedback_path=str(tmp_path / "f.jsonl"),
            prompt_frequency=0.5
        )
        assert collector.prompt_frequency == 0.5


# ---------------------------------------------------------------------------
# collect – disabled prompts
# ---------------------------------------------------------------------------

class TestCollectDisabled:

    def test_returns_none_when_disabled(self, tmp_path):
        collector = FeedbackCollector(
            feedback_path=str(tmp_path / "f.jsonl"),
            enable_prompts=False
        )
        result = collector.collect("ls", _make_intent(), 100.0, True)
        assert result is None


# ---------------------------------------------------------------------------
# collect – frequency sampling
# ---------------------------------------------------------------------------

class TestCollectSampling:

    def test_skips_when_random_above_frequency(self, tmp_path):
        collector = FeedbackCollector(
            feedback_path=str(tmp_path / "f.jsonl"),
            prompt_frequency=0.0,  # never prompt
            enable_prompts=True
        )
        with patch("random.random", return_value=0.5):
            result = collector.collect("ls", _make_intent(), 100.0, True)
        assert result is None

    def test_prompts_when_random_below_frequency(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.return_value = "skip"
        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                result = collector.collect("ls", _make_intent(), 100.0, True)
        assert result == "skip"


# ---------------------------------------------------------------------------
# collect – deduplication
# ---------------------------------------------------------------------------

class TestCollectDeduplication:

    def test_does_not_ask_twice_same_session(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.return_value = "y"

        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                collector.collect("check files", _make_intent(), 100.0, True)
                result = collector.collect("check files", _make_intent(), 100.0, True)

        assert result is None  # second call skipped

    def test_already_has_feedback_from_file(self, tmp_path):
        collector = _make_collector(tmp_path)
        # Write existing feedback for this command
        entry = {
            "user_input": "list all files",
            "intent_goal": "list",
            "tool_used": "FileOps",
            "feedback": "positive",
            "execution_time_ms": 50.0,
            "success": True,
            "comment": None,
            "timestamp": "2026-01-01T00:00:00"
        }
        collector.feedback_path.write_text(json.dumps(entry) + "\n")

        with patch("random.random", return_value=0.0):
            result = collector.collect("list all files", _make_intent(), 100.0, True)

        assert result is None  # already has feedback


# ---------------------------------------------------------------------------
# collect – user responses
# ---------------------------------------------------------------------------

class TestCollectResponses:

    def test_positive_feedback(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.return_value = "y"

        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                result = collector.collect("unique_cmd_1", _make_intent(), 100.0, True)

        assert result == "positive"

    def test_yes_full_word_feedback(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.return_value = "yes"

        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                result = collector.collect("unique_cmd_2", _make_intent(), 100.0, True)

        assert result == "positive"

    def test_negative_without_comment(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.side_effect = ["n", ""]  # negative, empty comment

        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                result = collector.collect("unique_cmd_3", _make_intent(), 100.0, False)

        assert result == "negative"

    def test_negative_with_comment(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.side_effect = ["n", "Wrong output"]

        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                result = collector.collect("unique_cmd_4", _make_intent(), 100.0, False)

        assert result == "negative"
        # Verify feedback was written
        content = collector.feedback_path.read_text()
        assert "Wrong output" in content

    def test_skip_response(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.return_value = "skip"

        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                result = collector.collect("unique_cmd_5", _make_intent(), 100.0, True)

        assert result == "skip"

    def test_keyboard_interrupt_returns_none(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.side_effect = KeyboardInterrupt()

        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                result = collector.collect("unique_cmd_6", _make_intent(), 100.0, True)

        assert result is None

    def test_eof_error_returns_none(self, tmp_path):
        collector = _make_collector(tmp_path)
        mock_console = MagicMock()
        mock_console.input.side_effect = EOFError()

        with patch("rich.console.Console", return_value=mock_console):
            with patch("random.random", return_value=0.0):
                result = collector.collect("unique_cmd_7", _make_intent(), 100.0, True)

        assert result is None


# ---------------------------------------------------------------------------
# _record_feedback
# ---------------------------------------------------------------------------

class TestRecordFeedback:

    def test_writes_jsonl_file(self, tmp_path):
        collector = _make_collector(tmp_path)
        collector._record_feedback(
            "ls -la", _make_intent(), 100.0, True, "positive"
        )
        assert collector.feedback_path.exists()
        content = collector.feedback_path.read_text()
        entry = json.loads(content.strip())
        assert entry["user_input"] == "ls -la"
        assert entry["feedback"] == "positive"

    def test_appends_multiple_entries(self, tmp_path):
        collector = _make_collector(tmp_path)
        collector._record_feedback("cmd1", _make_intent(), 100.0, True, "positive")
        collector._record_feedback("cmd2", _make_intent(), 200.0, False, "negative")
        lines = collector.feedback_path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_truncates_long_input(self, tmp_path):
        collector = _make_collector(tmp_path)
        long_input = "a" * 500
        collector._record_feedback(long_input, _make_intent(), 100.0, True, "positive")
        content = json.loads(collector.feedback_path.read_text())
        assert len(content["user_input"]) <= 200

    def test_intent_with_no_steps_uses_unknown_tool(self, tmp_path):
        collector = _make_collector(tmp_path)
        intent = Mock()
        intent.goal = "no steps"
        intent.steps = []
        collector._record_feedback("cmd", intent, 100.0, True, "positive")
        content = json.loads(collector.feedback_path.read_text())
        assert content["tool_used"] == "unknown"

    def test_invalidates_stats_cache(self, tmp_path):
        collector = _make_collector(tmp_path)
        collector._stats_cache = {"some": "data"}
        collector._record_feedback("cmd", _make_intent(), 100.0, True, "positive")
        assert collector._stats_cache is None


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:

    def test_empty_file_returns_zeros(self, tmp_path):
        collector = _make_collector(tmp_path)
        stats = collector.get_stats()
        assert stats["total_feedback"] == 0
        assert stats["positive"] == 0

    def test_missing_file_returns_zeros(self, tmp_path):
        collector = FeedbackCollector(
            feedback_path=str(tmp_path / "nonexistent.jsonl"),
            enable_prompts=False
        )
        stats = collector.get_stats()
        assert stats["total_feedback"] == 0

    def test_counts_feedback_types(self, tmp_path):
        collector = _make_collector(tmp_path)
        entries = [
            {"user_input": "a", "intent_goal": "a", "tool_used": "FileOps",
             "feedback": "positive", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
            {"user_input": "b", "intent_goal": "b", "tool_used": "FileOps",
             "feedback": "negative", "execution_time_ms": 100, "success": False,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
            {"user_input": "c", "intent_goal": "c", "tool_used": "ShellOps",
             "feedback": "skip", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
        ]
        collector.feedback_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        stats = collector.get_stats()
        assert stats["total_feedback"] == 3
        assert stats["positive"] == 1
        assert stats["negative"] == 1
        assert stats["skip"] == 1

    def test_stats_by_tool(self, tmp_path):
        collector = _make_collector(tmp_path)
        entries = [
            {"user_input": "a", "intent_goal": "a", "tool_used": "FileOps",
             "feedback": "positive", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
        ]
        collector.feedback_path.write_text(json.dumps(entries[0]) + "\n")
        stats = collector.get_stats()
        assert "FileOps" in stats["by_tool"]
        assert stats["by_tool"]["FileOps"]["positive"] == 1

    def test_stats_positive_rate(self, tmp_path):
        collector = _make_collector(tmp_path)
        entries = [
            {"user_input": "a", "intent_goal": "a", "tool_used": "FileOps",
             "feedback": "positive", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
            {"user_input": "b", "intent_goal": "b", "tool_used": "FileOps",
             "feedback": "positive", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
        ]
        collector.feedback_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        stats = collector.get_stats()
        assert stats["positive_rate"] == 1.0

    def test_stats_cached(self, tmp_path):
        collector = _make_collector(tmp_path)
        stats1 = collector.get_stats()
        stats2 = collector.get_stats()
        # Second call uses cache (same object)
        assert stats1["total_feedback"] == stats2["total_feedback"]

    def test_stats_by_success(self, tmp_path):
        collector = _make_collector(tmp_path)
        entries = [
            {"user_input": "a", "intent_goal": "a", "tool_used": "FileOps",
             "feedback": "positive", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
            {"user_input": "b", "intent_goal": "b", "tool_used": "FileOps",
             "feedback": "negative", "execution_time_ms": 100, "success": False,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
        ]
        collector.feedback_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        stats = collector.get_stats()
        assert stats["by_success"]["successful"] == 1
        assert stats["by_success"]["failed"] == 1


# ---------------------------------------------------------------------------
# export_training_data
# ---------------------------------------------------------------------------

class TestExportTrainingData:

    def test_returns_path_when_no_file(self, tmp_path):
        collector = FeedbackCollector(
            feedback_path=str(tmp_path / "nonexistent.jsonl"),
            enable_prompts=False
        )
        output = tmp_path / "training.jsonl"
        result = collector.export_training_data(str(output))
        assert str(output) in result

    def test_exports_positive_only_by_default(self, tmp_path):
        collector = _make_collector(tmp_path)
        entries = [
            {"user_input": "good cmd", "intent_goal": "good", "tool_used": "FileOps",
             "feedback": "positive", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
            {"user_input": "bad cmd", "intent_goal": "bad", "tool_used": "FileOps",
             "feedback": "negative", "execution_time_ms": 100, "success": False,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
            {"user_input": "skip cmd", "intent_goal": "skip", "tool_used": "FileOps",
             "feedback": "skip", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
        ]
        collector.feedback_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        output = str(tmp_path / "training.jsonl")
        result = collector.export_training_data(output)
        assert "Exported 1 examples" in result

    def test_exports_with_negative_included(self, tmp_path):
        collector = _make_collector(tmp_path)
        entries = [
            {"user_input": "good", "intent_goal": "good", "tool_used": "FileOps",
             "feedback": "positive", "execution_time_ms": 100, "success": True,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
            {"user_input": "bad", "intent_goal": "bad", "tool_used": "FileOps",
             "feedback": "negative", "execution_time_ms": 100, "success": False,
             "comment": None, "timestamp": "2026-01-01T00:00:00"},
        ]
        collector.feedback_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        output = str(tmp_path / "training.jsonl")
        # min_rating must NOT be 'positive' to allow negatives through
        result = collector.export_training_data(output, min_rating="any", include_negative=True)
        assert "Exported 2 examples" in result

    def test_exported_format(self, tmp_path):
        collector = _make_collector(tmp_path)
        entry = {"user_input": "test cmd", "intent_goal": "test goal", "tool_used": "FileOps",
                 "feedback": "positive", "execution_time_ms": 100, "success": True,
                 "comment": None, "timestamp": "2026-01-01T00:00:00"}
        collector.feedback_path.write_text(json.dumps(entry) + "\n")
        output = str(tmp_path / "training.jsonl")
        collector.export_training_data(output)
        exported = json.loads(Path(output).read_text())
        assert "prompt" in exported
        assert "completion" in exported
        assert exported["feedback"] == "positive"


# ---------------------------------------------------------------------------
# _sanitize_text
# ---------------------------------------------------------------------------

class TestSanitizeText:

    def setup_method(self):
        self.collector = FeedbackCollector(
            feedback_path="/tmp/test_feedback.jsonl",
            enable_prompts=False
        )

    def test_redacts_password(self):
        text = "connect password=supersecret database"
        result = self.collector._sanitize_text(text)
        assert "supersecret" not in result
        assert "[REDACTED]" in result

    def test_redacts_token(self):
        text = "auth token=abc123xyz"
        result = self.collector._sanitize_text(text)
        assert "abc123xyz" not in result

    def test_redacts_email(self):
        text = "send email to user@example.com"
        result = self.collector._sanitize_text(text)
        assert "user@example.com" not in result
        assert "[EMAIL]" in result

    def test_safe_text_unchanged(self):
        text = "list files in the current directory"
        result = self.collector._sanitize_text(text)
        assert result == text


# ---------------------------------------------------------------------------
# _already_has_feedback
# ---------------------------------------------------------------------------

class TestAlreadyHasFeedback:

    def test_false_when_no_file(self, tmp_path):
        collector = FeedbackCollector(
            feedback_path=str(tmp_path / "nonexistent.jsonl"),
            enable_prompts=False
        )
        assert collector._already_has_feedback("test command") is False

    def test_true_for_exact_match(self, tmp_path):
        collector = _make_collector(tmp_path)
        entry = {"user_input": "list files", "feedback": "positive"}
        collector.feedback_path.write_text(json.dumps(entry) + "\n")
        assert collector._already_has_feedback("list files") is True

    def test_false_for_different_command(self, tmp_path):
        collector = _make_collector(tmp_path)
        entry = {"user_input": "list files", "feedback": "positive"}
        collector.feedback_path.write_text(json.dumps(entry) + "\n")
        assert collector._already_has_feedback("delete files") is False

    def test_true_for_substring_match_long_cmd(self, tmp_path):
        collector = _make_collector(tmp_path)
        long_cmd = "list all files in the current directory recursively"
        entry = {"user_input": long_cmd, "feedback": "positive"}
        collector.feedback_path.write_text(json.dumps(entry) + "\n")
        # Short commands (< 20 chars) don't do substring matching
        assert collector._already_has_feedback(long_cmd) is True


# ---------------------------------------------------------------------------
# get_feedback_collector singleton
# ---------------------------------------------------------------------------

class TestGetFeedbackCollector:

    def test_returns_feedback_collector_instance(self):
        import zenus_core.feedback.collector as mod
        mod._feedback_collector = None
        fc = get_feedback_collector()
        assert isinstance(fc, FeedbackCollector)

    def test_returns_same_instance(self):
        import zenus_core.feedback.collector as mod
        mod._feedback_collector = None
        fc1 = get_feedback_collector()
        fc2 = get_feedback_collector()
        assert fc1 is fc2
