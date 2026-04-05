"""
/doctor — System Diagnostics

Checks Zenus health: API reachability, config validity, tool prerequisites,
MCP connectivity, and Python environment.  Prints a clear pass/fail table.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from typing import List, Tuple

from zenus_core.output.console import console


def _check(label: str, fn) -> Tuple[str, bool, str]:
    """Run *fn*; return (label, passed, detail)."""
    try:
        detail = fn()
        return label, True, detail or "OK"
    except Exception as exc:
        return label, False, str(exc)


def run_doctor() -> None:
    """Run all diagnostics and print a rich table."""
    from rich.table import Table

    results: List[Tuple[str, bool, str]] = []

    # 1. Config load
    def _check_config():
        from zenus_core.config.loader import get_config
        cfg = get_config()
        return f"profile={cfg.profile}, version={cfg.version}"

    results.append(_check("Config loads without errors", _check_config))

    # 2. LLM provider
    def _check_llm():
        from zenus_core.config.loader import get_config
        from zenus_core.brain.llm.factory import get_available_providers
        cfg = get_config()
        available = get_available_providers()
        if cfg.llm.provider not in available:
            raise RuntimeError(
                f"Provider '{cfg.llm.provider}' is not configured — check your API key"
            )
        return f"provider={cfg.llm.provider}"

    results.append(_check("Primary LLM provider configured", _check_llm))

    # 3. Anthropic API key
    def _check_anthropic_key():
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            # Try config
            try:
                from zenus_core.config.loader import get_config
                key = (get_config().llm.api_key or "")
            except Exception:
                pass
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        return f"key present (length={len(key)})"

    results.append(_check("Anthropic API key", _check_anthropic_key))

    # 4. Python version
    def _check_python():
        import sys
        v = sys.version_info
        if v < (3, 10):
            raise RuntimeError(f"Python {v.major}.{v.minor} — requires 3.10+")
        return f"Python {v.major}.{v.minor}.{v.micro}"

    results.append(_check("Python version ≥ 3.10", _check_python))

    # 5. Core dependencies
    for pkg in ["rich", "pydantic", "anthropic", "requests", "yaml"]:
        pkg_import = "yaml" if pkg == "yaml" else pkg

        def _check_pkg(p=pkg_import):
            importlib.import_module(p)
            return ""

        results.append(_check(f"Package: {pkg}", _check_pkg))

    # 6. git available
    def _check_git():
        path = shutil.which("git")
        if not path:
            raise RuntimeError("git not found in PATH")
        rc = subprocess.run(["git", "--version"], capture_output=True, text=True)
        return rc.stdout.strip()

    results.append(_check("git available", _check_git))

    # 7. Tool registry loads
    def _check_registry():
        from zenus_core.tools.registry import TOOLS
        return f"{len(TOOLS)} tools registered"

    results.append(_check("Tool registry", _check_registry))

    # 8. MCP config (if enabled)
    def _check_mcp():
        from zenus_core.config.loader import get_config
        cfg = get_config()
        if not cfg.mcp.client.enabled and not cfg.mcp.server.enabled:
            return "disabled (not configured)"
        try:
            import mcp  # noqa: F401
            return "mcp package available"
        except ImportError:
            raise RuntimeError("mcp package not installed; run: pip install mcp")

    results.append(_check("MCP integration", _check_mcp))

    # 9. Skills registry
    def _check_skills():
        from zenus_core.skills.registry import get_skills_registry
        count = get_skills_registry().count()
        return f"{count} skill(s) loaded"

    results.append(_check("Skills registry", _check_skills))

    # 10. History directory writable
    def _check_history_dir():
        from pathlib import Path
        d = Path.home() / ".zenus"
        d.mkdir(exist_ok=True)
        test_file = d / ".doctor_write_test"
        test_file.write_text("ok")
        test_file.unlink()
        return str(d)

    results.append(_check("~/.zenus/ writable", _check_history_dir))

    # -- Render table --
    console.print()
    table = Table(
        title="Zenus Doctor",
        show_header=True,
        header_style="bold cyan",
        box=None,
        padding=(0, 2),
    )
    table.add_column("Check", min_width=35)
    table.add_column("Status", width=8)
    table.add_column("Detail")

    passed = 0
    failed = 0
    for label, ok, detail in results:
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(label, status, detail)
        if ok:
            passed += 1
        else:
            failed += 1

    console.print(table)
    console.print()
    if failed == 0:
        console.print(f"[green]All {passed} checks passed.[/green]")
    else:
        console.print(
            f"[yellow]{passed} passed / [red]{failed} failed[/red][/yellow] — "
            "fix the failing checks above before using Zenus."
        )
    console.print()
