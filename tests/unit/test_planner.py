"""
Tests for plan execution
"""

import pytest
from unittest.mock import Mock
from zenus_core.brain.llm.schemas import IntentIR, Step
from zenus_core.brain.planner import execute_plan
from zenus_core.safety.policy import SafetyError
from zenus_core.tools.file_ops import FileOps


class TestPlanner:
    """Test plan execution logic"""
    
    def setup_method(self):
        """Reset tool registry before each test"""
        from zenus_core.tools import registry
        # Store original and reset
        self.original_tools = registry.TOOLS.copy()
        registry.TOOLS.clear()
        registry.TOOLS["FileOps"] = FileOps()
    
    def teardown_method(self):
        """Restore tool registry after each test"""
        from zenus_core.tools import registry
        registry.TOOLS.clear()
        registry.TOOLS.update(self.original_tools)
    
    def test_executes_simple_plan(self, capsys):
        """Should execute a simple single-step plan"""
        # Create mock tool
        mock_tool = Mock()
        mock_tool.scan = Mock(return_value=["file1.txt", "file2.txt"])
        
        # Replace in registry
        from zenus_core.tools import registry
        registry.TOOLS["FileOps"] = mock_tool
        
        step = Step(tool="FileOps", action="scan", args={"path": "/tmp"}, risk=0)
        intent = IntentIR(
            goal="List files in tmp",
            requires_confirmation=False,
            steps=[step]
        )
        
        execute_plan(intent)
        
        # Verify tool was called
        mock_tool.scan.assert_called_once_with(path="/tmp")
        
        # Verify output
        captured = capsys.readouterr()
        assert "Done:" in captured.out
    
    def test_executes_multi_step_plan(self):
        """Should execute multiple steps in sequence"""
        # Track calls
        calls = []
        
        class MockTool:
            def mkdir(self, **kwargs):
                calls.append(("mkdir", kwargs))
                return "Created"
            
            def touch(self, **kwargs):
                calls.append(("touch", kwargs))
                return "Touched"
        
        from zenus_core.tools import registry
        registry.TOOLS["FileOps"] = MockTool()
        
        steps = [
            Step(tool="FileOps", action="mkdir", args={"path": "/tmp/test"}, risk=1),
            Step(tool="FileOps", action="touch", args={"path": "/tmp/test/file"}, risk=1)
        ]
        intent = IntentIR(
            goal="Create directory and file",
            requires_confirmation=False,
            steps=steps
        )
        
        execute_plan(intent)
        
        # Verify both steps executed in order
        assert len(calls) == 2
        assert calls[0] == ("mkdir", {"path": "/tmp/test"})
        assert calls[1] == ("touch", {"path": "/tmp/test/file"})
    
    def test_stops_on_safety_error(self):
        """Should stop execution if safety check fails"""
        step = Step(tool="FileOps", action="delete", args={}, risk=3)
        intent = IntentIR(goal="Delete", requires_confirmation=False, steps=[step])
        
        with pytest.raises(SafetyError):
            execute_plan(intent)
    
    def test_raises_on_missing_tool(self):
        """Should raise ValueError if tool not found"""
        from zenus_core.tools import registry
        # Remove FileOps
        del registry.TOOLS["FileOps"]
        
        step = Step(tool="NonExistent", action="test", args={}, risk=0)
        intent = IntentIR(goal="Test", requires_confirmation=False, steps=[step])
        
        with pytest.raises(ValueError, match="Tool not found"):
            execute_plan(intent)
    
    def test_raises_on_missing_action(self):
        """Should raise ValueError if action not found"""
        class MockTool:
            def scan(self):
                return "result"
        
        from zenus_core.tools import registry
        registry.TOOLS["FileOps"] = MockTool()
        
        step = Step(tool="FileOps", action="nonexistent", args={}, risk=0)
        intent = IntentIR(goal="Test", requires_confirmation=False, steps=[step])
        
        with pytest.raises(ValueError, match="Action not found"):
            execute_plan(intent)
    
    def test_logs_steps_when_logger_provided(self):
        """Should log step results when logger is provided"""
        mock_tool = Mock()
        mock_tool.scan = Mock(return_value="result")
        mock_logger = Mock()

        from zenus_core.tools import registry
        registry.TOOLS["FileOps"] = mock_tool

        step = Step(tool="FileOps", action="scan", args={}, risk=0)
        intent = IntentIR(goal="Test", requires_confirmation=False, steps=[step])

        execute_plan(intent, logger=mock_logger)

        # Verify logger was called
        mock_logger.log_step_result.assert_called_once()
        args = mock_logger.log_step_result.call_args[0]
        assert args[0] == "FileOps"
        assert args[1] == "scan"
        assert args[3] is True  # success

    def test_parallel_false_skips_parallel_executor(self):
        """parallel=False should use sequential execution"""
        mock_tool = Mock()
        mock_tool.scan = Mock(return_value="seq_result")

        from zenus_core.tools import registry
        registry.TOOLS["FileOps"] = mock_tool

        steps = [
            Step(tool="FileOps", action="scan", args={"path": "/a"}, risk=0),
            Step(tool="FileOps", action="scan", args={"path": "/b"}, risk=0),
        ]
        intent = IntentIR(goal="scan", requires_confirmation=False, steps=steps)

        results = execute_plan(intent, parallel=False)

        assert mock_tool.scan.call_count == 2
        assert len(results) == 2

    def test_logs_missing_tool_error(self):
        """Logger should receive failure when tool not found"""
        from zenus_core.tools import registry
        del registry.TOOLS["FileOps"]

        mock_logger = Mock()
        step = Step(tool="NonExistent", action="test", args={}, risk=0)
        intent = IntentIR(goal="Test", requires_confirmation=False, steps=[step])

        with pytest.raises(ValueError):
            execute_plan(intent, logger=mock_logger, parallel=False)

        mock_logger.log_step_result.assert_called_once()
        args = mock_logger.log_step_result.call_args[0]
        assert args[3] is False  # failure

    def test_logs_missing_action_error(self):
        """Logger should receive failure when action not found"""
        class MockTool:
            pass

        from zenus_core.tools import registry
        registry.TOOLS["FileOps"] = MockTool()

        mock_logger = Mock()
        step = Step(tool="FileOps", action="nonexistent", args={}, risk=0)
        intent = IntentIR(goal="Test", requires_confirmation=False, steps=[step])

        with pytest.raises(ValueError):
            execute_plan(intent, logger=mock_logger, parallel=False)

        mock_logger.log_step_result.assert_called_once()
        args = mock_logger.log_step_result.call_args[0]
        assert args[3] is False

    def test_privilege_check_raises_for_restricted_tier(self):
        """ShellOps should be blocked at STANDARD tier"""
        from zenus_core.tools import registry
        from zenus_core.tools.privilege import PrivilegeTier
        from zenus_core.safety.policy import SafetyError

        mock_shell = Mock()
        mock_shell.run = Mock(return_value="ok")
        registry.TOOLS["ShellOps"] = mock_shell

        step = Step(tool="ShellOps", action="run", args={}, risk=1)
        intent = IntentIR(goal="Run shell", requires_confirmation=False, steps=[step])

        with pytest.raises(SafetyError):
            execute_plan(intent, parallel=False, privilege_tier=PrivilegeTier.STANDARD)

    def test_privilege_check_allows_privileged_tier(self, capsys):
        """ShellOps should succeed at PRIVILEGED tier"""
        from zenus_core.tools import registry
        from zenus_core.tools.privilege import PrivilegeTier

        mock_shell = Mock()
        mock_shell.run = Mock(return_value="shell output")
        registry.TOOLS["ShellOps"] = mock_shell

        step = Step(tool="ShellOps", action="run", args={}, risk=1)
        intent = IntentIR(goal="Run shell", requires_confirmation=False, steps=[step])

        results = execute_plan(intent, parallel=False, privilege_tier=PrivilegeTier.PRIVILEGED)

        mock_shell.run.assert_called_once()
        assert len(results) == 1

    def test_error_recovery_on_tool_exception(self):
        """Tool exception should trigger error recovery"""
        from unittest.mock import patch
        from zenus_core.tools import registry

        mock_tool = Mock()
        mock_tool.scan = Mock(side_effect=RuntimeError("disk I/O error"))
        registry.TOOLS["FileOps"] = mock_tool

        step = Step(tool="FileOps", action="scan", args={}, risk=0)
        intent = IntentIR(goal="scan", requires_confirmation=False, steps=[step])

        mock_recovery = Mock()
        mock_recovery.recover.return_value = Mock(
            success=True,
            message="Recovered successfully"
        )

        with patch(
            "zenus_core.execution.error_recovery.get_error_recovery",
            return_value=mock_recovery
        ):
            results = execute_plan(intent, parallel=False)

        mock_recovery.recover.assert_called_once()
        assert len(results) == 1
        assert "Recovered" in results[0]

    def test_error_recovery_failure_raises(self):
        """Failed recovery should raise RuntimeError via error handler"""
        from unittest.mock import patch, MagicMock
        from zenus_core.tools import registry

        mock_tool = Mock()
        mock_tool.scan = Mock(side_effect=RuntimeError("disk failure"))
        registry.TOOLS["FileOps"] = mock_tool

        step = Step(tool="FileOps", action="scan", args={}, risk=0)
        intent = IntentIR(goal="scan", requires_confirmation=False, steps=[step])

        mock_recovery = Mock()
        recovery_result = Mock()
        recovery_result.success = False
        recovery_result.message = "Could not recover"
        mock_recovery.recover.return_value = recovery_result

        mock_error_handler = MagicMock()
        mock_enhanced = MagicMock()
        mock_enhanced.user_friendly = "Human-friendly error"
        mock_enhanced.format.return_value = "[red]error[/red]"
        mock_error_handler.handle.return_value = mock_enhanced

        with patch("zenus_core.execution.error_recovery.get_error_recovery", return_value=mock_recovery):
            with patch("zenus_core.execution.error_handler.get_error_handler", return_value=mock_error_handler):
                with pytest.raises(RuntimeError):
                    execute_plan(intent, parallel=False)

        mock_recovery.recover.assert_called_once()

    def test_returns_list_of_string_results(self):
        """execute_plan should return a list of string results"""
        mock_tool = Mock()
        mock_tool.scan = Mock(return_value=42)  # non-string return value

        from zenus_core.tools import registry
        registry.TOOLS["FileOps"] = mock_tool

        step = Step(tool="FileOps", action="scan", args={}, risk=0)
        intent = IntentIR(goal="Test", requires_confirmation=False, steps=[step])

        results = execute_plan(intent, parallel=False)

        assert isinstance(results, list)
        assert all(isinstance(r, str) for r in results)
