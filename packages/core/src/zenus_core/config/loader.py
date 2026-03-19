"""
Configuration Loader

Load configuration from YAML/TOML files with profile support.
"""

import os
import threading
import logging
import yaml
from pathlib import Path
from typing import Optional, Dict, Callable, List

from watchdog.observers import Observer
from zenus_core.config.schema import ZenusConfig, Profile

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Load and manage configuration

    Features:
    - Load from YAML/TOML
    - Profile support (dev/staging/production)
    - Hot-reload (watch file for changes) with callback notifications
    - Thread-safe config access
    - Schema validation
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        profile: Optional[Profile] = None,
        watch: bool = False,
    ):
        self.config_path = config_path or self._find_config_file()
        self.profile = profile or self._detect_profile()
        self._config: Optional[ZenusConfig] = None
        self._lock = threading.RLock()
        self._reload_callbacks: List[Callable[[ZenusConfig], None]] = []
        self.observer: Optional[Observer] = None
        self.watch_enabled = watch

        # Load initial config
        self._load_config()

        # Start watching if enabled
        if watch:
            self._start_watching()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> ZenusConfig:
        """Get current configuration (thread-safe)."""
        with self._lock:
            return self._config

    @property
    def config(self) -> Optional[ZenusConfig]:
        """Backwards-compat property (prefer get_config())."""
        return self._config

    @config.setter
    def config(self, value: Optional[ZenusConfig]) -> None:
        with self._lock:
            self._config = value

    def reload(self) -> ZenusConfig:
        """Manually reload configuration from disk."""
        self._load_config()
        return self.get_config()

    def on_reload(self, callback: Callable[[ZenusConfig], None]) -> None:
        """
        Register a callback invoked every time config is reloaded.

        The callback receives the new ZenusConfig instance.  It is called
        from the watchdog thread, so it must be thread-safe.
        """
        with self._lock:
            self._reload_callbacks.append(callback)

    def remove_reload_callback(self, callback: Callable[[ZenusConfig], None]) -> None:
        """Deregister a previously registered reload callback."""
        with self._lock:
            try:
                self._reload_callbacks.remove(callback)
            except ValueError:
                pass

    def save_config(self, config: ZenusConfig) -> None:
        """Persist configuration to disk and reload."""
        data = config.model_dump(exclude_unset=False)
        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        self._load_config()

    def stop_watching(self) -> None:
        """Stop the filesystem watcher."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_config_file(self) -> Path:
        """Find config file in standard locations."""
        if "ZENUS_CONFIG" in os.environ:
            return Path(os.environ["ZENUS_CONFIG"])

        search_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd() / "zenus.yaml",
            Path.cwd() / "zenus.yml",
            Path.cwd() / ".zenus.yaml",
            Path.home() / ".zenus" / "config.yaml",
            Path.home() / ".config" / "zenus" / "config.yaml",
        ]

        for path in search_paths:
            if path.exists():
                return path

        default_path = Path.home() / ".zenus" / "config.yaml"
        default_path.parent.mkdir(parents=True, exist_ok=True)

        if not default_path.exists():
            self._create_default_config(default_path)

        return default_path

    def _detect_profile(self) -> Profile:
        """Detect profile from environment."""
        env_profile = os.getenv("ZENUS_PROFILE", "dev").lower()
        try:
            return Profile(env_profile)
        except ValueError:
            logger.warning("Unknown profile '%s', using 'dev'", env_profile)
            return Profile.DEV

    def _load_config(self) -> None:
        """Load config from file (thread-safe)."""
        if not self.config_path.exists():
            logger.warning("Config file not found: %s", self.config_path)
            new_config = ZenusConfig(profile=self.profile)
        else:
            try:
                with open(self.config_path, "r") as f:
                    data = yaml.safe_load(f) or {}

                if "profiles" in data and self.profile.value in data["profiles"]:
                    profile_data = data["profiles"][self.profile.value]
                    data = self._merge_dicts(data, profile_data)

                data.pop("profiles", None)
                data["profile"] = self.profile.value

                new_config = ZenusConfig(**data)
            except Exception as exc:
                logger.error("Error loading config: %s — using defaults", exc)
                new_config = ZenusConfig(profile=self.profile)

        with self._lock:
            self._config = new_config
            callbacks = list(self._reload_callbacks)

        # Fire callbacks outside the lock to prevent deadlocks
        for cb in callbacks:
            try:
                cb(new_config)
            except Exception as exc:
                logger.error("Config reload callback raised: %s", exc)

    def _merge_dicts(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    def _create_default_config(self, path: Path) -> None:
        """Write a default config.yaml."""
        default_config = {
            "version": "0.6.0",
            "profile": "dev",
            "llm": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout_seconds": 30,
            },
            "fallback": {"enabled": True, "providers": ["anthropic", "deepseek", "rule_based"]},
            "circuit_breaker": {
                "enabled": True,
                "failure_threshold": 5,
                "timeout_seconds": 60.0,
                "success_threshold": 2,
            },
            "retry": {
                "enabled": True,
                "max_attempts": 3,
                "initial_delay_seconds": 1.0,
                "max_delay_seconds": 30.0,
                "exponential_base": 2.0,
                "jitter": True,
            },
            "cache": {"enabled": True, "ttl_seconds": 3600, "max_size_mb": 100},
            "safety": {
                "sandbox_enabled": True,
                "max_file_size_mb": 100,
                "allowed_paths": ["."],
                "blocked_commands": ["rm -rf /", "dd if=", ":(){ :|:& };:"],
            },
            "monitoring": {
                "enabled": True,
                "check_interval_seconds": 300,
                "disk_warning_threshold": 0.8,
                "disk_critical_threshold": 0.9,
                "cpu_warning_threshold": 0.8,
                "memory_warning_threshold": 0.85,
            },
            "features": {
                "voice_interface": False,
                "multi_agent": False,
                "proactive_monitoring": True,
                "tree_of_thoughts": True,
                "prompt_evolution": True,
                "goal_inference": True,
                "self_reflection": True,
                "data_visualization": True,
            },
            "profiles": {
                "dev": {
                    "llm": {"temperature": 0.9},
                    "cache": {"ttl_seconds": 300},
                    "safety": {"sandbox_enabled": False},
                },
                "staging": {
                    "llm": {"temperature": 0.7},
                    "cache": {"ttl_seconds": 1800},
                    "safety": {"sandbox_enabled": True},
                },
                "production": {
                    "llm": {"temperature": 0.5},
                    "cache": {"ttl_seconds": 3600},
                    "safety": {"sandbox_enabled": True},
                    "features": {"voice_interface": False, "multi_agent": True},
                },
            },
        }

        with open(path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)

        logger.info("Created default config: %s", path)

    def _start_watching(self) -> None:
        """Start watchdog filesystem observer."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent

            loader_ref = self

            class _Handler(FileSystemEventHandler):
                def on_modified(self, event: FileModifiedEvent) -> None:
                    if Path(event.src_path).resolve() == loader_ref.config_path.resolve():
                        logger.info("Config file changed — reloading")
                        loader_ref._load_config()

            self.observer = Observer()
            self.observer.schedule(_Handler(), str(self.config_path.parent), recursive=False)
            self.observer.daemon = True
            self.observer.start()
            logger.debug("Config hot-reload watching: %s", self.config_path)

        except ImportError:
            logger.debug("watchdog not available — hot-reload disabled")


# ---------------------------------------------------------------------------
# Module-level globals
# ---------------------------------------------------------------------------

_config_loader: Optional[ConfigLoader] = None
_loader_lock = threading.Lock()


def get_config(reload: bool = False) -> ZenusConfig:
    """
    Get global configuration (thread-safe).

    Args:
        reload: Force re-instantiate the loader from disk.

    Returns:
        ZenusConfig instance
    """
    global _config_loader

    with _loader_lock:
        if _config_loader is None or reload:
            _config_loader = ConfigLoader(watch=True)

    return _config_loader.get_config()


def reload_config() -> ZenusConfig:
    """Reload configuration from file."""
    return get_config(reload=True)


def register_reload_callback(callback: Callable[[ZenusConfig], None]) -> None:
    """
    Register a module-level callback fired on every hot-reload.

    Useful for subsystems (e.g. model router, monitoring) that need to
    pick up config changes without polling.
    """
    global _config_loader

    with _loader_lock:
        if _config_loader is None:
            _config_loader = ConfigLoader(watch=True)

    _config_loader.on_reload(callback)
