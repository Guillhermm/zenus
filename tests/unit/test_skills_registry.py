"""
Unit tests for Skills Registry (SkillsRegistry, Skill, _parse_skill_file).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _parse_skill_file
# ---------------------------------------------------------------------------

class TestParseSkillFile:
    def _write(self, tmp_path, name, content):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_parses_front_matter(self, tmp_path):
        from zenus_core.skills.registry import _parse_skill_file
        p = self._write(tmp_path, "myskill.md", """\
---
name: My Skill
trigger: my-skill
description: Does something great
---

Do the thing: {args}
""")
        skill = _parse_skill_file(p)
        assert skill is not None
        assert skill.name == "My Skill"
        assert skill.trigger == "my-skill"
        assert skill.description == "Does something great"
        assert "Do the thing" in skill.prompt

    def test_defaults_to_filename_stem(self, tmp_path):
        from zenus_core.skills.registry import _parse_skill_file
        p = self._write(tmp_path, "do-stuff.md", "Do the stuff.\n")
        skill = _parse_skill_file(p)
        assert skill is not None
        assert skill.trigger == "do-stuff"

    def test_description_falls_back_to_first_line(self, tmp_path):
        from zenus_core.skills.registry import _parse_skill_file
        p = self._write(tmp_path, "thing.md", "First line as description.\n\nRest of prompt.")
        skill = _parse_skill_file(p)
        assert skill is not None
        assert "First line" in skill.description

    def test_empty_file_returns_none(self, tmp_path):
        from zenus_core.skills.registry import _parse_skill_file
        p = self._write(tmp_path, "empty.md", "")
        skill = _parse_skill_file(p)
        assert skill is None

    def test_bundled_flag(self, tmp_path):
        from zenus_core.skills.registry import _parse_skill_file
        p = self._write(tmp_path, "b.md", "Bundled skill.\n")
        skill = _parse_skill_file(p, bundled=True)
        assert skill is not None
        assert skill.bundled is True
        assert skill.source == "bundled"


# ---------------------------------------------------------------------------
# Skill.invoke
# ---------------------------------------------------------------------------

class TestSkillInvoke:
    def _make_skill(self, prompt):
        from zenus_core.skills.registry import Skill
        return Skill(
            name="test", trigger="test",
            description="test", prompt=prompt, source="test.md"
        )

    def test_substitutes_args(self):
        skill = self._make_skill("Run this: {args}")
        result = skill.invoke("hello world")
        assert result == "Run this: hello world"

    def test_appends_args_when_no_placeholder(self):
        skill = self._make_skill("Do the thing.")
        result = skill.invoke("extra context")
        assert "Do the thing." in result
        assert "extra context" in result

    def test_no_args_returns_prompt_unchanged(self):
        skill = self._make_skill("Simple prompt.")
        assert skill.invoke() == "Simple prompt."
        assert skill.invoke("") == "Simple prompt."


# ---------------------------------------------------------------------------
# SkillsRegistry
# ---------------------------------------------------------------------------

class TestSkillsRegistry:
    def _registry_with_dir(self, tmp_path):
        from zenus_core.skills.registry import SkillsRegistry
        reg = SkillsRegistry()

        mock_cfg = MagicMock()
        mock_cfg.skills.enabled = True
        mock_cfg.skills.load_bundled = False
        mock_cfg.skills.skills_dir = str(tmp_path)

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            with patch("pathlib.Path.home", return_value=tmp_path):
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    reg.reload()

        return reg

    def test_loads_skills_from_directory(self, tmp_path):
        (tmp_path / "hello.md").write_text("Say hello to {args}.", encoding="utf-8")
        reg = self._registry_with_dir(tmp_path)
        skill = reg.get("hello")
        assert skill is not None
        assert skill.trigger == "hello"

    def test_get_with_leading_slash(self, tmp_path):
        (tmp_path / "test.md").write_text("Test skill.", encoding="utf-8")
        reg = self._registry_with_dir(tmp_path)
        assert reg.get("/test") is not None
        assert reg.get("test") is not None

    def test_invoke_returns_rendered_prompt(self, tmp_path):
        (tmp_path / "greet.md").write_text("Hello {args}!", encoding="utf-8")
        reg = self._registry_with_dir(tmp_path)
        result = reg.invoke("greet", "world")
        assert result == "Hello world!"

    def test_invoke_unknown_returns_none(self, tmp_path):
        reg = self._registry_with_dir(tmp_path)
        assert reg.invoke("nonexistent") is None

    def test_list_skills_sorted(self, tmp_path):
        for name in ("zebra", "alpha", "monkey"):
            (tmp_path / f"{name}.md").write_text(f"{name} skill.", encoding="utf-8")
        reg = self._registry_with_dir(tmp_path)
        skills = reg.list_skills()
        triggers = [s.trigger for s in skills]
        assert triggers == sorted(triggers)

    def test_disabled_registry_loads_nothing(self, tmp_path):
        (tmp_path / "skill.md").write_text("A skill.", encoding="utf-8")
        from zenus_core.skills.registry import SkillsRegistry

        reg = SkillsRegistry()
        mock_cfg = MagicMock()
        mock_cfg.skills.enabled = False
        mock_cfg.skills.load_bundled = False
        mock_cfg.skills.skills_dir = str(tmp_path)

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            reg.reload()

        assert reg.count() == 0

    def test_reload_picks_up_new_files(self, tmp_path):
        reg = self._registry_with_dir(tmp_path)
        assert reg.count() == 0

        (tmp_path / "new.md").write_text("New skill.", encoding="utf-8")
        mock_cfg = MagicMock()
        mock_cfg.skills.enabled = True
        mock_cfg.skills.load_bundled = False
        mock_cfg.skills.skills_dir = str(tmp_path)

        with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
            with patch("pathlib.Path.home", return_value=tmp_path):
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    reg.reload()

        assert reg.count() == 1


# ---------------------------------------------------------------------------
# Bundled skills exist and parse correctly
# ---------------------------------------------------------------------------

def test_bundled_skills_are_valid():
    from pathlib import Path
    from zenus_core.skills.registry import _parse_skill_file

    bundled_dir = Path(__file__).parent.parent.parent / (
        "packages/core/src/zenus_core/skills/bundled"
    )
    md_files = list(bundled_dir.glob("*.md"))
    assert len(md_files) >= 5, "Expected at least 5 bundled skills"

    for f in md_files:
        skill = _parse_skill_file(f, bundled=True)
        assert skill is not None, f"Failed to parse {f.name}"
        assert skill.prompt.strip(), f"Empty prompt in {f.name}"
        assert skill.trigger, f"Missing trigger in {f.name}"
