"""
Skills Registry

Discovers, loads, and indexes user-defined and built-in skills.

A *skill* is a Markdown file with optional YAML front-matter that defines a
reusable, parameterised prompt template.  Skills are auto-loaded from:

  1. .zenus/skills/   (project-local, highest priority)
  2. ~/.zenus/skills/ (user-global)
  3. Built-in bundled skills shipped with Zenus

Front-matter fields (all optional):

    ---
    name: commit
    description: Commit staged changes with a descriptive message
    trigger: /commit
    ---

    The prompt body follows below the front-matter block.

If no YAML front-matter is present, the filename (sans .md) is used as the
trigger and the first non-empty line is used as the description.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """A loaded skill definition."""

    name: str
    """Human-readable name (from front-matter or filename)."""

    trigger: str
    """Slash-command trigger, e.g. '/commit' or 'commit'."""

    description: str
    """One-line description shown in /skills list."""

    prompt: str
    """The full prompt template body."""

    source: str
    """Absolute path to the skill file (or 'bundled' for built-ins)."""

    bundled: bool = False
    """True for skills shipped with Zenus."""

    def invoke(self, args: str = "") -> str:
        """Return the prompt with {args} substituted."""
        if "{args}" in self.prompt:
            return self.prompt.replace("{args}", args)
        if args:
            return f"{self.prompt}\n\n{args}"
        return self.prompt


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_skill_file(path: Path, bundled: bool = False) -> Optional[Skill]:
    """Parse a Markdown skill file; return None on error."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Cannot read skill file %s: %s", path, exc)
        return None

    front_matter: Dict[str, str] = {}
    body = text

    m = _FRONT_MATTER_RE.match(text)
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                front_matter[k.strip().lower()] = v.strip()

    stem = path.stem
    name = front_matter.get("name", stem)
    trigger = front_matter.get("trigger", stem).lstrip("/")

    description = front_matter.get("description", "")
    if not description:
        for line in body.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                description = line[:100]
                break
    if not description:
        description = f"Skill: {name}"

    prompt = body.strip()
    if not prompt:
        return None

    return Skill(
        name=name,
        trigger=trigger,
        description=description,
        prompt=prompt,
        source=str(path) if not bundled else "bundled",
        bundled=bundled,
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class SkillsRegistry:
    """
    Manages the full collection of loaded skills.

    Thread-safe.  Call ``reload()`` to rescan directories without restarting.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._skills: Dict[str, Skill] = {}  # trigger → Skill
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        with self._lock:
            if not self._loaded:
                self._load_all()

    def _load_all(self) -> None:
        """Load all skills (must be called with self._lock held)."""
        self._skills = {}

        enabled, load_bundled, custom_dir = self._get_config()
        if not enabled:
            self._loaded = True
            return

        # 1. Bundled skills (lowest priority — overridable by user)
        if load_bundled:
            self._load_from_bundled()

        # 2. User-global skills (~/.zenus/skills/)
        user_dir = Path.home() / ".zenus" / "skills"
        if user_dir.is_dir():
            self._load_from_dir(user_dir)

        # 3. Project-local skills (.zenus/skills/ in cwd — highest priority)
        project_dirs = [Path.cwd() / ".zenus" / "skills"]
        if custom_dir:
            project_dirs.insert(0, Path(custom_dir))
        for d in project_dirs:
            if d.is_dir():
                self._load_from_dir(d)

        self._loaded = True
        logger.debug("Skills registry loaded: %d skill(s)", len(self._skills))

    def _get_config(self):
        try:
            from zenus_core.config.loader import get_config
            cfg = get_config().skills
            return cfg.enabled, cfg.load_bundled, cfg.skills_dir
        except Exception:
            return True, True, None

    def _load_from_dir(self, directory: Path) -> None:
        for md_file in sorted(directory.glob("*.md")):
            skill = _parse_skill_file(md_file)
            if skill:
                self._skills[skill.trigger] = skill
                logger.debug("Loaded skill '%s' from %s", skill.trigger, md_file)

    def _load_from_bundled(self) -> None:
        from zenus_core.skills import bundled as bundled_mod
        bundled_dir = Path(bundled_mod.__file__).parent
        for md_file in sorted(bundled_dir.glob("*.md")):
            skill = _parse_skill_file(md_file, bundled=True)
            if skill:
                self._skills[skill.trigger] = skill

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> int:
        """Re-scan all skill directories. Returns new skill count."""
        with self._lock:
            self._loaded = False
            self._load_all()
            return len(self._skills)

    def list_skills(self) -> List[Skill]:
        """Return all loaded skills sorted by trigger name."""
        self._ensure_loaded()
        with self._lock:
            return sorted(self._skills.values(), key=lambda s: s.trigger)

    def get(self, trigger: str) -> Optional[Skill]:
        """Look up a skill by trigger name (with or without leading /)."""
        self._ensure_loaded()
        key = trigger.lstrip("/")
        with self._lock:
            return self._skills.get(key)

    def invoke(self, trigger: str, args: str = "") -> Optional[str]:
        """
        Find and render a skill's prompt.  Returns None if not found.
        """
        skill = self.get(trigger)
        if skill is None:
            return None
        return skill.invoke(args)

    def count(self) -> int:
        self._ensure_loaded()
        with self._lock:
            return len(self._skills)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: Optional[SkillsRegistry] = None
_registry_lock = threading.Lock()


def get_skills_registry() -> SkillsRegistry:
    """Return the global SkillsRegistry singleton."""
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = SkillsRegistry()
    return _registry
