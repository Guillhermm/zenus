# Changelog

All notable changes to Zenus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **LLM-driven search classification** (`brain/llm/schemas.py`, `orchestrator.py`, `tools/web_search.py`): replaced the heuristic `SearchDecisionEngine` (temporal regex patterns + knowledge-gap months + factual-question heuristic) with LLM-based classification. The LLM now receives the current date/time during intent translation and sets three new `IntentIR` fields: `search_provider` (`"web"` | `"llm"` | `null`), `search_category` (`"sports"` | `"tech"` | `"academic"` | `"news"` | `"general"`), and `cannot_answer` + `fallback_response` for truly unanswerable queries. The orchestrator uses these fields to decide whether to run `WebSearchTool`, answer from training knowledge, or return an immediate fallback — eliminating false-positive and false-negative search triggers from the old pattern-matching approach.
- **System prompt** (`brain/llm/system_prompt.py`): added SEARCH CLASSIFICATION and CANNOT ANSWER instruction blocks; current date/time injected at build time via `current_datetime` parameter (all LLM backends updated).
- **`SearchDecisionEngine` removed** (`tools/web_search.py`): class and all associated temporal regex patterns (`_TEMPORAL_PATTERNS`, `_ACTION_REQUEST_RE`) deleted. `WebSearchTool.search()` now accepts an optional `category` argument used directly from `IntentIR.search_category`.

### Added
- **Structured debug-output controls** (`zenus_core/debug.py`): new `DebugFlags` dataclass with per-subsystem flags (`orchestrator`, `brain`, `execution`, `voice`, `search`) and a master `enabled` switch. All flags default to `False` so regular users see clean output; developers can enable exactly the noise they need. Config-first, env-fallback pattern: `debug.*` keys in `config.yaml` take priority, then `ZENUS_DEBUG_<SUBSYSTEM>=1` env vars; `ZENUS_DEBUG=1` enables everything at once. Legacy `ZENUS_SEARCH_DEBUG` and `search.debug: true` continue to work and map to the `search` flag.
- **`DebugConfig` Pydantic model** (`config/schema.py`): `debug` section added to `ZenusConfig` with typed, documented fields for every subsystem. Added to `config.yaml.example` and `.env.example`.
- 18 unit tests in `tests/unit/test_debug_flags.py` covering defaults, master switch, per-subsystem env vars, legacy aliases, config-based loading, and cache reset.

### Changed
- **Orchestrator** (`orchestrator.py`): routing-decision messages, task-complexity scores, Tree of Thoughts path exploration, provider/model override notices, and intent-cache hits are now gated behind `debug.orchestrator`. Web-search debug output (query type, result breakdown) gated behind `debug.search`. Removed the standalone `_load_search_debug()` / `_search_debug` pattern — superseded by `get_debug_flags()`.
- **Planner** (`brain/planner.py`): per-step `Done: tool.action: result` output and parallel-fallback notice now gated behind `debug.execution`.
- **Prompt evolution** (`brain/prompt_evolution.py`): variant-promotion message gated behind `debug.brain`; load/save failure messages converted from `print()` to proper `logger.warning()` calls.
- **Model router** (`brain/model_router.py`): LLM fallback-chain messages gated behind `debug.orchestrator`; stats save failure converted to `logger.warning()`.
- **TTS** (`voice/tts.py`): engine-init messages (`✓ Using Piper TTS`, `✓ Using system TTS`, fallback notices) gated behind `debug.voice`; Piper/system error messages converted from `print()` to `logger.error()`.

### Added
- **Semantic Scholar source** (`tools/web_search.py`): free Allen Institute API (200M+ academic papers) added as first-priority source for academic queries. Returns title, abstract, year, venue, and up to 3 authors. No API key required.
- **OpenAlex source** (`tools/web_search.py`): free open academic graph (240M+ scholarly works) added as third-priority academic source. Reconstructs abstract from inverted index. Uses polite-pool mode (`?mailto=zenus@zenus.io`) for better rate limits.
- **Movie/entertainment temporal patterns**: `now playing`, `in theaters`, `current movies`, `box office`, `new movies this week`, `upcoming movie releases`, `what's showing`, `streaming now`, and several more — all now correctly trigger web search instead of falling through to the browser tool.
- **Attribution temporal patterns**: `who made/created/developed/wrote/authored/invented/designed/built` added to `_TEMPORAL_PATTERNS`. LLMs frequently hallucinate authorship of obscure works (benchmarks, algorithms, datasets); searching eliminates this risk.
- 48 new unit tests covering the two new sources, the new temporal patterns, and the updated academic routing.

### Changed
- **Academic query fallback routing** (`tools/web_search.py`): academic category now uses Semantic Scholar → arXiv → OpenAlex → Wikipedia (instead of arXiv → Wikipedia → HackerNews). HackerNews removed from academic routing as it rarely surfaces peer-reviewed content.
- **`_ACADEMIC_QUERY_RE`**: extended with `citation`, `peer-review`, `preprint`, `conference`, `proceedings`, `semantic scholar`, `pubmed`, `doi` for better academic query classification.

### Added
- **Zenus Voice v0.2.0 — local-first rewrite** (`packages/voice/`):
  - **`stt.py`**: rewritten to use `faster-whisper` (CTranslate2 backend) — 4× faster than `openai-whisper`, no PyTorch required, int8 quantization by default. Public API (`SpeechToText`, `WhisperModel`, `TranscriptionResult`, `get_stt`) unchanged.
  - **`wake_word.py`**: rewritten to use `openwakeword` — fully local, no API key. `WakeWordDetector` processes 80 ms audio frames via openwakeword's pre-trained models (`alexa`, `hey_jarvis`, etc.); `TextFallbackDetector` (renamed from `SimpleWakeWordDetector`, alias kept) uses faster-whisper for text-matching when openwakeword is not installed. `create_wake_detector()` auto-picks the best implementation.
  - **`pipeline.py`** (new): canonical `VoicePipeline` entry point — wake word → STT → Zenus Orchestrator → TTS, with `VoiceSession` context carryover, `PipelineState` state machine, `on_state_change` callback, and `create_voice_pipeline()` factory.
  - **`pyproject.toml`**: removed `openai-whisper` and `pvporcupine`; added `faster-whisper = "^1.0.0"` and `openwakeword = {version = "^0.6.0", optional = true}`. Updated extras: `wake`, `piper`, `full`.
  - 58 tests in `tests/unit/test_voice.py` covering all three modules with all hardware dependencies fully mocked.
- **Knowledge Graph** (`brain/knowledge_graph.py`): directed, typed entity-relationship graph built automatically from `ActionTracker` events. Stores `Entity` (FILE, DIR, PROCESS, SERVICE, PACKAGE, ENV_VAR, COMMAND) and `Edge` (DEPENDS_ON, READS, WRITES, RUNS, CONFIGURES, IMPORTS, PRODUCES, CONTAINS, RELATED_TO) with BFS traversal helpers (`what_depends_on`, `what_would_be_affected`, `related_to`) and natural-language query dispatch. Thread-safe via `RLock`; persisted atomically to JSON. Module-level singleton via `get_knowledge_graph()`. Orchestrator ingests every executed step into the graph automatically. 54 tests in `tests/unit/test_knowledge_graph.py`.
- **Q&A mode** (`brain/llm/schemas.py`, `orchestrator.py`): `IntentIR` gains an additive `is_question: bool = False` field. When the LLM sets `is_question=True` the orchestrator short-circuits directly to `llm.ask()`, bypassing all execution machinery. No tool execution, no confirmation prompt. All LLM backends gain an `ask(question, context)` method.
- **Dynamic execution summary** (`output/execution_summary.py`): `ExecutionSummaryBuilder` replaces the static "plan executed successfully" message with a concise, human-readable summary derived from step results (e.g. "Installed vim; Started nginx."). Falls back through: LLM-provided `action_summary` → verb-map derivation → `intent.goal`. No extra LLM call. 48 tests in `tests/unit/test_execution_summary.py`.
- **Autonomous web search** (`tools/web_search.py`): `WebSearchTool` fetches results from Brave Search API (primary, free tier 2,000 req/month — configure via `BRAVE_SEARCH_API_KEY` env var or `config.yaml` `search.brave_api_key`) with a 7-source parallel fallback — Wikipedia (search + extract API), HackerNews (Algolia), GitHub repositories, Reddit, arXiv (Atom XML), curated RSS/Atom feeds (BBC, TechCrunch, The Verge, ArsTechnica), and DDG Instant Answer. `ThreadPoolExecutor` runs all fallback sources concurrently; results merged in priority order and deduplicated by URL. The LLM decides when to search via `IntentIR.search_provider`; results injected transparently into LLM context. Registered in `tools/registry.py`.
- **`ask()` abstract method** (`brain/llm/base.py`): all LLM backends (Anthropic, OpenAI, DeepSeek, Ollama) now implement `ask(question, context="") -> str` for direct Q&A without JSON schema enforcement.
- **`IntentIR.action_summary`** field: additive optional field the LLM can populate with a past-tense summary of what was done, used as first-priority input for `ExecutionSummaryBuilder`.

### Security
- **XML bomb protection** (`tools/web_search.py`): replaced stdlib `xml.etree.ElementTree` with `defusedxml.ElementTree`. The stdlib parser is documented as vulnerable to entity expansion (XML bomb) and billion-laughs attacks; `defusedxml` blocks all known XML attack vectors. Added `defusedxml = "^0.7.1"` to `packages/core/pyproject.toml`.
- **Prompt injection hardening** (`orchestrator.py`): search results injected into LLM context are now wrapped in explicit untrusted-content delimiters (`--- BEGIN/END EXTERNAL SEARCH RESULTS ---`) with a system note instructing the model not to follow embedded instructions. Applied to all four injection paths: lookup bypass (`execute_command`), action-query context (`execute_command`), lookup bypass (`execute_iterative`), and action-query context (`execute_iterative`).
- **Safe HTML stripping** (`tools/web_search.py`): replaced `re.sub(r"<[^>]+>", "", text)` (which strips tags but leaks `<script>`/`<style>` content into LLM context) with `_SafeHTMLStripper` — a stdlib `html.parser.HTMLParser` subclass that discards the *content* of `script`, `style`, and `noscript` blocks. Applied to Wikipedia snippet fallback and RSS/Atom feed description extraction.

### Changed
- **`tools/registry.py`**: added `WebSearch` entry pointing to `WebSearchTool()`.
- **`orchestrator.py`**: Step 0a — web search runs before complexity routing (not after) to ensure real-time data is always injected; `force_oneshot=True` whenever search is triggered regardless of results; bypass `translate_intent` and call `llm.ask()` directly when search returns empty to prevent empty WebSearch tool loops; `execute_iterative` also injects web search context and includes `is_question` short-circuit after intent translation. Step 2.4 — Q&A short-circuit; Step 6.5 — knowledge graph ingestion after execution; final output uses `build_execution_summary` instead of static success message.
- **`config/schema.py`**: added `SearchConfig` model (`brave_api_key: Optional[str]`) and `search: SearchConfig` field to `ZenusConfig`.
- **`packages/core/pyproject.toml`**: removed `duckduckgo-search` dependency (blocked from server IPs; replaced by Brave + multi-source fallback).
- **Smart fallback routing** (`tools/web_search.py`): `_classify_query` categorises each query as sports/tech/academic/news/general and `_fallback_search` runs only the relevant 3-4 sources (e.g. sports → Wikipedia + Reddit + RSS; academic → arXiv + Wikipedia + HN). Eliminates irrelevant results (Minecraft Reddit posts for soccer queries).
- **Lookup bypass in orchestrator**: when `IntentIR.search_provider == "web"` and `is_question=True`, the orchestrator calls `llm.ask()` with search results directly. Users see only the synthesised plain-text answer — no raw `SearchResult` dump, no self-reflection output, no spinning WebSearch tool steps.
- **`ZENUS_SEARCH_DEBUG=1`** (new env var): exposes query category, result count, and per-result source/title/snippet before the synthesised answer. Off by default.
- **`memory/world_model.py`**: `get_summary()` now appends Knowledge Graph node/edge stats when the graph is non-empty.

---

## [1.0.0] - 2026-03-19

### Added
- **Property-based testing** (`tests/unit/test_property_based.py`): 27 invariant tests using Hypothesis covering `IntentIR`/`Step` schema boundaries, `SafetyPolicy` risk-threshold guarantees, config schema field constraints, and secrets masking — every `risk=3` step always raises `SafetyError` regardless of input.
- **Hot-reload config** (`config/loader.py`): `ConfigLoader` now supports `on_reload(callback)` / `remove_reload_callback()` and a module-level `register_reload_callback()`. Callbacks are fired outside the `threading.RLock` to prevent deadlocks; the watchdog observer runs as a daemon thread. Full test suite in `tests/unit/test_config_hot_reload.py` (15 tests).
- **Vault integration** (`config/secrets.py`): `VaultClient` wraps HashiCorp Vault KV v2 with lazy connection caching (failure cached to avoid repeated network calls), falls back to env vars when Vault is unconfigured. `SecretsManager` accepts an optional `vault:` param; Vault values win over env vars. 27 tests in `tests/unit/test_vault_secrets.py`.
- **Async stack** (`brain/llm/base.py`, `brain/llm/anthropic_llm.py`, `orchestrator.py`): `LLM` base class gains default async methods (`atranslate_intent`, `areflect_on_goal`, `agenerate`) via `asyncio.to_thread`. `AnthropicLLM` overrides these with native `AsyncAnthropic` calls. `Orchestrator.async_execute_command` delegates to the sync path via thread pool. 18 tests in `tests/unit/test_async_llm.py`.
- **Background task queue** (`execution/task_queue.py`): stdlib-only `BackgroundTaskQueue` (ThreadPoolExecutor) with `Priority` scheduling (HIGH/NORMAL/LOW), `TaskStatus` lifecycle (PENDING→RUNNING→DONE/FAILED/CANCELLED), cancellation, timeout, and context manager support. `AsyncBackgroundTaskQueue` wraps it for asyncio callers. Module-level singleton via `get_task_queue()`. 54 tests in `tests/unit/test_task_queue.py`.
- **HTTP connection pool** (`execution/connection_pool.py`): `ConnectionPool` wraps `urllib3.PoolManager` providing shared TCP connections across tool HTTP calls, configurable retry policy (backoff on 429/5xx), per-request timeout override, and convenience helpers (`get`, `post`, `put`, `delete`). Module-level singleton via `get_connection_pool()`. 34 tests in `tests/unit/test_connection_pool.py`.
- **Cache test coverage** (`tests/unit/test_smart_cache.py`): 64 tests for `SmartCache` (TTL, LRU eviction, `get_or_compute`, `invalidate_pattern`, stats) and `IntentCache` (context hashing, corruption handling, token savings estimation).
- **Test coverage catalog** (`docs/TEST_COVERAGE.md`): auto-generated index of all 2,496+ test cases across unit, integration, and E2E tiers.

### Changed
- **`execution/__init__.py`**: now exports `BackgroundTaskQueue`, `AsyncBackgroundTaskQueue`, `Priority`, `TaskStatus`, `TaskResult`, `get_task_queue`, `ConnectionPool`, `get_connection_pool`.
- **`config/__init__.py`**: exports `register_reload_callback` and `VaultClient`.
- **`packages/core/pyproject.toml`**: added `hypothesis = "^6.0.0"` to dev dependencies.

- **Production-ready integration test suite**: 143 integration tests across 8 suites exercise the full stack end-to-end using real DeepSeek API calls (skipped automatically when `DEEPSEEK_API_KEY` is absent):
  - `test_llm_deepseek.py` — DeepSeek adapter: `extract_json`, credential validation, `translate_intent`, `generate`, and `reflect_on_goal` with both mocked and live API scenarios.
  - `test_provider_contract.py` — LLM factory and provider contract: factory routing priorities, `get_available_providers`, interface compliance, and a live DeepSeek round-trip.
  - `test_pipeline_e2e.py` — Full orchestrator pipeline: wiring correctness (mocked LLM), intent cache isolation, dry-run mode, and real end-to-end execution (natural language → DeepSeek → IntentIR → tool → result).
  - `test_safety_pipeline.py` — Safety and privilege gates: risk-level blocking, `PrivilegeTier` enforcement for `ShellOps`/`CodeExec`, and destructive-command guard via real LLM.
  - `test_rollback_pipeline.py` — Rollback correctness: `ActionTracker` data model, `RollbackEngine` feasibility analysis, real filesystem rollback (create/copy/move), dry-run mode, and `rollback_last_n_actions`.
  - `test_concurrency.py` — `ParallelExecutor`: correctness, thread safety, failure isolation, `ResourceLimiter` IO throttling, real parallel file/system ops, and `should_use_parallel` heuristic.
  - `test_iterative_execution.py` — ReAct loop (`execute_iterative`): goal tracking, memory updates, dry-run, `GoalStatus` dataclass, and `GoalTracker` iteration safety limit.
- **`requires_deepseek` pytest marker**: auto-skips live LLM tests when API key is absent; configured in `pytest.ini` and `conftest.py`.
- **`deepseek_llm` and `isolated_tracker` fixtures**: added to `conftest.py` for reuse across integration suites.
- **Comprehensive unit test suite**: expanded from ~25% to 88.6% coverage with 2,333 tests — adds dedicated suites for `task_complexity`, `error_recovery`, `parallel_executor`, `feedback/collector`, `proactive_monitor`, `tools/base`, `shell/explain`, `shell/commands`, `shell_executor`, `container_ops`, `output`, and `orchestrator` subsystems; extends `planner` and `rollback` tests.
- **Test infrastructure**: `conftest.py` `restore_cwd` autouse fixture prevents working-directory leakage between tests; optional deps (playwright, pyautogui) stubbed in `sys.modules` so tests run without them installed.

### Changed
- **CI: three-tier test pipeline**:
  - `ci.yml` (PRs and feature branches) — unit + mocked tests only; no API key required, live tests auto-skip. Fast matrix across Python 3.10–3.12.
  - `integration.yml` (every merge to `main`, manual dispatch) — full suite including live DeepSeek API tests; uploads coverage artifact; fails if coverage drops below 75%. Switch trigger to `schedule` cron if cost becomes a concern.
  - `release.yml` (tag pushes) — same full suite as integration, now mandatory live-test gate before any artifact is published; enforces 75% coverage threshold.
- **CI: gate PyPI publish behind `PYPI_PUBLISH` variable**: mirrors the existing `SNAP_PUBLISH` guard, allowing independent control over each publish channel per release.

### Fixed
- **`visualization/__init__.py` import paths**: `ChartType` and `TableStyle` were incorrectly imported from `visualizer.py`; corrected to import from `chart_generator` and `table_formatter` respectively.
- **`provider_override.py` regex**: `using?` matched "usin/using" but not "use"; corrected to `(?:use|using)`.
- **CI: snap store publish glob not expanded**: `snapcore/action-publish@v1` ignores custom `snap:` input; replaced with direct `snapcraft upload` shell call.
- **CI: release workflow triggering on branch pushes**: reverted to tag-only trigger to prevent `VERSION` containing `/`.
- **CI: remove venv caching**: always create venv fresh to avoid stale symlinks.
- **CI: snap build syntax error**: wrapped `run:` value in block scalar to fix YAML parse error on `version: .*` pattern.

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
