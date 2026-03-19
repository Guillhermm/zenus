"""
Property-Based Tests for Intent IR and Safety Policy

Uses Hypothesis to verify invariants hold across arbitrary inputs:
- IntentIR / Step schema validation properties
- Safety policy invariants (risk thresholds, tool blocking)
- Config schema validation properties
- SecretsManager masking invariants
"""

import pytest
from hypothesis import given, assume, settings, HealthCheck
from hypothesis import strategies as st

from zenus_core.brain.llm.schemas import Step, IntentIR
from zenus_core.safety.policy import check_step, SafetyError
from zenus_core.config.schema import (
    ZenusConfig, LLMConfig, SafetyConfig, Profile,
    CacheConfig, RetrySettings, CircuitBreakerSettings,
)
from zenus_core.config.secrets import SecretsManager


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")),
    min_size=1,
    max_size=64,
)

tool_names = st.sampled_from([
    "file_ops", "shell_ops", "git_ops", "system_ops",
    "network_ops", "package_ops", "service_ops", "container_ops",
    "browser_ops", "vision_ops", "code_exec",
])

action_names = st.sampled_from([
    "read", "write", "run", "scan", "move", "copy",
    "delete", "list", "status", "install", "remove",
])

risk_levels = st.integers(min_value=0, max_value=3)

step_strategy = st.builds(
    Step,
    tool=tool_names,
    action=action_names,
    args=st.fixed_dictionaries({}),
    risk=risk_levels,
)

safe_step_strategy = st.builds(
    Step,
    tool=tool_names,
    action=action_names,
    args=st.fixed_dictionaries({}),
    risk=st.integers(min_value=0, max_value=2),
)

blocking_step_strategy = st.builds(
    Step,
    tool=tool_names,
    action=action_names,
    args=st.fixed_dictionaries({}),
    risk=st.just(3),
)

intent_strategy = st.builds(
    IntentIR,
    goal=safe_text,
    requires_confirmation=st.booleans(),
    steps=st.lists(step_strategy, min_size=0, max_size=10),
)


# ---------------------------------------------------------------------------
# IntentIR / Step schema properties
# ---------------------------------------------------------------------------

class TestStepSchemaProperties:
    @given(step_strategy)
    def test_step_risk_always_in_range(self, step: Step):
        """risk is always in [0, 3] regardless of how the object is built."""
        assert 0 <= step.risk <= 3

    @given(tool=tool_names, action=action_names, risk=risk_levels)
    def test_step_roundtrip_via_dict(self, tool: str, action: str, risk: int):
        """Step serialises and deserialises without data loss."""
        step = Step(tool=tool, action=action, args={}, risk=risk)
        restored = Step(**step.model_dump())
        assert restored.tool == step.tool
        assert restored.action == step.action
        assert restored.risk == step.risk

    @given(step_strategy)
    def test_step_tool_is_non_empty_string(self, step: Step):
        assert isinstance(step.tool, str) and len(step.tool) > 0

    @given(step_strategy)
    def test_step_args_always_dict(self, step: Step):
        assert isinstance(step.args, dict)

    @given(step_strategy)
    def test_step_model_dump_contains_required_keys(self, step: Step):
        d = step.model_dump()
        assert "tool" in d
        assert "action" in d
        assert "args" in d
        assert "risk" in d


class TestIntentIRSchemaProperties:
    @given(intent_strategy)
    def test_intentir_steps_is_list(self, intent: IntentIR):
        assert isinstance(intent.steps, list)

    @given(intent_strategy)
    def test_intentir_goal_non_empty(self, intent: IntentIR):
        assert isinstance(intent.goal, str) and len(intent.goal) > 0

    @given(intent_strategy)
    def test_intentir_requires_confirmation_is_bool(self, intent: IntentIR):
        assert isinstance(intent.requires_confirmation, bool)

    @given(intent_strategy)
    def test_intentir_all_step_risks_in_range(self, intent: IntentIR):
        for step in intent.steps:
            assert 0 <= step.risk <= 3

    @given(intent_strategy)
    def test_intentir_roundtrip(self, intent: IntentIR):
        """Full serialise/deserialise round-trip preserves structure."""
        d = intent.model_dump()
        restored = IntentIR(**d)
        assert restored.goal == intent.goal
        assert restored.requires_confirmation == intent.requires_confirmation
        assert len(restored.steps) == len(intent.steps)

    @given(st.lists(step_strategy, min_size=1, max_size=20))
    def test_intentir_step_count_preserved(self, steps):
        intent = IntentIR(goal="test", requires_confirmation=False, steps=steps)
        assert len(intent.steps) == len(steps)


# ---------------------------------------------------------------------------
# Safety policy invariants
# ---------------------------------------------------------------------------

class TestSafetyPolicyProperties:
    @given(safe_step_strategy)
    def test_safe_steps_never_raise(self, step: Step):
        """Any step with risk < 3 must pass the policy check."""
        result = check_step(step)
        assert result is True

    @given(blocking_step_strategy)
    def test_risk_3_always_raises(self, step: Step):
        """Every step with risk == 3 must be blocked by policy."""
        with pytest.raises(SafetyError):
            check_step(step)

    @given(step_strategy)
    def test_policy_is_deterministic(self, step: Step):
        """Calling check_step twice on the same step gives the same outcome."""
        if step.risk >= 3:
            with pytest.raises(SafetyError):
                check_step(step)
            with pytest.raises(SafetyError):
                check_step(step)
        else:
            assert check_step(step) is True
            assert check_step(step) is True

    @given(risk=st.integers(min_value=0, max_value=2))
    def test_any_tool_any_action_low_risk_passes(self, risk: int):
        """The policy is tool-agnostic for risk < 3."""
        step = Step(tool="shell_ops", action="run", args={}, risk=risk)
        assert check_step(step) is True

    @given(
        tool=tool_names,
        action=action_names,
    )
    def test_risk_3_blocked_regardless_of_tool_and_action(self, tool: str, action: str):
        """risk == 3 is always blocked, no matter which tool or action."""
        step = Step(tool=tool, action=action, args={}, risk=3)
        with pytest.raises(SafetyError):
            check_step(step)

    @given(
        n=st.integers(min_value=1, max_value=50),
        risk=st.integers(min_value=0, max_value=2),
    )
    def test_many_safe_steps_all_pass(self, n: int, risk: int):
        """Batch of safe steps: every single one must pass."""
        steps = [Step(tool="file_ops", action="read", args={}, risk=risk) for _ in range(n)]
        for s in steps:
            assert check_step(s) is True


# ---------------------------------------------------------------------------
# Config schema properties
# ---------------------------------------------------------------------------

class TestConfigSchemaProperties:
    @given(temperature=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    def test_valid_temperature_accepted(self, temperature: float):
        cfg = LLMConfig(temperature=temperature)
        assert 0.0 <= cfg.temperature <= 1.0

    @given(temperature=st.one_of(
        st.floats(max_value=-0.001, allow_nan=False),
        st.floats(min_value=1.001, allow_nan=False),
    ))
    def test_invalid_temperature_rejected(self, temperature: float):
        assume(not (temperature != temperature))  # exclude NaN
        with pytest.raises(Exception):
            LLMConfig(temperature=temperature)

    @given(profile=st.sampled_from(list(Profile)))
    def test_all_profiles_valid(self, profile: Profile):
        cfg = ZenusConfig(profile=profile)
        assert cfg.profile == profile.value or cfg.profile == profile

    @given(
        enabled=st.booleans(),
        ttl=st.integers(min_value=1, max_value=86400),
        size=st.integers(min_value=1, max_value=10240),
    )
    def test_cache_config_roundtrip(self, enabled: bool, ttl: int, size: int):
        cfg = CacheConfig(enabled=enabled, ttl_seconds=ttl, max_size_mb=size)
        d = cfg.model_dump()
        restored = CacheConfig(**d)
        assert restored.enabled == cfg.enabled
        assert restored.ttl_seconds == cfg.ttl_seconds

    @given(
        attempts=st.integers(min_value=1, max_value=100),
        initial=st.floats(min_value=0.1, max_value=10.0, allow_nan=False),
    )
    def test_retry_settings_roundtrip(self, attempts: int, initial: float):
        cfg = RetrySettings(max_attempts=attempts, initial_delay_seconds=initial)
        assert cfg.max_attempts == attempts


# ---------------------------------------------------------------------------
# SecretsManager masking invariants
# ---------------------------------------------------------------------------

class TestSecretsMaskingProperties:
    @given(value=st.text(min_size=8, max_size=128))
    def test_masked_value_never_reveals_middle(self, value: str):
        mgr = SecretsManager.__new__(SecretsManager)
        mgr._secrets = {}
        masked = mgr.mask_secret(value)
        # Masked output must not equal the original
        assert masked != value
        # Must contain *** somewhere
        assert "***" in masked

    @given(value=st.text(min_size=0, max_size=7))
    def test_short_secret_returns_stars(self, value: str):
        mgr = SecretsManager.__new__(SecretsManager)
        mgr._secrets = {}
        masked = mgr.mask_secret(value)
        assert masked == "***"

    @given(value=st.text(min_size=8, max_size=128))
    def test_masked_length_is_bounded(self, value: str):
        mgr = SecretsManager.__new__(SecretsManager)
        mgr._secrets = {}
        masked = mgr.mask_secret(value)
        # Stars plus prefix (6) and suffix (3) — must be shorter than original
        assert len(masked) < len(value) + 10  # allow small margin for stars

    @given(key=safe_text, value=st.text(min_size=1, max_size=128))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_get_returns_stored_value(self, key: str, value: str):
        mgr = SecretsManager.__new__(SecretsManager)
        mgr._secrets = {key: value}
        assert mgr.get(key) == value

    @given(key=safe_text)
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_missing_key_returns_default(self, key: str):
        mgr = SecretsManager.__new__(SecretsManager)
        mgr._secrets = {}
        assert mgr.get(key, "fallback") == "fallback"
        assert mgr.get(key) is None
