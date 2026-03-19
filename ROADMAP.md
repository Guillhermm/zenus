# Zenus Roadmap

**Vision**: An operating system driven by intent, not commands.

This roadmap outlines planned improvements across all phases of Zenus development — from the current system layer to the long-term goal of Zenus becoming a full operating system. All ideas are aspirational; implementation priority is determined by impact and feasibility.

---

## Phase 1: Foundation Hardening (Q2 2026)

### 1.1 Reliability & Production Readiness

**Goal**: Zero-crash, enterprise-grade stability

- [x] **Comprehensive Error Handling** ✅ (v0.5.0 - partial)
  - Graceful degradation for all failure modes (partial)
  - Automatic fallback strategies (LLM → simpler LLM → rule-based) ✅
  - Circuit breakers for external services ✅
  - Retry budget system to prevent infinite retries ✅

- [x] **Testing Infrastructure** ✅ (v1.0.0)
  - Integration tests for all tools ✅
  - E2E tests for common workflows ✅
  - Property-based testing for intent translation ✅ (Hypothesis, 27 invariant tests)
  - Fuzzing for safety policy ✅ (risk=3 always blocks)
  - CI/CD with automated test suite ✅
  - Coverage target: >85% ✅ (88.6%+)

- [x] **Observability** ✅ (v0.4.0 - partial)
  - Performance metrics (latency, token usage, success rate)
  - Real-time statistics
  - Cost tracking
  - Per-model breakdown
  - Historical data access

- [x] **Configuration Management** ✅ (v1.0.0)
  - YAML/TOML config files (not just .env) ✅
  - Config validation with schema ✅
  - Hot-reload without restart ✅ (watchdog + callback observer pattern)
  - Profile system (dev, staging, production) ✅
  - Secrets management ✅ (env/.env + HashiCorp Vault KV v2)

### 1.2 Performance Optimization

**Goal**: <100ms response time for most operations

- [x] **Caching Strategy** ✅ (v0.4.0 - partial)
  - Intent memoization (hash → plan)
  - LLM response streaming
  - 1-hour TTL cache
  - LRU eviction

- [x] **Concurrency** ✅ (v1.0.0)
  - Async/await throughout stack ✅ (LLM base class, AnthropicLLM, Orchestrator)
  - Non-blocking I/O for all network calls ✅ (AsyncAnthropic native client)
  - True parallel execution ✅ (ParallelExecutor with dependency analysis)
  - Background task queue ✅ (stdlib ThreadPoolExecutor, Priority, TaskStatus, no Redis needed)

- [x] **Resource Management** ✅ (v1.0.0)
  - In-memory LRU caching ✅ (SmartCache + IntentCache with disk persistence)
  - HTTP connection pooling ✅ (ConnectionPool via urllib3.PoolManager, shared per process)
  - Rate limiting & backpressure ✅ (retry budget + circuit breaker)
  - Graceful shutdown handling ✅ (BackgroundTaskQueue.shutdown)

---

## Phase 2: Intelligence Amplification (Q3 2026)

### 2.1 Self-Improving AI

**Goal**: System learns from every interaction

- [x] **Feedback Loop** ✅ (v0.4.0)
  - Explicit thumbs up/down on results
  - Success metric tracking per command type
  - Training data export
  - Privacy-aware collection

- [x] **Prompt Evolution** ✅ (v0.5.0 - REVOLUTIONARY!)
  - Auto-tune system prompts based on success rate
  - Generate few-shot examples from history
  - Prompt versioning and rollback
  - Domain-specific prompt variants (dev ops, data science, etc.)
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

**Goal**: Handle complex, multi-step tasks end-to-end

- [x] **Multi-Agent Collaboration** ✅ (v0.5.0 - REVOLUTIONARY!)
  - Spawn specialized sub-agents (research, execution, validation)
  - Agent communication protocol
  - Hierarchical planning (manager → workers)
  - ResearcherAgent, PlannerAgent, ExecutorAgent, ValidatorAgent
  - Complete collaboration workflow tracking

- [x] **Tree of Thoughts** ✅ (v0.5.0 - REVOLUTIONARY!)
  - Generate multiple solution paths
  - Explore alternatives in parallel
  - Intelligent path selection with scoring
  - Shows all alternatives with pros/cons
  - Confidence-based decision making

- [x] **Self-Reflection** ✅ (v0.5.0 - NEW!)
  - Critique own plans before execution
  - Validate assumptions with queries
  - Estimate confidence per step
  - Know when to ask for human input
  - Critical issue detection
  - Intelligent help requests

- [ ] **Knowledge Graph**
  - Build ontology of system state
  - Reason about relationships (file dependencies, service dependencies)
  - Infer implicit requirements
  - Detect contradictions

---

## Phase 3: Multimodal & Accessibility (Q4 2026)

### 3.1 Voice Interface

**Goal**: Hands-free, accessible interaction

- [ ] **Speech-to-Text**
  - Local STT (Whisper)
  - Cloud STT with privacy mode
  - Wake word detection ("Hey Zenus")
  - Noise cancellation
  - Multi-language support

- [ ] **Text-to-Speech**
  - Local TTS (Piper, Coqui)
  - Expressive voices (emotion, emphasis)
  - Streaming TTS (start speaking before complete)
  - Voice profiles (user preferences)

- [ ] **Conversational Flow**
  - Clarifying questions mid-execution
  - Natural interruptions ("wait, stop")
  - Context carryover ("and then do X")
  - Ambient mode (always listening)

### 3.2 Visual Understanding

**Goal**: See what you see, act accordingly

- [x] **Screenshot Analysis** ✅ (v0.5.0 - partial)
  - Describe UI elements ✅
  - Detect errors/warnings ✅
  - Suggest actions ("click the blue button") ✅
  - Accessibility tree extraction (pending)

- [ ] **OCR Integration**
  - Read text from images
  - Extract tables/charts
  - Parse handwritten notes
  - Multi-language OCR

- [ ] **Video Understanding**
  - Analyze screen recordings
  - Detect user actions (clicks, typing)
  - Learn workflows from videos
  - Generate automation scripts

### 3.3 Rich Output

**Goal**: Information presented optimally

- [x] **Data Visualization** ✅ (v0.5.0 - NEW!)
  - Auto-generate charts (matplotlib)
  - Tables with sorting/filtering (Rich)
  - Diff views (before/after)
  - Auto-detects best visualization
  - Multiple chart types (line, bar, pie, histogram, heatmap)
  - Beautiful table formatting

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

## Phase 4: Ecosystem & Integrations (Q1 2027)

### 4.1 Platform Integrations

**Goal**: Work seamlessly with existing tools

- [ ] **Version Control** (partial)
  - Advanced Git operations (rebase, cherry-pick, bisect) (basic ops ✅: clone, commit, push, pull, branch, diff, stash, log)
  - GitHub API integration: Issues ✅ (create, list, close, bulk from ROADMAP.md)
  - PR creation and review
  - GitLab/Bitbucket API integration
  - Commit message generation

- [ ] **Cloud Platforms**
  - AWS CLI automation
  - Azure operations
  - Google Cloud
  - Infrastructure as code (Terraform)
  - Cost optimization suggestions

- [ ] **Databases**
  - SQL query generation & execution
  - Schema migrations
  - Data import/export
  - Index optimization
  - Query performance analysis

- [ ] **Containers & Orchestration**
  - Docker Compose generation
  - Kubernetes management
  - Helm charts
  - Service mesh operations
  - Log aggregation

- [ ] **CI/CD**
  - GitHub Actions workflow generation
  - Jenkins pipeline creation
  - Build failure diagnosis
  - Deployment automation
  - Rollback strategies

### 4.2 Communication Platforms

**Goal**: Zenus as a team member

- [ ] **Chat Integrations**
  - Slack bot
  - Discord bot
  - Microsoft Teams
  - Telegram bot
  - Matrix/Element

- [ ] **Email Automation**
  - Email parsing & action extraction
  - Automated responses
  - Newsletter management
  - Calendar integration

- [ ] **Notifications**
  - Desktop notifications
  - Push notifications (mobile)
  - SMS alerts (critical only)
  - Webhook callbacks

### 4.3 Development Tools

**Goal**: Augment developer workflow

- [ ] **Code Operations**
  - Intelligent code generation
  - Refactoring (rename, extract method)
  - Bug detection and fixes
  - Test generation
  - Documentation generation
  - Code review comments

- [ ] **IDE Extensions**
  - VS Code extension
  - JetBrains plugin
  - Vim/Neovim plugin
  - Inline suggestions
  - Contextual commands

- [ ] **API Testing**
  - Generate curl/HTTP requests
  - Parse responses
  - Schema validation
  - Load testing
  - Mock server generation

- [ ] **Security Scanning**
  - Dependency vulnerability check
  - Secret detection
  - SAST integration
  - Compliance validation

---

## Phase 5: Collaboration & Enterprise (Q2 2027)

### 5.1 Multi-User Support

**Goal**: Team-friendly features

- [ ] **User Management**
  - User accounts and authentication
  - SSO integration (OAuth, SAML)
  - MFA support
  - Session management

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
  - Environment variable management

### 5.2 Enterprise Features

**Goal**: Production-ready for large organizations

- [ ] **Compliance & Auditing**
  - SOC 2 Type II compliance
  - GDPR compliance (data retention policies)
  - HIPAA support (PHI handling)
  - Comprehensive audit logs
  - Tamper-proof logging

- [ ] **High Availability**
  - Clustered deployment
  - Load balancing
  - Automatic failover
  - Backup and disaster recovery
  - Zero-downtime updates

- [ ] **Multi-Tenancy**
  - Tenant isolation
  - Resource quotas per tenant
  - Billing integration
  - Custom branding

- [ ] **SLA & Support**
  - Uptime monitoring
  - Incident management
  - Escalation procedures
  - Professional support tier

---

## Phase 6: Autonomy & Proactivity (Q3 2027)

### 6.1 Background Agent

**Goal**: Zenus works while you sleep

- [ ] **Scheduled Tasks**
  - Cron-like scheduling
  - Event-driven triggers
  - Chained workflows
  - Conditional execution

- [x] **Proactive Monitoring** ✅ (v0.5.0 - REVOLUTIONARY!)
  - Watch for system issues (disk full, memory leak)
  - Alert before problems occur
  - Auto-remediation (restart service, clear cache)
  - Health checks for services
  - Disk, memory, service, log, SSL certificate monitoring
  - Automatic issue fixing with safety logging

- [ ] **Maintenance Automation**
  - Automatic updates (OS, packages, dependencies)
  - Log rotation
  - Backup verification
  - Security patching

- [ ] **Learning User Patterns** (partial)
  - Predict next commands (partial — pattern detection implemented)
  - Suggest optimizations ✅ (SuggestionEngine via pattern analysis)
  - Automate repetitive workflows ✅ (WorkflowRecorder — record, save, replay)
  - Pre-fetch likely results

### 6.2 Intelligent Assistance

**Goal**: Anticipate needs, not just respond

- [x] **Contextual Suggestions** ✅ (v0.5.0 - partial)
  - "You usually do X after Y, want me to do it?" ✅ (SuggestionEngine)
  - "This file hasn't been backed up in 30 days" (pending)
  - "Your project dependencies are outdated" (pending)

- [x] **Goal Inference** ✅ (v0.5.0 - REVOLUTIONARY!)
  - Infer high-level goals from commands
  - Propose complete workflows
  - Fill in implicit steps
  - Detects 11 goal types (deploy, debug, migrate, security, etc.)
  - Adds safety steps automatically (backups, tests, verification)
  - Interactive workflow approval

- [ ] **Habit Formation**
  - Track good practices
  - Gentle nudges for best practices
  - Gamification (streaks, achievements)

---

## Phase 7: Distributed & Edge (Q4 2027)

### 7.1 Multi-Machine Orchestration

**Goal**: Manage entire infrastructure

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
  - Event mesh integration
  - Service discovery

### 7.2 Edge Computing

**Goal**: Run anywhere, even offline

- [ ] **Offline Mode**
  - Local LLM fallback
  - Cached commands work offline
  - Sync when online
  - Conflict resolution

- [ ] **Edge Devices**
  - Raspberry Pi support
  - IoT device management
  - ARM architecture optimization
  - Low-power mode

- [ ] **Embedded Zenus**
  - Zenus as library (not just CLI)
  - Embeddable in other apps
  - REST API server mode
  - gRPC service

---

## Phase 8: AI Safety & Ethics (Q1 2028)

### 8.1 Safety Mechanisms

**Goal**: Prevent harm, respect boundaries

- [ ] **Enhanced Sandboxing**
  - Mandatory dry-run for destructive ops
  - Undo stack with snapshots
  - Blast radius estimation
  - Capability-based security

- [ ] **Interpretability**
  - Explain every decision in plain language
  - Confidence scores per action
  - Alternative approaches shown
  - Reasoning chains visualized

- [ ] **Kill Switches**
  - Emergency stop (Ctrl+C+C)
  - Panic mode (undo recent actions)
  - Rate limiting (max X ops per minute)
  - Human-in-the-loop for high-risk

### 8.2 Ethical AI

**Goal**: Responsible, fair, transparent

- [ ] **Bias Detection**
  - Monitor for biased suggestions
  - Fairness metrics
  - Debiasing techniques

- [ ] **Privacy Protection**
  - Local-first architecture
  - Differential privacy
  - Data minimization
  - Right to be forgotten

- [ ] **Transparency**
  - Open-source models prioritized
  - Model cards for all LLMs
  - Data provenance tracking
  - Carbon footprint estimation

---

## Phase 9: Beyond Terminals (Q2 2028)

### 9.1 New Interfaces

**Goal**: Meet users where they are

- [ ] **AR/VR**
  - Spatial command interface
  - 3D visualization of file systems
  - Gesture controls

- [ ] **Wearables**
  - Smartwatch quick commands
  - AR glasses integration
  - Brain-computer interface (future)

- [ ] **Natural Interfaces**
  - Write commands in email
  - Speak to smart speakers
  - SMS commands

### 9.2 Physical World Integration

**Goal**: Bridge digital and physical

- [ ] **Smart Home**
  - Control IoT devices
  - Home automation routines
  - Energy optimization

- [ ] **Robotics**
  - ROS integration
  - Robot task planning
  - Sensor data analysis

---

## Phase 10: Operating System Transition (Q3 2027 - Q4 2028)

### 10.1 Vision: From Python App to True OS

**Goal**: Transform Zenus from a Python-based AI assistant into a true operating system managing hardware, processes, and resources at the kernel level.

**Why This Matters**:
- **Direct hardware control**: Remove OS abstraction layer
- **Better performance**: Native execution without Python/OS overhead
- **Enhanced security**: Kernel-level isolation and protection
- **Full system control**: Process scheduling, memory management, device drivers
- **Keep AI power**: Python AI/ML layer on top of custom kernel

### 10.2 Current vs Future Architecture

**Current State (v0.x - v1.x)**:
```
User → Python App (Zenus) → Linux/macOS/Windows → Hardware
```
- Python-based application running on existing OS
- High-level system operations through OS APIs
- Excellent for rapid development and AI integration
- Limited control over hardware and system resources

**Target State (v2.0+)**:
```
User → Python AI Layer → Custom OS Kernel (Rust/C++) → Hardware
```
- Low-level OS kernel managing hardware directly
- Python layer for AI/ML intelligence on top
- Direct process, memory, and device management
- Custom file system and drivers

### 10.3 Hybrid Architecture Design

**Three-Layer System**:

```mermaid
graph TD
    A[AI/ML Intelligence Layer Python<br/>• LLM integration Claude, DeepSeek<br/>• Intent translation & understanding<br/>• Context management & memory<br/>• Machine learning models<br/>• High-level orchestration<br/>• All current Zenus features]
    
    A -->|High-level API syscall-like| B[Orchestration/Services Layer Rust/C++<br/>• Process management & scheduling<br/>• Resource allocation & limits<br/>• Security policy enforcement<br/>• IPC Inter-Process Communication<br/>• Service management<br/>• Network stack]
    
    B -->|System calls| C[Kernel Layer Rust/C++/Zig<br/>• Hardware abstraction HAL<br/>• Memory management paging, allocation<br/>• Device drivers disk, network, GPU<br/>• File system implementation<br/>• Interrupt handling<br/>• Boot loader]
    
    C --> D[Hardware<br/>CPU, RAM, Disk, Network, GPU, etc.]
    
    style A fill:#fff4e6
    style B fill:#e8f5e9
    style C fill:#f3e5f5
    style D fill:#fce4ec
```

**Why This Design**:
1. **Preserve Python's Strengths**: AI/ML ecosystem, rapid development, extensive libraries
2. **Add OS-Level Power**: Direct hardware control, performance, security
3. **Best of Both Worlds**: Intelligence (Python) + Control (Kernel)
4. **Gradual Migration**: Can migrate components incrementally

### 10.4 Migration Path

**Phase 10a: Design & Planning (Q3 2027)**
- [ ] Kernel architecture design
- [ ] Choose kernel language (Rust vs C++ vs Zig)
- [ ] Microkernel vs Monolithic decision
- [ ] System call API design
- [ ] Python integration strategy
- [ ] Hardware support targets (x86_64, ARM, RISC-V)

**Phase 10b: Minimal Kernel (Q4 2027)**
- [ ] Boot loader implementation
- [ ] Memory management (paging, heap allocation)
- [ ] Process scheduler (basic round-robin)
- [ ] System call interface
- [ ] Basic I/O (keyboard, display)
- [ ] Hello World from bare metal!

**Phase 10c: File System & Drivers (Q1 2028)**
- [ ] VFS (Virtual File System) layer
- [ ] Simple file system implementation (ext2-like)
- [ ] Disk driver (AHCI/NVMe)
- [ ] Network driver (E1000/virtio-net)
- [ ] Basic networking stack (TCP/IP)

**Phase 10d: Python Runtime Integration (Q2 2028)**
- [ ] Embedded Python interpreter in kernel/userspace
- [ ] Python syscall bindings
- [ ] Port core Zenus modules to new platform
- [ ] Memory isolation between Python and kernel
- [ ] Error handling across language boundary

**Phase 10e: Tool & Service Migration (Q3 2028)**
- [ ] Port existing tools (FileOps, SystemOps, etc.)
- [ ] Implement native equivalents for performance
- [ ] Hybrid approach (Python orchestrates, kernel executes)
- [ ] Service management layer
- [ ] Multi-user support

**Phase 10f: Full OS Release - Zenus 2.0 (Q4 2028)**
- [ ] Complete OS installation ISO
- [ ] Bootable USB/CD image
- [ ] Graphical installer
- [ ] Hardware compatibility testing
- [ ] Documentation (user guide, developer guide)
- [ ] Migration tools from v1.x
- [ ] Public beta release

### 10.5 Technical Decisions To Make

**Kernel Programming Language**:
- **Rust**: Memory safety, modern tooling, growing ecosystem
  - Pros: Safety guarantees, no GC, package manager (Cargo)
  - Cons: Steep learning curve, compiler can be strict
  - Examples: Redox OS, Tock OS
  
- **C++**: Performance, mature ecosystem, compatibility
  - Pros: Highly optimized, vast libraries, familiar to many
  - Cons: Easy to make mistakes, manual memory management
  - Examples: Windows NT, QNX
  
- **Zig**: Simplicity, C interop, explicit control
  - Pros: Simple syntax, great C interop, explicit allocations
  - Cons: Less mature, smaller ecosystem
  - Examples: Helios OS (in development)

**Kernel Architecture**:
- **Microkernel**: Minimal kernel, services in userspace
  - Pros: Better isolation, easier to debug, modularity
  - Cons: IPC overhead, complexity
  - Examples: Minix, seL4
  
- **Monolithic**: Everything in kernel
  - Pros: Performance, simpler design
  - Cons: Harder to maintain, less isolation
  - Examples: Linux, FreeBSD

- **Hybrid**: Core in kernel, services split
  - Pros: Balance of performance and modularity
  - Cons: Can be complex
  - Examples: Windows NT, macOS XNU

**Python Integration**:
- **Embedded CPython**: Full Python runtime in userspace
  - Pros: Full compatibility, standard library available
  - Cons: Large memory footprint, startup time
  
- **MicroPython**: Minimal Python for embedded
  - Pros: Tiny footprint, fast startup
  - Cons: Limited standard library, some incompatibilities
  
- **Hybrid**: Python for AI, native code for performance paths
  - Pros: Optimal performance and convenience
  - Cons: Complexity in boundary management

### 10.6 Backward Compatibility

**Supporting Existing Zenus (v1.x) Users**:
- [ ] Compatibility layer (Zenus 1.x API on Zenus 2.0)
- [ ] Migration scripts (convert configs, data)
- [ ] Dual-boot support
- [ ] Virtual machine mode (run old Zenus in VM)
- [ ] Gradual feature parity

**Long-term Plan**:
- v1.x maintained for 2 years post-v2.0 release
- Security updates for v1.x until 2030
- Clear migration guides and tooling
- Community support during transition

### 10.7 Challenges & Risks

**Technical Challenges**:
- Hardware driver development (huge effort)
- Python-kernel boundary performance
- Memory safety across language boundaries
- Debugging kernel-level code
- Hardware compatibility testing

**Project Risks**:
- Scope is massive (2-3 year effort)
- Requires specialized expertise
- Community fragmentation (v1 vs v2)
- Competition from established OSes
- Resource intensive (time, money, contributors)

**Mitigation**:
- Start small (minimal viable kernel)
- Incremental delivery (usable at each phase)
- Extensive testing (QEMU, real hardware)
- Community involvement (open development)
- Fallback: v1.x remains production-ready

### 10.8 Success Criteria

**Phase 10 Complete When**:
- ✅ Boots on bare metal (x86_64)
- ✅ Python interpreter runs in userspace
- ✅ File system reads/writes work
- ✅ Network stack operational
- ✅ At least 10 core Zenus tools ported
- ✅ Installation ISO available
- ✅ Documentation complete
- ✅ 100+ beta testers successfully migrated

### 10.9 Why Build This?

**Long-Term Vision**:
1. **True System Intelligence**: AI that understands hardware, not just APIs
2. **Performance**: Remove OS abstraction overhead
3. **Security**: Kernel-level safety policies
4. **Innovation**: Rethink OS design with AI-first principles
5. **Differentiation**: No other AI assistant owns the full stack

**What This Enables**:
- AI-optimized process scheduling
- Intelligent memory management (predict usage patterns)
- Security policies enforced in kernel
- Hardware resource optimization
- Custom file system designed for AI workloads
- Native vector/tensor operations in kernel

This is the ultimate evolution: **Zenus becomes an actual operating system, not just a system manager.**

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

Things to decide as we build:

1. **Licensing**: Keep open-source? Dual license (AGPL + commercial)?
2. **Monetization**: Freemium? Enterprise only? Cloud hosting?
3. **Governance**: Foundation? Corporate-backed? Community-driven?
4. **LLM Strategy**: Partner with providers? Self-host? Hybrid?
5. **Cloud Service**: Offer hosted Zenus? Or self-hosted only?

---

## Get Involved

This is an ambitious roadmap. We can't build it alone.

**Contribute:**
- Code: https://github.com/Guillhermm/zenus
- Ideas: Open a discussion
- Bugs: File an issue
- Docs: Improve documentation

**Priorities**: We'll focus on what users need most. Feedback drives the roadmap.

---

*Last updated: 2026-03-10*
