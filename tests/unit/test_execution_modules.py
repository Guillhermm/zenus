"""
Tests for execution subsystem: smart_cache, intent_cache, error_handler, parallel_executor.
"""

import time
import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_intent(goal="test", steps=None, requires_confirmation=False):
    """Build a minimal IntentIR."""
    if steps is None:
        steps = [Step(tool="FileOps", action="read_file", args={"path": "/a"}, risk=0)]
    return IntentIR(goal=goal, requires_confirmation=requires_confirmation, steps=steps)


def make_step(tool="FileOps", action="read_file", args=None, risk=0):
    """Build a single Step."""
    return Step(tool=tool, action=action, args=args or {}, risk=risk)


# ===========================================================================
# CacheEntry (smart_cache.py)
# ===========================================================================

class TestCacheEntry:
    def test_not_expired_when_no_ttl(self):
        """Entry with ttl_seconds=None is never expired."""
        from zenus_core.execution.smart_cache import CacheEntry
        entry = CacheEntry(key="k", value="v", created_at=time.time(), ttl_seconds=None)
        assert entry.is_expired() is False

    def test_not_expired_when_fresh(self):
        """Entry created just now is not expired."""
        from zenus_core.execution.smart_cache import CacheEntry
        entry = CacheEntry(key="k", value="v", created_at=time.time(), ttl_seconds=60)
        assert entry.is_expired() is False

    def test_expired_when_old(self):
        """Entry created well past its TTL is expired."""
        from zenus_core.execution.smart_cache import CacheEntry
        old_time = time.time() - 9999
        entry = CacheEntry(key="k", value="v", created_at=old_time, ttl_seconds=1)
        assert entry.is_expired() is True

    def test_to_dict_round_trip(self):
        """to_dict / from_dict round-trips the entry correctly."""
        from zenus_core.execution.smart_cache import CacheEntry
        entry = CacheEntry(key="k", value={"x": 1}, created_at=123.0, ttl_seconds=60, hit_count=2)
        d = entry.to_dict()
        restored = CacheEntry.from_dict(d)
        assert restored.key == entry.key
        assert restored.value == entry.value
        assert restored.hit_count == 2


# ===========================================================================
# SmartCache (smart_cache.py)
# ===========================================================================

class TestSmartCacheBasics:
    def test_get_miss_returns_none(self):
        """Cache miss returns None."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        assert cache.get("missing") is None

    def test_set_and_get_returns_value(self):
        """Value set in the cache is retrievable."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        cache.set("k", "hello")
        assert cache.get("k") == "hello"

    def test_get_expired_entry_returns_none(self):
        """Expired entries are not returned."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        cache.set("k", "x", ttl_seconds=1)
        # Manually backdate the entry
        cache.cache["k"].created_at = time.time() - 100
        assert cache.get("k") is None

    def test_stats_track_hits_and_misses(self):
        """Hit/miss counts are incremented correctly."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        cache.set("k", "v")
        cache.get("k")      # hit
        cache.get("other")  # miss
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_hit_rate_calculation(self):
        """Hit rate is computed correctly."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        cache.set("k", "v")
        cache.get("k")      # hit
        cache.get("k")      # hit
        cache.get("x")      # miss
        stats = cache.get_stats()
        assert abs(stats["hit_rate"] - 2/3) < 0.01

    def test_clear_resets_cache_and_stats(self):
        """clear() removes all entries and resets statistics."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        cache.set("k", "v")
        cache.get("k")
        cache.clear()
        assert cache.get("k") is None
        assert cache.get_stats()["hits"] == 0

    def test_invalidate_existing_key(self):
        """invalidate returns True and removes the entry."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        cache.set("k", "v")
        assert cache.invalidate("k") is True
        assert cache.get("k") is None

    def test_invalidate_missing_key(self):
        """invalidate returns False when key not present."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        assert cache.invalidate("nonexistent") is False

    def test_invalidate_pattern_removes_matching(self):
        """invalidate_pattern removes all matching keys."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        cache.set("prefix:a", 1)
        cache.set("prefix:b", 2)
        cache.set("other", 3)
        removed = cache.invalidate_pattern("prefix:")
        assert removed == 2
        assert cache.get("other") == 3

    def test_max_entries_triggers_eviction(self):
        """Adding more entries than max_entries triggers LRU eviction."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache(max_entries=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # triggers eviction
        assert len(cache.cache) == 3


class TestSmartCacheGetOrCompute:
    def test_computes_on_miss_and_caches_result(self):
        """get_or_compute calls compute_fn on cache miss and stores result."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        called = []

        def compute():
            called.append(1)
            return "computed"

        result = cache.get_or_compute("k", compute)
        assert result == "computed"
        assert len(called) == 1

    def test_returns_cached_value_on_hit(self):
        """get_or_compute returns cached value without calling compute_fn."""
        from zenus_core.execution.smart_cache import SmartCache
        cache = SmartCache()
        cache.set("k", "already_there")
        called = []
        result = cache.get_or_compute("k", lambda: called.append(1) or "new")
        assert result == "already_there"
        assert len(called) == 0


class TestSmartCachePersistence:
    def test_persist_and_load(self):
        """Cache entries survive a save/load cycle."""
        from zenus_core.execution.smart_cache import SmartCache
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            cache1 = SmartCache(persist_path=path)
            cache1.set("key1", "value1", ttl_seconds=3600)
            cache1._persist()

            cache2 = SmartCache(persist_path=path)
            assert cache2.get("key1") == "value1"
        finally:
            os.unlink(path)

    def test_expired_entries_not_loaded(self):
        """Expired entries are skipped when loading from disk."""
        from zenus_core.execution.smart_cache import SmartCache, CacheEntry
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            entry = CacheEntry(key="old", value="x", created_at=1.0, ttl_seconds=1)
            data = {"cache": {"old": entry.to_dict()}, "stats": {}}
            json.dump(data, f)
            path = f.name
        try:
            cache = SmartCache(persist_path=path)
            assert cache.get("old") is None
        finally:
            os.unlink(path)


class TestComputeCacheKey:
    def test_same_args_produce_same_key(self):
        """Identical arguments always hash to the same key."""
        from zenus_core.execution.smart_cache import compute_cache_key
        k1 = compute_cache_key("list", "files", path="/home")
        k2 = compute_cache_key("list", "files", path="/home")
        assert k1 == k2

    def test_different_args_produce_different_keys(self):
        """Different arguments produce different keys."""
        from zenus_core.execution.smart_cache import compute_cache_key
        k1 = compute_cache_key("a")
        k2 = compute_cache_key("b")
        assert k1 != k2

    def test_key_length_is_16(self):
        """Returned key is exactly 16 hex characters."""
        from zenus_core.execution.smart_cache import compute_cache_key
        key = compute_cache_key("test")
        assert len(key) == 16


class TestSmartCacheSingletons:
    def test_get_llm_cache_returns_smart_cache(self):
        """get_llm_cache returns a SmartCache instance."""
        from zenus_core.execution.smart_cache import get_llm_cache, SmartCache
        from zenus_core.execution import smart_cache as sc_mod
        sc_mod._llm_cache = None
        cache = get_llm_cache()
        assert isinstance(cache, SmartCache)
        sc_mod._llm_cache = None

    def test_get_fs_cache_returns_smart_cache(self):
        """get_fs_cache returns a SmartCache with no persistence."""
        from zenus_core.execution.smart_cache import get_fs_cache, SmartCache
        from zenus_core.execution import smart_cache as sc_mod
        sc_mod._fs_cache = None
        cache = get_fs_cache()
        assert isinstance(cache, SmartCache)
        assert cache.persist_path is None
        sc_mod._fs_cache = None


# ===========================================================================
# CachedIntent (intent_cache.py)
# ===========================================================================

class TestCachedIntent:
    def test_not_expired_when_fresh(self):
        """Fresh CachedIntent is not expired."""
        from zenus_core.execution.intent_cache import CachedIntent
        entry = CachedIntent(
            intent_data={}, user_input="x", context_hash="h",
            created_at=time.time()
        )
        assert entry.is_expired(3600) is False

    def test_expired_when_old(self):
        """Old CachedIntent is expired."""
        from zenus_core.execution.intent_cache import CachedIntent
        entry = CachedIntent(
            intent_data={}, user_input="x", context_hash="h",
            created_at=time.time() - 9999
        )
        assert entry.is_expired(3600) is True

    def test_to_dict_round_trip(self):
        """to_dict / from_dict preserves all fields."""
        from zenus_core.execution.intent_cache import CachedIntent
        entry = CachedIntent(
            intent_data={"goal": "test"}, user_input="test",
            context_hash="abc", created_at=100.0, hit_count=3
        )
        d = entry.to_dict()
        restored = CachedIntent.from_dict(d)
        assert restored.user_input == "test"
        assert restored.hit_count == 3


# ===========================================================================
# IntentCache (intent_cache.py)
# ===========================================================================

class TestIntentCache:
    def _tmp_cache(self):
        """Create an IntentCache backed by a temp file."""
        from zenus_core.execution.intent_cache import IntentCache
        tmp = tempfile.mktemp(suffix=".json")
        return IntentCache(cache_path=tmp, ttl_seconds=3600)

    def test_get_miss_returns_none(self):
        """Cache miss returns None."""
        cache = self._tmp_cache()
        assert cache.get("list files") is None

    def test_set_and_get_returns_intent(self):
        """Stored intent can be retrieved."""
        cache = self._tmp_cache()
        intent = make_intent()
        cache.set("list files", "", intent)
        result = cache.get("list files", "")
        assert result is not None
        assert result.goal == intent.goal

    def test_get_is_case_insensitive(self):
        """Cache key normalisation is case-insensitive."""
        cache = self._tmp_cache()
        intent = make_intent()
        cache.set("List Files", "", intent)
        assert cache.get("list files", "") is not None

    def test_expired_entry_returns_none(self):
        """Expired entry is not returned."""
        from zenus_core.execution.intent_cache import IntentCache
        tmp = tempfile.mktemp(suffix=".json")
        cache = IntentCache(cache_path=tmp, ttl_seconds=1)
        intent = make_intent()
        cache.set("old cmd", "", intent)
        # Backdate the entry
        key = cache._compute_key("old cmd", "")
        cache.cache[key].created_at = time.time() - 9999
        assert cache.get("old cmd", "") is None

    def test_invalidate_removes_entry(self):
        """invalidate() removes a stored entry."""
        cache = self._tmp_cache()
        intent = make_intent()
        cache.set("do thing", "", intent)
        assert cache.invalidate("do thing", "") is True
        assert cache.get("do thing", "") is None

    def test_invalidate_missing_returns_false(self):
        """invalidate() returns False for non-existent entry."""
        cache = self._tmp_cache()
        assert cache.invalidate("nope", "") is False

    def test_clear_removes_all_entries(self):
        """clear() empties the cache."""
        cache = self._tmp_cache()
        cache.set("cmd1", "", make_intent())
        cache.set("cmd2", "", make_intent())
        cache.clear()
        assert cache.get("cmd1") is None

    def test_stats_tokens_saved_on_hit(self):
        """Each cache hit increments tokens_saved estimate."""
        cache = self._tmp_cache()
        intent = make_intent()
        cache.set("cmd", "", intent)
        cache.get("cmd", "")
        stats = cache.get_stats()
        assert stats["tokens_saved"] >= 1200

    def test_stats_hit_rate(self):
        """Hit rate is computed as hits / total_requests."""
        cache = self._tmp_cache()
        intent = make_intent()
        cache.set("cmd", "", intent)
        cache.get("cmd", "")   # hit
        cache.get("other", "")  # miss
        stats = cache.get_stats()
        assert abs(stats["hit_rate"] - 0.5) < 0.01

    def test_lru_eviction_on_max_entries(self):
        """Adding beyond max_entries triggers LRU eviction."""
        from zenus_core.execution.intent_cache import IntentCache
        tmp = tempfile.mktemp(suffix=".json")
        cache = IntentCache(cache_path=tmp, max_entries=2)
        cache.set("a", "", make_intent())
        cache.set("b", "", make_intent())
        cache.set("c", "", make_intent())  # evict oldest
        assert len(cache.cache) == 2


# ===========================================================================
# ErrorHandler (error_handler.py)
# ===========================================================================

class TestErrorCategory:
    def test_permission_pattern_matched(self):
        """'permission denied' maps to PERMISSION category."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        assert handler._categorize("permission denied") == ErrorCategory.PERMISSION

    def test_not_found_pattern_matched(self):
        """'no such file' maps to NOT_FOUND category."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        assert handler._categorize("no such file") == ErrorCategory.NOT_FOUND

    def test_network_pattern_matched(self):
        """'connection refused' maps to NETWORK category."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        assert handler._categorize("connection refused") == ErrorCategory.NETWORK

    def test_timeout_pattern_matched(self):
        """'timed out' maps to TIMEOUT category."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        assert handler._categorize("timed out") == ErrorCategory.TIMEOUT

    def test_unknown_error_maps_to_unknown(self):
        """Unrecognised error text maps to UNKNOWN category."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        assert handler._categorize("something went sideways") == ErrorCategory.UNKNOWN


class TestErrorHandlerMessages:
    def test_permission_message_mentions_path(self):
        """Permission error message includes the path from args."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        msg = handler._generate_message(
            ErrorCategory.PERMISSION, "FileOps", "read_file",
            {"path": "/etc/secret"}, "permission denied"
        )
        assert "/etc/secret" in msg

    def test_not_found_message_for_package_ops(self):
        """NOT_FOUND for PackageOps mentions the package name."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        msg = handler._generate_message(
            ErrorCategory.NOT_FOUND, "PackageOps", "install",
            {"package": "foobar"}, "package not found"
        )
        assert "foobar" in msg

    def test_network_message(self):
        """NETWORK category yields a network-related message."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        msg = handler._generate_message(
            ErrorCategory.NETWORK, "NetworkOps", "download", {}, "connection refused"
        )
        assert "network" in msg.lower() or "connection" in msg.lower()

    def test_unknown_message_contains_tool_and_action(self):
        """UNKNOWN category message includes tool.action."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        msg = handler._generate_message(
            ErrorCategory.UNKNOWN, "MyTool", "myAction", {}, "oops"
        )
        assert "MyTool" in msg
        assert "myAction" in msg


class TestErrorHandlerSuggestions:
    def test_permission_suggestions_mention_permissions(self):
        """PERMISSION suggestions include permission-checking advice."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        suggestions = handler._generate_suggestions(
            ErrorCategory.PERMISSION, "FileOps", "write", {}, "permission denied"
        )
        text = " ".join(suggestions).lower()
        assert "permission" in text or "sudo" in text

    def test_not_found_suggestions_for_package(self):
        """NOT_FOUND for PackageOps includes package-search suggestion."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        suggestions = handler._generate_suggestions(
            ErrorCategory.NOT_FOUND, "PackageOps", "install",
            {"package": "xyz"}, "package not found"
        )
        text = " ".join(suggestions)
        assert "xyz" in text

    def test_network_suggestions_include_connectivity_check(self):
        """NETWORK suggestions include internet connectivity advice."""
        from zenus_core.execution.error_handler import ErrorHandler, ErrorCategory
        handler = ErrorHandler()
        suggestions = handler._generate_suggestions(
            ErrorCategory.NETWORK, "NetworkOps", "download", {}, "connection refused"
        )
        text = " ".join(suggestions).lower()
        assert "internet" in text or "connection" in text


class TestErrorHandlerHandle:
    def test_handle_returns_enhanced_error(self):
        """handle() returns an EnhancedError with populated fields."""
        from zenus_core.execution.error_handler import ErrorHandler, EnhancedError
        handler = ErrorHandler()
        err = ValueError("permission denied")
        result = handler.handle(err, "FileOps", "write", {"path": "/tmp/x"})
        assert isinstance(result, EnhancedError)
        assert result.message != ""
        assert len(result.suggestions) > 0

    def test_enhanced_error_format_contains_message(self):
        """EnhancedError.format() includes the user-friendly message."""
        from zenus_core.execution.error_handler import ErrorHandler
        handler = ErrorHandler()
        err = FileNotFoundError("no such file")
        result = handler.handle(err, "FileOps", "read", {"path": "/missing.txt"})
        formatted = result.format()
        assert result.user_friendly in formatted

    def test_handle_accepts_context(self):
        """handle() stores provided context in the returned error."""
        from zenus_core.execution.error_handler import ErrorHandler
        handler = ErrorHandler()
        err = Exception("timeout")
        result = handler.handle(err, "T", "a", {}, context={"cwd": "/home"})
        assert result.context == {"cwd": "/home"}


class TestGetErrorHandler:
    def test_singleton(self):
        """get_error_handler returns the same instance on repeated calls."""
        from zenus_core.execution import error_handler as eh_mod
        eh_mod._error_handler = None
        a = eh_mod.get_error_handler()
        b = eh_mod.get_error_handler()
        assert a is b
        eh_mod._error_handler = None


# ===========================================================================
# ResourceLimiter (parallel_executor.py)
# ===========================================================================

class TestResourceLimiter:
    def test_non_io_step_can_always_execute(self):
        """Non-I/O steps always get the green light."""
        from zenus_core.execution.parallel_executor import ResourceLimiter
        limiter = ResourceLimiter()
        step = make_step(tool="TextOps", action="search")
        assert limiter.can_execute(step) is True

    def test_io_step_blocked_when_limit_reached(self):
        """I/O step is blocked when current_io_operations >= max."""
        from zenus_core.execution.parallel_executor import ResourceLimiter
        limiter = ResourceLimiter(max_concurrent_io=2)
        limiter.current_io_operations = 2
        step = make_step(tool="FileOps", action="read_file")
        assert limiter.can_execute(step) is False

    def test_io_step_allowed_below_limit(self):
        """I/O step is allowed when below the max concurrent limit."""
        from zenus_core.execution.parallel_executor import ResourceLimiter
        limiter = ResourceLimiter(max_concurrent_io=3)
        step = make_step(tool="FileOps", action="read_file")
        assert limiter.can_execute(step) is True

    def test_acquire_and_release_io(self):
        """acquire_io increments and release_io decrements the counter."""
        from zenus_core.execution.parallel_executor import ResourceLimiter
        limiter = ResourceLimiter()
        limiter.acquire_io()
        assert limiter.current_io_operations == 1
        limiter.release_io()
        assert limiter.current_io_operations == 0

    def test_release_io_does_not_go_below_zero(self):
        """release_io never decrements below 0."""
        from zenus_core.execution.parallel_executor import ResourceLimiter
        limiter = ResourceLimiter()
        limiter.release_io()
        assert limiter.current_io_operations == 0


class TestParallelExecutorShouldUseParallel:
    def _make_executor(self):
        from zenus_core.execution.parallel_executor import ParallelExecutor
        from zenus_core.brain.dependency_analyzer import DependencyAnalyzer
        executor = ParallelExecutor.__new__(ParallelExecutor)
        executor.max_workers = 4
        executor.timeout_seconds = 300
        executor.analyzer = DependencyAnalyzer()
        executor.logger = MagicMock()
        return executor

    def test_single_step_not_parallel(self):
        """A single-step intent is not worth parallelising."""
        executor = self._make_executor()
        intent = make_intent(steps=[make_step()])
        assert executor.should_use_parallel(intent) is False

    def test_sequential_steps_not_parallel(self):
        """Fully dependent steps are not parallelisable."""
        executor = self._make_executor()
        # PackageOps are always sequential
        steps = [
            make_step(tool="PackageOps", action="install", args={"package": "a"}),
            make_step(tool="PackageOps", action="install", args={"package": "b"}),
        ]
        intent = make_intent(steps=steps)
        assert executor.should_use_parallel(intent) is False

    def test_independent_steps_are_parallel(self):
        """Independent FileOps on different paths should use parallel execution."""
        executor = self._make_executor()
        steps = [
            make_step(tool="FileOps", action="read_file", args={"path": "/a"}),
            make_step(tool="FileOps", action="read_file", args={"path": "/b"}),
            make_step(tool="FileOps", action="read_file", args={"path": "/c"}),
        ]
        intent = make_intent(steps=steps)
        assert executor.should_use_parallel(intent) is True


class TestParallelExecutorExecute:
    def _make_executor(self):
        from zenus_core.execution.parallel_executor import ParallelExecutor
        from zenus_core.brain.dependency_analyzer import DependencyAnalyzer
        executor = ParallelExecutor.__new__(ParallelExecutor)
        executor.max_workers = 4
        executor.timeout_seconds = 300
        executor.analyzer = DependencyAnalyzer()
        executor.logger = MagicMock()
        return executor

    def test_empty_intent_returns_empty_list(self):
        """Zero steps returns an empty list."""
        executor = self._make_executor()
        intent = make_intent(steps=[])
        with patch('zenus_core.execution.parallel_executor.console'):
            result = executor.execute(intent, lambda s: "ok")
        assert result == []

    def test_single_step_result_returned(self):
        """Single step executes and its result is returned."""
        executor = self._make_executor()
        intent = make_intent(steps=[make_step()])
        with patch('zenus_core.execution.parallel_executor.console'):
            result = executor.execute(intent, lambda s: "done")
        assert result == ["done"]

    def test_sequential_steps_all_results_returned(self):
        """Sequential steps return one result per step."""
        executor = self._make_executor()
        steps = [
            make_step(tool="PackageOps", action="install", args={"package": "a"}),
            make_step(tool="PackageOps", action="install", args={"package": "b"}),
        ]
        intent = make_intent(steps=steps)
        counter = {"n": 0}

        def run(step):
            counter["n"] += 1
            return f"result_{counter['n']}"

        with patch('zenus_core.execution.parallel_executor.console'):
            results = executor.execute(intent, run)
        assert len(results) == 2

    def test_get_parallel_executor_factory(self):
        """get_parallel_executor returns a ParallelExecutor."""
        from zenus_core.execution.parallel_executor import get_parallel_executor, ParallelExecutor
        with patch('zenus_core.execution.parallel_executor.DependencyAnalyzer'), \
             patch('zenus_core.execution.parallel_executor.get_logger', return_value=MagicMock()):
            executor = get_parallel_executor(max_workers=2, timeout_seconds=60)
        assert isinstance(executor, ParallelExecutor)
        assert executor.max_workers == 2
        assert executor.timeout_seconds == 60
