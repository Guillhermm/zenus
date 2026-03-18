"""
Tests for shell subsystem: commands, enhanced shell, shell helpers, explain, response_generator.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_intent(goal="test goal", steps=None, requires_confirmation=False):
    """Build an IntentIR for testing."""
    if steps is None:
        steps = [Step(tool="FileOps", action="read_file", args={"path": "/tmp/a"}, risk=0)]
    return IntentIR(goal=goal, requires_confirmation=requires_confirmation, steps=steps)


def make_step(tool="FileOps", action="read_file", args=None, risk=0):
    """Build a single Step."""
    return Step(tool=tool, action=action, args=args or {}, risk=risk)


# ===========================================================================
# Shell helpers (shell_helpers.py)
# ===========================================================================

class TestShellHelpers:
    def test_setup_readline_does_not_raise(self):
        """setup_readline_prompt runs without raising even if readline absent."""
        from zenus_core.shell.shell_helpers import setup_readline_prompt
        setup_readline_prompt()

    def test_clear_line_writes_escape_sequence(self):
        """clear_line writes the ANSI clear-line sequence."""
        from zenus_core.shell import shell_helpers
        mock_stdout = MagicMock()
        with patch.object(shell_helpers.sys, 'stdout', mock_stdout):
            shell_helpers.clear_line()
        mock_stdout.write.assert_called_once_with('\r\033[K')

    def test_move_cursor_up_writes_sequence(self):
        """move_cursor_up writes correct ANSI sequence."""
        from zenus_core.shell import shell_helpers
        mock_stdout = MagicMock()
        with patch.object(shell_helpers.sys, 'stdout', mock_stdout):
            shell_helpers.move_cursor_up(3)
        mock_stdout.write.assert_called_once_with('\033[3A')

    def test_save_cursor_writes_sequence(self):
        """save_cursor writes the ANSI save cursor sequence."""
        from zenus_core.shell import shell_helpers
        mock_stdout = MagicMock()
        with patch.object(shell_helpers.sys, 'stdout', mock_stdout):
            shell_helpers.save_cursor()
        mock_stdout.write.assert_called_once_with('\033[s')

    def test_restore_cursor_writes_sequence(self):
        """restore_cursor writes the ANSI restore cursor sequence."""
        from zenus_core.shell import shell_helpers
        mock_stdout = MagicMock()
        with patch.object(shell_helpers.sys, 'stdout', mock_stdout):
            shell_helpers.restore_cursor()
        mock_stdout.write.assert_called_once_with('\033[u')

    def test_move_cursor_up_default_one_line(self):
        """move_cursor_up with no args moves up 1 line."""
        from zenus_core.shell import shell_helpers
        mock_stdout = MagicMock()
        with patch.object(shell_helpers.sys, 'stdout', mock_stdout):
            shell_helpers.move_cursor_up()
        mock_stdout.write.assert_called_once_with('\033[1A')


# ===========================================================================
# ZenusCompleter (enhanced_shell.py)
# ===========================================================================

class TestZenusCompleter:
    def _make_document(self, text, word=None):
        """Create a mock Document for the completer."""
        doc = MagicMock()
        doc.text_before_cursor = text
        doc.get_word_before_cursor.return_value = word if word is not None else text
        return doc

    def test_special_commands_completed_at_start(self):
        """Typing 'sta' at start yields 'status' as completion."""
        from zenus_core.shell.enhanced_shell import ZenusCompleter
        completer = ZenusCompleter()
        doc = self._make_document("sta", "sta")
        completions = list(completer.get_completions(doc, MagicMock()))
        names = [c.text for c in completions]
        assert "status" in names

    def test_action_verb_completed(self):
        """Typing 'li' yields 'list' as an action completion."""
        from zenus_core.shell.enhanced_shell import ZenusCompleter
        completer = ZenusCompleter()
        doc = self._make_document("li", "li")
        completions = list(completer.get_completions(doc, MagicMock()))
        names = [c.text for c in completions]
        assert "list" in names

    def test_common_target_completed(self):
        """Typing 'fil' yields 'files' as target completion."""
        from zenus_core.shell.enhanced_shell import ZenusCompleter
        completer = ZenusCompleter()
        doc = self._make_document("fil", "fil")
        completions = list(completer.get_completions(doc, MagicMock()))
        names = [c.text for c in completions]
        assert "files" in names

    def test_unknown_word_no_crash(self):
        """An unrecognised prefix returns no completions (but doesn't raise)."""
        from zenus_core.shell.enhanced_shell import ZenusCompleter
        completer = ZenusCompleter()
        doc = self._make_document("zzzzzz", "zzzzzz")
        completions = list(completer.get_completions(doc, MagicMock()))
        assert isinstance(completions, list)

    def test_completion_metadata_for_special_command(self):
        """Special command completions carry 'special command' as display_meta."""
        from zenus_core.shell.enhanced_shell import ZenusCompleter
        completer = ZenusCompleter()
        doc = self._make_document("sta", "sta")
        completions = list(completer.get_completions(doc, MagicMock()))
        meta_values = [c.display_meta for c in completions]
        assert any("special command" in str(m) for m in meta_values)


class TestEnhancedShell:
    def test_create_enhanced_shell_factory(self):
        """create_enhanced_shell returns an EnhancedShell instance."""
        from zenus_core.shell.enhanced_shell import create_enhanced_shell, EnhancedShell
        with patch('zenus_core.shell.enhanced_shell.PromptSession'):
            shell = create_enhanced_shell(history_file="/tmp/test_zenus_hist")
        assert isinstance(shell, EnhancedShell)

    def test_prompt_returns_stripped_input(self):
        """prompt() strips whitespace from user input."""
        from zenus_core.shell.enhanced_shell import EnhancedShell
        with patch('zenus_core.shell.enhanced_shell.PromptSession') as MockSession:
            instance = MockSession.return_value
            instance.prompt.return_value = "  list files  "
            shell = EnhancedShell(history_file="/tmp/test_zenus_hist")
            result = shell.prompt("zenus> ")
        assert result == "list files"

    def test_prompt_returns_empty_on_keyboard_interrupt(self):
        """KeyboardInterrupt during prompt() returns empty string."""
        from zenus_core.shell.enhanced_shell import EnhancedShell
        with patch('zenus_core.shell.enhanced_shell.PromptSession') as MockSession:
            instance = MockSession.return_value
            instance.prompt.side_effect = KeyboardInterrupt
            shell = EnhancedShell(history_file="/tmp/test_zenus_hist")
            result = shell.prompt("zenus> ")
        assert result == ""

    def test_prompt_returns_exit_on_eoferror(self):
        """EOFError during prompt() returns 'exit'."""
        from zenus_core.shell.enhanced_shell import EnhancedShell
        with patch('zenus_core.shell.enhanced_shell.PromptSession') as MockSession:
            instance = MockSession.return_value
            instance.prompt.side_effect = EOFError
            shell = EnhancedShell(history_file="/tmp/test_zenus_hist")
            result = shell.prompt("zenus> ")
        assert result == "exit"

    def test_multiline_prompt_restores_multiline_flag(self):
        """multiline_prompt restores original multiline setting after call."""
        from zenus_core.shell.enhanced_shell import EnhancedShell
        with patch('zenus_core.shell.enhanced_shell.PromptSession') as MockSession:
            instance = MockSession.return_value
            instance.multiline = False
            instance.prompt.return_value = "hello"
            shell = EnhancedShell(history_file="/tmp/test_zenus_hist")
            shell.session = instance
            shell.multiline_prompt()
        assert instance.multiline is False


# ===========================================================================
# ExplainMode (explain.py)
# ===========================================================================

class TestExplainMode:
    def test_generate_reasoning_single_step(self):
        """Single-step intent produces 'simple single-step' reasoning."""
        from zenus_core.shell.explain import ExplainMode
        mode = ExplainMode()
        intent = make_intent(steps=[make_step()])
        reasoning = mode._generate_reasoning(intent)
        assert "simple single-step" in reasoning

    def test_generate_reasoning_multiple_steps(self):
        """Multi-step intent mentions the step count in reasoning."""
        from zenus_core.shell.explain import ExplainMode
        mode = ExplainMode()
        intent = make_intent(steps=[make_step(), make_step(action="write_file", risk=2)])
        reasoning = mode._generate_reasoning(intent)
        assert "2 steps" in reasoning

    def test_generate_reasoning_all_read_only(self):
        """All risk=0 steps produce 'read-only' reasoning."""
        from zenus_core.shell.explain import ExplainMode
        mode = ExplainMode()
        steps = [make_step(risk=0), make_step(action="scan", risk=0)]
        intent = make_intent(steps=steps)
        reasoning = mode._generate_reasoning(intent)
        assert "read-only" in reasoning

    def test_generate_reasoning_danger_steps(self):
        """Dangerous steps trigger a warning in reasoning."""
        from zenus_core.shell.explain import ExplainMode
        mode = ExplainMode()
        intent = make_intent(steps=[make_step(risk=3)])
        reasoning = mode._generate_reasoning(intent)
        assert "destructive" in reasoning.lower() or "danger" in reasoning.lower()

    def test_generate_reasoning_lists_tools(self):
        """Reasoning includes the tool name(s) used."""
        from zenus_core.shell.explain import ExplainMode
        mode = ExplainMode()
        intent = make_intent(steps=[make_step(tool="GitOps", action="commit", risk=1)])
        reasoning = mode._generate_reasoning(intent)
        assert "GitOps" in reasoning

    def test_explain_calls_print_explanation(self):
        """explain() delegates to print_explanation from console module."""
        from zenus_core.shell.explain import ExplainMode
        mode = ExplainMode()
        intent = make_intent()
        with patch("zenus_core.shell.explain.print_explanation") as mock_pe, \
             patch("zenus_core.shell.explain.console"):
            mode.explain("list files", intent, show_similar=False)
        mock_pe.assert_called_once()

    def test_confirm_returns_true_for_y(self):
        """confirm() returns True when user enters 'y'."""
        from zenus_core.shell.explain import ExplainMode
        mode = ExplainMode()
        with patch("zenus_core.shell.explain.console") as mock_console:
            mock_console.input.return_value = "y"
            assert mode.confirm() is True

    def test_confirm_returns_false_for_n(self):
        """confirm() returns False when user enters 'n'."""
        from zenus_core.shell.explain import ExplainMode
        mode = ExplainMode()
        with patch("zenus_core.shell.explain.console") as mock_console:
            mock_console.input.return_value = "n"
            assert mode.confirm() is False


# ===========================================================================
# Explainer (explain.py)
# ===========================================================================

class TestExplainer:
    def test_explain_intent_prints_to_console(self):
        """explain_intent produces console output."""
        from zenus_core.shell.explain import Explainer
        explainer = Explainer()
        intent = make_intent(requires_confirmation=False)
        with patch("zenus_core.shell.explain.console") as mock_console:
            explainer.explain_intent("list files", intent)
        assert mock_console.print.call_count > 0

    def test_explain_task_complexity_iterative(self):
        """explain_task_complexity mentions ITERATIVE for needs_iteration=True."""
        from zenus_core.shell.explain import Explainer
        explainer = Explainer()
        with patch("zenus_core.shell.explain.console") as mock_console:
            explainer.explain_task_complexity("do X", True, 0.9, "complex", 5)
        texts = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "ITERATIVE" in texts

    def test_explain_task_complexity_one_shot(self):
        """explain_task_complexity mentions ONE-SHOT for needs_iteration=False."""
        from zenus_core.shell.explain import Explainer
        explainer = Explainer()
        with patch("zenus_core.shell.explain.console") as mock_console:
            explainer.explain_task_complexity("do Y", False, 0.95, "simple", 1)
        texts = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "ONE-SHOT" in texts

    def test_show_alternatives_prints_alternatives(self):
        """show_alternatives outputs each alternative name."""
        from zenus_core.shell.explain import Explainer
        explainer = Explainer()
        alts = [{"name": "Option A", "description": "desc", "pros": ["fast"]}]
        with patch("zenus_core.shell.explain.console") as mock_console:
            explainer.show_alternatives(alts)
        texts = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Option A" in texts


# ===========================================================================
# ExplainabilityDashboard (explain.py)
# ===========================================================================

class TestExplainabilityDashboard:
    def _make_execution_explanation(self):
        """Build a minimal ExecutionExplanation."""
        from zenus_core.shell.explain import ExecutionExplanation, StepExplanation
        step = make_step()
        se = StepExplanation(
            step=step, reasoning="because", confidence=0.9,
            execution_time=0.1, result="done", success=True
        )
        intent = make_intent()
        return ExecutionExplanation(
            user_input="list files",
            understood_goal="List all files",
            intent=intent,
            step_explanations=[se],
            total_time=0.5,
            overall_confidence=0.9
        )

    def test_add_execution_appends_to_history(self):
        """add_execution grows the history list."""
        from zenus_core.shell.explain import ExplainabilityDashboard
        db = ExplainabilityDashboard()
        exp = self._make_execution_explanation()
        db.add_execution(exp)
        assert len(db.history) == 1

    def test_history_trimmed_to_max(self):
        """History is trimmed to max_history when exceeded."""
        from zenus_core.shell.explain import ExplainabilityDashboard
        db = ExplainabilityDashboard()
        db.max_history = 3
        for _ in range(5):
            db.add_execution(self._make_execution_explanation())
        assert len(db.history) == 3

    def test_explain_last_with_empty_history(self):
        """explain_last with no history prints a warning."""
        from zenus_core.shell.explain import ExplainabilityDashboard
        db = ExplainabilityDashboard()
        with patch("zenus_core.shell.explain.console") as mock_console:
            db.explain_last()
        mock_console.print.assert_called_once()

    def test_explain_last_with_history_prints_details(self):
        """explain_last with history outputs explanation."""
        from zenus_core.shell.explain import ExplainabilityDashboard
        db = ExplainabilityDashboard()
        db.add_execution(self._make_execution_explanation())
        with patch("zenus_core.shell.explain.console") as mock_console:
            db.explain_last()
        assert mock_console.print.call_count > 0

    def test_explain_execution_invalid_index(self):
        """explain_execution with bad index shows error."""
        from zenus_core.shell.explain import ExplainabilityDashboard
        db = ExplainabilityDashboard()
        db.add_execution(self._make_execution_explanation())
        with patch("zenus_core.shell.explain.console") as mock_console:
            db.explain_execution(index=-99)
        mock_console.print.assert_called_once()

    def test_show_history_empty(self):
        """show_history with no entries prints a warning."""
        from zenus_core.shell.explain import ExplainabilityDashboard
        db = ExplainabilityDashboard()
        with patch("zenus_core.shell.explain.console") as mock_console:
            db.show_history()
        mock_console.print.assert_called_once()

    def test_execution_explanation_to_dict(self):
        """ExecutionExplanation.to_dict returns expected keys."""
        exp = self._make_execution_explanation()
        d = exp.to_dict()
        assert "user_input" in d
        assert "understood_goal" in d
        assert "intent" in d
        assert "step_explanations" in d

    def test_get_explainability_dashboard_singleton(self):
        """get_explainability_dashboard returns same instance."""
        from zenus_core.shell import explain as exp_mod
        exp_mod._dashboard = None
        a = exp_mod.get_explainability_dashboard()
        b = exp_mod.get_explainability_dashboard()
        assert a is b
        exp_mod._dashboard = None


# ===========================================================================
# ResponseGenerator (response_generator.py)
# ===========================================================================

class TestResponseGenerator:
    def test_simple_summary_no_results(self):
        """_simple_summary with empty results returns the goal."""
        from zenus_core.shell.response_generator import ResponseGenerator
        gen = ResponseGenerator(llm=MagicMock())
        intent = make_intent(goal="backup files")
        result = gen._simple_summary(intent, [])
        assert "backup files" in result

    def test_simple_summary_created_result(self):
        """_simple_summary for a 'created' result prepends 'Done!'."""
        from zenus_core.shell.response_generator import ResponseGenerator
        gen = ResponseGenerator(llm=MagicMock())
        intent = make_intent()
        result = gen._simple_summary(intent, ["created /tmp/output.txt"])
        assert result.startswith("Done!")

    def test_simple_summary_found_result(self):
        """_simple_summary for a 'found' result returns the result directly."""
        from zenus_core.shell.response_generator import ResponseGenerator
        gen = ResponseGenerator(llm=MagicMock())
        intent = make_intent()
        result = gen._simple_summary(intent, ["found 5 files"])
        assert "found 5 files" in result

    def test_simple_summary_generic_result(self):
        """_simple_summary for generic result prepends 'Completed:'."""
        from zenus_core.shell.response_generator import ResponseGenerator
        gen = ResponseGenerator(llm=MagicMock())
        intent = make_intent()
        result = gen._simple_summary(intent, ["all done"])
        assert result.startswith("Completed:")

    def test_generate_summary_returns_string(self):
        """generate_summary returns a non-empty string."""
        from zenus_core.shell.response_generator import ResponseGenerator
        gen = ResponseGenerator(llm=MagicMock())
        intent = make_intent()
        result = gen.generate_summary("backup", intent, ["backed up 10 files"])
        assert isinstance(result, str)
        assert len(result) > 0
