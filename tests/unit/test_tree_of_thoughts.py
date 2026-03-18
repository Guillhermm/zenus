"""
Tests for TreeOfThoughts - solution path generation, scoring, and selection
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from zenus_core.brain.llm.schemas import IntentIR, Step
from zenus_core.brain.tree_of_thoughts import (
    TreeOfThoughts,
    ThoughtTree,
    SolutionPath,
    PathQuality,
    get_tree_of_thoughts,
)


def make_step(**kwargs) -> Step:
    """Build a minimal Step."""
    defaults = dict(tool="FileOps", action="scan", args={}, risk=0)
    defaults.update(kwargs)
    return Step(**defaults)


def make_intent(goal="Execute task") -> IntentIR:
    """Build a minimal IntentIR."""
    return IntentIR(
        goal=goal,
        requires_confirmation=False,
        steps=[make_step()],
    )


def make_paths_response(paths=None) -> str:
    """Build a JSON string that looks like an LLM paths response."""
    if paths is None:
        paths = [
            {
                "description": "Quick approach",
                "steps": [{"action": "file.read", "args": {"path": "/etc"}, "goal": "read"}],
                "confidence": 0.85,
                "pros": ["Fast", "Reliable"],
                "cons": ["Less flexible"],
                "estimated_steps": 2,
                "estimated_time": "fast",
                "risk_level": "low",
                "reasoning": "Uses proven approach",
            },
            {
                "description": "Thorough approach",
                "steps": [{"action": "file.scan", "args": {}, "goal": "scan"}],
                "confidence": 0.70,
                "pros": ["Comprehensive"],
                "cons": ["Slower", "More steps"],
                "estimated_steps": 5,
                "estimated_time": "slow",
                "risk_level": "medium",
                "reasoning": "Full scan for completeness",
            },
            {
                "description": "Minimal approach",
                "steps": [{"action": "noop", "args": {}, "goal": "noop"}],
                "confidence": 0.60,
                "pros": ["Simple"],
                "cons": ["May miss edge cases"],
                "estimated_steps": 1,
                "estimated_time": "fast",
                "risk_level": "low",
                "reasoning": "Do the minimum necessary",
            },
        ]
    return json.dumps({"paths": paths})


class TestPathQualityDetermination:
    """Test _determine_quality thresholds"""

    def setup_method(self):
        """Instantiate TreeOfThoughts with mocks."""
        self.tot = TreeOfThoughts(Mock(), Mock())

    def test_confidence_above_90_is_excellent(self):
        """Confidence >= 0.9 maps to EXCELLENT"""
        assert self.tot._determine_quality(0.95) == PathQuality.EXCELLENT

    def test_confidence_exactly_90_is_excellent(self):
        """Confidence == 0.9 maps to EXCELLENT"""
        assert self.tot._determine_quality(0.9) == PathQuality.EXCELLENT

    def test_confidence_70_to_89_is_good(self):
        """Confidence in [0.7, 0.9) maps to GOOD"""
        assert self.tot._determine_quality(0.75) == PathQuality.GOOD
        assert self.tot._determine_quality(0.7) == PathQuality.GOOD

    def test_confidence_50_to_69_is_acceptable(self):
        """Confidence in [0.5, 0.7) maps to ACCEPTABLE"""
        assert self.tot._determine_quality(0.6) == PathQuality.ACCEPTABLE
        assert self.tot._determine_quality(0.5) == PathQuality.ACCEPTABLE

    def test_confidence_below_50_is_risky(self):
        """Confidence < 0.5 maps to RISKY"""
        assert self.tot._determine_quality(0.3) == PathQuality.RISKY
        assert self.tot._determine_quality(0.0) == PathQuality.RISKY


class TestPathScoring:
    """Test _calculate_path_score composite scoring"""

    def setup_method(self):
        """Instantiate TreeOfThoughts."""
        self.tot = TreeOfThoughts(Mock(), Mock())

    def _make_path(self, confidence=0.8, risk="low", time="fast", pros=None, cons=None) -> SolutionPath:
        return SolutionPath(
            path_id=1,
            description="Test path",
            intent=make_intent(),
            confidence=confidence,
            pros=pros or ["A", "B", "C"],
            cons=cons or ["X"],
            estimated_steps=3,
            estimated_time=time,
            risk_level=risk,
            quality=PathQuality.GOOD,
            reasoning="Test",
        )

    def test_high_confidence_increases_score(self):
        """Higher confidence yields higher composite score"""
        high = self._make_path(confidence=0.9)
        low = self._make_path(confidence=0.5)
        assert self.tot._calculate_path_score(high) > self.tot._calculate_path_score(low)

    def test_low_risk_increases_score(self):
        """Low risk yields higher composite score than high risk"""
        low_risk = self._make_path(risk="low")
        high_risk = self._make_path(risk="high")
        assert self.tot._calculate_path_score(low_risk) > self.tot._calculate_path_score(high_risk)

    def test_fast_time_increases_score(self):
        """Fast execution time yields higher score than slow"""
        fast = self._make_path(time="fast")
        slow = self._make_path(time="slow")
        assert self.tot._calculate_path_score(fast) > self.tot._calculate_path_score(slow)

    def test_more_pros_increases_score(self):
        """More pros relative to cons yields higher score"""
        many_pros = self._make_path(pros=["A", "B", "C", "D"], cons=["X"])
        few_pros = self._make_path(pros=["A"], cons=["X", "Y", "Z"])
        assert self.tot._calculate_path_score(many_pros) > self.tot._calculate_path_score(few_pros)

    def test_score_within_valid_range(self):
        """Composite score is always in [0.0, 1.0]"""
        path = self._make_path()
        score = self.tot._calculate_path_score(path)
        assert 0.0 <= score <= 1.0


class TestPathSelection:
    """Test _select_best_path selection logic"""

    def setup_method(self):
        """Instantiate TreeOfThoughts."""
        self.tot = TreeOfThoughts(Mock(), Mock())

    def _make_path(self, path_id, confidence=0.8, risk="low", time="fast") -> SolutionPath:
        return SolutionPath(
            path_id=path_id,
            description=f"Path {path_id}",
            intent=make_intent(),
            confidence=confidence,
            pros=["pro"],
            cons=["con"],
            estimated_steps=2,
            estimated_time=time,
            risk_level=risk,
            quality=PathQuality.GOOD,
            reasoning="reason",
        )

    def test_selects_highest_scoring_path(self):
        """Best scoring path is selected from alternatives"""
        paths = [
            self._make_path(1, confidence=0.6, risk="high", time="slow"),
            self._make_path(2, confidence=0.9, risk="low", time="fast"),
            self._make_path(3, confidence=0.7, risk="medium", time="medium"),
        ]
        best, _ = self.tot._select_best_path(paths, "do something")
        assert best.path_id == 2

    def test_single_path_is_returned_unchanged(self):
        """When only one path exists it is returned directly"""
        path = self._make_path(1)
        best, reasoning = self.tot._select_best_path([path], "cmd")
        assert best is path
        assert "only one" in reasoning.lower()

    def test_returns_selection_reasoning_string(self):
        """_select_best_path always returns a non-empty reasoning string"""
        paths = [self._make_path(1), self._make_path(2)]
        _, reasoning = self.tot._select_best_path(paths, "cmd")
        assert isinstance(reasoning, str)
        assert len(reasoning) > 0

    def test_large_margin_uses_clearly_wording(self):
        """Large score gap produces 'clearly' in reasoning"""
        best = self._make_path(1, confidence=0.95, risk="low", time="fast")
        worst = self._make_path(2, confidence=0.1, risk="high", time="slow")
        _, reasoning = self.tot._select_best_path([best, worst], "cmd")
        assert "clearly" in reasoning

    def test_selection_reasoning_mentions_path_id(self):
        """Selection reasoning references the chosen path id"""
        paths = [self._make_path(1, confidence=0.9), self._make_path(2, confidence=0.5)]
        _, reasoning = self.tot._select_best_path(paths, "cmd")
        assert "1" in reasoning


class TestGeneratePaths:
    """Test _generate_paths with mocked LLM.

    Note: _parse_intent_from_path uses Step fields (goal, expected_output) and IntentIR
    fields (explanation, expected_result) that do not exist in the current schema.
    This means the JSON parsing path always raises, triggering the fallback branch.
    These tests verify the fallback behaviour and prompt construction.
    """

    def setup_method(self):
        """Instantiate TreeOfThoughts with mocked LLM."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.tot = TreeOfThoughts(self.mock_llm, self.mock_logger)

    def test_returns_list_of_solution_paths(self):
        """_generate_paths always returns a list of SolutionPath objects"""
        self.mock_llm.generate.return_value = make_paths_response()
        self.mock_llm.translate_intent.return_value = make_intent()
        paths = self.tot._generate_paths("do something", "", 3)
        assert isinstance(paths, list)
        assert all(isinstance(p, SolutionPath) for p in paths)

    def test_fallback_path_returned_when_parse_fails(self):
        """Fallback path is returned because _parse_intent_from_path raises on schema mismatch"""
        self.mock_llm.generate.return_value = make_paths_response()
        fallback_intent = make_intent()
        self.mock_llm.translate_intent.return_value = fallback_intent
        paths = self.tot._generate_paths("cmd", "", 3)
        assert len(paths) == 1
        assert paths[0].path_id == 1
        assert "fallback" in paths[0].description.lower()

    def test_fallback_on_llm_generate_failure(self):
        """Returns single fallback path when LLM.generate raises"""
        self.mock_llm.generate.side_effect = RuntimeError("LLM down")
        fallback_intent = make_intent()
        self.mock_llm.translate_intent.return_value = fallback_intent
        paths = self.tot._generate_paths("cmd", "", 3)
        assert len(paths) == 1
        assert paths[0].path_id == 1
        assert "fallback" in paths[0].description.lower()

    def test_fallback_logs_error(self):
        """Error is logged when path generation falls back"""
        self.mock_llm.generate.return_value = make_paths_response()
        self.mock_llm.translate_intent.return_value = make_intent()
        self.tot._generate_paths("cmd", "", 3)
        self.mock_logger.log_error.assert_called_once()

    def test_fallback_confidence_is_0_7(self):
        """Fallback path uses confidence=0.7"""
        self.mock_llm.generate.return_value = make_paths_response()
        self.mock_llm.translate_intent.return_value = make_intent()
        paths = self.tot._generate_paths("cmd", "", 3)
        assert paths[0].confidence == pytest.approx(0.7)

    def test_fallback_quality_is_good(self):
        """Fallback path has PathQuality.GOOD (confidence=0.7)"""
        self.mock_llm.generate.return_value = make_paths_response()
        self.mock_llm.translate_intent.return_value = make_intent()
        paths = self.tot._generate_paths("cmd", "", 3)
        assert paths[0].quality == PathQuality.GOOD

    def test_prompt_contains_user_input(self):
        """LLM generate is called with prompt containing user input"""
        self.mock_llm.generate.return_value = make_paths_response()
        self.mock_llm.translate_intent.return_value = make_intent()
        self.tot._generate_paths("my custom task", "", 3)
        call_arg = self.mock_llm.generate.call_args[0][0]
        assert "my custom task" in call_arg

    def test_prompt_contains_num_paths(self):
        """Prompt specifies how many paths to generate"""
        self.mock_llm.generate.return_value = make_paths_response()
        self.mock_llm.translate_intent.return_value = make_intent()
        self.tot._generate_paths("cmd", "", 5)
        call_arg = self.mock_llm.generate.call_args[0][0]
        assert "5" in call_arg

    def test_context_included_in_prompt(self):
        """Context string is included in the generation prompt"""
        self.mock_llm.generate.return_value = make_paths_response()
        self.mock_llm.translate_intent.return_value = make_intent()
        self.tot._generate_paths("cmd", "context: production env", 3)
        call_arg = self.mock_llm.generate.call_args[0][0]
        assert "production env" in call_arg


class TestExplore:
    """Test the top-level explore method.

    Because _parse_intent_from_path uses schema fields that don't exist (Step.goal,
    IntentIR.explanation), _generate_paths always falls back to a single fallback path.
    Tests here account for that.
    """

    def setup_method(self):
        """Instantiate TreeOfThoughts with mocked LLM."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.tot = TreeOfThoughts(self.mock_llm, self.mock_logger)
        self.mock_llm.generate.return_value = make_paths_response()
        self.mock_llm.translate_intent.return_value = make_intent()

    def test_explore_returns_thought_tree(self):
        """explore returns a ThoughtTree"""
        tree = self.tot.explore("do something")
        assert isinstance(tree, ThoughtTree)

    def test_thought_tree_has_user_input(self):
        """ThoughtTree stores original user input"""
        tree = self.tot.explore("my special task")
        assert tree.user_input == "my special task"

    def test_thought_tree_has_selected_path(self):
        """ThoughtTree has a selected_path after exploration"""
        tree = self.tot.explore("do something")
        assert tree.selected_path is not None
        assert isinstance(tree.selected_path, SolutionPath)

    def test_thought_tree_paths_list_non_empty(self):
        """ThoughtTree.paths contains at least one path"""
        tree = self.tot.explore("do something")
        assert len(tree.paths) >= 1

    def test_explore_respects_custom_num_paths_in_prompt(self):
        """Passing num_paths=5 causes generate prompt to ask for 5 paths"""
        tree = self.tot.explore("cmd", num_paths=5)
        call_arg = self.mock_llm.generate.call_args[0][0]
        assert "5" in call_arg

    def test_explore_logs_when_learning_enabled(self):
        """log_info is called when enable_learning is True"""
        self.tot.explore("do something")
        self.mock_logger.log_info.assert_called()

    def test_explore_does_not_log_when_learning_disabled(self):
        """log_info is not called when enable_learning is False"""
        self.tot.enable_learning = False
        self.tot.explore("do something")
        self.mock_logger.log_info.assert_not_called()

    def test_explore_records_exploration_time(self):
        """ThoughtTree.exploration_time is a non-negative float"""
        tree = self.tot.explore("do something")
        assert isinstance(tree.exploration_time, float)
        assert tree.exploration_time >= 0.0

    def test_explore_selection_reasoning_non_empty(self):
        """ThoughtTree.selection_reasoning is a non-empty string"""
        tree = self.tot.explore("do something")
        assert isinstance(tree.selection_reasoning, str)
        assert len(tree.selection_reasoning) > 0


class TestThoughtTreeGetBestPath:
    """Test ThoughtTree.get_best_path fallback logic"""

    def _make_path(self, path_id, confidence) -> SolutionPath:
        return SolutionPath(
            path_id=path_id,
            description=f"path {path_id}",
            intent=make_intent(),
            confidence=confidence,
            pros=[],
            cons=[],
            estimated_steps=1,
            estimated_time="fast",
            risk_level="low",
            quality=PathQuality.GOOD,
            reasoning="",
        )

    def test_returns_selected_path_when_set(self):
        """get_best_path returns selected_path when it is set"""
        paths = [self._make_path(1, 0.5), self._make_path(2, 0.9)]
        selected = paths[0]
        tree = ThoughtTree(
            user_input="cmd",
            paths=paths,
            selected_path=selected,
            selection_reasoning="chosen",
            exploration_time=0.1,
        )
        assert tree.get_best_path() is selected

    def test_returns_highest_confidence_when_no_selected(self):
        """get_best_path falls back to max confidence when selected_path is None"""
        paths = [self._make_path(1, 0.5), self._make_path(2, 0.9), self._make_path(3, 0.7)]
        tree = ThoughtTree(
            user_input="cmd",
            paths=paths,
            selected_path=None,
            selection_reasoning="",
            exploration_time=0.1,
        )
        best = tree.get_best_path()
        assert best.path_id == 2


class TestParseIntentFromPath:
    """Test _parse_intent_from_path (note: uses schema fields not in current Step/IntentIR)"""

    def setup_method(self):
        """Instantiate TreeOfThoughts."""
        self.tot = TreeOfThoughts(Mock(), Mock())

    def test_raises_on_invalid_step_fields(self):
        """_parse_intent_from_path raises because Step schema does not accept goal/expected_output"""
        # This documents the known mismatch between tree_of_thoughts.py and the Step schema.
        # The Step schema requires: tool, action, args, risk — not goal/expected_output.
        # _parse_intent_from_path will raise a pydantic ValidationError.
        from pydantic import ValidationError
        path_dict = {
            "description": "Quick approach",
            "steps": [{"action": "file.read", "args": {"path": "/etc"}, "goal": "read"}],
            "reasoning": "fast",
        }
        with pytest.raises((ValidationError, TypeError)):
            self.tot._parse_intent_from_path(path_dict)

    def test_empty_steps_raises_on_invalid_intent_fields(self):
        """_parse_intent_from_path also fails on IntentIR(explanation=...) which is not in schema"""
        from pydantic import ValidationError
        path_dict = {"description": "No-op", "steps": [], "reasoning": ""}
        with pytest.raises((ValidationError, TypeError)):
            self.tot._parse_intent_from_path(path_dict)


class TestSolutionPathToDict:
    """Test SolutionPath.to_dict serialization"""

    def test_quality_is_serialized_as_string(self):
        """SolutionPath.to_dict encodes quality as its string value"""
        path = SolutionPath(
            path_id=1,
            description="Test",
            intent=make_intent(),
            confidence=0.8,
            pros=["A"],
            cons=["B"],
            estimated_steps=2,
            estimated_time="fast",
            risk_level="low",
            quality=PathQuality.GOOD,
            reasoning="test",
        )
        d = path.to_dict()
        assert d["quality"] == "good"
        assert isinstance(d["intent"], dict)


class TestGetTreeOfThoughts:
    """Test singleton factory"""

    def test_returns_instance(self):
        """get_tree_of_thoughts returns a TreeOfThoughts"""
        import zenus_core.brain.tree_of_thoughts as module
        original = module._tot_instance
        module._tot_instance = None
        try:
            instance = get_tree_of_thoughts(Mock(), Mock())
            assert isinstance(instance, TreeOfThoughts)
        finally:
            module._tot_instance = original

    def test_returns_same_singleton(self):
        """get_tree_of_thoughts returns same instance on repeat calls"""
        import zenus_core.brain.tree_of_thoughts as module
        original = module._tot_instance
        module._tot_instance = None
        try:
            a = get_tree_of_thoughts(Mock(), Mock())
            b = get_tree_of_thoughts(Mock(), Mock())
            assert a is b
        finally:
            module._tot_instance = original
