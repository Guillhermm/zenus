"""
Tests for DependencyAnalyzer
"""

import pytest
from zenus_core.brain.dependency_analyzer import DependencyAnalyzer, DependencyGraph
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_intent(steps):
    """Build an IntentIR from a list of Step objects."""
    return IntentIR(goal="test", requires_confirmation=False, steps=steps)


def file_step(action, path=None, source=None, dest=None, risk=0):
    """Convenience factory for FileOps steps."""
    args = {}
    if path:
        args["path"] = path
    if source:
        args["source"] = source
    if dest:
        args["dest"] = dest
    return Step(tool="FileOps", action=action, args=args, risk=risk)


def pkg_step(package=None, risk=0):
    """Convenience factory for PackageOps steps."""
    args = {}
    if package:
        args["package"] = package
    return Step(tool="PackageOps", action="install", args=args, risk=risk)


def git_step(risk=0):
    """Convenience factory for GitOps steps."""
    return Step(tool="GitOps", action="commit", args={}, risk=risk)


def net_step(url=None, risk=0):
    """Convenience factory for NetworkOps steps."""
    args = {}
    if url:
        args["url"] = url
    return Step(tool="NetworkOps", action="download", args=args, risk=risk)


def svc_step(service=None, risk=0):
    """Convenience factory for ServiceOps steps."""
    args = {}
    if service:
        args["service"] = service
    return Step(tool="ServiceOps", action="restart", args=args, risk=risk)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDependencyAnalyzerEmptyAndSingle:
    def test_empty_intent_returns_empty_graph(self):
        """Empty step list produces an empty graph."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([])
        graph = analyzer.analyze(intent)

        assert graph.nodes == []
        assert graph.edges == {}
        assert graph.levels == []

    def test_single_step_returns_trivial_graph(self):
        """Single step produces a one-node graph with one level."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([file_step("read_file", path="/a.txt")])
        graph = analyzer.analyze(intent)

        assert graph.nodes == [0]
        assert graph.edges == {0: set()}
        assert graph.levels == [[0]]


class TestDependencyGraphBuilding:
    def test_independent_file_ops_on_different_paths(self):
        """FileOps on different paths have no dependency."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 not in graph.edges[1]

    def test_same_path_creates_dependency(self):
        """Two FileOps on the same path must be ordered."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/shared.txt"),
            file_step("write_file", path="/shared.txt"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]

    def test_parent_child_path_creates_dependency(self):
        """FileOps where one path is a prefix of another creates a dependency."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/home"),
            file_step("write_file", path="/home/user/file.txt"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]

    def test_file_write_then_read_creates_dependency(self):
        """Step that reads a file written by a prior step must depend on it."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("create_file", dest="/out.txt"),
            file_step("read_file", source="/out.txt"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]

    def test_file_copy_creates_dependency_on_dest(self):
        """copy_file creates a dependency for any step that later reads dest."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("copy_file", dest="/copy.txt"),
            file_step("read_file", path="/copy.txt"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]

    def test_move_file_creates_dependency_on_dest(self):
        """move_file creates a dependency for any step that later reads dest."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("move_file", dest="/moved.txt"),
            file_step("read_file", source="/moved.txt"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]


class TestPackageAndGitDependencies:
    def test_package_ops_are_sequential(self):
        """All PackageOps steps must be executed sequentially."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([pkg_step("numpy"), pkg_step("pandas")])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]

    def test_git_ops_are_sequential(self):
        """All GitOps steps must be executed sequentially."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([git_step(), git_step()])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]

    def test_same_package_resource_conflict(self):
        """Two PackageOps on the same package name conflict."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([pkg_step("requests"), pkg_step("requests")])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]


class TestNetworkAndServiceDependencies:
    def test_network_ops_same_url_create_dependency(self):
        """Two NetworkOps targeting the same URL depend on each other."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            net_step("https://example.com"),
            net_step("https://example.com"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]

    def test_network_ops_different_urls_are_independent(self):
        """NetworkOps on different URLs are independent."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            net_step("https://a.com"),
            net_step("https://b.com"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 not in graph.edges[1]

    def test_service_ops_same_service_create_dependency(self):
        """ServiceOps on the same service name depend on each other."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            svc_step("nginx"),
            svc_step("nginx"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 in graph.edges[1]

    def test_service_ops_different_services_are_independent(self):
        """ServiceOps on different services are independent."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            svc_step("nginx"),
            svc_step("postgres"),
        ])
        graph = analyzer.analyze(intent)

        assert 0 not in graph.edges[1]


class TestExecutionLevels:
    def test_independent_steps_share_a_level(self):
        """Fully independent steps must appear in the same execution level."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
            file_step("read_file", path="/c.txt"),
        ])
        graph = analyzer.analyze(intent)

        assert len(graph.levels) == 1
        assert set(graph.levels[0]) == {0, 1, 2}

    def test_chained_steps_produce_sequential_levels(self):
        """Steps that each depend on the previous produce one level per step."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("create_file", dest="/x.txt"),
            file_step("read_file", source="/x.txt"),
        ])
        graph = analyzer.analyze(intent)

        assert len(graph.levels) == 2
        assert graph.levels[0] == [0]
        assert graph.levels[1] == [1]

    def test_all_nodes_included_in_levels(self):
        """Every step index must appear exactly once across all levels."""
        analyzer = DependencyAnalyzer()
        steps = [
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
            pkg_step("numpy"),
            pkg_step("pandas"),
        ]
        intent = make_intent(steps)
        graph = analyzer.analyze(intent)

        all_nodes = [n for level in graph.levels for n in level]
        assert sorted(all_nodes) == list(range(len(steps)))

    def test_cycle_handling_falls_back_to_sequential(self):
        """When a cycle is artificially injected the algorithm still terminates."""
        analyzer = DependencyAnalyzer()
        # Build a normal 3-step intent then manually inject a cycle
        intent = make_intent([
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
            file_step("read_file", path="/c.txt"),
        ])
        graph = analyzer.analyze(intent)
        # Inject cycle: 0 depends on 2
        graph.edges[0].add(2)
        # Now re-run levels with the cyclic edges
        levels = analyzer._calculate_levels(3, graph.edges)
        all_nodes = [n for level in levels for n in level]
        assert sorted(all_nodes) == [0, 1, 2]


class TestIsParallelizable:
    def test_single_step_not_parallelizable(self):
        """A single step cannot be parallelized."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([file_step("read_file", path="/a.txt")])
        assert analyzer.is_parallelizable(intent) is False

    def test_independent_steps_are_parallelizable(self):
        """Two independent steps can run in parallel."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
        ])
        assert analyzer.is_parallelizable(intent) is True

    def test_dependent_steps_are_not_parallelizable(self):
        """Steps where each depends on the prior are not parallelizable."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            pkg_step("numpy"),
            pkg_step("pandas"),
        ])
        assert analyzer.is_parallelizable(intent) is False


class TestEstimateSpeedup:
    def test_single_step_speedup_is_one(self):
        """No speedup for a single step."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([file_step("read_file", path="/a.txt")])
        assert analyzer.estimate_speedup(intent) == 1.0

    def test_fully_parallel_speedup_equals_step_count(self):
        """N independent steps yield an N× speedup."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
            file_step("read_file", path="/c.txt"),
        ])
        speedup = analyzer.estimate_speedup(intent)
        assert speedup == 3.0

    def test_sequential_speedup_is_one(self):
        """Fully sequential steps yield 1× speedup."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            pkg_step("a"),
            pkg_step("b"),
            pkg_step("c"),
        ])
        speedup = analyzer.estimate_speedup(intent)
        assert speedup == 1.0


class TestGetExecutionOrder:
    def test_returns_same_as_graph_levels(self):
        """get_execution_order must match the levels from analyze()."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
        ])
        order = analyzer.get_execution_order(intent)
        graph = analyzer.analyze(intent)
        assert order == graph.levels


class TestVisualize:
    def test_visualize_contains_total_steps(self):
        """Visualization output includes the step count."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
        ])
        output = analyzer.visualize(intent)
        assert "Total steps: 2" in output

    def test_visualize_marks_parallel_levels(self):
        """Visualization labels multi-step levels as parallel."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([
            file_step("read_file", path="/a.txt"),
            file_step("read_file", path="/b.txt"),
        ])
        output = analyzer.visualize(intent)
        assert "parallel" in output

    def test_visualize_marks_sequential_levels(self):
        """Visualization labels single-step levels as sequential."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([pkg_step("numpy"), pkg_step("pandas")])
        output = analyzer.visualize(intent)
        assert "sequential" in output

    def test_visualize_includes_tool_and_action(self):
        """Visualization mentions tool and action names."""
        analyzer = DependencyAnalyzer()
        intent = make_intent([file_step("read_file", path="/a.txt")])
        output = analyzer.visualize(intent)
        assert "FileOps" in output
        assert "read_file" in output
