# Configuration Guide

**Status**: ✅ Complete | **Version**: 1.2.0

Modern configuration system with YAML support, profiles, and hot-reload.

---

## 🎯 Overview

Zenus uses a **two-tier configuration system**:
1. **Configuration** (`config.yaml`) - Settings, features, profiles
2. **Secrets** (`.env`) - API keys, sensitive data

**Benefits:**
- ✅ Type-safe (Pydantic validation)
- ✅ Profile support (dev/staging/production)
- ✅ Hot-reload (instant changes)
- ✅ Secrets separate from config
- ✅ Well-organized structure

---

## 📂 File Locations

### Config File
```
~/.zenus/config.yaml        # Recommended
./zenus.yaml                # Project-specific
$ZENUS_CONFIG               # Custom location
```

### Secrets File
```
~/.zenus/.env              # Recommended
./.env                     # Project-specific
```

---

## ⚙️ Configuration Structure

### Complete Example

```yaml
# config.yaml
version: "1.1.0"
profile: dev  # dev, staging, production

llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  max_tokens: 4096
  temperature: 0.7
  timeout_seconds: 30

fallback:
  enabled: true
  providers:
    - anthropic
    - deepseek
    - rule_based

circuit_breaker:
  enabled: true
  failure_threshold: 5
  timeout_seconds: 60.0
  success_threshold: 2

retry:
  enabled: true
  max_attempts: 3
  initial_delay_seconds: 1.0
  max_delay_seconds: 30.0
  exponential_base: 2.0
  jitter: true

cache:
  enabled: true
  ttl_seconds: 3600
  max_size_mb: 100

safety:
  sandbox_enabled: true
  max_file_size_mb: 100
  allowed_paths:
    - "."
  blocked_commands:
    - "rm -rf /"

monitoring:
  enabled: true
  check_interval_seconds: 300
  disk_warning_threshold: 0.8
  disk_critical_threshold: 0.9
  cpu_warning_threshold: 0.8
  memory_warning_threshold: 0.85

features:
  voice_interface: false
  multi_agent: false
  proactive_monitoring: true
  tree_of_thoughts: true
  prompt_evolution: true
  goal_inference: true
  self_reflection: true
  data_visualization: true

profiles:
  dev:
    llm:
      temperature: 0.9
    safety:
      sandbox_enabled: false
  
  production:
    llm:
      temperature: 0.5
    safety:
      sandbox_enabled: true
```

---

## 🎭 Profile System

### Available Profiles

**dev** (Development)
- More creative (higher temperature)
- Shorter cache TTL
- Sandbox disabled for convenience
- All features enabled

**staging** (Staging)
- Balanced settings
- Medium cache TTL
- Sandbox enabled
- Stable features only

**production** (Production)
- Conservative (lower temperature)
- Longer cache TTL
- Sandbox always enabled
- Experimental features disabled

### Using Profiles

```bash
# Set via environment
export ZENUS_PROFILE=production
zenus "deploy app"

# Or inline
ZENUS_PROFILE=dev zenus "test feature"

# Check current profile
zenus config profile
```

---

## 🔧 Configuration Sections

### LLM Configuration

```yaml
llm:
  provider: anthropic  # anthropic, openai, deepseek, ollama
  model: claude-3-5-sonnet-20241022
  max_tokens: 4096
  temperature: 0.7     # 0.0-1.0 (creativity)
  timeout_seconds: 30
```

**Providers:**
- `anthropic` - Claude (best quality)
- `openai` - GPT-4 (fast, good)
- `deepseek` - DeepSeek (cheap, fast)
- `ollama` - Local (offline, private)

### Fallback Chain

```yaml
fallback:
  enabled: true
  providers:
    - anthropic      # Try first (best)
    - deepseek       # Try second (fast)
    - rule_based     # Always works (fallback)
```

### Circuit Breaker

```yaml
circuit_breaker:
  enabled: true
  failure_threshold: 5        # Open after 5 failures
  timeout_seconds: 60.0       # Try reset after 60s
  success_threshold: 2        # Close after 2 successes
```

### Retry Logic

```yaml
retry:
  enabled: true
  max_attempts: 3
  initial_delay_seconds: 1.0  # Start with 1s
  max_delay_seconds: 30.0     # Cap at 30s
  exponential_base: 2.0       # Double each time
  jitter: true                # Add randomness
```

### Cache

```yaml
cache:
  enabled: true
  ttl_seconds: 3600           # 1 hour
  max_size_mb: 100            # 100MB max
```

### Safety & Sandbox

```yaml
safety:
  sandbox_enabled: true
  max_file_size_mb: 100
  allowed_paths:
    - "."
    - "/home/user/projects"
  blocked_commands:
    - "rm -rf /"
    - "dd if="
```

### Proactive Monitoring

```yaml
monitoring:
  enabled: true
  check_interval_seconds: 300     # Every 5 minutes
  disk_warning_threshold: 0.8     # Warn at 80%
  disk_critical_threshold: 0.9    # Critical at 90%
  cpu_warning_threshold: 0.8
  memory_warning_threshold: 0.85
```

### Feature Flags

```yaml
features:
  voice_interface: false         # Experimental
  multi_agent: false             # Experimental
  proactive_monitoring: true     # Stable
  tree_of_thoughts: true         # Stable
  prompt_evolution: true         # Stable
  goal_inference: true           # Stable
  self_reflection: true          # Stable
  data_visualization: true       # Stable
```

### Web Search

Zenus automatically searches the web for time-sensitive queries — sports schedules, software versions, news, prices, and anything where the LLM's training data may be stale. No configuration required: a key-free multi-source fallback is always active.

```yaml
search:
  # Brave Search API key for full web index coverage.
  # Free tier: 2,000 req/month — https://brave.com/search/api
  # Leave empty to use the key-free multi-source fallback.
  brave_api_key:            # or set BRAVE_SEARCH_API_KEY env var

  # Show query category, source breakdown, and raw results before the
  # synthesised answer. Useful for debugging search quality.
  # Can also be enabled at runtime with: ZENUS_SEARCH_DEBUG=1
  debug: false
```

**How it works:**

1. During intent translation, the LLM receives the current date/time and classifies every query: `search_provider: "web"` (needs current data), `search_provider: "llm"` (training knowledge is sufficient), or `null` (action intent — no lookup needed). It also sets `search_category` to one of `sports`, `tech`, `academic`, `news`, or `general`.
2. If `search_provider` is `"web"`, `WebSearchTool` runs only the relevant 3–4 sources in parallel for the given category (e.g. sports → Wikipedia + Reddit + RSS; tech → HackerNews + GitHub + Wikipedia + RSS).
3. If `search.brave_api_key` is set, Brave Search is tried first (full web index); fallback sources are used if the key is absent or returns nothing.
4. For question intents with web results, the orchestrator calls `llm.ask()` with the results — the user sees only the synthesised plain-text answer.
5. If the LLM sets `cannot_answer: true`, a context-specific fallback message is returned immediately without any search or tool execution.

**Priority for settings:**

| Setting | Config key | Env var |
|---|---|---|
| Brave API key | `search.brave_api_key` | `BRAVE_SEARCH_API_KEY` |
| Search debug | `debug.search` | `ZENUS_DEBUG_SEARCH=1` |

Config values take precedence over env vars. Both can be used simultaneously (config for persistent settings, env for temporary overrides).

**Fallback sources by query type:**

| Category | Sources (priority order) |
|---|---|
| sports | Wikipedia, Reddit, RSS (BBC) |
| tech | HackerNews, GitHub, Wikipedia, RSS (TechCrunch/Verge/Ars Technica) |
| academic | Semantic Scholar, arXiv, OpenAlex, Wikipedia |
| news | RSS feeds, Reddit, HackerNews, DDG Instant Answer |
| general | Wikipedia, DDG Instant Answer, RSS feeds |

---

### Debug Output Controls

By default Zenus produces clean, minimal output for end users. Developers can enable detailed debug logging per-subsystem without drowning in irrelevant noise.

```yaml
# config.yaml
debug:
  enabled: false          # master switch — enables every subsystem below
  orchestrator: false     # routing decisions, complexity scores, Tree of Thoughts, cache hits
  brain: false            # prompt-evolution promotions, model internals
  execution: false        # per-step output (tool.action: result), parallel fallback
  voice: false            # TTS/STT init messages, pipeline internals
  search: false           # query type, source breakdown, raw result snippets
```

All flags can also be set via environment variables (useful for a single session without editing `config.yaml`):

| Subsystem | Config key | Env var |
|---|---|---|
| Master | `debug.enabled` | `ZENUS_DEBUG=1` |
| Orchestrator | `debug.orchestrator` | `ZENUS_DEBUG_ORCHESTRATOR=1` |
| Brain | `debug.brain` | `ZENUS_DEBUG_BRAIN=1` |
| Execution | `debug.execution` | `ZENUS_DEBUG_EXECUTION=1` |
| Voice | `debug.voice` | `ZENUS_DEBUG_VOICE=1` |
| Search | `debug.search` | `ZENUS_DEBUG_SEARCH=1` |

Legacy aliases still work: `ZENUS_SEARCH_DEBUG=1` maps to `debug.search`; `search.debug: true` in config also maps to the search flag.

**Priority:** `config.yaml debug.*` → subsystem env var → master `ZENUS_DEBUG`. Setting the master switch enables all subsystems regardless of the individual flags.

---

## 🔌 MCP Integration

Zenus supports the Model Context Protocol (MCP) as both server and client.

### MCP Server (expose Zenus tools to external clients)

```yaml
mcp:
  server:
    enabled: false          # Set true to auto-start; or just run 'zenus mcp-server'
    transport: stdio        # stdio (Claude Code/Cline) | sse (HTTP)
    allow_privileged: false # Expose ShellOps/CodeExec — only in trusted environments
    host: 127.0.0.1         # SSE bind address (ignored for stdio)
    port: 8765              # SSE port (ignored for stdio)
```

| Key | Type | Default | Description |
|---|---|---|---|
| `mcp.server.enabled` | bool | `false` | Whether `zenus mcp-server` auto-starts; mostly useful if wrapping Zenus programmatically |
| `mcp.server.transport` | str | `"stdio"` | `"stdio"` for Claude Code/Cline subprocess; `"sse"` for HTTP-based clients |
| `mcp.server.allow_privileged` | bool | `false` | Include `ShellOps` and `CodeExec` in the exposed tool set |
| `mcp.server.host` | str | `"127.0.0.1"` | SSE bind host |
| `mcp.server.port` | int | `8765` | SSE bind port |

**Environment override:** `MCP_ALLOW_PRIVILEGED=1` enables privileged tools for the current session.

**Adding Zenus to Claude Code:**
```json
{
  "mcpServers": {
    "zenus": {
      "command": "zenus",
      "args": ["mcp-server"]
    }
  }
}
```

### MCP Client (consume external MCP servers)

```yaml
mcp:
  client:
    enabled: true
    servers:
      - name: filesystem          # tool-name prefix inside Zenus
        transport: stdio
        command: "uvx mcp-server-filesystem /home/user/docs"
        env: {}                   # optional extra env vars for the subprocess
      - name: remote
        transport: sse
        url: "http://localhost:8080/sse"
```

| Key | Type | Default | Description |
|---|---|---|---|
| `mcp.client.enabled` | bool | `false` | Connect to external servers at startup |
| `mcp.client.servers[].name` | str | — | Unique prefix; tools appear as `mcp__{name}__{tool}` |
| `mcp.client.servers[].transport` | str | `"stdio"` | `"stdio"` or `"sse"` |
| `mcp.client.servers[].command` | str | — | Subprocess command for stdio transport |
| `mcp.client.servers[].url` | str | — | SSE endpoint URL |
| `mcp.client.servers[].env` | dict | `{}` | Extra env vars for stdio subprocess |

---

## 🔒 Secrets Management

### .env File

```bash
# ~/.zenus/.env

# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# OpenAI (GPT)
OPENAI_API_KEY=sk-your-key-here
OPENAI_API_BASE_URL=https://api.openai.com/v1

# DeepSeek
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_API_BASE_URL=https://api.deepseek.com

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3:mini

# Web Search (optional — key-free fallback always available)
# BRAVE_SEARCH_API_KEY=your-key-here   # https://brave.com/search/api

# Debug output (all off by default — prefer config.yaml for persistent use)
# ZENUS_DEBUG=1                        # master switch (enables all subsystems)
# ZENUS_DEBUG_ORCHESTRATOR=1           # routing, complexity, Tree of Thoughts
# ZENUS_DEBUG_BRAIN=1                  # prompt evolution, model internals
# ZENUS_DEBUG_EXECUTION=1              # per-step execution, parallel fallback
# ZENUS_DEBUG_VOICE=1                  # TTS/STT init and pipeline messages
# ZENUS_DEBUG_SEARCH=1                 # search decisions and result breakdown
# ZENUS_SEARCH_DEBUG=1                 # legacy alias for ZENUS_DEBUG_SEARCH
```

### Programmatic Access

```python
from zenus_core.config import get_secrets

secrets = get_secrets()

# Get specific secret
api_key = secrets.get("ANTHROPIC_API_KEY")

# Get LLM API key
api_key = secrets.get_llm_api_key("anthropic")

# Check if secret exists
if secrets.has_secret("OPENAI_API_KEY"):
    # Use OpenAI

# Mask for logging
masked = secrets.mask_secret(api_key)
print(f"Using key: {masked}")  # sk-ant-***xyz
```

---

## 🔄 Hot-Reload

Config changes apply **instantly** without restart!

```bash
# Start Zenus
zenus

# Edit config (in another terminal)
vim ~/.zenus/config.yaml
# Change temperature: 0.7 -> 0.9
# Save

# Next command uses new temperature!
# No restart needed! 🎉
```

**How it works:**
- Uses `watchdog` to monitor config file
- Reloads automatically on changes
- Validates schema before applying
- Falls back to old config on errors

---

## 🛠️ CLI Commands

```bash
# Show current config
zenus config show

# Show current profile
zenus config profile

# Validate config
zenus config validate

# Reload config (manual)
zenus config reload

# Show config file path
zenus config path

# Create default config
zenus config init
```

---

## 💻 Programmatic Usage

### Load Configuration

```python
from zenus_core.config import get_config

# Get config (auto-loads)
config = get_config()

# Access settings
print(config.llm.provider)      # "anthropic"
print(config.llm.temperature)   # 0.7
print(config.features.tree_of_thoughts)  # True

# Check profile
if config.is_production():
    # Production-specific logic
    pass

# Reload manually
from zenus_core.config import reload_config
config = reload_config()
```

### Save Configuration

```python
from zenus_core.config import get_config, ConfigLoader

config = get_config()

# Modify config
config.llm.temperature = 0.9
config.features.multi_agent = True

# Save (writes to file)
loader = ConfigLoader()
loader.save_config(config)
```

---

## 🎯 Best Practices

### ✅ DO:
- Use `production` profile in production
- Keep secrets in `.env` files
- Use profiles for different environments
- Enable sandbox in production
- Set restrictive `allowed_paths`
- Version control `config.yaml.example`

### ❌ DON'T:
- Put API keys in `config.yaml`
- Commit `.env` files
- Use dev config in production
- Disable sandbox in production
- Share secrets across environments

---

## 🐛 Troubleshooting

### Config Not Found

```bash
# Check search paths
ls -la ~/.zenus/config.yaml
ls -la ./zenus.yaml

# Create default
zenus config init
```

### Invalid Config

```bash
# Validate
zenus config validate

# Check errors
zenus config check

# Use default if broken
mv ~/.zenus/config.yaml ~/.zenus/config.yaml.backup
zenus config init
```

### Hot-Reload Not Working

```bash
# Install watchdog
pip install watchdog

# Check if installed
python -c "import watchdog; print('✓ Installed')"

# Restart Zenus
```

### Secrets Not Loading

```bash
# Check .env location
ls -la ~/.zenus/.env
ls -la ./.env

# Check syntax
cat ~/.zenus/.env

# Test loading
python -c "
from zenus_core.config import get_secrets
secrets = get_secrets()
print(secrets.list_available())
"
```

---

## 📊 Configuration Priority

Settings are loaded in this order (later overrides earlier):

1. **Default values** (in schema)
2. **Base config** (config.yaml root level)
3. **Profile overrides** (config.yaml profiles section)
4. **Environment variables** (ZENUS_*)
5. **Command-line flags** (--temperature, etc.)

---

## 🚀 Examples

### Development Setup

```yaml
# ~/.zenus/config.yaml
profile: dev

llm:
  temperature: 0.9  # More creative

safety:
  sandbox_enabled: false  # Convenience

cache:
  ttl_seconds: 300  # 5 minutes (shorter)

features:
  voice_interface: true  # Experimental OK
  multi_agent: true
```

### Production Setup

```yaml
# ~/.zenus/config.yaml
profile: production

llm:
  temperature: 0.5  # Conservative

safety:
  sandbox_enabled: true  # Always
  allowed_paths:
    - "/app/workspace"

cache:
  ttl_seconds: 3600  # 1 hour

features:
  voice_interface: false  # Stable only
  multi_agent: true
```

---

---

## Phase 1.6 — Advanced Features

### Hook Pipeline (PreToolUse / PostToolUse)

Run custom shell commands before or after any tool action. A pre-hook that exits non-zero denies the action; post-hooks run asynchronously and never block.

```yaml
hooks:
  pre_tool_use:
    - match: "ShellOps"          # tool name, "Tool.action", or "*" for all
      command: "echo pre ShellOps"
      timeout_seconds: 10        # default 10

  post_tool_use:
    - match: "*"
      command: "logger 'zenus tool used'"
      timeout_seconds: 10
```

| Key | Type | Default | Description |
|---|---|---|---|
| `hooks.pre_tool_use` | list | `[]` | Commands run before each matching tool action |
| `hooks.post_tool_use` | list | `[]` | Commands run after each matching tool action |
| `match` | str | — | fnmatch pattern against `ToolName` or `ToolName.action_name` |
| `command` | str | — | Shell command (runs via `sh -c`) |
| `timeout_seconds` | int | `10` | Max seconds before the hook is killed |

**Match examples:** `"ShellOps"`, `"FileOps.delete_file"`, `"*"`, `"*.read_*"`

---

### Plan Mode

When enabled, Zenus presents the full execution plan to the user for approval before running any step.

```yaml
plan_mode:
  enabled: false              # start with plan mode off
  auto_approve_low_risk: false # auto-approve plans where every step is READ-only (risk=0)
```

| Key | Type | Default | Description |
|---|---|---|---|
| `plan_mode.enabled` | bool | `false` | Activate plan gate on startup |
| `plan_mode.auto_approve_low_risk` | bool | `false` | Skip prompt when all steps are risk=0 |

Toggle at runtime: `/plan` in the interactive shell.

---

### Skills Registry

User-extensible slash commands loaded from Markdown files. Skills are invoked with `/skill-name [args]`.

```yaml
skills:
  enabled: true             # set false to disable all skills
  load_bundled: true        # load built-in skills (commit, review-pr, etc.)
  skills_dir: null          # extra directory of *.md skill files (optional)
```

| Key | Type | Default | Description |
|---|---|---|---|
| `skills.enabled` | bool | `true` | Enable/disable the skills system |
| `skills.load_bundled` | bool | `true` | Load the built-in bundled skills |
| `skills.skills_dir` | str\|null | `null` | Extra directory to load `*.md` skill files from |

**Skill file format** (`~/.zenus/skills/my-skill.md`):

```markdown
---
name: My Skill
trigger: my-skill
description: Does something useful
---

Do the thing with {args}.
```

Discovery order (highest priority wins): project `.zenus/skills/` → `~/.zenus/skills/` → `skills_dir` → bundled.

---

### Session Store

Persist conversation sessions to disk so they can be resumed later.

```yaml
session:
  persist: true              # save sessions to disk
  sessions_dir: null         # override ~/.zenus/sessions/
  max_sessions: 50           # auto-prune oldest when exceeded
  compact_threshold: 0.80   # trigger /compact when context hits 80%
```

| Key | Type | Default | Description |
|---|---|---|---|
| `session.persist` | bool | `true` | Write session JSON files to disk |
| `session.sessions_dir` | str\|null | `null` | Override default `~/.zenus/sessions/` directory |
| `session.max_sessions` | int | `50` | Oldest sessions are pruned when this is exceeded |
| `session.compact_threshold` | float | `0.80` | 0.0–1.0; auto-compacts when `token_count / max_tokens` exceeds this |

Session files are stored at `~/.zenus/sessions/<id>.json` with permissions `0600`.

---

### Output Style

Choose how Zenus renders its output.

```yaml
output_style:
  style: rich   # rich | plain | compact | json
```

| Value | Description |
|---|---|
| `rich` | Full colour, icons, rich markdown (default) |
| `plain` | Plain text, no ANSI colour codes |
| `compact` | Minimal output — just the result |
| `json` | Machine-readable JSON output |

Change at runtime: `/output-style <style>` in the interactive shell.

---

**See Also:**
- [CONFIG_MIGRATION_GUIDE.md](CONFIG_MIGRATION_GUIDE.md) - Migrate from .env
- [ERROR_HANDLING_GUIDE.md](ERROR_HANDLING_GUIDE.md) - Circuit breakers & retries
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing configuration
