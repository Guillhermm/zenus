"""
Tests for the debug flags module (zenus_core.debug).

Covers:
- Default state: all flags off
- Master ZENUS_DEBUG env var enables all subsystems
- Per-subsystem env vars work independently
- Legacy ZENUS_SEARCH_DEBUG maps to search flag
- config.yaml debug section is respected
- Legacy search.debug config key maps to search flag
- reset_debug_flags() invalidates the cache
- DebugConfig in ZenusConfig schema validates correctly
"""

import os
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_flags(**env_overrides):
    """Import and load debug flags with a clean cache and given env vars."""
    import zenus_core.debug as dbg

    dbg.reset_debug_flags()
    with patch.dict(os.environ, env_overrides, clear=False):
        # Also ensure any previously set debug env vars are removed
        flags = dbg._load_flags()
    dbg.reset_debug_flags()
    return flags


def _flags_with_env(**env):
    """Return DebugFlags loaded with only the supplied env vars set (others cleared)."""
    import zenus_core.debug as dbg

    dbg.reset_debug_flags()
    # Build env with all ZENUS_DEBUG* vars removed, then add supplied ones
    clean_env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("ZENUS_DEBUG") and k != "ZENUS_SEARCH_DEBUG"
    }
    clean_env.update(env)

    with patch.dict(os.environ, clean_env, clear=True):
        with patch("zenus_core.debug._load_flags", wraps=dbg._load_flags):
            # Bypass get_config so we only test env-var behaviour
            with patch("zenus_core.config.loader.get_config", side_effect=Exception("no config")):
                flags = dbg._load_flags()

    dbg.reset_debug_flags()
    return flags


# ---------------------------------------------------------------------------
# Default state
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_all_flags_off_by_default(self):
        flags = _flags_with_env()
        assert flags.enabled is False
        assert flags.orchestrator is False
        assert flags.brain is False
        assert flags.execution is False
        assert flags.voice is False
        assert flags.search is False


# ---------------------------------------------------------------------------
# Master ZENUS_DEBUG
# ---------------------------------------------------------------------------

class TestMasterSwitch:
    def test_zenus_debug_enables_all(self):
        flags = _flags_with_env(ZENUS_DEBUG="1")
        assert flags.enabled is True
        assert flags.orchestrator is True
        assert flags.brain is True
        assert flags.execution is True
        assert flags.voice is True
        assert flags.search is True

    def test_zenus_debug_empty_string_is_false(self):
        flags = _flags_with_env(ZENUS_DEBUG="")
        assert flags.enabled is False
        assert flags.orchestrator is False


# ---------------------------------------------------------------------------
# Per-subsystem env vars
# ---------------------------------------------------------------------------

class TestSubsystemEnvVars:
    @pytest.mark.parametrize("env_var,attr", [
        ("ZENUS_DEBUG_ORCHESTRATOR", "orchestrator"),
        ("ZENUS_DEBUG_BRAIN", "brain"),
        ("ZENUS_DEBUG_EXECUTION", "execution"),
        ("ZENUS_DEBUG_VOICE", "voice"),
        ("ZENUS_DEBUG_SEARCH", "search"),
    ])
    def test_specific_var_enables_only_that_subsystem(self, env_var, attr):
        flags = _flags_with_env(**{env_var: "1"})
        assert getattr(flags, attr) is True, f"{attr} should be True when {env_var}=1"
        # All other subsystems stay off (enabled stays False since master is off)
        for other in ("orchestrator", "brain", "execution", "voice", "search"):
            if other != attr:
                assert getattr(flags, other) is False, (
                    f"{other} should be False when only {env_var} is set"
                )


# ---------------------------------------------------------------------------
# Legacy ZENUS_SEARCH_DEBUG
# ---------------------------------------------------------------------------

class TestLegacySearchDebug:
    def test_zenus_search_debug_maps_to_search_flag(self):
        flags = _flags_with_env(ZENUS_SEARCH_DEBUG="1")
        assert flags.search is True

    def test_zenus_search_debug_does_not_enable_other_flags(self):
        flags = _flags_with_env(ZENUS_SEARCH_DEBUG="1")
        assert flags.orchestrator is False
        assert flags.brain is False
        assert flags.execution is False
        assert flags.voice is False


# ---------------------------------------------------------------------------
# Config-based flags
# ---------------------------------------------------------------------------

class TestConfigFlags:
    def _make_cfg(self, **debug_kwargs):
        from zenus_core.config.schema import DebugConfig, ZenusConfig
        cfg = ZenusConfig()
        for k, v in debug_kwargs.items():
            setattr(cfg.debug, k, v)
        return cfg

    def _load_with_cfg(self, cfg):
        import zenus_core.debug as dbg
        dbg.reset_debug_flags()
        clean_env = {
            k: v for k, v in os.environ.items()
            if not k.startswith("ZENUS_DEBUG") and k != "ZENUS_SEARCH_DEBUG"
        }
        with patch.dict(os.environ, clean_env, clear=True):
            with patch("zenus_core.config.loader.get_config", return_value=cfg):
                flags = dbg._load_flags()
        dbg.reset_debug_flags()
        return flags

    def test_debug_enabled_true_enables_all(self):
        cfg = self._make_cfg(enabled=True)
        flags = self._load_with_cfg(cfg)
        assert flags.enabled is True
        assert flags.orchestrator is True
        assert flags.brain is True
        assert flags.execution is True
        assert flags.voice is True
        assert flags.search is True

    def test_debug_orchestrator_only(self):
        cfg = self._make_cfg(orchestrator=True)
        flags = self._load_with_cfg(cfg)
        assert flags.orchestrator is True
        assert flags.brain is False
        assert flags.execution is False

    def test_debug_search_only(self):
        cfg = self._make_cfg(search=True)
        flags = self._load_with_cfg(cfg)
        assert flags.search is True
        assert flags.orchestrator is False

    def test_legacy_search_debug_in_search_config(self):
        """search.debug: true in SearchConfig should still enable the search flag."""
        from zenus_core.config.schema import ZenusConfig
        cfg = ZenusConfig()
        cfg.search.debug = True

        import zenus_core.debug as dbg
        dbg.reset_debug_flags()
        clean_env = {
            k: v for k, v in os.environ.items()
            if not k.startswith("ZENUS_DEBUG") and k != "ZENUS_SEARCH_DEBUG"
        }
        with patch.dict(os.environ, clean_env, clear=True):
            with patch("zenus_core.config.loader.get_config", return_value=cfg):
                flags = dbg._load_flags()
        dbg.reset_debug_flags()

        assert flags.search is True
        assert flags.orchestrator is False


# ---------------------------------------------------------------------------
# Cache / reset
# ---------------------------------------------------------------------------

class TestCacheReset:
    def test_get_debug_flags_caches_result(self):
        import zenus_core.debug as dbg
        dbg.reset_debug_flags()
        with patch("zenus_core.config.loader.get_config", side_effect=Exception("no config")):
            f1 = dbg.get_debug_flags()
            f2 = dbg.get_debug_flags()
        assert f1 is f2  # same object — cached

    def test_reset_clears_cache(self):
        import zenus_core.debug as dbg
        dbg.reset_debug_flags()
        with patch("zenus_core.config.loader.get_config", side_effect=Exception("no config")):
            f1 = dbg.get_debug_flags()
        dbg.reset_debug_flags()
        with patch("zenus_core.config.loader.get_config", side_effect=Exception("no config")):
            f2 = dbg.get_debug_flags()
        # Both are new objects (different instances after reset)
        assert f1 is not f2


# ---------------------------------------------------------------------------
# Schema — DebugConfig in ZenusConfig
# ---------------------------------------------------------------------------

class TestDebugConfigSchema:
    def test_default_debug_config(self):
        from zenus_core.config.schema import ZenusConfig
        cfg = ZenusConfig()
        assert cfg.debug.enabled is False
        assert cfg.debug.orchestrator is False
        assert cfg.debug.brain is False
        assert cfg.debug.execution is False
        assert cfg.debug.voice is False
        assert cfg.debug.search is False

    def test_debug_config_parses_from_dict(self):
        from zenus_core.config.schema import ZenusConfig
        cfg = ZenusConfig(debug={"enabled": True, "orchestrator": True})
        assert cfg.debug.enabled is True
        assert cfg.debug.orchestrator is True
        assert cfg.debug.brain is False  # not set, still default
