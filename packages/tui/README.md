# Zenus TUI

Text-based User Interface for Zenus using Textual framework.

## Features

- **Real-time Dashboard** - Live execution monitoring
- **Command History** - Browse past executions
- **Pattern Suggestions** - Visual pattern detection
- **Memory Explorer** - View sessions and patterns
- **Explainability** - Understand Zenus decisions
- **Keyboard Navigation** - F1-F4 to switch views

## Installation

```bash
cd packages/tui
poetry install
```

## Usage

```bash
zenus-tui
```

Or from Python:

```python
from zenus_tui.dashboard import main
main()
```

## Keyboard Shortcuts

- **F1** - Execution view
- **F2** - History view
- **F3** - Memory view
- **F4** - Explain view
- **Q** - Quit
- **Ctrl+C** - Quit
