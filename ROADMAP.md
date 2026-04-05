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

## Phase 1.6: Agentic Harness Hardening — target: by September 2026

*Each entry is classified by **Impact** (H/M/L) and **Adaptation Difficulty** for Zenus (H/M/L)*

### 1.6.1 Hook Pipeline — PreToolUse / PostToolUse [Impact: H | Difficulty: M]

- [ ] **PreToolUse hooks**: configurable shell or Python callbacks invoked before any tool executes
  - Can mutate tool inputs, deny execution based on conditions, or emit structured audit entries
  - Configured in `config.yaml` under `hooks.pre_tool_use[].match` + `hooks.pre_tool_use[].command`
- [ ] **PostToolUse hooks**: callbacks invoked after tool execution with access to the full result
  - Can transform outputs, trigger notifications, write structured events, or chain follow-up actions
- [ ] `/hooks` slash command: list all configured hooks, show which fired last session, test a hook inline

### 1.6.2 Plan Mode [Impact: H | Difficulty: M]

- [ ] **Plan-only execution mode**: agent proposes a complete, numbered step-by-step plan and cannot execute any step until the user explicitly approves the full plan
  - `EnterPlanMode` / `ExitPlanMode` as callable tools so agents can self-restrict while reasoning
  - `/plan` slash command to toggle plan mode interactively in CLI and TUI
  - Design note: `SandboxedAdaptivePlanner` already exists — this adds a hard gate that prevents any side-effectful tool from firing while in plan mode

### 1.6.3 Context & Session Management [Impact: H | Difficulty: M]

- [ ] **Context window compaction** (`/compact`): summarize and compress conversation history as token count approaches model context limits
  - Triggered manually or automatically when >80% of context is consumed
  - Preserves intent, tool call history, and key facts; discards verbatim intermediate output
  - Summary written back as a synthetic assistant turn; model continues without losing state
- [ ] **Multi-directory context** (`/add-dir`): add additional working directories to the active session
  - Zenus currently operates on a single `cwd`; `/add-dir` enables monorepo or multi-package workflows
  - Each directory is resolved, validated for access permissions, and added to the file tool search roots
- [ ] **Session resume**: persist full session state (conversation, tool history, intent, cost) to disk
  - Sessions get a short auto-generated name and a monotonic ID
  - `/session` command to list, inspect, and resume past sessions
  - `zenus resume <session-id>` from the CLI

### 1.6.4 Background Task System [Impact: H | Difficulty: M]

- [ ] **Formal task lifecycle tools**: `TaskCreate`, `TaskList`, `TaskGet`, `TaskStop`, `TaskUpdate`, `TaskOutput`
  - Agents can spawn long-running background tasks and poll their stdout/stderr mid-execution
  - Tasks survive session boundaries when persisted; accessible via `/tasks` command
  - Design note: Zenus already has a `ThreadPoolExecutor` background queue — this adds a user-visible, agent-addressable API on top
- [ ] **ScheduleCronTool**: agent-initiated cron registration — register a recurring job from within an execution plan
  - Integrates with Phase 6.1 Scheduled Tasks; generates a crontab entry or internal scheduler record
- [ ] **RemoteTriggerTool**: fire a named remote agent trigger from within a local execution (webhook-style callback to a registered endpoint)

### 1.6.5 Git Worktree Support [Impact: H | Difficulty: L]

- [ ] **EnterWorktree / ExitWorktree tools**: create an isolated git worktree for risky or exploratory code changes
  - Agent works exclusively in the worktree; main working tree is never modified
  - On `ExitWorktree`: cleaned up automatically if no net changes; branch name returned to caller if changes were committed
  - Pairs naturally with Plan Mode and the Phase 5.5 Sandboxed Intent Simulation
  - This is a low-difficulty, high-safety win — the `git worktree` plumbing is already in git

### 1.6.6 Developer Experience Primitives [Impact: M | Difficulty: L]

- [ ] **`/doctor`**: system diagnostics — verify API reachability, config schema validity, tool prerequisites, MCP server connectivity, and Python environment health; print a clear pass/fail table
- [ ] **ToolSearchTool**: allow agents to search the available tool registry by name or description at runtime — essential once the plugin ecosystem grows beyond a handful of tools
- [ ] **AskUserQuestion as a formal tool**: agents invoke `AskUserQuestion` to pause execution and prompt the user for structured input (options, free-text, confirmation) mid-plan
  - Currently user prompts are handled implicitly in the Orchestrator's confirmation logic; formalizing this as a tool gives agents explicit control and structured return values
- [ ] **SleepTool**: agent-callable sleep/wait primitive — useful for polling loops, rate-limit back-off, and timed retry patterns without spinning
- [ ] **`/output-style`**: switch between output rendering modes (rich Markdown, compact plain-text, machine-readable JSON) — enables piping Zenus output into other tools or scripts

### 1.6.7 Skills Registry [Impact: H | Difficulty: M]

- [ ] **User-extensible skill system**: auto-discover and load `.zenus/skills/*.md` files as slash commands at startup
  - Each skill is a Markdown file with a YAML front-matter trigger, description, and natural-language prompt body
  - Skills compose with MCP and plugin tools; a skill can reference any registered tool action
- [ ] **`/skills` command**: list available built-in and user-defined skills, show detail, reload without restart
- [ ] **Bundled built-in skills**: ship a curated default skill set (e.g. `commit`, `review-pr`, `simplify`, `explain`, `test-coverage`) that work out of the box
- [ ] **MCP skill builders**: expose bundled skills as MCP tools so external MCP clients can invoke them

### 1.6.8 Jupyter Notebook Support [Impact: M | Difficulty: M]

- [ ] **NotebookEditTool**: read and edit Jupyter `.ipynb` cells with proper cell-type awareness (code, markdown, raw)
  - Understands notebook structure: cell indices, cell outputs, kernel metadata
  - Enables data science and ML workflows where notebooks are primary artifacts
  - Pairs with the existing Screenshot Analysis (Phase 3.2) and Data Visualization (Phase 3.3)

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

*Last updated: 2026-04-05 (v1.1.0 — Phase 1.6 added: systematic CC/claw-code harness analysis — hooks pipeline, plan mode, context compaction, multi-dir context, session resume, background task system, git worktree support, developer experience primitives, skills registry, notebook support; LSP integration added to Phase 4.3; session sharing, settings sync, GitHub/Slack app wizards added to Phase 5.1; upstream proxy and teleport added to Phase 7.1; extended thinking visualization and per-tool sandbox toggle added to Phase 8.1)*
