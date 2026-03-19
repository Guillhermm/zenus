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

- [ ] **Knowledge Graph**
  - Build ontology of system state
  - Reason about relationships (file dependencies, service dependencies)
  - Infer implicit requirements
  - Detect contradictions

---

## Phase 3: Multimodal & Accessibility — target: by December 2026

### 3.1 Voice Interface

- [ ] **Speech-to-Text**
  - Local STT (Whisper)
  - Cloud STT with privacy mode
  - Wake word detection ("Hey Zenus")
  - Noise cancellation and multi-language support

- [ ] **Text-to-Speech**
  - Local TTS (Piper, Coqui)
  - Streaming TTS (start speaking before completion)
  - Voice profiles (user preferences)

- [ ] **Conversational Flow**
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

*Last updated: 2026-03-19*
