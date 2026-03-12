"""
Special CLI Commands

Built-in commands that don't go through intent translation.
"""

import os
import sys
from zenus_core.memory.session_memory import SessionMemory
from zenus_core.memory.world_model import WorldModel
from zenus_core.memory.intent_history import IntentHistory


def handle_status_command(orchestrator):
    """Show Zenus status"""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from zenus_core.brain.llm.factory import get_available_providers

    console = Console()
    console.print()
    console.print(Panel.fit("[bold cyan]Zenus Status[/bold cyan]", border_style="cyan"))
    console.print()

    # Session stats
    if orchestrator.use_memory:
        try:
            session_stats = orchestrator.session_memory.get_session_stats()
            console.print(f"[bold]Session:[/bold] {session_stats['session_duration_seconds']:.0f}s  "
                          f"| Commands: {session_stats['total_intents']}  "
                          f"| Context refs: {session_stats['context_refs']}")
        except Exception:
            pass

    # World model
    if orchestrator.use_memory:
        try:
            world_summary = orchestrator.world_model.get_summary()
            if world_summary:
                console.print(f"[bold]World:[/bold] {world_summary}")
        except Exception:
            pass

    # LLM configuration (read from config.yaml, not env var)
    console.print()
    console.print("[bold]LLM Configuration:[/bold]")

    primary_provider = "anthropic"
    primary_model = None
    fallback_enabled = False
    fallback_providers: list = []

    try:
        from zenus_core.config.loader import get_config
        cfg = get_config()
        primary_provider = cfg.llm.provider
        primary_model = cfg.llm.model
        fallback_enabled = cfg.fallback.enabled
        fallback_providers = list(cfg.fallback.providers) if cfg.fallback.providers else []
    except Exception:
        import os
        primary_provider = os.getenv("ZENUS_LLM", "anthropic")

    console.print(f"  Primary:  [cyan]{primary_provider}[/cyan]"
                  + (f" / [dim]{primary_model}[/dim]" if primary_model else ""))

    if fallback_enabled and fallback_providers:
        chain = " → ".join(fallback_providers)
        console.print(f"  Fallback: [dim]{chain}[/dim]")
    else:
        console.print("  Fallback: [dim]disabled[/dim]")

    # Available providers (those with API keys configured)
    console.print()
    console.print("[bold]Available providers:[/bold]")
    available = get_available_providers()

    for prov in ["anthropic", "openai", "deepseek", "ollama"]:
        has_key = prov in available
        mark = "[green]✓[/green]" if has_key else "[red]✗[/red]"
        active = " [bold cyan](primary)[/bold cyan]" if prov == primary_provider else ""
        console.print(f"  {mark} {prov}{active}")

    # Router stats if any
    try:
        stats = orchestrator.router.stats
        if stats.get("total_requests", 0) > 0:
            console.print()
            console.print(f"[bold]Router stats:[/bold] "
                          f"{stats['total_requests']} requests, "
                          f"${stats.get('total_cost', 0):.4f} estimated cost")
    except Exception:
        pass

    console.print()


def handle_model_command(subcommand: str = "status", args: list = None):
    """
    Model management commands

    Subcommands:
        status (default) — show current provider/model config
        list             — list all models by provider
        set <provider> [model] — update config.yaml default
    """
    from rich.console import Console
    from rich.table import Table
    from zenus_core.brain.llm.factory import get_available_providers

    console = Console()
    args = args or []

    # Available models per provider (kept up-to-date)
    MODELS = {
        "anthropic": [
            ("claude-opus-4-6",      "Most capable — complex agents & coding"),
            ("claude-sonnet-4-6",    "Best speed/intelligence balance (recommended)"),
            ("claude-haiku-4-5",     "Fastest, near-frontier intelligence"),
        ],
        "openai": [
            ("gpt-4o",               "Flagship multimodal model"),
            ("gpt-4o-mini",          "Fast and cost-efficient"),
            ("gpt-4.1",              "Strong instruction-following, long context"),
            ("gpt-4.1-mini",         "Smaller, cheaper GPT-4.1"),
            ("o3",                   "Frontier reasoning — math, coding, science"),
            ("o3-mini",              "Fast reasoning for STEM tasks"),
            ("o4-mini",              "Cost-efficient reasoning"),
        ],
        "deepseek": [
            ("deepseek-chat",        "DeepSeek-V3 — general purpose (recommended)"),
            ("deepseek-reasoner",    "DeepSeek-R1 — chain-of-thought & reasoning"),
        ],
        "ollama": [
            ("llama3.1:8b",          "Meta Llama 3.1 — most-pulled, great general model"),
            ("llama3.2:3b",          "Small Llama 3.2 — fast, low memory (2GB)"),
            ("qwen2.5:7b",           "Qwen 2.5 — excellent reasoning (4.7GB)"),
            ("qwen3:8b",             "Qwen 3 — latest generation"),
            ("deepseek-r1:7b",       "DeepSeek-R1 reasoning model (local)"),
            ("mistral:7b",           "Mistral 7B — fast, capable"),
            ("phi4:14b",             "Microsoft Phi-4 — efficient"),
            ("gemma3:4b",            "Google Gemma 3 — lightweight"),
        ],
    }

    if subcommand in ("status", ""):
        # Show current config
        primary_provider = "anthropic"
        primary_model = None
        fallback_enabled = False
        fallback_providers: list = []

        try:
            from zenus_core.config.loader import get_config
            cfg = get_config()
            primary_provider = cfg.llm.provider
            primary_model = cfg.llm.model
            fallback_enabled = cfg.fallback.enabled
            fallback_providers = list(cfg.fallback.providers) if cfg.fallback.providers else []
        except Exception:
            import os
            primary_provider = os.getenv("ZENUS_LLM", "anthropic")

        available = get_available_providers()

        console.print()
        console.print("[bold cyan]Current LLM configuration:[/bold cyan]")
        console.print(f"  Provider: [cyan]{primary_provider}[/cyan]"
                      + (f"  Model: [dim]{primary_model}[/dim]" if primary_model else ""))
        if fallback_enabled and fallback_providers:
            console.print(f"  Fallback: {' → '.join(fallback_providers)}")

        console.print()
        console.print("[bold]Available providers:[/bold]")
        for prov in ["anthropic", "openai", "deepseek", "ollama"]:
            mark = "[green]✓[/green]" if prov in available else "[red]✗[/red]"
            tag = " [bold cyan](active)[/bold cyan]" if prov == primary_provider else ""
            console.print(f"  {mark} {prov}{tag}")

        console.print()
        console.print("[dim]Change default: zenus model set <provider> [model][/dim]")
        console.print("[dim]List all models: zenus model list[/dim]")
        console.print("[dim]Per-command: @deepseek: your command  or  --provider deepseek your command[/dim]")
        console.print()

    elif subcommand == "list":
        console.print()
        available = get_available_providers()

        for prov, models in MODELS.items():
            has_key = prov in available
            header = f"[bold cyan]{prov}[/bold cyan]"
            if has_key:
                header += " [green](configured)[/green]"
            else:
                header += " [dim](no API key)[/dim]"

            table = Table(show_header=True, header_style="dim", box=None, padding=(0, 2))
            table.add_column("Model ID", style="cyan", no_wrap=True)
            table.add_column("Description")

            for model_id, desc in models:
                table.add_row(model_id, desc)

            console.print(header)
            console.print(table)
            console.print()

    elif subcommand == "set":
        if not args:
            console.print("[red]Usage: model set <provider> [model][/red]")
            console.print("[dim]Example: model set anthropic claude-opus-4-6[/dim]")
            return

        new_provider = args[0].lower()
        new_model = args[1] if len(args) > 1 else None

        # Validate provider
        valid_providers = list(MODELS.keys())
        if new_provider not in valid_providers:
            console.print(f"[red]Unknown provider '{new_provider}'.[/red] "
                          f"Valid: {', '.join(valid_providers)}")
            return

        # Write to config.yaml
        _update_config_provider(new_provider, new_model)

        label = new_provider + (f"/{new_model}" if new_model else "")
        console.print(f"[green]✓ Default provider set to {label}[/green]")
        console.print("[dim]Changes take effect on next command.[/dim]")

    else:
        console.print(f"[red]Unknown subcommand '{subcommand}'[/red]")
        console.print("[dim]Usage: model [status|list|set][/dim]")


def _update_config_provider(provider: str, model: str = None):
    """Update llm.provider (and optionally llm.model) in the active config.yaml."""
    import yaml
    from pathlib import Path

    # Find the config file that's actually loaded
    search_paths = [
        Path(os.environ.get("ZENUS_CONFIG", "")) if os.environ.get("ZENUS_CONFIG") else None,
        Path("config.yaml"),
        Path("zenus.yaml"),
        Path.home() / ".zenus" / "config.yaml",
        Path.home() / ".config" / "zenus" / "config.yaml",
    ]
    config_path = None
    for p in search_paths:
        if p and p.exists():
            config_path = p
            break

    if not config_path:
        raise FileNotFoundError("No config.yaml found. Run the install script first.")

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    if "llm" not in data:
        data["llm"] = {}
    data["llm"]["provider"] = provider
    if model:
        data["llm"]["model"] = model

    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def handle_memory_command(orchestrator, subcommand: str = "stats"):
    """Memory management commands"""
    
    if not orchestrator.use_memory:
        print("Memory is disabled")
        return
    
    if subcommand == "stats":
        session_stats = orchestrator.session_memory.get_session_stats()
        print(f"\n📊 Memory Statistics:\n")
        print(f"Session:")
        print(f"  Intents: {session_stats['total_intents']}")
        print(f"  References: {session_stats['context_refs']}")
        print(f"  Duration: {session_stats['session_duration_seconds']:.0f}s")
        print()
        
        frequent = orchestrator.world_model.get_frequent_paths(5)
        if frequent:
            print(f"Frequent Paths:")
            for path in frequent:
                print(f"  - {path}")
        print()
    
    elif subcommand == "clear":
        confirm = input("Clear session memory? (y/n): ")
        if confirm.lower() == 'y':
            orchestrator.session_memory.clear()
            print("✓ Session memory cleared")
    
    else:
        print(f"Unknown memory command: {subcommand}")
        print("Available: stats, clear")


def handle_update_command():
    """Update Zenus"""
    import subprocess
    import os
    
    print("\n🔄 Updating Zenus...")
    print()
    
    # Update git repo
    print("Pulling latest changes...")
    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        print(result.stdout.strip())
    except Exception as e:
        print(f"⚠️  Git pull failed: {e}")
    
    # Update dependencies via Poetry
    print("\nUpdating Python dependencies...")
    try:
        # Get the project root (2 levels up from core package)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        
        # Update core package
        core_dir = os.path.join(project_root, "packages/core")
        if os.path.exists(core_dir):
            print("  → Updating zenus-core...")
            subprocess.run(["poetry", "install"], cwd=core_dir, check=True, capture_output=True)
        
        # Update CLI package
        cli_dir = os.path.join(project_root, "packages/cli")
        if os.path.exists(cli_dir):
            print("  → Updating zenus-cli...")
            subprocess.run(["poetry", "install"], cwd=cli_dir, check=True, capture_output=True)
        
        print("✓ Dependencies updated")
    except Exception as e:
        print(f"⚠️  Dependency update failed: {e}")
    
    print("\n✓ Update complete!")
    print("  Restart Zenus to apply changes")
    print()


def handle_explain_command(orchestrator, arg: str = "last"):
    """Explain a past execution"""
    from zenus_core.shell.explain import get_explainability_dashboard
    
    dashboard = get_explainability_dashboard()
    
    if arg == "last":
        dashboard.explain_last(verbose=True)
    elif arg == "history":
        dashboard.show_history(limit=20)
    elif arg.isdigit():
        index = -int(arg)
        dashboard.explain_execution(index, verbose=True)
    else:
        print(f"Unknown explain command: {arg}")
        print("Usage: explain [last|history|N]")



def check_and_suggest_patterns(orchestrator):
    """
    Check for patterns and suggest automation
    
    Should be called periodically in interactive mode
    (e.g., every 10 commands)
    """
    from zenus_core.brain.pattern_detector import get_pattern_detector
    from zenus_core.brain.pattern_memory import get_pattern_memory
    from zenus_core.memory.intent_history import IntentHistory
    from rich.console import Console
    from rich.panel import Panel
    
    console = Console()
    
    # Get pattern detector and memory
    detector = get_pattern_detector()
    memory = get_pattern_memory()
    
    # Get execution history
    history = IntentHistory()
    
    try:
        # Load history records
        history_records = []
        for record in history.history:
            history_records.append({
                'user_input': record.get('user_input', ''),
                'timestamp': record.get('timestamp', ''),
                'intent': record.get('intent', {})
            })
        
        # Detect patterns
        patterns = detector.detect_patterns(history_records, lookback_days=30)
        
        # Filter to high-confidence patterns we haven't suggested yet
        high_confidence = []
        for p in patterns:
            if p.confidence >= 0.8:
                # Create unique key for this pattern
                pattern_key = f"{p.pattern_type}:{p.description[:50]}"
                if not memory.has_suggested(pattern_key):
                    high_confidence.append((p, pattern_key))
        
        if not high_confidence:
            return
        
        # Show first pattern suggestion
        pattern, pattern_key = high_confidence[0]
        
        # Mark as suggested (so we don't repeat)
        memory.mark_suggested(pattern_key)
        
        if pattern.pattern_type == 'recurring' and pattern.suggested_cron:
            console.print()
            console.print(Panel.fit(
                f"[cyan]💡 Pattern Detected[/cyan]\n\n"
                f"I noticed {pattern.description}.\n\n"
                f"Would you like me to set up an automatic {pattern.frequency} task?",
                border_style="cyan",
                title="[bold]Suggestion[/bold]"
            ))
            
            choice = input("\n[Y]es / [N]o / [S]how more: ").strip().lower()
            
            if choice == 'y':
                # Create cron job
                cmd = pattern.commands[-1] if pattern.commands else pattern.description
                
                console.print(f"\n[green]Creating cron job:[/green]")
                console.print(f"  Schedule: {pattern.suggested_cron}")
                console.print(f"  Command: {cmd}")
                console.print(f"\n[dim]Note: Cron integration coming soon![/dim]")
                console.print(f"[dim]For now, you can manually add this to your crontab.[/dim]")
            
            elif choice == 's':
                # Show all patterns
                console.print("\n[cyan]Detected Patterns:[/cyan]\n")
                for i, (p, _) in enumerate(high_confidence[:5], 1):
                    console.print(f"{i}. {p.description}")
                    console.print(f"   [dim]Confidence: {p.confidence:.0%}, Occurrences: {p.occurrences}[/dim]")
                    if p.suggested_cron:
                        console.print(f"   [dim]Cron: {p.suggested_cron}[/dim]")
                    console.print()
    
    except Exception as e:
        # Silently fail - pattern detection is optional
        pass


def handle_workflow_command(orchestrator, subcommand: str = "list", *args):
    """
    Workflow management commands
    
    Subcommands:
    - list: Show all workflows
    - record <name>: Start recording
    - stop: Stop recording
    - replay <name>: Replay workflow
    - info <name>: Show workflow details
    - delete <name>: Delete workflow
    """
    from zenus_core.workflows import get_workflow_recorder
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    recorder = get_workflow_recorder()
    
    if subcommand == "list":
        workflows = recorder.list_workflows()
        
        if not workflows:
            console.print("[yellow]No workflows saved yet[/yellow]")
            console.print("\n[dim]Start recording with: workflow record <name>[/dim]")
            return
        
        console.print("\n[bold cyan]Saved Workflows:[/bold cyan]\n")
        
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Steps", justify="right")
        table.add_column("Used", justify="right")
        table.add_column("Description")
        
        for name in workflows:
            info = recorder.get_workflow_info(name)
            if info:
                table.add_row(
                    name,
                    str(info['steps']),
                    str(info['use_count']),
                    info['description'][:50] if info['description'] else '-'
                )
        
        console.print(table)
    
    elif subcommand == "record":
        if not args:
            console.print("[red]Error: Provide workflow name[/red]")
            console.print("[dim]Usage: workflow record <name> [description][/dim]")
            return
        
        name = args[0]
        description = " ".join(args[1:]) if len(args) > 1 else ""
        
        result = recorder.start_recording(name, description)
        console.print(f"\n[green]{result}[/green]")
        console.print("[dim]Type commands, then: workflow stop[/dim]\n")
    
    elif subcommand == "stop":
        result = recorder.stop_recording()
        console.print(f"\n[green]{result}[/green]\n")
    
    elif subcommand == "cancel":
        result = recorder.cancel_recording()
        console.print(f"\n[yellow]{result}[/yellow]\n")
    
    elif subcommand == "replay":
        if not args:
            console.print("[red]Error: Provide workflow name[/red]")
            console.print("[dim]Usage: workflow replay <name>[/dim]")
            return
        
        name = args[0]
        commands = recorder.replay_workflow(name, dry_run=False)
        
        if commands and "not found" in commands[0].lower():
            console.print(f"\n[red]{commands[0]}[/red]\n")
            return
        
        console.print(f"\n[cyan]Replaying workflow: {name}[/cyan]\n")
        
        # Execute each command
        for i, cmd in enumerate(commands, 1):
            console.print(f"[dim]Step {i}:[/dim] {cmd}")
            try:
                orchestrator.execute_command(cmd)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                break
    
    elif subcommand == "info":
        if not args:
            console.print("[red]Error: Provide workflow name[/red]")
            return
        
        name = args[0]
        info = recorder.get_workflow_info(name)
        
        if not info:
            console.print(f"\n[red]Workflow not found: {name}[/red]\n")
            return
        
        console.print(f"\n[bold cyan]Workflow: {name}[/bold cyan]\n")
        console.print(f"Description: {info['description'] or '-'}")
        console.print(f"Steps: {info['steps']}")
        console.print(f"Created: {info['created']}")
        console.print(f"Used: {info['use_count']} times")
        if info['last_used']:
            console.print(f"Last used: {info['last_used']}")
        if info['parameters']:
            console.print(f"Parameters: {', '.join(info['parameters'])}")
        console.print()
    
    elif subcommand == "delete":
        if not args:
            console.print("[red]Error: Provide workflow name[/red]")
            return
        
        name = args[0]
        result = recorder.delete_workflow(name)
        console.print(f"\n{result}\n")
    
    else:
        console.print(f"[red]Unknown subcommand: {subcommand}[/red]")
        console.print("\n[dim]Available: list, record, stop, replay, info, delete[/dim]\n")
