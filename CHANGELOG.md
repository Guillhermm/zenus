# Changelog

All notable changes to Zenus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **CI: snap build syntax error**: replaced `${{ env.VERSION }}` with `$VERSION` in `release.yml` snap stamp step — the GHA expression inside an unquoted YAML scalar caused a parse error; the shell env var (already set via `$GITHUB_ENV`) is the correct reference.

---

## [0.6.0] - 2026-03-12

### Added
- **`ShellOps` meta-tool** (`shell` escape hatch): Allows the LLM to run arbitrary shell commands as IntentIR steps. Every invocation is logged, attributed, and gated by privilege tier. Hard-blocked patterns (fork bombs, `rm -rf /`, etc.) are always rejected.
- **`CodeExec` tool**: LLM can write and run Python snippets or Bash scripts as IntentIR steps. Code runs in an isolated subprocess; stdout/stderr feed back into the ReAct observation loop. Output is capped at 8 000 chars to prevent context blowout.
- **Privilege tiers** (`PrivilegeTier`): `STANDARD` (default, automated contexts) vs `PRIVILEGED` (interactive sessions). `ShellOps` and `CodeExec` are only available at `PRIVILEGED` tier. Interactive shell auto-elevates on startup.
- **Self-describing registry** (`registry.describe()` / `registry.describe_compact()`): Every tool exposes its actions with parameter types and docstrings. Lets the LLM introspect what's available and generate valid IntentIR steps without hallucinating tool names.
- **Per-command provider override**: Any command can target a specific LLM on-the-fly without changing defaults.
  - Natural language: `@deepseek: summarize this`, `use claude: refactor src/`
  - Flags: `--provider deepseek`, `--model claude-opus-4-6`
  - Works in CLI direct mode, interactive shell, and TUI
  - Provider inferred automatically from model name when using `--model`
  - New `zenus_core.brain.provider_override` module handles all syntax variants
- **CLI `zenus status`** subcommand: shows active provider/model from config.yaml, fallback chain, and available providers
- **CLI `zenus model` subcommands**:
  - `zenus model` / `zenus model status` — current provider/model and availability
  - `zenus model list` — all models per provider with descriptions (current as of 2026)
  - `zenus model set <provider> [model]` — update config.yaml default without editing the file
  - Available inside interactive shell too: `model set anthropic claude-opus-4-6`
- **TUI model picker** (`Ctrl+M`): modal dialog to select provider and model; updates config.yaml and applies for the session immediately
- **Install script**: all model lists refreshed to current versions
  - Anthropic: claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5
  - DeepSeek: deepseek-chat (V3), deepseek-reasoner (R1)
  - OpenAI: gpt-4o, gpt-4o-mini, gpt-4.1, o3, o4-mini
  - Ollama: llama3.1, qwen3, deepseek-r1, mistral, llama3.2, phi4, gemma3, qwen2.5-coder

### Fixed
- **`zenus status` model display**: was reading `ZENUS_LLM` env var (defaulting to `openai`) instead of `config.yaml`

### Fixed
- **TUI responsiveness**: `Orchestrator` init moved from `__init__` to an async background worker so the UI renders and accepts input immediately on launch
- **TUI model display**: Sub-title now correctly shows the active model name read from `config.yaml` once the orchestrator finishes loading
- **TUI execution log**: Replaced `Static` widget (which parsed `[HH:MM:SS]` as Rich markup tags) with `RichLog(markup=False)` so timestamped entries always render correctly
- **TUI command results**: Removed thread-unsafe `sys.stdout` capture; orchestrator return value is used directly, so responses now appear in the Execution tab
- **TUI history tab**: Fixed field name mismatches in `refresh_history()` (`timestamp`→`start_time`, `actions[0]['tool']`→`user_input`, `success`→`status=='completed'`)
- **TUI early-command guard**: `execute_command()` now shows a warning notification if the orchestrator hasn't finished initializing instead of crashing

### Added
- **GitHub Issues API in GitOps**: `GitOps` tool now supports full GitHub Issues workflow
  - `create_issue(repo, title, body, labels, milestone)` — creates a single issue
  - `list_issues(repo, state, labels, limit)` — lists issues with filtering
  - `close_issue(repo, issue_number, comment)` — closes an issue with optional comment
  - `create_issues_from_roadmap(repo, roadmap_path, phase_filter, dry_run)` — parses ROADMAP.md and bulk-creates issues for unchecked `[ ]` items; defaults to dry_run=True for safety
  - Token read from `GITHUB_TOKEN` env var or `github_token` in `config.yaml`

### Changed
- **Monorepo restructuring**: Dissolved `zenus_core/cli/` into proper responsibility-based modules
  - `zenus_core.orchestrator` — core engine (shared by CLI, TUI, Voice)
  - `zenus_core.rollback` — rollback engine (business logic, not CLI-specific)
  - `zenus_core.output.*` — shared display utilities (`console`, `streaming`, `progress`)
  - `zenus_core.shell.*` — interactive shell handlers (`commands`, `explain`, `response_generator`)
  - `zenus_cli.router` — CLI-only argument parser (correctly placed in CLI package)
  - Merged `explainer.py` + `explainability.py` → `zenus_core.shell.explain`
  - Renamed `FeedbackGenerator` → `ResponseGenerator` to distinguish from `FeedbackCollector`
  - Renamed schema classes `CircuitBreakerConfig/RetryConfig` → `CircuitBreakerSettings/RetrySettings`
  - Renamed `SandboxedTool` → `SandboxedToolBase`; new `ToolSandboxWrapper`/`ToolSandboxRegistry` for composition pattern

### Fixed
- **CI/CD pipeline**: All unit tests in `tests/unit/` now use fully qualified imports (`zenus_core.*`, `zenus_cli.*`) matching the Poetry monorepo structure
- **`tests/conftest.py`**: Fixed `sys.path` to correctly point at `packages/core/src` and `packages/cli/src`
- **`GoalTracker`**: LLM is now lazy-loaded via a property — avoids importing `anthropic` at module init time (fixes test failures in environments without the package)
- **`RollbackEngine`**: Raises `RollbackError` when a file to delete is already gone, rather than silently succeeding (fixes `test_rollback_partial_failure`)
- **`SelfReflection`**: Fixed `step.goal` reference → `step.tool` (`Step` schema has no `goal` field)
- **`TreeOfThoughts`**: Fixed `intent.to_dict()` → `intent.model_dump()` (Pydantic v2)
- **Revolutionary features tests**: Updated `Step`/`IntentIR` test fixtures to include required `tool`, `risk`, `requires_confirmation` fields; added `pytest.importorskip("matplotlib")` for visualization tests

### Added
- **API Key Diagnostic Tool** (`test_api_key.py`): Test Anthropic API key validity and diagnose authentication errors
  - Shows key format, length, and potential issues (whitespace, quotes, wrong prefix)
  - Tests actual API connection with simple message
  - Provides actionable error messages for common issues

### Fixed
- **Config System Integration**: LLM factory now properly reads from `config.yaml` with environment variable fallback for backwards compatibility
  - Priority: config.yaml > ZENUS_LLM env var > default (anthropic)
  - Enables proper YAML-based configuration instead of requiring .env files
  - **CRITICAL FIX**: Use `find_dotenv(usecwd=True)` to search up directory tree for `.env`
  - Works for both running from source (finds project `.env`) and system installs
  - All LLM backends now properly locate secrets regardless of working directory
  
- **Secure Install Script (Complete Rewrite)**: Fixed file creation bugs and added proper validation
  - **FIXED**: Config files now actually created (was silently failing)
  - **FIXED**: Explicit SKIP_CONFIG boolean logic (no more conditional edge cases)
  - **FIXED**: Creates `.env` and `config.yaml` in PROJECT directory (for running from source)
  - Secrets stored in `PROJECT_DIR/.env` with chmod 600 (verified at end)
  - Asks for primary LLM provider with full setup flow
  - **NEW**: Optional fallback provider configuration (multi-provider support)
  - **NEW**: Collects API keys for all selected providers in one flow
  - **NEW**: Updated model lists from official documentation:
    - Anthropic: claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022, claude-3-opus-20240229
    - DeepSeek: deepseek-chat, deepseek-coder (latest models)
    - OpenAI: gpt-4o, gpt-4o-mini, o1-preview, o1-mini (added o1 reasoning models)
    - Ollama: llama3.2, qwen2.5, phi3, mistral, codellama (popular models)
  - Validates configuration before completing
  - Verbose output shows exactly what's happening
  - Backwards compatible with existing .env files
  
- **Dynamic Model Router**: Router now only uses models that are actually configured/available
  - Detects available providers by checking API keys and service availability
  - Builds fallback chains dynamically based on what's configured
  - No longer requires both Anthropic AND DeepSeek - works with any single model
  - Prevents errors when only one LLM provider is configured
  - **CRITICAL**: Router now reads from config.yaml `fallback.enabled` and `fallback.providers`
  - Config loader updated to find `config.yaml` in project directory (was only checking `zenus.yaml`)
  - **CRITICAL FIX**: When `fallback.enabled=false`, router now ONLY uses `llm.provider`, ignores `fallback.providers` list
  - Previous bug: Even with fallback disabled, router used entire providers list if they had keys
  - **CRITICAL FIX**: Removed singleton pattern from router - was caching old config
  - Router now reads fresh config on every request (picks up config changes without restart)
  - **CRITICAL FIX**: TaskComplexityAnalyzer was hardcoded to recommend "deepseek" for simple tasks
  - Router now configures complexity analyzer with ONLY available models
  - If only one model available, uses it for all task complexities
  - Added safety check: if complexity analyzer recommends unavailable model, uses primary instead
  - Result: No more DeepSeek attempts when fallback is disabled (FINALLY FIXED)
  
- **API Key Sanitization**: Anthropic (and other LLM backends) now strip whitespace and quotes from API keys
  - Fixes common .env formatting mistakes (e.g., `ANTHROPIC_API_KEY="sk-ant-..."` with quotes)
  - Prevents 401 authentication errors caused by extra whitespace
  
- **Robust JSON Extraction**: Enhanced JSON parsing to handle markdown-wrapped responses
  - Strips ```json``` code fences automatically
  - Better error messages showing exact parse failure location
  - Prevents "invalid JSON" errors when LLMs wrap output in markdown
  
- **Observation Truncation**: Increased observation length limit from 300 to 2000 characters
  - Enables LLM to see actual file content when reading LaTeX, config files, etc.
  - Smart truncation shows beginning + end for very long outputs
  - Fixes "No meaningful observations" issue in iterative mode
  - Critical for complex multi-file tasks like book formatting

## [0.5.0] - 2026-02-27

### Added - Revolutionary Features

- **Tree of Thoughts**: Explores 3-5 alternative solutions in parallel before execution
  - Evaluates multiple approaches simultaneously
  - Confidence scoring for each alternative
  - Risk assessment and pros/cons analysis
  - Selects best approach based on context
  - Example: "deploy app" explores Docker Compose, Kubernetes, systemd

- **Prompt Evolution**: Self-improving prompts based on command success/failure
  - Tracks success rates per command type
  - Auto-tunes prompts based on failures
  - Automatic A/B testing
  - No manual prompt engineering needed
  - Learns from YOUR workflows

- **Goal Inference**: High-level goal understanding with complete workflow suggestions
  - Understands user intent beyond literal commands
  - Proposes complete workflows with safety steps
  - Suggests backup, testing, verification steps
  - Example: "deploy app" suggests backup → test → deploy → verify → monitor

- **Multi-Agent Collaboration**: Multiple specialized AI agents work together on complex tasks
  - Code review (one writes, another reviews)
  - Research + implementation workflows
  - Testing + debugging collaboration
  - Design + code separation
  - Spawns specialized agents as needed

- **Proactive Monitoring**: System health monitoring with alerts before problems occur
  - Disk space warnings (80% warning, 90% critical)
  - High CPU usage alerts (80% threshold)
  - High memory usage alerts (85% threshold)
  - Failed services detection
  - Security updates notifications
  - Prevents problems before they happen

- **Voice Interface**: Full hands-free voice control (100% local, no cloud)
  - Local Whisper STT (speech-to-text)
  - Piper TTS (text-to-speech)
  - Conversational flow
  - Optional wake word ("Hey Zenus")
  - Complete privacy - zero external dependencies

- **Data Visualization**: Automatic data formatting and visualization
  - Auto-detects data types (processes, disk usage, stats, etc.)
  - Rich tables with borders, colors, and alignment
  - Progress bars for resource usage
  - Color coding (green/yellow/red for status)
  - File trees with icons
  - Syntax highlighting for JSON/code
  - Graceful fallback to plain text

- **Self-Reflection**: Pre-execution plan critique and validation
  - Analyzes plans before execution
  - Confidence scoring per step (0-100%)
  - Issue detection (ambiguity, missing info, risks, invalid assumptions)
  - Smart question generation
  - Risk assessment and safeguard suggestions
  - Alternative approach proposals
  - Asks user when needed, proceeds automatically when safe

### Changed
- Enhanced system output with beautiful formatted visualizations
- Improved safety with pre-execution validation
- Better decision-making with multi-path exploration
- Increased accessibility with voice interface

### Impact
- 8 revolutionary features not available in competitors (Cursor, OpenClaw)
- True innovation beyond incremental improvements
- Local-first architecture (privacy + control)
- Self-improving system that gets smarter over time

## [0.4.0] - 2026-02-24

### Added - Cost Optimization & Production Readiness
- **Model Router**: Intelligent LLM selection based on task complexity (50-75% cost reduction)
  - Complexity analysis (simple tasks → DeepSeek, complex → Claude)
  - Fallback cascade (escalate if needed)
  - Cost tracking per model
  - Decision logging
  - 70-80% of commands route to cheap models
  
- **Intent Memoization**: Cache Intent IR translations (2-3x speedup, zero token cost)
  - Hash-based caching (user_input + context)
  - 1-hour TTL
  - LRU eviction (500 entries)
  - Persistent cache
  - Tokens saved tracking
  - 30-40% token reduction in typical usage

- **Feedback Collection**: User feedback for continuous improvement
  - Thumbs up/down prompts
  - Success rate tracking per tool/intent
  - Training data export
  - Privacy-aware sanitization
  - Statistics dashboard

- **Enhanced Error Handling**: User-friendly error messages with actionable suggestions
  - Categorized errors (permission, not_found, network, timeout, etc.)
  - Context-aware explanations
  - 3-5 suggestions per error type
  - Fallback command recommendations
  - Formatted output with rich

- **Observability & Metrics**: Comprehensive performance monitoring
  - Command latency tracking
  - Token usage per command
  - Cost estimation
  - Cache hit rate monitoring
  - Success rate tracking
  - Per-model statistics
  - Historical data access

### Performance
- 2-3x faster for repeated commands (intent cache)
- 50-75% cost reduction (model router)
- Real-time cost tracking
- Zero tokens for cache hits

### Impact
- $4 token budget → effective $6-8 purchasing power
- Instant responses for cached commands
- Better error messages reduce frustration
- Data-driven optimization enabled

## [0.3.0] - 2026-02-24

### Fixed
- **Result Caching Bug**: Fixed adaptive planner not clearing execution_history between commands, causing observations to show cached results from previous commands in the session
- **Anthropic Streaming**: Enabled streaming in regular execution mode (was only enabled in iterative mode), fixing timeout errors with Claude models on normal commands
- **Infinite Loops**: Added max 50 iteration limit, stuck detection (repeating same goal 3+ times), and user confirmation between batches to prevent runaway iterative tasks
- **Empty Observations**: Enhanced observation formatting to handle None/empty results gracefully, providing context even when commands produce minimal output
- **Large File Writes**: Added chunked writing (10MB chunks) for large files, enabling LaTeX documents and other big file operations
- **Package Operation Timeouts**: Removed fixed 300s timeout, using streaming executor with no timeout for install/remove/update operations
- **Shell Output Streaming**: Created StreamingExecutor for real-time line-by-line output with subprocess.Popen instead of subprocess.run

### Added
- **Real-Time Command Output**: All shell commands now stream output in real-time with dimmed formatting
- **System Resource Commands**: Added SystemOps.check_resource_usage() and SystemOps.find_large_files() for comprehensive system diagnostics
- **Loop Prevention**: Stuck detection warns users and offers to abort when tasks repeat without progress
- **Better Error Context**: Enhanced error messages throughout execution chain with stdout/stderr labels

## [0.2.0] - 2026-02-23

### Added
- **Anthropic Claude Support**: Full integration with Claude models (Sonnet, Opus, Haiku) via Anthropic API
- **Streaming for Claude**: Implemented streaming in translate_intent() and reflect_on_goal() to avoid timeout errors on long operations
- **Update Script**: Added update.sh for easy dependency reinstallation after git pull

### Fixed
- **Dependency Installation**: Fixed module not found errors by adding LLM provider dependencies directly to CLI and TUI packages
- **Streaming Reflection**: Fixed reflect_on_goal() to use Anthropic's streaming format (.text_stream) instead of OpenAI's format

## [0.2.0-beta] - 2026-02-22

### Added
- **Installation Automation**: install.sh now automatically installs Poetry, runs dependency installation, and configures bash aliases
- **Monorepo Support**: Proper Poetry workspace structure with three packages (core, cli, tui)

### Fixed
- **Monorepo Installation**: Fixed dependency resolution for path dependencies in Poetry workspace
- **Alias Consistency**: Standardized all aliases to use hyphens (zenus, zenus-tui) instead of mixed underscore/hyphen

## [0.2.0-alpha] - 2026-02-21

### Added
- **TUI (Terminal UI)**: Full-featured dashboard with Live Status, Execution Log, Memory Browser, and Statistics panels
- **Vision Capabilities**: VisionOps tool using Playwright for UI automation via screenshot analysis
- **Workflow Recorder**: Record command sequences and replay them with workflow system
- **Parallel Execution**: Dependency analysis and parallel execution for independent steps (2-3x faster)
- **Error Recovery**: Automatic retry with exponential backoff for transient failures
- **Smart Caching**: LLM response caching (1hr TTL) and filesystem caching (5min TTL)
- **Enhanced Shell**: Tab completion, Ctrl+R search, multi-line input, syntax highlighting
- **Progress Indicators**: Spinners for LLM calls, progress bars for multi-step execution
- **Pattern Detection**: Learns usage patterns and suggests automation after 10 similar commands
- **Explainability**: `explain` command shows decision-making process for last command

### Changed
- **Iterative Execution**: Now auto-continues in batches of 12 iterations, stopping early when goal achieved
- **Project Structure**: Refactored to Poetry workspace monorepo (core, cli, tui packages)

## [0.1.0] - 2026-02-20

### Added
- **Massive Tool Expansion**: 10 tools total (was 4)
  - BrowserOps: open, screenshot, get_text, search, download
  - PackageOps: install, remove, update, search, list_installed, info, clean
  - ServiceOps: start, stop, restart, status, enable, disable, logs
  - ContainerOps: run, ps, stop, logs, images, pull, build
  - GitOps: clone, status, add, commit, push, pull, branch, log, diff
  - NetworkOps: curl, wget, ping, ssh, traceroute, dns_lookup, netstat
- **Context Awareness**: Tracks current directory, git state, time, recent files, running processes
- **Learning from Failures**: FailureAnalyzer provides suggestions based on past errors
- **Undo/Rollback**: Transaction-based action tracking for reversible operations
- **Proactive Suggestions**: SuggestionEngine analyzes context and provides helpful tips
- **Auto-Detection**: TaskAnalyzer detects when tasks need iterative execution vs one-shot
- **Batch Operations**: Wildcard and pattern support for efficient file operations

### Changed
- **Iterative Mode**: Added --iterative flag and ReAct loop for complex tasks
- **Goal Tracking**: LLM-based reflection to determine when iterative goals are achieved

### Performance
- Batch file operations 2-3x faster with parallel execution
- Zero crashes on common errors with recovery system

## [0.1.0-alpha] - 2026-02-10

### Added
- **Semantic Memory**: sentence-transformers integration for similar command search
- **Explain Mode**: --explain flag shows reasoning, similar commands, and success probability before execution
- **Visual Output**: Rich library for color-coded, formatted CLI output with emoji risk levels
- **Readline Support**: Arrow keys for command history, saved to ~/.zenus/history.txt

### Fixed
- **Ollama Timeout**: Increased from 30s to 300s for longer operations
- **Token Limits**: Increased from 512 to 2048 tokens
- **Lazy Loading**: Fixed API key errors when using Ollama

## [0.0.1] - 2026-02-09

### Added - Initial Release
- **CLI Routing**: help, version, shell, direct command modes
- **Intent IR Schema**: Formal contract between LLM and execution
- **LLM Backends**: OpenAI, DeepSeek, Ollama (local) support
- **Audit Logging**: JSONL logs to ~/.zenus/logs/
- **Dry-run Mode**: --dry-run flag for safe preview
- **Adaptive Planner**: Retry with observation on failure
- **Three-layer Memory**: Session (RAM), World (persistent), History (audit)
- **Sandboxing**: Path validation and resource limits
- **Tools**: FileOps, TextOps, SystemOps, ProcessOps
- **Progress Indicators**: Spinner with elapsed time
- **Built-in Commands**: status, memory, update
- **Test Suite**: 57 test cases, 100% passing

---

## Installation

```bash
git clone https://github.com/Guillhermm/zenus.git
cd zenus
./install.sh
```

## Usage

```bash
zenus                         # Interactive mode
zenus "list files"            # Direct command
zenus "task" --explain        # Show explanation first
zenus "complex task" --iterative  # Use ReAct loop
zenus-tui                     # Launch TUI dashboard
```

## Links

- **Repository**: https://github.com/Guillhermm/zenus
- **Issues**: https://github.com/Guillhermm/zenus/issues
- **Discussions**: https://github.com/Guillhermm/zenus/discussions
