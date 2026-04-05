"""
Session Store

Saves and restores full Zenus session snapshots so users can resume past
sessions with ``zenus resume <id>`` or the ``/session resume <id>`` command.

Each session is stored as a single JSON file under the sessions directory:
  ~/.zenus/sessions/<session_id>.json

File format::

    {
        "id": "abc12345",
        "name": "fix-auth-bug",
        "created_at": "2026-04-05T18:30:00",
        "cwd": "/home/user/project",
        "intent_history": [...],   # list of intent history records
        "context_refs": [...],     # world model refs
        "cost": 0.0042
    }
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _sessions_dir() -> Path:
    try:
        from zenus_core.config.loader import get_config
        custom = get_config().session.sessions_dir
        if custom:
            return Path(custom)
    except Exception:
        pass
    d = Path.home() / ".zenus" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _auto_name(intent_history: List[Dict]) -> str:
    """Derive a short name from the most recent user input."""
    for entry in reversed(intent_history):
        raw = entry.get("user_input", "")
        if raw and not raw.startswith("["):
            words = raw.split()[:4]
            return "-".join(w.lower() for w in words if w.isalpha())[:30] or "session"
    return "session"


class SessionStore:
    """Saves, loads, lists, and prunes session snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, session_memory, world_model=None) -> str:
        """
        Snapshot the current session and write it to disk.

        Returns the session ID.
        """
        try:
            enabled = True
            max_sessions = 50
            try:
                from zenus_core.config.loader import get_config
                cfg = get_config().session
                enabled = cfg.persist
                max_sessions = cfg.max_sessions
            except Exception:
                pass

            if not enabled:
                return ""

            history = getattr(session_memory, "intent_history", [])
            context_refs = getattr(session_memory, "context_refs", [])

            session_id = _short_id()
            name = _auto_name(history)

            payload: Dict[str, Any] = {
                "id": session_id,
                "name": name,
                "created_at": datetime.now().isoformat(),
                "cwd": os.getcwd(),
                "intent_history": list(history),
                "context_refs": list(context_refs),
            }

            path = _sessions_dir() / f"{session_id}.json"
            with self._lock:
                path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
                os.chmod(path, 0o600)
                self._prune(max_sessions)

            logger.info("Session saved: %s (%s)", session_id, name)
            return session_id

        except Exception as exc:
            logger.warning("Failed to save session: %s", exc)
            return ""

    def load(self, session_id: str) -> Optional[Dict]:
        """Load a session snapshot by ID prefix. Returns None if not found."""
        try:
            sdir = _sessions_dir()
            matches = list(sdir.glob(f"{session_id}*.json"))
            if not matches:
                return None
            path = matches[0]
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load session %s: %s", session_id, exc)
            return None

    def list_sessions(self) -> List[Dict]:
        """Return metadata for all saved sessions, newest first."""
        try:
            sdir = _sessions_dir()
            sessions = []
            for p in sorted(sdir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    sessions.append({
                        "id": data.get("id", p.stem),
                        "name": data.get("name", p.stem),
                        "created_at": data.get("created_at", ""),
                        "cwd": data.get("cwd", ""),
                        "intents": len(data.get("intent_history", [])),
                    })
                except Exception:
                    continue
            return sessions
        except Exception:
            return []

    def delete(self, session_id: str) -> bool:
        """Delete a session snapshot. Returns True if deleted."""
        try:
            sdir = _sessions_dir()
            matches = list(sdir.glob(f"{session_id}*.json"))
            for p in matches:
                p.unlink()
            return bool(matches)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _prune(self, max_sessions: int) -> None:
        """Remove oldest sessions when limit is exceeded (lock must be held)."""
        try:
            sdir = _sessions_dir()
            files = sorted(sdir.glob("*.json"), key=lambda f: f.stat().st_mtime)
            while len(files) > max_sessions:
                files.pop(0).unlink()
        except Exception:
            pass

    def restore_into(self, session_data: Dict, session_memory) -> None:
        """Restore intent_history and context_refs into an existing SessionMemory."""
        try:
            session_memory.intent_history.clear()
            session_memory.intent_history.extend(session_data.get("intent_history", []))
            session_memory.context_refs.clear()
            session_memory.context_refs.extend(session_data.get("context_refs", []))
        except Exception as exc:
            logger.warning("Failed to restore session into memory: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[SessionStore] = None
_store_lock = threading.Lock()


def get_session_store() -> SessionStore:
    """Return the global SessionStore singleton."""
    global _store
    with _store_lock:
        if _store is None:
            _store = SessionStore()
    return _store
