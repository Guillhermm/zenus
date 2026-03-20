"""
CLI Formatting and Colors

Beautiful, readable output using rich library.
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich import box
from typing import List, Dict, Any

# Import visualization system
try:
    from zenus_visualization import Visualizer
    VISUALIZATION_ENABLED = True
except ImportError:
    VISUALIZATION_ENABLED = False
    Visualizer = None


console = Console()


def print_markdown(text: str) -> None:
    """Render LLM-generated text as Markdown (bold, italic, lists, code blocks…)."""
    console.print(Markdown(text))


def print_success(message: str):
    """Print success message in green"""
    console.print(f"✓ {message}", style="bold green")


def print_error(message: str):
    """Print error message in red"""
    console.print(f"✗ {message}", style="bold red")


def print_warning(message: str):
    """Print warning message in yellow"""
    console.print(f"⚠ {message}", style="bold yellow")


def print_info(message: str):
    """Print info message in blue"""
    console.print(f"ℹ {message}", style="bold cyan")


def print_step(step_num: int, tool: str, action: str, risk: int, result: Any = None):
    """Print execution step with color coding and automatic visualization"""
    
    # Risk color coding
    risk_colors = {
        0: "green",      # Read-only
        1: "cyan",       # Create/move
        2: "yellow",     # Overwrite
        3: "red"         # Delete
    }
    
    risk_labels = {
        0: "READ",
        1: "CREATE",
        2: "MODIFY",
        3: "DELETE"
    }
    
    color = risk_colors.get(risk, "white")
    label = risk_labels.get(risk, "UNKNOWN")
    
    console.print(
        f"  [{color}][{label}][/{color}] Step {step_num}: "
        f"[bold]{tool}.{action}[/bold]",
        highlight=False
    )
    
    if result:
        # Use visualization system if available
        if VISUALIZATION_ENABLED and Visualizer:
            # Determine context hint from tool/action
            context = None
            if "scan" in action.lower() or "list" in action.lower():
                context = "file_list"
            elif "process" in action.lower():
                context = "process_list"
            elif "disk" in action.lower():
                context = "disk_usage"
            
            try:
                Visualizer.visualize(result, context)
                return  # Skip old formatting
            except Exception:
                # Fallback on visualization error (silent fallback to old formatting)
                pass
        
        # Fallback: Try to format result if it's structured data
        result_str = str(result)
        
        # Check if result looks like it should be formatted nicely
        should_format = (
            result_str.count('\n') > 3 or  # Multi-line
            '{' in result_str or  # JSON-like
            '|' in result_str or  # Table-like
            '\t' in result_str     # Tab-separated
        )
        
        if should_format and len(result_str) > 50:
            # Use rich formatter for complex output
            try:
                from zenus_core.output import format_output
                console.print("  → Result:")
                format_output(result_str, title=None)
            except Exception:
                # Fallback to simple display
                console.print(f"  → {result}", style="dim")
        else:
            # Simple one-liner
            console.print(f"  → {result}", style="dim")


def print_goal(goal: str):
    """Print goal in a nice format"""
    console.print(f"\n[bold cyan]Goal:[/bold cyan] {goal}\n")


def print_plan_summary(steps: List[Dict]):
    """Print execution plan summary"""
    table = Table(
        title="Execution Plan",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta"
    )
    
    table.add_column("#", style="dim", width=3)
    table.add_column("Tool", style="cyan")
    table.add_column("Action", style="green")
    table.add_column("Risk", justify="center")
    
    risk_emoji = {0: "🟢", 1: "🔵", 2: "🟡", 3: "🔴"}
    
    for i, step in enumerate(steps, 1):
        risk = step.get("risk", 0)
        emoji = risk_emoji.get(risk, "⚪")
        
        table.add_row(
            str(i),
            step.get("tool", "?"),
            step.get("action", "?"),
            emoji
        )
    
    console.print(table)


def print_similar_commands(results: List[Dict]):
    """Print similar past commands"""
    if not results:
        return
    
    console.print("\n[bold yellow]Similar past commands:[/bold yellow]")
    
    for i, result in enumerate(results, 1):
        similarity = result.get("similarity", 0)
        success = result.get("success", False)
        user_input = result.get("user_input", "")
        
        status = "✓" if success else "✗"
        status_color = "green" if success else "red"
        
        console.print(
            f"  {i}. [{status_color}]{status}[/{status_color}] "
            f"[dim]{user_input}[/dim] "
            f"[cyan]({similarity:.0%} similar)[/cyan]"
        )


def print_explanation(goal: str, steps: List[Dict], reasoning: str = None):
    """Print detailed explanation of the plan"""
    
    # Create explanation panel
    explanation = f"[bold cyan]Goal:[/bold cyan] {goal}\n\n"
    
    if reasoning:
        explanation += f"[bold yellow]Reasoning:[/bold yellow]\n{reasoning}\n\n"
    
    explanation += "[bold green]Execution Plan:[/bold green]\n"
    
    for i, step in enumerate(steps, 1):
        tool = step.get("tool", "?")
        action = step.get("action", "?")
        args = step.get("args", {})
        risk = step.get("risk", 0)
        
        risk_labels = {0: "🟢 Safe", 1: "🔵 Create", 2: "🟡 Modify", 3: "🔴 Danger"}
        risk_label = risk_labels.get(risk, "⚪ Unknown")
        
        explanation += f"  {i}. {risk_label} [bold]{tool}.{action}[/bold]\n"
        
        # Show args
        for key, value in args.items():
            explanation += f"     • {key}: [cyan]{value}[/cyan]\n"
    
    panel = Panel(
        explanation,
        title="[bold]Plan Explanation[/bold]",
        border_style="blue",
        box=box.ROUNDED
    )
    
    console.print(panel)


def print_code_block(code: str, language: str = "python"):
    """Print syntax-highlighted code"""
    syntax = Syntax(code, language, theme="monokai", line_numbers=True)
    console.print(syntax)


def print_json(data: Dict):
    """Print formatted JSON"""
    syntax = Syntax(
        str(data), 
        "json", 
        theme="monokai",
        word_wrap=True
    )
    console.print(syntax)


def print_divider(char: str = "─", width: int = 80):
    """Print horizontal divider"""
    console.print(char * width, style="dim")


def print_header(text: str):
    """Print section header"""
    console.print(f"\n[bold underline cyan]{text}[/bold underline cyan]\n")


def print_status_table(data: Dict[str, str]):
    """Print status information as table"""
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Key", style="cyan", width=20)
    table.add_column("Value", style="white")
    
    for key, value in data.items():
        table.add_row(key, str(value))
    
    console.print(table)
