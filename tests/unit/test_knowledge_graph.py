"""
Tests for KnowledgeGraph.

All tests are pure unit tests — no disk I/O (temp storage paths), no LLM calls.
Covers:
- Entity upsert and observation counting
- Edge upsert and weight increment
- Self-loop avoidance
- ingest_action for all registered tool/operation pairs
- what_depends_on / what_would_be_affected / related_to queries
- query() natural language dispatch
- get_stats()
- JSON persistence round-trip
- Thread-safety concurrent upserts
- Singleton factory
"""

import json
import threading
import tempfile
import pytest
from pathlib import Path

from zenus_core.brain.knowledge_graph import (
    EdgeType,
    Entity,
    EntityType,
    KnowledgeGraph,
    get_knowledge_graph,
    _short_label,
    _resolve_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_graph(tmp_path):
    """Fresh KnowledgeGraph backed by a temp file."""
    return KnowledgeGraph(storage_path=str(tmp_path / "kg.json"))


# ---------------------------------------------------------------------------
# Entity upsert
# ---------------------------------------------------------------------------

class TestEntityUpsert:
    def test_add_new_entity(self, tmp_graph):
        e = tmp_graph.add_entity("/home/user/file.txt", EntityType.FILE)
        assert e.id == "/home/user/file.txt"
        assert e.type == EntityType.FILE

    def test_add_entity_empty_id_raises(self, tmp_graph):
        with pytest.raises(ValueError):
            tmp_graph.add_entity("   ")

    def test_upsert_increments_observation_count(self, tmp_graph):
        tmp_graph.add_entity("foo", EntityType.FILE)
        tmp_graph.add_entity("foo", EntityType.FILE)
        assert tmp_graph._nodes["foo"].observation_count == 2

    def test_upsert_returns_same_entity(self, tmp_graph):
        e1 = tmp_graph.add_entity("foo")
        e2 = tmp_graph.add_entity("foo")
        assert e1 is e2

    def test_label_defaults_to_short(self, tmp_graph):
        e = tmp_graph.add_entity("/home/user/config.yaml")
        assert e.label == "config.yaml"

    def test_custom_label(self, tmp_graph):
        e = tmp_graph.add_entity("nginx", EntityType.SERVICE, label="nginx web server")
        assert e.label == "nginx web server"

    def test_metadata_stored(self, tmp_graph):
        e = tmp_graph.add_entity("myapp", metadata={"version": "1.0"})
        assert e.metadata["version"] == "1.0"

    def test_entity_count_increases(self, tmp_graph):
        tmp_graph.add_entity("a")
        tmp_graph.add_entity("b")
        assert len(tmp_graph) == 2


# ---------------------------------------------------------------------------
# Edge upsert
# ---------------------------------------------------------------------------

class TestEdgeUpsert:
    def test_add_new_edge(self, tmp_graph):
        e = tmp_graph.add_edge("app.py", "config.yaml", EdgeType.READS)
        assert e.source_id == "app.py"
        assert e.target_id == "config.yaml"
        assert e.edge_type == EdgeType.READS

    def test_upsert_increments_weight(self, tmp_graph):
        tmp_graph.add_edge("a", "b", EdgeType.READS)
        tmp_graph.add_edge("a", "b", EdgeType.READS)
        key = "a|reads|b"
        assert tmp_graph._edges[key].weight == 2

    def test_edge_auto_creates_nodes(self, tmp_graph):
        tmp_graph.add_edge("src", "tgt")
        assert "src" in tmp_graph._nodes
        assert "tgt" in tmp_graph._nodes

    def test_edge_key_unique_per_type(self, tmp_graph):
        tmp_graph.add_edge("a", "b", EdgeType.READS)
        tmp_graph.add_edge("a", "b", EdgeType.WRITES)
        assert len(tmp_graph._edges) == 2


# ---------------------------------------------------------------------------
# ingest_action
# ---------------------------------------------------------------------------

class TestIngestAction:
    def test_fileops_write_file(self, tmp_graph):
        created = tmp_graph.ingest_action("FileOps", "write_file", {"path": "/etc/hosts"})
        assert created >= 1
        assert "/etc/hosts" in tmp_graph._nodes

    def test_fileops_scan_dir(self, tmp_graph):
        created = tmp_graph.ingest_action("FileOps", "scan", {"path": "/home/user"})
        assert created >= 1

    def test_fileops_move(self, tmp_graph):
        tmp_graph.ingest_action("FileOps", "move", {"source": "a.txt", "destination": "b.txt"})
        assert "a.txt" in tmp_graph._nodes
        assert "b.txt" in tmp_graph._nodes

    def test_fileops_mkdir(self, tmp_graph):
        tmp_graph.ingest_action("FileOps", "mkdir", {"path": "/tmp/newdir"})
        assert "/tmp/newdir" in tmp_graph._nodes

    def test_textops_read(self, tmp_graph):
        tmp_graph.ingest_action("TextOps", "read", {"path": "README.md"})
        assert "README.md" in tmp_graph._nodes

    def test_textops_write(self, tmp_graph):
        tmp_graph.ingest_action("TextOps", "write", {"path": "output.txt"})
        assert "output.txt" in tmp_graph._nodes

    def test_packageops_install(self, tmp_graph):
        tmp_graph.ingest_action("PackageOps", "install", {"package": "requests"})
        assert "requests" in tmp_graph._nodes

    def test_serviceops_start(self, tmp_graph):
        tmp_graph.ingest_action("ServiceOps", "start", {"service": "nginx"})
        assert "nginx" in tmp_graph._nodes

    def test_gitops_clone(self, tmp_graph):
        tmp_graph.ingest_action("GitOps", "clone", {"url": "https://github.com/x/y", "path": "/home/user/y"})
        assert "/home/user/y" in tmp_graph._nodes

    def test_shellops_run(self, tmp_graph):
        tmp_graph.ingest_action("ShellOps", "run", {"command": "ls -la"})
        assert "ls -la" in tmp_graph._nodes

    def test_unknown_tool_returns_zero(self, tmp_graph):
        created = tmp_graph.ingest_action("UnknownTool", "do_thing", {"x": "y"})
        assert created == 0

    def test_missing_param_skipped(self, tmp_graph):
        # write_file needs "path" — without it, nothing is created
        created = tmp_graph.ingest_action("FileOps", "write_file", {})
        assert created == 0

    def test_ingest_saves_to_disk(self, tmp_path):
        path = tmp_path / "kg.json"
        g = KnowledgeGraph(storage_path=str(path))
        g.ingest_action("FileOps", "write_file", {"path": "/etc/hosts"})
        assert path.exists()


# ---------------------------------------------------------------------------
# Dependency queries
# ---------------------------------------------------------------------------

class TestDependencyQueries:
    def test_what_depends_on_direct(self, tmp_graph):
        tmp_graph.add_entity("config.yaml", EntityType.FILE)
        tmp_graph.add_entity("app.py", EntityType.FILE)
        tmp_graph.add_edge("app.py", "config.yaml", EdgeType.READS)
        results = tmp_graph.what_depends_on("config.yaml")
        assert any(e.id == "app.py" for e in results)

    def test_what_depends_on_empty(self, tmp_graph):
        tmp_graph.add_entity("lonely.txt")
        assert tmp_graph.what_depends_on("lonely.txt") == []

    def test_what_would_be_affected_bfs(self, tmp_graph):
        tmp_graph.add_edge("a", "b", EdgeType.DEPENDS_ON)
        tmp_graph.add_edge("b", "c", EdgeType.DEPENDS_ON)
        results = tmp_graph.what_would_be_affected("a")
        ids = [e.id for e in results]
        assert "b" in ids
        assert "c" in ids

    def test_what_would_be_affected_respects_depth(self, tmp_graph):
        # a → b → c → d → e
        for x, y in [("a","b"),("b","c"),("c","d"),("d","e")]:
            tmp_graph.add_edge(x, y, EdgeType.DEPENDS_ON)
        results = tmp_graph.what_would_be_affected("a", max_depth=2)
        ids = [e.id for e in results]
        assert "b" in ids
        assert "c" in ids
        assert "d" not in ids  # beyond depth 2

    def test_what_would_be_affected_no_cycles(self, tmp_graph):
        tmp_graph.add_edge("a", "b", EdgeType.DEPENDS_ON)
        tmp_graph.add_edge("b", "a", EdgeType.DEPENDS_ON)  # cycle
        results = tmp_graph.what_would_be_affected("a")
        # Should not loop forever
        assert isinstance(results, list)

    def test_related_to_both_directions(self, tmp_graph):
        tmp_graph.add_edge("a", "b", EdgeType.READS)
        tmp_graph.add_edge("c", "a", EdgeType.WRITES)
        results = tmp_graph.related_to("a")
        ids = [e.id for e in results]
        assert "b" in ids
        assert "c" in ids

    def test_related_to_empty(self, tmp_graph):
        tmp_graph.add_entity("island")
        assert tmp_graph.related_to("island") == []


# ---------------------------------------------------------------------------
# Natural language query dispatch
# ---------------------------------------------------------------------------

class TestQueryDispatch:
    def test_depends_on_pattern(self, tmp_graph):
        tmp_graph.add_edge("app.py", "config.yaml", EdgeType.READS)
        result = tmp_graph.query("what depends on config.yaml")
        assert "app.py" in result or "1 entities" in result

    def test_affected_pattern(self, tmp_graph):
        tmp_graph.add_edge("config.yaml", "app.py", EdgeType.CONFIGURES)
        result = tmp_graph.query("what would be affected by config.yaml")
        assert "app.py" in result or "1 " in result

    def test_related_pattern(self, tmp_graph):
        tmp_graph.add_edge("a", "b", EdgeType.READS)
        result = tmp_graph.query("what is related to a")
        assert "b" in result

    def test_no_match_returns_help(self, tmp_graph):
        result = tmp_graph.query("show me everything")
        assert "Try:" in result

    def test_no_results_graceful(self, tmp_graph):
        result = tmp_graph.query("what depends on nonexistent.txt")
        assert "No" in result or "nonexistent" in result


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_graph(self, tmp_graph):
        stats = tmp_graph.get_stats()
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0

    def test_after_ingestion(self, tmp_graph):
        tmp_graph.ingest_action("FileOps", "write_file", {"path": "/etc/hosts"})
        stats = tmp_graph.get_stats()
        assert stats["total_nodes"] >= 1

    def test_nodes_by_type(self, tmp_graph):
        tmp_graph.add_entity("f", EntityType.FILE)
        tmp_graph.add_entity("s", EntityType.SERVICE)
        stats = tmp_graph.get_stats()
        assert stats["nodes_by_type"].get("file", 0) >= 1
        assert stats["nodes_by_type"].get("service", 0) >= 1


# ---------------------------------------------------------------------------
# JSON persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_reload(self, tmp_path):
        path = str(tmp_path / "kg.json")
        g1 = KnowledgeGraph(storage_path=path)
        g1.add_entity("myfile.txt", EntityType.FILE)
        g1.add_edge("app.py", "myfile.txt", EdgeType.READS)
        g1._save()

        g2 = KnowledgeGraph(storage_path=path)
        assert "myfile.txt" in g2._nodes
        assert "app.py" in g2._nodes
        assert len(g2._edges) == 1

    def test_corrupted_file_starts_fresh(self, tmp_path):
        path = tmp_path / "kg.json"
        path.write_text("NOT VALID JSON")
        g = KnowledgeGraph(storage_path=str(path))
        assert len(g._nodes) == 0

    def test_save_uses_atomic_write(self, tmp_path):
        path = str(tmp_path / "kg.json")
        g = KnowledgeGraph(storage_path=path)
        g.add_entity("x")
        g._save()
        # .tmp file should be gone after atomic rename
        assert not Path(path).with_suffix(".tmp").exists()

    def test_entity_type_restored(self, tmp_path):
        path = str(tmp_path / "kg.json")
        g1 = KnowledgeGraph(storage_path=path)
        g1.add_entity("svc", EntityType.SERVICE)
        g1._save()

        g2 = KnowledgeGraph(storage_path=path)
        assert g2._nodes["svc"].type == EntityType.SERVICE

    def test_edge_type_restored(self, tmp_path):
        path = str(tmp_path / "kg.json")
        g1 = KnowledgeGraph(storage_path=path)
        g1.add_edge("a", "b", EdgeType.CONFIGURES)
        g1._save()

        g2 = KnowledgeGraph(storage_path=path)
        edge = list(g2._edges.values())[0]
        assert edge.edge_type == EdgeType.CONFIGURES


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_add_entity(self, tmp_graph):
        errors = []

        def add(i):
            try:
                tmp_graph.add_entity(f"entity_{i}", EntityType.FILE)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(tmp_graph) == 50

    def test_concurrent_ingest(self, tmp_graph):
        errors = []

        def ingest(i):
            try:
                tmp_graph.ingest_action("FileOps", "write_file", {"path": f"/tmp/file_{i}.txt"})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=ingest, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_short_label_path(self):
        assert _short_label("/home/user/config.yaml") == "config.yaml"

    def test_short_label_plain(self):
        assert _short_label("nginx") == "nginx"

    def test_resolve_id_param(self):
        assert _resolve_id(("param", "path"), {"path": "/etc/hosts"}) == "/etc/hosts"

    def test_resolve_id_missing_param(self):
        assert _resolve_id(("param", "path"), {}) == ""

    def test_resolve_id_literal(self):
        assert _resolve_id("literal_value", {}) == "literal_value"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_returns_knowledge_graph(self):
        g = get_knowledge_graph()
        assert isinstance(g, KnowledgeGraph)

    def test_singleton_same_instance(self):
        g1 = get_knowledge_graph()
        g2 = get_knowledge_graph()
        assert g1 is g2
