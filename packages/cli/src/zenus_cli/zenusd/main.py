"""
Zenus - Main Entry Point

CLI-first, agent-driven operating layer
Routes commands through: CLI to Intent to Plan to Execute
"""

import sys
from zenus_cli.router import CommandRouter
from zenus_core.orchestrator import Orchestrator, OrchestratorError
from zenus_core.rollback import get_rollback_engine, RollbackError
from zenus_core.memory.action_tracker import get_action_tracker
from zenus_core.memory.failure_logger import get_failure_logger
from zenus_core.output.console import console


def main():
    """Main entry point for Zenus"""
    
    router = CommandRouter()
    orchestrator = Orchestrator()
    
    # Parse CLI arguments (skip program name)
    args = sys.argv[1:]
    command = router.parse(args)
    
    # Route to appropriate handler
    try:
        if command.mode == "help":
            router.show_help()

        elif command.mode == "version":
            router.show_version()

        elif command.mode == "status":
            from zenus_core.shell.commands import handle_status_command
            handle_status_command(orchestrator)

        elif command.mode == "model":
            from zenus_core.shell.commands import handle_model_command
            parts = (command.input_text or "status").split()
            subcommand = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            handle_model_command(subcommand, args)

        elif command.mode == "interactive":
            orchestrator.interactive_shell()
        
        elif command.mode == "rollback":
            # Rollback command
            rollback_engine = get_rollback_engine()
            dry_run = command.flags.get("dry_run", False)
            
            # Parse number of actions to rollback
            n = 1
            if command.input_text:
                try:
                    n = int(command.input_text)
                except ValueError:
                    console.print("[red]Error: rollback argument must be a number[/red]")
                    sys.exit(1)
            
            try:
                result = rollback_engine.rollback_last_n_actions(n, dry_run=dry_run)
                if result["success"]:
                    if result.get("dry_run"):
                        console.print("\n[green]Dry run complete - no changes made[/green]")
                    else:
                        console.print(f"\n[green]✓ Successfully rolled back {result['actions_rolled_back']} action(s)[/green]")
                else:
                    console.print(f"\n[yellow]⚠ Partial rollback: {result['actions_rolled_back']} succeeded, {result['actions_failed']} failed[/yellow]")
                    for error in result["errors"]:
                        console.print(f"  [red]• {error}[/red]")
            except RollbackError as e:
                console.print(f"[red]Rollback error: {e}[/red]")
                sys.exit(1)
        
        elif command.mode == "history":
            # History command
            action_tracker = get_action_tracker()
            failure_logger = get_failure_logger()
            
            # Check if --failures flag
            show_failures = command.input_text == "--failures"
            
            if show_failures:
                # Show failure history
                stats = failure_logger.get_failure_stats()
                console.print("\n[cyan]Failure History:[/cyan]")
                console.print(f"  Total failures: {stats['total_failures']}")
                console.print(f"  Recent (7 days): {stats['recent_7_days']}")
                
                if stats['by_tool']:
                    console.print("\n[cyan]By tool:[/cyan]")
                    for tool, count in sorted(stats['by_tool'].items(), key=lambda x: x[1], reverse=True)[:10]:
                        console.print(f"  {tool}: {count}")
                
                if stats['by_error_type']:
                    console.print("\n[cyan]By error type:[/cyan]")
                    for error_type, count in sorted(stats['by_error_type'].items(), key=lambda x: x[1], reverse=True):
                        console.print(f"  {error_type}: {count}")
                
                console.print(f"\n[cyan]Patterns with suggestions: {stats['patterns_with_suggestions']}[/cyan]")
            else:
                # Show transaction history
                transactions = action_tracker.get_recent_transactions(limit=10)
                console.print("\n[cyan]Recent Transactions:[/cyan]")
                for tx in transactions:
                    status_color = "green" if tx["status"] == "completed" else "red"
                    rollback_info = " (rolled back)" if tx.get("rollback_status") else ""
                    console.print(f"  [{status_color}]{tx['id']}[/{status_color}]: {tx['user_input']}{rollback_info}")
                    console.print(f"    Goal: {tx['intent_goal']}")
                    console.print(f"    Status: {tx['status']}")
                    console.print()
        
        elif command.mode == "mcp_server":
            from zenus_core.config.loader import get_config
            from zenus_core.mcp.server import run_server
            cfg = get_config()
            srv = cfg.mcp.server
            # CLI flags override config
            allow_privileged = command.flags.get("allow_privileged", srv.allow_privileged)
            transport = command.flags.get("transport", srv.transport)
            host = command.flags.get("host", srv.host)
            port = command.flags.get("port", srv.port)
            console.print(
                f"[cyan]Starting Zenus MCP server[/cyan] "
                f"(transport=[bold]{transport}[/bold], "
                f"privileged=[bold]{allow_privileged}[/bold])"
            )
            if transport == "sse":
                console.print(f"  Listening on [bold]{host}:{port}[/bold]")
            run_server(
                transport=transport,
                host=host,
                port=port,
                allow_privileged=allow_privileged,
            )

        elif command.mode == "direct":
            # Direct execution
            dry_run = command.flags.get("dry_run", False)
            iterative = command.flags.get("iterative", False)
            force_provider = command.flags.get("force_provider")
            force_model = command.flags.get("force_model")

            # If --model given without --provider, embed it as an inline directive
            # so the orchestrator's provider_override parser can infer the provider
            input_text = command.input_text
            if force_model and not force_provider:
                input_text = f"--model {force_model} {input_text}"
                force_provider = None  # let the parser infer it

            if iterative:
                result = orchestrator.execute_iterative(
                    input_text,
                    max_iterations=10,
                    dry_run=dry_run,
                    force_provider=force_provider,
                )
            else:
                result = orchestrator.execute_command(
                    input_text,
                    dry_run=dry_run,
                    force_provider=force_provider,
                )

            if result:
                print(result)
    
    except OrchestratorError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
