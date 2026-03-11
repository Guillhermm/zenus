"""
Configuration Loader

Load configuration from YAML/TOML files with profile support.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

from zenus_core.config.schema import ZenusConfig, Profile


class ConfigLoader:
    """
    Load and manage configuration
    
    Features:
    - Load from YAML/TOML
    - Profile support (dev/staging/production)
    - Hot-reload (watch file for changes)
    - Schema validation
    """
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        profile: Optional[Profile] = None,
        watch: bool = False
    ):
        self.config_path = config_path or self._find_config_file()
        self.profile = profile or self._detect_profile()
        self.config: Optional[ZenusConfig] = None
        self.observer: Optional[Observer] = None
        self.watch_enabled = watch
        
        # Load initial config
        self._load_config()
        
        # Start watching if enabled
        if watch:
            self._start_watching()
    
    def _find_config_file(self) -> Path:
        """Find config file in standard locations"""
        # Check environment variable first
        if "ZENUS_CONFIG" in os.environ:
            return Path(os.environ["ZENUS_CONFIG"])
        
        # Check standard locations
        search_paths = [
            Path.cwd() / "config.yaml",           # Project config (running from source)
            Path.cwd() / "zenus.yaml",
            Path.cwd() / "zenus.yml",
            Path.cwd() / ".zenus.yaml",
            Path.home() / ".zenus" / "config.yaml",
            Path.home() / ".config" / "zenus" / "config.yaml",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        # Default: use ~/.zenus/config.yaml
        default_path = Path.home() / ".zenus" / "config.yaml"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create default config if doesn't exist
        if not default_path.exists():
            self._create_default_config(default_path)
        
        return default_path
    
    def _detect_profile(self) -> Profile:
        """Detect profile from environment"""
        env_profile = os.getenv("ZENUS_PROFILE", "dev").lower()
        
        try:
            return Profile(env_profile)
        except ValueError:
            print(f"⚠️  Unknown profile '{env_profile}', using 'dev'")
            return Profile.DEV
    
    def _load_config(self):
        """Load config from file"""
        if not self.config_path.exists():
            print(f"⚠️  Config file not found: {self.config_path}")
            self.config = ZenusConfig(profile=self.profile)
            return
        
        try:
            # Load YAML
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            # Merge with profile-specific overrides
            if "profiles" in data and self.profile.value in data["profiles"]:
                profile_data = data["profiles"][self.profile.value]
                data = self._merge_dicts(data, profile_data)
            
            # Remove profiles section (already merged)
            data.pop("profiles", None)
            
            # Set profile
            data["profile"] = self.profile.value
            
            # Validate and create config
            self.config = ZenusConfig(**data)
            
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            print(f"Using default configuration")
            self.config = ZenusConfig(profile=self.profile)
    
    def _merge_dicts(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _create_default_config(self, path: Path):
        """Create default config file"""
        default_config = {
            "version": "0.5.1",
            "profile": "dev",
            
            "llm": {
                "provider": "anthropic",
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout_seconds": 30
            },
            
            "fallback": {
                "enabled": True,
                "providers": ["anthropic", "deepseek", "rule_based"]
            },
            
            "circuit_breaker": {
                "enabled": True,
                "failure_threshold": 5,
                "timeout_seconds": 60.0,
                "success_threshold": 2
            },
            
            "retry": {
                "enabled": True,
                "max_attempts": 3,
                "initial_delay_seconds": 1.0,
                "max_delay_seconds": 30.0,
                "exponential_base": 2.0,
                "jitter": True
            },
            
            "cache": {
                "enabled": True,
                "ttl_seconds": 3600,
                "max_size_mb": 100
            },
            
            "safety": {
                "sandbox_enabled": True,
                "max_file_size_mb": 100,
                "allowed_paths": ["."],
                "blocked_commands": ["rm -rf /", "dd if=", ":(){ :|:& };:"]
            },
            
            "monitoring": {
                "enabled": True,
                "check_interval_seconds": 300,
                "disk_warning_threshold": 0.8,
                "disk_critical_threshold": 0.9,
                "cpu_warning_threshold": 0.8,
                "memory_warning_threshold": 0.85
            },
            
            "features": {
                "voice_interface": False,
                "multi_agent": False,
                "proactive_monitoring": True,
                "tree_of_thoughts": True,
                "prompt_evolution": True,
                "goal_inference": True,
                "self_reflection": True,
                "data_visualization": True
            },
            
            "profiles": {
                "dev": {
                    "llm": {
                        "temperature": 0.9
                    },
                    "cache": {
                        "ttl_seconds": 300
                    },
                    "safety": {
                        "sandbox_enabled": False
                    }
                },
                
                "staging": {
                    "llm": {
                        "temperature": 0.7
                    },
                    "cache": {
                        "ttl_seconds": 1800
                    },
                    "safety": {
                        "sandbox_enabled": True
                    }
                },
                
                "production": {
                    "llm": {
                        "temperature": 0.5
                    },
                    "cache": {
                        "ttl_seconds": 3600
                    },
                    "safety": {
                        "sandbox_enabled": True
                    },
                    "features": {
                        "voice_interface": False,
                        "multi_agent": True
                    }
                }
            }
        }
        
        with open(path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
        
        print(f"✅ Created default config: {path}")
    
    def _start_watching(self):
        """Start watching config file for changes"""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent

            loader_ref = self

            class ConfigFileHandler(FileSystemEventHandler):
                def on_modified(self, event: FileModifiedEvent):
                    if event.src_path == str(loader_ref.config_path):
                        loader_ref._load_config()

            self.observer = Observer()
            self.observer.schedule(
                ConfigFileHandler(),
                str(self.config_path.parent),
                recursive=False,
            )
            self.observer.start()

        except ImportError:
            pass  # watchdog optional — hot-reload simply disabled
    
    def stop_watching(self):
        """Stop watching config file"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
    
    def reload(self):
        """Manually reload configuration"""
        self._load_config()
        return self.config
    
    def get_config(self) -> ZenusConfig:
        """Get current configuration"""
        return self.config
    
    def save_config(self, config: ZenusConfig):
        """Save configuration to file"""
        # Convert to dict
        data = config.model_dump(exclude_unset=False)
        
        # Write to file
        with open(self.config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        # Reload
        self._load_config()


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config(reload: bool = False) -> ZenusConfig:
    """
    Get global configuration
    
    Args:
        reload: Force reload from file
    
    Returns:
        ZenusConfig instance
    """
    global _config_loader
    
    if _config_loader is None or reload:
        _config_loader = ConfigLoader(watch=True)
    
    return _config_loader.get_config()


def reload_config() -> ZenusConfig:
    """Reload configuration from file"""
    return get_config(reload=True)
