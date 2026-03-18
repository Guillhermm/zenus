"""
Tests for MultiAgentSystem - agent roles, collaboration workflow, result aggregation
"""

import json
import pytest
from unittest.mock import Mock, patch, call

from zenus_core.brain.multi_agent import (
    MultiAgentSystem,
    ResearcherAgent,
    PlannerAgent,
    ExecutorAgent,
    ValidatorAgent,
    Agent,
    AgentRole,
    AgentResult,
    CollaborationSession,
    Message,
    get_multi_agent_system,
)


def make_agent_response(confidence=0.85, reasoning="ok", **extra) -> str:
    """Build a JSON string representing a successful agent LLM response."""
    data = {"confidence": confidence, "reasoning": reasoning}
    data.update(extra)
    return json.dumps(data)


def make_research_response(confidence=0.85) -> str:
    """LLM response for the researcher agent."""
    return json.dumps({
        "analysis": "Problem is X",
        "approaches": [{"name": "A1", "pros": [], "cons": [], "complexity": "low"}],
        "recommended_tools": ["tool1"],
        "challenges": ["c1"],
        "best_practices": ["bp1"],
        "confidence": confidence,
        "reasoning": "Research complete",
    })


def make_plan_response(confidence=0.85) -> str:
    """LLM response for the planner agent."""
    return json.dumps({
        "prerequisites": ["pre1"],
        "steps": [
            {
                "step_num": 1,
                "action": "do thing",
                "command": "echo hello",
                "risk": "low",
                "depends_on": [],
                "validation": "check output",
                "rollback": "undo",
            }
        ],
        "timeline": "5 minutes",
        "risks": [],
        "confidence": confidence,
        "reasoning": "Plan is solid",
    })


def make_validation_response(overall_success=True, confidence=0.9) -> str:
    """LLM response for the validator agent."""
    return json.dumps({
        "overall_success": overall_success,
        "checks": [{"check": "output present", "passed": True, "details": "ok"}],
        "issues": [],
        "recommendations": [],
        "confidence": confidence,
        "reasoning": "All checks passed",
    })


class TestAgentRoles:
    """Test AgentRole enum values"""

    def test_researcher_role_value(self):
        """AgentRole.RESEARCHER has value 'researcher'"""
        assert AgentRole.RESEARCHER.value == "researcher"

    def test_planner_role_value(self):
        """AgentRole.PLANNER has value 'planner'"""
        assert AgentRole.PLANNER.value == "planner"

    def test_executor_role_value(self):
        """AgentRole.EXECUTOR has value 'executor'"""
        assert AgentRole.EXECUTOR.value == "executor"

    def test_validator_role_value(self):
        """AgentRole.VALIDATOR has value 'validator'"""
        assert AgentRole.VALIDATOR.value == "validator"

    def test_coordinator_role_value(self):
        """AgentRole.COORDINATOR has value 'coordinator'"""
        assert AgentRole.COORDINATOR.value == "coordinator"


class TestMessageCreation:
    """Test Agent.send_message inter-agent messaging"""

    def setup_method(self):
        """Create a concrete agent subclass for testing send_message."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.agent = ResearcherAgent(self.mock_llm, self.mock_logger)

    def _make_session(self) -> CollaborationSession:
        return CollaborationSession(
            session_id="abc123",
            task="test task",
            agents_involved=[],
            messages=[],
            results=[],
            final_result=None,
            success=False,
            total_duration=0.0,
        )

    def test_message_appended_to_session(self):
        """send_message appends Message to session.messages"""
        session = self._make_session()
        self.agent.send_message(AgentRole.PLANNER, "request", {"data": "x"}, session)
        assert len(session.messages) == 1

    def test_message_has_correct_from_agent(self):
        """Message.from_agent matches sending agent's role"""
        session = self._make_session()
        msg = self.agent.send_message(AgentRole.PLANNER, "request", {}, session)
        assert msg.from_agent == AgentRole.RESEARCHER

    def test_message_has_correct_to_agent(self):
        """Message.to_agent matches recipient role"""
        session = self._make_session()
        msg = self.agent.send_message(AgentRole.VALIDATOR, "update", {}, session)
        assert msg.to_agent == AgentRole.VALIDATOR

    def test_messages_sent_counter_incremented(self):
        """Agent.messages_sent is incremented per send_message call"""
        session = self._make_session()
        self.agent.send_message(AgentRole.PLANNER, "request", {}, session)
        self.agent.send_message(AgentRole.PLANNER, "request", {}, session)
        assert self.agent.messages_sent == 2

    def test_message_id_is_string(self):
        """Message.message_id is a non-empty string"""
        session = self._make_session()
        msg = self.agent.send_message(AgentRole.PLANNER, "request", {}, session)
        assert isinstance(msg.message_id, str)
        assert len(msg.message_id) > 0

    def test_message_to_dict_has_string_roles(self):
        """Message.to_dict serializes role enums as strings"""
        session = self._make_session()
        msg = self.agent.send_message(AgentRole.PLANNER, "request", {}, session)
        d = msg.to_dict()
        assert d["from_agent"] == "researcher"
        assert d["to_agent"] == "planner"


class TestResearcherAgent:
    """Test ResearcherAgent.execute"""

    def setup_method(self):
        """Create researcher agent with mocked LLM."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.agent = ResearcherAgent(self.mock_llm, self.mock_logger)

    def test_execute_returns_agent_result(self):
        """execute returns an AgentResult"""
        self.mock_llm.generate.return_value = make_research_response()
        result = self.agent.execute("solve problem", {})
        assert isinstance(result, AgentResult)

    def test_execute_success_on_valid_response(self):
        """Successful LLM response sets success=True"""
        self.mock_llm.generate.return_value = make_research_response()
        result = self.agent.execute("solve problem", {})
        assert result.success is True

    def test_execute_confidence_from_response(self):
        """Confidence value is parsed from LLM response"""
        self.mock_llm.generate.return_value = make_research_response(confidence=0.72)
        result = self.agent.execute("solve problem", {})
        assert result.confidence == pytest.approx(0.72)

    def test_execute_agent_role_is_researcher(self):
        """Result.agent is RESEARCHER"""
        self.mock_llm.generate.return_value = make_research_response()
        result = self.agent.execute("solve problem", {})
        assert result.agent == AgentRole.RESEARCHER

    def test_execute_failure_on_llm_error(self):
        """LLM error sets success=False and confidence=0.0"""
        self.mock_llm.generate.side_effect = RuntimeError("LLM down")
        result = self.agent.execute("solve problem", {})
        assert result.success is False
        assert result.confidence == 0.0

    def test_execute_failure_on_invalid_json(self):
        """Invalid JSON from LLM sets success=False"""
        self.mock_llm.generate.return_value = "not json"
        result = self.agent.execute("solve problem", {})
        assert result.success is False

    def test_prompt_contains_task(self):
        """LLM generate is called with prompt containing the task"""
        self.mock_llm.generate.return_value = make_research_response()
        self.agent.execute("my specific task", {})
        prompt = self.mock_llm.generate.call_args[0][0]
        assert "my specific task" in prompt

    def test_result_duration_is_non_negative(self):
        """Execution duration is >= 0"""
        self.mock_llm.generate.return_value = make_research_response()
        result = self.agent.execute("task", {})
        assert result.duration >= 0.0


class TestPlannerAgent:
    """Test PlannerAgent.execute"""

    def setup_method(self):
        """Create planner agent with mocked LLM."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.agent = PlannerAgent(self.mock_llm, self.mock_logger)

    def test_execute_returns_agent_result(self):
        """execute returns an AgentResult"""
        self.mock_llm.generate.return_value = make_plan_response()
        result = self.agent.execute("plan task", {})
        assert isinstance(result, AgentResult)

    def test_execute_success_on_valid_response(self):
        """Valid LLM plan response sets success=True"""
        self.mock_llm.generate.return_value = make_plan_response()
        result = self.agent.execute("plan task", {})
        assert result.success is True

    def test_execute_agent_role_is_planner(self):
        """Result.agent is PLANNER"""
        self.mock_llm.generate.return_value = make_plan_response()
        result = self.agent.execute("plan task", {})
        assert result.agent == AgentRole.PLANNER

    def test_prompt_includes_research_context(self):
        """Planner prompt includes research results from context"""
        self.mock_llm.generate.return_value = make_plan_response()
        ctx = {"research": {"analysis": "deep insight"}}
        self.agent.execute("plan task", ctx)
        prompt = self.mock_llm.generate.call_args[0][0]
        assert "deep insight" in prompt

    def test_execute_failure_on_llm_error(self):
        """LLM exception results in failed AgentResult"""
        self.mock_llm.generate.side_effect = RuntimeError("fail")
        result = self.agent.execute("plan task", {})
        assert result.success is False


class TestExecutorAgent:
    """Test ExecutorAgent.execute"""

    def setup_method(self):
        """Create executor agent with mocked orchestrator."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.mock_orchestrator = Mock()
        self.agent = ExecutorAgent(self.mock_llm, self.mock_logger, self.mock_orchestrator)

    def test_execute_returns_agent_result(self):
        """execute returns an AgentResult"""
        self.mock_orchestrator.execute_command.return_value = "done"
        ctx = {"plan": {"steps": [{"step_num": 1, "action": "do thing", "command": "echo hi", "risk": "low"}]}}
        result = self.agent.execute("task", ctx)
        assert isinstance(result, AgentResult)

    def test_execute_agent_role_is_executor(self):
        """Result.agent is EXECUTOR"""
        ctx = {"plan": {"steps": []}}
        result = self.agent.execute("task", ctx)
        assert result.agent == AgentRole.EXECUTOR

    def test_execute_calls_orchestrator_per_step(self):
        """orchestrator.execute_command is called once per plan step"""
        self.mock_orchestrator.execute_command.return_value = "ok"
        ctx = {
            "plan": {
                "steps": [
                    {"step_num": 1, "action": "step1", "command": "cmd1", "risk": "low"},
                    {"step_num": 2, "action": "step2", "command": "cmd2", "risk": "low"},
                ]
            }
        }
        self.agent.execute("task", ctx)
        assert self.mock_orchestrator.execute_command.call_count == 2

    def test_execute_success_when_all_steps_pass(self):
        """All steps succeeding sets result.success=True"""
        self.mock_orchestrator.execute_command.return_value = "ok"
        ctx = {"plan": {"steps": [{"step_num": 1, "action": "a", "command": "c", "risk": "low"}]}}
        result = self.agent.execute("task", ctx)
        assert result.success is True

    def test_execute_failure_when_step_raises(self):
        """Step exception sets result.success=False"""
        self.mock_orchestrator.execute_command.side_effect = RuntimeError("cmd failed")
        ctx = {"plan": {"steps": [{"step_num": 1, "action": "a", "command": "c", "risk": "low"}]}}
        result = self.agent.execute("task", ctx)
        assert result.success is False

    def test_stops_on_high_risk_failure(self):
        """Execution stops after first high-risk step failure"""
        self.mock_orchestrator.execute_command.side_effect = RuntimeError("fail")
        ctx = {
            "plan": {
                "steps": [
                    {"step_num": 1, "action": "a", "command": "c1", "risk": "high"},
                    {"step_num": 2, "action": "b", "command": "c2", "risk": "low"},
                ]
            }
        }
        self.agent.execute("task", ctx)
        # Only first step attempted
        assert self.mock_orchestrator.execute_command.call_count == 1

    def test_execute_no_steps_returns_success(self):
        """Empty plan steps still returns a result (success=True, all steps passed)"""
        ctx = {"plan": {"steps": []}}
        result = self.agent.execute("task", ctx)
        assert result.agent == AgentRole.EXECUTOR

    def test_result_contains_step_results(self):
        """Execution result output contains per-step result entries"""
        self.mock_orchestrator.execute_command.return_value = "output"
        ctx = {"plan": {"steps": [{"step_num": 1, "action": "a", "command": "c", "risk": "low"}]}}
        result = self.agent.execute("task", ctx)
        assert "results" in result.output
        assert len(result.output["results"]) == 1


class TestValidatorAgent:
    """Test ValidatorAgent.execute"""

    def setup_method(self):
        """Create validator agent with mocked LLM."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.agent = ValidatorAgent(self.mock_llm, self.mock_logger)

    def test_execute_returns_agent_result(self):
        """execute returns an AgentResult"""
        self.mock_llm.generate.return_value = make_validation_response()
        result = self.agent.execute("validate", {})
        assert isinstance(result, AgentResult)

    def test_execute_agent_role_is_validator(self):
        """Result.agent is VALIDATOR"""
        self.mock_llm.generate.return_value = make_validation_response()
        result = self.agent.execute("validate", {})
        assert result.agent == AgentRole.VALIDATOR

    def test_success_reflects_llm_overall_success(self):
        """result.success mirrors overall_success from LLM response"""
        self.mock_llm.generate.return_value = make_validation_response(overall_success=False)
        result = self.agent.execute("validate", {})
        assert result.success is False

    def test_execute_failure_on_llm_error(self):
        """LLM exception sets success=False"""
        self.mock_llm.generate.side_effect = RuntimeError("fail")
        result = self.agent.execute("validate", {})
        assert result.success is False

    def test_prompt_contains_task(self):
        """Validator prompt contains the original task"""
        self.mock_llm.generate.return_value = make_validation_response()
        self.agent.execute("my validation task", {})
        prompt = self.mock_llm.generate.call_args[0][0]
        assert "my validation task" in prompt

    def test_prompt_includes_plan_context(self):
        """Validator prompt includes plan data from context"""
        self.mock_llm.generate.return_value = make_validation_response()
        ctx = {"plan": {"steps": [{"step_num": 1}]}, "execution": {"results": []}}
        self.agent.execute("validate", ctx)
        prompt = self.mock_llm.generate.call_args[0][0]
        assert "step_num" in prompt


class TestMultiAgentSystemCollaboration:
    """Test MultiAgentSystem.collaborate workflow"""

    def setup_method(self):
        """Create multi-agent system with all agents mocked."""
        self.mock_llm = Mock()
        self.mock_logger = Mock()
        self.mas = MultiAgentSystem(self.mock_llm, self.mock_logger, orchestrator=None)

        # Patch agent execute methods
        self.mas.researcher = Mock()
        self.mas.planner = Mock()
        self.mas.validator = Mock()
        self.mas.executor = None

        # Default successful responses
        self.mas.researcher.execute.return_value = AgentResult(
            agent=AgentRole.RESEARCHER,
            success=True,
            output={"analysis": "done"},
            confidence=0.9,
            reasoning="research ok",
            duration=0.1,
            messages_sent=0,
        )
        self.mas.planner.execute.return_value = AgentResult(
            agent=AgentRole.PLANNER,
            success=True,
            output={"steps": [], "reasoning": "plan ok"},
            confidence=0.85,
            reasoning="plan ok",
            duration=0.1,
            messages_sent=0,
        )
        self.mas.validator.execute.return_value = AgentResult(
            agent=AgentRole.VALIDATOR,
            success=True,
            output={"reasoning": "all good"},
            confidence=0.95,
            reasoning="valid",
            duration=0.1,
            messages_sent=0,
        )

    def test_collaborate_returns_session(self):
        """collaborate returns a CollaborationSession"""
        session = self.mas.collaborate("do something")
        assert isinstance(session, CollaborationSession)

    def test_collaboration_runs_all_phases(self):
        """All three phases (researcher, planner, validator) are invoked"""
        self.mas.collaborate("do something")
        self.mas.researcher.execute.assert_called_once()
        self.mas.planner.execute.assert_called_once()
        self.mas.validator.execute.assert_called_once()

    def test_session_success_on_all_agents_pass(self):
        """Session is marked successful when all agents succeed"""
        session = self.mas.collaborate("task")
        assert session.success is True

    def test_research_output_propagated_to_planner(self):
        """Planner receives research output in its context"""
        self.mas.collaborate("task")
        planner_ctx = self.mas.planner.execute.call_args[0][1]
        assert "research" in planner_ctx

    def test_plan_output_propagated_to_validator(self):
        """Validator receives plan output in its context"""
        self.mas.collaborate("task")
        validator_ctx = self.mas.validator.execute.call_args[0][1]
        assert "plan" in validator_ctx

    def test_stops_on_researcher_failure(self):
        """Collaboration stops and returns if researcher fails"""
        self.mas.researcher.execute.return_value = AgentResult(
            agent=AgentRole.RESEARCHER,
            success=False,
            output={"error": "failed"},
            confidence=0.0,
            reasoning="fail",
            duration=0.0,
            messages_sent=0,
        )
        session = self.mas.collaborate("task")
        assert session.success is False
        assert session.final_result == "Research failed"
        self.mas.planner.execute.assert_not_called()

    def test_stops_on_planner_failure(self):
        """Collaboration stops and returns if planner fails"""
        self.mas.planner.execute.return_value = AgentResult(
            agent=AgentRole.PLANNER,
            success=False,
            output={},
            confidence=0.0,
            reasoning="fail",
            duration=0.0,
            messages_sent=0,
        )
        session = self.mas.collaborate("task")
        assert session.success is False
        assert session.final_result == "Planning failed"
        self.mas.validator.execute.assert_not_called()

    def test_session_contains_all_results(self):
        """Session.results contains researcher, planner, and validator results"""
        session = self.mas.collaborate("task")
        agent_roles = {r.agent for r in session.results}
        assert AgentRole.RESEARCHER in agent_roles
        assert AgentRole.PLANNER in agent_roles
        assert AgentRole.VALIDATOR in agent_roles

    def test_session_agents_involved_populated(self):
        """Session.agents_involved lists all participating agents"""
        session = self.mas.collaborate("task")
        assert AgentRole.RESEARCHER in session.agents_involved
        assert AgentRole.PLANNER in session.agents_involved
        assert AgentRole.VALIDATOR in session.agents_involved

    def test_session_duration_is_non_negative(self):
        """Session total_duration is >= 0"""
        session = self.mas.collaborate("task")
        assert session.total_duration >= 0.0

    def test_session_has_unique_id(self):
        """Session session_id is a non-empty string"""
        session = self.mas.collaborate("task")
        assert isinstance(session.session_id, str)
        assert len(session.session_id) > 0

    def test_exception_during_collaboration_returns_failed_session(self):
        """Unhandled exception produces a failed session instead of raising"""
        self.mas.researcher.execute.side_effect = RuntimeError("unexpected crash")
        session = self.mas.collaborate("task")
        assert session.success is False
        assert "failed" in session.final_result.lower()

    def test_executor_runs_when_present(self):
        """When executor is set, it is also invoked during collaboration"""
        mock_executor = Mock()
        mock_executor.execute.return_value = AgentResult(
            agent=AgentRole.EXECUTOR,
            success=True,
            output={"results": []},
            confidence=1.0,
            reasoning="executed",
            duration=0.1,
            messages_sent=0,
        )
        self.mas.executor = mock_executor
        self.mas.collaborate("task")
        mock_executor.execute.assert_called_once()

    def test_stops_on_executor_failure(self):
        """Collaboration stops if executor fails"""
        mock_executor = Mock()
        mock_executor.execute.return_value = AgentResult(
            agent=AgentRole.EXECUTOR,
            success=False,
            output={},
            confidence=0.0,
            reasoning="exec fail",
            duration=0.0,
            messages_sent=0,
        )
        self.mas.executor = mock_executor
        session = self.mas.collaborate("task")
        assert session.success is False
        assert session.final_result == "Execution failed"
        self.mas.validator.execute.assert_not_called()


class TestCollaborationSessionToDict:
    """Test CollaborationSession.to_dict serialization"""

    def test_agents_involved_serialized_as_strings(self):
        """agents_involved list is serialized as role string values"""
        session = CollaborationSession(
            session_id="abc",
            task="test",
            agents_involved=[AgentRole.RESEARCHER, AgentRole.PLANNER],
            messages=[],
            results=[],
            final_result=None,
            success=True,
            total_duration=0.5,
        )
        d = session.to_dict()
        assert d["agents_involved"] == ["researcher", "planner"]


class TestAgentResultToDict:
    """Test AgentResult.to_dict serialization"""

    def test_agent_role_serialized_as_string(self):
        """AgentResult.to_dict encodes agent as string"""
        result = AgentResult(
            agent=AgentRole.VALIDATOR,
            success=True,
            output={},
            confidence=0.9,
            reasoning="ok",
            duration=0.1,
            messages_sent=0,
        )
        d = result.to_dict()
        assert d["agent"] == "validator"


class TestGetMultiAgentSystem:
    """Test singleton factory"""

    def test_returns_instance(self):
        """get_multi_agent_system returns a MultiAgentSystem"""
        import zenus_core.brain.multi_agent as module
        original = module._multi_agent_system
        module._multi_agent_system = None
        try:
            instance = get_multi_agent_system(Mock(), Mock())
            assert isinstance(instance, MultiAgentSystem)
        finally:
            module._multi_agent_system = original

    def test_returns_same_singleton(self):
        """get_multi_agent_system returns same instance on repeat calls"""
        import zenus_core.brain.multi_agent as module
        original = module._multi_agent_system
        module._multi_agent_system = None
        try:
            a = get_multi_agent_system(Mock(), Mock())
            b = get_multi_agent_system(Mock(), Mock())
            assert a is b
        finally:
            module._multi_agent_system = original
