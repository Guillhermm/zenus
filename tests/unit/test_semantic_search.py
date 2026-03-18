"""
Tests for Semantic Search
"""

import json
import sys
import types
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock


# ---------------------------------------------------------------------------
# Helpers to inject fake numpy / sentence_transformers so the module can be
# imported without the real ML stack.  We do this at the module level so all
# test classes benefit without repeating the patch setup.
# ---------------------------------------------------------------------------

def _make_fake_numpy():
    """Return a minimal numpy stand-in sufficient for SemanticSearch."""
    np = types.ModuleType("numpy")

    import math

    class _FakeArray:
        """Very thin ndarray-like object."""
        def __init__(self, data):
            # data is a list-of-lists (2-D) or list (1-D)
            self._data = data

        @property
        def nbytes(self):
            flat = self._data if not isinstance(self._data[0], list) else [v for row in self._data for v in row]
            return len(flat) * 4  # pretend float32

        def reshape(self, *shape):
            return _FakeArray([self._data])

        def __len__(self):
            return len(self._data)

    def array(data):
        return _FakeArray(data)

    def zeros(shape):
        if isinstance(shape, int):
            return _FakeArray([0.0] * shape)
        rows, cols = shape
        return _FakeArray([[0.0] * cols for _ in range(rows)])

    def dot(a, b):
        # a is 1-D list, b is also 1-D list → scalar for cosine result per embedding
        if isinstance(a, _FakeArray):
            a = a._data
        if isinstance(b, _FakeArray):
            b = b._data

        # embeddings_norm (2-D) · query_norm (1-D) -> 1-D similarities array
        if isinstance(a[0], list):
            return _FakeArray([sum(r[i] * b[i] for i in range(len(b))) for r in a])
        return sum(a[i] * b[i] for i in range(len(a)))

    def vstack(arrays):
        combined = []
        for arr in arrays:
            data = arr._data if isinstance(arr, _FakeArray) else arr
            if isinstance(data[0], list):
                combined.extend(data)
            else:
                combined.append(data)
        return _FakeArray(combined)

    def save(path, arr):
        """Fake np.save — write JSON so _load_cache can call np.load."""
        with open(str(path), "w") as f:
            data = arr._data if isinstance(arr, _FakeArray) else arr
            json.dump(data, f)

    def load(path):
        with open(str(path)) as f:
            data = json.load(f)
        return _FakeArray(data)

    def argsort(arr):
        data = arr._data if isinstance(arr, _FakeArray) else arr
        indexed = sorted(enumerate(data), key=lambda x: x[1])
        return _FakeArray([i for i, _ in indexed])

    def linalg_norm_1d(v):
        return math.sqrt(sum(x * x for x in v)) or 1.0

    class _Linalg:
        @staticmethod
        def norm(arr, axis=None, keepdims=False):
            if isinstance(arr, _FakeArray):
                data = arr._data
            else:
                data = arr

            if axis == 1:
                # 2-D: norm of each row
                norms = [linalg_norm_1d(row) for row in data]
                if keepdims:
                    return _FakeArray([[n] for n in norms])
                return _FakeArray(norms)
            # 1-D
            return linalg_norm_1d(data)

    np.array = array
    np.zeros = zeros
    np.dot = dot
    np.vstack = vstack
    np.save = save
    np.load = load
    np.argsort = argsort
    np.linalg = _Linalg()
    # Provide ndarray as a type used in annotations
    np.ndarray = _FakeArray
    return np


# Build fake modules once
_fake_np = _make_fake_numpy()
_fake_st = types.ModuleType("sentence_transformers")


class _FakeSentenceTransformer:
    """Fake SentenceTransformer that returns deterministic fixed embeddings."""

    def __init__(self, model_name):
        self.model_name = model_name
        # Map text -> fixed embedding so similarity is reproducible
        self._registry = {}
        self._dim = 4

    def encode(self, text, show_progress_bar=False):
        import numpy as np
        if text not in self._registry:
            # Assign a unique embedding based on registration order
            idx = len(self._registry)
            vec = [float(i == idx % self._dim) for i in range(self._dim)]
            self._registry[text] = vec
        return np.array(self._registry[text])


_fake_st.SentenceTransformer = _FakeSentenceTransformer


# ---------------------------------------------------------------------------
# Patch sys.modules *before* importing the module under test so that the
# module-level `try: import numpy …` block sees our fakes.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_ml_deps(monkeypatch):
    """Inject fake sentence_transformers and ensure numpy is available for every test."""
    # Inject fake sentence_transformers (may not be installed)
    monkeypatch.setitem(sys.modules, "sentence_transformers", _fake_st)

    import zenus_core.memory.semantic_search as ss_mod

    # Use real numpy (it IS installed) so pytest.approx and other tools work correctly
    try:
        import numpy as real_np
        monkeypatch.setattr(ss_mod, "np", real_np)
    except ImportError:
        # Fall back to fake numpy only if real numpy isn't available
        monkeypatch.setattr(ss_mod, "np", _fake_np)

    # Force SEMANTIC_SEARCH_AVAILABLE = True and inject fake SentenceTransformer
    monkeypatch.setattr(ss_mod, "SEMANTIC_SEARCH_AVAILABLE", True)
    monkeypatch.setattr(ss_mod, "SentenceTransformer", _FakeSentenceTransformer)


@pytest.fixture
def search(tmp_path, monkeypatch):
    """Create a SemanticSearch instance rooted under tmp_path."""
    # Redirect the cache directory
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    from zenus_core.memory.semantic_search import SemanticSearch
    return SemanticSearch()


def _add(search_instance, user_input, goal, steps=None, success=True, timestamp=1_000_000.0):
    """Convenience wrapper to add a command."""
    search_instance.add_command(
        user_input=user_input,
        goal=goal,
        steps=steps or [],
        success=success,
        timestamp=timestamp,
    )


class TestSemanticSearchInit:
    def test_raises_import_error_when_deps_missing(self, monkeypatch):
        """Constructor raises ImportError when ML deps are unavailable."""
        import zenus_core.memory.semantic_search as ss_mod
        monkeypatch.setattr(ss_mod, "SEMANTIC_SEARCH_AVAILABLE", False)
        from zenus_core.memory.semantic_search import SemanticSearch
        with pytest.raises(ImportError, match="sentence-transformers"):
            SemanticSearch()

    def test_initial_embeddings_are_none(self, search):
        """Fresh instance has no embeddings loaded."""
        assert search.embeddings is None

    def test_initial_metadata_is_empty(self, search):
        """Fresh instance has empty metadata list."""
        assert search.metadata == []

    def test_cache_dir_created(self, search):
        """Constructor creates the cache directory."""
        assert search.cache_dir.exists()


class TestAddCommand:
    def test_add_single_command_sets_embeddings(self, search):
        """After adding one command, embeddings is not None."""
        _add(search, "list files", "list directory contents")
        assert search.embeddings is not None

    def test_add_single_command_stores_metadata(self, search):
        """After adding one command, metadata has one entry."""
        _add(search, "list files", "list directory contents")
        assert len(search.metadata) == 1

    def test_metadata_fields_stored(self, search):
        """All metadata fields are stored correctly."""
        _add(search, "move photos", "move image files", steps=["s1"], success=True, timestamp=9999.0)
        entry = search.metadata[0]
        assert entry["user_input"] == "move photos"
        assert entry["goal"] == "move image files"
        assert entry["steps"] == ["s1"]
        assert entry["success"] is True
        assert entry["timestamp"] == 9999.0

    def test_add_multiple_commands_accumulates_metadata(self, search):
        """Adding several commands grows the metadata list."""
        for i in range(4):
            _add(search, f"command {i}", f"goal {i}")
        assert len(search.metadata) == 4

    def test_add_command_persists_to_disk(self, search):
        """After add_command, cache files exist on disk."""
        _add(search, "compile project", "build project")
        assert search.embeddings_file.exists()
        assert search.metadata_file.exists()

    def test_add_command_default_timestamp(self, search):
        """When timestamp is None, a current time float is used."""
        _add_no_ts = lambda: search.add_command(
            user_input="u", goal="g", steps=[], success=True, timestamp=None
        )
        _add_no_ts()
        assert search.metadata[0]["timestamp"] > 0


class TestLoadCache:
    def test_cache_loaded_on_reinit(self, tmp_path, monkeypatch):
        """Metadata and embeddings persist across SemanticSearch instances."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        from zenus_core.memory.semantic_search import SemanticSearch

        s1 = SemanticSearch()
        _add(s1, "compress logs", "archive log files")

        s2 = SemanticSearch()
        assert len(s2.metadata) == 1
        assert s2.metadata[0]["user_input"] == "compress logs"

    def test_corrupt_cache_falls_back_to_empty(self, tmp_path, monkeypatch):
        """Corrupted cache files result in empty embeddings and metadata."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        from zenus_core.memory.semantic_search import SemanticSearch

        s1 = SemanticSearch()
        _add(s1, "cmd", "goal")

        # Corrupt the embeddings file
        s1.embeddings_file.write_text("not valid json{{")

        s2 = SemanticSearch()
        assert s2.embeddings is None
        assert s2.metadata == []


class TestSearch:
    def test_search_empty_index_returns_empty(self, search):
        """Search on an empty index returns an empty list."""
        results = search.search("anything")
        assert results == []

    def test_search_returns_list(self, search):
        """search() always returns a list."""
        _add(search, "delete temp files", "remove temporary files")
        results = search.search("delete temp files")
        assert isinstance(results, list)

    def test_search_result_has_similarity_field(self, search):
        """Each result entry contains a similarity score."""
        _add(search, "open browser", "launch web browser")
        # Use same text to guarantee a match above threshold
        results = search.search("open browser", min_similarity=0.0)
        assert len(results) > 0
        assert "similarity" in results[0]

    def test_search_respects_top_k(self, search):
        """search() returns at most top_k results."""
        for i in range(6):
            _add(search, f"cmd {i}", f"goal {i}")

        results = search.search("cmd 0", top_k=2, min_similarity=0.0)
        assert len(results) <= 2

    def test_search_filters_by_min_similarity(self, search):
        """Results below min_similarity are excluded."""
        _add(search, "completely unrelated content", "unrelated goal")
        # Request an impossibly high threshold — the fake embeddings are
        # orthogonal unit vectors so similarity is 0 for mismatches.
        results = search.search("totally different query", min_similarity=0.99)
        # Either no results or all results have similarity >= threshold
        for r in results:
            assert r["similarity"] >= 0.99

    def test_search_metadata_fields_in_results(self, search):
        """Result entries include user_input, goal, steps, success, timestamp."""
        _add(search, "install curl", "install package", steps=["s"], success=True, timestamp=42.0)
        results = search.search("install curl", min_similarity=0.0)
        assert len(results) > 0
        r = results[0]
        assert "user_input" in r
        assert "goal" in r
        assert "steps" in r
        assert "success" in r
        assert "timestamp" in r

    def test_search_does_not_mutate_metadata(self, search):
        """Adding similarity to results does not modify stored metadata."""
        _add(search, "backup data", "backup files")
        before = dict(search.metadata[0])
        search.search("backup", min_similarity=0.0)
        assert "similarity" not in search.metadata[0]
        assert search.metadata[0] == before


class TestGetSuccessRate:
    def test_returns_half_when_no_similar_results(self, search):
        """Returns 0.5 (unknown) when no similar commands found."""
        rate = search.get_success_rate("completely novel query")
        assert rate == pytest.approx(0.5)

    def test_full_success_rate(self, search):
        """Returns 1.0 when all similar commands succeeded."""
        text = "sync directory"
        _add(search, text, text, success=True)
        # Force min_similarity low enough to always match
        with patch.object(search, "search", return_value=[
            {"success": True},
            {"success": True},
        ]):
            rate = search.get_success_rate(text)
        assert rate == pytest.approx(1.0)

    def test_zero_success_rate(self, search):
        """Returns 0.0 when all similar commands failed."""
        with patch.object(search, "search", return_value=[
            {"success": False},
            {"success": False},
        ]):
            rate = search.get_success_rate("some query")
        assert rate == pytest.approx(0.0)

    def test_mixed_success_rate(self, search):
        """Returns correct ratio for mixed successes and failures."""
        with patch.object(search, "search", return_value=[
            {"success": True},
            {"success": False},
            {"success": True},
            {"success": True},
        ]):
            rate = search.get_success_rate("query")
        assert rate == pytest.approx(0.75)


class TestGetStats:
    def test_stats_empty_index(self, search):
        """Stats for empty index show zero commands."""
        stats = search.get_stats()
        assert stats["total_commands"] == 0
        assert stats["success_rate"] == 0.0

    def test_stats_total_commands(self, search):
        """total_commands matches number of indexed entries."""
        for _ in range(3):
            _add(search, "cmd", "goal")
        stats = search.get_stats()
        assert stats["total_commands"] == 3

    def test_stats_success_rate_all_success(self, search):
        """success_rate is 1.0 when all commands succeeded."""
        for _ in range(3):
            _add(search, "cmd", "goal", success=True)
        stats = search.get_stats()
        assert stats["success_rate"] == pytest.approx(1.0)

    def test_stats_success_rate_mixed(self, search):
        """success_rate is correct for a mix of outcomes."""
        _add(search, "c1", "g1", success=True)
        _add(search, "c2", "g2", success=False)
        stats = search.get_stats()
        assert stats["success_rate"] == pytest.approx(0.5)

    def test_stats_contains_cache_size_mb(self, search):
        """Stats include cache_size_mb after at least one command is indexed."""
        _add(search, "cmd", "goal")
        stats = search.get_stats()
        assert "cache_size_mb" in stats
        assert stats["cache_size_mb"] >= 0
