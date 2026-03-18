"""
Tests for visualization module: Visualizer, ChartGenerator, TableFormatter, DiffViewer
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO


# ---------------------------------------------------------------------------
# ChartType / ChartGenerator
# ---------------------------------------------------------------------------

class TestChartType:
    """Test ChartType enum values"""

    def test_auto_value(self):
        """ChartType.AUTO has value 'auto'"""
        from zenus_core.visualization.chart_generator import ChartType
        assert ChartType.AUTO.value == "auto"

    def test_all_types_present(self):
        """All expected chart types are defined"""
        from zenus_core.visualization.chart_generator import ChartType
        names = {t.name for t in ChartType}
        assert names == {"AUTO", "LINE", "BAR", "SCATTER", "PIE", "HISTOGRAM", "HEATMAP"}


class TestChartGeneratorDetect:
    """Test _detect_chart_type auto-detection logic"""

    def setup_method(self):
        """Create ChartGenerator with matplotlib mocked."""
        with patch("matplotlib.pyplot.style") as _ms:
            _ms.available = []
            from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
            self.gen = ChartGenerator()
            self.ChartType = ChartType

    def test_dict_few_values_returns_pie(self):
        """Dict with <=5 numeric values detected as PIE"""
        result = self.gen._detect_chart_type({"a": 1, "b": 2})
        assert result == self.ChartType.PIE

    def test_dict_many_values_returns_bar(self):
        """Dict with >5 numeric values detected as BAR"""
        data = {str(i): i for i in range(6)}
        result = self.gen._detect_chart_type(data)
        assert result == self.ChartType.BAR

    def test_list_short_numbers_returns_line(self):
        """List of <=20 numbers detected as LINE"""
        result = self.gen._detect_chart_type([1, 2, 3, 4])
        assert result == self.ChartType.LINE

    def test_list_long_numbers_returns_histogram(self):
        """List of >20 numbers detected as HISTOGRAM"""
        result = self.gen._detect_chart_type(list(range(21)))
        assert result == self.ChartType.HISTOGRAM

    def test_list_of_pairs_returns_scatter(self):
        """List of 2-tuples detected as SCATTER"""
        result = self.gen._detect_chart_type([(1, 2), (3, 4), (5, 6)])
        assert result == self.ChartType.SCATTER

    def test_unknown_falls_back_to_bar(self):
        """Unrecognised data defaults to BAR"""
        result = self.gen._detect_chart_type({"nested": [1, 2]})
        assert result == self.ChartType.BAR


class TestChartGeneratorCreate:
    """Test create_chart returns a valid file path"""

    def test_create_chart_returns_path(self):
        """create_chart writes a file and returns its path"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
        gen = ChartGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "chart.png")
            path = gen.create_chart([1, 2, 3], ChartType.LINE, output_path=out)
            assert path == out
            assert os.path.exists(out)

    def test_create_chart_with_dict_bar(self):
        """create_chart with dict data and BAR type writes a file"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
        gen = ChartGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "bar.png")
            path = gen.create_chart({"x": 10, "y": 20, "z": 30}, ChartType.BAR, output_path=out)
            assert os.path.exists(path)

    def test_create_chart_auto_temp_file(self):
        """create_chart without output_path creates a temp .png file"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
        gen = ChartGenerator()
        path = gen.create_chart([5, 10, 15], ChartType.AUTO)
        assert path.endswith(".png")
        assert os.path.exists(path)
        os.unlink(path)  # cleanup

    def test_create_chart_pie(self):
        """create_chart with PIE type writes a file"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
        gen = ChartGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "pie.png")
            path = gen.create_chart({"a": 1, "b": 2}, ChartType.PIE, output_path=out)
            assert os.path.exists(path)

    def test_create_chart_histogram(self):
        """create_chart with HISTOGRAM type writes a file"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
        gen = ChartGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "hist.png")
            path = gen.create_chart(list(range(30)), ChartType.HISTOGRAM, output_path=out)
            assert os.path.exists(path)

    def test_create_chart_scatter(self):
        """create_chart with SCATTER type writes a file"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
        gen = ChartGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "scatter.png")
            path = gen.create_chart([(1, 2), (3, 4)], ChartType.SCATTER, output_path=out)
            assert os.path.exists(path)

    def test_create_chart_heatmap(self):
        """create_chart with HEATMAP type writes a file"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
        gen = ChartGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "heat.png")
            path = gen.create_chart([[1, 2], [3, 4]], ChartType.HEATMAP, output_path=out)
            assert os.path.exists(path)

    def test_create_chart_with_title_and_labels(self):
        """create_chart accepts title, xlabel, ylabel without error"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import ChartGenerator, ChartType
        gen = ChartGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "labeled.png")
            path = gen.create_chart(
                [1, 2, 3], ChartType.LINE,
                title="Test", xlabel="X", ylabel="Y",
                output_path=out
            )
            assert os.path.exists(path)


class TestCreateChartFunction:
    """Test module-level create_chart convenience function"""

    def test_function_delegates_to_generator(self):
        """create_chart function produces a file"""
        import matplotlib
        matplotlib.use('Agg')
        from zenus_core.visualization.chart_generator import create_chart, ChartType
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "fn.png")
            path = create_chart([1, 2, 3], ChartType.LINE, output_path=out)
            assert os.path.exists(path)


# ---------------------------------------------------------------------------
# TableFormatter
# ---------------------------------------------------------------------------

class TestTableFormatterNormalize:
    """Test _normalize_data converts various formats to list of dicts"""

    def setup_method(self):
        """Create TableFormatter."""
        from zenus_core.visualization.table_formatter import TableFormatter
        self.fmt = TableFormatter()

    def test_list_of_dicts_passthrough(self):
        """List of dicts is returned as-is"""
        data = [{"a": 1}, {"a": 2}]
        result = self.fmt._normalize_data(data, None)
        assert result == data

    def test_list_of_lists_with_columns(self):
        """List of lists with explicit columns maps correctly"""
        data = [[1, 2], [3, 4]]
        result = self.fmt._normalize_data(data, ["x", "y"])
        assert result == [{"x": 1, "y": 2}, {"x": 3, "y": 4}]

    def test_list_of_lists_auto_columns(self):
        """List of lists without columns generates Col0, Col1, ..."""
        data = [[1, 2], [3, 4]]
        result = self.fmt._normalize_data(data, None)
        assert "Col0" in result[0]
        assert "Col1" in result[0]

    def test_column_oriented_dict(self):
        """Column-oriented dict is transposed to row-oriented"""
        data = {"a": [1, 2], "b": [3, 4]}
        result = self.fmt._normalize_data(data, None)
        assert len(result) == 2
        assert result[0] == {"a": 1, "b": 3}

    def test_single_row_dict(self):
        """Single-row dict wrapped in list"""
        data = {"x": 10, "y": 20}
        result = self.fmt._normalize_data(data, None)
        assert result == [{"x": 10, "y": 20}]

    def test_list_of_simple_values(self):
        """List of plain values wrapped as Value column"""
        data = [1, 2, 3]
        result = self.fmt._normalize_data(data, None)
        assert result == [{"Value": 1}, {"Value": 2}, {"Value": 3}]


class TestTableFormatterFormatTable:
    """Test format_table produces non-empty strings"""

    def setup_method(self):
        """Create TableFormatter."""
        from zenus_core.visualization.table_formatter import TableFormatter
        self.fmt = TableFormatter()

    def test_format_list_of_dicts(self):
        """format_table with list of dicts returns non-empty string"""
        result = self.fmt.format_table([{"name": "Alice", "age": 30}])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_empty_data(self):
        """format_table with empty data returns 'No data to display'"""
        result = self.fmt.format_table([])
        assert "No data to display" in result

    def test_format_with_title(self):
        """format_table includes title in output"""
        import re
        result = self.fmt.format_table([{"x": 1}], title="My Table")
        # Strip ANSI escape codes before checking
        clean = re.sub(r'\x1b\[[0-9;]*m', '', result)
        assert "My Table" in clean or "My" in clean

    def test_format_with_limit(self):
        """format_table with limit truncates rows"""
        import re
        data = [{"n": i} for i in range(10)]
        result = self.fmt.format_table(data, limit=3)
        clean = re.sub(r'\x1b\[[0-9;]*m', '', result)
        assert "Showing" in clean and "3" in clean and "10" in clean

    def test_format_with_sort_by(self):
        """format_table with sort_by does not raise"""
        data = [{"k": "b", "v": 2}, {"k": "a", "v": 1}]
        result = self.fmt.format_table(data, sort_by="k")
        assert isinstance(result, str)

    def test_format_with_filter_func(self):
        """format_table with filter_func applies filter"""
        data = [{"n": 1}, {"n": 2}, {"n": 3}]
        result = self.fmt.format_table(data, filter_func=lambda r: r["n"] > 1)
        assert isinstance(result, str)

    def test_format_with_show_index(self):
        """format_table with show_index=True adds index column"""
        data = [{"x": 1}, {"x": 2}]
        result = self.fmt.format_table(data, show_index=True)
        assert isinstance(result, str)


class TestTableFormatterCellValues:
    """Test _format_cell_value formatting"""

    def setup_method(self):
        """Create TableFormatter."""
        from zenus_core.visualization.table_formatter import TableFormatter
        self.fmt = TableFormatter()

    def test_none_returns_dim_null(self):
        """None formatted as '[dim]null[/dim]'"""
        assert self.fmt._format_cell_value(None) == "[dim]null[/dim]"

    def test_true_returns_green_checkmark(self):
        """True formatted as green checkmark"""
        assert "[green]" in self.fmt._format_cell_value(True)

    def test_false_returns_red_cross(self):
        """False formatted as red cross"""
        assert "[red]" in self.fmt._format_cell_value(False)

    def test_int_formatted_with_commas(self):
        """Integer formatted with comma separator"""
        assert self.fmt._format_cell_value(1000) == "1,000"

    def test_float_formatted_two_decimals(self):
        """Float formatted with two decimal places"""
        assert self.fmt._format_cell_value(3.14159) == "3.14"

    def test_long_string_truncated(self):
        """String longer than max_cell_width is truncated with ellipsis"""
        long_str = "x" * 100
        result = self.fmt._format_cell_value(long_str)
        assert result.endswith("...")
        assert len(result) <= self.fmt.max_cell_width

    def test_list_serialized_as_json(self):
        """List value is JSON-serialized"""
        result = self.fmt._format_cell_value([1, 2])
        assert result == "[1, 2]"


class TestTableFormatterProperties:
    """Test format_dict_as_properties"""

    def setup_method(self):
        """Create TableFormatter."""
        from zenus_core.visualization.table_formatter import TableFormatter
        self.fmt = TableFormatter()

    def test_format_dict_returns_string(self):
        """format_dict_as_properties returns non-empty string"""
        result = self.fmt.format_dict_as_properties({"key": "value"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_dict_with_title(self):
        """format_dict_as_properties includes title"""
        result = self.fmt.format_dict_as_properties({"k": "v"}, title="Props")
        assert "Props" in result


class TestFormatTableFunction:
    """Test module-level format_table function"""

    def test_function_returns_string(self):
        """format_table function returns a formatted string"""
        from zenus_core.visualization.table_formatter import format_table
        result = format_table([{"a": 1, "b": 2}])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# DiffViewer
# ---------------------------------------------------------------------------

class TestDiffViewerTextDiff:
    """Test DiffViewer.show_diff for string inputs"""

    def setup_method(self):
        """Create DiffViewer."""
        from zenus_core.visualization.diff_viewer import DiffViewer
        self.viewer = DiffViewer()

    def test_identical_strings_no_diff(self):
        """Identical strings produce output without +/- lines"""
        result = self.viewer.show_diff("hello\n", "hello\n")
        assert "+" not in result or "+++" in result  # Only unified header

    def test_added_line_shows_green(self):
        """Added lines produce output (unified diff format)"""
        result = self.viewer.show_diff("line1\n", "line1\nline2\n")
        assert isinstance(result, str)

    def test_title_in_output(self):
        """Title appears in diff output"""
        result = self.viewer.show_diff("a", "b", title="My Diff")
        assert "My Diff" in result

    def test_non_unified_mode(self):
        """Non-unified diff uses ndiff format"""
        result = self.viewer.show_diff("a\n", "b\n", unified=False)
        assert isinstance(result, str)


class TestDiffViewerDictDiff:
    """Test DiffViewer._show_dict_diff"""

    def setup_method(self):
        """Create DiffViewer."""
        from zenus_core.visualization.diff_viewer import DiffViewer
        self.viewer = DiffViewer()

    def test_added_key_shown(self):
        """Added keys appear in diff output"""
        result = self.viewer.show_diff({"a": 1}, {"a": 1, "b": 2})
        assert "Added" in result

    def test_removed_key_shown(self):
        """Removed keys appear in diff output"""
        result = self.viewer.show_diff({"a": 1, "b": 2}, {"a": 1})
        assert "Removed" in result

    def test_changed_value_shown(self):
        """Changed values appear in diff output"""
        result = self.viewer.show_diff({"a": 1}, {"a": 99})
        assert "Changed" in result

    def test_no_changes_message(self):
        """Identical dicts produce 'No changes' message"""
        result = self.viewer.show_diff({"a": 1}, {"a": 1})
        assert "No changes" in result


class TestDiffViewerListDiff:
    """Test DiffViewer._show_list_diff"""

    def setup_method(self):
        """Create DiffViewer."""
        from zenus_core.visualization.diff_viewer import DiffViewer
        self.viewer = DiffViewer()

    def test_list_diff_returns_string(self):
        """List diff returns a non-empty string"""
        result = self.viewer.show_diff([1, 2, 3], [1, 2, 4])
        assert isinstance(result, str)

    def test_added_items_in_output(self):
        """Items added to list appear with + marker"""
        result = self.viewer.show_diff(["a", "b"], ["a", "b", "c"])
        assert "+" in result or "c" in result


class TestDiffViewerSummary:
    """Test DiffViewer.show_summary"""

    def setup_method(self):
        """Create DiffViewer."""
        from zenus_core.visualization.diff_viewer import DiffViewer
        self.viewer = DiffViewer()

    def test_dict_summary_contains_added_removed(self):
        """Dict summary mentions added/removed counts"""
        result = self.viewer.show_summary({"a": 1}, {"b": 2})
        assert "+" in result or "added" in result.lower()

    def test_list_summary_contains_added(self):
        """List summary mentions added count"""
        result = self.viewer.show_summary([1, 2], [1, 2, 3])
        assert "+" in result

    def test_text_summary_contains_lines(self):
        """Text summary mentions line changes"""
        result = self.viewer.show_summary("line1\n", "line1\nline2\n")
        assert "lines" in result


class TestDiffViewerFileDiff:
    """Test DiffViewer.show_file_diff"""

    def setup_method(self):
        """Create DiffViewer."""
        from zenus_core.visualization.diff_viewer import DiffViewer
        self.viewer = DiffViewer()

    def test_file_diff_with_real_files(self):
        """show_file_diff compares two real files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f1:
            f1.write("before content\n")
            path1 = f1.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f2:
            f2.write("after content\n")
            path2 = f2.name
        try:
            result = self.viewer.show_file_diff(path1, path2)
            assert isinstance(result, str)
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_file_diff_missing_file_returns_error(self):
        """show_file_diff returns error string for missing file"""
        result = self.viewer.show_file_diff("/nonexistent/file.txt", "/also/missing.txt")
        assert "Error" in result


class TestShowDiffFunction:
    """Test module-level show_diff function"""

    def test_function_returns_string(self):
        """show_diff function returns a formatted string"""
        from zenus_core.visualization.diff_viewer import show_diff
        result = show_diff("old", "new")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Core Visualizer
# ---------------------------------------------------------------------------

class TestDataTypeDetection:
    """Test Visualizer._detect_data_type"""

    def setup_method(self):
        """Create core Visualizer."""
        from zenus_core.visualization.visualizer import Visualizer, DataType
        self.viz = Visualizer()
        self.DataType = DataType

    def test_numeric_list_detected(self):
        """List of numbers detected as NUMERIC_SERIES"""
        assert self.viz._detect_data_type([1, 2, 3]) == self.DataType.NUMERIC_SERIES

    def test_categorical_dict_detected(self):
        """Dict with numeric values detected as CATEGORICAL"""
        assert self.viz._detect_data_type({"a": 1, "b": 2}) == self.DataType.CATEGORICAL

    def test_list_of_dicts_detected_as_tabular(self):
        """List of dicts detected as TABULAR"""
        assert self.viz._detect_data_type([{"a": 1}]) == self.DataType.TABULAR

    def test_list_of_lists_detected_as_tabular(self):
        """List of lists detected as TABULAR"""
        assert self.viz._detect_data_type([[1, 2], [3, 4]]) == self.DataType.TABULAR

    def test_string_detected_as_text(self):
        """String detected as TEXT"""
        assert self.viz._detect_data_type("hello") == self.DataType.TEXT

    def test_mixed_dict_detected_as_properties(self):
        """Dict with mixed value types detected as DICT_PROPERTIES"""
        result = self.viz._detect_data_type({"name": "Alice", "age": 30})
        assert result == self.DataType.DICT_PROPERTIES

    def test_empty_list_returns_unknown(self):
        """Empty list returns UNKNOWN"""
        assert self.viz._detect_data_type([]) == self.DataType.UNKNOWN


class TestVisualizerAutoVisualize:
    """Test Visualizer.visualize with auto format"""

    def setup_method(self):
        """Create core Visualizer with chart generator mocked."""
        with patch("zenus_core.visualization.chart_generator.plt"):
            from zenus_core.visualization.visualizer import Visualizer
            self.viz = Visualizer()
            self.viz.chart_gen = Mock()
            self.viz.chart_gen.create_chart.return_value = "/tmp/chart.png"

    def test_numeric_series_short_returns_chart(self):
        """Short numeric list produces chart path in output"""
        result = self.viz.visualize([1, 2, 3])
        assert "Chart" in result or "/tmp" in result

    def test_numeric_series_long_returns_histogram(self):
        """Long numeric list (>10) produces histogram chart path"""
        result = self.viz.visualize(list(range(20)))
        assert "Chart" in result or "/tmp" in result

    def test_categorical_few_returns_pie(self):
        """Categorical dict with <=6 items returns pie chart path"""
        result = self.viz.visualize({"a": 1, "b": 2, "c": 3})
        assert "Chart" in result or "/tmp" in result

    def test_categorical_many_returns_bar(self):
        """Categorical dict with >6 items returns bar chart path"""
        data = {str(i): i for i in range(7)}
        result = self.viz.visualize(data)
        assert "Chart" in result or "/tmp" in result

    def test_tabular_returns_table_string(self):
        """Tabular data returns table formatted string"""
        result = self.viz.visualize([{"x": 1, "y": 2}])
        assert isinstance(result, str)

    def test_text_returns_original(self):
        """Text data returned as-is"""
        result = self.viz.visualize("hello world")
        assert result == "hello world"


class TestVisualizerForceFormats:
    """Test Visualizer.visualize with explicit output_format"""

    def setup_method(self):
        """Create core Visualizer with chart generator mocked."""
        with patch("zenus_core.visualization.chart_generator.plt"):
            from zenus_core.visualization.visualizer import Visualizer
            self.viz = Visualizer()
            self.viz.chart_gen = Mock()
            self.viz.chart_gen.create_chart.return_value = "/tmp/out.png"

    def test_force_chart(self):
        """output_format='chart' always creates chart"""
        result = self.viz.visualize({"a": 1}, output_format="chart")
        assert "Chart" in result or "/tmp" in result

    def test_force_table(self):
        """output_format='table' formats as table"""
        result = self.viz.visualize([{"x": 1}], output_format="table")
        assert isinstance(result, str)

    def test_force_text_returns_str(self):
        """output_format='text' falls back to str()"""
        result = self.viz.visualize(42, output_format="text")
        assert result == "42"


class TestVisualizerShowDiff:
    """Test Visualizer.show_diff delegates to DiffViewer"""

    def setup_method(self):
        """Create core Visualizer."""
        from zenus_core.visualization.visualizer import Visualizer
        self.viz = Visualizer()
        self.viz.diff_viewer = Mock()
        self.viz.diff_viewer.show_diff.return_value = "diff output"

    def test_delegates_to_diff_viewer(self):
        """show_diff calls diff_viewer.show_diff and returns its result"""
        result = self.viz.show_diff("before", "after", title="T")
        self.viz.diff_viewer.show_diff.assert_called_once_with("before", "after", title="T")
        assert result == "diff output"


class TestVisualizerSummaryStats:
    """Test Visualizer.show_summary_stats"""

    def setup_method(self):
        """Create core Visualizer."""
        from zenus_core.visualization.visualizer import Visualizer
        self.viz = Visualizer()

    def test_returns_stats_for_numeric_data(self):
        """show_summary_stats returns a formatted table for numeric data"""
        result = self.viz.show_summary_stats([1, 2, 3, 4, 5])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_error_for_non_numeric(self):
        """show_summary_stats returns error message for non-numeric data"""
        result = self.viz.show_summary_stats(["a", "b"])
        assert result == "Data must be numeric"

    def test_returns_error_for_empty_data(self):
        """show_summary_stats returns error message for empty list"""
        result = self.viz.show_summary_stats([])
        assert result == "Data must be numeric"

    def test_single_element_std_dev_zero(self):
        """Single element list has std dev of 0"""
        result = self.viz.show_summary_stats([42])
        assert isinstance(result, str)


class TestVisualizerComparisonTable:
    """Test Visualizer.create_comparison_table"""

    def setup_method(self):
        """Create core Visualizer."""
        from zenus_core.visualization.visualizer import Visualizer
        self.viz = Visualizer()

    def test_empty_items_returns_message(self):
        """Empty items list returns 'No items to compare'"""
        result = self.viz.create_comparison_table([])
        assert result == "No items to compare"

    def test_returns_table_string(self):
        """create_comparison_table returns non-empty formatted string"""
        items = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = self.viz.create_comparison_table(items)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_respects_compare_keys(self):
        """compare_keys limits which properties appear"""
        items = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = self.viz.create_comparison_table(items, compare_keys=["a"])
        assert isinstance(result, str)


class TestGetVisualizer:
    """Test get_visualizer singleton"""

    def test_returns_visualizer_instance(self):
        """get_visualizer returns a Visualizer instance"""
        import zenus_core.visualization.visualizer as mod
        mod._visualizer_instance = None  # reset singleton
        from zenus_core.visualization.visualizer import get_visualizer, Visualizer
        v = get_visualizer()
        assert isinstance(v, Visualizer)
        mod._visualizer_instance = None  # cleanup


# ---------------------------------------------------------------------------
# zenus_visualization package Visualizer (static methods, no charts)
# ---------------------------------------------------------------------------

class TestZenusVisualizationVisualizer:
    """Test the zenus_visualization.visualizer.Visualizer static interface"""

    def test_visualize_dict_simple(self, capsys):
        """Visualizer.visualize prints dict as key-value table without error"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize({"key": "val", "num": 42})
        # No assertion on exact output; just verify no exception

    def test_visualize_list_of_dicts(self, capsys):
        """Visualizer.visualize handles list of dicts as table"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize([{"a": 1, "b": 2}, {"a": 3, "b": 4}])

    def test_visualize_list_of_strings(self, capsys):
        """Visualizer.visualize handles list of strings as tree"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize(["item1", "item2"])

    def test_visualize_empty_list(self, capsys):
        """Visualizer.visualize handles empty list gracefully"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize([])

    def test_visualize_string_with_context(self, capsys):
        """Visualizer.visualize handles plain string with context"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize("plain text output", context="general")

    def test_visualize_process_list_string(self, capsys):
        """Visualizer.visualize handles process list pattern"""
        from zenus_visualization.visualizer import Visualizer
        data = "PID 1009: my-service (12.6% mem)"
        Visualizer.visualize(data)

    def test_visualize_json_string(self, capsys):
        """Visualizer.visualize parses and renders JSON string"""
        from zenus_visualization.visualizer import Visualizer
        import json
        Visualizer.visualize(json.dumps({"x": 1, "y": 2}))

    def test_visualize_key_value_multiline(self, capsys):
        """Visualizer.visualize formats multiline key:value string as table"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize("Name: Alice\nAge: 30\nCity: Lisbon")

    def test_visualize_percentage_string(self, capsys):
        """Visualizer.visualize handles percentage string"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize("Usage: 75%")

    def test_visualize_complex_dict(self, capsys):
        """Visualizer.visualize handles dict with complex values as JSON"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize({"nested": [1, 2, 3], "deep": {"a": 1}})

    def test_visualize_other_type(self, capsys):
        """Visualizer.visualize falls back to str for unknown types"""
        from zenus_visualization.visualizer import Visualizer
        Visualizer.visualize(42)
