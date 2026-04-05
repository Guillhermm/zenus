"""
Unit tests for SessionStore and ContextCompactor.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------

class TestSessionStore:
    def _make_session_memory(self, history=None, refs=None):
        m = MagicMock()
        m.intent_history = list(history or [])
        m.context_refs = list(refs or [])
        return m

    def _store_with_tmpdir(self, tmp_path):
        from zenus_core.memory.session_store import SessionStore
        store = SessionStore()

        mock_cfg = MagicMock()
        mock_cfg.session.persist = True
        mock_cfg.session.max_sessions = 10
        mock_cfg.session.sessions_dir = str(tmp_path)

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            return store, mock_cfg

    def test_save_creates_json_file(self, tmp_path):
        store, mock_cfg = self._store_with_tmpdir(tmp_path)
        mem = self._make_session_memory(
            history=[{"user_input": "list files", "intent": {"goal": "list"}, "results": ["ok"]}]
        )

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            with patch("zenus_core.memory.session_store._sessions_dir", return_value=tmp_path):
                sid = store.save(mem)

        assert sid != ""
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1

    def test_saved_file_is_owner_only(self, tmp_path):
        store, mock_cfg = self._store_with_tmpdir(tmp_path)
        mem = self._make_session_memory(
            history=[{"user_input": "test", "intent": {}, "results": []}]
        )

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            with patch("zenus_core.memory.session_store._sessions_dir", return_value=tmp_path):
                store.save(mem)

        for f in tmp_path.glob("*.json"):
            mode = oct(f.stat().st_mode)[-3:]
            assert mode == "600", f"File {f.name} has mode {mode}, expected 600"

    def test_load_by_id_prefix(self, tmp_path):
        store, mock_cfg = self._store_with_tmpdir(tmp_path)
        mem = self._make_session_memory(
            history=[{"user_input": "do something", "intent": {"goal": "g"}, "results": ["r"]}]
        )

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            with patch("zenus_core.memory.session_store._sessions_dir", return_value=tmp_path):
                sid = store.save(mem)
                data = store.load(sid)

        assert data is not None
        assert data["id"] == sid

    def test_load_nonexistent_returns_none(self, tmp_path):
        store, mock_cfg = self._store_with_tmpdir(tmp_path)
        with patch("zenus_core.memory.session_store._sessions_dir", return_value=tmp_path):
            assert store.load("doesnotexist") is None

    def test_list_sessions_newest_first(self, tmp_path):
        store, mock_cfg = self._store_with_tmpdir(tmp_path)

        for i in range(3):
            mem = self._make_session_memory(
                history=[{"user_input": f"cmd{i}", "intent": {}, "results": []}]
            )
            with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
                with patch("zenus_core.memory.session_store._sessions_dir", return_value=tmp_path):
                    store.save(mem)

        with patch("zenus_core.memory.session_store._sessions_dir", return_value=tmp_path):
            sessions = store.list_sessions()

        assert len(sessions) == 3

    def test_delete_removes_file(self, tmp_path):
        store, mock_cfg = self._store_with_tmpdir(tmp_path)
        mem = self._make_session_memory(
            history=[{"user_input": "x", "intent": {}, "results": []}]
        )

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            with patch("zenus_core.memory.session_store._sessions_dir", return_value=tmp_path):
                sid = store.save(mem)
                ok = store.delete(sid)

        assert ok is True
        assert not list(tmp_path.glob(f"{sid}*.json"))

    def test_restore_into_replaces_history(self, tmp_path):
        store, mock_cfg = self._store_with_tmpdir(tmp_path)
        saved_data = {
            "id": "abc", "name": "test",
            "intent_history": [{"user_input": "restored"}],
            "context_refs": ["ref1"],
        }
        mem = self._make_session_memory()
        store.restore_into(saved_data, mem)

        assert mem.intent_history == [{"user_input": "restored"}]
        assert mem.context_refs == ["ref1"]

    def test_persist_disabled_returns_empty_id(self, tmp_path):
        from zenus_core.memory.session_store import SessionStore
        store = SessionStore()
        mock_cfg = MagicMock()
        mock_cfg.session.persist = False
        mock_cfg.session.max_sessions = 10
        mock_cfg.session.sessions_dir = str(tmp_path)

        mem = self._make_session_memory(
            history=[{"user_input": "x", "intent": {}, "results": []}]
        )
        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            sid = store.save(mem)

        assert sid == ""

    def test_auto_prune_respects_max_sessions(self, tmp_path):
        from zenus_core.memory.session_store import SessionStore
        store = SessionStore()
        mock_cfg = MagicMock()
        mock_cfg.session.persist = True
        mock_cfg.session.max_sessions = 3
        mock_cfg.session.sessions_dir = str(tmp_path)

        for i in range(5):
            mem = self._make_session_memory(
                history=[{"user_input": f"cmd{i}", "intent": {}, "results": []}]
            )
            with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
                with patch("zenus_core.memory.session_store._sessions_dir", return_value=tmp_path):
                    store.save(mem)

        remaining = list(tmp_path.glob("*.json"))
        assert len(remaining) <= 3


# ---------------------------------------------------------------------------
# ContextCompactor
# ---------------------------------------------------------------------------

class TestContextCompactor:
    def _make_session_memory_with_history(self, entries):
        m = MagicMock()
        m.intent_history = list(entries)
        return m

    def test_compact_empty_history_returns_empty_string(self):
        from zenus_core.context.compactor import compact_session
        mem = self._make_session_memory_with_history([])
        result = compact_session(mem)
        assert result == ""

    def test_compact_calls_llm_and_replaces_history(self):
        from zenus_core.context.compactor import compact_session

        entries = [
            {"user_input": "do X", "intent": {"goal": "X"}, "results": ["done"]},
            {"user_input": "do Y", "intent": {"goal": "Y"}, "results": ["done"]},
        ]
        mem = self._make_session_memory_with_history(entries)

        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Summary: did X and Y"

        with patch("zenus_core.brain.llm.factory.get_llm", return_value=mock_llm):
            result = compact_session(mem)

        assert "Summary" in result
        assert len(mem.intent_history) == 1
        assert mem.intent_history[0].get("compacted") is True

    def test_compact_handles_llm_failure_gracefully(self):
        from zenus_core.context.compactor import compact_session

        entries = [{"user_input": "x", "intent": {}, "results": []}]
        mem = self._make_session_memory_with_history(entries)

        with patch("zenus_core.brain.llm.factory.get_llm", side_effect=RuntimeError("LLM down")):
            result = compact_session(mem)

        assert result == ""
        # History should be unchanged since compaction failed
        assert len(mem.intent_history) == 1

    def test_maybe_compact_skips_below_threshold(self):
        from zenus_core.context.compactor import maybe_compact

        mem = self._make_session_memory_with_history([{"user_input": "x", "intent": {}, "results": []}])
        mock_cfg = MagicMock()
        mock_cfg.session.compact_threshold = 0.80

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            # 50% usage — below 80% threshold
            result = maybe_compact(mem, token_count=500, max_tokens=1000)

        assert result is False

    def test_maybe_compact_triggers_above_threshold(self):
        from zenus_core.context.compactor import maybe_compact

        entries = [{"user_input": "x", "intent": {}, "results": []}]
        mem = self._make_session_memory_with_history(entries)
        mock_cfg = MagicMock()
        mock_cfg.session.compact_threshold = 0.80

        mock_llm = MagicMock()
        mock_llm.ask.return_value = "Summary"

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            with patch("zenus_core.brain.llm.factory.get_llm", return_value=mock_llm):
                with patch("zenus_core.output.console.print_warning"):
                    with patch("zenus_core.output.console.print_info"):
                        result = maybe_compact(mem, token_count=850, max_tokens=1000)

        assert result is True
