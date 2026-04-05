# Zenus Roadmap

**Vision**: An operating system driven by intent, not commands.

This roadmap outlines planned improvements across all phases of Zenus development — from the current system layer to the long-term goal of Zenus becoming a full operating system. All ideas are aspirational; implementation priority is determined by impact and feasibility.

Dates are stated as **maximum targets**, not promises. Phase 1 was originally scheduled for Q2 2026 and was completed in March 2026 — earlier phases can shift later ones earlier, but we do not adjust remaining targets optimistically until work is underway.

---

## Phase 1: Foundation Hardening ✅ — Completed March 2026

### 1.1 Reliability & Production Readiness

- [x] **Comprehensive Error Handling** ✅ (v0.5.0)
  - Graceful degradation for all failure modes
  - Automatic fallback strategies (LLM → simpler LLM → rule-based)
  - Circuit breakers for external services
  - Retry budget system to prevent infinite retries

- [x] **Testing Infrastructure** ✅ (v1.0.0)
  - Integration tests for all tools
  - E2E tests for common workflows
  - Property-based testing for intent translation (Hypothesis, 27 invariant tests)
  - Fuzzing for safety policy (risk=3 always blocks)
  - CI/CD with automated test suite
  - Coverage: 88.6%+

- [x] **Observability** ✅ (v0.4.0)
  - Performance metrics (latency, token usage, success rate)
  - Real-time statistics
  - Cost tracking and per-model breakdown
  - Historical data access

- [x] **Configuration Management** ✅ (v1.0.0)
  - YAML config files with schema validation
  - Hot-reload without restart (watchdog + callback observer pattern)
  - Profile system (dev, staging, production)
  - Secrets management (env/.env + HashiCorp Vault KV v2)

### 1.2 Performance Optimization

- [x] **Caching Strategy** ✅ (v0.4.0 + v1.0.0)
  - Intent memoization (hash → plan) with LRU eviction and 1-hour TTL
  - LLM response streaming
  - SmartCache with disk persistence

- [x] **Concurrency** ✅ (v1.0.0)
  - Async/await throughout the stack (LLM base class, AnthropicLLM, Orchestrator)
  - Non-blocking I/O for LLM calls (AsyncAnthropic native client)
  - True parallel execution (ParallelExecutor with dependency analysis)
  - Background task queue (stdlib ThreadPoolExecutor, Priority scheduling, no broker needed)

- [x] **Resource Management** ✅ (v1.0.0)
  - In-memory LRU caching with disk persistence
  - HTTP connection pooling (urllib3 PoolManager, shared per process)
  - Rate limiting and backpressure (retry budget + circuit breaker)
  - Graceful shutdown handling

---

## Phase 1.5: Pre-Launch Hardening — target: by June 2026

These items were identified before the first public release. All are prerequisite to promoting Zenus broadly: they close known gaps, harden security, and improve interoperability with the current AI tooling ecosystem.

### 1.5.1 Security Audit & Hardening

- [x] **OWASP Top-10 audit** ✅ (`zenus_core/` full sweep — v1.1.0)
  - A01 Broken Access Control: privilege tiers reviewed; path traversal closed via `Path.resolve()`
  - A03 Injection: URL scheme validation in NetworkOps; temp-file permissions hardened in CodeExec
  - A08 Software & Data Integrity: `enforce_confirmation_policy()` ensures risk≥2 always requires confirmation
  - A09 Logging & Monitoring: secret masking in audit logs and intent history; owner-only file permissions
  - GitHub token restricted to env-only (no config.yaml fallback)
  - 30 regression tests in `tests/unit/test_security.py`

### 1.5.2 MCP (Model Context Protocol) Support

- [x] **MCP server mode** ✅ (`zenus_core/mcp/server.py` — v1.2.0)
  - `FastMCP`-based server mapping every tool action to an MCP tool descriptor
  - Tool names: `{ToolName}__{action_name}` (e.g. `FileOps__read_file`)
  - Privilege tiers enforced: privileged tools (ShellOps, CodeExec) excluded by default
  - Configurable via `mcp.server.*` in `config.yaml`; start with `zenus mcp-server`
  - Supports `stdio` transport and `sse` transport (HTTP clients)
- [x] **MCP client mode** ✅ (`zenus_core/mcp/client.py` — v1.2.0)
  - `MCPClientRegistry` discovers remote tools from external MCP servers at startup
  - Tools injected as `mcp__{server}__{tool}` into the Zenus tool registry
  - `config.yaml` `mcp.client.servers` list; `stdio` and `sse` transports supported
- [x] Updated `docs/TOOLS.md` and `docs/CONFIGURATION.md` with MCP setup guide ✅

### 1.5.3 Voice Completion

- [ ] **TTS finalization** (`packages/voice/tts.py`)
  - Piper TTS: complete streaming output (start speaking before LLM finishes)
  - Voice profile support (speed, pitch) configurable via `config.yaml`
  - Graceful fallback chain: Piper → system TTS (`espeak`) → silent
- [ ] **Conversational flow** (`packages/voice/pipeline.py`)
  - Clarifying questions mid-execution: pipeline pauses and speaks the question, waits for STT answer
  - Natural interruption: detect "stop", "cancel", "wait" during TTS playback and halt execution
  - Context carryover: pronouns and references ("do it again", "and then X") resolved against prior `VoiceSession` turns

### 1.5.4 Parallel Execution — Benchmarks & UX

- [ ] **Concrete benchmarks**: measure and document real wall-clock speedups for representative parallel workloads (batch file ops, multi-package install, concurrent git queries); publish results in `docs/PERFORMANCE.md`
- [ ] **Execution plan visualization**: before execution, show which steps will run in parallel (dependency graph rendered in the TUI and as a Rich table in CLI)
- [ ] **Parallel progress display**: when steps run concurrently, show live per-step status (running / done / failed) rather than a sequential list

---

## Phase 1.6: Agentic Harness Hardening ✅ — Completed April 2026

*Each entry is classified by **Impact** (H/M/L) and **Adaptation Difficulty** for Zenus (H/M/L)*

### 1.6.1 Hook Pipeline — PreToolUse / PostToolUse ✅ [Impact: H | Difficulty: M]

- [x] **PreToolUse hooks**: configurable shell callbacks invoked before any tool executes ✅
  - fnmatch pattern matching against `ToolName` or `ToolName.action_name`
  - Non-zero exit denies tool execution; all hook failures guarded so they never crash execution
  - Configured in `config.yaml` under `hooks.pre_tool_use[].match` + `command` + `timeout_seconds`
- [x] **PostToolUse hooks**: callbacks invoked after tool execution, run asynchronously (daemon thread) ✅
- [x] `/hooks` slash command: list all configured pre/post hooks ✅

### 1.6.2 Plan Mode ✅ [Impact: H | Difficulty: M]

- [x] **Plan-only execution mode**: proposes a rich table of steps and waits for user approval before executing ✅
  - `PlanModeManager` with `APPROVED` / `DENIED` / `BYPASSED` decisions
  - `auto_approve_low_risk`: skips prompt when all steps have risk=0
  - `/plan` slash command to toggle plan mode interactively in CLI and TUI ✅
  - Thread-safe singleton; integrated into `orchestrator.py` before `execute_plan()`

### 1.6.3 Context & Session Management ✅ [Impact: H | Difficulty: M]

- [x] **Context window compaction** (`/compact`): summarises history via LLM and replaces it with one entry ✅
  - Auto-triggered via `maybe_compact()` when token usage crosses `session.compact_threshold`
  - Fails gracefully if LLM is unavailable (history left unchanged)
- [x] **Multi-directory context** (`/add-dir`): add additional working directories to the active session ✅
- [x] **Session resume**: persist full session state to `~/.zenus/sessions/<id>.json` (chmod 600) ✅
  - `/session list/save/load/delete` shell commands; auto-prune to `max_sessions`

### 1.6.4 Background Task System ✅ [Impact: H | Difficulty: M]

- [x] **TaskOps tool**: `create`, `list`, `get`, `stop`, `output`, `purge` — full task lifecycle API ✅
  - Wraps existing `BackgroundTaskQueue`; accessible via `/tasks` command
- [x] **ScheduleOps tool**: cron job registration via `crontab`, with `# zenus-managed:<label>` sentinels ✅
- [x] **RemoteTriggerTool**: HTTP webhook trigger with URL scheme validation (http/https only) ✅

### 1.6.5 Git Worktree Support ✅ [Impact: H | Difficulty: L]

- [x] **WorktreeOps tool**: `enter(branch)`, `exit_worktree()`, `current()` — full worktree lifecycle ✅
  - `enter` calls `git worktree add` + `os.chdir()` into the isolated branch
  - `exit_worktree` checks for new commits; cleans up via `git worktree remove` if none

### 1.6.6 Developer Experience Primitives ✅ [Impact: M | Difficulty: L]

- [x] **`/doctor`**: 10-check system diagnostics rendered as a rich pass/fail table ✅
- [x] **ToolSearch tool**: search tool registry by name or description at runtime ✅
- [x] **AskUserQuestion tool**: formal tool for structured user input with options validation and retry ✅
- [x] **SleepTool**: agent-callable wait primitive, capped at 300 seconds ✅
- [x] **`/output-style`**: switch between `rich`, `plain`, `compact`, `json` rendering modes ✅

### 1.6.7 Skills Registry ✅ [Impact: H | Difficulty: M]

- [x] **User-extensible skill system**: auto-discovers `*.md` files with YAML front-matter as slash commands ✅
  - Discovery order: bundled → `~/.zenus/skills/` → `.zenus/skills/` → `skills_dir` config
  - `{args}` substitution in prompt body; appended when no placeholder present
- [x] **`/skills` command**: list skills, invoke by trigger, reload without restart ✅
- [x] **Bundled built-in skills**: `commit`, `review-pr`, `simplify`, `explain`, `test-coverage` ✅
- [ ] **MCP skill builders**: expose bundled skills as MCP tools — deferred to Phase 4.3

### 1.6.8 Jupyter Notebook Support ✅ [Impact: M | Difficulty: M]

- [x] **NotebookOps tool**: pure-JSON `.ipynb` manipulation without a kernel ✅
  - `list_cells`, `read_cell`, `edit_cell`, `add_cell`, `delete_cell`, `read_output`, `clear_outputs`
  - Validates extension and file existence; raises typed exceptions (ValueError, FileNotFoundError, IndexError)

---

## Phase 1.7: Resilience, Observability & MCP Modernization — target: by December 2026

Informed by the real Claude Code feature delta (v2.1.x), recent AI framework evolution (LangGraph 1.0, OpenAI Agents SDK), and academic research published in 2024–2025.

### 1.7.1 Durable Execution & Recovery

- [ ] **Per-step atomic checkpointing** — snapshot full execution state at every completed plan step to `~/.zenus/checkpoints/<session-id>/<step-n>.json`. If the process crashes mid-plan, `zenus --resume` picks up from the last checkpoint rather than restarting from scratch. Complements the session store (coarser-grained) without replacing it.
  - *Source: LangGraph 1.0 persistence model, PydanticAI durable execution*

- [ ] **VIGIL self-healing layer** — post-execution reflection that detects tool failure patterns, diagnoses the causal defect (bad argument, missing prereq, wrong path), and generates a targeted prompt patch or corrected tool invocation stored in a per-intent patch pool. Failed steps are automatically retried with the generated patch before surfacing an error to the user.
  - *Source: arXiv 2512.07094 — VIGIL: Reflective Runtime for Self-Healing LLM Agents*

- [ ] **HiAgent hierarchical compaction** — instead of compacting the entire context at the 80% threshold in one shot, compact per-completed-subgoal: as each plan step finishes, its fine-grained action-observation pair is summarised at the subgoal level. Keeps context lean and structured rather than producing one flat summary blob.
  - *Source: HiAgent: Hierarchical Working Memory (2025)*

### 1.7.2 Observability & Developer Experience

- [ ] **`/context` token breakdown** — show per-tool and per-type (system, tool results, conversation) token usage with actionable optimization suggestions. Circuit breaker: auto-compaction disabled for the session after 3 consecutive failures. Real Claude Code had this added in v2.1.x.

- [ ] **Session branching (`/branch` / `/fork`)** — branch the current conversation from any historical checkpoint into a parallel diverging session. Useful for exploring "what if I had approved the other plan?" without losing the current state. Builds on the session store and per-step checkpointing.
  - *Source: real Claude Code v2.1.x `/branch` feature*

- [ ] **Effort / adaptive thinking levels** — three session-level effort modes: `low` (fast, minimal reasoning), `normal` (default), `high` (extended thinking, ToT paths, deeper self-reflection). `ultrathink` keyword triggers `high` for the next turn only. Configurable per session and per skill via front-matter.
  - *Source: real Claude Code effort system, v2.1.x*

- [ ] **OTEL-compatible distributed trace export** — emit OpenTelemetry spans for every orchestrator decision, tool invocation, LLM call, and planning step. Compatible with Langfuse, Logfire, AgentOps, and any standard OTEL collector. Complements the existing `ExecutionLogger`; OTEL is additive, not a replacement.
  - *Source: LangGraph 1.0, OpenAI Agents SDK — both export OTEL natively*

### 1.7.3 Parallel Guardrail Layer

- [ ] **Concurrent input/output guardrails** — a validation layer that runs in parallel with tool execution rather than sequentially inside the hook pipeline. Input guardrails can short-circuit before any tokens are consumed; output guardrails intercept every tool result. Fail-fast semantics: first failing guardrail aborts without waiting for others.
  - *Source: OpenAI Agents SDK guardrail system; arXiv 2509.14285 multi-agent defense pipeline (0% attack success rate across 55 attack types)*

### 1.7.4 MCP Modernization

- [ ] **MCP Streamable HTTP transport** — replace the current SSE transport with the MCP Streamable HTTP specification (standardized March 2025). SSE transport deprecated; Streamable HTTP is the canonical bidirectional transport for HTTP-based MCP clients and servers.
  - *Source: real Claude Code March 2025 MCP update*

- [ ] **MCP Elicitation** — allow MCP server tools to request structured interactive input from the user via a typed dialog (text field, dropdown, confirmation). The Zenus orchestrator renders the elicitation prompt using the existing `AskUserQuestion` mechanism and returns the result to the MCP tool.
  - *Source: real Claude Code MCP Elicitation, v2.1.x*

- [ ] **Log-To-Leak MCP security audit** — new attack class: a malicious MCP tool injected into an agent's context causes the agent to invoke it as a logging side effect, exfiltrating secrets. Audit all paths where tool invocations can be sourced from tool *results* (not only from the user or LLM), and block or sandbox them. Security regression tests required.
  - *Source: Log-To-Leak: MCP Prompt Injection (OpenReview)*

### 1.7.5 Experiential Learning

- [ ] **ERL heuristics pool** — after each completed session, generate 2–3 concise heuristics about what worked and what failed (e.g. "when deleting node_modules, always confirm the project root first"). Store in `~/.zenus/heuristics/`. On the next session with a similar intent (cosine similarity on the goal embedding), retrieve and inject the top-3 heuristics into the system prompt.
  - *Source: arXiv 2603.24639 — Experiential Reflective Learning (ERL)*

---

## Phase 2: Intelligence Amplification — target: by September 2026

### 2.1 Self-Improving AI

- [x] **Feedback Loop** ✅ (v0.4.0)
  - Explicit thumbs up/down on results
  - Success metric tracking per command type
  - Training data export
  - Privacy-aware collection

- [x] **Prompt Evolution** ✅ (v0.5.0)
  - Auto-tune system prompts based on success rate
  - Generate few-shot examples from history
  - Prompt versioning and rollback
  - Domain-specific prompt variants (devops, data science, etc.)
  - A/B testing with automatic promotion
  - Continuous learning from every execution

- [x] **Model Router** ✅ (v0.4.0)
  - Task complexity estimator
  - Route simple tasks to fast/cheap models (DeepSeek)
  - Route complex tasks to powerful models (Claude)
  - Cost tracking per model
  - Fallback cascade

- [ ] **Local Fine-Tuning**
  - Export training data from successful executions
  - Fine-tune small models (Llama, Mistral) on user's workflow
  - Periodic retraining with new data
  - Privacy-preserving training (federated learning option)

### 2.2 Advanced Reasoning

- [x] **Multi-Agent Collaboration** ✅ (v0.5.0)
  - Spawn specialized sub-agents (research, execution, validation)
  - Agent communication protocol
  - Hierarchical planning (manager → workers)
  - ResearcherAgent, PlannerAgent, ExecutorAgent, ValidatorAgent

- [x] **Tree of Thoughts** ✅ (v0.5.0)
  - Generate multiple solution paths
  - Explore alternatives in parallel
  - Confidence-based path selection with pros/cons display

- [x] **Self-Reflection** ✅ (v0.5.0)
  - Critique own plans before execution
  - Validate assumptions with queries
  - Estimate confidence per step
  - Know when to ask for human input

- [x] **Knowledge Graph** ✅ (v1.1.0)
  - Directed, typed entity-relationship graph built from ActionTracker events
  - Reason about relationships (file dependencies, service dependencies)
  - BFS traversal: `what_depends_on`, `what_would_be_affected`, `related_to`
  - Natural-language query dispatch, thread-safe, JSON persistence

---

## Phase 3: Multimodal & Accessibility — target: by December 2026

### 3.1 Voice Interface

- [x] **Speech-to-Text** ✅ (v0.2.0 — faster-whisper, no PyTorch, int8)
  - Local STT via `faster-whisper` (CTranslate2 backend, 4× faster than openai-whisper)
  - Wake word detection via `openwakeword` — no API key, no cloud
  - Text-matching fallback (`TextFallbackDetector`) when openwakeword not installed
  - `voice/pipeline.py` — canonical `VoicePipeline` with wake→STT→Zenus→TTS loop

- [ ] **Text-to-Speech** *(in progress — Phase 1.5.3)*
  - Local TTS (Piper, Coqui)
  - Streaming TTS (start speaking before completion)
  - Voice profiles (user preferences)

- [ ] **Conversational Flow** *(in progress — Phase 1.5.3)*
  - Clarifying questions mid-execution
  - Natural interruptions ("wait, stop")
  - Context carryover ("and then do X")

### 3.2 Visual Understanding

- [x] **Screenshot Analysis** ✅ (v0.5.0 - partial)
  - Describe UI elements
  - Detect errors and warnings
  - Suggest actions
  - Accessibility tree extraction (pending)

- [ ] **OCR Integration**
  - Read text from images
  - Extract tables and charts
  - Multi-language OCR

- [ ] **Video Understanding**
  - Analyze screen recordings
  - Detect user actions (clicks, typing)
  - Generate automation scripts from recordings

### 3.3 Rich Output

- [x] **Data Visualization** ✅ (v0.5.0)
  - Auto-generate charts (matplotlib)
  - Tables with sorting/filtering (Rich)
  - Diff views (before/after)
  - Multiple chart types (line, bar, pie, histogram, heatmap)

- [ ] **Web Dashboard**
  - Browser-based UI (FastAPI + React)
  - Real-time updates (WebSocket)
  - Multi-pane layout
  - Shareable URLs for results

- [ ] **Mobile App**
  - iOS/Android native apps
  - Push notifications
  - Remote execution
  - Biometric auth

---

## Phase 4: Ecosystem & Integrations — target: by March 2027

### 4.1 Platform Integrations

- [ ] **Version Control** (partial)
  - Advanced Git operations (rebase, cherry-pick, bisect) — basic ops done
  - GitHub Issues API done; PR creation and review pending
  - GitLab/Bitbucket API integration
  - Commit message generation

- [ ] **Cloud Platforms**
  - AWS CLI automation
  - Azure and Google Cloud operations
  - Infrastructure as code (Terraform)
  - Cost optimization suggestions

- [ ] **Databases**
  - SQL query generation and execution
  - Schema migrations
  - Data import/export
  - Query performance analysis

- [ ] **Containers & Orchestration**
  - Docker Compose generation
  - Kubernetes management
  - Helm charts
  - Log aggregation

- [ ] **CI/CD**
  - GitHub Actions workflow generation
  - Build failure diagnosis
  - Deployment automation and rollback strategies

### 4.2 Communication Platforms

- [ ] **Chat Integrations**
  - Slack bot
  - Discord bot
  - Microsoft Teams
  - Telegram bot

- [ ] **Email Automation**
  - Email parsing and action extraction
  - Automated responses
  - Calendar integration

- [ ] **Notifications**
  - Desktop notifications
  - Push notifications (mobile)
  - Webhook callbacks

### 4.3 Development Tools

- [ ] **MCP Integration** *(moved to Phase 1.5.2 — prioritized for pre-launch)*

- [ ] **Code Operations**
  - Intelligent code generation
  - Refactoring (rename, extract method)
  - Bug detection and fixes
  - Test generation and documentation generation
  - Code review comments

- [ ] **IDE Extensions**
  - VS Code extension
  - JetBrains plugin
  - Vim/Neovim plugin
  - Inline suggestions and contextual commands

- [ ] **API Testing**
  - Generate curl/HTTP requests
  - Schema validation and load testing
  - Mock server generation

- [ ] **Security Scanning**
  - Dependency vulnerability check
  - Secret detection
  - SAST integration
  - Compliance validation

- [ ] **LSP Integration** [Impact: H | Difficulty: H — from CC analysis]
  - Language Server Protocol client: connect to running language servers (pylsp, rust-analyzer, tsserver, etc.)
  - Expose `LSPTool` actions: go-to-definition, hover documentation, find references, get diagnostics, rename symbol
  - Agent uses LSP data to ground code operations in actual type information rather than text heuristics
  - Enables accurate multi-file refactoring, real-time error detection before running code, and navigation of large codebases
  - Design note: high difficulty because LSP is stateful (server process per workspace) and protocol-heavy, but the payoff for code-centric workflows is substantial

---

## Phase 5: Collaboration & Enterprise — target: by June 2027

### 5.1 Multi-User Support

- [ ] **User Management**
  - User accounts and authentication
  - SSO integration (OAuth, SAML)
  - MFA support and session management

- [ ] **Role-Based Access Control**
  - Roles (admin, developer, viewer)
  - Permissions per tool/operation
  - Approval workflows for dangerous ops
  - Audit trail per user

- [ ] **Collaboration Features**
  - Shared execution history
  - Command templates library
  - Team-wide context (projects, conventions)
  - Handoff mechanism (pause → transfer)

- [ ] **Workspaces**
  - Isolated environments per project
  - Shared resources (tools, configs)
  - Workspace templates

- [ ] **Session sharing** [Impact: M | Difficulty: M — from CC analysis]
  - Export a session (conversation, plan, results) as a portable artifact
  - Import and replay a shared session on another machine or user account
  - Shareable URL if a hosted Zenus service is available (aligns with Phase 3.3 Web Dashboard)

- [ ] **Settings sync** [Impact: M | Difficulty: M — from CC analysis]
  - Sync `config.yaml` user preferences and skill definitions across machines via a cloud store or git repo
  - Conflict resolution: last-write-wins for scalar values, merge for lists (tools deny-list, MCP servers)
  - Local-only mode remains the default; sync is opt-in

- [ ] **GitHub App integration wizard** [Impact: M | Difficulty: M — from CC analysis]
  - `/install-github-app`: guided flow to install the Zenus GitHub App on a repo or org
  - Enables webhook-driven triggers (PR opened → Zenus runs review), automated commit signing, and fine-grained token management
  - Foundation for Phase 4.1 CI/CD automation

- [ ] **Slack App integration wizard** [Impact: M | Difficulty: M — from CC analysis]
  - `/install-slack-app`: guided OAuth flow to connect Zenus to a Slack workspace
  - Enables `zenus` slash command from Slack, result posting, and alert delivery (links Phase 6.2 Contextual Suggestions to chat)

### 5.2 Enterprise Features

- [ ] **Compliance & Auditing**
  - SOC 2 Type II compliance
  - GDPR compliance (data retention policies)
  - HIPAA support
  - Tamper-proof audit logs

- [ ] **High Availability**
  - Clustered deployment
  - Load balancing and automatic failover
  - Zero-downtime updates

- [ ] **Multi-Tenancy**
  - Tenant isolation
  - Resource quotas per tenant
  - Billing integration

---

## Experiments: Research-Grade Concepts Under Exploration

These ideas are grounded in peer-reviewed research published in 2024–2025 and in observed gaps between Zenus and the frontier of AI agent platform design. They are **not committed deliverables** — each requires a dedicated design spike before any implementation begins. They are listed here to preserve the research intent and to give future contributors a clear starting point.

Unlike Phase 5.5 (which captures design concepts that emerged organically during v1.x development), this section tracks ideas explicitly sourced from academic papers and framework benchmarking.

---

### E.1 Memory Architecture Upgrades

**A-MEM: Agentic Memory with Zettelkasten-Style Linking** — *arXiv 2502.12110*
- Assign every memory note a unique ID, keyword set, and dynamic links to related notes. Retrieval follows link graphs rather than flat similarity search — significantly improves relevance for multi-hop queries.
- Zenus already has a knowledge graph (entity → entity edges). A-MEM adds note → note linking at the memory level, orthogonal to the KG.
- Design spike needed: how does A-MEM interact with the existing `intent_history.py` and `world_model.py`? Are they unified or layered?

**Multi-Layered Memory (Working + Episodic + Semantic)** — *arXiv 2603.29194*
- Three-tier hierarchy: working memory (active context, current session), episodic memory (per-session event log), semantic memory (long-term facts, currently the world model + knowledge graph). An adaptive retrieval gate decides which tier to query per turn.
- Retention regularization prevents cross-session drift (the system "forgets" stale facts gracefully rather than accumulating noise).
- Zenus has semantic and episodic elements but no formal working/episodic split with a retrieval gate.

**TiMem: Temporal-Hierarchical Memory Tree** — *(2025)*
- Memory tree that consolidates entries temporally: recent → session-level → project-level → long-term. No RL or fine-tuning required.
- Valuable for users who run Zenus over long projects (weeks/months) where older context becomes noise but should not be fully discarded.

**AgentHER: Hindsight Experience Replay** — *arXiv 2603.21357*
- When a session fails to achieve goal G, retrospectively relabel the trajectory with the goal G' that it *actually achieved*, and store it as a positive example. Requires reverse-engineering a natural-language prompt that the actual trajectory satisfies.
- Failed Zenus sessions currently produce only negative signal. AgentHER turns them into a source of positive training signal without any model fine-tuning.

---

### E.2 Planning and Reasoning Extensions

**LATS: Language Agent Tree Search** — *arXiv 2310.04406*
- Unifies ReAct, Tree of Thoughts, and Monte Carlo Tree Search into one framework operating at the *action* level (not the reasoning token level). The agent explores the action space with MCTS, backpropagating value estimates from execution outcomes.
- Zenus's existing ToT implementation operates at the plan-generation level. LATS would extend it to search over actual tool-execution paths, not just candidate plans.
- High complexity: requires execution rollback between MCTS simulations (pairs with per-step checkpointing from 1.7.1).

**MAR: Multi-Agent Reflexion with Adversarial Validator** — *arXiv 2512.20845*
- Separates acting, diagnosing, critiquing, and aggregating into distinct agents. A *judge model* synthesises critiques from diverse validator personas into a unified reflection, preventing the "echo chamber" failure of single-agent self-reflection.
- Zenus's self-reflection loop could spawn a second LLM call as an adversarial critic before finalizing a plan.
- Relatively low effort to prototype given Zenus already has multi-agent scaffolding.

**Multi-Agent ToT Validator** — *arXiv 2409.11527*
- A separate validator agent challenges Tree of Thoughts reasoning paths for logical and factual correctness. Reduces shared blind spots vs. single-agent reflection.
- Simpler than full MAR; a good intermediate step.

---

### E.3 Tool Use Paradigm Shift

**Code-as-Actions (smolagents CodeAgent pattern)**
- Instead of producing JSON tool calls, the LLM writes Python code snippets that are executed directly. Function nesting, loops, and conditionals are handled natively by the code, not by the planner.
- Demonstrated ~30% step reduction and higher benchmark scores vs. JSON tool-call agents on common benchmarks.
- The IntentIR model is fundamentally JSON-structured; adopting Code-as-Actions would require a parallel execution path (not a replacement) to preserve safety guarantees. Design spike: how does risk assessment and rollback work for code-as-actions?

---

### E.4 Inter-Agent Interoperability

**A2A Protocol (Google, v1.0 early 2026)**
- Agent-to-Agent open standard: signed Agent Cards (capability declarations), gRPC transport, multi-tenancy support, peer-to-peer message exchange between agents on different frameworks.
- Real Claude Code SDK (renamed Claude Agent SDK in late 2025) added A2A support as a bridge between MCP and inter-framework agent communication.
- Zenus agents could expose an A2A endpoint to receive tasks from external orchestrators and return results, making Zenus composable with any A2A-compatible agent ecosystem.
- Design spike: A2A + MCP coexistence; authentication model; privilege mapping.

---

### E.5 Agentic Retrieval and Knowledge Grounding

**Agentic RAG with Knowledge Graph Multi-Hop Reasoning** — *arXiv 2507.16507*
- Combines KG traversal with unstructured retrieval: the LLM proposes KG-grounded relation paths, validates them against the graph, performs stepwise reasoning along confirmed paths.
- Zenus's knowledge graph is currently a storage and querying layer. This would make it an *active retrieval planner* that drives context construction for multi-hop questions.

**HiPRAG: Hierarchical Process Rewards for Agentic RAG** — *arXiv 2510.07794*
- Process reward models guide individual retrieval decisions at each reasoning step, outperforming flat retrieval pipelines on complex multi-hop tasks.
- Research-grade: requires a trained reward model or adaptation of an open PRM. Worth revisiting as open PRMs become more available.

---

### E.6 Safety Research

**Design Patterns for Securing LLM Agents** — *arXiv 2506.08837*
- Formal taxonomy of prompt injection defense patterns with provable-resistance analysis: privilege separation, input validation gates, output canonicalization, sandboxed tool execution, dual-LLM verification.
- Zenus's IntentIR "prison" implements several of these implicitly. A formal mapping — which patterns are active, which are partial, which are absent — would produce a concrete security hardening backlog.
- Recommended action: assign a contributor to map the taxonomy against the current codebase and file issues for each gap.

---

## Phase 5.5: New Concepts Under Exploration

These ideas emerged during v1.x development and will be revisited when Phase 5 is underway. They are listed here to preserve the design intent, not as committed deliverables.

### Intent Versioning & Replay

- [ ] **Intent version history**: every `IntentIR` stored with a monotonic version ID
- [ ] **Replay any past intent**: re-execute a previous plan against the current system state
- [ ] **Diff two intents**: surface exactly what changed between two versions of the same goal
- [ ] **Time-travel debugging**: replay a failed execution step by step in a sandbox
- [ ] **Design note**: `IntentIR` is already serializable; the main work is a version store and a replay engine that can substitute observations from the past run with fresh ones

### Sandboxed Intent Simulation

- [ ] **Dry-run with state tracking**: simulate full execution in an isolated scratch space (tmpfs, namespace, or container) and report what would have changed
- [ ] **Blast-radius report**: before any destructive op, show exactly which files/services would be affected and by how much
- [ ] **Conflict detection**: detect if two pending intents would race on the same resource
- [ ] **Design note**: builds on `SandboxedAdaptivePlanner` already in place; extends it to return a structured diff rather than a yes/no

### Plugin & Extension System

- [ ] **Tool plugin API**: third-party tools installable as Python packages (`zenus-tool-*`), auto-discovered and merged into the registry at startup
- [ ] **Tool manifest**: each plugin declares its actions, risk levels, and privilege requirements in a `tool.yaml`
- [ ] **Sandboxed plugin execution**: plugins run with constrained permissions (no network by default, filesystem limited to declared paths)
- [ ] **Plugin marketplace**: curated index of community tools; `zenus plugin install <name>`
- [ ] **Design note**: the current registry is a flat dict — the main work is a discovery layer, a validation step (manifest + safety policy), and a reload mechanism compatible with hot-reload config

---

## Phase 6: Autonomy & Proactivity — target: by September 2027

### 6.1 Background Agent

- [ ] **Scheduled Tasks**
  - Cron-like scheduling
  - Event-driven triggers
  - Chained workflows and conditional execution

- [x] **Proactive Monitoring** ✅ (v0.5.0)
  - Watch for system issues (disk full, memory leak)
  - Alert before problems occur
  - Auto-remediation (restart service, clear cache)
  - Health checks: disk, memory, service, log, SSL certificate

- [ ] **Maintenance Automation**
  - Automatic updates (OS, packages, dependencies)
  - Log rotation and backup verification
  - Security patching

- [ ] **Learning User Patterns** (partial)
  - Predict next commands (pattern detection implemented)
  - Suggest optimizations (SuggestionEngine done)
  - Automate repetitive workflows (WorkflowRecorder done)
  - Pre-fetch likely results

### 6.2 Intelligent Assistance

- [x] **Contextual Suggestions** ✅ (v0.5.0 - partial)
  - "You usually do X after Y, want me to do it?" (SuggestionEngine done)
  - "This file hasn't been backed up in 30 days" (pending)
  - "Your project dependencies are outdated" (pending)

- [x] **Goal Inference** ✅ (v0.5.0)
  - Infer high-level goals from commands
  - Propose complete workflows with implicit steps filled in
  - Detects 11 goal types (deploy, debug, migrate, security, etc.)
  - Adds safety steps automatically (backups, tests, verification)
  - Interactive workflow approval

- [ ] **Habit Formation**
  - Track good practices
  - Gentle nudges for best practices

---

## Phase 7: Distributed & Edge — target: by December 2027

### 7.1 Multi-Machine Orchestration

- [ ] **Remote Execution**
  - SSH tunnel management
  - Agent installation on remote hosts
  - Inventory management (Ansible-like)
  - Parallel execution across fleet

- [ ] **Upstream proxy support** [Impact: M | Difficulty: L — from CC analysis]
  - Route all Zenus API calls through a configurable HTTP proxy (`api.proxy_url` in `config.yaml`)
  - Required for enterprise deployments behind corporate firewalls or data-residency requirements
  - Also enables local proxy for cost interception, logging, and rate-limit pooling across a team

- [ ] **Teleport / remote agent deployment** [Impact: H | Difficulty: H — from CC analysis]
  - `zenus teleport <host>`: install and launch a Zenus agent on a remote host over SSH, then control it from the local TUI
  - Zenus becomes the "nerve centre" and the remote instance becomes a worker
  - Foundation for Phase 7.1 fleet orchestration and the OS-layer agent model in Phase 10

- [ ] **Distributed Tasks**
  - Map-reduce style operations
  - Data pipelines across machines
  - Coordination primitives (locks, barriers)

- [ ] **Cloud-Native**
  - Kubernetes operator
  - Serverless functions (Lambda, Cloud Functions)
  - Service discovery

### 7.2 Edge Computing

- [ ] **Offline Mode**
  - Local LLM fallback
  - Cached commands work offline
  - Sync when online with conflict resolution

- [ ] **Edge Devices**
  - Raspberry Pi support
  - IoT device management
  - ARM architecture optimization

- [ ] **Embedded Zenus**
  - Zenus as library (not just CLI)
  - REST API server mode
  - gRPC service

---

## Phase 8: AI Safety & Ethics — target: by March 2028

### 8.1 Safety Mechanisms

- [ ] **Enhanced Sandboxing**
  - Mandatory dry-run for destructive ops
  - Undo stack with snapshots
  - Blast radius estimation
  - Capability-based security

- [ ] **Interpretability**
  - Explain every decision in plain language
  - Confidence scores per action
  - Reasoning chains visualized
  - **Extended thinking visualization** (`/thinkback`, `/thinkback-play`) [Impact: M | Difficulty: M — from CC analysis]: surface the model's full chain-of-thought as a navigable, playable transcript; lets users inspect *why* an action was chosen, not just *what* was chosen; pairs with Tree of Thoughts (already in Phase 2.2)

- [ ] **Per-tool sandbox toggle** [Impact: M | Difficulty: L — from CC analysis]
  - `/sandbox-toggle`: flip sandboxing on or off for specific tools interactively during a session
  - Useful when a trusted plugin needs temporary elevated access without permanently changing privilege tiers
  - Decision is logged and expires at session end; never persisted silently

- [ ] **Kill Switches**
  - Emergency stop (Ctrl+C+C)
  - Panic mode (undo recent actions)
  - Rate limiting (max X ops per minute)
  - Human-in-the-loop for high-risk operations

### 8.2 Ethical AI

- [ ] **Privacy Protection**
  - Local-first architecture
  - Data minimization
  - Right to be forgotten

- [ ] **Transparency**
  - Open-source models prioritized
  - Data provenance tracking
  - Carbon footprint estimation

---

## Phase 8.5: Zenus-Native Intelligence Layer — target: after Zenus reaches stable maturity

The long-term goal of Zenus is to become an operating system. An OS cannot depend on a third-party API for its core cognitive layer. This phase builds the Zenus-native model: a small, domain-optimised language model trained specifically on Zenus's task domain, designed to run entirely locally without internet access or API keys, and continuously improved by real usage data. It replaces the `rule_based` fallback in the provider chain with something substantially more capable, and eventually becomes the primary engine for cost-sensitive and privacy-sensitive deployments.

**Prerequisites**: Zenus must be feature-stable (Phases 1–8 substantially complete), with at minimum several hundred real users generating execution data. The training pipeline described here requires a corpus of real intent→plan pairs to reach meaningful quality above the fine-tuned baseline.

---

### 8.5.1 Task Framing and Scope

The Zenus model does **not** need to be a general-purpose language model. Its task domain is precisely defined:

```
Input  → Natural language user command + system context
               (working directory, OS, git status, session history)
Output → Valid IntentIR JSON
               { goal, steps[{ tool, action, args, risk }],
                 requires_confirmation, search_provider, is_question }
```

This is a **structured output problem over a fixed schema with ~25 tool types and ~120 actions**. The search space is orders of magnitude smaller than general instruction following. A 1–3B parameter model fine-tuned on this task can outperform a 70B general model on it, because:
- The output grammar is formally specified (Pydantic schema)
- Invalid outputs are immediately detectable and retryable
- Every production execution produces a labeled training example automatically

---

### 8.5.2 Training Data Pipeline

Zenus is its own training data generator. Every executed command produces:
```
(user_input, system_context) → IntentIR → execution_results → success/failure
```

This is a labeled `(input, structured_output, quality_signal)` triple — exactly what supervised fine-tuning and RLHF require.

**Bootstrap dataset (pre-launch, synthetic)**
- [ ] Write 500 diverse user command templates covering all Zenus tool categories: file management, system ops, git workflows, package management, networking, scheduling, notebooks, voice commands
- [ ] Expand to **50,000 instruction pairs** using a frontier model (DeepSeek-V3 or Claude) as the oracle teacher. Cost: ~$100–150 at frontier model API rates
- [ ] For each example, generate: the ideal IntentIR, two common error variants (wrong tool, wrong risk level), and the corrected recovery plan
- [ ] Include edge cases: ambiguous commands, multi-step plans with dependencies, risk=3 operations requiring confirmation, Q&A intents that should set `is_question=true`
- [ ] Format as instruction-tuning pairs: system prompt (Zenus context) + user turn + assistant turn (IntentIR JSON)
- [ ] Hold out 5,000 examples for evaluation; never used in training

**Production data flywheel (post-launch)**
- [ ] Instrument `orchestrator.py` to log every `execute_command` call with: anonymized input, produced IntentIR, execution outcome, any user rollback signal
- [ ] Treat successful executions (no rollback, no error) as positive examples
- [ ] Treat rolled-back or error-terminated executions as negative examples with structured failure labels
- [ ] Consent model: opt-in by default, configurable via `config.yaml model_training.contribute_data: false`
- [ ] Local-only mode: data stays on-device and is used only for local model retraining; never uploaded unless user explicitly enables telemetry
- [ ] Monthly retraining batch: collect new examples → filter by quality threshold → merge with previous dataset → retrain LoRA adapter

**Data quality gates**
- [ ] Schema validation: every generated IntentIR must parse against the live Pydantic schema
- [ ] Risk consistency: verify that risk levels match tool action risk tables (no `delete_file` at risk=0)
- [ ] Deduplication: fuzzy dedup on user inputs using MinHash LSH to prevent overfitting to repeated patterns
- [ ] Human review sample: 1% random sample reviewed manually per training batch

---

### 8.5.3 Tokenizer Design

Standard BPE tokenizers are English-optimized and waste tokens on Zenus's domain. The plan:

**Custom SentencePiece unigram tokenizer**
- [ ] Collect training corpus: Zenus source code + generated IntentIR dataset + tool documentation + config YAML files
- [ ] Train SentencePiece unigram tokenizer, vocabulary size **24,576 tokens** (24K general + 512 reserved for domain specials)
- [ ] Validate: measure average tokens-per-IntentIR on held-out set; target ≥35% reduction vs. base model tokenizer

**Domain special tokens**
```
<|intent_start|>   <|intent_end|>
<|step_start|>     <|step_end|>
<|goal|>           <|tool|>        <|action|>      <|args|>
<|risk_0|>         <|risk_1|>      <|risk_2|>      <|risk_3|>
<|requires_confirm|>  <|is_question|>  <|search_web|>
<|context_start|>  <|context_end|>
```

- [ ] These tokens collapse frequently recurring multi-token patterns into single tokens. `<|risk_3|>` replaces `"risk": 3` (4 tokens → 1)
- [ ] Embed new tokens by averaging the embeddings of their constituent sub-tokens at initialisation; this gives non-random starting weights and accelerates training convergence
- [ ] Add domain tokens to the base model vocabulary via embedding table extension before fine-tuning

---

### 8.5.4 Base Model Selection and Fine-Tuning

**Candidate base models**

| Model | Params | License | Rationale |
|---|---|---|---|
| **Qwen2.5-3B-Instruct** | 3B | Apache 2.0 | Best 3B class; strong JSON/structured output; active development |
| **Llama-3.2-3B-Instruct** | 3B | Llama (commercial OK) | Wide tooling support; best GGUF ecosystem |
| **SmolLM2-1.7B-Instruct** | 1.7B | Apache 2.0 | Smallest viable; good for resource-constrained fallback |
| **DeepSeek-R1-Distill-Qwen-7B** | 7B | MIT | Already distilled reasoning; best quality ceiling; higher resource cost |

Primary target: **Qwen2.5-3B-Instruct** (best quality-to-size ratio at 3B, Apache 2.0 allows unrestricted commercial use).

**Training method: QLoRA + supervised fine-tuning**
- [ ] Quantize base model to 4-bit (NF4) using bitsandbytes; this is the "QL" part of QLoRA
- [ ] Add LoRA adapter layers (r=64, alpha=128) to all attention projection matrices (q_proj, k_proj, v_proj, o_proj) and MLP layers
- [ ] Train only the adapter weights (~40M parameters out of 3B); base model weights frozen
- [ ] Hardware requirement: **1× GPU with 24GB VRAM** (RTX 4090, A10G, or A100 40GB). All are available on Lambda Labs / Vast.ai / RunPod
- [ ] Training framework: **Axolotl** (handles QLoRA, custom tokenizer extension, gradient checkpointing, Flash Attention 2) or **LLaMA-Factory**
- [ ] Training hyperparameters: batch_size=4, grad_accum=8, lr=2e-4, warmup_ratio=0.05, 3 epochs, cosine scheduler
- [ ] Estimated training time: **8–12 hours** on A10G for 50K examples × 3 epochs
- [ ] Checkpoint every 500 steps; evaluate on held-out set after each epoch

**Evaluation metrics**
- [ ] IntentIR schema validity rate (target: >99% — invalid JSON is immediate fail)
- [ ] Tool accuracy: correct tool selected for intent (target: >92%)
- [ ] Action accuracy: correct action selected given tool (target: >90%)
- [ ] Risk level accuracy: correct risk assigned (target: >95% — risk errors are safety-relevant)
- [ ] `is_question` F1: correctly classifies Q&A vs. execution intents (target: >93%)
- [ ] Compare against: current Ollama fallback (Llama-3.2-3B vanilla), rule_based fallback

---

### 8.5.5 Distillation from Frontier Teacher

Beyond SFT, apply **knowledge distillation** to transfer reasoning quality from a frontier model:

- [ ] Generate a **distillation dataset** separately from the SFT data: for each training example, record the full **logit distribution** (not just the top token) from the frontier teacher (Claude or GPT-4) over the IntentIR output sequence
- [ ] Train the student (Qwen2.5-3B) to minimize KL divergence from teacher logits, not just cross-entropy on the correct token. This teaches the student the teacher's uncertainty distribution — it learns *which alternatives are plausible* not just *which answer is right*
- [ ] Loss function: `L = α × CE(student, label) + (1-α) × KL(student_logits ∥ teacher_logits)`, with α=0.5
- [ ] This is exactly the technique behind DeepSeek's distilled models: the student inherits reasoning patterns the teacher learned, not just answers

---

### 8.5.6 Inference Efficiency Stack

**Quantization for CPU deployment**
- [ ] After fine-tuning, merge LoRA adapter into base model weights (full-precision merge)
- [ ] Quantize to GGUF format using `llama.cpp/convert_hf_to_gguf.py`
- [ ] Target format: **Q4_K_M** (4-bit, mixed precision on "important" layers — attention and first/last MLP layers kept at Q6)
- [ ] Expected model size: **~1.8GB** for 3B Q4_K_M
- [ ] Expected CPU throughput: 15–30 tok/s on modern laptop CPU (Intel Core i7 / Apple M-series)
- [ ] Validate: measure perplexity delta vs. BF16 on IntentIR eval set; acceptable threshold <5% degradation

**LLMLingua context compression (input side)**
- [ ] Integrate **LLMLingua-2** (Microsoft, Apache 2.0) as a pre-processor step before any LLM call in the provider chain — not just the Zenus model
- [ ] LLMLingua uses a small 250M-parameter model to score token importance; low-importance tokens in the context (session history, world model facts, system prompt boilerplate) are dropped
- [ ] Target compression ratio: 4–8× on context; keep all user-turn content intact; compress assistant turns and tool results
- [ ] Integration point: `brain/llm/base.py` — add `compress_context()` hook called before `translate_intent()` when context exceeds a configurable token threshold
- [ ] Config key: `model_training.context_compression: true` (default false, opt-in)

**Speculative decoding with a 0.5B drafter**
- [ ] After the 3B model is stable, distill a **0.5B speculative draft model** from it using the same pipeline at smaller scale
- [ ] The drafter proposes 4–8 candidate tokens per step; the 3B verifier accepts or rejects in a single forward pass
- [ ] Net effect: **2–3× throughput increase** with identical output quality (mathematically equivalent to running the 3B alone)
- [ ] llama.cpp supports speculative decoding natively via `--draft-model` flag; no Zenus code changes needed

**Serving via llama-server (OpenAI-compatible)**
- [ ] Serve the GGUF model with `llama-server` (ships with llama.cpp), which exposes an OpenAI-compatible REST API on localhost
- [ ] Zenus's existing `OllamaLLM` backend works with any OpenAI-compatible endpoint — point it at `http://localhost:8080` instead of `http://localhost:11434`
- [ ] Alternatively: package the GGUF with `ollama create zenus-3b -f Modelfile` and serve via Ollama for zero-config user experience

---

### 8.5.7 Zenus Integration

**Fallback chain placement**
```yaml
# config.yaml
llm:
  provider: anthropic      # primary

fallback:
  providers:
    - anthropic            # frontier quality, API required
    - deepseek             # fast, cheap, API required
    - zenus-native         # local, no API, no internet — this phase
    - rule_based           # deterministic last resort
```

**New LLM backend: `ZenusNativeLLM`**
- [ ] Implement `zenus_core/brain/llm/zenus_native.py` extending `BaseLLM`
- [ ] On init: check if `zenus-3b` model exists in Ollama registry or if llama-server is running; skip gracefully if not installed
- [ ] `translate_intent()`: call llama-server with the Zenus system prompt; parse response against IntentIR schema; on schema validation failure, retry once with an error-correction prompt ("the previous response was invalid JSON: {error}. Correct it and return only valid JSON")
- [ ] `ask()`: pass directly to model as a Q&A prompt; no IntentIR wrapping
- [ ] Expose `zenus model install` CLI command: downloads the GGUF, sets up Ollama model, tests inference, adds to provider chain

**Model management commands**
- [ ] `zenus model status` — show which local models are installed, their sizes, and benchmark scores
- [ ] `zenus model install [zenus-3b|zenus-1.7b]` — download from Zenus releases, install via Ollama
- [ ] `zenus model benchmark` — run the held-out eval set against local model, print accuracy metrics
- [ ] `zenus model retrain` — (advanced) trigger a local retraining cycle using accumulated on-device data

---

### 8.5.8 Continuous Improvement via Reinforcement Learning

Once the base fine-tuned model is deployed, upgrade from SFT to RL-based training using Zenus itself as the reward environment:

**Reward signal design**
```
+1.0  → Execution completed successfully, no rollback, no user correction
+0.5  → Execution completed with minor user edit (one step changed)
 0.0  → Execution abandoned mid-way (neutral)
-0.5  → Tool error (wrong args, missing prereq)
-1.0  → User issued rollback immediately after execution
-1.5  → Safety policy rejection (risk level misclassified upward)
```

- [ ] Implement reward logging in `brain/planner.py` and `shell/commands.py`; attach reward signal to the IntentIR that produced the execution
- [ ] Buffer rewards locally in `~/.zenus/rl_buffer/` as structured JSONL
- [ ] Training algorithm: **GRPO** (Group Relative Policy Optimization — used by DeepSeek-R1) over LoRA adapter weights; computationally lighter than PPO for structured output tasks
- [ ] Retrain monthly: collect ≥1,000 new reward-labeled examples → run 1 GRPO epoch → merge adapter → requantize → push updated GGUF to local Ollama registry
- [ ] Guard: never allow RL to reduce schema validity rate below 98%; if it does, revert to the last SFT checkpoint

**AgentHER retrospective relabeling** *(from Experiments section)*
- [ ] When a session fails to achieve goal G, retrospectively relabel the trajectory with the goal G' it *actually achieved* and store as a positive training example
- [ ] Requires: a small post-session analysis step that asks the frontier model "given these execution results, what goal was actually accomplished?" and produces a new (input, IntentIR) pair with G' as the goal
- [ ] This converts every failed session from a negative signal into two signals: a negative on G and a positive on G'

---

### 8.5.9 Future Research Paths (post-v1 model)

These require the base pipeline to be working first and are research-grade:

**Coconut-style latent planning**
- Replace the token-by-token IntentIR generation with continuous-thought reasoning: the model generates a fixed number of latent state vectors (one per plan step), then decodes them all into the final IntentIR JSON simultaneously
- Expected benefit: more globally coherent plans, fewer step-level inconsistencies, faster generation (parallel decode)
- Requires: architectural modification to the model (adding latent "thinking step" positions to the forward pass); custom training objective
- *Source: arXiv 2412.06769 — Coconut: Chain of Continuous Thought (Meta AI, 2024)*

**Per-domain micro-vocabulary specialization**
- Instead of one Zenus tokenizer, train separate tokenizer extensions per domain: one for file/system ops, one for git workflows, one for network/API tasks
- At inference, select the domain tokenizer based on the classified intent category
- Expected benefit: 40–60% further token reduction for in-domain commands

**BitNet ternary weights from scratch**
- If the 3B fine-tuned model is working well and the training pipeline is mature, experiment with training a smaller (~1B) model from scratch using BitNet b1.58 ternary weights {-1, 0, 1}
- Ternary weights eliminate multiplications in inference: all operations become additions. On a purpose-built RISC-V extension or FPGA, this could run at 10–100× the throughput of Q4 quantized models
- The 1B ternary model would be ~180MB on disk — a realistic embedded component for the OS phase

---

### 8.5.10 Resource Requirements and Cost Estimates

**Hardware**

| Task | Hardware | Source | Cost |
|---|---|---|---|
| Synthetic data generation (50K examples) | Any machine with internet | Claude/DeepSeek API | $100–200 |
| Tokenizer training | CPU, any machine | — | $0 |
| QLoRA fine-tuning | 1× A10G (24GB) | Lambda Labs / RunPod | $10–20 (10 hours) |
| Distillation dataset generation | API | Frontier model API | $50–100 |
| Evaluation runs | 1× A10G | Lambda Labs | $5–10 |
| GGUF quantization | CPU | — | $0 |
| **Total (first working model)** | | | **$165–330** |
| Monthly RL retraining cycle | 1× A10G, 3–4 hours | Lambda Labs | $5–10/month |

**Time**

| Phase | Duration (solo, part-time) | Duration (solo, full-time) |
|---|---|---|
| Data pipeline + synthetic generation | 2 weeks | 1 week |
| Tokenizer design + vocabulary extension | 1 week | 3 days |
| QLoRA fine-tuning + evaluation iterations | 2 weeks | 1 week |
| Distillation dataset + distillation run | 1 week | 3 days |
| GGUF quantization + Zenus integration | 1 week | 3 days |
| Testing, edge cases, benchmarking | 1 week | 3 days |
| **Total to first deployable model** | **8 weeks** | **4 weeks** |

**Ongoing maintenance**: ~4 hours/month to curate new training data, run retraining, validate metrics.

---

### 8.5.11 Success Criteria

The Zenus-native model is ready for production fallback when it meets all of:

- [ ] IntentIR schema validity: **≥ 99%** on held-out eval set (1,000 examples)
- [ ] Tool selection accuracy: **≥ 92%**
- [ ] Action accuracy: **≥ 90%**
- [ ] Risk level accuracy: **≥ 95%** (safety-critical)
- [ ] `is_question` F1: **≥ 93%**
- [ ] CPU throughput: **≥ 10 tok/s** on a modern laptop CPU (i7 / Ryzen 7)
- [ ] Model size: **≤ 2GB** on disk
- [ ] Cold start: **≤ 3 seconds** to first token on CPU
- [ ] Outperforms `rule_based` fallback on all metrics
- [ ] Does not regress Zenus's overall test suite (3,033 tests passing)

---

## Phase 9: Beyond Terminals — target: by June 2028

### 9.1 New Interfaces

- [ ] **Natural Interfaces**
  - Write commands in email
  - Speak to smart speakers
  - SMS commands

- [ ] **Wearables**
  - Smartwatch quick commands
  - AR glasses integration

### 9.2 Physical World Integration

- [ ] **Smart Home**
  - Control IoT devices
  - Home automation routines
  - Energy optimization

- [ ] **Robotics**
  - ROS integration
  - Robot task planning
  - Sensor data analysis

---

## Phase 10: Operating System Transition — target: by December 2028

This is the long-term ambition: Zenus evolving from a Python application into a system where the AI layer sits closer to the hardware. It is the most uncertain phase and will only begin once the upper layers are stable and mature. The architecture and language choices will be revisited when we get there.

### 10.1 Architecture Direction

**Current state (v1.x)**:
```
User → Python App (Zenus) → Linux → Hardware
```

**Target direction**:
```
User → Python AI Layer → Custom OS Services (Rust/C++) → Hardware
```

The Python layer keeps the AI and ML ecosystem. The lower layer provides tighter control over scheduling, memory, and security policies without the overhead of a general-purpose OS.

### 10.2 Migration Path

**Phase 10a: Design & Planning**
- [ ] Kernel architecture design
- [ ] Language selection (Rust vs Zig vs C++)
- [ ] Microkernel vs monolithic decision
- [ ] System call API design
- [ ] Python integration strategy
- [ ] Hardware support targets (x86_64, ARM, RISC-V)

**Phase 10b: Minimal Kernel**
- [ ] Boot loader implementation
- [ ] Memory management (paging, heap allocation)
- [ ] Process scheduler (basic round-robin)
- [ ] System call interface
- [ ] Basic I/O (keyboard, display)

**Phase 10c: File System & Drivers**
- [ ] VFS (Virtual File System) layer
- [ ] Simple file system implementation
- [ ] Disk and network drivers
- [ ] Basic TCP/IP stack

**Phase 10d: Python Runtime Integration**
- [ ] Embedded Python interpreter in userspace
- [ ] Python syscall bindings
- [ ] Port core Zenus modules to new platform
- [ ] Memory isolation between Python and kernel

**Phase 10e: Tool & Service Migration**
- [ ] Port existing tools (FileOps, SystemOps, etc.)
- [ ] Hybrid approach (Python orchestrates, kernel executes)
- [ ] Service management layer
- [ ] Multi-user support

**Phase 10f: Full OS Release**
- [ ] Complete OS installation ISO
- [ ] Bootable USB/CD image
- [ ] Graphical installer
- [ ] Hardware compatibility testing
- [ ] Documentation (user guide, developer guide)
- [ ] Migration tools from v1.x

### 10.3 Technical Decisions (to be made when Phase 10 begins)

**Kernel language candidates**: Rust (memory safety, growing OS ecosystem), Zig (simplicity, C interop), C++ (mature, proven)

**Kernel architecture candidates**: Microkernel (better isolation, easier to debug), Monolithic (performance, simpler), Hybrid (balance of both)

**Python integration options**: Embedded CPython (full compatibility, larger footprint), MicroPython (tiny footprint, limited stdlib), Hybrid (Python for AI, native for hot paths)

### 10.4 Risks

- Scope is large — realistically a 3+ year effort once started
- Requires kernel and systems programming expertise
- Hardware driver coverage is a major unknown
- Community fragmentation (v1 vs v2 users)
- Fallback: v1.x remains production-ready and will be maintained regardless

### 10.5 Backward Compatibility

- v1.x API compatibility layer planned for v2.0
- v1.x maintained for at least 2 years post-v2.0 release
- Clear migration guides and tooling before any transition

---

## Success Metrics

### User Metrics
- Daily active users
- Commands per user per day
- Success rate (>95% target)
- User retention (7-day, 30-day)
- Net Promoter Score (>50 target)

### Technical Metrics
- P50 latency (<100ms)
- P99 latency (<1s)
- Error rate (<1%)
- Token efficiency (tokens per command)
- Cache hit rate (>70%)

### Business Metrics
- GitHub stars growth
- Community contributions
- Enterprise adoption
- Revenue (if commercial tier)

---

## Open Questions

1. **Licensing**: Keep open-source? Dual license (AGPL + commercial)?
2. **Monetization**: Freemium? Enterprise only? Cloud hosting?
3. **Governance**: Foundation? Corporate-backed? Community-driven?
4. **LLM Strategy**: Partner with providers? Self-host? Hybrid?
5. **Cloud Service**: Offer hosted Zenus? Or self-hosted only?

---

## Get Involved

**Contribute:**
- Code: https://github.com/Guillhermm/zenus
- Ideas: Open a discussion
- Bugs: File an issue
- Docs: Improve documentation

**Priorities**: We focus on what users need most. Feedback drives the roadmap.

---

*Last updated: 2026-04-05 (v1.2.0 — Phase 1.6 complete; Phase 1.7 added; Experiments section added; Phase 8.5 added: Zenus-native model — domain tokenizer, QLoRA distillation pipeline, GGUF CPU deployment, RL continuous improvement, Coconut latent planning, BitNet ternary research path, full cost/time estimates)*
