"""
Unit tests for config schema additions: HooksConfig, PlanModeConfig, SkillsConfig, SessionConfig, OutputStyleConfig.
"""

import pytest


class TestHooksConfig:
    def test_default_empty(self):
        from zenus_core.config.schema import HooksConfig
        cfg = HooksConfig()
        assert cfg.pre_tool_use == []
        assert cfg.post_tool_use == []

    def test_hook_entry_defaults(self):
        from zenus_core.config.schema import HookEntry
        entry = HookEntry(match="FileOps", command="echo hi")
        assert entry.timeout_seconds == 10

    def test_hook_entry_custom_timeout(self):
        from zenus_core.config.schema import HookEntry
        entry = HookEntry(match="*", command="test", timeout_seconds=30)
        assert entry.timeout_seconds == 30

    def test_hooks_config_with_entries(self):
        from zenus_core.config.schema import HooksConfig, HookEntry
        cfg = HooksConfig(
            pre_tool_use=[HookEntry(match="ShellOps", command="echo pre")],
            post_tool_use=[HookEntry(match="*", command="echo post")],
        )
        assert len(cfg.pre_tool_use) == 1
        assert len(cfg.post_tool_use) == 1


class TestPlanModeConfig:
    def test_default_disabled(self):
        from zenus_core.config.schema import PlanModeConfig
        cfg = PlanModeConfig()
        assert cfg.enabled is False
        assert cfg.auto_approve_low_risk is False

    def test_can_enable(self):
        from zenus_core.config.schema import PlanModeConfig
        cfg = PlanModeConfig(enabled=True)
        assert cfg.enabled is True


class TestSkillsConfig:
    def test_defaults(self):
        from zenus_core.config.schema import SkillsConfig
        cfg = SkillsConfig()
        assert cfg.enabled is True
        assert cfg.load_bundled is True
        assert cfg.skills_dir is None

    def test_custom_dir(self):
        from zenus_core.config.schema import SkillsConfig
        cfg = SkillsConfig(skills_dir="/custom/path")
        assert cfg.skills_dir == "/custom/path"


class TestSessionConfig:
    def test_defaults(self):
        from zenus_core.config.schema import SessionConfig
        cfg = SessionConfig()
        assert cfg.persist is True
        assert cfg.max_sessions == 50
        assert 0 < cfg.compact_threshold <= 1.0

    def test_custom_compact_threshold(self):
        from zenus_core.config.schema import SessionConfig
        cfg = SessionConfig(compact_threshold=0.9)
        assert cfg.compact_threshold == 0.9


class TestOutputStyleConfig:
    def test_default_rich(self):
        from zenus_core.config.schema import OutputStyleConfig
        cfg = OutputStyleConfig()
        assert cfg.style == "rich"

    def test_valid_styles(self):
        from zenus_core.config.schema import OutputStyleConfig
        for style in ("rich", "plain", "compact", "json"):
            cfg = OutputStyleConfig(style=style)
            assert cfg.style == style


class TestZenusConfigIntegration:
    def test_zenus_config_includes_all_new_fields(self):
        from zenus_core.config.schema import ZenusConfig
        cfg = ZenusConfig()
        assert hasattr(cfg, "hooks")
        assert hasattr(cfg, "plan_mode")
        assert hasattr(cfg, "skills")
        assert hasattr(cfg, "session")
        assert hasattr(cfg, "output_style")

    def test_full_config_loads_with_defaults(self):
        from zenus_core.config.schema import ZenusConfig
        cfg = ZenusConfig()
        # All nested objects should be default instances
        assert cfg.hooks.pre_tool_use == []
        assert cfg.plan_mode.enabled is False
        assert cfg.skills.enabled is True
        assert cfg.session.persist is True
        assert cfg.output_style.style == "rich"

    def test_config_serialises_to_dict(self):
        from zenus_core.config.schema import ZenusConfig
        cfg = ZenusConfig()
        d = cfg.model_dump()
        assert "hooks" in d
        assert "plan_mode" in d
        assert "skills" in d
        assert "session" in d
        assert "output_style" in d
