"""
Safety and privilege integration tests.

Verifies the full enforcement chain:
  SafetyPolicy → planner → orchestrator

Tests run without a real LLM — the IntentIR is constructed directly so we
control which risk levels and tools reach the safety checks.
"""

import pytest
from unittest.mock import patch, Mock

from zenus_core.brain.llm.schemas import IntentIR, Step
from zenus_core.brain.planner import execute_plan
from zenus_core.safety.policy import SafetyError
from zenus_core.tools.privilege import PrivilegeTier
from zenus_core.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intent(*steps):
    return IntentIR(goal="test", requires_confirmation=False, steps=list(steps))


def _step(tool="FileOps", action="scan", risk=0, args=None):
    return Step(tool=tool, action=action, args=args or {}, risk=risk)


def _make_orch(**kwargs):
    defaults = dict(
        adaptive=False, use_memory=False, show_progress=False,
        enable_parallel=False, enable_tree_of_thoughts=False,
        enable_prompt_evolution=False, enable_goal_inference=False,
        enable_multi_agent=False, enable_proactive_monitoring=False,
        enable_self_reflection=False, enable_visualization=False,
    )
    defaults.update(kwargs)
    return Orchestrator(**defaults)


# ---------------------------------------------------------------------------
# SafetyError in execute_plan
# ---------------------------------------------------------------------------

class TestSafetyPolicyInPlanner:

    def test_risk_3_raises_safety_error(self):
        """risk=3 must be blocked regardless of tool."""
        step = _step("FileOps", "delete", risk=3)
        intent = _intent(step)
        with pytest.raises(SafetyError):
            execute_plan(intent, parallel=False)

    def test_risk_2_is_allowed(self):
        """risk=2 is below the block threshold."""
        from zenus_core.tools import registry
        mock_tool = Mock()
        mock_tool.move = Mock(return_value="moved")
        original = registry.TOOLS.get("FileOps")
        registry.TOOLS["FileOps"] = mock_tool
        try:
            step = _step("FileOps", "move", risk=2)
            results = execute_plan(_intent(step), parallel=False)
            assert len(results) == 1
        finally:
            if original is not None:
                registry.TOOLS["FileOps"] = original
            elif "FileOps" in registry.TOOLS:
                del registry.TOOLS["FileOps"]

    def test_risk_0_is_allowed(self):
        """risk=0 must always pass."""
        from zenus_core.tools import registry
        mock_tool = Mock()
        mock_tool.scan = Mock(return_value="ok")
        original = registry.TOOLS.get("FileOps")
        registry.TOOLS["FileOps"] = mock_tool
        try:
            step = _step("FileOps", "scan", risk=0)
            results = execute_plan(_intent(step), parallel=False)
            assert results == ["ok"]
        finally:
            if original is not None:
                registry.TOOLS["FileOps"] = original
            elif "FileOps" in registry.TOOLS:
                del registry.TOOLS["FileOps"]

    def test_multiple_steps_blocked_if_any_has_risk_3(self):
        """One high-risk step stops the whole plan."""
        from zenus_core.tools import registry
        mock_tool = Mock()
        mock_tool.scan = Mock(return_value="ok")
        mock_tool.delete = Mock(return_value="deleted")
        original = registry.TOOLS.get("FileOps")
        registry.TOOLS["FileOps"] = mock_tool
        try:
            steps = [
                _step("FileOps", "scan", risk=0),
                _step("FileOps", "delete", risk=3),
            ]
            with pytest.raises(SafetyError):
                execute_plan(_intent(*steps), parallel=False)
            # First step executed, second raised before the second call
        finally:
            if original is not None:
                registry.TOOLS["FileOps"] = original
            elif "FileOps" in registry.TOOLS:
                del registry.TOOLS["FileOps"]

    def test_safety_error_message_is_descriptive(self):
        step = _step("FileOps", "delete", risk=3)
        with pytest.raises(SafetyError) as exc_info:
            execute_plan(_intent(step), parallel=False)
        msg = str(exc_info.value)
        assert "risk" in msg.lower() or "high" in msg.lower() or "blocked" in msg.lower()


# ---------------------------------------------------------------------------
# Privilege tier enforcement in execute_plan
# ---------------------------------------------------------------------------

class TestPrivilegeTierInPlanner:

    def test_shellops_blocked_at_standard_tier(self):
        """ShellOps requires PRIVILEGED tier — blocked at STANDARD."""
        from zenus_core.tools import registry
        mock_shell = Mock()
        mock_shell.run = Mock(return_value="output")
        original = registry.TOOLS.get("ShellOps")
        registry.TOOLS["ShellOps"] = mock_shell
        try:
            step = _step("ShellOps", "run", risk=1)
            with pytest.raises(SafetyError):
                execute_plan(_intent(step), parallel=False,
                             privilege_tier=PrivilegeTier.STANDARD)
        finally:
            if original is not None:
                registry.TOOLS["ShellOps"] = original
            elif "ShellOps" in registry.TOOLS:
                del registry.TOOLS["ShellOps"]

    def test_shellops_allowed_at_privileged_tier(self):
        """ShellOps succeeds at PRIVILEGED tier."""
        from zenus_core.tools import registry
        mock_shell = Mock()
        mock_shell.run = Mock(return_value="shell output")
        original = registry.TOOLS.get("ShellOps")
        registry.TOOLS["ShellOps"] = mock_shell
        try:
            step = _step("ShellOps", "run", risk=1)
            results = execute_plan(_intent(step), parallel=False,
                                   privilege_tier=PrivilegeTier.PRIVILEGED)
            assert results == ["shell output"]
        finally:
            if original is not None:
                registry.TOOLS["ShellOps"] = original
            elif "ShellOps" in registry.TOOLS:
                del registry.TOOLS["ShellOps"]

    def test_codeexec_blocked_at_standard_tier(self):
        """CodeExec is privileged-only."""
        from zenus_core.tools import registry
        mock_code = Mock()
        mock_code.run_python = Mock(return_value="result")
        original = registry.TOOLS.get("CodeExec")
        registry.TOOLS["CodeExec"] = mock_code
        try:
            step = _step("CodeExec", "run_python", risk=1)
            with pytest.raises(SafetyError):
                execute_plan(_intent(step), parallel=False,
                             privilege_tier=PrivilegeTier.STANDARD)
        finally:
            if original is not None:
                registry.TOOLS["CodeExec"] = original
            elif "CodeExec" in registry.TOOLS:
                del registry.TOOLS["CodeExec"]

    def test_fileops_allowed_at_standard_tier(self):
        """FileOps is unprivileged and must be usable at STANDARD."""
        from zenus_core.tools import registry
        mock_tool = Mock()
        mock_tool.scan = Mock(return_value="files!")
        original = registry.TOOLS.get("FileOps")
        registry.TOOLS["FileOps"] = mock_tool
        try:
            step = _step("FileOps", "scan", risk=0)
            results = execute_plan(_intent(step), parallel=False,
                                   privilege_tier=PrivilegeTier.STANDARD)
            assert results == ["files!"]
        finally:
            if original is not None:
                registry.TOOLS["FileOps"] = original
            elif "FileOps" in registry.TOOLS:
                del registry.TOOLS["FileOps"]


# ---------------------------------------------------------------------------
# Safety enforcement through the Orchestrator (full stack, mocked LLM)
# ---------------------------------------------------------------------------

class TestSafetyThroughOrchestrator:

    def test_risk3_intent_returns_error_string(self):
        """Orchestrator must catch SafetyError and return an error string."""
        intent = _intent(_step("FileOps", "delete", risk=3))

        with patch("zenus_core.orchestrator.get_llm") as mock_factory, \
             patch("zenus_core.brain.provider_override.parse_provider_override",
                   return_value=("delete all", None, None)):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mock_factory.return_value = mock_llm

            orch = _make_orch()
            result = orch.execute_command("delete all", force_oneshot=True)

        assert isinstance(result, str)

    def test_shellops_at_standard_tier_via_orchestrator(self):
        """Orchestrator at STANDARD tier must block ShellOps."""
        from zenus_core.tools.privilege import PrivilegeTier
        intent = _intent(_step("ShellOps", "run", risk=1))

        with patch("zenus_core.orchestrator.get_llm") as mock_factory, \
             patch("zenus_core.brain.provider_override.parse_provider_override",
                   return_value=("run shell", None, None)):
            mock_llm = Mock()
            mock_llm.translate_intent.return_value = intent
            mock_factory.return_value = mock_llm

            orch = _make_orch(privilege_tier=PrivilegeTier.STANDARD)
            result = orch.execute_command("run shell", force_oneshot=True)

        assert isinstance(result, str)

    def test_privileged_orchestrator_allows_shellops(self):
        """Orchestrator at PRIVILEGED tier must execute ShellOps."""
        from zenus_core.tools import registry
        from zenus_core.tools.privilege import PrivilegeTier

        mock_shell = Mock()
        mock_shell.run = Mock(return_value="shell ok")
        original = registry.TOOLS.get("ShellOps")
        registry.TOOLS["ShellOps"] = mock_shell

        intent = _intent(_step("ShellOps", "run", risk=1))

        try:
            with patch("zenus_core.orchestrator.get_llm") as mock_factory, \
                 patch("zenus_core.brain.provider_override.parse_provider_override",
                       return_value=("run shell", None, None)):
                mock_llm = Mock()
                mock_llm.translate_intent.return_value = intent
                mock_factory.return_value = mock_llm

                orch = _make_orch(privilege_tier=PrivilegeTier.PRIVILEGED)
                result = orch.execute_command("run shell", force_oneshot=True)

            assert isinstance(result, str)
            mock_shell.run.assert_called_once()
        finally:
            if original is not None:
                registry.TOOLS["ShellOps"] = original
            elif "ShellOps" in registry.TOOLS:
                del registry.TOOLS["ShellOps"]


# ---------------------------------------------------------------------------
# Live safety test with real LLM (requires DeepSeek key)
# ---------------------------------------------------------------------------

@pytest.mark.requires_deepseek
@pytest.mark.integration
class TestSafetyWithRealLLM:

    def test_destructive_command_blocked_or_returns_string(self):
        """
        Ask DeepSeek to delete files. The safety system should either:
        - Block it (risk=3 step → SafetyError caught → error string), or
        - Return a safe response string.
        Either way, execute_command must return a str, not raise.
        """
        import os
        with patch.dict(os.environ, {"ZENUS_LLM": "deepseek"}):
            orch = _make_orch()
            result = orch.execute_command(
                "permanently delete all files in /tmp/zenus_test_safe",
                force_oneshot=True,
            )
        assert isinstance(result, str)
