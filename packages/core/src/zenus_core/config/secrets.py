"""
Secrets Management

Secure handling of API keys and sensitive data.
Priority order:
  1. HashiCorp Vault  (if VAULT_ADDR + VAULT_TOKEN are set)
  2. .env file / environment variables

Vault support is fully optional: if the `hvac` package is not installed, or if
the required environment variables are absent, Zenus silently falls back to the
env/dotenv path.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SECRET_KEYS: List[str] = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_API_BASE_URL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_API_BASE_URL",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "DATABASE_URL",
    "REDIS_URL",
    "ZENUS_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
]

_PROVIDER_KEY_MAP: Dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


# ---------------------------------------------------------------------------
# VaultClient — thin wrapper so hvac is truly optional
# ---------------------------------------------------------------------------

class VaultClient:
    """
    Thin wrapper around hvac (HashiCorp Vault).

    Connection is lazy — the first call to ``get`` establishes the
    client.  Subsequent calls reuse the session.

    Environment variables consumed:
        VAULT_ADDR   — e.g. http://127.0.0.1:8200
        VAULT_TOKEN  — Vault token
        VAULT_PATH   — KV v2 mount path for Zenus secrets
                       (default: "secret/data/zenus")
        VAULT_NAMESPACE — Enterprise namespace (optional)
    """

    def __init__(self) -> None:
        self._client = None
        self._available: Optional[bool] = None
        self.addr = os.getenv("VAULT_ADDR", "")
        self.token = os.getenv("VAULT_TOKEN", "")
        self.path = os.getenv("VAULT_PATH", "secret/data/zenus")
        self.namespace = os.getenv("VAULT_NAMESPACE")

    def is_configured(self) -> bool:
        """Return True when the minimum env vars are present."""
        return bool(self.addr and self.token)

    def _connect(self) -> bool:
        """Attempt to initialise the hvac client.  Returns True on success."""
        if self._available is not None:
            return self._available

        if not self.is_configured():
            self._available = False
            return False

        try:
            import hvac  # type: ignore

            kwargs: Dict = {"url": self.addr, "token": self.token}
            if self.namespace:
                kwargs["namespace"] = self.namespace

            client = hvac.Client(**kwargs)
            if not client.is_authenticated():
                logger.warning("Vault: authentication failed — falling back to env secrets")
                self._available = False
                return False

            self._client = client
            self._available = True
            logger.info("Vault: connected to %s", self.addr)
            return True

        except ImportError:
            logger.debug("hvac not installed — Vault integration disabled")
            self._available = False
            return False
        except Exception as exc:
            logger.warning("Vault: connection error (%s) — falling back to env secrets", exc)
            self._available = False
            return False

    def get_all(self) -> Dict[str, str]:
        """
        Return all key/value pairs from the configured Vault path.

        Returns an empty dict if Vault is unavailable or the path does
        not exist.
        """
        if not self._connect():
            return {}

        try:
            # KV v2 — data lives under data.data
            response = self._client.secrets.kv.v2.read_secret_version(
                path=self.path.replace("secret/data/", "", 1),
                mount_point="secret",
            )
            raw = response.get("data", {}).get("data", {})
            return {k: str(v) for k, v in raw.items() if v is not None}
        except Exception as exc:
            logger.warning("Vault: could not read secrets from '%s': %s", self.path, exc)
            return {}

    def get(self, key: str) -> Optional[str]:
        """Return a single secret by key, or None."""
        return self.get_all().get(key)


# ---------------------------------------------------------------------------
# SecretsManager
# ---------------------------------------------------------------------------

class SecretsManager:
    """
    Manage secrets securely.

    Features:
    - Load from .env files + environment variables
    - Optional HashiCorp Vault back-end (requires `hvac` + VAULT_ADDR/TOKEN)
    - Vault values take precedence over env vars
    - Never logs secret values
    - Validate required secrets
    """

    def __init__(
        self,
        env_file: Optional[Path] = None,
        vault: Optional[VaultClient] = None,
    ) -> None:
        self.env_file = env_file or self._find_env_file()
        self._vault = vault if vault is not None else VaultClient()
        self._secrets: Dict[str, str] = {}
        self._load_secrets()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Return a secret value, or *default* if not found."""
        return self._secrets.get(key, default)

    def get_llm_api_key(self, provider: str) -> Optional[str]:
        """Return the API key for an LLM provider."""
        key_name = _PROVIDER_KEY_MAP.get(provider.lower())
        if not key_name:
            return None
        return self.get(key_name)

    def has_secret(self, key: str) -> bool:
        """Return True if the secret is present."""
        return key in self._secrets

    def validate_required(self, *keys: str) -> bool:
        """
        Validate that all required secrets exist.

        Returns True if all present; logs missing keys and returns False
        otherwise.
        """
        missing = [k for k in keys if not self.has_secret(k)]
        if missing:
            logger.error("Missing required secrets: %s", ", ".join(missing))
            return False
        return True

    def list_available(self) -> List[str]:
        """Return the list of available secret *keys* (never values)."""
        return list(self._secrets.keys())

    def mask_secret(self, value: str) -> str:
        """Return a masked representation safe for logging."""
        if not value or len(value) < 8:
            return "***"
        return f"{value[:6]}***{value[-3:]}"

    def reload(self) -> None:
        """Re-read secrets from all sources."""
        self._secrets = {}
        self._load_secrets()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_env_file(self) -> Optional[Path]:
        search_paths = [
            Path.cwd() / ".env",
            Path.cwd() / ".env.local",
            Path.home() / ".zenus" / ".env",
        ]
        for path in search_paths:
            if path.exists():
                return path
        return None

    def _load_secrets(self) -> None:
        """Load secrets: env/dotenv first, Vault overrides on top."""
        # 1. dotenv + environment variables
        if self.env_file and self.env_file.exists():
            load_dotenv(self.env_file)

        for key in _SECRET_KEYS:
            value = os.getenv(key)
            if value:
                self._secrets[key] = value

        # 2. Vault (values take precedence over env)
        if self._vault.is_configured():
            vault_secrets = self._vault.get_all()
            if vault_secrets:
                logger.info(
                    "Vault: loaded %d secret(s) from %s",
                    len(vault_secrets),
                    self._vault.path,
                )
            self._secrets.update(vault_secrets)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_secrets_manager: Optional[SecretsManager] = None


def get_secrets(reload: bool = False) -> SecretsManager:
    """
    Return the global SecretsManager instance.

    Args:
        reload: Force re-initialisation (re-reads .env and Vault).
    """
    global _secrets_manager

    if _secrets_manager is None or reload:
        _secrets_manager = SecretsManager()

    return _secrets_manager
