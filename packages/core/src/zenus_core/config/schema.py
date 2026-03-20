"""
Configuration Schema

Type-safe configuration using Pydantic.
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class Profile(str, Enum):
    """Configuration profiles"""
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMConfig(BaseModel):
    """LLM provider configuration"""
    provider: str = Field(default="anthropic", description="LLM provider name")
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Model identifier")
    api_key: Optional[str] = Field(default=None, description="API key (loaded from secrets)")
    max_tokens: int = Field(default=4096, description="Maximum tokens per request")
    temperature: float = Field(default=0.7, description="Temperature (0-1)")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    
    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is between 0 and 1"""
        if not 0 <= v <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        return v


class FallbackConfig(BaseModel):
    """Fallback LLM configuration"""
    enabled: bool = Field(default=True, description="Enable fallback chain")
    providers: List[str] = Field(
        default=["anthropic", "deepseek", "rule_based"],
        description="Fallback chain in priority order"
    )


class CircuitBreakerSettings(BaseModel):
    """Circuit breaker configuration (schema only; runtime config lives in zenus_core.error)"""
    enabled: bool = Field(default=True, description="Enable circuit breakers")
    failure_threshold: int = Field(default=5, description="Failures before opening")
    timeout_seconds: float = Field(default=60.0, description="Timeout before retry")
    success_threshold: int = Field(default=2, description="Successes to close")


class RetrySettings(BaseModel):
    """Retry configuration (schema only; runtime config lives in zenus_core.error)"""
    enabled: bool = Field(default=True, description="Enable retry logic")
    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    initial_delay_seconds: float = Field(default=1.0, description="Initial delay")
    max_delay_seconds: float = Field(default=30.0, description="Maximum delay")
    exponential_base: float = Field(default=2.0, description="Exponential backoff base")
    jitter: bool = Field(default=True, description="Add jitter to delays")


class CacheConfig(BaseModel):
    """Cache configuration"""
    enabled: bool = Field(default=True, description="Enable caching")
    ttl_seconds: int = Field(default=3600, description="Cache TTL (1 hour)")
    max_size_mb: int = Field(default=100, description="Maximum cache size in MB")


class SafetyConfig(BaseModel):
    """Safety and sandbox configuration"""
    sandbox_enabled: bool = Field(default=True, description="Enable sandbox")
    max_file_size_mb: int = Field(default=100, description="Max file size")
    allowed_paths: List[str] = Field(
        default=["."],
        description="Allowed paths for operations"
    )
    blocked_commands: List[str] = Field(
        default=["rm -rf /", "dd if=", ":(){ :|:& };:"],
        description="Blocked dangerous commands"
    )


class MonitoringConfig(BaseModel):
    """Proactive monitoring configuration"""
    enabled: bool = Field(default=True, description="Enable proactive monitoring")
    check_interval_seconds: int = Field(default=300, description="Check interval (5 min)")
    disk_warning_threshold: float = Field(default=0.8, description="Disk warning at 80%")
    disk_critical_threshold: float = Field(default=0.9, description="Disk critical at 90%")
    cpu_warning_threshold: float = Field(default=0.8, description="CPU warning at 80%")
    memory_warning_threshold: float = Field(default=0.85, description="Memory warning at 85%")


class FeaturesConfig(BaseModel):
    """Feature flags"""
    voice_interface: bool = Field(default=False, description="Enable voice interface")
    multi_agent: bool = Field(default=False, description="Enable multi-agent collaboration")
    proactive_monitoring: bool = Field(default=True, description="Enable proactive monitoring")
    tree_of_thoughts: bool = Field(default=True, description="Enable Tree of Thoughts")
    prompt_evolution: bool = Field(default=True, description="Enable Prompt Evolution")
    goal_inference: bool = Field(default=True, description="Enable Goal Inference")
    self_reflection: bool = Field(default=True, description="Enable Self-Reflection")
    data_visualization: bool = Field(default=True, description="Enable Data Visualization")


class SearchConfig(BaseModel):
    """Web search configuration"""
    brave_api_key: Optional[str] = Field(
        default=None,
        description="Brave Search API key — free tier at brave.com/search/api (2,000 req/month)"
    )
    debug: bool = Field(
        default=False,
        description=(
            "Legacy alias for debug.search. Show query category, source breakdown, "
            "and raw results before the synthesised answer. "
            "Prefer setting debug.search: true instead."
        )
    )


class DebugConfig(BaseModel):
    """Debug output controls.

    All flags default to False so regular users see clean output.
    Set ``enabled: true`` (or ``ZENUS_DEBUG=1``) to turn everything on at once.
    Individual subsystem flags override the master switch per-subsystem.

    Environment variable equivalents (useful for one-off sessions):
        ZENUS_DEBUG=1                  master — enables all subsystems
        ZENUS_DEBUG_ORCHESTRATOR=1     routing, complexity, Tree of Thoughts
        ZENUS_DEBUG_BRAIN=1            prompt evolution, model internals
        ZENUS_DEBUG_EXECUTION=1        per-step output, parallel fallback
        ZENUS_DEBUG_VOICE=1            TTS/STT init and pipeline messages
        ZENUS_DEBUG_SEARCH=1           search decisions and result breakdown
    """

    enabled: bool = Field(
        default=False,
        description="Master debug switch — enables all subsystem flags when True.",
    )
    orchestrator: bool = Field(
        default=False,
        description=(
            "Show routing decisions, task-complexity scores, Tree of Thoughts "
            "exploration, provider/model override notices, and cache hits."
        ),
    )
    brain: bool = Field(
        default=False,
        description="Show prompt-evolution promotions and internal brain events.",
    )
    execution: bool = Field(
        default=False,
        description=(
            "Show per-step execution output (tool.action: result) and "
            "parallel-to-sequential fallback notices."
        ),
    )
    voice: bool = Field(
        default=False,
        description="Show TTS/STT initialisation messages and pipeline internals.",
    )
    search: bool = Field(
        default=False,
        description=(
            "Show query category, source breakdown, and raw result snippets before "
            "the synthesised answer. Also enabled by ZENUS_SEARCH_DEBUG for "
            "backwards compatibility."
        ),
    )


class ZenusConfig(BaseModel):
    """
    Main Zenus configuration
    
    Supports multiple profiles (dev, staging, production) with
    schema validation and hot-reload capability.
    """
    
    # Metadata
    profile: Profile = Field(default=Profile.DEV, description="Active profile")
    version: str = Field(default="0.5.1", description="Config version")
    
    # LLM Configuration
    llm: LLMConfig = Field(default_factory=LLMConfig)
    fallback: FallbackConfig = Field(default_factory=FallbackConfig)
    
    # Error Handling
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    
    # Performance
    cache: CacheConfig = Field(default_factory=CacheConfig)
    
    # Safety
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    
    # Monitoring
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Features
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)

    # Search
    search: SearchConfig = Field(default_factory=SearchConfig)

    # Debug output controls
    debug: DebugConfig = Field(default_factory=DebugConfig)

    # Custom settings
    custom: Dict[str, Any] = Field(default_factory=dict, description="Custom settings")

    @field_validator("custom", mode="before")
    @classmethod
    def _normalize_custom(cls, v: Any) -> Dict[str, Any]:
        """Coerce None or missing custom field to an empty dict."""
        return v if isinstance(v, dict) else {}
    
    class Config:
        """Pydantic config"""
        use_enum_values = True
        validate_assignment = True
        
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.profile == Profile.PRODUCTION
    
    def is_dev(self) -> bool:
        """Check if running in development"""
        return self.profile == Profile.DEV
    
    def is_staging(self) -> bool:
        """Check if running in staging"""
        return self.profile == Profile.STAGING
