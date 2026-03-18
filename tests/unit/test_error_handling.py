"""
Tests for circuit breaker, fallback chain, and retry budget.
"""

import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from zenus_core.error.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
    get_circuit_breaker,
    reset_all_circuit_breakers,
    _circuit_breakers,
)
from zenus_core.error.fallback import (
    Fallback,
    FallbackStrategy,
    FallbackOption,
    AllFallbacksFailedError,
    create_llm_fallback,
    get_fallback,
    register_fallback,
    _rule_based_fallback,
    _fallbacks,
)
from zenus_core.error.retry_budget import (
    RetryBudget,
    RetryConfig,
    RetryExhaustedError,
    RetryBudgetExceededError,
    retry_with_budget,
    get_retry_budget,
    reset_all_budgets,
    get_budget_stats,
    _retry_budgets,
)


# ---------------------------------------------------------------------------
# CircuitBreaker tests
# ---------------------------------------------------------------------------

class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig dataclass"""

    def test_defaults(self):
        """CircuitBreakerConfig should have correct default values"""
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.timeout_seconds == 60.0
        assert cfg.success_threshold == 2
        assert cfg.window_seconds == 300.0

    def test_custom_values(self):
        """CircuitBreakerConfig accepts custom values"""
        cfg = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=10.0)
        assert cfg.failure_threshold == 3
        assert cfg.timeout_seconds == 10.0


class TestCircuitBreakerInitialState:
    """Test initial state of a new CircuitBreaker"""

    def test_initial_state_is_closed(self):
        """New circuit breaker should start in CLOSED state"""
        cb = CircuitBreaker("test")
        assert cb.get_state() == CircuitState.CLOSED

    def test_initial_stats(self):
        """New circuit breaker stats should all be zero/None"""
        cb = CircuitBreaker("test")
        stats = cb.get_stats()
        assert stats["state"] == CircuitState.CLOSED.value
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        assert stats["total_requests"] == 0
        assert stats["total_failures"] == 0
        assert stats["total_successes"] == 0
        assert stats["failure_rate"] == 0.0
        assert stats["last_failure"] is None
        assert stats["last_success"] is None


class TestCircuitBreakerClosedState:
    """Test CircuitBreaker behaviour in CLOSED state"""

    def test_successful_call_passes_through(self):
        """A successful function call returns the function's result"""
        cb = CircuitBreaker("test")
        result = cb.call(lambda: "ok")
        assert result == "ok"

    def test_successful_call_increments_totals(self):
        """Each successful call increments total_requests and total_successes"""
        cb = CircuitBreaker("test")
        cb.call(lambda: None)
        cb.call(lambda: None)
        stats = cb.get_stats()
        assert stats["total_requests"] == 2
        assert stats["total_successes"] == 2

    def test_failed_call_increments_failure_count(self):
        """A failed call increments the failure_count and total_failures"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=10))

        def boom():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            cb.call(boom)

        stats = cb.get_stats()
        assert stats["failure_count"] == 1
        assert stats["total_failures"] == 1

    def test_success_resets_failure_count(self):
        """A success in CLOSED state resets the rolling failure_count"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=10))

        def boom():
            raise ValueError()

        # Record two failures then one success
        with pytest.raises(ValueError):
            cb.call(boom)
        with pytest.raises(ValueError):
            cb.call(boom)

        cb.call(lambda: None)
        assert cb.stats.failure_count == 0

    def test_opens_after_threshold(self):
        """Circuit opens after failure_threshold consecutive failures"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))

        def boom():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(boom)

        assert cb.get_state() == CircuitState.OPEN

    def test_failure_rate_calculation(self):
        """failure_rate stat is computed correctly"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=10))
        cb.call(lambda: None)

        def boom():
            raise RuntimeError()

        with pytest.raises(RuntimeError):
            cb.call(boom)

        stats = cb.get_stats()
        assert stats["failure_rate"] == pytest.approx(0.5)


class TestCircuitBreakerOpenState:
    """Test CircuitBreaker behaviour when OPEN"""

    def _open_circuit(self, cb: CircuitBreaker):
        def boom():
            raise RuntimeError("fail")

        for _ in range(cb.config.failure_threshold):
            with pytest.raises(RuntimeError):
                cb.call(boom)

    def test_open_circuit_rejects_calls(self):
        """Calls to an open circuit raise CircuitBreakerOpenError immediately"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
        self._open_circuit(cb)
        assert cb.get_state() == CircuitState.OPEN

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: None)

    def test_open_circuit_error_message(self):
        """CircuitBreakerOpenError message includes the breaker name"""
        cb = CircuitBreaker("my-service", CircuitBreakerConfig(failure_threshold=2))
        self._open_circuit(cb)

        with pytest.raises(CircuitBreakerOpenError, match="my-service"):
            cb.call(lambda: None)

    def test_total_requests_still_incremented_when_open(self):
        """total_requests is incremented even when the circuit is open"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
        self._open_circuit(cb)
        total_before = cb.stats.total_requests

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: None)

        assert cb.stats.total_requests == total_before + 1

    def test_transitions_to_half_open_after_timeout(self):
        """Circuit moves to HALF_OPEN when timeout has elapsed"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2, timeout_seconds=0.0))
        self._open_circuit(cb)

        # Backdate opened_at so timeout is considered elapsed
        cb.stats.opened_at = datetime.now() - timedelta(seconds=1)
        cb.call(lambda: None)  # This should transition to HALF_OPEN, then succeed
        # After a success in HALF_OPEN it eventually closes; the key assertion is
        # that the call did NOT raise CircuitBreakerOpenError
        assert cb.get_state() in (CircuitState.HALF_OPEN, CircuitState.CLOSED)


class TestCircuitBreakerHalfOpenState:
    """Test CircuitBreaker behaviour in HALF_OPEN state"""

    def _force_half_open(self, cb: CircuitBreaker):
        """Helper: put the circuit directly into HALF_OPEN."""
        cb.stats.state = CircuitState.OPEN
        cb.stats.opened_at = datetime.now() - timedelta(seconds=9999)

    def test_success_in_half_open_increments_success_count(self):
        """Successes in HALF_OPEN increment the success_count"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(success_threshold=3))
        self._force_half_open(cb)

        cb.call(lambda: None)
        assert cb.stats.success_count == 1

    def test_closes_after_success_threshold(self):
        """Circuit closes once success_threshold successes accumulate in HALF_OPEN"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(success_threshold=2))
        self._force_half_open(cb)

        cb.call(lambda: None)
        cb.call(lambda: None)

        assert cb.get_state() == CircuitState.CLOSED

    def test_failure_in_half_open_reopens(self):
        """A single failure in HALF_OPEN re-opens the circuit"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(success_threshold=5))
        self._force_half_open(cb)

        # Trigger transition to HALF_OPEN via a successful call that gets in
        # Force state directly instead
        cb.stats.state = CircuitState.HALF_OPEN

        def boom():
            raise RuntimeError()

        with pytest.raises(RuntimeError):
            cb.call(boom)

        assert cb.get_state() == CircuitState.OPEN

    def test_closed_circuit_resets_counters(self):
        """_close_circuit() clears failure and success counts and opened_at"""
        cb = CircuitBreaker("test")
        cb.stats.failure_count = 3
        cb.stats.success_count = 2
        cb.stats.opened_at = datetime.now()

        cb._close_circuit()

        assert cb.stats.failure_count == 0
        assert cb.stats.success_count == 0
        assert cb.stats.opened_at is None
        assert cb.get_state() == CircuitState.CLOSED


class TestCircuitBreakerReset:
    """Test manual reset of the CircuitBreaker"""

    def test_reset_from_open(self):
        """reset() closes an open circuit"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))

        def boom():
            raise RuntimeError()

        with pytest.raises(RuntimeError):
            cb.call(boom)

        assert cb.get_state() == CircuitState.OPEN
        cb.reset()
        assert cb.get_state() == CircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        """reset() clears the failure_count"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=10))

        def boom():
            raise RuntimeError()

        with pytest.raises(RuntimeError):
            cb.call(boom)

        cb.reset()
        assert cb.stats.failure_count == 0


class TestCircuitBreakerStats:
    """Test get_stats() output"""

    def test_stats_zero_requests_failure_rate(self):
        """failure_rate is 0.0 when there have been no requests"""
        cb = CircuitBreaker("test")
        assert cb.get_stats()["failure_rate"] == 0.0

    def test_stats_last_failure_is_iso_string(self):
        """last_failure is an ISO-format string after a failure"""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=10))

        def boom():
            raise RuntimeError()

        with pytest.raises(RuntimeError):
            cb.call(boom)

        last = cb.get_stats()["last_failure"]
        assert last is not None
        # Should be parseable as an ISO datetime
        datetime.fromisoformat(last)

    def test_stats_last_success_is_iso_string(self):
        """last_success is an ISO-format string after a success"""
        cb = CircuitBreaker("test")
        cb.call(lambda: None)
        last = cb.get_stats()["last_success"]
        assert last is not None
        datetime.fromisoformat(last)


class TestCircuitBreakerRegistry:
    """Test module-level get_circuit_breaker and reset_all"""

    def setup_method(self):
        """Clear global registry before each test"""
        _circuit_breakers.clear()

    def test_get_creates_new_instance(self):
        """get_circuit_breaker() creates a new instance for unknown names"""
        cb = get_circuit_breaker("svc-a")
        assert isinstance(cb, CircuitBreaker)
        assert cb.name == "svc-a"

    def test_get_returns_existing_instance(self):
        """get_circuit_breaker() returns the same instance on repeated calls"""
        cb1 = get_circuit_breaker("svc-b")
        cb2 = get_circuit_breaker("svc-b")
        assert cb1 is cb2

    def test_reset_all_resets_each_breaker(self):
        """reset_all_circuit_breakers() closes every registered breaker"""
        cb = get_circuit_breaker("svc-c", CircuitBreakerConfig(failure_threshold=1))

        def boom():
            raise RuntimeError()

        with pytest.raises(RuntimeError):
            cb.call(boom)

        assert cb.get_state() == CircuitState.OPEN
        reset_all_circuit_breakers()
        assert cb.get_state() == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Fallback tests
# ---------------------------------------------------------------------------

class TestFallbackOption:
    """Test FallbackOption dataclass"""

    def test_creation(self):
        """FallbackOption stores name, func and priority"""
        fn = lambda: "x"
        opt = FallbackOption(name="primary", func=fn, priority=5)
        assert opt.name == "primary"
        assert opt.func is fn
        assert opt.priority == 5


class TestFallback:
    """Test Fallback chain execution"""

    def test_no_options_raises(self):
        """execute() with no options configured raises ValueError"""
        fb = Fallback("empty")
        with pytest.raises(ValueError, match="No fallback options"):
            fb.execute()

    def test_first_option_succeeds(self):
        """Returns result of the first (highest-priority) option when it succeeds"""
        fb = Fallback("test")
        fb.add_option("primary", lambda: "primary_result", priority=2)
        fb.add_option("secondary", lambda: "secondary_result", priority=1)

        assert fb.execute() == "primary_result"

    def test_falls_through_to_next_on_exception(self):
        """Falls through to next option when primary raises"""
        fb = Fallback("test")
        fb.add_option("bad", lambda: (_ for _ in ()).throw(RuntimeError("boom")), priority=2)
        fb.add_option("good", lambda: "fallback_result", priority=1)

        assert fb.execute() == "fallback_result"

    def test_last_successful_option_is_tracked(self):
        """last_successful_option is updated after a successful call"""
        fb = Fallback("test")
        fb.add_option("only", lambda: "ok", priority=1)
        fb.execute()
        assert fb.last_successful_option == "only"

    def test_all_fail_raises_all_fallbacks_failed(self):
        """AllFallbacksFailedError is raised when every option fails"""
        fb = Fallback("test")
        fb.add_option("a", lambda: (_ for _ in ()).throw(RuntimeError("a")), priority=2)
        fb.add_option("b", lambda: (_ for _ in ()).throw(RuntimeError("b")), priority=1)

        with pytest.raises(AllFallbacksFailedError):
            fb.execute()

    def test_all_fallbacks_failed_message_contains_names(self):
        """AllFallbacksFailedError message lists the names of failed options"""
        fb = Fallback("chain")
        fb.add_option("opt-x", lambda: (_ for _ in ()).throw(RuntimeError("x")), priority=1)

        with pytest.raises(AllFallbacksFailedError, match="opt-x"):
            fb.execute()

    def test_priority_ordering(self):
        """Options are tried in descending priority order"""
        called = []

        def make_fn(name):
            def fn():
                called.append(name)
                raise RuntimeError(name)
            return fn

        fb = Fallback("test")
        fb.add_option("low", make_fn("low"), priority=1)
        fb.add_option("high", make_fn("high"), priority=3)
        fb.add_option("mid", make_fn("mid"), priority=2)

        with pytest.raises(AllFallbacksFailedError):
            fb.execute()

        assert called == ["high", "mid", "low"]

    def test_options_sorted_after_add(self):
        """add_option() keeps options sorted by priority descending"""
        fb = Fallback("test")
        fb.add_option("c", lambda: None, priority=1)
        fb.add_option("a", lambda: None, priority=3)
        fb.add_option("b", lambda: None, priority=2)

        names = [o.name for o in fb.options]
        assert names == ["a", "b", "c"]

    def test_parallel_strategy_falls_back_to_cascade(self):
        """PARALLEL strategy currently delegates to cascade"""
        fb = Fallback("test", FallbackStrategy.PARALLEL)
        fb.add_option("only", lambda: "parallel_ok", priority=1)
        assert fb.execute() == "parallel_ok"

    def test_unknown_strategy_raises(self):
        """An unknown strategy in execute() raises ValueError"""
        fb = Fallback("test")
        fb.options.append(FallbackOption("x", lambda: None))
        fb.strategy = "bad_strategy"  # type: ignore

        with pytest.raises((ValueError, AttributeError)):
            fb.execute()

    def test_get_stats(self):
        """get_stats() returns a dict with expected keys"""
        fb = Fallback("test", FallbackStrategy.CASCADE)
        fb.add_option("opt", lambda: None, priority=1)
        fb.execute()

        stats = fb.get_stats()
        assert stats["name"] == "test"
        assert stats["strategy"] == FallbackStrategy.CASCADE.value
        assert "opt" in stats["options"]
        assert stats["last_successful"] == "opt"

    def test_kwargs_passed_to_func(self):
        """execute() forwards args and kwargs to the option function"""
        received = {}

        def capture(**kwargs):
            received.update(kwargs)
            return "done"

        fb = Fallback("test")
        fb.add_option("cap", capture, priority=1)
        fb.execute(key="value")

        assert received == {"key": "value"}


class TestRuleBasedFallback:
    """Test _rule_based_fallback keyword matching"""

    def test_list_keyword(self):
        """'list' keyword returns FileOps hint"""
        result = _rule_based_fallback("list all files")
        assert "FileOps" in result or "scan" in result

    def test_create_keyword(self):
        """'create' keyword returns creation hint"""
        result = _rule_based_fallback("create a new directory")
        assert "create" in result.lower() or "FileOps" in result

    def test_delete_keyword(self):
        """'delete' keyword returns deletion hint"""
        result = _rule_based_fallback("delete old logs")
        assert "delete" in result.lower() or "FileOps" in result

    def test_move_keyword(self):
        """'move' keyword returns move hint"""
        result = _rule_based_fallback("move files to archive")
        assert "move" in result.lower() or "FileOps" in result

    def test_cpu_keyword(self):
        """'cpu' keyword returns system resource hint"""
        result = _rule_based_fallback("check cpu usage")
        assert "SystemOps" in result or "cpu" in result.lower()

    def test_git_keyword(self):
        """'git' keyword returns GitOps hint"""
        result = _rule_based_fallback("git status")
        assert "GitOps" in result or "git" in result.lower()

    def test_unknown_prompt_returns_generic(self):
        """An unrecognised prompt returns the generic fallback message"""
        result = _rule_based_fallback("xyzzy frobnicate")
        assert "LLM unavailable" in result or "rule-based" in result.lower()


class TestFallbackRegistry:
    """Test module-level fallback registry helpers"""

    def setup_method(self):
        """Clear global fallback registry before each test"""
        _fallbacks.clear()

    def test_register_and_get(self):
        """register_fallback then get_fallback returns the same instance"""
        fb = Fallback("custom")
        register_fallback("custom", fb)
        assert get_fallback("custom") is fb

    def test_get_creates_empty_fallback_for_unknown_name(self):
        """get_fallback() creates an empty Fallback for names other than 'llm'"""
        result = get_fallback("something-new")
        assert isinstance(result, Fallback)
        assert result.name == "something-new"

    def test_get_llm_creates_llm_fallback(self):
        """get_fallback('llm') creates the LLM fallback chain"""
        with patch("zenus_core.brain.llm.factory.get_llm") as mock_get_llm:
            mock_get_llm.return_value = Mock()
            result = get_fallback("llm")

        assert isinstance(result, Fallback)
        assert result.name == "llm"


# ---------------------------------------------------------------------------
# RetryBudget tests
# ---------------------------------------------------------------------------

class TestRetryConfig:
    """Test RetryConfig dataclass"""

    def test_defaults(self):
        """RetryConfig should have correct defaults"""
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.initial_delay_seconds == 1.0
        assert cfg.max_delay_seconds == 30.0
        assert cfg.exponential_base == 2.0
        assert cfg.jitter is True


class TestRetryBudget:
    """Test RetryBudget tracking"""

    def test_initial_state(self):
        """New RetryBudget starts with zero usage"""
        budget = RetryBudget(total_budget=50)
        assert budget.budget_used == 0
        assert budget.get_remaining() == 50

    def test_can_retry_when_budget_available(self):
        """can_retry() returns True when budget is not exhausted"""
        budget = RetryBudget(total_budget=10)
        assert budget.can_retry() is True

    def test_can_retry_false_when_exhausted(self):
        """can_retry() returns False when budget is fully consumed"""
        budget = RetryBudget(total_budget=5)
        budget.consume(5)
        assert budget.can_retry() is False

    def test_consume_reduces_remaining(self):
        """consume() reduces the remaining budget"""
        budget = RetryBudget(total_budget=10)
        budget.consume(3)
        assert budget.get_remaining() == 7

    def test_consume_multiple_times(self):
        """Multiple consume() calls accumulate correctly"""
        budget = RetryBudget(total_budget=10)
        budget.consume(2)
        budget.consume(3)
        assert budget.budget_used == 5

    def test_get_usage_percentage(self):
        """get_usage_percentage() returns correct fraction"""
        budget = RetryBudget(total_budget=100)
        budget.consume(25)
        assert budget.get_usage_percentage() == pytest.approx(25.0)

    def test_window_reset_clears_usage(self):
        """Budget resets when the window expires"""
        budget = RetryBudget(total_budget=10, window_seconds=0.001)
        budget.consume(10)
        assert budget.can_retry() is False

        # Backdate window_start to simulate expiry
        budget.window_start = datetime.now() - timedelta(seconds=1)
        assert budget.can_retry() is True
        assert budget.budget_used == 0

    def test_get_remaining_never_negative(self):
        """get_remaining() clamps at zero even if overconsumed"""
        budget = RetryBudget(total_budget=5)
        budget.budget_used = 100  # Force overrun
        assert budget.get_remaining() == 0


class TestRetryWithBudget:
    """Test the retry_with_budget executor"""

    def test_succeeds_on_first_attempt(self):
        """A function that succeeds immediately is returned without retries"""
        result = retry_with_budget(lambda: "ok", config=RetryConfig(max_attempts=3))
        assert result == "ok"

    def test_retries_on_failure_then_succeeds(self):
        """Retries until the function succeeds within max_attempts"""
        attempts = {"count": 0}

        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("not yet")
            return "success"

        with patch("time.sleep"):
            result = retry_with_budget(
                flaky,
                config=RetryConfig(max_attempts=3, jitter=False),
                budget=RetryBudget(total_budget=100),
            )

        assert result == "success"
        assert attempts["count"] == 3

    def test_raises_retry_exhausted_after_all_attempts(self):
        """RetryExhaustedError is raised when max_attempts are exhausted"""
        def always_fail():
            raise RuntimeError("fail")

        with patch("time.sleep"):
            with pytest.raises(RetryExhaustedError):
                retry_with_budget(
                    always_fail,
                    config=RetryConfig(max_attempts=3, jitter=False),
                    budget=RetryBudget(total_budget=100),
                )

    def test_raises_budget_exceeded(self):
        """RetryBudgetExceededError is raised when budget is exhausted before attempts"""
        budget = RetryBudget(total_budget=0)

        def always_fail():
            raise RuntimeError("fail")

        with pytest.raises(RetryBudgetExceededError):
            retry_with_budget(
                always_fail,
                config=RetryConfig(max_attempts=3, jitter=False),
                budget=budget,
            )

    def test_retry_only_on_specified_exception(self):
        """retry_on tuple restricts which exceptions trigger retries"""
        attempts = {"count": 0}

        def raises_value_error():
            attempts["count"] += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            retry_with_budget(
                raises_value_error,
                config=RetryConfig(max_attempts=5, jitter=False),
                budget=RetryBudget(total_budget=100),
                retry_on=(ValueError,),
            )

        # TypeError is not in retry_on, so we only call it once
        assert attempts["count"] == 1

    def test_exponential_backoff_capped_at_max_delay(self):
        """Delay is capped at max_delay_seconds"""
        sleep_calls = []

        def record_sleep(d):
            sleep_calls.append(d)

        def always_fail():
            raise RuntimeError()

        with patch("time.sleep", side_effect=record_sleep):
            with pytest.raises(RetryExhaustedError):
                retry_with_budget(
                    always_fail,
                    config=RetryConfig(
                        max_attempts=4,
                        initial_delay_seconds=1.0,
                        max_delay_seconds=2.0,
                        exponential_base=10.0,
                        jitter=False,
                    ),
                    budget=RetryBudget(total_budget=100),
                )

        for d in sleep_calls:
            assert d <= 2.0

    def test_no_sleep_after_last_attempt(self):
        """time.sleep is not called after the final failed attempt"""
        sleep_calls = []

        def record_sleep(d):
            sleep_calls.append(d)

        def always_fail():
            raise RuntimeError()

        with patch("time.sleep", side_effect=record_sleep):
            with pytest.raises(RetryExhaustedError):
                retry_with_budget(
                    always_fail,
                    config=RetryConfig(max_attempts=3, jitter=False),
                    budget=RetryBudget(total_budget=100),
                )

        # 3 attempts → sleep called at most max_attempts-1 times
        assert len(sleep_calls) <= 2

    def test_budget_consumed_per_retry(self):
        """Each retry (not the initial attempt) consumes one unit of budget"""
        budget = RetryBudget(total_budget=100)

        def always_fail():
            raise RuntimeError()

        with patch("time.sleep"):
            with pytest.raises(RetryExhaustedError):
                retry_with_budget(
                    always_fail,
                    config=RetryConfig(max_attempts=3, jitter=False),
                    budget=budget,
                )

        # 3 attempts → 2 retries → 2 budget units consumed
        assert budget.budget_used == 2

    def test_default_config_and_budget_used_when_not_provided(self):
        """retry_with_budget works with no explicit config or budget"""
        with patch("time.sleep"):
            with pytest.raises(RetryExhaustedError):
                retry_with_budget(lambda: (_ for _ in ()).throw(RuntimeError("x")))


class TestRetryBudgetRegistry:
    """Test module-level retry budget registry helpers"""

    def setup_method(self):
        """Clear global registry before each test"""
        reset_all_budgets()

    def test_get_creates_new_budget(self):
        """get_retry_budget() creates a fresh RetryBudget for a new key"""
        budget = get_retry_budget("llm_calls")
        assert isinstance(budget, RetryBudget)

    def test_get_returns_same_instance(self):
        """get_retry_budget() returns the same object on repeated calls"""
        b1 = get_retry_budget("llm_calls")
        b2 = get_retry_budget("llm_calls")
        assert b1 is b2

    def test_reset_all_clears_registry(self):
        """reset_all_budgets() empties the registry"""
        get_retry_budget("op-a")
        get_retry_budget("op-b")
        reset_all_budgets()
        assert len(_retry_budgets) == 0

    def test_get_budget_stats_returns_dict(self):
        """get_budget_stats() returns a summary dict for each registered budget"""
        budget = get_retry_budget("file_ops")
        budget.consume(10)

        stats = get_budget_stats()
        assert "file_ops" in stats
        assert stats["file_ops"]["used"] == 10
        assert stats["file_ops"]["total"] == budget.total_budget
        assert "remaining" in stats["file_ops"]
        assert "usage_percentage" in stats["file_ops"]
