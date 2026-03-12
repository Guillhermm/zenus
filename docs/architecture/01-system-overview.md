# Zenus - System Architecture Overview

## Core Philosophy

Zenus is a cognitive operating layer that translates human intent into safe, deterministic system actions. Unlike conversational AI assistants, Zenus operates through formal intermediate representations with explicit safety contracts.

## High-Level Architecture

```mermaid
graph TB
    User[User Input<br/>Voice/Text/CLI]
    Router[CLI Router]
    Orchestrator[Orchestrator]
    LLM[LLM Backend<br/>OpenAI/DeepSeek]
    IR[Intent IR<br/>Validated Schema]
    Planner[Adaptive Planner]
    Safety[Safety Policy]
    Tools[Tool Registry]
    Audit[Audit Logger]
    
    User --> Router
    Router --> Orchestrator
    Orchestrator --> LLM
    LLM --> IR
    IR --> Planner
    Planner --> Safety
    Safety --> Tools
    Tools --> Audit
    Audit --> User
    
    style IR fill:#4a9eff
    style Safety fill:#ff6b6b
    style Tools fill:#51cf66
```

## Component Responsibilities

### CLI Layer
- **Router**: Parse arguments, route to modes (help/version/shell/direct)
- **Orchestrator**: Manage full pipeline, handle confirmations, coordinate execution

### Brain Layer
- **LLM Backend**: Translate natural language to Intent IR
- **Planner**: Execute plans with observation and adaptation
- **Memory**: Context retention and learning (future)

### Execution Layer
- **Tools**: FileOps, SystemOps, ProcessOps with explicit contracts
- **Safety Policy**: Risk assessment and permission gates
- **Audit Logger**: JSONL logs for all operations

## Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant L as LLM
    participant P as Planner
    participant S as Safety
    participant T as Tool
    participant A as Audit
    
    U->>O: "organize downloads by type"
    O->>L: translate_intent(input)
    L->>O: IntentIR
    O->>A: log_intent(IR)
    O->>U: Show plan
    U->>O: Confirm
    O->>P: execute_plan(IR)
    
    loop For each step
        P->>S: check_step(step)
        S->>P: ✓ allowed
        P->>T: execute(step)
        T->>P: result
        P->>A: log_step_result(result)
    end
    
    P->>O: summary
    O->>U: Report completion
```

## Key Design Decisions

### 1. Intent IR as Contract
All LLM outputs must conform to IntentIR schema. Raw text never executes.

### 2. Safety First
Every operation has explicit risk level (0-3). High-risk operations require confirmation.

### 3. Auditability
Every intent, plan, and execution is logged to `~/.zenus/logs/` in structured JSONL.

### 4. LLM Backend Agnostic
Abstract interface allows swapping OpenAI, DeepSeek, or local models without changing core.

### 5. Tool Contracts
Tools declare capabilities, arguments, and risk levels explicitly.

## Future Architecture

```mermaid
graph TB
    subgraph "Cognitive Layer (Python)"
        Intent[Intent Parser]
        Plan[Adaptive Planner]
        Mem[Memory System]
    end
    
    subgraph "Execution Layer (Rust/Go)"
        Sandbox[Sandboxed Executor]
        Priv[Privilege Manager]
    end
    
    subgraph "System Layer (Linux)"
        Kernel[Linux Kernel]
        FS[Filesystem]
        Proc[Processes]
    end
    
    Intent --> Plan
    Plan --> Mem
    Plan --> Sandbox
    Sandbox --> Priv
    Priv --> Kernel
    Kernel --> FS
    Kernel --> Proc
    
    style Intent fill:#4a9eff
    style Sandbox fill:#ff6b6b
    style Kernel fill:#868e96
```

## Comparison: OpenClaw vs Zenus

| Aspect | OpenClaw | Zenus |
|--------|----------|----------|
| Interaction | Conversational | Intent-driven |
| Safety | Plugin marketplace | Formal contracts |
| Execution | Flexible, async | Deterministic, validated |
| Architecture | Agent + tools | OS layer + tools |
| Focus | Task automation | System control |

Zenus is not trying to be more flexible than OpenClaw. It's trying to be more correct.
