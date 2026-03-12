# Self-Reflection Guide

**Feature Status**: ✅ Complete and Integrated

Zenus now critiques its own plans before execution, catching mistakes and validating assumptions automatically.

## What It Does

The self-reflection system analyzes execution plans **before running them** to:
- Estimate confidence for each step (0-100%)
- Identify potential issues (ambiguity, missing info, risks)
- Validate assumptions
- Detect prerequisites and dependencies
- Suggest improvements
- **Decide when to ask the user for help**

## How It Works

### 1. Plan Critique
Before executing any plan, Zenus:
1. Analyzes each step individually
2. Estimates confidence level (VERY_HIGH → VERY_LOW)
3. Identifies issues, risks, and assumptions
4. Calculates overall plan confidence
5. Decides whether to proceed or ask for clarification

### 2. Confidence Levels

```python
VERY_HIGH  # >90% confidence - proceed automatically
HIGH       # 70-90% - proceed with caution
MEDIUM     # 50-70% - show warning, proceed
LOW        # 30-50% - warn user, ask for confirmation
VERY_LOW   # <30% - stop and ask for help
```

### 3. Issue Detection

The system detects six types of issues:

- **AMBIGUITY**: Unclear user intent
- **MISSING_INFO**: Need more information to proceed
- **RISKY_OPERATION**: High-risk action (delete, overwrite, etc.)
- **INVALID_ASSUMPTION**: Making bad assumptions about the environment
- **BETTER_APPROACH**: Suboptimal method detected
- **PREREQUISITE**: Missing requirements or dependencies

### 4. Smart User Interaction

The reflection system decides **intelligently** whether to bother the user:

**Ask user when:**
- Overall confidence < 50%
- Critical issues found (VERY_LOW confidence steps)
- Multiple RISKY_OPERATION steps
- Ambiguous intent that could lead to wrong actions

**Proceed automatically when:**
- High confidence (≥70%)
- No critical issues
- Clear intent
- Low-risk operations

## Example Output

```bash
zenus deploy my app to production

🤔 Self-Reflection:
Overall Confidence: 45%
Risk: HIGH - Missing backup step

⚠️  Low Confidence Steps:
  Step 1: deploy
    Confidence: 40%
    Issues: Missing backup, no rollback plan
    Suggestions: Add backup before deploy, prepare rollback

❓ Questions for User:
  1. Do you have a backup of the current version?
  2. Should I create a backup before deploying?
  3. What's the rollback plan if deployment fails?

Continue anyway? (y/n):
```

## Integration with Existing Features

### Works With Adaptive Planner
- Reflection happens **before** the adaptive planner executes
- If issues found, can abort before any actions taken
- Complements retry logic (catch errors before they happen)

### Works With Goal Inference
- Goal inference suggests complete workflows
- Self-reflection validates those workflows
- Together they create comprehensive, safe plans

### Works With Tree of Thoughts
- ToT explores multiple approaches
- Self-reflection evaluates each approach
- Best approach selected based on confidence scores

## Technical Architecture

### Package Structure
```
packages/core/src/zenus_core/brain/
├── self_reflection.py        # Main reflection system
└── llm/
    └── prompts/
        └── reflection.py     # LLM prompts for reflection
```

### Key Classes

#### `SelfReflection`
Main reflection engine:
- `reflect_on_plan()`: Analyzes a complete execution plan
- `reflect_on_step()`: Analyzes a single step
- LLM-powered analysis with structured output
- Fallback mechanism if LLM unavailable

#### `PlanReflection`
Dataclass for complete plan analysis:
- Overall confidence score
- Per-step reflections
- Critical issues list
- User questions (if needed)
- Suggested improvements
- Risk assessment

#### `StepReflection`
Dataclass for single step analysis:
- Confidence level and score
- Issues detected
- Assumptions made
- Risks identified
- Alternative approaches
- Prerequisites needed

### LLM Integration

The system uses the LLM to:
1. Analyze user intent for ambiguity
2. Validate assumptions about the environment
3. Identify potential issues and risks
4. Suggest better approaches
5. Generate helpful questions for the user

**Prompt Example:**
```python
f"""Analyze this execution step:
Tool: {step.tool}
Action: {step.action}
Args: {step.args}

Assess:
1. Confidence (0-100%)
2. Issues (ambiguity, missing_info, risky_operation, etc.)
3. Assumptions being made
4. Potential risks
5. Alternative approaches
6. Prerequisites needed

Return as JSON."""
```

### Fallback Mechanism

If the LLM is unavailable:
- Returns 50% confidence (MEDIUM)
- No specific issues detected
- Graceful degradation - system still works
- User sees warning: "Reflection unavailable - proceed with caution"

## Configuration

### Enable/Disable
```python
# In config or code
orchestrator = Orchestrator(
    enable_reflection=True  # Default: True
)
```

### Confidence Thresholds
```python
# Customize when to ask user
CONFIDENCE_THRESHOLD_ASK = 50  # Ask user if <50%
CONFIDENCE_THRESHOLD_WARN = 70  # Warn if <70%
```

## Why This Matters

**Without Self-Reflection:**
```bash
zenus delete all log files
→ Executing immediately... ❌ Oops, deleted production logs!
```

**With Self-Reflection:**
```bash
zenus delete all log files

🤔 Self-Reflection:
Risk: HIGH - No backup, irreversible deletion

⚠️  Issues:
  - Ambiguous: "all log files" - which directory?
  - Risky: Permanent deletion without backup
  - Missing info: Should archived logs be included?

❓ Questions:
  1. Which directory should I search for log files?
  2. Should I move to trash instead of permanent delete?
  3. Should archived/compressed logs be included?

Continue? (y/n):
```

**Result**: Catches potential disasters before they happen!

## Revolutionary Aspect

**This feature doesn't exist in Cursor or OpenClaw:**
- Cursor executes plans immediately without critique
- OpenClaw executes plans immediately without critique
- **Zenus analyzes its own plans and knows when to ask for help**

No other AI assistant:
- Pre-emptively validates plans before execution
- Estimates confidence per step
- Intelligently decides when to ask vs proceed
- Identifies ambiguity and invalid assumptions
- Suggests improvements proactively

This makes Zenus significantly safer and smarter - it thinks before acting, just like a careful human would.

## Budget

**Estimated Cost**: $1.50
**Actual Cost**: ~$1.50 (implementation + testing)
**Status**: ✅ Complete

## Testing

Test the self-reflection system with:

```bash
# Ambiguous command (should ask for clarification)
zenus delete all files

# Risky operation (should warn)
zenus deploy to production

# Clear, safe command (should proceed automatically)
zenus list files in current directory

# Missing information (should ask questions)
zenus backup database
```

## Future Enhancements

Possible improvements (not in scope for v0.5.0):
- Learn from past mistakes (feedback loop)
- User preference learning (some users want fewer questions)
- Risk profile customization (cautious vs aggressive)
- Confidence calibration (improve accuracy over time)
- Multi-step dependency analysis
- Cost estimation before expensive operations
