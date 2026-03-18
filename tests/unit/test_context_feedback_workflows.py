"""
Tests for context manager, feedback collector, and workflow recorder.
"""

import json
import os
import time
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_intent(goal="test goal", steps=None, requires_confirmation=False):
    """Build a minimal IntentIR."""
    if steps is None:
        steps = [Step(tool="FileOps", action="read_file", args={"path": "/tmp/a"}, risk=0)]
    return IntentIR(goal=goal, requires_confirmation=requires_confirmation, steps=steps)


# ===========================================================================
# ContextManager (context/context_manager.py)
# ===========================================================================

class TestContextManagerTimeContext:
    def test_time_context_has_required_keys(self):
        """get_time_context returns all expected keys."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_time_context()
        for key in ("timestamp", "time_of_day", "hour", "day_of_week", "is_weekend", "is_work_hours"):
            assert key in ctx

    def test_time_of_day_is_valid_value(self):
        """time_of_day is one of the four recognised values."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_time_context()
        assert ctx["time_of_day"] in ("morning", "afternoon", "evening", "night")

    def test_is_weekend_is_bool(self):
        """is_weekend is a boolean."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_time_context()
        assert isinstance(ctx["is_weekend"], bool)

    def test_is_work_hours_is_bool(self):
        """is_work_hours is a boolean."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_time_context()
        assert isinstance(ctx["is_work_hours"], bool)

    def test_timestamp_format(self):
        """timestamp follows YYYY-MM-DD HH:MM:SS format."""
        from zenus_core.context.context_manager import ContextManager
        from datetime import datetime
        cm = ContextManager()
        ctx = cm.get_time_context()
        # Should be parseable
        datetime.strptime(ctx["timestamp"], "%Y-%m-%d %H:%M:%S")


class TestContextManagerDirectoryContext:
    def test_directory_context_has_required_keys(self):
        """get_directory_context returns all expected keys."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_directory_context()
        for key in ("path", "absolute_path", "project_name", "project_type", "is_home"):
            assert key in ctx

    def test_absolute_path_is_absolute(self):
        """absolute_path is an absolute filesystem path."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_directory_context()
        assert os.path.isabs(ctx["absolute_path"])

    def test_project_name_is_directory_basename(self):
        """project_name matches the basename of the current directory."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_directory_context()
        assert ctx["project_name"] == os.path.basename(os.getcwd())


class TestContextManagerDetectProjectType:
    def test_detects_python_from_pyproject(self):
        """Presence of pyproject.toml yields Python project type."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "pyproject.toml").write_text("")
            assert cm._detect_project_type(tmp) == "Python"

    def test_detects_node_from_package_json(self):
        """Presence of package.json yields Node.js project type."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "package.json").write_text("{}")
            assert cm._detect_project_type(tmp) == "Node.js"

    def test_detects_rust_from_cargo_toml(self):
        """Presence of Cargo.toml yields Rust project type."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "Cargo.toml").write_text("")
            assert cm._detect_project_type(tmp) == "Rust"

    def test_returns_none_for_unknown(self):
        """Empty directory returns None for project type."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        with tempfile.TemporaryDirectory() as tmp:
            assert cm._detect_project_type(tmp) is None


class TestContextManagerTrackFileAccess:
    def test_track_adds_file_to_recent(self):
        """track_file_access prepends the file to recent_files."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        cm.track_file_access("/tmp/foo.txt")
        assert "/tmp/foo.txt" in cm.recent_files

    def test_track_does_not_duplicate(self):
        """tracking the same file twice doesn't create a duplicate entry."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        cm.track_file_access("/tmp/foo.txt")
        cm.track_file_access("/tmp/foo.txt")
        assert cm.recent_files.count("/tmp/foo.txt") == 1

    def test_track_trims_to_max(self):
        """recent_files never exceeds max_recent_files."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        for i in range(cm.max_recent_files + 5):
            cm.track_file_access(f"/tmp/file{i}.txt")
        assert len(cm.recent_files) <= cm.max_recent_files


class TestContextManagerGetFullContext:
    def test_full_context_has_all_sections(self):
        """get_full_context contains all expected section keys."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_full_context()
        for key in ("directory", "git", "time", "processes", "recent_files", "system"):
            assert key in ctx

    def test_contextual_prompt_is_string(self):
        """get_contextual_prompt returns a non-empty string."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        prompt = cm.get_contextual_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestContextManagerSystemContext:
    def test_system_context_has_required_keys(self):
        """get_system_context always returns the expected keys."""
        from zenus_core.context.context_manager import ContextManager
        cm = ContextManager()
        ctx = cm.get_system_context()
        for key in ("load_average", "disk_usage_percent", "is_busy", "low_disk"):
            assert key in ctx


class TestGetContextManagerSingleton:
    def test_returns_same_instance(self):
        """get_context_manager returns the same object on repeated calls."""
        from zenus_core.context import context_manager as cm_mod
        cm_mod._context_manager = None
        a = cm_mod.get_context_manager()
        b = cm_mod.get_context_manager()
        assert a is b
        cm_mod._context_manager = None


# ===========================================================================
# FeedbackEntry (feedback/collector.py)
# ===========================================================================

class TestFeedbackEntry:
    def test_to_dict_round_trip(self):
        """FeedbackEntry.to_dict returns all expected fields."""
        from zenus_core.feedback.collector import FeedbackEntry
        entry = FeedbackEntry(
            timestamp="2024-01-01T10:00:00",
            user_input="list files",
            intent_goal="List all files",
            tool_used="FileOps",
            feedback="positive",
            execution_time_ms=120.0,
            success=True,
            comment=None
        )
        d = entry.to_dict()
        assert d["feedback"] == "positive"
        assert d["tool_used"] == "FileOps"
        assert d["success"] is True


# ===========================================================================
# FeedbackCollector (feedback/collector.py)
# ===========================================================================

class TestFeedbackCollectorDisabled:
    def test_collect_returns_none_when_disabled(self):
        """collect() returns None when prompts are disabled."""
        from zenus_core.feedback.collector import FeedbackCollector
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            collector = FeedbackCollector(feedback_path=path, enable_prompts=False)
            intent = make_intent()
            result = collector.collect("list files", intent, 100.0, True)
            assert result is None
        finally:
            os.unlink(path)

    def test_env_var_disables_prompts(self):
        """ZENUS_FEEDBACK_PROMPTS=false disables prompts regardless of constructor arg."""
        from zenus_core.feedback.collector import FeedbackCollector
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch.dict(os.environ, {"ZENUS_FEEDBACK_PROMPTS": "false"}):
                collector = FeedbackCollector(feedback_path=path, enable_prompts=True)
            assert collector.enable_prompts is False
        finally:
            os.unlink(path)


class TestFeedbackCollectorStats:
    def _make_collector_with_data(self, entries):
        """Write entries to a temp JSONL file and return a FeedbackCollector."""
        from zenus_core.feedback.collector import FeedbackCollector
        f = tempfile.NamedTemporaryFile(
            suffix=".jsonl", delete=False, mode='w'
        )
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
        f.close()
        return FeedbackCollector(feedback_path=f.name, enable_prompts=False), f.name

    def test_stats_empty_file_returns_zeros(self):
        """Stats on an empty feedback file return zero counts."""
        from zenus_core.feedback.collector import FeedbackCollector
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            collector = FeedbackCollector(feedback_path=path, enable_prompts=False)
            stats = collector.get_stats()
            assert stats["total_feedback"] == 0
        finally:
            os.unlink(path)

    def test_stats_count_positive_and_negative(self):
        """Stats correctly count positive/negative entries."""
        entries = [
            {"feedback": "positive", "tool_used": "FileOps", "success": True},
            {"feedback": "positive", "tool_used": "FileOps", "success": True},
            {"feedback": "negative", "tool_used": "FileOps", "success": False},
        ]
        collector, path = self._make_collector_with_data(entries)
        try:
            stats = collector.get_stats()
            assert stats["positive"] == 2
            assert stats["negative"] == 1
            assert stats["total_feedback"] == 3
        finally:
            os.unlink(path)

    def test_stats_positive_rate(self):
        """Stats compute positive_rate correctly."""
        entries = [
            {"feedback": "positive", "tool_used": "A", "success": True},
            {"feedback": "negative", "tool_used": "A", "success": False},
        ]
        collector, path = self._make_collector_with_data(entries)
        try:
            stats = collector.get_stats()
            assert abs(stats["positive_rate"] - 0.5) < 0.01
        finally:
            os.unlink(path)

    def test_stats_by_tool(self):
        """Stats group entries by tool_used."""
        entries = [
            {"feedback": "positive", "tool_used": "FileOps", "success": True},
            {"feedback": "negative", "tool_used": "GitOps", "success": False},
        ]
        collector, path = self._make_collector_with_data(entries)
        try:
            stats = collector.get_stats()
            assert "FileOps" in stats["by_tool"]
            assert "GitOps" in stats["by_tool"]
        finally:
            os.unlink(path)

    def test_stats_cache_is_used(self):
        """Subsequent calls within TTL return the cached stats dict."""
        from zenus_core.feedback.collector import FeedbackCollector
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            collector = FeedbackCollector(feedback_path=path, enable_prompts=False)
            s1 = collector.get_stats()
            s2 = collector.get_stats()
            assert s1 is s2  # Same object = cache hit
        finally:
            os.unlink(path)


class TestFeedbackCollectorSanitize:
    def test_sanitize_removes_password(self):
        """_sanitize_text redacts password-like tokens."""
        from zenus_core.feedback.collector import FeedbackCollector
        collector = FeedbackCollector(enable_prompts=False)
        result = collector._sanitize_text("password: mySecret123")
        assert "mySecret123" not in result
        assert "[REDACTED]" in result

    def test_sanitize_removes_email(self):
        """_sanitize_text redacts email addresses."""
        from zenus_core.feedback.collector import FeedbackCollector
        collector = FeedbackCollector(enable_prompts=False)
        result = collector._sanitize_text("contact user@example.com about it")
        assert "user@example.com" not in result
        assert "[EMAIL]" in result

    def test_sanitize_leaves_normal_text_unchanged(self):
        """_sanitize_text leaves ordinary text untouched."""
        from zenus_core.feedback.collector import FeedbackCollector
        collector = FeedbackCollector(enable_prompts=False)
        text = "list files in the documents folder"
        assert collector._sanitize_text(text) == text


class TestFeedbackCollectorExport:
    def test_export_creates_file(self):
        """export_training_data creates an output file."""
        from zenus_core.feedback.collector import FeedbackCollector
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w') as fin:
            entry = {
                "feedback": "positive",
                "tool_used": "FileOps",
                "success": True,
                "user_input": "list files",
                "intent_goal": "List all files",
            }
            fin.write(json.dumps(entry) + "\n")
            feedback_path = fin.name

        out_path = tempfile.mktemp(suffix=".jsonl")
        try:
            collector = FeedbackCollector(feedback_path=feedback_path, enable_prompts=False)
            result = collector.export_training_data(output_path=out_path)
            assert "Exported" in result
            assert Path(out_path).exists()
        finally:
            os.unlink(feedback_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_export_skips_negative_by_default(self):
        """export_training_data skips negative entries when include_negative=False."""
        from zenus_core.feedback.collector import FeedbackCollector
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w') as fin:
            for fb in ("positive", "negative", "skip"):
                entry = {
                    "feedback": fb, "tool_used": "FileOps", "success": True,
                    "user_input": "test", "intent_goal": "test"
                }
                fin.write(json.dumps(entry) + "\n")
            feedback_path = fin.name

        out_path = tempfile.mktemp(suffix=".jsonl")
        try:
            collector = FeedbackCollector(feedback_path=feedback_path, enable_prompts=False)
            collector.export_training_data(output_path=out_path, include_negative=False)
            with open(out_path) as f:
                lines = [l for l in f if l.strip()]
            # Only positive entries should be exported
            assert len(lines) == 1
        finally:
            os.unlink(feedback_path)
            if os.path.exists(out_path):
                os.unlink(out_path)


class TestGetFeedbackCollectorSingleton:
    def test_returns_same_instance(self):
        """get_feedback_collector returns the same object on repeated calls."""
        from zenus_core.feedback import collector as col_mod
        col_mod._feedback_collector = None
        a = col_mod.get_feedback_collector()
        b = col_mod.get_feedback_collector()
        assert a is b
        col_mod._feedback_collector = None


# ===========================================================================
# WorkflowStep / Workflow (workflows/recorder.py)
# ===========================================================================

class TestWorkflowStep:
    def test_default_timestamp_is_set(self):
        """WorkflowStep sets a timestamp by default."""
        from zenus_core.workflows.recorder import WorkflowStep
        step = WorkflowStep(command="list files")
        assert step.timestamp is not None

    def test_duration_defaults_to_zero(self):
        """WorkflowStep.duration defaults to 0."""
        from zenus_core.workflows.recorder import WorkflowStep
        step = WorkflowStep(command="list files")
        assert step.duration == 0.0


class TestWorkflow:
    def test_to_dict_and_from_dict_round_trip(self):
        """Workflow round-trips through to_dict / from_dict."""
        from zenus_core.workflows.recorder import Workflow, WorkflowStep
        step = WorkflowStep(command="do something", result="ok")
        wf = Workflow(name="my_wf", description="test", steps=[step])
        d = wf.to_dict()
        restored = Workflow.from_dict(d)
        assert restored.name == "my_wf"
        assert len(restored.steps) == 1
        assert restored.steps[0].command == "do something"

    def test_default_use_count_is_zero(self):
        """Newly created Workflow has use_count=0."""
        from zenus_core.workflows.recorder import Workflow
        wf = Workflow(name="x", description="", steps=[])
        assert wf.use_count == 0


# ===========================================================================
# WorkflowRecorder (workflows/recorder.py)
# ===========================================================================

class TestWorkflowRecorder:
    def _make_recorder(self):
        """Create a WorkflowRecorder backed by a temp directory."""
        from zenus_core.workflows.recorder import WorkflowRecorder
        tmp = tempfile.mkdtemp()
        return WorkflowRecorder(workflows_dir=tmp), tmp

    # --- start / stop / cancel recording ---

    def test_start_recording_sets_recording_flag(self):
        """start_recording activates the recording state."""
        recorder, _ = self._make_recorder()
        recorder.start_recording("test_wf")
        assert recorder.recording is True

    def test_start_recording_while_active_returns_message(self):
        """start_recording while already recording returns a warning."""
        recorder, _ = self._make_recorder()
        recorder.start_recording("first")
        msg = recorder.start_recording("second")
        assert "already recording" in msg.lower() or "stop" in msg.lower()

    def test_stop_recording_no_steps_discards(self):
        """stop_recording with no steps does not save a file."""
        recorder, tmp = self._make_recorder()
        recorder.start_recording("empty_wf")
        msg = recorder.stop_recording()
        assert "discarded" in msg.lower() or "no steps" in msg.lower()
        assert not Path(tmp, "empty_wf.json").exists()

    def test_stop_recording_saves_file(self):
        """stop_recording with steps saves the workflow JSON."""
        recorder, tmp = self._make_recorder()
        recorder.start_recording("my_wf")
        recorder.record_step("list files", "3 files")
        msg = recorder.stop_recording()
        assert "saved" in msg.lower() or "my_wf" in msg
        assert Path(tmp, "my_wf.json").exists()

    def test_stop_recording_resets_state(self):
        """After stop_recording the recorder is no longer in recording mode."""
        recorder, _ = self._make_recorder()
        recorder.start_recording("wf")
        recorder.record_step("cmd")
        recorder.stop_recording()
        assert recorder.recording is False

    def test_cancel_recording_clears_state(self):
        """cancel_recording resets recording state without saving."""
        recorder, tmp = self._make_recorder()
        recorder.start_recording("cancel_me")
        recorder.record_step("something")
        recorder.cancel_recording()
        assert recorder.recording is False
        assert not Path(tmp, "cancel_me.json").exists()

    def test_cancel_when_not_recording(self):
        """cancel_recording when idle returns appropriate message."""
        recorder, _ = self._make_recorder()
        msg = recorder.cancel_recording()
        assert "not" in msg.lower()

    # --- record_step ---

    def test_record_step_when_not_recording_is_noop(self):
        """record_step is a no-op when not in recording mode."""
        recorder, _ = self._make_recorder()
        recorder.record_step("ignored command")
        assert recorder.current_steps == []

    def test_record_step_appends_step(self):
        """record_step appends a WorkflowStep to current_steps."""
        recorder, _ = self._make_recorder()
        recorder.start_recording("wf")
        recorder.record_step("list files", "done", 0.1)
        assert len(recorder.current_steps) == 1
        assert recorder.current_steps[0].command == "list files"

    # --- save / load ---

    def test_load_workflow_returns_none_for_missing(self):
        """load_workflow returns None for a non-existent workflow."""
        recorder, _ = self._make_recorder()
        assert recorder.load_workflow("nonexistent") is None

    def test_save_and_load_workflow(self):
        """save_workflow followed by load_workflow returns the same data."""
        from zenus_core.workflows.recorder import Workflow, WorkflowStep
        recorder, _ = self._make_recorder()
        wf = Workflow(
            name="saved_wf", description="desc",
            steps=[WorkflowStep(command="do it")]
        )
        recorder.save_workflow(wf)
        loaded = recorder.load_workflow("saved_wf")
        assert loaded is not None
        assert loaded.name == "saved_wf"
        assert len(loaded.steps) == 1

    # --- list / delete ---

    def test_list_workflows_empty(self):
        """list_workflows returns empty list for a new directory."""
        recorder, _ = self._make_recorder()
        assert recorder.list_workflows() == []

    def test_list_workflows_returns_sorted_names(self):
        """list_workflows returns workflow names sorted alphabetically."""
        from zenus_core.workflows.recorder import Workflow
        recorder, _ = self._make_recorder()
        for name in ("beta", "alpha", "gamma"):
            recorder.save_workflow(Workflow(name=name, description="", steps=[]))
        names = recorder.list_workflows()
        assert names == sorted(names)

    def test_delete_existing_workflow(self):
        """delete_workflow removes the file and confirms deletion."""
        from zenus_core.workflows.recorder import Workflow
        recorder, tmp = self._make_recorder()
        recorder.save_workflow(Workflow(name="del_me", description="", steps=[]))
        msg = recorder.delete_workflow("del_me")
        assert "del_me" in msg
        assert not Path(tmp, "del_me.json").exists()

    def test_delete_nonexistent_workflow(self):
        """delete_workflow returns 'not found' for missing workflow."""
        recorder, _ = self._make_recorder()
        msg = recorder.delete_workflow("ghost")
        assert "not found" in msg.lower() or "ghost" in msg

    # --- get_workflow_info ---

    def test_get_workflow_info_returns_dict(self):
        """get_workflow_info returns a dict with expected keys."""
        from zenus_core.workflows.recorder import Workflow, WorkflowStep
        recorder, _ = self._make_recorder()
        wf = Workflow(
            name="info_wf", description="test wf",
            steps=[WorkflowStep(command="step1")]
        )
        recorder.save_workflow(wf)
        info = recorder.get_workflow_info("info_wf")
        assert info is not None
        for key in ("name", "description", "steps", "created", "last_used", "use_count", "parameters"):
            assert key in info

    def test_get_workflow_info_steps_count(self):
        """get_workflow_info.steps reflects actual step count."""
        from zenus_core.workflows.recorder import Workflow, WorkflowStep
        recorder, _ = self._make_recorder()
        steps = [WorkflowStep(command=f"step{i}") for i in range(3)]
        wf = Workflow(name="three_steps", description="", steps=steps)
        recorder.save_workflow(wf)
        info = recorder.get_workflow_info("three_steps")
        assert info["steps"] == 3

    # --- replay ---

    def test_replay_nonexistent_returns_not_found(self):
        """replay_workflow returns a 'not found' message for missing workflow."""
        recorder, _ = self._make_recorder()
        result = recorder.replay_workflow("ghost", dry_run=True)
        assert "not found" in result[0].lower()

    def test_replay_returns_command_list(self):
        """replay_workflow returns one command string per step."""
        from zenus_core.workflows.recorder import Workflow, WorkflowStep
        recorder, _ = self._make_recorder()
        wf = Workflow(
            name="replay_wf", description="",
            steps=[WorkflowStep(command="cmd1"), WorkflowStep(command="cmd2")]
        )
        recorder.save_workflow(wf)
        cmds = recorder.replay_workflow("replay_wf", dry_run=True)
        assert cmds == ["cmd1", "cmd2"]

    def test_replay_parameter_substitution(self):
        """replay_workflow substitutes {param} placeholders."""
        from zenus_core.workflows.recorder import Workflow, WorkflowStep
        recorder, _ = self._make_recorder()
        wf = Workflow(
            name="param_wf", description="",
            steps=[WorkflowStep(command="backup {folder}")]
        )
        recorder.save_workflow(wf)
        cmds = recorder.replay_workflow(
            "param_wf", parameters={"folder": "Documents"}, dry_run=True
        )
        assert cmds[0] == "backup Documents"

    def test_replay_increments_use_count(self):
        """replay_workflow (non-dry-run) increments use_count."""
        from zenus_core.workflows.recorder import Workflow, WorkflowStep
        recorder, _ = self._make_recorder()
        wf = Workflow(
            name="count_wf", description="",
            steps=[WorkflowStep(command="do it")]
        )
        recorder.save_workflow(wf)
        recorder.replay_workflow("count_wf", dry_run=False)
        loaded = recorder.load_workflow("count_wf")
        assert loaded.use_count == 1

    # --- parameterize ---

    def test_parameterize_workflow_saves_parameters(self):
        """parameterize_workflow stores the parameter list on the workflow."""
        from zenus_core.workflows.recorder import Workflow
        recorder, _ = self._make_recorder()
        recorder.save_workflow(Workflow(name="p_wf", description="", steps=[]))
        msg = recorder.parameterize_workflow("p_wf", ["folder", "date"])
        loaded = recorder.load_workflow("p_wf")
        assert loaded.parameters == ["folder", "date"]
        assert "folder" in msg

    # --- export / import ---

    def test_export_and_import_round_trip(self):
        """export then import preserves the workflow name and steps."""
        from zenus_core.workflows.recorder import Workflow, WorkflowStep
        recorder, _ = self._make_recorder()
        wf = Workflow(
            name="export_wf", description="exported",
            steps=[WorkflowStep(command="step1")]
        )
        recorder.save_workflow(wf)

        export_path = tempfile.mktemp(suffix=".json")
        try:
            recorder.export_workflow("export_wf", export_path)
            msg = recorder.import_workflow(export_path)
            assert "export_wf" in msg
            loaded = recorder.load_workflow("export_wf")
            assert loaded is not None
            assert loaded.description == "exported"
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_import_nonexistent_file_returns_error(self):
        """import_workflow with a bad path returns an error message."""
        recorder, _ = self._make_recorder()
        msg = recorder.import_workflow("/tmp/does_not_exist_12345.json")
        assert "failed" in msg.lower() or "error" in msg.lower()


class TestGetWorkflowRecorderSingleton:
    def test_returns_same_instance(self):
        """get_workflow_recorder returns the same object on repeated calls."""
        from zenus_core.workflows import recorder as rec_mod
        rec_mod._recorder = None
        a = rec_mod.get_workflow_recorder()
        b = rec_mod.get_workflow_recorder()
        assert a is b
        rec_mod._recorder = None
