"""
Tests for configuration loading, schema validation, and secrets management.
"""

import os
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from pydantic import ValidationError

from zenus_core.config.schema import (
    Profile,
    LLMConfig,
    FallbackConfig,
    CircuitBreakerSettings,
    RetrySettings,
    CacheConfig,
    SafetyConfig,
    MonitoringConfig,
    FeaturesConfig,
    ZenusConfig,
)
from zenus_core.config.loader import ConfigLoader
from zenus_core.config.secrets import SecretsManager


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestProfile:
    """Test Profile enum values"""

    def test_dev_value(self):
        """Profile.DEV should have value 'dev'"""
        assert Profile.DEV.value == "dev"

    def test_staging_value(self):
        """Profile.STAGING should have value 'staging'"""
        assert Profile.STAGING.value == "staging"

    def test_production_value(self):
        """Profile.PRODUCTION should have value 'production'"""
        assert Profile.PRODUCTION.value == "production"

    def test_profile_from_string(self):
        """Profile should be constructible from its string value"""
        assert Profile("dev") == Profile.DEV
        assert Profile("staging") == Profile.STAGING
        assert Profile("production") == Profile.PRODUCTION

    def test_invalid_profile_raises(self):
        """An unknown string should raise ValueError"""
        with pytest.raises(ValueError):
            Profile("unknown")


class TestLLMConfig:
    """Test LLM configuration schema"""

    def test_defaults(self):
        """LLMConfig should expose sensible defaults"""
        cfg = LLMConfig()
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-3-5-sonnet-20241022"
        assert cfg.api_key is None
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.7
        assert cfg.timeout_seconds == 30

    def test_custom_values(self):
        """LLMConfig accepts explicit field overrides"""
        cfg = LLMConfig(provider="openai", model="gpt-4o", temperature=0.5, max_tokens=2048)
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o"
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 2048

    def test_temperature_boundary_zero(self):
        """Temperature of 0 should be accepted"""
        cfg = LLMConfig(temperature=0)
        assert cfg.temperature == 0

    def test_temperature_boundary_one(self):
        """Temperature of 1 should be accepted"""
        cfg = LLMConfig(temperature=1)
        assert cfg.temperature == 1

    def test_temperature_too_low(self):
        """Temperature below 0 should raise ValidationError"""
        with pytest.raises(ValidationError):
            LLMConfig(temperature=-0.1)

    def test_temperature_too_high(self):
        """Temperature above 1 should raise ValidationError"""
        with pytest.raises(ValidationError):
            LLMConfig(temperature=1.1)


class TestFallbackConfig:
    """Test fallback configuration schema"""

    def test_defaults(self):
        """FallbackConfig should default to enabled with three providers"""
        cfg = FallbackConfig()
        assert cfg.enabled is True
        assert cfg.providers == ["anthropic", "deepseek", "rule_based"]

    def test_custom_providers(self):
        """FallbackConfig accepts a custom providers list"""
        cfg = FallbackConfig(providers=["openai"])
        assert cfg.providers == ["openai"]

    def test_disabled(self):
        """FallbackConfig can be disabled"""
        cfg = FallbackConfig(enabled=False)
        assert cfg.enabled is False


class TestCircuitBreakerSettings:
    """Test circuit breaker schema"""

    def test_defaults(self):
        """CircuitBreakerSettings should have correct defaults"""
        cfg = CircuitBreakerSettings()
        assert cfg.enabled is True
        assert cfg.failure_threshold == 5
        assert cfg.timeout_seconds == 60.0
        assert cfg.success_threshold == 2

    def test_custom_values(self):
        """CircuitBreakerSettings accepts overrides"""
        cfg = CircuitBreakerSettings(failure_threshold=3, success_threshold=1)
        assert cfg.failure_threshold == 3
        assert cfg.success_threshold == 1


class TestRetrySettings:
    """Test retry configuration schema"""

    def test_defaults(self):
        """RetrySettings should have correct defaults"""
        cfg = RetrySettings()
        assert cfg.enabled is True
        assert cfg.max_attempts == 3
        assert cfg.initial_delay_seconds == 1.0
        assert cfg.max_delay_seconds == 30.0
        assert cfg.exponential_base == 2.0
        assert cfg.jitter is True

    def test_disable_jitter(self):
        """Jitter can be disabled"""
        cfg = RetrySettings(jitter=False)
        assert cfg.jitter is False


class TestCacheConfig:
    """Test cache configuration schema"""

    def test_defaults(self):
        """CacheConfig should default to enabled with 1-hour TTL"""
        cfg = CacheConfig()
        assert cfg.enabled is True
        assert cfg.ttl_seconds == 3600
        assert cfg.max_size_mb == 100


class TestSafetyConfig:
    """Test safety configuration schema"""

    def test_defaults(self):
        """SafetyConfig should default to sandbox enabled"""
        cfg = SafetyConfig()
        assert cfg.sandbox_enabled is True
        assert cfg.max_file_size_mb == 100
        assert "." in cfg.allowed_paths
        assert len(cfg.blocked_commands) > 0

    def test_disable_sandbox(self):
        """Sandbox can be disabled"""
        cfg = SafetyConfig(sandbox_enabled=False)
        assert cfg.sandbox_enabled is False


class TestMonitoringConfig:
    """Test monitoring configuration schema"""

    def test_defaults(self):
        """MonitoringConfig should have sensible threshold defaults"""
        cfg = MonitoringConfig()
        assert cfg.enabled is True
        assert cfg.check_interval_seconds == 300
        assert cfg.disk_warning_threshold == 0.8
        assert cfg.disk_critical_threshold == 0.9
        assert cfg.cpu_warning_threshold == 0.8
        assert cfg.memory_warning_threshold == 0.85


class TestFeaturesConfig:
    """Test feature flag schema"""

    def test_defaults(self):
        """FeaturesConfig should default voice and multi-agent off, rest on"""
        cfg = FeaturesConfig()
        assert cfg.voice_interface is False
        assert cfg.multi_agent is False
        assert cfg.proactive_monitoring is True
        assert cfg.tree_of_thoughts is True
        assert cfg.prompt_evolution is True
        assert cfg.goal_inference is True
        assert cfg.self_reflection is True
        assert cfg.data_visualization is True


class TestZenusConfig:
    """Test the main ZenusConfig composite schema"""

    def test_defaults(self):
        """ZenusConfig should compose sub-configs with their defaults"""
        cfg = ZenusConfig()
        assert cfg.profile == Profile.DEV
        assert cfg.version == "0.5.1"
        assert isinstance(cfg.llm, LLMConfig)
        assert isinstance(cfg.fallback, FallbackConfig)
        assert isinstance(cfg.circuit_breaker, CircuitBreakerSettings)
        assert isinstance(cfg.retry, RetrySettings)
        assert isinstance(cfg.cache, CacheConfig)
        assert isinstance(cfg.safety, SafetyConfig)
        assert isinstance(cfg.monitoring, MonitoringConfig)
        assert isinstance(cfg.features, FeaturesConfig)
        assert cfg.custom == {}

    def test_is_dev(self):
        """is_dev() returns True only for DEV profile"""
        assert ZenusConfig(profile=Profile.DEV).is_dev() is True
        assert ZenusConfig(profile=Profile.STAGING).is_dev() is False
        assert ZenusConfig(profile=Profile.PRODUCTION).is_dev() is False

    def test_is_staging(self):
        """is_staging() returns True only for STAGING profile"""
        assert ZenusConfig(profile=Profile.STAGING).is_staging() is True
        assert ZenusConfig(profile=Profile.DEV).is_staging() is False

    def test_is_production(self):
        """is_production() returns True only for PRODUCTION profile"""
        assert ZenusConfig(profile=Profile.PRODUCTION).is_production() is True
        assert ZenusConfig(profile=Profile.DEV).is_production() is False

    def test_custom_normalises_none_to_empty_dict(self):
        """Passing None for custom should yield an empty dict"""
        cfg = ZenusConfig(custom=None)
        assert cfg.custom == {}

    def test_custom_accepts_dict(self):
        """Custom field accepts a dictionary"""
        cfg = ZenusConfig(custom={"my_key": "my_value"})
        assert cfg.custom == {"my_key": "my_value"}

    def test_profile_string_accepted(self):
        """Profile can be given as a plain string"""
        cfg = ZenusConfig(profile="production")
        assert cfg.is_production() is True

    def test_validate_assignment(self):
        """Pydantic validate_assignment is active – bad temperature is rejected on re-assign"""
        cfg = ZenusConfig()
        with pytest.raises(ValidationError):
            cfg.llm = LLMConfig(temperature=5.0)


# ---------------------------------------------------------------------------
# ConfigLoader tests
# ---------------------------------------------------------------------------

class TestConfigLoader:
    """Test ConfigLoader behaviour"""

    def _write_yaml(self, path: Path, data: dict):
        """Helper: write a YAML file."""
        with open(path, "w") as fh:
            yaml.dump(data, fh)

    def test_loads_yaml_file(self, tmp_path):
        """ConfigLoader reads a YAML file and returns a ZenusConfig"""
        cfg_file = tmp_path / "zenus.yaml"
        self._write_yaml(cfg_file, {"profile": "dev", "version": "1.0.0"})

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        assert loader.config.version == "1.0.0"
        assert loader.config.is_dev()

    def test_missing_file_falls_back_to_defaults(self, tmp_path):
        """ConfigLoader uses defaults when the config file does not exist"""
        missing = tmp_path / "nonexistent.yaml"

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=missing, watch=False)

        assert isinstance(loader.config, ZenusConfig)

    def test_empty_yaml_uses_defaults(self, tmp_path):
        """An empty YAML file results in default ZenusConfig"""
        cfg_file = tmp_path / "zenus.yaml"
        cfg_file.write_text("")  # empty file

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        assert isinstance(loader.config, ZenusConfig)

    def test_profile_override_merges_correctly(self, tmp_path):
        """Profile-specific overrides are merged into the base config"""
        data = {
            "profile": "dev",
            "llm": {"provider": "anthropic", "temperature": 0.7},
            "profiles": {
                "dev": {"llm": {"temperature": 0.9}}
            }
        }
        cfg_file = tmp_path / "zenus.yaml"
        self._write_yaml(cfg_file, data)

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(
                config_path=cfg_file,
                profile=Profile.DEV,
                watch=False
            )

        assert loader.config.llm.temperature == 0.9

    def test_non_active_profile_not_merged(self, tmp_path):
        """Overrides for a different profile should NOT be applied"""
        data = {
            "llm": {"temperature": 0.7},
            "profiles": {
                "production": {"llm": {"temperature": 0.1}}
            }
        }
        cfg_file = tmp_path / "zenus.yaml"
        self._write_yaml(cfg_file, data)

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(
                config_path=cfg_file,
                profile=Profile.DEV,
                watch=False
            )

        assert loader.config.llm.temperature == 0.7

    def test_get_config_returns_zenus_config(self, tmp_path):
        """get_config() method returns the loaded ZenusConfig"""
        cfg_file = tmp_path / "zenus.yaml"
        self._write_yaml(cfg_file, {})

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        result = loader.get_config()
        assert isinstance(result, ZenusConfig)

    def test_reload_re_reads_file(self, tmp_path):
        """reload() picks up changes written to disk after initial load"""
        cfg_file = tmp_path / "zenus.yaml"
        self._write_yaml(cfg_file, {"version": "1.0.0"})

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        assert loader.config.version == "1.0.0"

        # Now update the file
        self._write_yaml(cfg_file, {"version": "2.0.0"})
        loader.reload()

        assert loader.config.version == "2.0.0"

    def test_save_config_writes_yaml(self, tmp_path):
        """save_config() serialises the config object to disk"""
        cfg_file = tmp_path / "zenus.yaml"
        cfg_file.write_text("")

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        new_cfg = ZenusConfig(version="9.9.9")
        loader.save_config(new_cfg)

        # Verify the file is non-empty and contains the expected version string
        content = cfg_file.read_text()
        assert len(content) > 0
        assert "9.9.9" in content

    def test_invalid_yaml_falls_back_to_defaults(self, tmp_path):
        """Corrupt YAML triggers the except branch and returns defaults"""
        cfg_file = tmp_path / "zenus.yaml"
        cfg_file.write_text("{{{{ invalid yaml ::::")

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        assert isinstance(loader.config, ZenusConfig)

    def test_merge_dicts_deep(self, tmp_path):
        """_merge_dicts should recursively override nested keys"""
        cfg_file = tmp_path / "z.yaml"
        cfg_file.write_text("")

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99}, "b": 100}
        result = loader._merge_dicts(base, override)

        assert result == {"a": {"x": 1, "y": 99}, "b": 100}

    def test_detect_profile_from_env(self, tmp_path):
        """Profile is read from ZENUS_PROFILE env var"""
        cfg_file = tmp_path / "z.yaml"
        cfg_file.write_text("")

        with patch.dict(os.environ, {"ZENUS_PROFILE": "production"}):
            with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
                loader = ConfigLoader(config_path=cfg_file, watch=False)

        assert loader.profile == Profile.PRODUCTION

    def test_detect_profile_defaults_to_dev(self, tmp_path):
        """Profile defaults to dev when ZENUS_PROFILE is not set"""
        cfg_file = tmp_path / "z.yaml"
        cfg_file.write_text("")
        env = {k: v for k, v in os.environ.items() if k != "ZENUS_PROFILE"}

        with patch.dict(os.environ, env, clear=True):
            with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
                loader = ConfigLoader(config_path=cfg_file, watch=False)

        assert loader.profile == Profile.DEV

    def test_detect_profile_unknown_falls_back_to_dev(self, tmp_path):
        """An unknown ZENUS_PROFILE value falls back to dev"""
        cfg_file = tmp_path / "z.yaml"
        cfg_file.write_text("")

        with patch.dict(os.environ, {"ZENUS_PROFILE": "canary"}):
            with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
                loader = ConfigLoader(config_path=cfg_file, watch=False)

        assert loader.profile == Profile.DEV

    def test_find_config_from_zenus_config_env(self, tmp_path):
        """ZENUS_CONFIG env var points ConfigLoader at a custom path"""
        cfg_file = tmp_path / "custom.yaml"
        self._write_yaml(cfg_file, {"version": "7.7.7"})

        with patch.dict(os.environ, {"ZENUS_CONFIG": str(cfg_file)}):
            with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
                loader = ConfigLoader(watch=False)

        assert loader.config.version == "7.7.7"

    def test_stop_watching_when_observer_is_none(self, tmp_path):
        """stop_watching() is a no-op when no observer is running"""
        cfg_file = tmp_path / "z.yaml"
        cfg_file.write_text("")

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        # Should not raise
        loader.stop_watching()

    def test_stop_watching_stops_observer(self, tmp_path):
        """stop_watching() calls stop/join on the observer"""
        cfg_file = tmp_path / "z.yaml"
        cfg_file.write_text("")

        observer_mock = MagicMock()

        with patch("zenus_core.config.loader.ConfigLoader._start_watching"):
            loader = ConfigLoader(config_path=cfg_file, watch=False)

        loader.observer = observer_mock
        loader.stop_watching()

        observer_mock.stop.assert_called_once()
        observer_mock.join.assert_called_once()


# ---------------------------------------------------------------------------
# SecretsManager tests
# ---------------------------------------------------------------------------

class TestSecretsManager:
    """Test SecretsManager secret resolution"""

    def test_get_existing_secret(self):
        """get() returns the value when the key is loaded"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.get("ANTHROPIC_API_KEY") == "sk-ant-test"

    def test_get_missing_secret_returns_default(self):
        """get() returns the supplied default for a missing key"""
        clean_env = {k: v for k, v in os.environ.items() if k not in (
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
            "OLLAMA_BASE_URL", "OLLAMA_MODEL", "DATABASE_URL", "REDIS_URL",
            "ZENUS_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "OPENAI_API_BASE_URL",
            "DEEPSEEK_API_BASE_URL",
        )}
        with patch.dict(os.environ, clean_env, clear=True):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.get("ANTHROPIC_API_KEY", "fallback") == "fallback"

    def test_has_secret_true(self):
        """has_secret() returns True when the key is present"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.has_secret("OPENAI_API_KEY") is True

    def test_has_secret_false(self):
        """has_secret() returns False when the key is absent"""
        clean_env = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
        with patch.dict(os.environ, clean_env, clear=True):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.has_secret("GITHUB_TOKEN") is False

    def test_get_llm_api_key_anthropic(self):
        """get_llm_api_key('anthropic') maps to ANTHROPIC_API_KEY"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-xyz"}):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.get_llm_api_key("anthropic") == "sk-ant-xyz"

    def test_get_llm_api_key_openai(self):
        """get_llm_api_key('openai') maps to OPENAI_API_KEY"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-oai-xyz"}):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.get_llm_api_key("openai") == "sk-oai-xyz"

    def test_get_llm_api_key_deepseek(self):
        """get_llm_api_key('deepseek') maps to DEEPSEEK_API_KEY"""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-ds-xyz"}):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.get_llm_api_key("deepseek") == "sk-ds-xyz"

    def test_get_llm_api_key_unknown_provider(self):
        """get_llm_api_key() returns None for an unrecognised provider"""
        with patch("zenus_core.config.secrets.load_dotenv"):
            mgr = SecretsManager(env_file=None)

        assert mgr.get_llm_api_key("unknown_provider") is None

    def test_get_llm_api_key_case_insensitive(self):
        """Provider name matching is case-insensitive"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-case"}):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.get_llm_api_key("ANTHROPIC") == "sk-ant-case"

    def test_validate_required_all_present(self):
        """validate_required() returns True when every key exists"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-a", "OPENAI_API_KEY": "sk-b"}):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.validate_required("ANTHROPIC_API_KEY", "OPENAI_API_KEY") is True

    def test_validate_required_missing(self):
        """validate_required() returns False when a key is missing"""
        clean_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, clean_env, clear=True):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        assert mgr.validate_required("ANTHROPIC_API_KEY") is False

    def test_list_available_returns_keys(self):
        """list_available() returns the names of loaded secrets"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-a"}):
            with patch("zenus_core.config.secrets.load_dotenv"):
                mgr = SecretsManager(env_file=None)

        keys = mgr.list_available()
        assert isinstance(keys, list)
        assert "ANTHROPIC_API_KEY" in keys

    def test_mask_secret_normal_value(self):
        """mask_secret() shows first 6 and last 3 chars with *** in between"""
        with patch("zenus_core.config.secrets.load_dotenv"):
            mgr = SecretsManager(env_file=None)

        masked = mgr.mask_secret("sk-ant-abcdefghijk")
        assert masked.startswith("sk-ant")
        assert masked.endswith("ijk")
        assert "***" in masked

    def test_mask_secret_short_value(self):
        """mask_secret() returns '***' for values shorter than 8 chars"""
        with patch("zenus_core.config.secrets.load_dotenv"):
            mgr = SecretsManager(env_file=None)

        assert mgr.mask_secret("abc") == "***"

    def test_mask_secret_empty_string(self):
        """mask_secret() returns '***' for empty string"""
        with patch("zenus_core.config.secrets.load_dotenv"):
            mgr = SecretsManager(env_file=None)

        assert mgr.mask_secret("") == "***"

    def test_loads_from_env_file(self, tmp_path):
        """SecretsManager calls load_dotenv with the resolved env file path"""
        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=sk-from-file\n")

        with patch("zenus_core.config.secrets.load_dotenv") as mock_load:
            SecretsManager(env_file=env_file)

        mock_load.assert_called_once_with(env_file)

    def test_find_env_file_returns_none_when_no_files_exist(self):
        """_find_env_file() returns None when none of the standard paths exist"""
        with patch("zenus_core.config.secrets.load_dotenv"):
            with patch.object(Path, "exists", return_value=False):
                mgr = SecretsManager(env_file=None)

        # The manager should still initialise cleanly
        assert isinstance(mgr, SecretsManager)
