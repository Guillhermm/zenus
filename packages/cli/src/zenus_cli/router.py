"""
CLI Command Router

Responsible for:
- Parsing CLI arguments
- Routing to appropriate handlers (interactive/direct/help)
- Maintaining clear separation between parse, intent, execute
"""

import sys
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class CLICommand:
    """Represents a parsed CLI command"""
    mode: str  # 'interactive', 'direct', 'help', 'version', 'status', 'model'
    input_text: Optional[str] = None
    flags: dict = field(default_factory=dict)


class CommandRouter:
    """Routes CLI invocations to appropriate handlers"""

    def __init__(self):
        self.version = "0.1.0-alpha"

    def parse(self, args: List[str]) -> CLICommand:
        """
        Parse command line arguments into a CLICommand
        
        Modes:
        - No args or 'shell' -> interactive REPL
        - 'help' / '--help' / '-h' -> help message
        - 'version' / '--version' / '-v' -> version info
        - 'rollback' -> rollback commands
        - 'history' -> history commands
        - '--dry-run <text>' -> show plan but do not execute
        - Direct text -> immediate intent execution
        """
        
        # Check for flags
        dry_run = False
        iterative = False
        force_provider: Optional[str] = None
        force_model: Optional[str] = None
        filtered_args = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--dry-run":
                dry_run = True
            elif arg == "--iterative":
                iterative = True
            elif arg in ("--provider", "-p") and i + 1 < len(args):
                force_provider = args[i + 1]
                i += 1
            elif arg.startswith("--provider="):
                force_provider = arg.split("=", 1)[1]
            elif arg == "--model" and i + 1 < len(args):
                force_model = args[i + 1]
                i += 1
            elif arg.startswith("--model="):
                force_model = arg.split("=", 1)[1]
            else:
                filtered_args.append(arg)
            i += 1

        args = filtered_args
        
        if not args or args[0] == "shell":
            return CLICommand(mode="interactive")
        
        if args[0] in ("help", "--help", "-h"):
            return CLICommand(mode="help")
        
        if args[0] in ("version", "--version", "-v"):
            return CLICommand(mode="version")
        
        if args[0] == "status":
            return CLICommand(mode="status")

        if args[0] == "model":
            return CLICommand(
                mode="model",
                input_text=" ".join(args[1:]) if len(args) > 1 else "status",
            )

        if args[0] == "rollback":
            return CLICommand(
                mode="rollback",
                input_text=" ".join(args[1:]) if len(args) > 1 else None,
                flags={"dry_run": dry_run}
            )
        
        if args[0] == "history":
            return CLICommand(
                mode="history",
                input_text=" ".join(args[1:]) if len(args) > 1 else None
            )
        
        # Everything else is a direct command
        input_text = " ".join(args)
        return CLICommand(
            mode="direct",
            input_text=input_text,
            flags={
                "dry_run": dry_run,
                "iterative": iterative,
                "force_provider": force_provider,
                "force_model": force_model,
            },
        )

    def show_help(self):
        """Display help message"""
        help_text = f"""
Zenus v{self.version}
A developer-centric, CLI-first, agent-driven operating layer

USAGE:
    zenus [OPTIONS] [COMMAND]

COMMANDS:
    shell                   Start interactive REPL (default)
    status                  Show system status and active LLM config
    model [status]          Show current provider/model configuration
    model list              List all available models per provider
    model set <p> [model]   Set default provider (and optionally model)
    rollback [N]            Rollback last N actions (default: 1)
    history                 Show command history and failures
    help                    Show this help message
    version                 Show version information
    <direct command>        Execute command immediately

OPTIONS:
    --dry-run               Show plan but do not execute
    --iterative             Use iterative ReAct loop (for complex tasks)
    --provider <name>       Use specific provider for this command only
                              (anthropic, openai, deepseek, ollama)
    --model <id>            Use specific model for this command only

EXAMPLES:
    zenus                                         # Start interactive shell
    zenus "list files in ~/Documents"             # Direct execution
    zenus --dry-run "delete all tmp files"        # Preview without executing
    zenus --provider deepseek "summarize this"    # Override provider once
    zenus --model claude-opus-4-6 "refactor src"  # Override model once
    zenus model set anthropic claude-opus-4-6     # Change default
    zenus --iterative "read project and improve"  # Multi-step ReAct loop

INTERACTIVE SHELL SHORTCUTS:
    @deepseek: your command    # Use deepseek for this command
    use claude: your command   # Use anthropic for this command
    --provider openai <cmd>    # Override provider in shell mode
    model set deepseek         # Change default inside shell
    status                     # Show status inside shell

PROVIDER ALIASES (for inline overrides):
    anthropic, claude, sonnet, haiku, opus → anthropic
    openai, gpt, chatgpt, o1, o3          → openai
    deepseek                               → deepseek
    ollama, local, llama                   → ollama

CREDENTIALS:
    ANTHROPIC_API_KEY   Anthropic (Claude) API key
    OPENAI_API_KEY      OpenAI API key
    DEEPSEEK_API_KEY    DeepSeek API key
    (or set in config.yaml / .env)

LOGS:
    Audit logs: ~/.zenus/logs/

For more information, visit: https://github.com/Guillhermm/zenus
        """.strip()
        print(help_text)

    def show_version(self):
        """Display version information"""
        print(f"Zenus v{self.version}")
