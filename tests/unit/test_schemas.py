"""
Tests for core data schemas
"""

import pytest
from pydantic import ValidationError
from zenus_core.brain.llm.schemas import Step, IntentIR


class TestStep:
    """Test Step schema validation"""
    
    def test_valid_step_creation(self):
        """Should create valid step with all fields"""
        step = Step(
            tool="FileOps",
            action="scan",
            args={"path": "/tmp"},
            risk=0
        )
        
        assert step.tool == "FileOps"
        assert step.action == "scan"
        assert step.args == {"path": "/tmp"}
        assert step.risk == 0
    
    def test_step_defaults_empty_args(self):
        """Args should default to empty dict"""
        step = Step(tool="FileOps", action="test", risk=0)
        assert step.args == {}
    
    def test_step_requires_tool(self):
        """Tool field is required"""
        with pytest.raises(ValidationError):
            Step(action="test", risk=0)
    
    def test_step_requires_action(self):
        """Action field is required"""
        with pytest.raises(ValidationError):
            Step(tool="FileOps", risk=0)
    
    def test_step_requires_risk(self):
        """Risk field is required"""
        with pytest.raises(ValidationError):
            Step(tool="FileOps", action="test")
    
    def test_step_validates_risk_range(self):
        """Risk must be between 0 and 3"""
        # Valid risks
        for risk in [0, 1, 2, 3]:
            step = Step(tool="FileOps", action="test", risk=risk)
            assert step.risk == risk
        
        # Invalid risks
        with pytest.raises(ValidationError):
            Step(tool="FileOps", action="test", risk=-1)
        
        with pytest.raises(ValidationError):
            Step(tool="FileOps", action="test", risk=4)


class TestIntentIR:
    """Test IntentIR schema validation"""
    
    def test_valid_intent_creation(self):
        """Should create valid intent with steps"""
        steps = [
            Step(tool="FileOps", action="scan", risk=0)
        ]
        intent = IntentIR(
            goal="List files",
            requires_confirmation=False,
            steps=steps
        )
        
        assert intent.goal == "List files"
        assert intent.requires_confirmation is False
        assert len(intent.steps) == 1
    
    def test_intent_requires_goal(self):
        """Goal field is required"""
        with pytest.raises(ValidationError):
            IntentIR(requires_confirmation=False, steps=[])
    
    def test_intent_requires_confirmation_flag(self):
        """Requires confirmation field is required"""
        with pytest.raises(ValidationError):
            IntentIR(goal="Test", steps=[])
    
    def test_intent_requires_steps(self):
        """Steps field is required"""
        with pytest.raises(ValidationError):
            IntentIR(goal="Test", requires_confirmation=False)
    
    def test_intent_can_have_empty_steps(self):
        """Steps can be empty list"""
        intent = IntentIR(
            goal="No-op",
            requires_confirmation=False,
            steps=[]
        )
        assert intent.steps == []
    
    def test_intent_validates_step_structure(self):
        """Steps must be valid Step objects"""
        with pytest.raises(ValidationError):
            IntentIR(
                goal="Test",
                requires_confirmation=False,
                steps=[{"invalid": "dict"}]
            )

    def test_is_question_defaults_false(self):
        intent = IntentIR(goal="do X", requires_confirmation=False, steps=[])
        assert intent.is_question is False

    def test_action_summary_defaults_none(self):
        intent = IntentIR(goal="do X", requires_confirmation=False, steps=[])
        assert intent.action_summary is None

    def test_search_provider_defaults_none(self):
        intent = IntentIR(goal="do X", requires_confirmation=False, steps=[])
        assert intent.search_provider is None

    def test_search_category_defaults_none(self):
        intent = IntentIR(goal="do X", requires_confirmation=False, steps=[])
        assert intent.search_category is None

    def test_cannot_answer_defaults_false(self):
        intent = IntentIR(goal="do X", requires_confirmation=False, steps=[])
        assert intent.cannot_answer is False

    def test_fallback_response_defaults_none(self):
        intent = IntentIR(goal="do X", requires_confirmation=False, steps=[])
        assert intent.fallback_response is None

    def test_search_provider_web(self):
        intent = IntentIR(
            goal="who won the match",
            requires_confirmation=False,
            steps=[],
            is_question=True,
            search_provider="web",
            search_category="sports",
        )
        assert intent.search_provider == "web"
        assert intent.search_category == "sports"

    def test_search_provider_llm(self):
        intent = IntentIR(
            goal="what is photosynthesis",
            requires_confirmation=False,
            steps=[],
            is_question=True,
            search_provider="llm",
        )
        assert intent.search_provider == "llm"
        assert intent.search_category is None

    def test_search_provider_invalid_rejected(self):
        with pytest.raises(ValidationError):
            IntentIR(
                goal="test",
                requires_confirmation=False,
                steps=[],
                search_provider="google",
            )

    def test_search_category_invalid_rejected(self):
        with pytest.raises(ValidationError):
            IntentIR(
                goal="test",
                requires_confirmation=False,
                steps=[],
                search_category="cooking",
            )

    def test_cannot_answer_with_fallback(self):
        intent = IntentIR(
            goal="what is in private db",
            requires_confirmation=False,
            steps=[],
            cannot_answer=True,
            fallback_response="This question requires access to a private database I cannot reach.",
        )
        assert intent.cannot_answer is True
        assert "private database" in intent.fallback_response

    def test_all_search_categories_valid(self):
        for cat in ("sports", "tech", "academic", "news", "general"):
            intent = IntentIR(
                goal="test",
                requires_confirmation=False,
                steps=[],
                search_provider="web",
                search_category=cat,
            )
            assert intent.search_category == cat

    def test_backward_compatible_without_new_fields(self):
        """Old intents without new fields must still validate."""
        data = {"goal": "list files", "requires_confirmation": False, "steps": []}
        intent = IntentIR.model_validate(data)
        assert intent.search_provider is None
        assert intent.cannot_answer is False
