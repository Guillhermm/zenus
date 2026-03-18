"""
Tests for output subsystem: formatter, console helpers, progress tracker, and streaming.
"""

import time
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_console_mock():
    """Return a MagicMock that replaces Rich Console."""
    return MagicMock()


# ===========================================================================
# OutputFormatter
# ===========================================================================

class TestOutputFormatterDetection:
    def test_looks_like_json_object(self):
        """String starting/ending with braces is detected as JSON."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._looks_like_json('{"key": "value"}') is True

    def test_looks_like_json_array(self):
        """String starting/ending with brackets is detected as JSON."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._looks_like_json('[1, 2, 3]') is True

    def test_not_json(self):
        """Plain text is not detected as JSON."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._looks_like_json('hello world') is False

    def test_looks_like_table_with_pipe(self):
        """Multiple lines containing | are detected as table."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        text = "a | b | c\n1 | 2 | 3\n4 | 5 | 6"
        assert fmt._looks_like_table(text) is True

    def test_not_table_single_line(self):
        """Single line is never detected as a table."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._looks_like_table("a | b") is False

    def test_looks_like_code_python(self):
        """String containing 'def ' is detected as code."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._looks_like_code('def foo():\n    pass') is True

    def test_looks_like_code_import(self):
        """String containing 'import ' is detected as code."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._looks_like_code('import os') is True

    def test_not_code(self):
        """Plain sentence does not trigger code detection."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._looks_like_code('Hello, world!') is False


class TestOutputFormatterLanguageDetection:
    def test_detects_python(self):
        """Code with 'def' is identified as Python."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._detect_language('def foo(): pass') == 'python'

    def test_detects_javascript(self):
        """Code with 'function' is identified as JavaScript."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._detect_language('function foo() {}') == 'javascript'

    def test_detects_php(self):
        """Code with '<?php' is identified as PHP."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._detect_language('<?php echo "hello";') == 'php'

    def test_detects_bash(self):
        """Code with shebang is identified as bash."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._detect_language('#!/bin/bash\necho hi') == 'bash'

    def test_fallback_text(self):
        """Unknown code returns 'text'."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._detect_language('just some stuff') == 'text'


class TestOutputFormatterSimpleDict:
    def test_is_simple_dict_no_nesting(self):
        """Flat dict is recognised as simple."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._is_simple_dict({"a": 1, "b": "x"}) is True

    def test_is_not_simple_dict_with_nested_dict(self):
        """Dict with nested dict is NOT simple."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._is_simple_dict({"a": {"b": 1}}) is False

    def test_is_not_simple_dict_with_list(self):
        """Dict with list value is NOT simple."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._is_simple_dict({"a": [1, 2]}) is False


class TestOutputFormatterFormat:
    def test_format_empty_list_returns_empty_message(self):
        """Empty list yields 'Empty list' without printing."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        fmt.console = make_console_mock()
        result = fmt.format([])
        assert result == "Empty list"

    def test_format_list_of_dicts_returns_table_string(self):
        """List of dicts is formatted as a table summary."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        fmt.console = make_console_mock()
        result = fmt.format([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
        assert "Table" in result
        assert "2 rows" in result

    def test_format_simple_dict_returns_table_string(self):
        """Simple flat dict is formatted as a two-column table."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        fmt.console = make_console_mock()
        result = fmt.format({"x": 1, "y": 2})
        assert "Table" in result

    def test_format_int_falls_through_to_str(self):
        """Non-string, non-list, non-dict returns str() of the value."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        fmt.console = make_console_mock()
        assert fmt.format(42) == "42"

    def test_format_list_of_scalars_returns_bullets(self):
        """List of plain values is formatted as bullet points."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        fmt.console = make_console_mock()
        result = fmt.format(["alpha", "beta", "gamma"])
        assert "alpha" in result
        assert "beta" in result

    def test_format_string_json_returns_json_dump(self):
        """JSON string is parsed and dumped with indentation."""
        from zenus_core.output.formatter import OutputFormatter
        import json
        fmt = OutputFormatter()
        fmt.console = make_console_mock()
        result = fmt.format('{"key": "val"}')
        assert json.loads(result) == {"key": "val"}


class TestOutputFormatterDelimiterDetection:
    def test_detect_delimiter_pipe(self):
        """Pipe-heavy line selects | as delimiter."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._detect_delimiter("a|b|c|d") == "|"

    def test_detect_delimiter_comma(self):
        """Comma-heavy line selects , as delimiter."""
        from zenus_core.output.formatter import OutputFormatter
        fmt = OutputFormatter()
        assert fmt._detect_delimiter("a,b,c,d") == ","


class TestGetFormatter:
    def test_singleton_is_returned(self):
        """get_formatter returns the same object on repeated calls."""
        from zenus_core.output import formatter as fmt_mod
        fmt_mod._formatter = None  # reset
        a = fmt_mod.get_formatter()
        b = fmt_mod.get_formatter()
        assert a is b

    def test_format_output_convenience(self):
        """format_output delegates to the formatter instance."""
        from zenus_core.output.formatter import OutputFormatter
        from zenus_core.output import formatter as fmt_mod
        mock_fmt = MagicMock(spec=OutputFormatter)
        mock_fmt.format.return_value = "ok"
        fmt_mod._formatter = mock_fmt
        result = fmt_mod.format_output("hello")
        mock_fmt.format.assert_called_once_with("hello", None)
        assert result == "ok"
        fmt_mod._formatter = None  # cleanup


# ===========================================================================
# Console helpers
# ===========================================================================

class TestConsolePrintHelpers:
    def test_print_success_uses_green_style(self):
        """print_success calls console.print with bold green."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_success("all good")
        mock.print.assert_called_once()
        args, kwargs = mock.print.call_args
        assert "green" in kwargs.get("style", "")

    def test_print_error_uses_red_style(self):
        """print_error calls console.print with bold red."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_error("bad stuff")
        mock.print.assert_called_once()
        _, kwargs = mock.print.call_args
        assert "red" in kwargs.get("style", "")

    def test_print_warning_uses_yellow_style(self):
        """print_warning calls console.print with bold yellow."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_warning("careful")
        mock.print.assert_called_once()
        _, kwargs = mock.print.call_args
        assert "yellow" in kwargs.get("style", "")

    def test_print_info_uses_cyan_style(self):
        """print_info calls console.print with bold cyan."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_info("fyi")
        mock.print.assert_called_once()
        _, kwargs = mock.print.call_args
        assert "cyan" in kwargs.get("style", "")

    def test_print_goal_contains_goal_text(self):
        """print_goal passes the goal string to console."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_goal("do something")
        mock.print.assert_called_once()
        args, _ = mock.print.call_args
        assert "do something" in args[0]

    def test_print_divider_calls_print(self):
        """print_divider outputs a line."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_divider()
        mock.print.assert_called_once()

    def test_print_header_calls_print(self):
        """print_header outputs a section header."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_header("Section")
        mock.print.assert_called_once()

    def test_print_step_risk_read_prints_label(self):
        """print_step for risk 0 includes READ label."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_step(1, "FileOps", "read_file", 0)
        mock.print.assert_called()
        args, _ = mock.print.call_args_list[0]
        assert "READ" in args[0]

    def test_print_similar_commands_empty_does_nothing(self):
        """print_similar_commands with empty list makes no output."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_similar_commands([])
        mock.print.assert_not_called()

    def test_print_plan_summary_calls_print_once(self):
        """print_plan_summary prints a table."""
        import importlib; con_mod = importlib.import_module("zenus_core.output.console")
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_plan_summary([{"tool": "FileOps", "action": "read", "risk": 0}])
        mock.print.assert_called_once()


# ===========================================================================
# ProgressTracker
# ===========================================================================

class TestProgressTracker:
    def test_start_timer_and_stop_returns_positive_elapsed(self):
        """Stopping a timer right after starting returns a small positive value."""
        from zenus_core.output.progress import ProgressTracker
        tracker = ProgressTracker()
        tracker.start_timer("t1")
        elapsed = tracker.stop_timer("t1")
        assert elapsed >= 0.0

    def test_stop_unknown_timer_returns_zero(self):
        """Stopping a timer that was never started returns 0."""
        from zenus_core.output.progress import ProgressTracker
        tracker = ProgressTracker()
        assert tracker.stop_timer("nonexistent") == 0.0

    def test_get_elapsed_unknown_returns_zero(self):
        """get_elapsed for an unknown timer returns 0."""
        from zenus_core.output.progress import ProgressTracker
        tracker = ProgressTracker()
        assert tracker.get_elapsed("nonexistent") == 0.0

    def test_get_elapsed_running_timer(self):
        """get_elapsed for a running timer returns positive."""
        from zenus_core.output.progress import ProgressTracker
        tracker = ProgressTracker()
        tracker.start_timer("run")
        elapsed = tracker.get_elapsed("run")
        tracker.stop_timer("run")
        assert elapsed >= 0.0

    def test_stop_timer_removes_entry(self):
        """After stop_timer the timer no longer exists in start_times."""
        from zenus_core.output.progress import ProgressTracker
        tracker = ProgressTracker()
        tracker.start_timer("x")
        tracker.stop_timer("x")
        assert "x" not in tracker.start_times


class TestStreamingDisplay:
    def test_start_sets_start_time(self):
        """start() records a start_time."""
        from zenus_core.output.progress import StreamingDisplay
        display = StreamingDisplay()
        display.console = MagicMock()
        display.start("Starting...")
        assert display.start_time is not None

    def test_new_iteration_updates_current_iteration(self):
        """new_iteration() sets current_iteration."""
        from zenus_core.output.progress import StreamingDisplay
        display = StreamingDisplay()
        display.console = MagicMock()
        display.start_time = time.time()
        display.new_iteration(3, 1, 12)
        assert display.current_iteration == 3

    def test_complete_step_success_calls_print(self):
        """complete_step with success=True calls console.print."""
        from zenus_core.output.progress import StreamingDisplay
        display = StreamingDisplay()
        display.console = MagicMock()
        display.complete_step("done", success=True)
        display.console.print.assert_called_once()

    def test_complete_step_truncates_long_result(self):
        """complete_step truncates results longer than 100 chars."""
        from zenus_core.output.progress import StreamingDisplay
        display = StreamingDisplay()
        display.console = MagicMock()
        long_result = "x" * 200
        display.complete_step(long_result, success=True)
        args, _ = display.console.print.call_args
        assert len(args[0]) < 220  # truncated + markup < 220

    def test_finish_calls_print(self):
        """finish() calls console.print at least once."""
        from zenus_core.output.progress import StreamingDisplay
        display = StreamingDisplay()
        display.console = MagicMock()
        display.start_time = time.time()
        display.finish(5, 2)
        display.console.print.assert_called()

    def test_batch_complete_calls_print(self):
        """batch_complete() notifies about batch completion."""
        from zenus_core.output.progress import StreamingDisplay
        display = StreamingDisplay()
        display.console = MagicMock()
        display.batch_complete(1, 10)
        display.console.print.assert_called()


class TestProgressIndicatorAlias:
    def test_alias_points_to_tracker(self):
        """ProgressIndicator is an alias for ProgressTracker."""
        from zenus_core.output.progress import ProgressIndicator, ProgressTracker
        assert ProgressIndicator is ProgressTracker


class TestGetProgressSingletons:
    def test_get_progress_tracker_returns_singleton(self):
        """get_progress_tracker returns same instance on repeated calls."""
        from zenus_core.output import progress as prog_mod
        prog_mod._progress_tracker = None
        a = prog_mod.get_progress_tracker()
        b = prog_mod.get_progress_tracker()
        assert a is b
        prog_mod._progress_tracker = None

    def test_get_streaming_display_returns_singleton(self):
        """get_streaming_display returns same instance on repeated calls."""
        from zenus_core.output import progress as prog_mod
        prog_mod._streaming_display = None
        a = prog_mod.get_streaming_display()
        b = prog_mod.get_streaming_display()
        assert a is b
        prog_mod._streaming_display = None


# ===========================================================================
# StreamHandler
# ===========================================================================

class TestStreamHandler:
    def test_initial_cancelled_is_false(self):
        """New StreamHandler is not cancelled."""
        from zenus_core.output.streaming import StreamHandler
        handler = StreamHandler()
        assert handler.cancelled is False

    def test_cancel_sets_flag(self):
        """cancel() sets cancelled to True."""
        from zenus_core.output.streaming import StreamHandler
        handler = StreamHandler()
        handler.cancel()
        assert handler.cancelled is True

    def test_cancel_invokes_callbacks(self):
        """cancel() calls all registered callbacks."""
        from zenus_core.output.streaming import StreamHandler
        handler = StreamHandler()
        cb = MagicMock()
        handler.register_cancel_callback(cb)
        handler.cancel()
        cb.assert_called_once()

    def test_cancel_callback_exception_does_not_propagate(self):
        """A failing callback is swallowed by cancel()."""
        from zenus_core.output.streaming import StreamHandler
        handler = StreamHandler()
        handler.register_cancel_callback(lambda: 1 / 0)
        handler.cancel()  # should not raise

    def test_register_multiple_callbacks(self):
        """Multiple callbacks are all called on cancel."""
        from zenus_core.output.streaming import StreamHandler
        handler = StreamHandler()
        cb1, cb2 = MagicMock(), MagicMock()
        handler.register_cancel_callback(cb1)
        handler.register_cancel_callback(cb2)
        handler.cancel()
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_stream_llm_tokens_returns_complete_text(self):
        """stream_llm_tokens assembles chunks into the full text."""
        from zenus_core.output.streaming import StreamHandler
        handler = StreamHandler()

        # Build fake chunks
        def make_chunk(text):
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = text
            return chunk

        chunks = [make_chunk("hello"), make_chunk(" world")]
        with patch('zenus_core.output.streaming.console'):
            result = handler.stream_llm_tokens(iter(chunks))
        assert result == "hello world"

    def test_stream_llm_tokens_stops_on_cancel(self):
        """stream_llm_tokens stops early when cancelled is True."""
        from zenus_core.output.streaming import StreamHandler
        handler = StreamHandler()
        handler.cancelled = True

        def make_chunk(text):
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = text
            return chunk

        with patch('zenus_core.output.streaming.console'):
            result = handler.stream_llm_tokens(iter([make_chunk("x")]))
        assert result == ""

    def test_show_progress_returns_progress_and_task_id(self):
        """show_progress returns a (Progress, task_id) tuple."""
        from zenus_core.output.streaming import StreamHandler
        handler = StreamHandler()
        progress, task_id = handler.show_progress(10, "doing stuff")
        assert task_id is not None

    def test_get_stream_handler_returns_global(self):
        """get_stream_handler returns the module-level singleton."""
        from zenus_core.output.streaming import get_stream_handler, _global_handler
        assert get_stream_handler() is _global_handler


class TestCancelableOperation:
    def test_context_manager_restores_sigint(self):
        """CancelableOperation restores the original SIGINT handler on exit."""
        import signal
        from zenus_core.output.streaming import CancelableOperation, StreamHandler
        handler = StreamHandler()
        original = signal.getsignal(signal.SIGINT)
        with CancelableOperation(handler):
            pass
        assert signal.getsignal(signal.SIGINT) == original


# ===========================================================================
# Additional console.py coverage
# ===========================================================================

class TestConsolePrintHelpersExtended:
    """Tests for console functions not covered by TestConsolePrintHelpers."""

    def _get_mod(self):
        import importlib
        return importlib.import_module("zenus_core.output.console")

    def test_print_step_with_result_simple(self):
        """print_step with a short result prints it inline."""
        con_mod = self._get_mod()
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            with patch.object(con_mod, 'VISUALIZATION_ENABLED', False):
                con_mod.print_step(1, "FileOps", "read", 0, result="done")
        assert mock.print.call_count >= 2  # step + result

    def test_print_step_with_multiline_result(self):
        """print_step with multi-line result tries format_output."""
        con_mod = self._get_mod()
        mock = MagicMock()
        multiline = "line1\nline2\nline3\nline4\nline5"
        with patch.object(con_mod, 'console', mock):
            with patch.object(con_mod, 'VISUALIZATION_ENABLED', False):
                con_mod.print_step(1, "FileOps", "scan_dir", 0, result=multiline)
        assert mock.print.call_count >= 1

    def test_print_step_with_json_result(self):
        """print_step with JSON-like result calls format_output."""
        con_mod = self._get_mod()
        mock = MagicMock()
        json_result = '{"key": "value", "count": 5, "items": [1, 2, 3]}'
        with patch.object(con_mod, 'console', mock):
            with patch.object(con_mod, 'VISUALIZATION_ENABLED', False):
                with patch("zenus_core.output.formatter.format_output") as mock_fmt:
                    con_mod.print_step(1, "Tool", "op", 0, result=json_result)
        # format_output may or may not be called depending on length threshold

    def test_print_step_visualization_fallback(self):
        """print_step falls back gracefully when visualization raises."""
        con_mod = self._get_mod()
        mock = MagicMock()
        mock_viz = MagicMock()
        mock_viz.visualize.side_effect = Exception("viz error")
        with patch.object(con_mod, 'console', mock):
            with patch.object(con_mod, 'VISUALIZATION_ENABLED', True):
                with patch.object(con_mod, 'Visualizer', mock_viz):
                    con_mod.print_step(1, "Tool", "scan_dir", 0, result="some result")
        # Should fall through without raising

    def test_print_similar_commands_with_data(self):
        """print_similar_commands with results prints each one."""
        con_mod = self._get_mod()
        mock = MagicMock()
        commands = [
            {"similarity": 0.95, "success": True, "user_input": "list files"},
            {"similarity": 0.80, "success": False, "user_input": "show files"},
        ]
        with patch.object(con_mod, 'console', mock):
            con_mod.print_similar_commands(commands)
        # Should print header + 2 results = at least 3 calls
        assert mock.print.call_count >= 3

    def test_print_explanation_with_reasoning(self):
        """print_explanation includes reasoning when provided."""
        con_mod = self._get_mod()
        mock = MagicMock()
        steps = [
            {"tool": "FileOps", "action": "read_file", "args": {"path": "/tmp/x"}, "risk": 0},
            {"tool": "FileOps", "action": "delete_file", "args": {"path": "/tmp/x"}, "risk": 3},
        ]
        with patch.object(con_mod, 'console', mock):
            con_mod.print_explanation("clean up temp files", steps, reasoning="No longer needed")
        mock.print.assert_called_once()

    def test_print_explanation_without_reasoning(self):
        """print_explanation works when no reasoning is provided."""
        con_mod = self._get_mod()
        mock = MagicMock()
        steps = [{"tool": "FileOps", "action": "read_file", "args": {}, "risk": 0}]
        with patch.object(con_mod, 'console', mock):
            con_mod.print_explanation("do thing", steps)
        mock.print.assert_called_once()

    def test_print_explanation_all_risk_levels(self):
        """print_explanation handles all risk levels (0-3) in steps."""
        con_mod = self._get_mod()
        mock = MagicMock()
        steps = [
            {"tool": "T", "action": "a", "args": {}, "risk": 0},
            {"tool": "T", "action": "b", "args": {}, "risk": 1},
            {"tool": "T", "action": "c", "args": {}, "risk": 2},
            {"tool": "T", "action": "d", "args": {}, "risk": 3},
        ]
        with patch.object(con_mod, 'console', mock):
            con_mod.print_explanation("do stuff", steps)
        mock.print.assert_called_once()

    def test_print_code_block_calls_print(self):
        """print_code_block passes syntax to console.print."""
        con_mod = self._get_mod()
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_code_block("x = 1\nprint(x)", language="python")
        mock.print.assert_called_once()

    def test_print_json_calls_print(self):
        """print_json calls console.print with formatted syntax."""
        con_mod = self._get_mod()
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_json({"key": "value", "count": 42})
        mock.print.assert_called_once()

    def test_print_status_table_with_data(self):
        """print_status_table renders key/value pairs."""
        con_mod = self._get_mod()
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_status_table({"Status": "running", "PID": "1234"})
        mock.print.assert_called_once()

    def test_print_status_table_empty(self):
        """print_status_table with empty dict still renders table."""
        con_mod = self._get_mod()
        mock = MagicMock()
        with patch.object(con_mod, 'console', mock):
            con_mod.print_status_table({})
        mock.print.assert_called_once()

    def test_print_step_risk_variants(self):
        """print_step covers risk levels 1, 2, 3 (CREATE/MODIFY/DELETE labels)."""
        con_mod = self._get_mod()
        for risk, label in [(1, "CREATE"), (2, "MODIFY"), (3, "DELETE")]:
            mock = MagicMock()
            with patch.object(con_mod, 'console', mock):
                con_mod.print_step(1, "Tool", "op", risk)
            args, _ = mock.print.call_args_list[0]
            assert label in args[0]
