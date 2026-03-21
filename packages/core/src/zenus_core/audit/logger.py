"""
Audit Logger

Records all intent translation and execution flows for review and debugging.
"""

import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional
from zenus_core.brain.llm.schemas import IntentIR

# Patterns that look like secrets — masked before writing to disk.
# Order matters: more specific patterns first.
_SECRET_PATTERNS = [
    (re.compile(r'(?i)(api[_-]?key|apikey|api[_-]?secret)\s*[:=]\s*["\']?([A-Za-z0-9\-_]{16,})["\']?'), r'\1=[REDACTED]'),
    (re.compile(r'(?i)(token|secret|password|passwd|auth|bearer|credential)\s*[:=]\s*["\']?([A-Za-z0-9\-_\.]{8,})["\']?'), r'\1=[REDACTED]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]{16,}'), 'Bearer [REDACTED]'),
    (re.compile(r'ghp_[A-Za-z0-9]{36}'), '[REDACTED_GH_TOKEN]'),
    (re.compile(r'sk-[A-Za-z0-9]{32,}'), '[REDACTED_API_KEY]'),
]


def _mask_secrets(text: str) -> str:
    """Replace known secret patterns with redacted placeholders."""
    if not isinstance(text, str):
        return text
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _mask_dict(obj):
    """Recursively mask secrets in a dict/list/str structure."""
    if isinstance(obj, str):
        return _mask_secrets(obj)
    if isinstance(obj, dict):
        return {k: _mask_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mask_dict(item) for item in obj]
    return obj


class AuditLogger:
    """Logs all operations to structured audit files"""

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            log_dir = os.path.expanduser("~/.zenus/logs")

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # Restrict log directory to owner only
        self.log_dir.chmod(0o700)

        # Current session log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.log_dir / f"session_{timestamp}.jsonl"

    def log_intent(self, user_input: str, intent: IntentIR, mode: str = "execution"):
        """Log intent translation (secrets in args are redacted)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "intent",
            "mode": mode,
            "user_input": _mask_secrets(user_input),
            "goal": intent.goal,
            "requires_confirmation": intent.requires_confirmation,
            "steps": [
                {
                    "tool": step.tool,
                    "action": step.action,
                    "args": _mask_dict(step.args),
                    "risk": step.risk
                }
                for step in intent.steps
            ]
        }
        self._write(entry)

    def log_execution_start(self, intent: IntentIR):
        """Log execution start"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "execution_start",
            "goal": intent.goal
        }
        self._write(entry)

    def log_step_result(self, tool: str, action: str, result: str, success: bool):
        """Log individual step result (secrets in result output are redacted)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "step_result",
            "tool": tool,
            "action": action,
            "result": _mask_secrets(result),
            "success": success
        }
        self._write(entry)

    def log_execution_end(self, success: bool, message: Optional[str] = None):
        """Log execution completion"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "execution_end",
            "success": success,
            "message": message
        }
        self._write(entry)

    def log_error(self, error: str, context: Optional[dict] = None):
        """Log error"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "error",
            "error": error,
            "context": context or {}
        }
        self._write(entry)
    
    def log_info(self, event_type: str, data: Optional[dict] = None):
        """Log informational event"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "info",
            "event": event_type,
            "data": data or {}
        }
        self._write(entry)

    def _write(self, entry: dict):
        """Write entry to log file with owner-only permissions."""
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(self.session_file, flags, mode=0o600)
        try:
            with os.fdopen(fd, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            # fd is closed by fdopen on success; on failure close manually
            try:
                os.close(fd)
            except OSError:
                pass
            raise


# Global logger instance
_logger: Optional[AuditLogger] = None


def get_logger() -> AuditLogger:
    """Get or create global logger"""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger
