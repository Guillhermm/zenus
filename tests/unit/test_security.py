"""
Security regression tests — OWASP audit fixes (v1.1.0 / Phase 1.5.1).

Each test corresponds to a specific finding from the security audit so that
future regressions are caught immediately.
"""

import json
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# A09 — AuditLogger: secret masking & file permissions
# ---------------------------------------------------------------------------

class TestAuditLoggerSecretMasking:
    """Secrets must be redacted before any data reaches disk."""

    def setup_method(self):
        from zenus_core.audit.logger import AuditLogger
        self.tmp = tempfile.mkdtemp()
        self.logger = AuditLogger(log_dir=self.tmp)

    def _read_log(self):
        return self.logger.session_file.read_text()

    def test_api_key_in_user_input_is_redacted(self):
        intent = MagicMock()
        intent.goal = "test"
        intent.requires_confirmation = False
        intent.steps = []
        self.logger.log_intent("api_key=sk-abc123456789012345678901234567890", intent)
        assert "sk-abc" not in self._read_log()
        assert "REDACTED" in self._read_log()

    def test_bearer_token_in_step_args_is_redacted(self):
        step = MagicMock()
        step.tool = "NetworkOps"
        step.action = "curl"
        step.args = {"headers": {"Authorization": "Bearer ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"}}
        step.risk = 0
        intent = MagicMock()
        intent.goal = "fetch"
        intent.requires_confirmation = False
        intent.steps = [step]
        self.logger.log_intent("fetch data", intent)
        raw = self._read_log()
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789" not in raw
        assert "REDACTED" in raw

    def test_step_result_with_token_is_redacted(self):
        self.logger.log_step_result("NetworkOps", "curl", "token=sk-abc12345678901234567890", True)
        assert "sk-abc" not in self._read_log()

    def test_benign_content_is_not_altered(self):
        intent = MagicMock()
        intent.goal = "list files"
        intent.requires_confirmation = False
        step = MagicMock()
        step.tool = "FileOps"
        step.action = "scan"
        step.args = {"path": "~/Documents"}
        step.risk = 0
        intent.steps = [step]
        self.logger.log_intent("list files in Documents", intent)
        raw = self._read_log()
        assert "list files in Documents" in raw
        assert "~/Documents" in raw


class TestAuditLoggerFilePermissions:
    """Log files must be owner-only (0o600)."""

    def test_log_directory_is_owner_only(self):
        from zenus_core.audit.logger import AuditLogger
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)
            mode = stat.S_IMODE(os.stat(tmp).st_mode)
            assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_session_file_is_owner_only(self):
        from zenus_core.audit.logger import AuditLogger
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            logger = AuditLogger(log_dir=tmp)
            intent = MagicMock()
            intent.goal = "test"
            intent.requires_confirmation = False
            intent.steps = []
            logger.log_intent("hello", intent)
            mode = stat.S_IMODE(os.stat(logger.session_file).st_mode)
            assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


# ---------------------------------------------------------------------------
# A09 — IntentHistory: file permissions & secret masking
# ---------------------------------------------------------------------------

class TestIntentHistoryPermissions:
    def test_history_directory_is_owner_only(self):
        from zenus_core.memory.intent_history import IntentHistory
        with tempfile.TemporaryDirectory() as tmp:
            hist = IntentHistory(history_dir=tmp)
            mode = stat.S_IMODE(os.stat(tmp).st_mode)
            assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_history_file_is_owner_only(self):
        from zenus_core.memory.intent_history import IntentHistory
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            hist = IntentHistory(history_dir=tmp)
            intent = MagicMock()
            intent.goal = "test"
            intent.steps = []
            hist.record("hello", intent, [], success=True)
            mode = stat.S_IMODE(os.stat(hist.current_file).st_mode)
            assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_secrets_in_user_input_are_masked(self):
        from zenus_core.memory.intent_history import IntentHistory
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            hist = IntentHistory(history_dir=tmp)
            intent = MagicMock()
            intent.goal = "test"
            intent.steps = []
            hist.record("token=sk-abc12345678901234567890", intent, ["ok"], success=True)
            raw = hist.current_file.read_text()
            assert "sk-abc" not in raw
            assert "REDACTED" in raw


# ---------------------------------------------------------------------------
# A01 — FileOps: path resolution
# ---------------------------------------------------------------------------

class TestFileOpsPathResolution:
    """Path traversal sequences must be normalised before operations."""

    def test_resolve_helper_normalises_traversal(self):
        from zenus_core.tools.file_ops import _resolve
        result = _resolve("~/.")
        assert ".." not in result
        assert result == str(Path.home())

    def test_resolve_strips_dotdot_sequences(self):
        from zenus_core.tools.file_ops import _resolve
        # Create a real path so resolve() can follow it
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "sub")
            os.makedirs(sub)
            # Path with ../ traversal should resolve to tmp
            traversal = os.path.join(sub, "..", "sub")
            resolved = _resolve(traversal)
            assert ".." not in resolved
            # Use realpath for comparison — on macOS /var is a symlink to /private/var
            assert resolved == os.path.realpath(sub)


# ---------------------------------------------------------------------------
# A03 — NetworkOps: URL scheme validation
# ---------------------------------------------------------------------------

class TestNetworkOpsURLValidation:
    def _ops(self):
        from zenus_core.tools.network_ops import NetworkOps
        return NetworkOps()

    def test_http_url_is_accepted(self):
        ops = self._ops()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", returncode=0)
            result = ops.curl("http://example.com")
        assert "Error" not in result

    def test_https_url_is_accepted(self):
        ops = self._ops()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", returncode=0)
            result = ops.curl("https://example.com")
        assert "Error" not in result

    def test_file_scheme_is_rejected(self):
        ops = self._ops()
        result = ops.curl("file:///etc/passwd")
        assert "Error" in result
        assert "Unsupported URL scheme" in result

    def test_ftp_scheme_is_accepted(self):
        ops = self._ops()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", returncode=0)
            result = ops.curl("ftp://example.com/file.txt")
        assert "Unsupported URL scheme" not in result

    def test_wget_rejects_file_scheme(self):
        ops = self._ops()
        result = ops.wget("file:///etc/shadow")
        assert "Error" in result

    def test_wget_accepts_https(self):
        ops = self._ops()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            result = ops.wget("https://example.com/file.zip")
        assert "Error" not in result or "Unsupported" not in result


# ---------------------------------------------------------------------------
# A08 — SafetyPolicy: confirmation enforcement
# ---------------------------------------------------------------------------

class TestEnforceConfirmationPolicy:
    def _make_intent(self, risk: int, requires_confirmation: bool = False):
        from zenus_core.brain.llm.schemas import IntentIR, Step
        step = Step(tool="FileOps", action="move", args={}, risk=risk)
        return IntentIR(
            goal="test",
            requires_confirmation=requires_confirmation,
            steps=[step],
        )

    def test_risk_2_forces_confirmation(self):
        from zenus_core.safety.policy import enforce_confirmation_policy
        intent = self._make_intent(risk=2, requires_confirmation=False)
        result = enforce_confirmation_policy(intent)
        assert result.requires_confirmation is True

    def test_risk_3_forces_confirmation(self):
        from zenus_core.safety.policy import enforce_confirmation_policy
        intent = self._make_intent(risk=3, requires_confirmation=False)
        result = enforce_confirmation_policy(intent)
        assert result.requires_confirmation is True

    def test_risk_0_leaves_confirmation_unchanged(self):
        from zenus_core.safety.policy import enforce_confirmation_policy
        intent = self._make_intent(risk=0, requires_confirmation=False)
        result = enforce_confirmation_policy(intent)
        assert result.requires_confirmation is False

    def test_risk_1_leaves_confirmation_unchanged(self):
        from zenus_core.safety.policy import enforce_confirmation_policy
        intent = self._make_intent(risk=1, requires_confirmation=False)
        result = enforce_confirmation_policy(intent)
        assert result.requires_confirmation is False

    def test_already_true_stays_true(self):
        from zenus_core.safety.policy import enforce_confirmation_policy
        intent = self._make_intent(risk=0, requires_confirmation=True)
        result = enforce_confirmation_policy(intent)
        assert result.requires_confirmation is True

    def test_returns_new_object_when_changed(self):
        from zenus_core.safety.policy import enforce_confirmation_policy
        intent = self._make_intent(risk=2, requires_confirmation=False)
        result = enforce_confirmation_policy(intent)
        # Should return a new object (model_copy), not mutate in place
        assert result is not intent

    def test_returns_same_object_when_unchanged(self):
        from zenus_core.safety.policy import enforce_confirmation_policy
        intent = self._make_intent(risk=0, requires_confirmation=False)
        result = enforce_confirmation_policy(intent)
        assert result is intent


# ---------------------------------------------------------------------------
# A03 — Secret masking helpers
# ---------------------------------------------------------------------------

class TestSecretMaskingHelpers:
    def test_mask_api_key_pattern(self):
        from zenus_core.audit.logger import _mask_secrets
        text = "api_key=sk-abc1234567890123456789012345678"
        result = _mask_secrets(text)
        assert "sk-abc" not in result

    def test_mask_bearer_token(self):
        from zenus_core.audit.logger import _mask_secrets
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = _mask_secrets(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_mask_github_token(self):
        from zenus_core.audit.logger import _mask_secrets
        # Real GitHub PAT format: ghp_ followed by exactly 36 alphanumeric chars
        text = "token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
        result = _mask_secrets(text)
        assert "ghp_ABCDE" not in result

    def test_plain_text_unchanged(self):
        from zenus_core.audit.logger import _mask_secrets
        text = "list files in ~/Documents sorted by size"
        assert _mask_secrets(text) == text

    def test_mask_dict_recurses(self):
        from zenus_core.audit.logger import _mask_dict
        obj = {"cmd": "curl", "headers": {"Authorization": "Bearer sk-abc12345678901234"}}
        result = _mask_dict(obj)
        assert "sk-abc" not in str(result)
        assert result["cmd"] == "curl"

    def test_mask_dict_handles_list(self):
        from zenus_core.audit.logger import _mask_dict
        obj = ["api_key=sk-12345678901234567890", "safe text"]
        result = _mask_dict(obj)
        assert "sk-1234" not in result[0]
        assert result[1] == "safe text"
