"""
Unit tests for execution/error_recovery.py

input() and time.sleep() are fully mocked.
"""

import pytest
from unittest.mock import Mock, patch, call
from zenus_core.execution.error_recovery import (
    ErrorRecovery,
    RecoveryResult,
    RecoveryStrategy,
    get_error_recovery,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_recovery(max_retries=3, backoff_base=2.0):
    return ErrorRecovery(max_retries=max_retries, backoff_base=backoff_base)


def _ctx(tool="FileOps", action="write", args=None):
    return {"tool": tool, "action": action, "args": args or {}}


# ===========================================================================
# RecoveryResult dataclass
# ===========================================================================

class TestRecoveryResult:

    def test_defaults(self):
        r = RecoveryResult(
            success=True,
            strategy=RecoveryStrategy.RETRY,
            message="ok"
        )
        assert r.retry_count == 0
        assert r.alternative_used is None

    def test_all_fields(self):
        r = RecoveryResult(
            success=False,
            strategy=RecoveryStrategy.ABORT,
            message="aborted",
            retry_count=3,
            alternative_used="fallback"
        )
        assert r.retry_count == 3
        assert r.alternative_used == "fallback"


# ===========================================================================
# RecoveryStrategy enum
# ===========================================================================

class TestRecoveryStrategy:

    def test_strategy_values(self):
        assert RecoveryStrategy.RETRY.value == "retry"
        assert RecoveryStrategy.SKIP.value == "skip"
        assert RecoveryStrategy.SUBSTITUTE.value == "substitute"
        assert RecoveryStrategy.ASK_USER.value == "ask_user"
        assert RecoveryStrategy.ROLLBACK.value == "rollback"
        assert RecoveryStrategy.ABORT.value == "abort"


# ===========================================================================
# ErrorRecovery.__init__
# ===========================================================================

class TestErrorRecoveryInit:

    def test_defaults(self):
        er = ErrorRecovery()
        assert er.max_retries == 3
        assert er.backoff_base == 2.0

    def test_custom_params(self):
        er = ErrorRecovery(max_retries=5, backoff_base=1.5)
        assert er.max_retries == 5
        assert er.backoff_base == 1.5

    def test_initial_stats_zero(self):
        er = ErrorRecovery()
        stats = er.get_stats()
        for v in stats.values():
            assert v == 0


# ===========================================================================
# _retry_with_backoff
# ===========================================================================

class TestRetryWithBackoff:

    def test_success_on_first_retry(self):
        er = _make_recovery(max_retries=3, backoff_base=1.0)
        op = Mock(return_value="ok")

        with patch("time.sleep"):
            result = er._retry_with_backoff(op, _ctx())

        assert result.success is True
        assert result.strategy == RecoveryStrategy.RETRY
        assert result.retry_count == 1
        assert er.recovery_stats["retries"] == 1

    def test_success_on_second_retry(self):
        er = _make_recovery(max_retries=3, backoff_base=1.0)
        op = Mock(side_effect=[ValueError("fail"), "ok"])

        with patch("time.sleep"):
            result = er._retry_with_backoff(op, _ctx())

        assert result.success is True
        assert result.retry_count == 2

    def test_all_retries_fail(self):
        er = _make_recovery(max_retries=2, backoff_base=1.0)
        op = Mock(side_effect=ValueError("always fails"))

        with patch("time.sleep"):
            result = er._retry_with_backoff(op, _ctx())

        assert result.success is False
        assert result.retry_count == 2
        assert "failed after" in result.message.lower()

    def test_backoff_sleep_called(self):
        er = _make_recovery(max_retries=2, backoff_base=2.0)
        op = Mock(side_effect=[Exception("fail"), "ok"])

        with patch("time.sleep") as mock_sleep:
            er._retry_with_backoff(op, _ctx())

        # sleep is called once per attempt; first call is sleep(2**0)=1.0
        assert mock_sleep.call_count >= 1
        assert mock_sleep.call_args_list[0] == call(1.0)

    def test_passes_args_and_kwargs(self):
        er = _make_recovery(max_retries=1, backoff_base=1.0)
        op = Mock(return_value="result")

        with patch("time.sleep"):
            er._retry_with_backoff(op, _ctx(), "arg1", key="val")

        op.assert_called_with("arg1", key="val")


# ===========================================================================
# _request_permission
# ===========================================================================

class TestRequestPermission:

    def test_user_grants_permission(self):
        er = _make_recovery()
        with patch("builtins.input", return_value="y"):
            result = er._request_permission(_ctx())
        assert result.strategy == RecoveryStrategy.ASK_USER
        assert er.recovery_stats["user_interventions"] == 1

    def test_user_skips(self):
        er = _make_recovery()
        with patch("builtins.input", return_value="s"):
            result = er._request_permission(_ctx())
        assert result.success is True
        assert result.strategy == RecoveryStrategy.SKIP
        assert er.recovery_stats["skips"] == 1

    def test_user_aborts(self):
        er = _make_recovery()
        with patch("builtins.input", return_value="n"):
            result = er._request_permission(_ctx())
        assert result.success is False
        assert result.strategy == RecoveryStrategy.ABORT
        assert er.recovery_stats["aborts"] == 1

    def test_empty_input_aborts(self):
        er = _make_recovery()
        with patch("builtins.input", return_value=""):
            result = er._request_permission(_ctx())
        assert result.strategy == RecoveryStrategy.ABORT


# ===========================================================================
# _handle_missing_resource
# ===========================================================================

class TestHandleMissingResource:

    def test_user_skips(self):
        er = _make_recovery()
        err = FileNotFoundError("'/tmp/missing.txt' not found")
        with patch("builtins.input", return_value="y"):
            result = er._handle_missing_resource(err, _ctx())
        assert result.success is True
        assert result.strategy == RecoveryStrategy.SKIP
        assert er.recovery_stats["skips"] == 1

    def test_empty_input_skips(self):
        er = _make_recovery()
        err = FileNotFoundError("'/tmp/missing.txt' not found")
        with patch("builtins.input", return_value=""):
            result = er._handle_missing_resource(err, _ctx())
        assert result.success is True

    def test_user_aborts(self):
        er = _make_recovery()
        err = FileNotFoundError("missing file")
        with patch("builtins.input", return_value="a"):
            result = er._handle_missing_resource(err, _ctx())
        assert result.success is False
        assert result.strategy == RecoveryStrategy.ABORT
        assert er.recovery_stats["aborts"] == 1


# ===========================================================================
# _handle_missing_dependency
# ===========================================================================

class TestHandleMissingDependency:

    def test_skips_operation(self):
        er = _make_recovery()
        err = ImportError("No module named 'requests'")
        result = er._handle_missing_dependency(err, _ctx())
        assert result.success is True
        assert result.strategy == RecoveryStrategy.SKIP
        assert er.recovery_stats["skips"] == 1

    def test_message_contains_module_name(self):
        er = _make_recovery()
        err = ImportError("No module named 'numpy'")
        result = er._handle_missing_dependency(err, _ctx())
        assert "numpy" in result.message


# ===========================================================================
# _handle_missing_key
# ===========================================================================

class TestHandleMissingKey:

    def test_continues_without_key(self):
        er = _make_recovery()
        err = KeyError("some_key")
        result = er._handle_missing_key(err, _ctx())
        assert result.success is True
        assert result.strategy == RecoveryStrategy.SKIP
        assert er.recovery_stats["skips"] == 1

    def test_message_contains_key_name(self):
        er = _make_recovery()
        err = KeyError("missing_key")
        result = er._handle_missing_key(err, _ctx())
        assert "missing_key" in result.message


# ===========================================================================
# _handle_rate_limit
# ===========================================================================

class TestHandleRateLimit:

    def test_success_after_wait(self):
        er = _make_recovery()
        op = Mock(return_value="ok")
        with patch("time.sleep") as mock_sleep:
            result = er._handle_rate_limit(op, _ctx())
        assert result.success is True
        assert result.strategy == RecoveryStrategy.RETRY
        assert result.retry_count == 1
        mock_sleep.assert_called_once_with(60)
        assert er.recovery_stats["retries"] == 1

    def test_failure_after_wait(self):
        er = _make_recovery()
        op = Mock(side_effect=Exception("still rate limited"))
        with patch("time.sleep"):
            result = er._handle_rate_limit(op, _ctx())
        assert result.success is False
        assert result.retry_count == 1


# ===========================================================================
# _handle_unknown_error
# ===========================================================================

class TestHandleUnknownError:

    def test_user_continues(self):
        er = _make_recovery()
        err = RuntimeError("unexpected")
        with patch("builtins.input", return_value="y"):
            result = er._handle_unknown_error(err, _ctx())
        assert result.success is True
        assert result.strategy == RecoveryStrategy.SKIP
        assert er.recovery_stats["skips"] == 1

    def test_empty_input_continues(self):
        er = _make_recovery()
        err = RuntimeError("unexpected")
        with patch("builtins.input", return_value=""):
            result = er._handle_unknown_error(err, _ctx())
        assert result.success is True

    def test_user_aborts(self):
        er = _make_recovery()
        err = RuntimeError("unexpected")
        with patch("builtins.input", return_value="n"):
            result = er._handle_unknown_error(err, _ctx())
        assert result.success is False
        assert result.strategy == RecoveryStrategy.ABORT
        assert er.recovery_stats["aborts"] == 1


# ===========================================================================
# recover – dispatch
# ===========================================================================

class TestRecoverDispatch:

    def test_timeout_error_dispatches_retry(self):
        er = _make_recovery(max_retries=1, backoff_base=1.0)
        op = Mock(return_value="ok")
        with patch("time.sleep"):
            result = er.recover(TimeoutError("timed out"), _ctx(), op)
        assert result.strategy == RecoveryStrategy.RETRY

    def test_connection_error_dispatches_retry(self):
        er = _make_recovery(max_retries=1, backoff_base=1.0)
        op = Mock(return_value="ok")
        with patch("time.sleep"):
            result = er.recover(ConnectionError("conn refused"), _ctx(), op)
        assert result.strategy == RecoveryStrategy.RETRY

    def test_permission_error_dispatches_permission(self):
        er = _make_recovery()
        with patch("builtins.input", return_value="s"):
            result = er.recover(PermissionError("denied"), _ctx(), Mock())
        assert result.strategy == RecoveryStrategy.SKIP

    def test_file_not_found_dispatches_missing_resource(self):
        er = _make_recovery()
        with patch("builtins.input", return_value="y"):
            result = er.recover(FileNotFoundError("'file.txt'"), _ctx(), Mock())
        assert result.strategy == RecoveryStrategy.SKIP

    def test_import_error_dispatches_missing_dependency(self):
        er = _make_recovery()
        result = er.recover(ImportError("No module named 'foo'"), _ctx(), Mock())
        assert result.strategy == RecoveryStrategy.SKIP

    def test_module_not_found_dispatches_missing_dependency(self):
        er = _make_recovery()
        result = er.recover(ModuleNotFoundError("No module named 'bar'"), _ctx(), Mock())
        assert result.strategy == RecoveryStrategy.SKIP

    def test_key_error_dispatches_missing_key(self):
        er = _make_recovery()
        result = er.recover(KeyError("missing"), _ctx(), Mock())
        assert result.strategy == RecoveryStrategy.SKIP

    def test_rate_limit_string_dispatches_rate_limit(self):
        er = _make_recovery()
        err = Exception("API rate limit exceeded")
        op = Mock(return_value="ok")
        with patch("time.sleep"):
            result = er.recover(err, _ctx(), op)
        assert result.strategy == RecoveryStrategy.RETRY

    def test_unknown_error_dispatches_unknown(self):
        er = _make_recovery()
        with patch("builtins.input", return_value="y"):
            result = er.recover(ValueError("something"), _ctx(), Mock())
        assert result.strategy == RecoveryStrategy.SKIP

    def test_recover_passes_args_to_operation(self):
        er = _make_recovery(max_retries=1, backoff_base=1.0)
        op = Mock(return_value="ok")
        with patch("time.sleep"):
            er.recover(TimeoutError("t"), _ctx(), op, "a1", k="v1")
        op.assert_called_with("a1", k="v1")


# ===========================================================================
# get_stats
# ===========================================================================

class TestGetStats:

    def test_returns_copy(self):
        er = _make_recovery()
        stats1 = er.get_stats()
        stats1["retries"] = 999
        stats2 = er.get_stats()
        assert stats2["retries"] == 0

    def test_stats_all_keys_present(self):
        er = _make_recovery()
        stats = er.get_stats()
        expected_keys = {"retries", "skips", "substitutions", "user_interventions",
                         "rollbacks", "aborts"}
        assert expected_keys.issubset(set(stats.keys()))

    def test_stats_accumulate(self):
        er = _make_recovery()
        with patch("builtins.input", return_value="s"):
            er._request_permission(_ctx())  # skip
        with patch("builtins.input", return_value="s"):
            er._request_permission(_ctx())  # skip again
        assert er.get_stats()["skips"] == 2


# ===========================================================================
# get_error_recovery singleton
# ===========================================================================

class TestGetErrorRecovery:

    def test_returns_error_recovery_instance(self):
        # Reset singleton
        import zenus_core.execution.error_recovery as mod
        mod._recovery_instance = None
        er = get_error_recovery()
        assert isinstance(er, ErrorRecovery)

    def test_returns_same_instance(self):
        import zenus_core.execution.error_recovery as mod
        mod._recovery_instance = None
        er1 = get_error_recovery()
        er2 = get_error_recovery()
        assert er1 is er2
