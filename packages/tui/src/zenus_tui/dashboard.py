"""
Zenus OS Dashboard

Main TUI application with multiple views and real-time updates.
Fully wired to Zenus orchestrator and memory systems.
Polished with advanced features.
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Button, Input,
    DataTable, TabbedContent, TabPane, Log,
    Label, ProgressBar, RichLog, LoadingIndicator, Select,
)
from textual.binding import Binding
from textual.worker import Worker, WorkerState
from textual.message import Message
from textual.screen import ModalScreen
from rich.text import Text
from rich.table import Table as RichTable
from rich.panel import Panel
from rich.tree import Tree
from datetime import datetime
import asyncio
from typing import Optional, List
from collections import deque

# Zenus imports
from zenus_core.orchestrator import Orchestrator
from zenus_core.memory.action_tracker import get_action_tracker
from zenus_core.brain.pattern_detector import PatternDetector
from zenus_core.memory.world_model import WorldModel


class CommandCompleted(Message):
    """Posted by the async worker when a command finishes executing."""

    def __init__(self, command: str, result: str, duration: float, success: bool) -> None:
        super().__init__()
        self.command = command
        self.result = result
        self.duration = duration
        self.success = success


PROVIDER_MODELS = {
    "anthropic": [
        ("claude-sonnet-4-6", "Sonnet 4.6 — balanced (recommended)"),
        ("claude-opus-4-6",   "Opus 4.6 — most capable"),
        ("claude-haiku-4-5",  "Haiku 4.5 — fastest"),
    ],
    "openai": [
        ("gpt-4o",      "GPT-4o — flagship multimodal"),
        ("gpt-4o-mini", "GPT-4o mini — fast & cheap"),
        ("gpt-4.1",     "GPT-4.1 — long context"),
        ("o3",          "o3 — frontier reasoning"),
        ("o3-mini",     "o3-mini — fast reasoning"),
        ("o4-mini",     "o4-mini — cost-efficient reasoning"),
    ],
    "deepseek": [
        ("deepseek-chat",     "DeepSeek-V3 — general purpose"),
        ("deepseek-reasoner", "DeepSeek-R1 — chain-of-thought"),
    ],
    "ollama": [
        ("llama3.1:8b",      "Llama 3.1 8B — popular & capable"),
        ("llama3.2:3b",      "Llama 3.2 3B — fast, low memory"),
        ("qwen2.5:7b",       "Qwen 2.5 7B — excellent reasoning"),
        ("qwen3:8b",         "Qwen 3 8B — latest generation"),
        ("deepseek-r1:7b",   "DeepSeek-R1 7B — local reasoning"),
        ("mistral:7b",       "Mistral 7B — fast & capable"),
        ("phi4:14b",         "Phi-4 14B — Microsoft, efficient"),
        ("gemma3:4b",        "Gemma 3 4B — Google, lightweight"),
    ],
}


class ModelPickerScreen(ModalScreen):
    """Modal screen for selecting provider and model."""

    CSS = """
    ModelPickerScreen {
        align: center middle;
    }
    #model-picker-container {
        width: 60;
        height: auto;
        max-height: 30;
        background: $panel;
        border: solid $primary;
        padding: 1 2;
    }
    #provider-select { margin-bottom: 1; }
    #model-select    { margin-bottom: 1; }
    #picker-buttons  { height: 3; }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel"),
    ]

    def __init__(self, current_provider: str = "anthropic", current_model: str = ""):
        super().__init__()
        self._current_provider = current_provider
        self._current_model = current_model

    def compose(self) -> ComposeResult:
        provider_options = [(p, p) for p in PROVIDER_MODELS]
        with Container(id="model-picker-container"):
            yield Label("[bold]Select LLM Provider & Model[/bold]")
            yield Select(
                options=provider_options,
                value=self._current_provider,
                id="provider-select",
            )
            yield Select(
                options=self._model_options(self._current_provider),
                value=self._current_model or PROVIDER_MODELS[self._current_provider][0][0],
                id="model-select",
            )
            with Horizontal(id="picker-buttons"):
                yield Button("Apply", variant="primary", id="apply-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def _model_options(self, provider: str):
        return [(f"{mid}  —  {desc}", mid) for mid, desc in PROVIDER_MODELS.get(provider, [])]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-select":
            model_select = self.query_one("#model-select", Select)
            new_opts = self._model_options(str(event.value))
            model_select.set_options(new_opts)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-btn":
            provider = str(self.query_one("#provider-select", Select).value)
            model = str(self.query_one("#model-select", Select).value)
            self.dismiss((provider, model))
        else:
            self.dismiss(None)


class StatusBar(Static):
    """Status bar showing system state"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session_start = datetime.now()
        self.command_count = 0
        self.last_result = "Ready"
    
    def update_status(self, command_count: int = None, last_result: str = None):
        """Update status information"""
        if command_count is not None:
            self.command_count = command_count
        if last_result is not None:
            self.last_result = last_result
        
        # Calculate session duration
        duration = datetime.now() - self.session_start
        minutes = int(duration.total_seconds() / 60)
        
        # Build status text with emoji indicators
        status_text = Text()
        status_text.append("Status: ", style="bold")
        
        # Smart status styling
        if "Executing" in self.last_result:
            status_text.append(self.last_result, style="bold yellow")
        elif "✓" in self.last_result or "Success" in self.last_result:
            status_text.append(self.last_result, style="bold green")
        elif "✗" in self.last_result or "Failed" in self.last_result:
            status_text.append(self.last_result, style="bold red")
        else:
            status_text.append(self.last_result, style="cyan")
        
        status_text.append(" | ", style="dim")
        status_text.append(f"Commands: {self.command_count}", style="cyan")
        status_text.append(" | ", style="dim")
        status_text.append(f"Session: {minutes}m", style="dim")
        
        self.update(status_text)


class CommandInput(Container):
    """Command input area with action buttons and history"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.command_history: deque = deque(maxlen=100)
        self.history_index = -1
    
    def compose(self) -> ComposeResult:
        with Horizontal(id="command-input-container"):
            yield Input(placeholder="Enter command... (↑↓ for history)", id="command-input")
            yield Button("Execute", variant="primary", id="execute-btn")
            yield Button("Dry Run", variant="default", id="dry-run-btn")
            yield Button("Iterative", variant="default", id="iterative-btn")
            yield Button("Clear Log", variant="warning", id="clear-log-btn")
    
    def add_to_history(self, command: str):
        """Add command to history"""
        if command and (not self.command_history or self.command_history[-1] != command):
            self.command_history.append(command)
        self.history_index = -1
    
    def get_previous_command(self) -> Optional[str]:
        """Get previous command from history"""
        if not self.command_history:
            return None
        
        if self.history_index == -1:
            self.history_index = len(self.command_history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        
        return self.command_history[self.history_index] if self.history_index >= 0 else None
    
    def get_next_command(self) -> Optional[str]:
        """Get next command from history"""
        if not self.command_history or self.history_index == -1:
            return ""
        
        self.history_index += 1
        
        if self.history_index >= len(self.command_history):
            self.history_index = -1
            return ""
        
        return self.command_history[self.history_index]


class ExecutionLog(Vertical):
    """Live execution log viewer with real-time updates.

    Uses a fixed-height RichLog (height: 1fr) with auto_scroll so Textual's
    built-in scroll mechanism handles keeping the latest output visible.
    """

    def compose(self) -> ComposeResult:
        # markup=False so timestamps like [12:34:56] are never parsed as Rich tags
        # auto_scroll=True (default) scrolls to bottom on every write()
        yield RichLog(id="execution-log", highlight=False, markup=False, auto_scroll=True)

    def on_mount(self):
        log = self.query_one("#execution-log", RichLog)
        log.write("✓ Execution log ready. Enter a command below to get started.")

    def show_spinner(self):
        pass

    def hide_spinner(self):
        pass

    def add_execution(self, command: str, result: str, duration: float, success: bool):
        """Append one execution entry to the log"""
        log = self.query_one("#execution-log", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_icon = "✓" if success else "✗"

        log.write(f"[{timestamp}] {command}  {status_icon}  {duration:.1f}s")

        if result:
            for line in result.split("\n")[:10]:
                if line.strip():
                    log.write(f"  → {line[:200]}")
        else:
            log.write("  → (completed, no output)" if success else "  → (failed, no output)")

        log.write("")  # blank separator

    def add_progress(self, message: str):
        log = self.query_one("#execution-log", RichLog)
        log.write(f"⏳ {message}")

    def clear_log(self):
        log = self.query_one("#execution-log", RichLog)
        log.clear()
        log.write("✓ Log cleared.")


class PatternSuggestion(Container):
    """Pattern suggestion panel"""
    
    def compose(self) -> ComposeResult:
        yield Label("💡 Pattern Detected", id="pattern-title")
        yield Static("", id="pattern-content")
    
    def show_pattern(self, description: str, suggestion: str):
        """Display a detected pattern"""
        content = self.query_one("#pattern-content", Static)
        
        text = Text()
        text.append(description, style="yellow")
        text.append("\n\n💡 Suggestion: ", style="bold cyan")
        text.append(suggestion, style="cyan")
        
        content.update(text)
        self.display = True
    
    def hide(self):
        """Hide pattern panel"""
        self.display = False


class HistoryView(ScrollableContainer):
    """Command history viewer with search"""
    
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search history...", id="history-search")
        yield DataTable(id="history-table")
    
    def on_mount(self):
        """Initialize history table"""
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Time", "Command", "Status", "Duration")
        table.cursor_type = "row"
        self.refresh_history()
    
    def on_input_changed(self, event: Input.Changed):
        """Filter history on search"""
        if event.input.id == "history-search":
            self.refresh_history(search=event.value)
    
    def refresh_history(self, search: str = ""):
        """Load history from action tracker"""
        table = self.query_one("#history-table", DataTable)
        table.clear()

        try:
            tracker = get_action_tracker()
            transactions = tracker.get_recent_transactions(limit=100)

            for txn in transactions:  # already DESC from DB
                # Timestamp
                raw_ts = txn.get("start_time", "")
                try:
                    time_str = datetime.fromisoformat(raw_ts).strftime("%m/%d %H:%M")
                except Exception:
                    time_str = raw_ts[:16] if raw_ts else "Unknown"

                # Command — tracker stores the original user input
                command = txn.get("user_input") or txn.get("intent_goal") or "Unknown"

                # Filter
                if search and search.lower() not in command.lower():
                    continue

                # Status
                status_val = txn.get("status", "")
                status = "✓" if status_val == "completed" else "✗"

                # Duration from start/end
                end_ts = txn.get("end_time", "")
                try:
                    dur = (
                        datetime.fromisoformat(end_ts) - datetime.fromisoformat(raw_ts)
                    ).total_seconds()
                    duration_str = f"{dur:.1f}s"
                except Exception:
                    duration_str = "N/A"

                table.add_row(time_str, command[:60], status, duration_str)
        except Exception as e:
            table.add_row("Error", f"Failed to load history: {e}", "", "")


class MemoryView(ScrollableContainer):
    """Memory and pattern viewer"""
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="memory-log", highlight=True, markup=True)
    
    def on_mount(self):
        """Load memory and patterns"""
        self.refresh_memory()
    
    def refresh_memory(self):
        """Display patterns and world model state"""
        log = self.query_one("#memory-log", RichLog)
        log.clear()
        
        log.write("[bold cyan]🧠 Detected Patterns[/bold cyan]\n")
        
        try:
            # Get patterns
            tracker = get_action_tracker()
            history = tracker.get_recent_transactions(limit=100)
            
            detector = PatternDetector()
            patterns = detector.detect_patterns(history, lookback_days=30)
            
            if patterns:
                for i, pattern in enumerate(patterns[:10], 1):  # Top 10
                    log.write(f"\n[yellow]{i}. {pattern.pattern_type.title()}[/yellow]")
                    log.write(f"   {pattern.description}")
                    log.write(f"   [dim]Confidence: {pattern.confidence:.0%} | Occurrences: {pattern.occurrences}[/dim]")
                    
                    if pattern.suggested_cron:
                        log.write(f"   [green]💡 Suggested cron: {pattern.suggested_cron}[/green]")
            else:
                log.write("[dim]No patterns detected yet. Keep using Zenus![/dim]")
            
            # World model state
            log.write("\n\n[bold cyan]🌍 World Model[/bold cyan]\n")
            
            try:
                world_model = WorldModel()
                
                # Show frequent paths
                paths = world_model.get_frequent_paths(limit=5)
                if paths:
                    log.write("\n[yellow]Frequent Paths:[/yellow]")
                    for path in paths:
                        log.write(f"  • {path}")
                
                # Show patterns
                patterns = world_model.get_patterns()
                if patterns:
                    log.write("\n[yellow]Learned Patterns:[/yellow]")
                    for pattern in patterns[:5]:  # Top 5
                        log.write(f"  • {pattern.get('description', 'Unknown')}")
                
                # Show summary
                summary = world_model.get_summary()
                if summary and not paths and not patterns:
                    log.write(f"\n{summary}")
                
                if not paths and not patterns and not summary:
                    log.write("[dim]No world model data yet[/dim]")
                    
            except Exception as e:
                log.write(f"[dim]World model unavailable: {e}[/dim]")
                
        except Exception as e:
            log.write(f"[red]Error loading memory: {e}[/red]")


class ExplainView(ScrollableContainer):
    """Explainability dashboard with detailed step breakdown"""
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="explain-log", highlight=True, markup=True)
    
    def show_explanation(self, user_input: str, result: str, steps: Optional[List] = None):
        """Display detailed explanation for last command"""
        log = self.query_one("#explain-log", RichLog)
        log.clear()
        
        log.write("[bold cyan]📊 Command Explanation[/bold cyan]\n")
        log.write(f"[yellow]Input:[/yellow] {user_input}\n")
        
        # Show steps if available
        if steps:
            log.write("\n[bold cyan]📝 Execution Steps:[/bold cyan]\n")
            for i, step in enumerate(steps, 1):
                log.write(f"\n[cyan]{i}. {step.get('tool', 'Unknown')}.{step.get('action', 'Unknown')}[/cyan]")
                if step.get('reasoning'):
                    log.write(f"   [dim]{step['reasoning']}[/dim]")
                if step.get('confidence'):
                    log.write(f"   [dim]Confidence: {step['confidence']:.0%}[/dim]")
        
        # Show result
        log.write(f"\n[yellow]Result:[/yellow]")
        all_lines = result.split('\n')
        result_lines = all_lines[:10]  # First 10 lines
        for line in result_lines:
            if line.strip():
                log.write(f"  {line}")
        
        if len(all_lines) > 10:
            remaining = len(all_lines) - 10
            log.write(f"\n  [dim]... ({remaining} more lines)[/dim]")


class RollbackPanel(Container):
    """Rollback control panel"""
    
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Button("⎌ Rollback Last", variant="error", id="rollback-btn")
            yield Static("", id="rollback-status")
    
    def show_rollback_status(self, message: str, success: bool):
        """Show rollback result"""
        status = self.query_one("#rollback-status", Static)
        style = "green" if success else "red"
        status.update(f"[{style}]{message}[/{style}]")


class SystemView(ScrollableContainer):
    """System overview tab — shows live info, refreshes on activation."""

    def compose(self) -> ComposeResult:
        yield RichLog(id="system-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        self.refresh_info()

    def refresh_info(self) -> None:
        log = self.query_one("#system-log", RichLog)
        log.clear()
        log.write("[bold cyan]🔄 System Overview[/bold cyan]\n")
        try:
            import platform, os
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.write(f"[yellow]Refreshed at:[/yellow] {now}")
            log.write(f"[yellow]Hostname:[/yellow] {platform.node()}")
            log.write(f"[yellow]OS:[/yellow] {platform.system()} {platform.release()}")
            log.write(f"[yellow]Python:[/yellow] {platform.python_version()}")
            log.write(f"[yellow]CWD:[/yellow] {os.getcwd()}")
        except Exception as e:
            log.write(f"[red]Error: {e}[/red]")


class RollbackView(ScrollableContainer):
    """Rollback tab — shows recent actions and allows rolling back."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="rollback-buttons"):
            yield Button("⎌ Rollback Last Action", variant="error", id="rollback-last-btn")
            yield Static("", id="rollback-status")
        yield RichLog(id="rollback-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        self.refresh_history()

    def refresh_history(self) -> None:
        log = self.query_one("#rollback-log", RichLog)
        log.clear()
        log.write("[bold cyan]⎌ Recent Actions (rollback candidates)[/bold cyan]\n")
        try:
            tracker = get_action_tracker()
            transactions = tracker.get_recent_transactions(limit=20)
            if not transactions:
                log.write("[dim]No recent actions recorded.[/dim]")
                return
            for txn in transactions:
                raw_ts = txn.get("start_time", "")
                try:
                    time_str = datetime.fromisoformat(raw_ts).strftime("%m/%d %H:%M")
                except Exception:
                    time_str = raw_ts[:16] if raw_ts else "?"
                command = txn.get("user_input") or txn.get("intent_goal") or "Unknown"
                status_val = txn.get("status", "")
                icon = "✓" if status_val == "completed" else "✗"
                log.write(f"  [{time_str}] {icon} {command[:80]}")
        except Exception as e:
            log.write(f"[red]Error loading history: {e}[/red]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rollback-last-btn":
            status = self.query_one("#rollback-status", Static)
            status.update("[yellow]Rollback is not yet implemented.[/yellow]")


class ModelTabView(Container):
    """Model tab — inline provider/model selection."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]LLM Provider & Model[/bold]", id="model-tab-title")
        provider_options = [(p, p) for p in PROVIDER_MODELS]
        yield Select(options=provider_options, id="tab-provider-select")
        yield Select(
            options=self._model_options("anthropic"),
            id="tab-model-select",
        )
        yield Button("Apply", variant="primary", id="tab-apply-btn")
        yield Static("", id="tab-model-status")

    def _model_options(self, provider: str):
        return [(f"{mid}  —  {desc}", mid) for mid, desc in PROVIDER_MODELS.get(provider, [])]

    def on_mount(self) -> None:
        """Pre-select current provider/model from config if available."""
        try:
            from zenus_core.config.loader import get_config
            cfg = get_config()
            provider = cfg.llm.provider
            model = cfg.llm.model or PROVIDER_MODELS[provider][0][0]
            self.query_one("#tab-provider-select", Select).value = provider
            opts = self._model_options(provider)
            self.query_one("#tab-model-select", Select).set_options(opts)
            self.query_one("#tab-model-select", Select).value = model
        except Exception:
            pass

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "tab-provider-select":
            provider = str(event.value)
            opts = self._model_options(provider)
            self.query_one("#tab-model-select", Select).set_options(opts)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "tab-apply-btn":
            return
        provider = str(self.query_one("#tab-provider-select", Select).value)
        model = str(self.query_one("#tab-model-select", Select).value)
        status = self.query_one("#tab-model-status", Static)

        def save():
            try:
                from zenus_core.shell.commands import _update_config_provider
                _update_config_provider(provider, model)
                self.call_from_thread(
                    status.update,
                    f"[green]✓ Saved: {provider} / {model}[/green]",
                )
                # Propagate to the app-level active override
                app = self.app
                app.active_provider = provider
                app.active_model = model
                app.sub_title = f"{provider} / {model}  [override]"
            except Exception as e:
                self.call_from_thread(
                    status.update,
                    f"[red]Save failed: {e}[/red]",
                )

        import asyncio
        self.run_worker(asyncio.get_event_loop().run_in_executor(None, save))


class ZenusDashboard(App):
    """Zenus OS TUI Dashboard - Polished Edition"""
    
    CSS = """
    #status-bar {
        dock: top;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    
    #command-input-container {
        dock: bottom;
        height: 3;
        background: $panel;
        padding: 0 1;
    }
    
    #command-input {
        width: 50%;
    }
    
    #execution-log-container {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    #execution-log {
        height: 1fr;
    }

    #pattern-suggestion {
        height: auto;
        max-height: 8;
        border: solid yellow;
        background: $panel;
        padding: 1;
    }
    
    #history-search {
        margin: 0 0 1 0;
    }
    
    #history-table {
        height: 1fr;
    }
    
    #memory-log {
        height: 100%;
    }
    
    #explain-log {
        height: 100%;
    }
    
    Button {
        margin: 0 1;
    }
    
    LoadingIndicator {
        height: 1;
        width: auto;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("q", "quit", "Quit", show=False),
        Binding("f1", "tab('execution')", "Execution", show=True),
        Binding("f2", "tab('history')", "History", show=True),
        Binding("f3", "tab('memory')", "Memory", show=True),
        Binding("f4", "tab('explain')", "Explain", show=True),
        Binding("f5", "tab('refresh')", "Refresh", show=True),
        Binding("f6", "tab('rollback')", "Rollback", show=True),
        Binding("f7", "tab('model')", "Model", show=True),
        Binding("ctrl+r", "tab('rollback')", "Rollback", show=False),
        Binding("ctrl+m", "tab('model')", "Model", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.title = "Zenus OS Dashboard"
        self.sub_title = "AI-Powered System Management"

        # Orchestrator is initialized asynchronously in on_mount to avoid
        # blocking the UI before the first frame renders
        self.orchestrator = None

        # Active provider/model override (None = use config.yaml defaults)
        self.active_provider: Optional[str] = None
        self.active_model: Optional[str] = None

        self.command_count = 0
        self.last_command = None
        self.last_result = None
        self.last_steps = None
    
    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield Header()
        
        # Status bar
        yield StatusBar(id="status-bar")
        
        # Main content area with tabs
        with TabbedContent(id="main-tabs"):
            with TabPane("Execution", id="execution-tab"):
                yield ExecutionLog(id="execution-log-container")
                yield PatternSuggestion(id="pattern-suggestion")

            with TabPane("History", id="history-tab"):
                yield HistoryView(id="history-view")

            with TabPane("Memory", id="memory-tab"):
                yield MemoryView(id="memory-view")

            with TabPane("Explain", id="explain-tab"):
                yield ExplainView(id="explain-view")

            with TabPane("Refresh", id="refresh-tab"):
                yield SystemView(id="system-view")

            with TabPane("Rollback", id="rollback-tab"):
                yield RollbackView(id="rollback-view")

            with TabPane("Model", id="model-tab"):
                yield ModelTabView(id="model-tab-view")
        
        # Command input area
        yield CommandInput(id="command-input-area")
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize after mounting"""
        # Hide pattern suggestion initially
        pattern = self.query_one("#pattern-suggestion", PatternSuggestion)
        pattern.display = False

        # Show initializing state — TUI is already responsive at this point
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.update_status(0, "Initializing... ⏳")

        # Focus input so user can start typing immediately
        input_widget = self.query_one("#command-input", Input)
        input_widget.focus()

        # Load the orchestrator in a background thread (imports LLM, config, etc.)
        self.run_worker(self._init_orchestrator(), name="init-orchestrator")

    async def _init_orchestrator(self) -> None:
        """Create the Orchestrator in a thread pool so the UI stays responsive"""
        loop = asyncio.get_event_loop()
        status_bar = self.query_one("#status-bar", StatusBar)
        try:
            self.orchestrator = await loop.run_in_executor(
                None,
                lambda: Orchestrator(
                    adaptive=True,
                    use_memory=True,
                    use_sandbox=True,
                    show_progress=False,
                    enable_parallel=True,
                ),
            )
            # Show active provider/model in sub-title
            try:
                model = self.orchestrator.llm.model
                provider = self.orchestrator.router.primary_provider
                self.sub_title = f"{provider} / {model}"
            except Exception:
                try:
                    model = self.orchestrator.llm.model
                    self.sub_title = f"Model: {model}"
                except Exception:
                    pass
            status_bar.update_status(0, "Ready ✓")
        except Exception as e:
            status_bar.update_status(0, f"Init error: {e}")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        
        if button_id == "execute-btn":
            self.execute_command(dry_run=False, iterative=False)
        elif button_id == "dry-run-btn":
            self.execute_command(dry_run=True, iterative=False)
        elif button_id == "iterative-btn":
            self.execute_command(dry_run=False, iterative=True)
        elif button_id == "clear-log-btn":
            self.action_clear_log()
        elif button_id == "rollback-btn":
            self.action_rollback()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input field"""
        if event.input.id == "command-input":
            self.execute_command(dry_run=False, iterative=False)
    
    def on_key(self, event) -> None:
        """Handle special keys"""
        input_widget = self.query_one("#command-input", Input)
        command_input_container = self.query_one("#command-input-area", CommandInput)
        
        # Only handle arrow keys when input is focused
        if self.focused == input_widget:
            if event.key == "up":
                prev_cmd = command_input_container.get_previous_command()
                if prev_cmd:
                    input_widget.value = prev_cmd
                    input_widget.cursor_position = len(prev_cmd)
                event.prevent_default()
            elif event.key == "down":
                next_cmd = command_input_container.get_next_command()
                if next_cmd is not None:
                    input_widget.value = next_cmd
                    input_widget.cursor_position = len(next_cmd)
                event.prevent_default()
    
    def execute_command(self, dry_run: bool = False, iterative: bool = False):
        """Execute command in background worker"""
        if self.orchestrator is None:
            self.notify("Still initializing, please wait...", severity="warning")
            return

        # Get command from input
        input_widget = self.query_one("#command-input", Input)
        command = input_widget.value.strip()

        if not command:
            return

        # Add to history
        command_input_container = self.query_one("#command-input-area", CommandInput)
        command_input_container.add_to_history(command)

        # Clear input
        input_widget.value = ""

        # Update status and show spinner
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.update_status(last_result="Executing... ⏳")

        exec_log = self.query_one("#execution-log-container", ExecutionLog)
        exec_log.show_spinner()

        # Store for explain view
        self.last_command = command

        # Run in background worker
        self.run_worker(
            self._execute_async(command, dry_run, iterative),
            name=f"execute-{datetime.now().timestamp()}"
        )

    async def _execute_async(self, command: str, dry_run: bool, iterative: bool):
        """Execute command asynchronously"""
        start_time = datetime.now()
        success = False
        result = ""

        # Session-level provider override set via Ctrl+M
        session_provider = self.active_provider

        def run_command(cmd, is_dry, is_iter):
            """Run orchestrator synchronously (called from thread pool)"""
            if is_iter:
                return self.orchestrator.execute_iterative(
                    cmd,
                    max_iterations=12,
                    dry_run=is_dry,
                    force_provider=session_provider,
                )
            else:
                return self.orchestrator.execute_command(
                    cmd,
                    dry_run=is_dry,
                    force_oneshot=True,
                    force_provider=session_provider,
                )

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                run_command,
                command,
                dry_run,
                iterative,
            )
            if result is None:
                result = ""
            
            success = True
            self.last_result = result
            
        except Exception as e:
            result = f"Error: {str(e)}"
            success = False
            self.last_result = result
        
        finally:
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Post a message so Textual delivers the UI update on the event loop
            # in a safe, well-defined render cycle (avoids worker mutation issues).
            self.post_message(CommandCompleted(command, result, duration, success))

    def on_command_completed(self, event: CommandCompleted) -> None:
        """Handle CommandCompleted message on the main event loop."""
        self._update_after_execution(event.command, event.result, event.duration, event.success)

    def _update_after_execution(self, command: str, result: str, duration: float, success: bool):
        """Update UI after command execution (on main event loop)."""
        # Increment command count
        self.command_count += 1
        
        # Update status bar
        status_bar = self.query_one("#status-bar", StatusBar)
        status_text = "Success ✓" if success else "Failed ✗"
        status_bar.update_status(self.command_count, status_text)
        
        # Hide spinner and add to execution log
        exec_log = self.query_one("#execution-log-container", ExecutionLog)
        exec_log.hide_spinner()
        exec_log.add_execution(command, result, duration, success)
        
        # Check for patterns (every 10 commands)
        if self.command_count % 10 == 0:
            self._check_patterns()
        
        # Refresh history and memory tabs
        try:
            history_view = self.query_one("#history-view", HistoryView)
            history_view.refresh_history()
        except:
            pass
        
        try:
            memory_view = self.query_one("#memory-view", MemoryView)
            memory_view.refresh_memory()
        except:
            pass
        
        # Update explain view
        try:
            explain_view = self.query_one("#explain-view", ExplainView)
            explain_view.show_explanation(command, result, self.last_steps)
        except:
            pass
    
    def _check_patterns(self):
        """Check for patterns and show suggestions"""
        try:
            tracker = get_action_tracker()
            history = tracker.get_recent_transactions(limit=100)
            
            detector = PatternDetector()
            patterns = detector.detect_patterns(history, lookback_days=30)
            
            # Show top pattern if found
            if patterns:
                pattern = patterns[0]  # Highest confidence
                
                suggestion = pattern.description
                if pattern.suggested_cron:
                    suggestion += f"\n\nTry: zenus schedule '{pattern.suggested_cron}' ..."
                
                pattern_widget = self.query_one("#pattern-suggestion", PatternSuggestion)
                pattern_widget.show_pattern(pattern.description, suggestion)
        except Exception as e:
            pass  # Silent fail for pattern detection
    
    def action_tab(self, tab_name: str) -> None:
        """Switch to a specific tab"""
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = f"{tab_name}-tab"
    
    def action_refresh(self) -> None:
        """Refresh current tab data"""
        tabs = self.query_one("#main-tabs", TabbedContent)
        active_tab = tabs.active

        if active_tab == "history-tab":
            self.query_one("#history-view", HistoryView).refresh_history()
        elif active_tab == "memory-tab":
            self.query_one("#memory-view", MemoryView).refresh_memory()
        elif active_tab == "refresh-tab":
            self.query_one("#system-view", SystemView).refresh_info()
        elif active_tab == "rollback-tab":
            self.query_one("#rollback-view", RollbackView).refresh_history()
    
    def action_clear_log(self) -> None:
        """Clear execution log"""
        exec_log = self.query_one("#execution-log-container", ExecutionLog)
        exec_log.clear_log()
    
    def action_rollback(self) -> None:
        """Switch to Rollback tab."""
        self.action_tab("rollback")

    def action_pick_model(self) -> None:
        """Switch to Model tab."""
        self.action_tab("model")


def main():
    """Entry point for TUI"""
    app = ZenusDashboard()
    app.run()


if __name__ == "__main__":
    main()
