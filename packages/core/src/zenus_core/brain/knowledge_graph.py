"""
Knowledge Graph

Maintains a directed graph of relationships between entities observed
during Zenus execution: files, directories, processes, services, packages,
environment variables, and shell commands.

Nodes: entities (things that exist)
Edges: typed relationships (how entities relate to each other)

The graph is built incrementally from Action objects emitted by the
ActionTracker. It persists to ~/.zenus/knowledge_graph.json between
sessions and can answer structural queries without calling the LLM.

Queries:
    graph.what_depends_on("~/.zshrc")
    graph.what_would_be_affected("nginx.service")
    graph.related_to("requirements.txt")
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    FILE = "file"
    DIR = "dir"
    PROCESS = "process"
    SERVICE = "service"
    PACKAGE = "package"
    ENV_VAR = "env_var"
    COMMAND = "command"
    UNKNOWN = "unknown"


class EdgeType(str, Enum):
    DEPENDS_ON = "depends_on"
    READS = "reads"
    WRITES = "writes"
    RUNS = "runs"
    CONFIGURES = "configures"
    IMPORTS = "imports"
    PRODUCES = "produces"
    CONTAINS = "contains"
    RELATED_TO = "related_to"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Entity:
    id: str                          # Canonical identifier (e.g. path, service name)
    type: EntityType
    label: str                       # Human-readable short name
    metadata: Dict[str, Any] = field(default_factory=dict)
    first_seen: str = field(default_factory=lambda: _now())
    last_seen: str = field(default_factory=lambda: _now())
    observation_count: int = 1

    def touch(self) -> None:
        self.last_seen = _now()
        self.observation_count += 1


@dataclass
class Edge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: int = 1
    last_seen: str = field(default_factory=lambda: _now())

    def key(self) -> str:
        return f"{self.source_id}|{self.edge_type.value}|{self.target_id}"

    def touch(self) -> None:
        self.last_seen = _now()
        self.weight += 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Ingestion map: (tool, operation) → list of (entity_args, edge_args)
# Each entry tells the ingester how to turn an Action into graph elements.
# ---------------------------------------------------------------------------

# Sentinel: read the value from Action.params[key]
_P = lambda key: ("param", key)  # noqa: E731

# How to map tool/operation pairs to graph relationships
# Format: (source_entity_type, source_id_key, edge_type, target_entity_type, target_id_key)
# id_key is either a literal string or _P(param_key) to look up from action.params

_INGESTION_MAP: Dict[tuple, List[tuple]] = {
    # FileOps
    ("FileOps", "scan"):       [(_P("path"),  EntityType.DIR,     EdgeType.READS,    _P("path"),  EntityType.DIR)],
    ("FileOps", "mkdir"):      [(_P("path"),  EntityType.DIR,     EdgeType.PRODUCES, _P("path"),  EntityType.DIR)],
    ("FileOps", "move"):       [(_P("source"), EntityType.FILE,   EdgeType.PRODUCES, _P("destination"), EntityType.FILE)],
    ("FileOps", "write_file"): [(_P("path"),  EntityType.FILE,    EdgeType.WRITES,   _P("path"),  EntityType.FILE)],
    ("FileOps", "touch"):      [(_P("path"),  EntityType.FILE,    EdgeType.PRODUCES, _P("path"),  EntityType.FILE)],
    # TextOps
    ("TextOps", "read"):       [(_P("path"),  EntityType.FILE,    EdgeType.READS,    _P("path"),  EntityType.FILE)],
    ("TextOps", "write"):      [(_P("path"),  EntityType.FILE,    EdgeType.WRITES,   _P("path"),  EntityType.FILE)],
    ("TextOps", "append"):     [(_P("path"),  EntityType.FILE,    EdgeType.WRITES,   _P("path"),  EntityType.FILE)],
    # PackageOps
    ("PackageOps", "install"): [(_P("package"), EntityType.PACKAGE, EdgeType.DEPENDS_ON, _P("package"), EntityType.PACKAGE)],
    ("PackageOps", "remove"):  [(_P("package"), EntityType.PACKAGE, EdgeType.RELATED_TO, _P("package"), EntityType.PACKAGE)],
    # ServiceOps
    ("ServiceOps", "start"):   [(_P("service"), EntityType.SERVICE, EdgeType.RUNS,    _P("service"), EntityType.SERVICE)],
    ("ServiceOps", "stop"):    [(_P("service"), EntityType.SERVICE, EdgeType.RELATED_TO, _P("service"), EntityType.SERVICE)],
    ("ServiceOps", "restart"): [(_P("service"), EntityType.SERVICE, EdgeType.RUNS,    _P("service"), EntityType.SERVICE)],
    # GitOps
    ("GitOps", "clone"):       [(_P("url"),  EntityType.COMMAND, EdgeType.PRODUCES, _P("path"), EntityType.DIR)],
    ("GitOps", "commit"):      [(_P("path"),  EntityType.DIR,    EdgeType.WRITES,   _P("path"), EntityType.DIR)],
    # ProcessOps
    ("ProcessOps", "kill"):    [(_P("name"),  EntityType.PROCESS, EdgeType.RELATED_TO, _P("name"), EntityType.PROCESS)],
    # ShellOps/CodeExec
    ("ShellOps", "run"):       [(_P("command"), EntityType.COMMAND, EdgeType.RUNS,   _P("command"), EntityType.COMMAND)],
    ("CodeExec", "python"):    [(_P("code"), EntityType.COMMAND,   EdgeType.RUNS,   _P("code"), EntityType.COMMAND)],
    ("CodeExec", "bash_script"):[(_P("code"), EntityType.COMMAND, EdgeType.RUNS,   _P("code"), EntityType.COMMAND)],
}


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------

class KnowledgeGraph:
    """
    In-process directed graph of entity relationships.

    Thread-safe: all mutations go through a single RLock.
    Persisted to JSON after every ingestion so the graph survives restarts.
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        if storage_path is None:
            storage_path = str(Path.home() / ".zenus" / "knowledge_graph.json")
        self._path = Path(storage_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._nodes: Dict[str, Entity] = {}
        self._edges: Dict[str, Edge] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public mutation API
    # ------------------------------------------------------------------

    def add_entity(
        self,
        entity_id: str,
        entity_type: EntityType = EntityType.UNKNOWN,
        label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Entity:
        """Upsert an entity; touch observation count if already present."""
        entity_id = entity_id.strip()
        if not entity_id:
            raise ValueError("entity_id must not be empty")
        with self._lock:
            if entity_id in self._nodes:
                self._nodes[entity_id].touch()
                return self._nodes[entity_id]
            entity = Entity(
                id=entity_id,
                type=entity_type,
                label=label or _short_label(entity_id),
                metadata=metadata or {},
            )
            self._nodes[entity_id] = entity
            return entity

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType = EdgeType.RELATED_TO,
    ) -> Edge:
        """Upsert a directed edge; increment weight if already present."""
        # Ensure both endpoints exist
        if source_id not in self._nodes:
            self.add_entity(source_id)
        if target_id not in self._nodes:
            self.add_entity(target_id)

        edge = Edge(source_id=source_id, target_id=target_id, edge_type=edge_type)
        key = edge.key()
        with self._lock:
            if key in self._edges:
                self._edges[key].touch()
                return self._edges[key]
            self._edges[key] = edge
            return edge

    def ingest_action(self, tool: str, operation: str, params: Dict[str, Any]) -> int:
        """
        Ingest an executed action and derive graph elements from it.

        Args:
            tool:      Tool name as recorded by ActionTracker (e.g. "FileOps")
            operation: Operation name (e.g. "write_file")
            params:    The step args dict

        Returns:
            Number of new graph elements created (nodes + edges).
        """
        rules = _INGESTION_MAP.get((tool, operation), [])
        if not rules:
            return 0

        created = 0
        for src_id_spec, src_type, edge_type, tgt_id_spec, tgt_type in rules:
            src_id = _resolve_id(src_id_spec, params)
            tgt_id = _resolve_id(tgt_id_spec, params)
            if not src_id or not tgt_id:
                continue

            # When source and target are the same entity, just record it as
            # a node (no self-loop edge needed)
            if src_id == tgt_id:
                node_before = len(self._nodes)
                self.add_entity(src_id, src_type)
                created += len(self._nodes) - node_before
                continue

            before = len(self._nodes) + len(self._edges)
            self.add_entity(src_id, src_type)
            self.add_entity(tgt_id, tgt_type)
            self.add_edge(src_id, tgt_id, edge_type)
            created += (len(self._nodes) + len(self._edges)) - before

        if rules:
            self._save()

        return created

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def what_depends_on(self, entity_id: str) -> List[Entity]:
        """
        Return all entities that have an outgoing edge pointing TO entity_id.
        Answers: "what would break if entity_id disappeared?"
        """
        with self._lock:
            results = [
                self._nodes[e.source_id]
                for e in self._edges.values()
                if e.target_id == entity_id and e.source_id in self._nodes
            ]
        return results

    def what_would_be_affected(self, entity_id: str, max_depth: int = 3) -> List[Entity]:
        """
        BFS over outgoing edges from entity_id up to max_depth hops.
        Answers: "if I change/remove entity_id, what else is touched?"
        """
        visited: Set[str] = set()
        queue: deque = deque([(entity_id, 0)])
        results: List[Entity] = []

        with self._lock:
            while queue:
                current_id, depth = queue.popleft()
                if current_id in visited or depth > max_depth:
                    continue
                visited.add(current_id)
                if depth > 0:  # Don't include the starting entity itself
                    if current_id in self._nodes and current_id != entity_id:
                        results.append(self._nodes[current_id])
                for edge in self._edges.values():
                    if edge.source_id == current_id and edge.target_id not in visited:
                        queue.append((edge.target_id, depth + 1))

        return results

    def related_to(self, entity_id: str) -> List[Entity]:
        """Return all directly connected entities (both directions)."""
        with self._lock:
            connected_ids: Set[str] = set()
            for edge in self._edges.values():
                if edge.source_id == entity_id:
                    connected_ids.add(edge.target_id)
                elif edge.target_id == entity_id:
                    connected_ids.add(edge.source_id)
            return [self._nodes[eid] for eid in connected_ids if eid in self._nodes]

    def query(self, question: str) -> str:
        """
        Simple keyword dispatch for natural-language graph queries.
        Returns a human-readable answer string.
        """
        import re
        q = question.lower()

        # Extract entity reference from common question patterns
        # "what depends on X", "who uses X", "what needs X"
        depends_pattern = re.search(
            r"(?:depends on|uses|needs|requires|reads|imports)\s+['\"]?([^\s'\"?]+)", q
        )
        # "what would be affected by X", "what breaks if X changes"
        affected_pattern = re.search(
            r"(?:affected by|breaks if|changes to|impact of)\s+['\"]?([^\s'\"?]+)", q
        )
        # "what is related to X", "what is connected to X"
        related_pattern = re.search(
            r"(?:related to|connected to|linked to)\s+['\"]?([^\s'\"?]+)", q
        )

        if depends_pattern:
            entity_id = depends_pattern.group(1)
            results = self.what_depends_on(entity_id)
            if not results:
                return f"No known entities depend on '{entity_id}'."
            names = [e.label for e in results]
            return f"{len(results)} entities depend on '{entity_id}': {', '.join(names)}"

        if affected_pattern:
            entity_id = affected_pattern.group(1)
            results = self.what_would_be_affected(entity_id)
            if not results:
                return f"No downstream effects found for '{entity_id}'."
            names = [e.label for e in results]
            return f"Changing '{entity_id}' may affect {len(results)} entities: {', '.join(names)}"

        if related_pattern:
            entity_id = related_pattern.group(1)
            results = self.related_to(entity_id)
            if not results:
                return f"No known relationships for '{entity_id}'."
            names = [e.label for e in results]
            return f"'{entity_id}' is connected to: {', '.join(names)}"

        return (
            "Try: 'what depends on <entity>', "
            "'what would be affected by <entity>', or "
            "'what is related to <entity>'"
        )

    # ------------------------------------------------------------------
    # Stats / introspection
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Summary suitable for inclusion in WorldModel.get_summary()."""
        with self._lock:
            node_counts: Dict[str, int] = {}
            for n in self._nodes.values():
                node_counts[n.type.value] = node_counts.get(n.type.value, 0) + 1
            edge_counts: Dict[str, int] = {}
            for e in self._edges.values():
                edge_counts[e.edge_type.value] = edge_counts.get(e.edge_type.value, 0) + 1
            return {
                "total_nodes": len(self._nodes),
                "total_edges": len(self._edges),
                "nodes_by_type": node_counts,
                "edges_by_type": edge_counts,
            }

    def __len__(self) -> int:
        return len(self._nodes)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        with self._lock:
            try:
                data = {
                    "nodes": {k: asdict(v) for k, v in self._nodes.items()},
                    "edges": {k: asdict(v) for k, v in self._edges.items()},
                }
                tmp = self._path.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, indent=2))
                tmp.replace(self._path)
            except Exception as exc:
                logger.warning("KnowledgeGraph save failed: %s", exc)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for k, v in data.get("nodes", {}).items():
                v["type"] = EntityType(v["type"])
                self._nodes[k] = Entity(**v)
            for k, v in data.get("edges", {}).items():
                v["edge_type"] = EdgeType(v["edge_type"])
                self._edges[k] = Edge(**v)
            logger.debug(
                "KnowledgeGraph loaded: %d nodes, %d edges",
                len(self._nodes), len(self._edges),
            )
        except Exception as exc:
            logger.warning("KnowledgeGraph load failed (starting fresh): %s", exc)
            self._nodes.clear()
            self._edges.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_id(spec: Any, params: Dict[str, Any]) -> str:
    """Resolve a parameter spec to a concrete entity ID string."""
    if isinstance(spec, tuple) and spec[0] == "param":
        val = params.get(spec[1], "")
        return str(val).strip() if val else ""
    return str(spec).strip()


def _short_label(entity_id: str) -> str:
    """Return the last path component or the whole string if not path-like."""
    p = Path(entity_id)
    return p.name or entity_id


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_graph: Optional[KnowledgeGraph] = None
_graph_lock = threading.Lock()


def get_knowledge_graph() -> KnowledgeGraph:
    """Return the process-wide singleton KnowledgeGraph."""
    global _default_graph
    with _graph_lock:
        if _default_graph is None:
            _default_graph = KnowledgeGraph()
    return _default_graph
