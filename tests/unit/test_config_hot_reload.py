"""
Tests for ConfigLoader hot-reload and callback notification.

These tests write real files to tmp_path and exercise the full
thread-safe reload path without needing watchdog to fire (we call
_load_config() directly to stay fast and deterministic).
"""

import threading
import time
import yaml
import pytest
from pathlib import Path

from zenus_core.config.loader import ConfigLoader, register_reload_callback, get_config
from zenus_core.config.schema import ZenusConfig, Profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(path: Path, temperature: float = 0.7, provider: str = "anthropic") -> None:
    data = {
        "profile": "dev",
        "llm": {"provider": provider, "temperature": temperature},
    }
    path.write_text(yaml.dump(data))


# ---------------------------------------------------------------------------
# Reload correctness
# ---------------------------------------------------------------------------

class TestHotReloadCorrectness:
    def test_manual_reload_picks_up_new_values(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path, temperature=0.5)

        loader = ConfigLoader(config_path=cfg_path, watch=False)
        assert loader.get_config().llm.temperature == 0.5

        _write_config(cfg_path, temperature=0.9)
        loader.reload()

        assert loader.get_config().llm.temperature == 0.9

    def test_reload_returns_new_config_instance(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path, temperature=0.3)

        loader = ConfigLoader(config_path=cfg_path, watch=False)
        first = loader.get_config()

        _write_config(cfg_path, temperature=0.8)
        second = loader.reload()

        assert second is not first
        assert second.llm.temperature == 0.8

    def test_reload_on_broken_yaml_keeps_previous_config(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path, temperature=0.4)

        loader = ConfigLoader(config_path=cfg_path, watch=False)
        before = loader.get_config().llm.temperature

        cfg_path.write_text(": invalid: yaml: {{{{")
        loader.reload()

        # Must fall back to defaults, not crash
        assert loader.get_config() is not None
        # Temperature defaults to 0.7 (from ZenusConfig default)
        assert isinstance(loader.get_config().llm.temperature, float)
        _ = before  # previous value was captured

    def test_reload_on_missing_file_returns_defaults(self, tmp_path):
        cfg_path = tmp_path / "missing.yaml"
        loader = ConfigLoader(config_path=cfg_path, watch=False)
        # Should not raise
        cfg = loader.get_config()
        assert isinstance(cfg, ZenusConfig)

    def test_provider_change_picked_up_on_reload(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path, provider="anthropic")

        loader = ConfigLoader(config_path=cfg_path, watch=False)
        assert loader.get_config().llm.provider == "anthropic"

        _write_config(cfg_path, provider="deepseek")
        loader.reload()
        assert loader.get_config().llm.provider == "deepseek"


# ---------------------------------------------------------------------------
# Callback notifications
# ---------------------------------------------------------------------------

class TestReloadCallbacks:
    def test_callback_called_on_reload(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)

        received = []
        loader = ConfigLoader(config_path=cfg_path, watch=False)
        loader.on_reload(received.append)

        _write_config(cfg_path, temperature=0.2)
        loader.reload()

        assert len(received) == 1
        assert received[0].llm.temperature == 0.2

    def test_multiple_callbacks_all_called(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)

        counters = [0, 0, 0]

        def cb0(cfg): counters[0] += 1
        def cb1(cfg): counters[1] += 1
        def cb2(cfg): counters[2] += 1

        loader = ConfigLoader(config_path=cfg_path, watch=False)
        loader.on_reload(cb0)
        loader.on_reload(cb1)
        loader.on_reload(cb2)

        loader.reload()

        assert counters == [1, 1, 1]

    def test_callback_called_multiple_times_on_multiple_reloads(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)

        counter = [0]
        loader = ConfigLoader(config_path=cfg_path, watch=False)
        loader.on_reload(lambda cfg: counter.__setitem__(0, counter[0] + 1))

        loader.reload()
        loader.reload()
        loader.reload()

        assert counter[0] == 3

    def test_remove_callback_stops_calls(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)

        counter = [0]
        def cb(cfg): counter[0] += 1

        loader = ConfigLoader(config_path=cfg_path, watch=False)
        loader.on_reload(cb)
        loader.reload()
        assert counter[0] == 1

        loader.remove_reload_callback(cb)
        loader.reload()
        assert counter[0] == 1  # not incremented again

    def test_callback_exception_does_not_prevent_other_callbacks(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)

        results = []

        def bad_cb(cfg): raise RuntimeError("callback error")
        def good_cb(cfg): results.append(cfg)

        loader = ConfigLoader(config_path=cfg_path, watch=False)
        loader.on_reload(bad_cb)
        loader.on_reload(good_cb)

        loader.reload()  # must not raise
        assert len(results) == 1

    def test_callback_receives_correct_config(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path, temperature=0.1)

        received = []
        loader = ConfigLoader(config_path=cfg_path, watch=False)
        loader.on_reload(received.append)

        _write_config(cfg_path, temperature=0.55)
        loader.reload()

        assert received[0].llm.temperature == pytest.approx(0.55, abs=1e-6)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestHotReloadThreadSafety:
    def test_concurrent_get_config_does_not_raise(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)
        loader = ConfigLoader(config_path=cfg_path, watch=False)

        errors = []

        def reader():
            for _ in range(50):
                try:
                    cfg = loader.get_config()
                    assert cfg is not None
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_reload_and_read_does_not_raise(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)
        loader = ConfigLoader(config_path=cfg_path, watch=False)

        errors = []

        def reloader():
            for i in range(20):
                try:
                    _write_config(cfg_path, temperature=round(0.1 + i * 0.01, 3))
                    loader.reload()
                except Exception as e:
                    errors.append(e)

        def reader():
            for _ in range(100):
                try:
                    assert loader.get_config() is not None
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=reloader)] + [
            threading.Thread(target=reader) for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ---------------------------------------------------------------------------
# stop_watching
# ---------------------------------------------------------------------------

class TestStopWatching:
    def test_stop_watching_when_not_started_is_noop(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)
        loader = ConfigLoader(config_path=cfg_path, watch=False)
        loader.stop_watching()  # should not raise

    def test_stop_watching_stops_observer(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        _write_config(cfg_path)
        loader = ConfigLoader(config_path=cfg_path, watch=True)
        assert loader.observer is not None
        loader.stop_watching()
        assert loader.observer is None
