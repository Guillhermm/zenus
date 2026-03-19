"""
Tests for VaultClient and the updated SecretsManager vault integration.

All tests run without a real Vault instance — we mock hvac or test the
fallback paths so the suite never requires external services.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from zenus_core.config.secrets import VaultClient, SecretsManager


# ---------------------------------------------------------------------------
# VaultClient — configuration detection
# ---------------------------------------------------------------------------

class TestVaultClientConfiguration:
    def test_not_configured_when_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        vc = VaultClient()
        assert not vc.is_configured()

    def test_not_configured_when_only_addr(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        vc = VaultClient()
        assert not vc.is_configured()

    def test_not_configured_when_only_token(self, monkeypatch):
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.setenv("VAULT_TOKEN", "s.abc123")
        vc = VaultClient()
        assert not vc.is_configured()

    def test_configured_when_both_present(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.abc123")
        vc = VaultClient()
        assert vc.is_configured()

    def test_custom_path_from_env(self, monkeypatch):
        monkeypatch.setenv("VAULT_PATH", "kv/data/myapp")
        vc = VaultClient()
        assert vc.path == "kv/data/myapp"

    def test_default_path(self, monkeypatch):
        monkeypatch.delenv("VAULT_PATH", raising=False)
        vc = VaultClient()
        assert vc.path == "secret/data/zenus"

    def test_namespace_from_env(self, monkeypatch):
        monkeypatch.setenv("VAULT_NAMESPACE", "my-org")
        vc = VaultClient()
        assert vc.namespace == "my-org"


# ---------------------------------------------------------------------------
# VaultClient — fallback when hvac missing or auth fails
# ---------------------------------------------------------------------------

class TestVaultClientFallback:
    def test_get_all_returns_empty_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        vc = VaultClient()
        assert vc.get_all() == {}

    def test_get_returns_none_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        vc = VaultClient()
        assert vc.get("ANTHROPIC_API_KEY") is None

    def test_get_all_returns_empty_when_hvac_missing(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.test")
        # Simulate hvac not installed
        with patch.dict(sys.modules, {"hvac": None}):
            vc = VaultClient()
            result = vc.get_all()
        assert result == {}

    def test_get_all_returns_empty_when_auth_fails(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
        monkeypatch.setenv("VAULT_TOKEN", "bad-token")

        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False
        mock_hvac.Client.return_value = mock_client

        with patch.dict(sys.modules, {"hvac": mock_hvac}):
            vc = VaultClient()
            result = vc.get_all()

        assert result == {}

    def test_get_all_returns_empty_on_connection_error(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.test")

        mock_hvac = MagicMock()
        mock_hvac.Client.side_effect = ConnectionRefusedError("refused")

        with patch.dict(sys.modules, {"hvac": mock_hvac}):
            vc = VaultClient()
            result = vc.get_all()

        assert result == {}

    def test_connect_is_cached_after_first_failure(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.test")

        mock_hvac = MagicMock()
        mock_hvac.Client.side_effect = ConnectionRefusedError("refused")

        with patch.dict(sys.modules, {"hvac": mock_hvac}):
            vc = VaultClient()
            vc.get_all()
            vc.get_all()  # second call must NOT re-attempt

        # Client() was called only once (cached failure)
        assert mock_hvac.Client.call_count == 1


# ---------------------------------------------------------------------------
# VaultClient — successful read
# ---------------------------------------------------------------------------

class TestVaultClientSuccessfulRead:
    def _make_vault_client(self, monkeypatch, secrets: dict) -> VaultClient:
        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.valid")

        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": secrets}
        }
        mock_hvac.Client.return_value = mock_client

        with patch.dict(sys.modules, {"hvac": mock_hvac}):
            vc = VaultClient()
            vc._connect()
            vc._client = mock_client
            vc._available = True

        return vc

    def test_get_all_returns_secrets(self, monkeypatch):
        vc = self._make_vault_client(monkeypatch, {"ANTHROPIC_API_KEY": "sk-ant-test"})
        result = vc.get_all()
        assert result.get("ANTHROPIC_API_KEY") == "sk-ant-test"

    def test_get_returns_specific_secret(self, monkeypatch):
        vc = self._make_vault_client(monkeypatch, {"DEEPSEEK_API_KEY": "ds-key-xyz"})
        assert vc.get("DEEPSEEK_API_KEY") == "ds-key-xyz"

    def test_get_returns_none_for_missing_key(self, monkeypatch):
        vc = self._make_vault_client(monkeypatch, {"ANTHROPIC_API_KEY": "sk"})
        assert vc.get("OPENAI_API_KEY") is None

    def test_get_all_returns_empty_on_read_error(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://127.0.0.1:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.valid")

        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.side_effect = Exception("read error")
        mock_hvac.Client.return_value = mock_client

        with patch.dict(sys.modules, {"hvac": mock_hvac}):
            vc = VaultClient()
            vc._client = mock_client
            vc._available = True
            result = vc.get_all()

        assert result == {}


# ---------------------------------------------------------------------------
# SecretsManager — vault integration
# ---------------------------------------------------------------------------

def _make_mock_vault(configured: bool = True, secrets: dict = None) -> MagicMock:
    """Helper: build a fully-specced VaultClient mock."""
    mock = MagicMock(spec=VaultClient)
    mock.is_configured.return_value = configured
    mock.get_all.return_value = secrets or {}
    mock.path = "secret/data/zenus"
    return mock


class TestSecretsManagerVaultIntegration:
    def test_vault_secrets_override_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

        mock_vault = _make_mock_vault(secrets={"ANTHROPIC_API_KEY": "vault-key"})

        mgr = SecretsManager(env_file=None, vault=mock_vault)
        assert mgr.get("ANTHROPIC_API_KEY") == "vault-key"

    def test_env_used_when_vault_not_configured(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "openai-env-key")
        mock_vault = _make_mock_vault(configured=False)
        mgr = SecretsManager(env_file=None, vault=mock_vault)
        assert mgr.get("OPENAI_API_KEY") == "openai-env-key"

    def test_vault_not_queried_when_not_configured(self, monkeypatch):
        mock_vault = _make_mock_vault(configured=False)
        SecretsManager(env_file=None, vault=mock_vault)
        mock_vault.get_all.assert_not_called()

    def test_missing_key_returns_none_with_vault(self, monkeypatch):
        mock_vault = _make_mock_vault(secrets={})
        mgr = SecretsManager(env_file=None, vault=mock_vault)
        assert mgr.get("NONEXISTENT_KEY") is None

    def test_env_file_loaded_alongside_vault(self, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("ZENUS_API_KEY=from-env-file\n")
        mock_vault = _make_mock_vault(secrets={"ANTHROPIC_API_KEY": "from-vault"})
        mgr = SecretsManager(env_file=env_file, vault=mock_vault)
        assert mgr.get("ANTHROPIC_API_KEY") == "from-vault"
        assert mgr.get("ZENUS_API_KEY") == "from-env-file"

    def test_reload_re_reads_vault(self, monkeypatch):
        mock_vault = _make_mock_vault()
        mock_vault.get_all.side_effect = [
            {"ANTHROPIC_API_KEY": "first"},
            {"ANTHROPIC_API_KEY": "second"},
        ]
        mgr = SecretsManager(env_file=None, vault=mock_vault)
        assert mgr.get("ANTHROPIC_API_KEY") == "first"
        mgr.reload()
        assert mgr.get("ANTHROPIC_API_KEY") == "second"

    def test_list_available_includes_vault_keys(self, monkeypatch):
        mock_vault = _make_mock_vault(secrets={"ANTHROPIC_API_KEY": "k1", "DEEPSEEK_API_KEY": "k2"})
        mgr = SecretsManager(env_file=None, vault=mock_vault)
        available = mgr.list_available()
        assert "ANTHROPIC_API_KEY" in available
        assert "DEEPSEEK_API_KEY" in available

    def test_get_llm_api_key_reads_from_vault(self, monkeypatch):
        mock_vault = _make_mock_vault(secrets={"ANTHROPIC_API_KEY": "sk-ant-vault"})
        mgr = SecretsManager(env_file=None, vault=mock_vault)
        assert mgr.get_llm_api_key("anthropic") == "sk-ant-vault"

    def test_validate_required_passes_when_vault_provides(self, monkeypatch):
        mock_vault = _make_mock_vault(secrets={"ANTHROPIC_API_KEY": "key"})
        mgr = SecretsManager(env_file=None, vault=mock_vault)
        assert mgr.validate_required("ANTHROPIC_API_KEY") is True

    def test_validate_required_fails_when_key_absent(self, monkeypatch):
        mock_vault = _make_mock_vault(configured=False)
        for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]:
            monkeypatch.delenv(k, raising=False)
        mgr = SecretsManager(env_file=None, vault=mock_vault)
        assert mgr.validate_required("NONEXISTENT_KEY_XYZ") is False
