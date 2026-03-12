# Zenus Visualization

Automatic data visualization system for Zenus.

## Features

- **Auto-detection**: Automatically detects data types and chooses the best visualization
- **Rich tables**: Beautiful tables for structured data
- **Progress bars**: Visual indicators for percentages and resource usage
- **File trees**: Hierarchical file and directory displays
- **Syntax highlighting**: Code and JSON with color coding

## Usage

```python
from zenus_visualization import Visualizer

# Automatically visualize any data
Visualizer.visualize(data)

# With context hint
Visualizer.visualize(data, context="process_list")
```

## Supported Data Types

- Process lists
- Disk usage stats
- System resource summaries
- File listings
- JSON/structured data
- Key-value pairs
- Plain text (fallback)
