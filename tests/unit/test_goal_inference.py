"""
Tests for GoalInference - goal type detection and workflow proposal generation
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from zenus_core.brain.goal_inference import (
    GoalInference,
    GoalType,
    GoalPattern,
    ImplicitStep,
    WorkflowSuggestion,
    get_goal_inference,
)


def make_goal_inference(tmp_path: Path) -> GoalInference:
    """Build a GoalInference instance backed by a temp directory."""
    mock_llm = Mock()
    mock_logger = Mock()
    with patch.object(GoalInference, "__init__", wraps=GoalInference.__init__):
        with patch(
            "zenus_core.brain.goal_inference.Path.home", return_value=tmp_path
        ):
            gi = GoalInference.__new__(GoalInference)
            gi.llm = mock_llm
            gi.logger = mock_logger
            gi.storage_dir = tmp_path / ".zenus" / "goals"
            gi.storage_dir.mkdir(parents=True, exist_ok=True)
            gi.patterns_file = gi.storage_dir / "patterns.json"
            gi.patterns = []
            gi._initialize_common_patterns()
    return gi


class TestGoalTypeDetection:
    """Test _detect_goal_type against all keyword groups"""

    def setup_method(self, tmp_path=None):
        """Create GoalInference with mocked deps."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()

    def _make(self, tmp_path):
        return make_goal_inference(tmp_path)

    def test_detects_deploy(self, tmp_path):
        """deploy keyword maps to GoalType.DEPLOY"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("deploy my app to production") == GoalType.DEPLOY

    def test_detects_deploy_via_release(self, tmp_path):
        """release keyword maps to GoalType.DEPLOY"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("release version 2.0") == GoalType.DEPLOY

    def test_detects_develop(self, tmp_path):
        """dev env phrase maps to GoalType.DEVELOP"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("setup dev environment for the project") == GoalType.DEVELOP

    def test_detects_debug(self, tmp_path):
        """debug keyword maps to GoalType.DEBUG"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("debug the login error") == GoalType.DEBUG

    def test_detects_debug_via_fix(self, tmp_path):
        """fix keyword maps to GoalType.DEBUG"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("fix the broken API") == GoalType.DEBUG

    def test_detects_migrate(self, tmp_path):
        """migrate keyword maps to GoalType.MIGRATE"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("migrate the database to postgres") == GoalType.MIGRATE

    def test_detects_backup(self, tmp_path):
        """backup keyword maps to GoalType.BACKUP"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("backup all user data") == GoalType.BACKUP

    def test_detects_monitor(self, tmp_path):
        """monitor keyword maps to GoalType.MONITOR"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("monitor server metrics") == GoalType.MONITOR

    def test_detects_optimize(self, tmp_path):
        """optimize keyword maps to GoalType.OPTIMIZE"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("optimize the slow query") == GoalType.OPTIMIZE

    def test_detects_security(self, tmp_path):
        """secure keyword maps to GoalType.SECURITY"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("secure the web server") == GoalType.SECURITY

    def test_detects_test(self, tmp_path):
        """test keyword maps to GoalType.TEST"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("run tests for the module") == GoalType.TEST

    def test_detects_setup(self, tmp_path):
        """setup keyword maps to GoalType.SETUP"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("setup nginx on the server") == GoalType.SETUP

    def test_detects_cleanup(self, tmp_path):
        """cleanup keyword maps to GoalType.CLEANUP"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("cleanup old docker images") == GoalType.CLEANUP

    def test_returns_unknown_for_unrecognized_input(self, tmp_path):
        """Unrecognized input returns GoalType.UNKNOWN"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("say hello to the world") == GoalType.UNKNOWN

    def test_case_insensitive_detection(self, tmp_path):
        """Goal detection is case-insensitive"""
        gi = self._make(tmp_path)
        assert gi._detect_goal_type("DEPLOY the service") == GoalType.DEPLOY


class TestExplicitStepExtraction:
    """Test _extract_explicit_steps"""

    def test_extracts_known_action_words(self, tmp_path):
        """Extracts recognized action verbs from user input"""
        gi = make_goal_inference(tmp_path)
        steps = gi._extract_explicit_steps("create a directory and install dependencies")
        assert "create" in steps
        assert "install" in steps

    def test_returns_default_when_no_actions_found(self, tmp_path):
        """Falls back to ['execute task'] when no action words present"""
        gi = make_goal_inference(tmp_path)
        steps = gi._extract_explicit_steps("hello world something")
        assert steps == ["execute task"]

    def test_does_not_duplicate_steps(self, tmp_path):
        """Same action word appearing multiple times is only added once"""
        gi = make_goal_inference(tmp_path)
        steps = gi._extract_explicit_steps("build the app and build the image")
        assert steps.count("build") == 1


class TestImplicitStepInsertion:
    """Test _infer_implicit_steps for each goal type"""

    def test_deploy_adds_critical_before_steps(self, tmp_path):
        """DEPLOY goal inserts run-tests and backup before deployment"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("deploy to production", GoalType.DEPLOY, ["deploy"], "")
        actions = [s.action for s in steps]
        assert any("test" in a.lower() for a in actions)
        assert any("backup" in a.lower() for a in actions)

    def test_deploy_adds_health_check_after(self, tmp_path):
        """DEPLOY goal inserts health verification after deployment"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("deploy to production", GoalType.DEPLOY, ["deploy"], "")
        after_steps = [s for s in steps if s.when == "after"]
        assert len(after_steps) >= 1

    def test_develop_checks_system_requirements(self, tmp_path):
        """DEVELOP goal adds system requirements check"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("setup dev environment", GoalType.DEVELOP, ["setup"], "")
        assert any("requirements" in s.action.lower() for s in steps)

    def test_migrate_adds_backup_before(self, tmp_path):
        """MIGRATE goal inserts backup as critical before step"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("migrate db to postgres", GoalType.MIGRATE, [], "")
        before_critical = [s for s in steps if s.when == "before" and s.importance == "critical"]
        assert any("backup" in s.action.lower() for s in before_critical)

    def test_migrate_adds_dry_run_before(self, tmp_path):
        """MIGRATE goal inserts dry-run step before migration"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("migrate db to postgres", GoalType.MIGRATE, [], "")
        assert any("dry" in s.action.lower() for s in steps)

    def test_security_adds_audit_before(self, tmp_path):
        """SECURITY goal inserts vulnerability audit before hardening"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("secure the server", GoalType.SECURITY, [], "")
        assert any("audit" in s.action.lower() for s in steps)

    def test_cleanup_adds_preview_and_confirm(self, tmp_path):
        """CLEANUP goal inserts list-preview and confirmation before deletion"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("cleanup old files", GoalType.CLEANUP, [], "")
        before_steps = [s for s in steps if s.when == "before"]
        assert len(before_steps) >= 2

    def test_database_keyword_adds_db_backup(self, tmp_path):
        """Input mentioning 'database' always adds DB backup step"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("update the database schema", GoalType.SETUP, [], "")
        assert any("database" in s.action.lower() or "backup" in s.action.lower() for s in steps)

    def test_delete_keyword_adds_trash_step(self, tmp_path):
        """Input containing 'delete' adds trash-instead-of-delete step"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("delete old logs", GoalType.CLEANUP, [], "")
        assert any("trash" in s.action.lower() for s in steps)

    def test_unknown_goal_returns_empty_or_minimal(self, tmp_path):
        """Unknown goal type returns no goal-specific implicit steps"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("say hello world", GoalType.UNKNOWN, [], "")
        # No goal-type-specific steps, only cross-cutting ones (none here)
        assert isinstance(steps, list)

    def test_implicit_steps_have_valid_importance_levels(self, tmp_path):
        """All implicit steps have importance in critical/recommended/optional"""
        gi = make_goal_inference(tmp_path)
        steps = gi._infer_implicit_steps("deploy to production", GoalType.DEPLOY, [], "")
        valid = {"critical", "recommended", "optional"}
        assert all(s.importance in valid for s in steps)


class TestCompleteWorkflowBuilding:
    """Test _build_complete_workflow ordering logic"""

    def test_critical_before_steps_come_first(self, tmp_path):
        """[SAFETY] prefixed steps appear before explicit steps"""
        gi = make_goal_inference(tmp_path)
        implicit = [
            ImplicitStep("Run tests", "safety", "critical", "before", "safety"),
        ]
        workflow = gi._build_complete_workflow(["deploy"], implicit)
        assert workflow.index("[SAFETY] Run tests") < workflow.index("deploy")

    def test_after_steps_come_last(self, tmp_path):
        """[VERIFY] prefixed steps appear after explicit steps"""
        gi = make_goal_inference(tmp_path)
        implicit = [
            ImplicitStep("Check health", "verify", "critical", "after", "best_practice"),
        ]
        workflow = gi._build_complete_workflow(["deploy"], implicit)
        assert workflow.index("deploy") < workflow.index("[VERIFY] Check health")

    def test_during_steps_are_recommended(self, tmp_path):
        """during steps are labelled [RECOMMENDED]"""
        gi = make_goal_inference(tmp_path)
        implicit = [
            ImplicitStep("Setup git hooks", "hooks", "recommended", "during", "best_practice"),
        ]
        workflow = gi._build_complete_workflow(["configure"], implicit)
        assert "[RECOMMENDED] Setup git hooks" in workflow

    def test_explicit_steps_preserved(self, tmp_path):
        """Explicit user steps appear in the workflow unchanged"""
        gi = make_goal_inference(tmp_path)
        workflow = gi._build_complete_workflow(["build", "test"], [])
        assert "build" in workflow
        assert "test" in workflow


class TestReasoningAndMetadata:
    """Test _generate_reasoning, _estimate_time, _assess_risk, prereqs, post-actions"""

    def test_reasoning_mentions_goal_type(self, tmp_path):
        """Reasoning string includes the detected goal type name"""
        gi = make_goal_inference(tmp_path)
        reasoning = gi._generate_reasoning(GoalType.DEPLOY, [])
        assert "deploy" in reasoning.lower()

    def test_reasoning_mentions_critical_count(self, tmp_path):
        """Reasoning counts critical safety steps added"""
        gi = make_goal_inference(tmp_path)
        critical = ImplicitStep("Run tests", "safety", "critical", "before", "safety")
        reasoning = gi._generate_reasoning(GoalType.DEPLOY, [critical])
        assert "1" in reasoning

    def test_estimate_time_short_workflow(self, tmp_path):
        """Up to 3 steps returns ~1-2 minutes"""
        gi = make_goal_inference(tmp_path)
        assert gi._estimate_time(["a", "b"]) == "~1-2 minutes"

    def test_estimate_time_medium_workflow(self, tmp_path):
        """4-7 steps returns ~5-10 minutes"""
        gi = make_goal_inference(tmp_path)
        assert gi._estimate_time(["a"] * 5) == "~5-10 minutes"

    def test_estimate_time_long_workflow(self, tmp_path):
        """8-12 steps returns ~15-30 minutes"""
        gi = make_goal_inference(tmp_path)
        assert gi._estimate_time(["a"] * 10) == "~15-30 minutes"

    def test_estimate_time_very_long_workflow(self, tmp_path):
        """More than 12 steps returns ~30+ minutes"""
        gi = make_goal_inference(tmp_path)
        assert gi._estimate_time(["a"] * 15) == "~30+ minutes"

    def test_risk_high_when_no_safety_steps(self, tmp_path):
        """High-risk goals without safety steps are rated HIGH"""
        gi = make_goal_inference(tmp_path)
        risk = gi._assess_risk(GoalType.DEPLOY, ["deploy"])
        assert "HIGH" in risk

    def test_risk_medium_with_safety_steps(self, tmp_path):
        """High-risk goals with safety steps drop to MEDIUM"""
        gi = make_goal_inference(tmp_path)
        risk = gi._assess_risk(GoalType.DEPLOY, ["[SAFETY] backup", "deploy"])
        assert "MEDIUM" in risk

    def test_risk_low_for_non_destructive_goals(self, tmp_path):
        """Non-destructive goals get LOW risk even without safety steps"""
        gi = make_goal_inference(tmp_path)
        risk = gi._assess_risk(GoalType.MONITOR, ["watch logs"])
        assert "LOW" in risk

    def test_deploy_prerequisites(self, tmp_path):
        """DEPLOY goal returns list of prerequisites"""
        gi = make_goal_inference(tmp_path)
        prereqs = gi._identify_prerequisites(GoalType.DEPLOY, "deploy app")
        assert len(prereqs) > 0
        assert any("test" in p.lower() for p in prereqs)

    def test_develop_prerequisites(self, tmp_path):
        """DEVELOP goal returns list of prerequisites"""
        gi = make_goal_inference(tmp_path)
        prereqs = gi._identify_prerequisites(GoalType.DEVELOP, "setup dev env")
        assert len(prereqs) > 0

    def test_unknown_goal_has_empty_prerequisites(self, tmp_path):
        """UNKNOWN goal returns empty prerequisites list"""
        gi = make_goal_inference(tmp_path)
        prereqs = gi._identify_prerequisites(GoalType.UNKNOWN, "say hello")
        assert prereqs == []

    def test_deploy_post_actions(self, tmp_path):
        """DEPLOY goal returns post-deployment actions"""
        gi = make_goal_inference(tmp_path)
        post = gi._suggest_post_actions(GoalType.DEPLOY)
        assert len(post) > 0

    def test_security_post_actions(self, tmp_path):
        """SECURITY goal returns post-hardening actions"""
        gi = make_goal_inference(tmp_path)
        post = gi._suggest_post_actions(GoalType.SECURITY)
        assert len(post) > 0

    def test_unknown_goal_returns_empty_post_actions(self, tmp_path):
        """UNKNOWN goal returns empty post actions"""
        gi = make_goal_inference(tmp_path)
        post = gi._suggest_post_actions(GoalType.UNKNOWN)
        assert post == []


class TestInferGoal:
    """Test the top-level infer_goal orchestrator"""

    def test_infer_goal_returns_workflow_suggestion(self, tmp_path):
        """infer_goal returns a WorkflowSuggestion instance"""
        gi = make_goal_inference(tmp_path)
        result = gi.infer_goal("deploy the app to production")
        assert isinstance(result, WorkflowSuggestion)

    def test_infer_goal_detects_correct_type(self, tmp_path):
        """infer_goal correctly sets goal_type in the suggestion"""
        gi = make_goal_inference(tmp_path)
        result = gi.infer_goal("backup all data")
        assert result.goal_type == GoalType.BACKUP

    def test_infer_goal_includes_implicit_steps(self, tmp_path):
        """infer_goal adds implicit steps for high-risk operations"""
        gi = make_goal_inference(tmp_path)
        result = gi.infer_goal("deploy the app to production")
        assert len(result.implicit_steps) > 0

    def test_infer_goal_builds_complete_workflow(self, tmp_path):
        """complete_workflow contains both explicit and implicit step text"""
        gi = make_goal_inference(tmp_path)
        result = gi.infer_goal("deploy the app to production")
        assert len(result.complete_workflow) > 0

    def test_infer_goal_logs_info(self, tmp_path):
        """infer_goal calls logger.log_info"""
        gi = make_goal_inference(tmp_path)
        gi.infer_goal("deploy the app")
        gi.logger.log_info.assert_called_once()

    def test_infer_goal_goal_description_truncated(self, tmp_path):
        """Goal description is truncated to 100 chars with ellipsis"""
        gi = make_goal_inference(tmp_path)
        long_input = "deploy " + "x" * 200
        result = gi.infer_goal(long_input)
        assert result.goal.endswith("...")
        assert len(result.goal) <= 103  # 100 + "..."

    def test_workflow_suggestion_to_dict(self, tmp_path):
        """WorkflowSuggestion.to_dict serializes goal_type as string"""
        gi = make_goal_inference(tmp_path)
        result = gi.infer_goal("deploy the app")
        d = result.to_dict()
        assert isinstance(d["goal_type"], str)
        assert d["goal_type"] == "deploy"


class TestPatternPersistence:
    """Test loading and saving of GoalPattern data"""

    def test_initializes_common_patterns_when_file_absent(self, tmp_path):
        """Fresh instance creates default patterns"""
        gi = make_goal_inference(tmp_path)
        assert len(gi.patterns) >= 2

    def test_save_and_reload_patterns(self, tmp_path):
        """Patterns written to disk are read back on reload"""
        gi = make_goal_inference(tmp_path)
        gi._save_patterns()

        gi2 = GoalInference.__new__(GoalInference)
        gi2.llm = Mock()
        gi2.logger = Mock()
        gi2.storage_dir = gi.storage_dir
        gi2.patterns_file = gi.patterns_file
        gi2.patterns = gi2._load_patterns()

        assert len(gi2.patterns) == len(gi.patterns)

    def test_load_patterns_returns_empty_on_missing_file(self, tmp_path):
        """_load_patterns returns [] when patterns file does not exist"""
        gi = GoalInference.__new__(GoalInference)
        gi.llm = Mock()
        gi.logger = Mock()
        gi.storage_dir = tmp_path / "none"
        gi.storage_dir.mkdir(parents=True)
        gi.patterns_file = gi.storage_dir / "patterns.json"
        assert gi._load_patterns() == []

    def test_load_patterns_handles_corrupt_file(self, tmp_path):
        """_load_patterns returns [] and logs error on corrupt JSON"""
        gi = GoalInference.__new__(GoalInference)
        gi.llm = Mock()
        gi.logger = Mock()
        gi.storage_dir = tmp_path
        gi.patterns_file = tmp_path / "patterns.json"
        gi.patterns_file.write_text("not valid json")
        result = gi._load_patterns()
        assert result == []
        gi.logger.log_error.assert_called_once()


class TestGetGoalInference:
    """Test singleton factory"""

    def test_get_goal_inference_returns_instance(self, tmp_path):
        """get_goal_inference returns a GoalInference"""
        import zenus_core.brain.goal_inference as module
        original = module._goal_inference_instance
        module._goal_inference_instance = None
        try:
            with patch("zenus_core.brain.goal_inference.Path.home", return_value=tmp_path):
                instance = get_goal_inference(Mock(), Mock())
            assert isinstance(instance, GoalInference)
        finally:
            module._goal_inference_instance = original

    def test_get_goal_inference_returns_same_instance(self, tmp_path):
        """get_goal_inference returns same singleton on repeat calls"""
        import zenus_core.brain.goal_inference as module
        original = module._goal_inference_instance
        module._goal_inference_instance = None
        try:
            with patch("zenus_core.brain.goal_inference.Path.home", return_value=tmp_path):
                a = get_goal_inference(Mock(), Mock())
                b = get_goal_inference(Mock(), Mock())
            assert a is b
        finally:
            module._goal_inference_instance = original
