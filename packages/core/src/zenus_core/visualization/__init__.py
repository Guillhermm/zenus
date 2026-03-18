"""
Visualization module for Zenus

Auto-generates charts, tables, and rich output from data.
"""

from zenus_core.visualization.visualizer import (
    Visualizer,
    get_visualizer
)

from zenus_core.visualization.chart_generator import (
    ChartGenerator,
    ChartType,
    create_chart
)

from zenus_core.visualization.table_formatter import (
    TableFormatter,
    TableStyle,
    format_table
)

from zenus_core.visualization.diff_viewer import (
    DiffViewer,
    show_diff
)

__all__ = [
    'Visualizer',
    'ChartType',
    'TableStyle',
    'get_visualizer',
    'ChartGenerator',
    'create_chart',
    'TableFormatter',
    'format_table',
    'DiffViewer',
    'show_diff'
]
