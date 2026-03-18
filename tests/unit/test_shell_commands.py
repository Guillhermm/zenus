"""
Unit tests for shell/commands.py

Patch targets are at the SOURCE location of lazy imports (inside function bodies):
  get_config → zenus_core.config.loader.get_config
  get_available_providers → zenus_core.brain.llm.factory.get_available_providers
  get_explainability_dashboard → zenus_core.shell.explain.get_explainability_dashboard
  get_pattern_detector → zenus_core.brain.pattern_detector.get_pattern_detector
  get_pattern_memory → zenus_core.brain.pattern_memory.get_pattern_memory
  get_workflow_recorder → zenus_core.workflows.get_workflow_recorder
  IntentHistory → zenus_core.memory.intent_history.IntentHistory
"""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch

_GET_CONFIG = "zenus_core.config.loader.get_config"
_GET_PROVIDERS = "zenus_core.brain.llm.factory.get_available_providers"
_GET_EXPLAIN_DASH = "zenus_core.shell.explain.get_explainability_dashboard"
_GET_PATTERN_DET = "zenus_core.brain.pattern_detector.get_pattern_detector"
_GET_PATTERN_MEM = "zenus_core.brain.pattern_memory.get_pattern_memory"
_GET_WORKFLOW_REC = "zenus_core.workflows.get_workflow_recorder"
_INTENT_HISTORY = "zenus_core.shell.commands.IntentHistory"


def _make_orch(**kw):
    orch = Mock()
    orch.use_memory = kw.get("use_memory", True)
    orch.session_memory = Mock()
    orch.session_memory.get_session_stats.return_value = {
        "session_duration_seconds": 42.0, "total_intents": 5, "context_refs": 2,
    }
    orch.world_model = Mock()
    orch.world_model.get_summary.return_value = "2 known paths"
    orch.world_model.get_frequent_paths.return_value = ["/home/user", "/tmp"]
    orch.router = Mock()
    orch.router.stats = {"total_requests": 10, "total_cost": 0.0025}
    return orch


def _mc():
    return MagicMock()


def _cfg(provider="anthropic", model=None, fallback_enabled=False, fallback_providers=None):
    cfg = Mock()
    cfg.llm.provider = provider
    cfg.llm.model = model
    cfg.fallback.enabled = fallback_enabled
    cfg.fallback.providers = fallback_providers or []
    return cfg


# ===========================================================================
# handle_status_command
# ===========================================================================

class TestHandleStatusCommand:

    def test_runs_without_error(self):
        from zenus_core.shell.commands import handle_status_command
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_PROVIDERS, return_value=["anthropic"]):
                with patch(_GET_CONFIG, return_value=_cfg()):
                    handle_status_command(_make_orch())

    def test_memory_disabled_no_crash(self):
        from zenus_core.shell.commands import handle_status_command
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_PROVIDERS, return_value=[]):
                with patch(_GET_CONFIG, side_effect=Exception("no cfg")):
                    handle_status_command(_make_orch(use_memory=False))

    def test_config_exception_fallback(self):
        from zenus_core.shell.commands import handle_status_command
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_PROVIDERS, return_value=[]):
                with patch(_GET_CONFIG, side_effect=Exception("oops")):
                    handle_status_command(_make_orch())

    def test_fallback_disabled_printed(self):
        from zenus_core.shell.commands import handle_status_command
        con = _mc()
        with patch("rich.console.Console", return_value=con):
            with patch(_GET_PROVIDERS, return_value=["anthropic"]):
                with patch(_GET_CONFIG, return_value=_cfg(fallback_enabled=False)):
                    handle_status_command(_make_orch())
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "disabled" in printed.lower()

    def test_fallback_chain_printed(self):
        from zenus_core.shell.commands import handle_status_command
        con = _mc()
        with patch("rich.console.Console", return_value=con):
            with patch(_GET_PROVIDERS, return_value=["anthropic"]):
                with patch(_GET_CONFIG, return_value=_cfg(fallback_enabled=True, fallback_providers=["openai"])):
                    handle_status_command(_make_orch())
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "openai" in printed.lower()


# ===========================================================================
# handle_model_command
# ===========================================================================

class TestHandleModelCommand:

    def _call(self, sub="status", args=None, cfg=None):
        from zenus_core.shell.commands import handle_model_command
        con = _mc()
        with patch("rich.console.Console", return_value=con):
            with patch(_GET_PROVIDERS, return_value=["anthropic"]):
                with patch(_GET_CONFIG, return_value=(cfg or _cfg())):
                    handle_model_command(subcommand=sub, args=args)
        return con

    def test_status(self):
        con = self._call("status")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "anthropic" in printed.lower()

    def test_empty_is_status(self):
        con = self._call("")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "anthropic" in printed.lower()

    def test_list(self):
        from zenus_core.shell.commands import handle_model_command
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_PROVIDERS, return_value=[]):
                handle_model_command(subcommand="list")

    def test_set_no_args_usage(self):
        from zenus_core.shell.commands import handle_model_command
        con = _mc()
        with patch("rich.console.Console", return_value=con):
            with patch(_GET_PROVIDERS, return_value=[]):
                handle_model_command(subcommand="set", args=[])
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "Usage" in printed

    def test_set_invalid_provider(self):
        from zenus_core.shell.commands import handle_model_command
        con = _mc()
        with patch("rich.console.Console", return_value=con):
            with patch(_GET_PROVIDERS, return_value=[]):
                handle_model_command(subcommand="set", args=["notaprovider"])
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "Unknown provider" in printed or "notaprovider" in printed

    def test_set_valid_provider_calls_update(self):
        from zenus_core.shell.commands import handle_model_command
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_PROVIDERS, return_value=[]):
                with patch("zenus_core.shell.commands._update_config_provider") as mock_upd:
                    handle_model_command(subcommand="set", args=["anthropic", "claude-opus-4-6"])
        mock_upd.assert_called_once_with("anthropic", "claude-opus-4-6")

    def test_set_provider_only_passes_none_model(self):
        from zenus_core.shell.commands import handle_model_command
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_PROVIDERS, return_value=[]):
                with patch("zenus_core.shell.commands._update_config_provider") as mock_upd:
                    handle_model_command(subcommand="set", args=["openai"])
        mock_upd.assert_called_once_with("openai", None)

    def test_unknown_subcommand(self):
        from zenus_core.shell.commands import handle_model_command
        con = _mc()
        with patch("rich.console.Console", return_value=con):
            with patch(_GET_PROVIDERS, return_value=[]):
                handle_model_command(subcommand="badcmd")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "badcmd" in printed or "Unknown" in printed

    def test_config_exception_fallback(self):
        from zenus_core.shell.commands import handle_model_command
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_PROVIDERS, return_value=[]):
                with patch(_GET_CONFIG, side_effect=Exception("no config")):
                    handle_model_command(subcommand="status")

    def test_fallback_providers_in_output(self):
        from zenus_core.shell.commands import handle_model_command
        con = _mc()
        with patch("rich.console.Console", return_value=con):
            with patch(_GET_PROVIDERS, return_value=[]):
                with patch(_GET_CONFIG, return_value=_cfg(fallback_enabled=True, fallback_providers=["openai", "deepseek"])):
                    handle_model_command(subcommand="status")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "openai" in printed.lower()


# ===========================================================================
# _update_config_provider
# ===========================================================================

class TestUpdateConfigProvider:

    def test_raises_when_no_config_found(self, tmp_path, monkeypatch):
        from zenus_core.shell.commands import _update_config_provider
        monkeypatch.delenv("ZENUS_CONFIG", raising=False)
        monkeypatch.chdir(tmp_path)
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises((FileNotFoundError, Exception)):
                _update_config_provider("anthropic")

    def test_updates_provider_and_model(self, tmp_path):
        import yaml
        from zenus_core.shell.commands import _update_config_provider
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"llm": {"provider": "openai"}}))
        with patch.dict(os.environ, {"ZENUS_CONFIG": str(config_file)}):
            _update_config_provider("anthropic", "claude-opus-4-6")
        data = yaml.safe_load(open(config_file))
        assert data["llm"]["provider"] == "anthropic"
        assert data["llm"]["model"] == "claude-opus-4-6"

    def test_updates_provider_without_model(self, tmp_path):
        import yaml
        from zenus_core.shell.commands import _update_config_provider
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"llm": {"provider": "openai"}}))
        with patch.dict(os.environ, {"ZENUS_CONFIG": str(config_file)}):
            _update_config_provider("anthropic")
        data = yaml.safe_load(open(config_file))
        assert data["llm"]["provider"] == "anthropic"

    def test_creates_llm_section_if_missing(self, tmp_path):
        import yaml
        from zenus_core.shell.commands import _update_config_provider
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({}))
        with patch.dict(os.environ, {"ZENUS_CONFIG": str(config_file)}):
            _update_config_provider("deepseek")
        data = yaml.safe_load(open(config_file))
        assert data["llm"]["provider"] == "deepseek"


# ===========================================================================
# handle_memory_command
# ===========================================================================

class TestHandleMemoryCommand:

    def test_memory_disabled_prints_message(self, capsys):
        from zenus_core.shell.commands import handle_memory_command
        handle_memory_command(_make_orch(use_memory=False))
        out = capsys.readouterr().out
        assert "disabled" in out.lower() or "Memory" in out

    def test_stats(self, capsys):
        from zenus_core.shell.commands import handle_memory_command
        handle_memory_command(_make_orch(), "stats")
        out = capsys.readouterr().out
        assert "5" in out or "Intents" in out or "Memory" in out

    def test_stats_no_frequent_paths(self, capsys):
        from zenus_core.shell.commands import handle_memory_command
        orch = _make_orch()
        orch.world_model.get_frequent_paths.return_value = []
        handle_memory_command(orch, "stats")

    def test_clear_confirmed(self):
        from zenus_core.shell.commands import handle_memory_command
        orch = _make_orch()
        with patch("builtins.input", return_value="y"):
            handle_memory_command(orch, "clear")
        orch.session_memory.clear.assert_called_once()

    def test_clear_declined(self):
        from zenus_core.shell.commands import handle_memory_command
        orch = _make_orch()
        with patch("builtins.input", return_value="n"):
            handle_memory_command(orch, "clear")
        orch.session_memory.clear.assert_not_called()

    def test_unknown_subcommand(self, capsys):
        from zenus_core.shell.commands import handle_memory_command
        handle_memory_command(_make_orch(), "nope")
        out = capsys.readouterr().out
        assert "nope" in out or "Unknown" in out


# ===========================================================================
# handle_update_command
# ===========================================================================

class TestHandleUpdateCommand:

    def test_runs_without_error(self, capsys):
        from zenus_core.shell.commands import handle_update_command
        mock_result = Mock(); mock_result.stdout = "Up to date."
        with patch("subprocess.run", return_value=mock_result):
            handle_update_command()
        out = capsys.readouterr().out
        assert "Update" in out or "complete" in out.lower()

    def test_git_pull_failure_handled(self, capsys):
        from zenus_core.shell.commands import handle_update_command
        with patch("subprocess.run", side_effect=Exception("git not found")):
            handle_update_command()
        out = capsys.readouterr().out
        assert "failed" in out.lower() or "⚠" in out


# ===========================================================================
# handle_explain_command
# ===========================================================================

class TestHandleExplainCommand:

    def test_last(self):
        from zenus_core.shell.commands import handle_explain_command
        dashboard = Mock()
        with patch(_GET_EXPLAIN_DASH, return_value=dashboard):
            handle_explain_command(_make_orch(), "last")
        dashboard.explain_last.assert_called_once_with(verbose=True)

    def test_history(self):
        from zenus_core.shell.commands import handle_explain_command
        dashboard = Mock()
        with patch(_GET_EXPLAIN_DASH, return_value=dashboard):
            handle_explain_command(_make_orch(), "history")
        dashboard.show_history.assert_called_once_with(limit=20)

    def test_digit(self):
        from zenus_core.shell.commands import handle_explain_command
        dashboard = Mock()
        with patch(_GET_EXPLAIN_DASH, return_value=dashboard):
            handle_explain_command(_make_orch(), "3")
        dashboard.explain_execution.assert_called_once_with(-3, verbose=True)

    def test_unknown_arg_prints_usage(self, capsys):
        from zenus_core.shell.commands import handle_explain_command
        with patch(_GET_EXPLAIN_DASH, return_value=Mock()):
            handle_explain_command(_make_orch(), "badcmd")
        out = capsys.readouterr().out
        assert "Usage" in out or "badcmd" in out


# ===========================================================================
# check_and_suggest_patterns
# ===========================================================================

class TestCheckAndSuggestPatterns:

    def _history(self, items=None):
        h = Mock()
        h.history = items or []
        return h

    def test_no_patterns_returns_early(self):
        from zenus_core.shell.commands import check_and_suggest_patterns
        detector = Mock(); detector.detect_patterns.return_value = []
        with patch(_GET_PATTERN_DET, return_value=detector):
            with patch(_GET_PATTERN_MEM, return_value=Mock()):
                with patch(_INTENT_HISTORY, return_value=self._history()):
                    check_and_suggest_patterns(_make_orch())
        detector.detect_patterns.assert_called_once()

    def test_exception_silenced(self):
        from zenus_core.shell.commands import check_and_suggest_patterns
        detector = Mock()
        detector.detect_patterns.side_effect = Exception("boom")
        with patch(_GET_PATTERN_DET, return_value=detector):
            with patch(_GET_PATTERN_MEM, return_value=Mock()):
                with patch(_INTENT_HISTORY, return_value=self._history()):
                    check_and_suggest_patterns(_make_orch())

    def test_already_suggested_skipped(self):
        from zenus_core.shell.commands import check_and_suggest_patterns
        p = Mock(); p.confidence = 0.9; p.pattern_type = "recurring"
        p.description = "daily test"; p.suggested_cron = "0 9 * * *"
        p.commands = ["run tests"]; p.occurrences = 5
        detector = Mock(); detector.detect_patterns.return_value = [p]
        mem = Mock(); mem.has_suggested.return_value = True
        with patch(_GET_PATTERN_DET, return_value=detector):
            with patch(_GET_PATTERN_MEM, return_value=mem):
                with patch(_INTENT_HISTORY, return_value=self._history()):
                    with patch("rich.console.Console", return_value=_mc()):
                        check_and_suggest_patterns(_make_orch())

    def test_recurring_user_accepts(self):
        from zenus_core.shell.commands import check_and_suggest_patterns
        p = Mock(); p.confidence = 0.9; p.pattern_type = "recurring"
        p.description = "daily test"; p.suggested_cron = "0 9 * * *"
        p.commands = ["run tests"]; p.occurrences = 5
        detector = Mock(); detector.detect_patterns.return_value = [p]
        mem = Mock(); mem.has_suggested.return_value = False
        with patch(_GET_PATTERN_DET, return_value=detector):
            with patch(_GET_PATTERN_MEM, return_value=mem):
                with patch(_INTENT_HISTORY, return_value=self._history()):
                    with patch("rich.console.Console", return_value=_mc()):
                        with patch("builtins.input", return_value="y"):
                            check_and_suggest_patterns(_make_orch())
        mem.mark_suggested.assert_called_once()

    def test_recurring_user_show_more(self):
        from zenus_core.shell.commands import check_and_suggest_patterns
        p = Mock(); p.confidence = 0.9; p.pattern_type = "recurring"
        p.description = "daily test"; p.suggested_cron = "0 9 * * *"
        p.commands = ["run tests"]; p.occurrences = 5
        detector = Mock(); detector.detect_patterns.return_value = [p]
        mem = Mock(); mem.has_suggested.return_value = False
        with patch(_GET_PATTERN_DET, return_value=detector):
            with patch(_GET_PATTERN_MEM, return_value=mem):
                with patch(_INTENT_HISTORY, return_value=self._history()):
                    with patch("rich.console.Console", return_value=_mc()):
                        with patch("builtins.input", return_value="s"):
                            check_and_suggest_patterns(_make_orch())


# ===========================================================================
# handle_workflow_command
# ===========================================================================

class TestHandleWorkflowCommand:

    def _make_recorder(self):
        r = Mock()
        r.list_workflows.return_value = []
        r.get_workflow_info.return_value = {
            "steps": 3, "use_count": 1, "description": "Test wf",
            "created": "2026-03-18", "last_used": None, "parameters": [],
        }
        r.start_recording.return_value = "Recording started"
        r.stop_recording.return_value = "Stopped: my_flow (3 steps)"
        r.cancel_recording.return_value = "Recording cancelled"
        r.replay_workflow.return_value = ["do this", "do that"]
        r.delete_workflow.return_value = "Deleted: my_flow"
        return r

    def _call(self, sub, *args, recorder=None):
        from zenus_core.shell.commands import handle_workflow_command
        orch = _make_orch()
        rec = recorder or self._make_recorder()
        con = _mc()
        with patch("rich.console.Console", return_value=con):
            with patch(_GET_WORKFLOW_REC, return_value=rec):
                handle_workflow_command(orch, sub, *args)
        return con, rec

    def test_list_no_workflows(self):
        con, _ = self._call("list")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "No workflows" in printed or "workflow" in printed.lower()

    def test_list_with_workflows(self):
        rec = self._make_recorder()
        rec.list_workflows.return_value = ["deploy", "test"]
        self._call("list", recorder=rec)

    def test_record_no_args(self):
        con, _ = self._call("record")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "Error" in printed or "name" in printed.lower()

    def test_record_with_name_and_desc(self):
        _, rec = self._call("record", "my_flow", "My description")
        rec.start_recording.assert_called_once_with("my_flow", "My description")

    def test_record_with_name_no_desc(self):
        _, rec = self._call("record", "my_flow")
        rec.start_recording.assert_called_once_with("my_flow", "")

    def test_stop(self):
        _, rec = self._call("stop")
        rec.stop_recording.assert_called_once()

    def test_cancel(self):
        _, rec = self._call("cancel")
        rec.cancel_recording.assert_called_once()

    def test_replay_no_args(self):
        con, _ = self._call("replay")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "Error" in printed or "name" in printed.lower()

    def test_replay_not_found(self):
        rec = self._make_recorder()
        rec.replay_workflow.return_value = ["Workflow not found: x"]
        con, _ = self._call("replay", "x", recorder=rec)
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "not found" in printed.lower() or "Workflow" in printed

    def test_replay_executes_commands(self):
        from zenus_core.shell.commands import handle_workflow_command
        orch = _make_orch()
        rec = self._make_recorder()
        rec.replay_workflow.return_value = ["do this", "do that"]
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_WORKFLOW_REC, return_value=rec):
                handle_workflow_command(orch, "replay", "my_flow")
        assert orch.execute_command.call_count == 2

    def test_replay_command_exception_breaks(self):
        from zenus_core.shell.commands import handle_workflow_command
        orch = _make_orch()
        orch.execute_command.side_effect = Exception("bad")
        rec = self._make_recorder()
        rec.replay_workflow.return_value = ["bad", "also bad"]
        with patch("rich.console.Console", return_value=_mc()):
            with patch(_GET_WORKFLOW_REC, return_value=rec):
                handle_workflow_command(orch, "replay", "my_flow")
        assert orch.execute_command.call_count == 1

    def test_info_no_args(self):
        con, _ = self._call("info")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "Error" in printed or "name" in printed.lower()

    def test_info_not_found(self):
        rec = self._make_recorder()
        rec.get_workflow_info.return_value = None
        con, _ = self._call("info", "ghost", recorder=rec)
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "not found" in printed.lower() or "ghost" in printed

    def test_info_found_with_params(self):
        rec = self._make_recorder()
        rec.get_workflow_info.return_value = {
            "steps": 3, "use_count": 2, "description": "Deploy to prod",
            "created": "2026-03-18", "last_used": "2026-03-18",
            "parameters": ["env", "version"],
        }
        con, _ = self._call("info", "deploy", recorder=rec)
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "Deploy" in printed or "deploy" in printed

    def test_delete_no_args(self):
        con, _ = self._call("delete")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "Error" in printed or "name" in printed.lower()

    def test_delete_with_name(self):
        _, rec = self._call("delete", "my_flow")
        rec.delete_workflow.assert_called_once_with("my_flow")

    def test_unknown_subcommand(self):
        con, _ = self._call("foobar")
        printed = " ".join(str(c) for c in con.print.call_args_list)
        assert "foobar" in printed or "Unknown" in printed
