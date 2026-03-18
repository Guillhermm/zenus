"""
Tests for SelfReflection - plan critique, confidence levels, critical issue detection
"""

import json
import pytest
from unittest.mock import Mock, patch

from zenus_core.brain.llm.schemas import IntentIR, Step
from zenus_core.brain.self_reflection import (
    SelfReflection,
    ConfidenceLevel,
    ReflectionIssue,
    StepReflection,
    PlanReflection,
    get_self_reflection,
)


def make_intent(goal="Test goal", steps=None, requires_confirmation=False) -> IntentIR:
    """Build a minimal IntentIR for testing."""
    if steps is None:
        steps = [Step(tool="FileOps", action="scan", args={"path": "/tmp"}, risk=0)]
    return IntentIR(goal=goal, requires_confirmation=requires_confirmation, steps=steps)


def make_reflection_response(
    overall_confidence=0.85,
    step_reflections=None,
    critical_issues=None,
    should_ask_user=False,
    questions=None,
    improvements=None,
    risk="Low risk",
    reasoning="Plan looks solid",
) -> str:
    """Produce JSON string that mirrors the LLM reflection response format."""
    if step_reflections is None:
        step_reflections = [
            {
                "step_index": 0,
                "confidence": overall_confidence,
                "issues": [],
                "assumptions": ["Path exists"],
                "risks": [],
                "alternatives": [],
                "prerequisites": [],
                "reasoning": "Straightforward step",
            }
        ]
    return json.dumps(
        {
            "overall_confidence": overall_confidence,
            "step_reflections": step_reflections,
            "critical_issues": critical_issues or [],
            "should_ask_user": should_ask_user,
            "questions_for_user": questions or [],
            "suggested_improvements": improvements or [],
            "risk_assessment": risk,
            "reasoning": reasoning,
        }
    )


class TestConfidenceLevelMapping:
    """Test _score_to_level thresholds"""

    def setup_method(self):
        """Instantiate SelfReflection with mocks."""
        self.sr = SelfReflection(Mock(), Mock())

    def test_score_above_90_is_very_high(self):
        """Score >= 0.9 maps to VERY_HIGH"""
        assert self.sr._score_to_level(0.95) == ConfidenceLevel.VERY_HIGH

    def test_score_exactly_90_is_very_high(self):
        """Score == 0.9 maps to VERY_HIGH"""
        assert self.sr._score_to_level(0.9) == ConfidenceLevel.VERY_HIGH

    def test_score_70_to_89_is_high(self):
        """Score in [0.7, 0.9) maps to HIGH"""
        assert self.sr._score_to_level(0.75) == ConfidenceLevel.HIGH
        assert self.sr._score_to_level(0.7) == ConfidenceLevel.HIGH

    def test_score_50_to_69_is_medium(self):
        """Score in [0.5, 0.7) maps to MEDIUM"""
        assert self.sr._score_to_level(0.6) == ConfidenceLevel.MEDIUM
        assert self.sr._score_to_level(0.5) == ConfidenceLevel.MEDIUM

    def test_score_30_to_49_is_low(self):
        """Score in [0.3, 0.5) maps to LOW"""
        assert self.sr._score_to_level(0.4) == ConfidenceLevel.LOW
        assert self.sr._score_to_level(0.3) == ConfidenceLevel.LOW

    def test_score_below_30_is_very_low(self):
        """Score < 0.3 maps to VERY_LOW"""
        assert self.sr._score_to_level(0.1) == ConfidenceLevel.VERY_LOW
        assert self.sr._score_to_level(0.0) == ConfidenceLevel.VERY_LOW


class TestReflectOnPlan:
    """Test reflect_on_plan with mocked LLM calls"""

    def setup_method(self):
        """Instantiate SelfReflection with mocked LLM."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.sr = SelfReflection(self.mock_llm, self.mock_logger)

    def _set_llm_response(self, response_json: str):
        self.mock_llm.generate.return_value = response_json

    def test_returns_plan_reflection_instance(self):
        """reflect_on_plan returns a PlanReflection"""
        self._set_llm_response(make_reflection_response())
        intent = make_intent()
        result = self.sr.reflect_on_plan("scan /tmp", intent)
        assert isinstance(result, PlanReflection)

    def test_high_confidence_plan(self):
        """High-confidence LLM response produces VERY_HIGH or HIGH level"""
        self._set_llm_response(make_reflection_response(overall_confidence=0.92))
        result = self.sr.reflect_on_plan("scan /tmp", make_intent())
        assert result.overall_confidence in (ConfidenceLevel.VERY_HIGH, ConfidenceLevel.HIGH)

    def test_low_confidence_forces_ask_user(self):
        """Confidence below ask_user_threshold forces should_ask_user=True"""
        self._set_llm_response(
            make_reflection_response(overall_confidence=0.35, should_ask_user=False)
        )
        result = self.sr.reflect_on_plan("scary command", make_intent())
        assert result.should_ask_user is True

    def test_critical_issues_are_stored(self):
        """Critical issues from LLM response appear in reflection.critical_issues"""
        issues = [{"type": "risky_operation", "description": "Deletes without backup", "severity": "high"}]
        self._set_llm_response(make_reflection_response(critical_issues=issues))
        result = self.sr.reflect_on_plan("rm -rf /", make_intent())
        assert len(result.critical_issues) == 1
        assert result.critical_issues[0]["description"] == "Deletes without backup"

    def test_questions_for_user_propagated(self):
        """Questions from LLM response are stored in reflection"""
        self._set_llm_response(
            make_reflection_response(
                should_ask_user=True,
                questions=["Which environment?", "Do you have a backup?"],
            )
        )
        result = self.sr.reflect_on_plan("deploy something", make_intent())
        assert "Which environment?" in result.questions_for_user

    def test_suggested_improvements_propagated(self):
        """Improvement suggestions from LLM response are stored"""
        self._set_llm_response(
            make_reflection_response(improvements=["Add existence check", "Validate permissions"])
        )
        result = self.sr.reflect_on_plan("read file", make_intent())
        assert "Add existence check" in result.suggested_improvements

    def test_step_reflection_parsed(self):
        """Step-level reflections are parsed into StepReflection objects"""
        self._set_llm_response(make_reflection_response())
        result = self.sr.reflect_on_plan("scan /tmp", make_intent())
        assert len(result.step_reflections) == 1
        assert isinstance(result.step_reflections[0], StepReflection)

    def test_step_confidence_level_assigned(self):
        """Each StepReflection has a ConfidenceLevel assigned"""
        self._set_llm_response(make_reflection_response(overall_confidence=0.8))
        result = self.sr.reflect_on_plan("scan /tmp", make_intent())
        assert isinstance(result.step_reflections[0].confidence, ConfidenceLevel)

    def test_logger_called_on_success(self):
        """log_info is called once when reflection succeeds"""
        self._set_llm_response(make_reflection_response())
        self.sr.reflect_on_plan("scan /tmp", make_intent())
        self.mock_logger.log_info.assert_called_once()

    def test_llm_called_with_prompt(self):
        """LLM generate is invoked with the reflection prompt"""
        self._set_llm_response(make_reflection_response())
        self.sr.reflect_on_plan("scan /tmp", make_intent())
        self.mock_llm.generate.assert_called_once()
        call_args = self.mock_llm.generate.call_args
        prompt_arg = call_args[0][0]
        assert "scan /tmp" in prompt_arg

    def test_context_included_in_prompt(self):
        """Additional context dict is serialized into the prompt"""
        self._set_llm_response(make_reflection_response())
        ctx = {"env": "production", "user": "admin"}
        self.sr.reflect_on_plan("deploy", make_intent(), context=ctx)
        prompt_arg = self.mock_llm.generate.call_args[0][0]
        assert "production" in prompt_arg

    def test_returns_fallback_on_llm_json_error(self):
        """Fallback reflection is returned when LLM output is not valid JSON"""
        self.mock_llm.generate.return_value = "not json at all"
        result = self.sr.reflect_on_plan("scan /tmp", make_intent())
        assert isinstance(result, PlanReflection)
        assert result.overall_confidence == ConfidenceLevel.MEDIUM

    def test_fallback_logs_error(self):
        """log_error is called when LLM fails"""
        self.mock_llm.generate.side_effect = RuntimeError("timeout")
        self.sr.reflect_on_plan("scan /tmp", make_intent())
        self.mock_logger.log_error.assert_called_once()

    def test_fallback_has_one_step_reflection_per_intent_step(self):
        """Fallback reflection creates one StepReflection per step in intent"""
        self.mock_llm.generate.side_effect = RuntimeError("timeout")
        steps = [
            Step(tool="FileOps", action="scan", args={}, risk=0),
            Step(tool="FileOps", action="mkdir", args={}, risk=1),
        ]
        intent = make_intent(steps=steps)
        result = self.sr.reflect_on_plan("multi-step command", intent)
        assert len(result.step_reflections) == 2

    def test_estimated_success_probability_equals_overall_score(self):
        """estimated_success_probability matches overall_confidence_score"""
        self._set_llm_response(make_reflection_response(overall_confidence=0.77))
        result = self.sr.reflect_on_plan("cmd", make_intent())
        assert result.estimated_success_probability == pytest.approx(0.77)


class TestShouldProceed:
    """Test should_proceed decision logic"""

    def setup_method(self):
        """Instantiate SelfReflection."""
        self.sr = SelfReflection(Mock(), Mock())

    def _make_reflection(
        self,
        confidence=ConfidenceLevel.HIGH,
        score=0.8,
        critical_issues=None,
        should_ask=False,
    ) -> PlanReflection:
        return PlanReflection(
            overall_confidence=confidence,
            overall_confidence_score=score,
            step_reflections=[],
            critical_issues=critical_issues or [],
            should_ask_user=should_ask,
            questions_for_user=[],
            suggested_improvements=[],
            risk_assessment="Low",
            estimated_success_probability=score,
            reasoning="ok",
        )

    def test_proceeds_when_all_clear(self):
        """High confidence, no issues, no questions -> proceed"""
        r = self._make_reflection()
        ok, reason = self.sr.should_proceed(r)
        assert ok is True

    def test_does_not_proceed_with_critical_issues(self):
        """Critical issues block execution"""
        r = self._make_reflection(critical_issues=[{"description": "bad"}])
        ok, reason = self.sr.should_proceed(r)
        assert ok is False
        assert "critical" in reason.lower()

    def test_does_not_proceed_with_low_confidence(self):
        """LOW confidence blocks execution"""
        r = self._make_reflection(confidence=ConfidenceLevel.LOW, score=0.35)
        ok, reason = self.sr.should_proceed(r)
        assert ok is False

    def test_does_not_proceed_with_very_low_confidence(self):
        """VERY_LOW confidence blocks execution"""
        r = self._make_reflection(confidence=ConfidenceLevel.VERY_LOW, score=0.2)
        ok, reason = self.sr.should_proceed(r)
        assert ok is False

    def test_does_not_proceed_when_ask_user_set(self):
        """should_ask_user flag blocks execution"""
        r = self._make_reflection(should_ask=True)
        ok, reason = self.sr.should_proceed(r)
        assert ok is False
        assert "user" in reason.lower()

    def test_returns_reason_string_on_proceed(self):
        """should_proceed always returns a non-empty reason string"""
        r = self._make_reflection()
        ok, reason = self.sr.should_proceed(r)
        assert isinstance(reason, str)
        assert len(reason) > 0


class TestFallbackReflection:
    """Test _create_fallback_reflection"""

    def test_fallback_confidence_is_medium(self):
        """Fallback reflection uses MEDIUM confidence"""
        sr = SelfReflection(Mock(), Mock())
        intent = make_intent()
        result = sr._create_fallback_reflection(intent)
        assert result.overall_confidence == ConfidenceLevel.MEDIUM
        assert result.overall_confidence_score == pytest.approx(0.5)

    def test_fallback_does_not_ask_user(self):
        """Fallback reflection does not trigger user questions"""
        sr = SelfReflection(Mock(), Mock())
        result = sr._create_fallback_reflection(make_intent())
        assert result.should_ask_user is False

    def test_fallback_step_descriptions_match_intent(self):
        """Fallback step descriptions correspond to intent step actions"""
        sr = SelfReflection(Mock(), Mock())
        steps = [Step(tool="FileOps", action="scan", args={}, risk=0)]
        intent = make_intent(steps=steps)
        result = sr._create_fallback_reflection(intent)
        assert result.step_reflections[0].step_description == "scan"


class TestReflectionPromptBuilding:
    """Test _build_reflection_prompt content"""

    def setup_method(self):
        """Instantiate SelfReflection."""
        self.sr = SelfReflection(Mock(), Mock())

    def test_prompt_contains_user_input(self):
        """User input appears in the generated prompt"""
        intent = make_intent()
        prompt = self.sr._build_reflection_prompt("list files in /tmp", intent, None)
        assert "list files in /tmp" in prompt

    def test_prompt_contains_goal(self):
        """Intent goal appears in the generated prompt"""
        intent = make_intent(goal="My important goal")
        prompt = self.sr._build_reflection_prompt("cmd", intent, None)
        assert "My important goal" in prompt

    def test_prompt_contains_step_tool_and_action(self):
        """Step tool and action names appear in the generated prompt"""
        intent = make_intent()
        prompt = self.sr._build_reflection_prompt("cmd", intent, None)
        assert "FileOps" in prompt
        assert "scan" in prompt

    def test_prompt_includes_context_when_provided(self):
        """Context dict is serialized into the prompt"""
        intent = make_intent()
        ctx = {"server": "prod-01"}
        prompt = self.sr._build_reflection_prompt("cmd", intent, ctx)
        assert "prod-01" in prompt


class TestGetSelfReflection:
    """Test singleton factory"""

    def test_get_self_reflection_returns_instance(self):
        """get_self_reflection returns a SelfReflection"""
        import zenus_core.brain.self_reflection as module
        original = module._self_reflection_instance
        module._self_reflection_instance = None
        try:
            instance = get_self_reflection(Mock(), Mock())
            assert isinstance(instance, SelfReflection)
        finally:
            module._self_reflection_instance = original

    def test_get_self_reflection_singleton(self):
        """get_self_reflection returns same instance on repeat calls"""
        import zenus_core.brain.self_reflection as module
        original = module._self_reflection_instance
        module._self_reflection_instance = None
        try:
            a = get_self_reflection(Mock(), Mock())
            b = get_self_reflection(Mock(), Mock())
            assert a is b
        finally:
            module._self_reflection_instance = original
