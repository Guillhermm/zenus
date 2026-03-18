"""
Unit tests for tools/base.py – Tool base class.
"""

import pytest
from zenus_core.tools.base import Tool


# ===========================================================================
# Tool base class
# ===========================================================================

class TestToolInterface:

    def test_dry_run_raises_not_implemented(self):
        """dry_run must be overridden by subclasses."""
        tool = Tool()
        with pytest.raises(NotImplementedError):
            tool.dry_run()

    def test_execute_raises_not_implemented(self):
        """execute must be overridden by subclasses."""
        tool = Tool()
        with pytest.raises(NotImplementedError):
            tool.execute()

    def test_dry_run_raises_with_kwargs(self):
        tool = Tool()
        with pytest.raises(NotImplementedError):
            tool.dry_run(path="/tmp", mode="r")

    def test_execute_raises_with_kwargs(self):
        tool = Tool()
        with pytest.raises(NotImplementedError):
            tool.execute(path="/tmp", content="hello")


class TestToolSubclass:

    def test_subclass_can_override_dry_run(self):
        class MyTool(Tool):
            name = "my_tool"
            def dry_run(self, **kwargs):
                return f"would execute with {kwargs}"
            def execute(self, **kwargs):
                return f"executed with {kwargs}"

        t = MyTool()
        assert t.dry_run(x=1) == "would execute with {'x': 1}"

    def test_subclass_can_override_execute(self):
        class MyTool(Tool):
            name = "my_tool"
            def dry_run(self, **kwargs):
                return "dry"
            def execute(self, **kwargs):
                return "real"

        t = MyTool()
        assert t.execute() == "real"

    def test_subclass_dry_run_not_raises(self):
        class ReadTool(Tool):
            name = "read"
            def dry_run(self, **kwargs):
                return "would read"
            def execute(self, **kwargs):
                return "reading"

        t = ReadTool()
        result = t.dry_run(path="/etc/hosts")
        assert result == "would read"

    def test_partial_subclass_execute_still_raises(self):
        """If only dry_run is implemented, execute still raises."""
        class PartialTool(Tool):
            name = "partial"
            def dry_run(self, **kwargs):
                return "dry"

        t = PartialTool()
        with pytest.raises(NotImplementedError):
            t.execute()

    def test_partial_subclass_dry_run_still_raises(self):
        """If only execute is implemented, dry_run still raises."""
        class PartialTool(Tool):
            name = "partial"
            def execute(self, **kwargs):
                return "real"

        t = PartialTool()
        with pytest.raises(NotImplementedError):
            t.dry_run()

    def test_name_attribute_on_subclass(self):
        class FileTool(Tool):
            name = "FileOps"
            def dry_run(self, **kwargs): return ""
            def execute(self, **kwargs): return ""

        t = FileTool()
        assert t.name == "FileOps"

    def test_multiple_subclasses_independent(self):
        class ToolA(Tool):
            name = "A"
            def dry_run(self, **kwargs): return "a-dry"
            def execute(self, **kwargs): return "a-exec"

        class ToolB(Tool):
            name = "B"
            def dry_run(self, **kwargs): return "b-dry"
            def execute(self, **kwargs): return "b-exec"

        a, b = ToolA(), ToolB()
        assert a.execute() == "a-exec"
        assert b.execute() == "b-exec"
        assert a.name != b.name
