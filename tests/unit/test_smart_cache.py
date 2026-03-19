"""
Tests for SmartCache and IntentCache.

All tests are pure unit tests — no disk I/O, no network, no LLM calls.
Covers:
- Basic get/set/invalidate operations
- TTL expiration
- LRU eviction
- Hit/miss statistics
- Persistence helpers (mocked)
- get_or_compute shortcut
- IntentCache: key hashing, TTL, LRU, stats
- Module-level singletons
"""

import time
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from zenus_core.execution.smart_cache import (
    CacheEntry,
    SmartCache,
    compute_cache_key,
    get_llm_cache,
    get_fs_cache,
)
from zenus_core.execution.intent_cache import (
    CachedIntent,
    IntentCache,
    get_intent_cache,
)
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_intent(goal: str = "test goal") -> IntentIR:
    return IntentIR(
        goal=goal,
        requires_confirmation=False,
        steps=[Step(tool="file_ops", action="scan", args={}, risk=0)],
    )


def _make_cache(**kwargs) -> SmartCache:
    """SmartCache with no persistence."""
    defaults = dict(max_entries=10, default_ttl=60, persist_path=None)
    defaults.update(kwargs)
    return SmartCache(**defaults)


def _make_intent_cache(**kwargs) -> IntentCache:
    """IntentCache backed by a temp dir that won't actually write."""
    c = IntentCache.__new__(IntentCache)
    c.cache_path = Path("/tmp/zenus_test_intent_cache.json")
    c.ttl_seconds = kwargs.get("ttl_seconds", 3600)
    c.max_entries = kwargs.get("max_entries", 10)
    c.cache = {}
    c.stats = {
        "hits": 0,
        "misses": 0,
        "evictions": 0,
        "expirations": 0,
        "tokens_saved": 0,
    }
    return c


# ---------------------------------------------------------------------------
# CacheEntry
# ---------------------------------------------------------------------------

class TestCacheEntry:
    def test_not_expired_with_none_ttl(self):
        entry = CacheEntry(key="k", value="v", created_at=time.time() - 10000, ttl_seconds=None)
        assert not entry.is_expired()

    def test_expired_when_past_ttl(self):
        entry = CacheEntry(key="k", value="v", created_at=time.time() - 100, ttl_seconds=10)
        assert entry.is_expired()

    def test_not_expired_within_ttl(self):
        entry = CacheEntry(key="k", value="v", created_at=time.time(), ttl_seconds=60)
        assert not entry.is_expired()

    def test_to_dict_roundtrip(self):
        entry = CacheEntry(key="k", value=42, created_at=1000.0, ttl_seconds=60, hit_count=3, last_hit=1001.0)
        d = entry.to_dict()
        restored = CacheEntry.from_dict(d)
        assert restored.key == "k"
        assert restored.value == 42
        assert restored.hit_count == 3
        assert restored.ttl_seconds == 60


# ---------------------------------------------------------------------------
# SmartCache — basic CRUD
# ---------------------------------------------------------------------------

class TestSmartCacheBasic:
    def test_get_miss_returns_none(self):
        c = _make_cache()
        assert c.get("nonexistent") is None

    def test_miss_increments_stat(self):
        c = _make_cache()
        c.get("x")
        assert c.stats["misses"] == 1

    def test_set_and_get(self):
        c = _make_cache()
        c.set("k", "hello")
        assert c.get("k") == "hello"

    def test_hit_increments_stat(self):
        c = _make_cache()
        c.set("k", "v")
        c.get("k")
        assert c.stats["hits"] == 1

    def test_overwrite_value(self):
        c = _make_cache()
        c.set("k", "first")
        c.set("k", "second")
        assert c.get("k") == "second"

    def test_stores_various_types(self):
        c = _make_cache()
        c.set("list", [1, 2, 3])
        c.set("dict", {"a": 1})
        c.set("none", None)
        assert c.get("list") == [1, 2, 3]
        assert c.get("dict") == {"a": 1}
        # None value: get() returns None which looks like a miss

    def test_invalidate_existing(self):
        c = _make_cache()
        c.set("k", "v")
        assert c.invalidate("k") is True
        assert c.get("k") is None

    def test_invalidate_nonexistent(self):
        c = _make_cache()
        assert c.invalidate("nope") is False

    def test_clear_removes_all(self):
        c = _make_cache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_clear_resets_stats(self):
        c = _make_cache()
        c.set("k", "v")
        c.get("k")
        c.clear()
        assert c.stats["hits"] == 0
        assert c.stats["misses"] == 0


# ---------------------------------------------------------------------------
# SmartCache — TTL expiration
# ---------------------------------------------------------------------------

class TestSmartCacheTTL:
    def test_expired_entry_returns_none(self):
        c = _make_cache()
        c.set("k", "v", ttl_seconds=1)
        # Manually push creation time back
        c.cache["k"].created_at -= 2
        assert c.get("k") is None

    def test_expired_entry_increments_expiration(self):
        c = _make_cache()
        c.set("k", "v", ttl_seconds=1)
        c.cache["k"].created_at -= 2
        c.get("k")
        assert c.stats["expirations"] == 1

    def test_expired_entry_removed_from_cache(self):
        c = _make_cache()
        c.set("k", "v", ttl_seconds=1)
        c.cache["k"].created_at -= 2
        c.get("k")
        assert "k" not in c.cache

    def test_within_ttl_not_expired(self):
        c = _make_cache()
        c.set("k", "v", ttl_seconds=3600)
        assert c.get("k") == "v"

    def test_default_ttl_used_when_not_specified(self):
        c = _make_cache(default_ttl=5)
        c.set("k", "v")
        assert c.cache["k"].ttl_seconds == 5


# ---------------------------------------------------------------------------
# SmartCache — LRU eviction
# ---------------------------------------------------------------------------

class TestSmartCacheLRU:
    def test_evicts_when_full(self):
        c = _make_cache(max_entries=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)  # triggers eviction
        assert len(c.cache) == 3

    def test_eviction_increments_stat(self):
        c = _make_cache(max_entries=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        assert c.stats["evictions"] == 1

    def test_lru_entry_evicted(self):
        c = _make_cache(max_entries=2)
        c.set("a", 1)
        # Make 'a' older
        c.cache["a"].created_at -= 1000
        c.set("b", 2)
        c.set("c", 3)  # 'a' should be evicted
        assert "a" not in c.cache

    def test_recently_accessed_not_evicted(self):
        c = _make_cache(max_entries=2)
        c.set("a", 1)
        c.set("b", 2)
        # Access 'a' to update last_hit
        c.get("a")
        # Make 'b' older
        c.cache["b"].created_at -= 1000
        c.set("c", 3)  # 'b' should be evicted
        assert "a" in c.cache
        assert "b" not in c.cache


# ---------------------------------------------------------------------------
# SmartCache — statistics
# ---------------------------------------------------------------------------

class TestSmartCacheStats:
    def test_get_stats_empty(self):
        c = _make_cache()
        stats = c.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["total_requests"] == 0
        assert stats["total_entries"] == 0

    def test_hit_rate_calculation(self):
        c = _make_cache()
        c.set("k", "v")
        c.get("k")   # hit
        c.get("x")   # miss
        stats = c.get_stats()
        assert stats["hit_rate"] == pytest.approx(0.5)

    def test_total_requests(self):
        c = _make_cache()
        c.set("k", "v")
        c.get("k")
        c.get("missing")
        stats = c.get_stats()
        assert stats["total_requests"] == 2


# ---------------------------------------------------------------------------
# SmartCache — get_or_compute
# ---------------------------------------------------------------------------

class TestGetOrCompute:
    def test_calls_fn_on_miss(self):
        c = _make_cache()
        fn = MagicMock(return_value="computed")
        result = c.get_or_compute("k", fn)
        assert result == "computed"
        fn.assert_called_once()

    def test_returns_cached_on_hit(self):
        c = _make_cache()
        c.set("k", "cached")
        fn = MagicMock(return_value="new")
        result = c.get_or_compute("k", fn)
        assert result == "cached"
        fn.assert_not_called()

    def test_stores_computed_value(self):
        c = _make_cache()
        c.get_or_compute("k", lambda: "stored")
        assert c.get("k") == "stored"


# ---------------------------------------------------------------------------
# SmartCache — invalidate_pattern
# ---------------------------------------------------------------------------

class TestInvalidatePattern:
    def test_removes_matching_keys(self):
        c = _make_cache()
        c.set("user:1", "a")
        c.set("user:2", "b")
        c.set("post:1", "c")
        removed = c.invalidate_pattern("user:")
        assert removed == 2
        assert c.get("post:1") == "c"

    def test_no_matches(self):
        c = _make_cache()
        c.set("k", "v")
        assert c.invalidate_pattern("xyz") == 0


# ---------------------------------------------------------------------------
# compute_cache_key
# ---------------------------------------------------------------------------

class TestComputeCacheKey:
    def test_returns_string(self):
        assert isinstance(compute_cache_key("a", "b"), str)

    def test_same_args_same_key(self):
        assert compute_cache_key("a", "b") == compute_cache_key("a", "b")

    def test_different_args_different_key(self):
        assert compute_cache_key("a") != compute_cache_key("b")

    def test_kwargs_included(self):
        k1 = compute_cache_key("x", foo="bar")
        k2 = compute_cache_key("x", foo="baz")
        assert k1 != k2

    def test_key_length(self):
        key = compute_cache_key("test")
        assert len(key) == 16  # sha256 truncated to 16 chars


# ---------------------------------------------------------------------------
# SmartCache singletons
# ---------------------------------------------------------------------------

class TestSmartCacheSingletons:
    def test_get_llm_cache_returns_smart_cache(self):
        with patch("zenus_core.execution.smart_cache.Path") as _:
            cache = get_llm_cache()
        assert isinstance(cache, SmartCache)

    def test_get_fs_cache_returns_smart_cache(self):
        cache = get_fs_cache()
        assert isinstance(cache, SmartCache)

    def test_get_fs_cache_no_persistence(self):
        cache = get_fs_cache()
        assert cache.persist_path is None


# ---------------------------------------------------------------------------
# CachedIntent
# ---------------------------------------------------------------------------

class TestCachedIntent:
    def test_not_expired(self):
        entry = CachedIntent(
            intent_data={}, user_input="list files",
            context_hash="abc", created_at=time.time()
        )
        assert not entry.is_expired()

    def test_expired(self):
        entry = CachedIntent(
            intent_data={}, user_input="list files",
            context_hash="abc", created_at=time.time() - 7200
        )
        assert entry.is_expired(ttl_seconds=3600)

    def test_to_dict_roundtrip(self):
        entry = CachedIntent(
            intent_data={"goal": "test"}, user_input="test",
            context_hash="hash", created_at=1000.0, hit_count=5, last_hit=1001.0
        )
        d = entry.to_dict()
        restored = CachedIntent.from_dict(d)
        assert restored.intent_data == {"goal": "test"}
        assert restored.hit_count == 5


# ---------------------------------------------------------------------------
# IntentCache — get / set
# ---------------------------------------------------------------------------

class TestIntentCacheGetSet:
    def test_miss_returns_none(self):
        c = _make_intent_cache()
        assert c.get("list files") is None

    def test_miss_increments_misses(self):
        c = _make_intent_cache()
        c.get("list files")
        assert c.stats["misses"] == 1

    def test_set_and_get(self):
        c = _make_intent_cache()
        intent = _make_intent("list files")
        with patch.object(c, "_save"):
            c.set("list files", "", intent)
            result = c.get("list files")
        assert result is not None
        assert result.goal == "list files"

    def test_hit_increments_hits(self):
        c = _make_intent_cache()
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
            c.get("cmd")
        assert c.stats["hits"] == 1

    def test_hit_updates_tokens_saved(self):
        c = _make_intent_cache()
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
            c.get("cmd")
        assert c.stats["tokens_saved"] > 0


# ---------------------------------------------------------------------------
# IntentCache — TTL
# ---------------------------------------------------------------------------

class TestIntentCacheTTL:
    def test_expired_entry_returns_none(self):
        c = _make_intent_cache(ttl_seconds=3600)
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
            # Expire the entry
            key = list(c.cache.keys())[0]
            c.cache[key].created_at -= 7200
            result = c.get("cmd")
        assert result is None

    def test_expired_entry_removed(self):
        c = _make_intent_cache(ttl_seconds=3600)
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
            key = list(c.cache.keys())[0]
            c.cache[key].created_at -= 7200
            c.get("cmd")
        assert len(c.cache) == 0

    def test_expiration_increments_stat(self):
        c = _make_intent_cache()
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
            key = list(c.cache.keys())[0]
            c.cache[key].created_at -= 7200
            c.get("cmd")
        assert c.stats["expirations"] == 1


# ---------------------------------------------------------------------------
# IntentCache — context hashing
# ---------------------------------------------------------------------------

class TestIntentCacheContextHashing:
    def test_same_input_different_context_different_cache(self):
        c = _make_intent_cache()
        intent = _make_intent("list")
        with patch.object(c, "_save"):
            c.set("list files", "/home", intent)
            result = c.get("list files", context="/tmp")
        assert result is None

    def test_same_input_same_context_hits(self):
        c = _make_intent_cache()
        intent = _make_intent("list")
        with patch.object(c, "_save"):
            c.set("list files", "/home", intent)
            result = c.get("list files", "/home")
        assert result is not None

    def test_case_insensitive_input(self):
        """Input is normalized to lowercase."""
        c = _make_intent_cache()
        intent = _make_intent("list")
        with patch.object(c, "_save"):
            c.set("List Files", "", intent)
            result = c.get("list files")
        assert result is not None


# ---------------------------------------------------------------------------
# IntentCache — invalidate / clear
# ---------------------------------------------------------------------------

class TestIntentCacheInvalidate:
    def test_invalidate_existing(self):
        c = _make_intent_cache()
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
            removed = c.invalidate("cmd")
            assert removed is True
            assert c.get("cmd") is None

    def test_invalidate_nonexistent(self):
        c = _make_intent_cache()
        assert c.invalidate("nonexistent") is False

    def test_clear(self):
        c = _make_intent_cache()
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd1", "", intent)
            c.set("cmd2", "", intent)
            c.clear()
        assert c.get("cmd1") is None
        assert c.get("cmd2") is None
        assert c.stats["hits"] == 0


# ---------------------------------------------------------------------------
# IntentCache — LRU eviction
# ---------------------------------------------------------------------------

class TestIntentCacheLRU:
    def test_eviction_when_full(self):
        c = _make_intent_cache(max_entries=2)
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("a", "", intent)
            c.set("b", "", intent)
            c.set("c", "", intent)
        assert len(c.cache) == 2

    def test_eviction_stat_incremented(self):
        c = _make_intent_cache(max_entries=2)
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("a", "", intent)
            c.set("b", "", intent)
            c.set("c", "", intent)
        # LRU eviction happened internally
        # The eviction stat is incremented inside _evict_lru
        assert c.stats["evictions"] == 1


# ---------------------------------------------------------------------------
# IntentCache — stats
# ---------------------------------------------------------------------------

class TestIntentCacheStats:
    def test_get_stats_structure(self):
        c = _make_intent_cache()
        stats = c.get_stats()
        assert "hit_rate" in stats
        assert "total_entries" in stats
        assert "estimated_cost_saved" in stats

    def test_hit_rate_calculation(self):
        c = _make_intent_cache()
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
            c.get("cmd")    # hit
            c.get("other")  # miss
        stats = c.get_stats()
        assert stats["hit_rate"] == pytest.approx(0.5)

    def test_estimated_cost_saved(self):
        c = _make_intent_cache()
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
            c.get("cmd")
        stats = c.get_stats()
        assert stats["estimated_cost_saved"] > 0


# ---------------------------------------------------------------------------
# IntentCache — corrupted entry handling
# ---------------------------------------------------------------------------

class TestIntentCacheCorruption:
    def test_corrupted_entry_returns_none(self):
        c = _make_intent_cache()
        intent = _make_intent()
        with patch.object(c, "_save"):
            c.set("cmd", "", intent)
        # Corrupt the stored data
        key = list(c.cache.keys())[0]
        c.cache[key].intent_data = {"invalid": "schema"}
        with patch.object(c, "_save"):
            result = c.get("cmd")
        assert result is None


# ---------------------------------------------------------------------------
# IntentCache singleton
# ---------------------------------------------------------------------------

class TestIntentCacheSingleton:
    def test_get_intent_cache_returns_instance(self):
        cache = get_intent_cache()
        assert isinstance(cache, IntentCache)

    def test_get_intent_cache_singleton(self):
        c1 = get_intent_cache()
        c2 = get_intent_cache()
        assert c1 is c2
