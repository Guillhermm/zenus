# Zenus Features

Complete guide to all features and capabilities.

---

## 🧠 Intelligence Features

### Natural Language Understanding

Zenus understands intent, not just literal commands:

```bash
# These all work:
zenus "organize my downloads"
zenus "clean up the download folder"
zenus "sort downloads by type"
zenus "arrange files in downloads by extension"
```

**How it works**:
- LLM translates natural language to structured Intent IR
- Context-aware (knows your location, git status, time)
- Handles ambiguity and variations
- Asks clarifying questions when needed

### Automatic Complexity Detection

Zenus automatically detects when tasks need iterative execution:

```bash
# Simple task - one-shot execution
zenus "list files in downloads"

# Complex task - automatic iterative mode
zenus "read my research paper and improve chapter 3"
# Detected complex task (confidence: 92%)
# Using iterative execution...
```

**Detection criteria**:
- Multiple steps with dependencies
- Open-ended goals ("improve", "optimize")
- Verification needs ("ensure", "check")
- Large scope ("all", "entire")

### Context Awareness

Zenus knows your environment:

**Working Directory**:
```bash
$ cd ~/projects/my-app
$ zenus "show git status"
# Automatically operates on current git repo
```

**Time Awareness**:
```bash
$ zenus "what happened today?"
# Uses current date/time for context
```

**System State**:
- Git repository and branch
- Running processes
- Recent file modifications
- Project type detection

---

## ⚡ Performance Features

### Parallel Execution

Automatic concurrent execution for independent operations:

```bash
$ zenus "download reports: Q1.pdf, Q2.pdf, Q3.pdf, Q4.pdf from company.com"

Using parallel execution (estimated 4.0x speedup)
  Level 1 (parallel - 4 steps):
    [0] NetworkOps.download (Q1.pdf)
    [1] NetworkOps.download (Q2.pdf)
    [2] NetworkOps.download (Q3.pdf)
    [3] NetworkOps.download (Q4.pdf)

✓ Completed in 2.3s (was 9.1s sequentially)
4x speedup achieved!
```

**Features**:
- Dependency analysis (topological sort)
- Resource conflict detection
- Thread-safe execution
- Graceful error handling
- Estimated speedup calculation

**When parallelization happens**:
- Multiple independent file operations
- Batch downloads
- Independent system checks
- Concurrent package installations (when safe)

### Batch Optimization

Detects inefficient patterns and suggests better approaches:

```bash
$ zenus "copy report1.pdf report2.pdf report3.pdf ... (15 files)"

💡 Suggestions:
  ⚡ Use wildcard for batch operations
     Instead of processing 15 files individually, use: *.pdf
     Reason: Wildcards can reduce execution time by ~93%
```

**Optimizations detected**:
- Multiple similar file operations → wildcards
- Sequential downloads → parallel execution
- Repeated operations → caching
- Inefficient tool choices → alternatives

### Adaptive Retry

Automatically retries transient failures:

```bash
$ zenus "download https://api.example.com/report.pdf"
⚠️  Attempt 1 failed: Connection timeout
🔄 Retrying with backoff...
✓ Success on attempt 2
```

**Retry logic**:
- Network errors: Up to 3 retries with exponential backoff
- Timeout errors: Retry with increased timeout
- Permission errors: No retry (needs manual intervention)
- Unknown errors: One retry attempt

---

## 🛡️ Safety Features

### Undo/Rollback

Reverse operations when you make mistakes:

```bash
$ zenus "install packages: curl, wget, htop"
✓ Installed 3 packages

$ zenus rollback
Rolling back last 3 action(s)...
  Rolling back: PackageOps.install (curl)
  Rolling back: PackageOps.install (wget)
  Rolling back: PackageOps.install (htop)
✓ Successfully rolled back 3 action(s)
```

**Rollback capabilities**:
- File creation/copy/move → Delete/restore
- Package install → Uninstall
- Git commits → Reset
- Service start/stop → Inverse operation
- Container run → Stop and remove

**Rollback commands**:
```bash
zenus rollback           # Last action
zenus rollback 5         # Last 5 actions
zenus rollback --dry-run # Preview without executing
```

**Limitations**:
- File deletions (without checkpoint)
- Git push to remote
- External API calls
- Already-rolled-back actions

### Dry-Run Mode

Preview operations before execution:

```bash
$ zenus --dry-run "delete all tmp files in downloads"

Dry Run - Would execute:
  Goal: Delete temporary files

  Step 1: FileOps.scan
    Action: List directory contents
    Path: ~/Downloads
    Risk: 0 (Read-only)

  Step 2: FileOps.delete
    Action: Delete files matching *.tmp
    Count: 47 files
    Risk: 3 (Destructive)

No changes made (dry run)
```

### Risk Assessment

Warns about destructive operations:

```bash
$ zenus "delete all logs older than 30 days"

⚠️  High-risk operation detected
  This operation cannot be undone without backup
  Affects: 156 files

Destructive operations:
  • Delete 156 files from /var/log

Proceed? (y/n):
```

**Risk levels**:
- **0**: Read-only (list, read, show)
- **1**: Modify (write, move, create)
- **2**: Significant change (install, uninstall)
- **3**: Destructive (delete, irreversible changes)

### Sandboxing

Path validation and resource limits:

```bash
$ zenus "delete /etc/passwd"
❌ Safety violation: Cannot access /etc/passwd
   Reason: System file protection

$ zenus "read /root/secret.txt"
❌ Safety violation: Path outside allowed boundaries
   Reason: Access denied to /root
```

**Protections**:
- System file protection (`/etc`, `/sys`, `/proc`)
- Home directory restriction (by default)
- Command whitelist/blacklist
- Resource limits (memory, CPU)

---

## 💡 Learning Features

### Failure Learning

Learns from every mistake:

```bash
# First time - failure
$ zenus "docker ps"
❌ Permission denied: /var/run/docker.sock

💡 Suggestions to fix this:
  1. Add user to docker group: sudo usermod -aG docker $USER
  2. Log out and back in
  3. Verify: groups (should show 'docker')

📋 Recovery plan: [detailed steps]

# Later - intelligent warning
$ zenus "docker run nginx"

📚 Learning from past experience:
  ⚠️  Tool 'ContainerOps' has failed 1 time(s) recently
  Success probability: 50%

💡 Learned fix: Add user to docker group and restart session

Proceed anyway? (y/n):
```

**Learning capabilities**:
- Pattern recognition (8 error categories)
- Success probability calculation
- Recovery plan generation
- Tool-specific suggestions
- Retry decision logic

**Error categories**:
- `permission_denied`: File/directory access issues
- `file_not_found`: Missing files or paths
- `command_not_found`: Missing executables
- `syntax_error`: Invalid command syntax
- `network_error`: Connection problems
- `disk_space`: Storage issues
- `package_conflict`: Dependency conflicts
- `timeout`: Operations took too long

### Proactive Suggestions

Suggests improvements before execution:

```bash
$ zenus "copy file1.pdf file2.pdf file3.pdf ... (20 files)"

💡 Suggestions:
  ⚡ Use wildcard for batch operations
     Instead of 20 files, use: *.pdf
     Reason: 95% faster execution

  ⚡ Enable parallel execution
     Potentially 20x faster with concurrent copies
     Reason: Independent operations detected

  ⚠️  This might take a while
     20 file operations detected
     Reason: Large batch operation
```

**Suggestion types**:
- **Optimization** (⚡): Performance improvements
- **Alternative** (🔄): Better tool choices
- **Warning** (⚠️): Potential issues
- **Tip** (💡): Best practices

### Semantic Search

Find similar past commands:

```bash
$ zenus history --search "install python"

Similar commands found:
  [2024-01-15] "install python packages"
    Success: ✓
    
  [2024-01-10] "setup python environment"
    Success: ✓
    
  [2024-01-05] "install python3"
    Success: ✗ (Permission denied)
```

---

## 📊 Memory Features

### Session Memory

Remembers context within conversations:

```bash
zenus > read notes.txt
Content: "Meeting at 2pm. Call Bob about proposal."

zenus > append to it: "Sent proposal to Bob"
✓ Appended to notes.txt

zenus > show it
# Remembers "it" refers to notes.txt
Content: "Meeting at 2pm. Call Bob about proposal. Sent proposal to Bob."
```

### World Model

Learns your preferences over time:

- Frequent paths (auto-completes common directories)
- Preferred tools (suggests tools you use often)
- Naming conventions (learns your file naming patterns)
- Working patterns (morning routine, evening cleanup)

### Intent History

Complete audit trail:

```bash
$ zenus history

Recent operations:
  [20:45] "organize downloads" - ✓ Success
    • Moved 25 files
    • Created 4 directories
    
  [20:30] "install curl" - ✓ Success (rolled back at 20:35)
    • Installed curl package
    
  [20:15] "find python processes" - ✓ Success
    • Found 3 processes
```

**History storage**:
- Location: `~/.zenus/history/`
- Format: JSONL (one operation per line)
- Retention: Unlimited (can be cleaned manually)
- Privacy: Local-only, never uploaded

---

## 🔧 Tool Capabilities

### FileOps (File Operations)

**Basic operations**:
- `scan`: List directory contents
- `read_file`: Read file contents
- `write_file`: Create/overwrite files
- `create_file`: Create new file
- `delete_file`: Delete files
- `mkdir`: Create directories
- `copy_file`: Copy files
- `move_file`: Move/rename files
- `touch`: Create empty file

**Advanced**:
- Wildcard support (`*.pdf`, `file?.txt`)
- Recursive directory operations
- Batch operations with parallel execution

### SystemOps (System Management)

- `disk_usage`: Show disk space
- `memory_info`: Show RAM usage
- `cpu_info`: Show CPU usage and load
- `list_processes`: List top processes by CPU/memory
- `uptime`: System uptime and load average

### ProcessOps (Process Management)

- `find_by_name`: Find processes by name
- `info`: Get detailed process information
- `kill`: Terminate processes (requires confirmation)

### PackageOps (Package Management)

Supports multiple package managers:
- **apt** (Debian/Ubuntu)
- **dnf** (Fedora/RedHat)
- **pacman** (Arch)

Operations:
- `install`: Install packages
- `uninstall`: Remove packages
- `update`: Update package lists
- `upgrade`: Upgrade installed packages
- `search`: Search for packages

### BrowserOps (Browser Automation)

Powered by Playwright:
- `open`: Open URL in browser
- `screenshot`: Capture page screenshot
- `navigate`: Navigate and interact
- `search`: Perform search queries
- `download`: Download files from web
- `extract_links`: Get all links from page
- `fill_form`: Fill form fields
- `click`: Click elements

### GitOps (Git Operations)

- `status`: Show repository status
- `commit`: Commit changes
- `push`: Push to remote
- `pull`: Pull from remote
- `branch`: Create/list branches
- `checkout`: Switch branches
- `log`: Show commit history
- `diff`: Show changes

### NetworkOps (Network Operations)

- `download`: Download files from URLs
- `curl`: Make HTTP requests
- `ping`: Test connectivity
- `wget`: Alternative download
- `ssh`: SSH connection (interactive)

### ServiceOps (Service Management)

Systemd integration:
- `start`: Start service
- `stop`: Stop service
- `restart`: Restart service
- `status`: Show service status
- `enable`: Enable on boot
- `disable`: Disable on boot

### ContainerOps (Docker/Podman)

- `run`: Run container
- `stop`: Stop container
- `list`: List containers
- `logs`: Show container logs
- `exec`: Execute command in container
- `images`: List images
- `pull`: Pull image
- `remove`: Remove container

### TextOps (Text Processing)

- `read`: Read text file
- `write`: Write text file
- `append`: Append to file
- `search`: Search for pattern
- `count_lines`: Count lines
- `head`: Show first N lines
- `tail`: Show last N lines
- `grep`: Search with grep
- `sed`: Text transformation

---

## 🎛️ Advanced Features

### Iterative Mode

For complex, multi-step tasks:

```bash
$ zenus --iterative "analyze my Python project and suggest improvements"

# Zenus will:
# 1. Scan project structure
# 2. Read key files
# 3. Analyze code quality
# 4. Generate suggestions
# 5. Ask for confirmation
# 6. Apply improvements
```

**Triggered automatically for**:
- Open-ended goals
- Multi-step requirements
- Verification needs
- Large scope operations

**Manual override**:
```bash
zenus --iterative "your complex task"
zenus --force-oneshot "normally complex task"  # Skip auto-detection
```

### Explain Mode

Show detailed reasoning before execution:

```bash
$ zenus --explain "organize downloads"

📋 Execution Plan:
  Goal: Organize files in downloads directory by type

  Analysis:
    • This requires 2 steps to complete
    • Will modify 47 item(s)
    • Using: FileOps

  Context:
    • Working directory: ~/Downloads
    • Project: None
    • Time: afternoon (15:30)
    • Disk usage: 142 GB used / 500 GB (28%)

  Steps:
    [1] FileOps.scan
        List files in ~/Downloads
        Risk: 0 (Read-only)
        
    [2] FileOps.move
        Move files into type-based folders
        Risk: 1 (Modify)

  Success probability: 95% (high confidence)

Proceed with execution? (y/n):
```

### Transaction Groups

Operations are grouped for atomic rollback:

```bash
$ zenus "setup dev environment: install python, node, docker"

Transaction tx_abc123:
  [1] PackageOps.install (python3)
  [2] PackageOps.install (nodejs)
  [3] PackageOps.install (docker)

✓ Transaction completed

# Rollback all at once:
$ zenus rollback
Rolling back transaction tx_abc123...
✓ All 3 operations reversed
```

---

## 📈 Performance Metrics

### Speedup Benchmarks

| Operation Type | Sequential | Parallel | Speedup |
|---------------|-----------|----------|---------|
| Download 10 files | 30s | 6s | **5.0x** |
| Copy 20 files | 20s | 4s | **5.0x** |
| Process 50 images | 50s | 12s | **4.2x** |
| Batch with wildcards | 100s | 2s | **50x** |
| Git operations (sequential) | 15s | 15s | 1.0x |
| Mixed operations | 45s | 18s | **2.5x** |

### Overhead Analysis

- Intent translation: 100-500ms (LLM latency)
- Failure analysis: <50ms
- Dependency analysis: <30ms
- Suggestion generation: <50ms
- Action tracking: <10ms
- **Total overhead**: <700ms worst case

### Resource Usage

- **Memory**: 50-200MB (depends on LLM backend)
- **CPU**: Minimal (unless LLM is local)
- **Storage**: ~10KB per day (logs)
- **Network**: Only for cloud LLMs

---

## 🔮 Future Features

### Planned (v0.3.0)
- Voice interface (Whisper STT + ElevenLabs TTS)
- Enhanced semantic search with vector embeddings
- Custom skill plugins
- Advanced rollback (git branch restore, database snapshots)
- Performance profiling dashboard

### Experimental
- Process-based parallelism (for CPU-intensive tasks)
- LLM-powered failure analysis
- Shared learning database (opt-in)
- Predictive failure prevention
- Auto-fix application

---

**See also**:
- [Architecture](ARCHITECTURE.md) - System design
- [User Guide](USER_GUIDE.md) - Detailed examples
- [Configuration](CONFIGURATION.md) - Advanced configuration
