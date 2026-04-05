"""
Unit tests for Plan Mode (PlanModeManager, PlanDecision, gate logic).
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_intent(steps=None, goal="test goal"):
    """Build a minimal IntentIR-like mock."""
    intent = MagicMock()
    intent.goal = goal
    if steps is None:
        step = MagicMock()
        step.tool = "FileOps"
        step.action = "read_file"
        step.risk = 0
        step.args = {"path": "/tmp/test.txt"}
        steps = [step]
    intent.steps = steps
    return intent


class TestPlanModeManager:
    def _fresh_manager(self, enabled=False):
        from zenus_core.brain.plan_mode import PlanModeManager
        mgr = PlanModeManager.__new__(PlanModeManager)
        import threading
        mgr._lock = threading.Lock()
        mgr._enabled = enabled
        return mgr

    def test_default_disabled(self):
        mgr = self._fresh_manager(enabled=False)
        assert mgr.enabled is False

    def test_enable_disable(self):
        mgr = self._fresh_manager()
        mgr.enable()
        assert mgr.enabled is True
        mgr.disable()
        assert mgr.enabled is False

    def test_toggle(self):
        mgr = self._fresh_manager(enabled=False)
        result = mgr.toggle()
        assert result is True
        assert mgr.enabled is True
        result = mgr.toggle()
        assert result is False

    def test_gate_bypassed_when_disabled(self):
        from zenus_core.brain.plan_mode import PlanDecision
        mgr = self._fresh_manager(enabled=False)
        intent = _make_intent()
        result = mgr.gate(intent)
        assert result == PlanDecision.BYPASSED

    def test_gate_approved_on_y_input(self):
        from zenus_core.brain.plan_mode import PlanDecision
        mgr = self._fresh_manager(enabled=True)
        intent = _make_intent()

        with patch("builtins.input", return_value="y"):
            with patch("zenus_core.output.console.console"):
                result = mgr.gate(intent)

        assert result == PlanDecision.APPROVED

    def test_gate_denied_on_n_input(self):
        from zenus_core.brain.plan_mode import PlanDecision
        mgr = self._fresh_manager(enabled=True)
        intent = _make_intent()

        with patch("builtins.input", return_value="n"):
            with patch("zenus_core.output.console.console"):
                result = mgr.gate(intent)

        assert result == PlanDecision.DENIED

    def test_gate_denied_on_keyboard_interrupt(self):
        from zenus_core.brain.plan_mode import PlanDecision
        mgr = self._fresh_manager(enabled=True)
        intent = _make_intent()

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with patch("zenus_core.output.console.console"):
                result = mgr.gate(intent)

        assert result == PlanDecision.DENIED

    def test_auto_approve_low_risk(self):
        from zenus_core.brain.plan_mode import PlanDecision
        mgr = self._fresh_manager(enabled=True)
        intent = _make_intent()  # risk=0 step

        mock_cfg = MagicMock()
        mock_cfg.plan_mode.auto_approve_low_risk = True

        with patch("zenus_core.output.console.console"):
            with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
                result = mgr.gate(intent)

        assert result == PlanDecision.APPROVED

    def test_auto_approve_does_not_apply_to_high_risk(self):
        from zenus_core.brain.plan_mode import PlanDecision
        mgr = self._fresh_manager(enabled=True)

        step = MagicMock()
        step.tool = "FileOps"
        step.action = "delete_file"
        step.risk = 3  # DELETE
        step.args = {}
        intent = _make_intent(steps=[step])

        mock_cfg = MagicMock()
        mock_cfg.plan_mode.auto_approve_low_risk = True

        with patch("builtins.input", return_value="y"):
            with patch("zenus_core.output.console.console"):
                with patch("zenus_core.config.loader.get_config", return_value=mock_cfg):
                    result = mgr.gate(intent)

        assert result == PlanDecision.APPROVED  # user typed y manually

    def test_accepts_multiple_approval_words(self):
        from zenus_core.brain.plan_mode import PlanDecision
        mgr = self._fresh_manager(enabled=True)
        for word in ("yes", "approve", "ok", "go"):
            intent = _make_intent()
            with patch("builtins.input", return_value=word):
                with patch("zenus_core.output.console.console"):
                    assert mgr.gate(intent) == PlanDecision.APPROVED


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_get_plan_mode_manager_singleton():
    import zenus_core.brain.plan_mode as pm
    pm._manager = None  # reset

    from zenus_core.brain.plan_mode import get_plan_mode_manager
    m1 = get_plan_mode_manager()
    m2 = get_plan_mode_manager()
    assert m1 is m2
