# Auto-Detection of Iterative Tasks

## Overview

Zenus now **automatically detects** when tasks need iterative execution. You don't need to specify `--iterative` flag manually.

## How It Works

### Task Analyzer

Before executing any command, Zenus analyzes the task complexity using heuristics:

```python
TaskAnalyzer → Determines: One-shot or Iterative?
    ↓
If Iterative → execute_iterative() automatically
If One-shot → execute_command() as before
```

### Detection Criteria

**Iterative tasks** (multi-step execution):
- Contain analysis keywords: `analyze`, `understand`, `examine`, `study`
- Have multi-step language: `then`, `after`, `followed by`
- Include improvements: `improve`, `enhance`, `optimize`, `refactor`
- Need context: `based on`, `depending on`, `according to`
- Require discovery: `find out`, `discover`, `determine`
- Complex organization: `organize by`, `sort by`, `group by`

**One-shot tasks** (single execution):
- Simple queries: `list`, `show`, `display`
- Basic creation: `create`, `make folder`
- Info requests: `what is`, `status of`

### Examples

#### Automatically Detected as Iterative ✓

```bash
# No flag needed!
zenus "read my LaTeX project and improve chapter 3"
zenus "organize downloads by type and date"
zenus "analyze code and suggest refactorings"
zenus "find all Python files and generate docs"
```

Output:
```
Detected complex task (confidence: 85%)
Using iterative execution (Analysis + multi-step detected)

═══ Iteration 1/8 ═══
...
```

#### Automatically Detected as One-Shot ✓

```bash
zenus "list files in ~/Documents"
zenus "show disk usage"
zenus "create folder ~/test"
zenus "display CPU info"
```

Output:
```
Step 1: FileOps.scan → Listed 15 files
✓ Plan executed successfully
```

## User Confirmation on Max Iterations

When max iterations is reached, Zenus **asks for confirmation** instead of just stopping:

```
⚠ Maximum iterations (10) reached
Observations so far: 8 steps completed
Goal not yet achieved with high confidence

Would you like to continue for more iterations?
Continue? [y/N]:
```

### If you choose "y":
```
Continuing execution...
New max: 15 iterations
```

### If you choose "N" (or just press Enter):
```
Stopping execution as requested.
Task incomplete after 10 iterations (user chose to stop)
```

## Configuration

### Default Max Iterations

The max iterations is **dynamically calculated** based on task complexity:

```python
max_iterations = estimated_steps × 2
```

Example:
- Simple task (3 estimated steps) → max 6 iterations
- Complex task (5 estimated steps) → max 10 iterations
- Very complex (10 estimated steps) → max 20 iterations

### Override Auto-Detection

If you want to **force one-shot** execution:

```python
# Programmatically
orchestrator.execute_command(
    "complex task",
    force_oneshot=True  # Skip auto-detection
)
```

Or use `--oneshot` flag (if implemented in CLI).

### Manual Iterative Flag

The `--iterative` flag **still works** for explicit control:

```bash
# Force iterative even for simple tasks
zenus --iterative "list files"
```

## Performance Benefits

### Batch Operations

All LLM system prompts now **emphasize batch operations**:

**Bad (old behavior):**
```json
{
  "steps": [
    {"tool": "FileOps", "action": "move", "args": {"source": "file1.pdf", "destination": "PDFs/"}},
    {"tool": "FileOps", "action": "move", "args": {"source": "file2.pdf", "destination": "PDFs/"}},
    {"tool": "FileOps", "action": "move", "args": {"source": "file3.pdf", "destination": "PDFs/"}}
  ]
}
```

**Good (new behavior):**
```json
{
  "steps": [
    {"tool": "FileOps", "action": "mkdir", "args": {"path": "PDFs"}},
    {"tool": "FileOps", "action": "move", "args": {"source": "*.pdf", "destination": "PDFs/"}}
  ]
}
```

**Result:**
- 3 operations → 2 operations (33% faster!)
- 100 PDF files → Still only 2 operations (98% faster!)

### Wildcards Supported

Zenus now uses shell patterns:
- `*.pdf` - All PDF files
- `*.jpg`, `*.png` - All images
- `file_*.txt` - Pattern matching
- `backup_*` - Prefix matching

## Heuristic Details

### Complexity Scoring

```python
complexity_score = 0

# Iterative keywords (+3 each)
if "analyze" in task: complexity_score += 3
if "improve" in task: complexity_score += 3

# One-shot keywords (-3 each)
if "list" in task: complexity_score -= 3
if "show" in task: complexity_score -= 3

# Multi-step indicators
if "then" in task: complexity_score += 1
if sentences > 1: complexity_score += sentence_count

# Conditional logic
if "if" in task and "file" in task: complexity_score += 3

# Word count
if word_count > 15: complexity_score += 2

# Decision
needs_iteration = complexity_score >= 2
```

### Confidence Levels

- **0.9**: Very complex (score ≥ 5)
- **0.75**: Moderately complex (score ≥ 2)
- **0.85**: Very simple (score ≤ -2)
- **0.6**: Uncertain (score between -1 and 1)

## Examples with Reasoning

### Example 1: LaTeX Project

**Input:**
```bash
zenus "read my LaTeX thesis and improve chapter 3"
```

**Analysis:**
```
Detected complex task (confidence: 85%)
Using iterative execution (keywords: read, improve; multi-clause detected)

Estimated steps: 6
Max iterations: 12
```

**Reasoning:**
- "read" + "improve" = 2 iterative keywords (score +6)
- "and" clause separator (score +1)
- Word count: 7 (below threshold)
- **Total score: 7 → Iterative with high confidence**

### Example 2: Simple Listing

**Input:**
```bash
zenus "list files in ~/Documents"
```

**Analysis:**
```
(no auto-detection message - one-shot execution)
```

**Reasoning:**
- "list" = one-shot keyword (score -3)
- No iterative keywords
- Single sentence
- Word count: 4
- **Total score: -3 → One-shot with high confidence**

### Example 3: Organization Task

**Input:**
```bash
zenus "organize my downloads by type and then by date"
```

**Analysis:**
```
Detected complex task (confidence: 75%)
Using iterative execution (keywords: organize by, then; multi-step detected)

Estimated steps: 4
Max iterations: 8
```

**Reasoning:**
- "organize by" = iterative keyword (score +3)
- "then" = multi-step indicator (score +1)
- "and" clause (score +1)
- **Total score: 5 → Iterative with moderate confidence**

## Troubleshooting

### "Task detected as one-shot but needs iteration"

**Solution 1:** Be more explicit in task description:
```bash
# Instead of:
zenus "fix the code"

# Use:
zenus "analyze the code, identify issues, and then fix them"
```

**Solution 2:** Force iterative:
```bash
zenus --iterative "task that should be iterative"
```

### "Task detected as iterative but is simple"

**Solution:** Use simple, direct language:
```bash
# Instead of:
zenus "I need you to please show me all the files"

# Use:
zenus "list files"
```

### "Max iterations reached too quickly"

The system now **asks for confirmation**, so you can:
1. Choose to continue (adds 5 more iterations)
2. Break task into smaller sub-tasks
3. Make goal more specific

### "Batch operations not working"

If you see individual file operations:
1. Check that you're using latest Zenus (with updated prompts)
2. Try being more explicit: "move all PDF files to PDFs folder"
3. The LLM should now automatically use `*.pdf` patterns

## Implementation Files

- **TaskAnalyzer**: `src/brain/task_analyzer.py`
- **Orchestrator**: `src/cli/orchestrator.py` → `execute_command()` with auto-detection
- **System Prompts**: 
  - `src/brain/llm/deepseek_llm.py`
  - `src/brain/llm/openai_llm.py`
  - `src/brain/llm/ollama_llm.py`

## Testing

Run TaskAnalyzer tests:
```bash
pytest tests/test_task_analyzer.py -v
```

Expected: 13 tests passing

## Benefits Summary

### For Users

✅ **No flag needed** - Zenus knows when to iterate  
✅ **Confirmation prompts** - Control over continuation  
✅ **Faster execution** - Batch operations by default  
✅ **More intuitive** - Just describe what you want  

### For Developers

✅ **Heuristic-based** - No LLM call needed for detection  
✅ **Testable** - 13 unit tests covering detection logic  
✅ **Configurable** - Easy to tune thresholds  
✅ **Backward compatible** - `--iterative` flag still works  

---

**Version**: 0.3.0-alpha  
**Last Updated**: 2026-02-20  
**Status**: Production-ready
