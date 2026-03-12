# Undo/Rollback System

## Overview

Zenus tracks every operation and provides safe rollback capabilities to undo actions when needed.

## Architecture

### Components

1. **Action Tracker** (`memory/action_tracker.py`)
   - SQLite-backed persistent tracking
   - Transaction grouping
   - Automatic rollback strategy determination
   - Checkpoint management

2. **Rollback Engine** (`cli/rollback.py`)
   - Executes inverse operations
   - Dry-run mode
   - Feasibility analysis
   - Partial rollback support

3. **Orchestrator Integration** (`cli/orchestrator.py`)
   - Automatic action tracking during execution
   - Transaction lifecycle management

## Features

### 1. Automatic Action Tracking

Every operation is automatically tracked:

```bash
$ zenus "create file test.txt with content 'hello'"

# Behind the scenes:
# - Transaction started: tx_abc123
# - Action tracked: FileOps.create_file
# - Rollback strategy: delete
# - Transaction completed
```

### 2. Transaction Grouping

Related actions are grouped into transactions:

```bash
$ zenus "copy all PDFs from downloads to documents"

Transaction tx_abc123:
  Action 1: FileOps.copy_file (report.pdf)
  Action 2: FileOps.copy_file (invoice.pdf)
  Action 3: FileOps.copy_file (thesis.pdf)
```

### 3. Rollback Last N Actions

```bash
# Undo last action
$ zenus rollback

# Undo last 3 actions
$ zenus rollback 3

# Preview what would be undone
$ zenus rollback --dry-run
```

Output:
```
Rolling back last 1 action(s)
  Rolling back: FileOps.create_file
✓ Successfully rolled back 1 action(s)
```

### 4. Transaction History

View recent transactions:

```bash
$ zenus history

Recent Transactions:
  tx_abc123: create file test.txt
    Goal: Create a file
    Status: completed

  tx_def456: install package curl
    Goal: Install curl package
    Status: completed (rolled back)
```

### 5. Rollback Strategies

Different operations have different rollback strategies:

| Operation | Rollback Strategy | Reversibility |
|-----------|------------------|---------------|
| create_file | delete | ✅ Full |
| delete_file | restore (needs checkpoint) | ⚠️ With backup |
| move_file | move_back | ✅ Full |
| copy_file | delete_copy | ✅ Full |
| install (package) | uninstall | ✅ Full |
| uninstall (package) | reinstall | ✅ Full |
| git commit | git_reset | ✅ Full |
| git push | requires_manual | ❌ Manual only |
| start (service) | stop | ✅ Full |
| stop (service) | start | ✅ Full |
| run (container) | stop_and_remove | ✅ Full |

### 6. Feasibility Analysis

Before rollback, Zenus analyzes if it's safe:

```bash
$ zenus rollback

❌ Rollback error: Cannot rollback transaction
Non-rollbackable actions: GitOps.push

Reason: git push operations cannot be automatically rolled back
Please manually revert the pushed commits if needed
```

### 7. Checkpoints (File Backups)

For destructive operations, create checkpoints:

```python
tracker.create_checkpoint(
    checkpoint_name="before_cleanup",
    description="Before deleting temp files",
    file_paths=["/path/to/important/file.txt"]
)
```

Restore from checkpoint:

```bash
$ zenus restore before_cleanup
```

## Database Schema

### actions table

```sql
CREATE TABLE actions (
    id INTEGER PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    tool TEXT NOT NULL,
    operation TEXT NOT NULL,
    params_json TEXT NOT NULL,
    result_json TEXT,
    rollback_possible BOOLEAN NOT NULL,
    rollback_strategy TEXT,
    rollback_data_json TEXT,
    rolled_back BOOLEAN DEFAULT 0
);
```

### transactions table

```sql
CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    user_input TEXT NOT NULL,
    intent_goal TEXT NOT NULL,
    status TEXT NOT NULL,
    rollback_status TEXT
);
```

### checkpoints table

```sql
CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY,
    checkpoint_name TEXT UNIQUE NOT NULL,
    transaction_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    description TEXT,
    backup_paths_json TEXT
);
```

## CLI Commands

### Rollback

```bash
# Rollback last action
zenus rollback

# Rollback last N actions
zenus rollback N

# Dry run (preview without executing)
zenus rollback --dry-run

# Rollback specific transaction
zenus rollback tx_abc123
```

### History

```bash
# Show transaction history
zenus history

# Show failure history
zenus history --failures
```

## Usage Examples

### Example 1: Undo File Creation

```bash
$ zenus "create file mistake.txt"
✓ Plan executed successfully

$ zenus history
Recent Transactions:
  tx_abc123: create file mistake.txt
    Goal: Create a file
    Status: completed

$ zenus rollback
Rolling back last 1 action(s)
  Rolling back: FileOps.create_file
✓ Successfully rolled back 1 action(s)

# File is deleted!
```

### Example 2: Undo Multiple Operations

```bash
$ zenus "copy all logs from /var/log to ~/backup"
✓ Copied 15 files

$ zenus rollback 15
Rolling back last 15 action(s)
  Rolling back: FileOps.copy_file (syslog)
  Rolling back: FileOps.copy_file (auth.log)
  ... (13 more)
✓ Successfully rolled back 15 action(s)

# All copied files removed!
```

### Example 3: Undo Package Installation

```bash
$ zenus "install package neofetch"
✓ Package installed successfully

# Changed your mind?
$ zenus rollback
Rolling back last 1 action(s)
  Rolling back: PackageOps.install
  Uninstalling package neofetch
✓ Successfully rolled back 1 action(s)
```

### Example 4: Cannot Rollback Git Push

```bash
$ zenus "commit and push changes to main"
✓ Committed and pushed

$ zenus rollback
❌ Rollback error: Cannot rollback transaction
Non-rollbackable actions: GitOps.push

The following actions cannot be rolled back: GitOps.push
Pushed commits require manual revert
```

### Example 5: Dry Run Preview

```bash
$ zenus "delete all tmp files in downloads"
✓ Deleted 47 files

$ zenus rollback --dry-run

Dry run - showing rollback plan:
  • Delete /tmp/file1.tmp
  • Delete /tmp/file2.tmp
  ... (45 more)

Dry run complete - no changes made

$ zenus rollback
# Actually executes the rollback
```

### Example 6: Partial Rollback

```bash
$ zenus "organize downloads: move PDFs to docs, delete temps"

Transaction includes:
  - Move report.pdf
  - Move invoice.pdf
  - Delete temp1.tmp (irreversible!)
  - Delete temp2.tmp (irreversible!)

$ zenus rollback
⚠ Partial rollback: 2 succeeded, 2 failed
✓ Moved back: report.pdf, invoice.pdf
✗ Cannot restore: temp1.tmp, temp2.tmp (already deleted)
```

## Safety Guarantees

### What Can Be Rolled Back

✅ **Safe to rollback:**
- File creation, copy, move
- Package installation/uninstallation
- Service start/stop
- Container operations
- Git commits (local only)
- Configuration changes (if tracked)

### What Cannot Be Rolled Back

❌ **Cannot rollback:**
- File deletions (without checkpoint)
- Git push to remote
- External API calls
- Network operations
- Already-rolled-back actions

### Rollback Safeguards

1. **Feasibility Check**: Analyzes if rollback is possible before executing
2. **Dry Run Mode**: Preview changes without executing
3. **Transaction Atomicity**: All-or-nothing for grouped operations
4. **Rollback Tracking**: Prevents double-rollback
5. **Error Handling**: Graceful degradation on partial failures

## Implementation Details

### Rollback Strategy Determination

When tracking an action, Zenus determines the rollback strategy:

```python
def _determine_rollback_strategy(tool, operation, params, result):
    if tool == "FileOps" and operation == "create_file":
        return {
            "possible": True,
            "strategy": "delete",
            "data": {"path": params["path"]}
        }
    
    if tool == "PackageOps" and operation == "install":
        return {
            "possible": True,
            "strategy": "uninstall",
            "data": {"package": params["package"]}
        }
    
    # ... more strategies
```

### Executing Inverse Operations

The rollback engine executes inverse operations:

```python
def _execute_rollback(action):
    strategy = action.rollback_strategy
    data = action.rollback_data
    
    if strategy == "delete":
        os.remove(data["path"])
    
    elif strategy == "uninstall":
        subprocess.run(["apt", "remove", "-y", data["package"]])
    
    # ... more strategies
```

## Performance

- **Tracking Overhead**: <10ms per action
- **Rollback Speed**: Depends on operation (typically <1s per action)
- **Storage**: ~100 bytes per action in SQLite
- **Retention**: Unlimited (can be cleaned up manually)

## Privacy & Storage

- Database: `~/.zenus/actions.db`
- Backups: `~/.zenus/backups/`
- Local-only storage (no cloud sync)
- Can be deleted anytime

## Limitations

1. **No Checkpointing by Default**: File deletions not reversible without manual checkpoint
2. **No Cross-Machine Rollback**: Actions on one machine can't be rolled back from another
3. **No Time-Travel**: Can only rollback recent transactions, not arbitrary points
4. **External Effects**: API calls, emails, etc. cannot be rolled back

## Future Enhancements

1. **Automatic Checkpointing**: Create backups before destructive operations
2. **Selective Rollback**: Choose which actions to rollback in a transaction
3. **Rollback to Timestamp**: "Undo everything after 2PM"
4. **Smart Conflict Resolution**: Handle dependent actions intelligently
5. **Rollback Recommendations**: Suggest when to rollback based on outcomes

## Testing

30+ comprehensive tests cover:
- Action tracking and retrieval
- Rollback strategy determination
- Feasibility analysis
- File operations rollback
- Package operations rollback
- Transaction management
- Checkpoint creation and restoration
- Error handling and partial failures

Run tests:
```bash
pytest tests/test_action_tracker.py tests/test_rollback.py -v
```

## Best Practices

### When to Rollback

✅ **Good use cases:**
- Accidental file operations
- Testing configurations
- Reverting recent package installations
- Undoing batch operations
- Learning/experimenting safely

❌ **Don't rely on rollback for:**
- Critical data recovery (use proper backups)
- Production deployments (use proper CI/CD)
- Security incidents (may not be complete)

### Creating Checkpoints

Create checkpoints before risky operations:

```python
# Before bulk deletion
tracker.create_checkpoint(
    "before_cleanup",
    "Before deleting old logs",
    file_paths=["/var/log/important.log"]
)

# Perform deletion
...

# Restore if needed
rollback_engine.restore_checkpoint("before_cleanup")
```

### Verifying Rollback

After rollback, verify the system state:

```bash
$ zenus rollback
✓ Successfully rolled back 3 action(s)

# Verify files/packages/services are back to expected state
$ ls /path/to/files
$ dpkg -l | grep package_name
$ systemctl status service_name
```

---

**Note**: Rollback is a safety net, not a substitute for careful planning and backups!
