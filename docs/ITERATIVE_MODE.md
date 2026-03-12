# Iterative Execution Mode (ReAct Loop)

## Overview

Zenus now supports **iterative execution** using the ReAct (Reasoning + Acting) pattern. This allows Zenus to solve complex, multi-step problems by continuously planning, executing, observing, and re-planning until the goal is achieved.

## Problem Solved

**Before (One-Shot Execution):**
```
User: "Read LaTeX project and improve chapter 3"
Zenus:
  1. Plans: [read main.tex, list chapters/]
  2. Executes: [reads main.tex, lists chapters/]  
  3. Stops ❌ (doesn't actually read chapters or make improvements)
```

**After (Iterative Execution):**
```
User: "Read LaTeX project and improve chapter 3"
Zenus:
  Iteration 1: Plans [read main.tex] → Observes: "imports chapters/03-methods.tex"
  Iteration 2: Plans [read chapters/03-methods.tex] → Observes: "chapter content"
  Iteration 3: Plans [analyze weaknesses] → Observes: "weak methodology section"
  Iteration 4: Plans [improve methodology] → Executes: Updates file
  Iteration 5: Reflects → Goal achieved ✓
```

## Usage

### Command Line

Use the `--iterative` flag for complex tasks:

```bash
# Simple one-shot task (default)
zenus "list files in ~/Documents"

# Complex multi-step task (iterative)
zenus --iterative "read my LaTeX project and improve chapter 3"
zenus --iterative "organize my downloads folder by file type and date"
zenus --iterative "find all Python files, analyze them, and generate documentation"
```

### Interactive Shell

Use `--iterative` flag within the shell:

```bash
zenus shell

zenus > --iterative read project and improve readme
zenus > --iterative analyze codebase and suggest refactorings
```

## How It Works

### ReAct Loop Architecture

```
┌─────────────────────────────────────────────┐
│  User Goal: "Complex multi-step task"      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│  Iteration 1                               │
├────────────────────────────────────────────┤
│  1. Plan next steps (based on context)     │
│  2. Execute plan                           │
│  3. Observe results                        │
│  4. Add observations to context            │
│  5. Reflect: Goal achieved? No → Continue  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│  Iteration 2                               │
├────────────────────────────────────────────┤
│  1. Re-plan (with previous observations)   │
│  2. Execute new plan                       │
│  3. Observe new results                    │
│  4. Accumulate observations                │
│  5. Reflect: Goal achieved? No → Continue  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
              ...continues...
                 │
                 ▼
┌────────────────────────────────────────────┐
│  Iteration N                               │
├────────────────────────────────────────────┤
│  1. Re-plan (with all observations)        │
│  2. Execute final steps                    │
│  3. Observe final results                  │
│  4. Full context accumulated               │
│  5. Reflect: Goal achieved? Yes ✓          │
└────────────────┬────────────────────────────┘
                 │
                 ▼
         Task Complete!
```

### Key Components

#### 1. GoalTracker (`src/brain/goal_tracker.py`)

Determines when a goal has been achieved:
- Uses LLM to reflect on observations
- Checks confidence level
- Suggests next steps if goal not achieved
- Prevents infinite loops (max_iterations)

#### 2. Context Accumulation

Each iteration builds on previous knowledge:
- Previous observations are added to context
- LLM sees full history when planning
- Recent observations weighted more heavily

#### 3. Reflection Prompts

LLM evaluates its own progress:
- **ACHIEVED**: Yes/No
- **CONFIDENCE**: 0.0-1.0
- **REASONING**: Explanation
- **NEXT_STEPS**: Suggested actions if not complete

## Configuration

### Max Iterations

Default: 10 iterations

Change in code:
```python
# In src/zenusd/main.py
result = orchestrator.execute_iterative(
    command.input_text,
    max_iterations=20,  # Increase for very complex tasks
    dry_run=dry_run
)
```

Or programmatically:
```python
from cli.orchestrator import Orchestrator

orchestrator = Orchestrator()
result = orchestrator.execute_iterative(
    "complex task",
    max_iterations=15
)
```

### Iteration Safety

To prevent infinite loops:
- **Default max**: 10 iterations
- **Hard stop**: Returns "incomplete" after max iterations
- **Reasoning**: Included in final message

## Examples

### Example 1: Reading and Analyzing LaTeX Project

```bash
zenus --iterative "read my LaTeX thesis in ~/thesis/, understand structure, and suggest improvements to chapter 3"
```

**Output:**
```
Starting iterative execution: read my LaTeX thesis...
Max iterations: 10

═══ Iteration 1/10 ═══
→ Goal: Read main.tex to understand thesis structure
  Step 1: TextOps.read → thesis imports 5 chapters from chapters/

Reflecting on progress...
⟳ Goal not yet achieved
Confidence: 40%
Reasoning: Found main file but haven't read chapters yet
Next steps suggested:
  • Read chapters/03-methodology.tex
  • Analyze content structure

═══ Iteration 2/10 ═══
→ Goal: Read chapter 3 content
  Step 1: TextOps.read → Chapter discusses research methods...

Reflecting on progress...
⟳ Goal not yet achieved
Confidence: 70%
Reasoning: Chapter read, but improvements not yet identified
Next steps suggested:
  • Analyze methodology section structure
  • Identify weak points

═══ Iteration 3/10 ═══
→ Goal: Identify improvements for chapter 3
  Step 1: Observation → Weak areas: lack of justification for sampling method

Reflecting on progress...
⟳ Goal not yet achieved
Confidence: 85%
Reasoning: Improvements identified but not yet implemented
Next steps suggested:
  • Suggest specific additions for methodology justification

═══ Iteration 4/10 ═══
→ Goal: Suggest improvements
  Result: Generated 3 specific suggestions for chapter 3

Reflecting on progress...
✓ Goal Achieved!
All suggestions provided for improving chapter 3

Task completed in 4 iterations
```

### Example 2: Complex File Organization

```bash
zenus --iterative "organize ~/Downloads by file type, then by date, and move duplicates to a separate folder"
```

**Execution:**
- Iteration 1: Scan Downloads folder
- Iteration 2: Identify file types (images, PDFs, videos, etc.)
- Iteration 3: Create type-based folders
- Iteration 4: Move files to type folders
- Iteration 5: Within each folder, organize by date
- Iteration 6: Find duplicates
- Iteration 7: Create "Duplicates" folder
- Iteration 8: Move duplicates
- Goal achieved ✓

## When to Use Iterative Mode

### Use `--iterative` for:

✅ **Multi-step tasks** where each step depends on previous results
✅ **Exploration tasks** (e.g., "read project and understand structure")
✅ **Analysis + action** (e.g., "analyze code and refactor")
✅ **Complex workflows** requiring multiple tool calls
✅ **Uncertain scope** where you don't know exactly what's needed upfront

### Use standard mode (no flag) for:

✅ **Simple one-shot tasks** (e.g., "list files", "create folder")
✅ **Well-defined actions** with clear single steps
✅ **Quick information queries**
✅ **Tasks where you know exactly what to do**

## Technical Details

### Observation Format

Each step generates an observation:
```
{tool}.{action} → {result_summary}
```

Example:
```
FileOps.scan → Found 15 files in ~/Documents
TextOps.read → File contains 243 lines of Python code
```

### Context Building

Enhanced input sent to LLM each iteration:
```
{original_user_goal}

Context: {memory_context}

Previous observations:
- FileOps.scan → Found 15 files
- TextOps.read → main.py has 243 lines
- SystemOps.cpu_info → CPU usage at 45%
```

### Reflection Trigger

After each iteration, GoalTracker asks LLM:
```markdown
# Goal Achievement Reflection

**User's Goal:** {original_goal}
**Original Plan:** {plan_steps}
**Observations:** {all_observations}

Has the goal been fully achieved?
What is your confidence level?
Why do you believe this?
If not achieved, what are the next logical steps?
```

## Limitations

1. **Token consumption**: Each iteration uses LLM tokens (plan + reflection)
2. **Time**: Complex tasks may take several iterations (30s - 2min)
3. **LLM quality**: Reflection quality depends on underlying model
4. **Max iterations**: Hard cap prevents infinite loops but may stop before completion
5. **Cost**: More API calls = higher cost for API-based LLMs

## Future Enhancements

- [ ] Dynamic max_iterations based on task complexity
- [ ] Confidence threshold tuning
- [ ] Observation summarization for very long iterations
- [ ] Parallel execution of independent sub-goals
- [ ] Learning from past successful iterations
- [ ] User interrupt/continue during iteration

## Testing

Run GoalTracker tests:
```bash
cd ~/projects/zenus
source .venv/bin/activate
pytest tests/test_goal_tracker.py -v
```

Expected: 7 tests passing

## Architecture Files

- **GoalTracker**: `src/brain/goal_tracker.py`
- **Iterative Orchestrator**: `src/cli/orchestrator.py` → `execute_iterative()`
- **LLM Reflection**: `src/brain/llm/base.py` → `reflect_on_goal()`
- **CLI Router**: `src/cli/router.py` → `--iterative` flag parsing
- **Entry Point**: `src/zenusd/main.py` → routing to iterative execution

## Troubleshooting

### "Maximum iterations reached"

**Cause**: Task too complex or ill-defined for current max_iterations

**Solutions:**
- Increase max_iterations (see Configuration above)
- Break task into smaller sub-tasks
- Make goal more specific

### "Goal not achieved after reflection"

**Cause**: LLM incorrectly thinks goal is complete

**Solutions:**
- Make goal statement more explicit
- Add success criteria to task description
- Check if observations contain expected results

### Very slow execution

**Cause**: Each iteration requires 2 LLM calls (plan + reflection)

**Solutions:**
- Use faster LLM (e.g., DeepSeek vs GPT-4)
- Reduce max_iterations
- Use standard mode for simpler tasks
- Consider local LLM (Ollama) for speed

## Related Documentation

- [Architecture Overview](../README.md)
- [Memory System](./MEMORY.md)
- [Adaptive Planner](./ADAPTIVE_PLANNER.md)
- [Safety & Sandboxing](./SAFETY.md)

---

**Version**: 0.2.0-alpha  
**Last Updated**: 2026-02-20  
**Status**: Production-ready
