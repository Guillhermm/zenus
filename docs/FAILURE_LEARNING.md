# Failure Learning System

## Overview

Zenus learns from execution failures to prevent repeating mistakes and suggest intelligent recovery strategies.

## Architecture

### Components

1. **Failure Logger** (`memory/failure_logger.py`)
   - Persistent SQLite storage for all failures
   - Pattern tracking and normalization
   - Suggestion management

2. **Failure Analyzer** (`brain/failure_analyzer.py`)
   - Categorizes errors intelligently
   - Generates context-aware suggestions
   - Calculates success probabilities
   - Determines retry strategies

3. **Orchestrator Integration** (`cli/orchestrator.py`)
   - Pre-execution failure analysis
   - Post-failure intelligent error messages
   - Automatic suggestion display

## Features

### 1. Pre-Execution Analysis

Before running a command, Zenus analyzes similar past failures:

```bash
$ zenus "npm install react"

📚 Learning from past experience:
  ⚠️  Tool 'PackageOps' has failed 3 time(s) recently

💡 Suggestions based on past failures:
  • Check your internet connection
  • Try updating npm: npm install -g npm
  • Consider using yarn as an alternative

  Success probability: 50%

Proceed anyway? (y/n):
```

### 2. Failure Categorization

Automatic classification of errors:

- **permission_denied**: File/directory access issues
- **file_not_found**: Missing files or incorrect paths
- **command_not_found**: Missing executables or PATH issues
- **syntax_error**: Invalid command syntax
- **network_error**: Connection/timeout problems
- **disk_space**: Storage capacity issues
- **package_conflict**: Dependency version conflicts
- **timeout**: Operation took too long
- **unknown**: Uncategorized errors

### 3. Intelligent Suggestions

Context-aware recovery suggestions:

```python
# Permission error on Docker
❌ Execution failed: Permission denied: /var/run/docker.sock

💡 Suggestions to fix this:
  1. Add your user to the docker group: sudo usermod -aG docker $USER
  2. Or run with sudo (less recommended for security)
  3. Check Docker service is running: sudo systemctl status docker
  4. Log out and back in after adding to group
```

### 4. Pattern Learning

Zenus tracks failure patterns and learns:

- Which errors occur frequently
- Which fixes worked before
- Success rates for suggested fixes

```python
# Pattern database tracks:
- Pattern hash (normalized error signature)
- Occurrence count
- Last seen timestamp
- Suggested fix
- Success rate after applying fix
```

### 5. Retry Intelligence

Decides whether to retry based on error type:

| Error Type | Retry? | Reason |
|------------|--------|--------|
| permission_denied | No | Requires manual intervention |
| file_not_found | No | Won't exist on retry |
| network_error | Yes (3x) | Might be transient |
| timeout | Yes (3x) | Server might recover |
| unknown | Yes (1x) | Worth trying once |

### 6. Success Probability

Calculates likelihood of success based on history:

```python
# No similar failures
Success probability: 95% (high confidence)

# 1-2 similar failures
Success probability: 70-85% (medium confidence)

# 3-4 similar failures
Success probability: 50% (medium confidence)

# 5+ similar failures
Success probability: 30% (low confidence)
```

## Database Schema

### failures table

```sql
CREATE TABLE failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_input TEXT NOT NULL,
    intent_goal TEXT NOT NULL,
    tool TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    context_json TEXT,
    resolution TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### failure_patterns table

```sql
CREATE TABLE failure_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_hash TEXT UNIQUE NOT NULL,
    pattern_description TEXT,
    count INTEGER DEFAULT 1,
    last_seen TEXT NOT NULL,
    suggested_fix TEXT,
    success_after_fix INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Usage

### As a User

Zenus automatically learns from failures - no configuration needed!

When you encounter an error, Zenus will:
1. Log it for future reference
2. Show intelligent suggestions
3. Remember if you succeed after retrying

### Viewing Failure History

```bash
# Get failure statistics
zenus history --failures

# Output:
Total failures: 45
Recent (7 days): 12

By tool:
  FileOps: 15
  NetworkOps: 10
  PackageOps: 8
  ...

By error type:
  permission_denied: 12
  network_error: 10
  file_not_found: 8
  ...
```

### For Developers

#### Log a Failure

```python
from memory.failure_logger import get_failure_logger

logger = get_failure_logger()

failure_id = logger.log_failure(
    user_input="docker run nginx",
    intent_goal="Run container",
    tool="ContainerOps",
    error_type="permission_denied",
    error_message="Permission denied: /var/run/docker.sock",
    context={"cwd": "/home/user", "docker_group": False}
)
```

#### Analyze Before Execution

```python
from brain.failure_analyzer import FailureAnalyzer

analyzer = FailureAnalyzer()

analysis = analyzer.analyze_before_execution(user_input, intent)

if analysis["has_warnings"]:
    print(f"⚠️  Success probability: {analysis['success_probability']:.0%}")
    for suggestion in analysis["suggestions"]:
        print(f"  • {suggestion}")
```

#### Analyze a Failure

```python
analysis = analyzer.analyze_failure(
    user_input="npm install",
    intent_goal="Install dependencies",
    tool="PackageOps",
    error_message="ECONNREFUSED: Connection refused",
    context={"network": "slow"}
)

print(f"Error type: {analysis['error_type']}")
print(f"Is recurring: {analysis['is_recurring']}")

for suggestion in analysis["suggestions"]:
    print(f"  • {suggestion}")
```

## Error Normalization

To detect patterns, errors are normalized:

| Original | Normalized |
|----------|-----------|
| `/home/user/file.txt` | `/<path>` |
| `line 42` | `line <N>` |
| `port 8080` | `port <NUM>` |
| `FILE NOT FOUND` | `file not found` |

This allows Zenus to recognize similar errors across different contexts.

## Tool-Specific Intelligence

### BrowserOps
- Timeout suggestions: increase timeoutMs
- Element not found: page structure changed

### PackageOps
- Package not found: update package lists
- Conflict: fix broken dependencies

### GitOps
- Conflict: manual resolution needed
- Remote errors: check configuration

### ContainerOps
- Not found: pull image first
- Permission: add user to docker group

### NetworkOps
- Connection: check connectivity
- Timeout: server might be slow

## Privacy & Storage

- Database location: `~/.zenus/failures.db`
- Only local storage (no cloud sync)
- Contains command history and errors
- Can be deleted anytime: `rm ~/.zenus/failures.db`

## Performance

- Minimal overhead: <50ms per command
- SQLite with indexed queries
- Pattern matching with hash lookup
- Only analyzes on failure

## Future Enhancements

1. **LLM-Powered Analysis**
   - Use LLM to generate custom fixes
   - Learn from error message semantics

2. **Shared Learning**
   - Opt-in anonymous pattern sharing
   - Community-driven fix suggestions

3. **Automatic Fixes**
   - Apply known fixes automatically
   - "Did you mean..." suggestions

4. **Failure Prediction**
   - Predict failures before execution
   - Suggest alternative approaches

## Examples

### Example 1: Permission Denied

```bash
$ zenus "read /root/secret.txt"

❌ Execution failed: Permission denied: /root/secret.txt

💡 Suggestions to fix this:
  1. Try using 'sudo' for elevated permissions
  2. Check file permissions with 'ls -la /root/secret.txt'
  3. Verify you should have access to this file

📋 Recovery plan:
  1. Check permissions with 'ls -la /root/secret.txt'
  2. Fix permissions with 'chmod' or 'chown'
  3. Or retry with 'sudo' if appropriate
```

### Example 2: Network Failure with Learning

```bash
# First failure
$ zenus "curl https://api.slow.com/data"
❌ Connection timeout after 30s

# Second failure (Zenus remembers)
$ zenus "curl https://api.slow.com/users"

📚 Learning from past experience:
  ⚠️  Tool 'NetworkOps' has failed 1 time(s) recently

💡 Suggestions based on past failures:
  • Increase timeout: --timeout 60
  • This server is known to be slow

  Success probability: 85%

Proceed anyway? (y/n): y

# This time with longer timeout
✓ Success!
```

### Example 3: Recurring Docker Permission

```bash
$ zenus "docker ps"

❌ Execution failed: Permission denied: /var/run/docker.sock

⚠️  This failure has occurred 3 times before
  Consider reviewing the suggestions carefully

💡 Learned fix: Add user to docker group and restart session

📋 Recovery plan:
  1. Add user to docker group: sudo usermod -aG docker $USER
  2. Log out completely
  3. Log back in
  4. Verify: groups (should show 'docker')
  5. Retry command
```

## Testing

31 comprehensive tests cover:
- Failure logging and retrieval
- Pattern tracking and normalization
- Error categorization
- Suggestion generation
- Success probability calculation
- Retry decision logic
- Tool-specific suggestions
- Recovery plan generation

Run tests:
```bash
pytest tests/test_failure_logger.py tests/test_failure_analyzer.py -v
```

## Metrics

Track effectiveness with:
- Failure reduction rate (repeated errors)
- Suggestion acceptance rate
- Success after suggestion rate
- Pattern coverage (% of errors categorized)

## Integration Points

### Orchestrator
- `analyze_before_execution()`: Pre-flight checks
- `analyze_failure()`: Post-failure analysis

### Adaptive Planner
- Uses failure history for retry decisions
- Learns which approaches work better

### Explain Mode
- Shows failure history when explaining risky operations
- Warns about operations with high failure rates

---

**Note**: The failure learning system is always active. Every failure makes Zenus smarter!
