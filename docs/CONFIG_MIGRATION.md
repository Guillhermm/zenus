# Configuration Migration Guide

**Migrating from .env to config.yaml**

Zenus now uses modern YAML configuration with profile support and hot-reload!

---

## 🎯 Why Migrate?

### Old (.env)
```bash
# .env
ZENUS_LLM=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
# ... 20+ environment variables
```

**Problems:**
- ❌ No type validation
- ❌ No profiles (dev/staging/production)
- ❌ Hard to organize
- ❌ API keys mixed with config
- ❌ No hot-reload

### New (config.yaml)
```yaml
# config.yaml
profile: dev
llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  temperature: 0.7
  
# API keys in .env (separate)
```

**Benefits:**
- ✅ Type-safe (Pydantic validation)
- ✅ Multiple profiles (dev/staging/production)
- ✅ Well-organized structure
- ✅ Secrets separate from config
- ✅ Hot-reload (changes apply instantly)

---

## 🚀 Quick Start

### 1. Create Config File

Copy the example:
```bash
cp config.yaml.example ~/.zenus/config.yaml
```

Or let Zenus create it automatically:
```bash
zenus help  # Creates default config on first run
```

### 2. Keep API Keys in .env

Create `~/.zenus/.env`:
```bash
# ~/.zenus/.env
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
DEEPSEEK_API_KEY=sk-your-key-here
```

**Important:** API keys stay in `.env` for security!

### 3. Choose Profile

Set profile via environment variable:
```bash
export ZENUS_PROFILE=dev        # Development
export ZENUS_PROFILE=staging    # Staging
export ZENUS_PROFILE=production # Production
```

Or in config.yaml:
```yaml
profile: dev  # dev, staging, or production
```

---

## 📋 Migration Mapping

### LLM Configuration

**Old (.env):**
```bash
ZENUS_LLM=anthropic
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_TOKENS=4096
```

**New (config.yaml):**
```yaml
llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  max_tokens: 4096
  temperature: 0.7
  timeout_seconds: 30
```

**Secrets (.env):**
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

---

### Feature Flags

**Old (.env):**
```bash
ZENUS_FEATURE_VOICE=false
ZENUS_FEATURE_MULTI_AGENT=false
```

**New (config.yaml):**
```yaml
features:
  voice_interface: false
  multi_agent: false
  proactive_monitoring: true
  tree_of_thoughts: true
```

---

### Safety & Sandbox

**Old (.env):**
```bash
ZENUS_SANDBOX=true
ZENUS_MAX_FILE_SIZE=100
```

**New (config.yaml):**
```yaml
safety:
  sandbox_enabled: true
  max_file_size_mb: 100
  allowed_paths:
    - "."
  blocked_commands:
    - "rm -rf /"
```

---

## 🎭 Profile System

The profile system lets you have different configs for different environments:

### config.yaml
```yaml
# Base configuration (shared)
llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022

# Profile-specific overrides
profiles:
  dev:
    llm:
      temperature: 0.9    # More creative in dev
    safety:
      sandbox_enabled: false  # Disabled for convenience
  
  production:
    llm:
      temperature: 0.5    # More conservative
    safety:
      sandbox_enabled: true   # Always sandboxed
    features:
      voice_interface: false  # Stable only
```

### Switching Profiles

```bash
# Development (default)
ZENUS_PROFILE=dev zenus "list files"

# Staging
ZENUS_PROFILE=staging zenus "deploy app"

# Production
ZENUS_PROFILE=production zenus "backup database"
```

---

## 🔄 Hot-Reload

Config changes apply **instantly** without restart!

```bash
# Terminal 1: Run Zenus
zenus

# Terminal 2: Edit config
vim ~/.zenus/config.yaml
# Change temperature: 0.7 -> 0.9
# Save

# Terminal 1: Next command uses new config!
# No restart needed! 🎉
```

---

## 🔒 Security Best Practices

### ✅ DO:
- Keep API keys in `.env` files
- Use restrictive file permissions: `chmod 600 ~/.zenus/.env`
- Use different keys for dev/staging/production
- Never commit `.env` files to git
- Use `production` profile in production

### ❌ DON'T:
- Put API keys in `config.yaml`
- Commit `config.yaml` with secrets
- Use dev config in production
- Share API keys across environments

---

## 📂 File Locations

### Config File (config.yaml)
Searched in this order:
1. `$ZENUS_CONFIG` (environment variable)
2. `./zenus.yaml` (current directory)
3. `./zenus.yml`
4. `./.zenus.yaml`
5. `~/.zenus/config.yaml` (default)
6. `~/.config/zenus/config.yaml`

### Secrets File (.env)
Searched in this order:
1. `./.env` (current directory)
2. `./.env.local`
3. `~/.zenus/.env` (recommended)

---

## 🛠️ Programmatic Access

### Python
```python
from zenus_core.config import get_config, get_secrets

# Get configuration
config = get_config()
print(f"Provider: {config.llm.provider}")
print(f"Temperature: {config.llm.temperature}")

# Get secrets
secrets = get_secrets()
api_key = secrets.get_llm_api_key("anthropic")

# Reload config (hot-reload)
from zenus_core.config import reload_config
config = reload_config()
```

### CLI
```bash
# Check current config
zenus config show

# Reload config
zenus config reload

# Validate config
zenus config validate
```

---

## 🐛 Troubleshooting

### Config not found
```bash
# Check search paths
zenus config paths

# Create default
zenus config init
```

### Invalid config
```bash
# Validate schema
zenus config validate

# Show errors
zenus config check
```

### Hot-reload not working
```bash
# Check if watchdog installed
pip install watchdog

# Or disable hot-reload
# (Restart Zenus after config changes)
```

---

## 📚 Complete Example

### ~/.zenus/config.yaml
```yaml
version: "0.5.1"
profile: dev

llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  max_tokens: 4096
  temperature: 0.7

fallback:
  enabled: true
  providers:
    - anthropic
    - deepseek
    - rule_based

features:
  tree_of_thoughts: true
  self_reflection: true
  data_visualization: true

profiles:
  dev:
    llm:
      temperature: 0.9
  
  production:
    llm:
      temperature: 0.5
    features:
      multi_agent: true
```

### ~/.zenus/.env
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
DEEPSEEK_API_KEY=sk-your-key-here
```

### Usage
```bash
# Development
ZENUS_PROFILE=dev zenus "analyze logs"

# Production
ZENUS_PROFILE=production zenus "deploy"
```

---

## ✅ Migration Checklist

- [ ] Create `~/.zenus/config.yaml` from example
- [ ] Move API keys to `~/.zenus/.env`
- [ ] Remove old environment variables
- [ ] Set `ZENUS_PROFILE` environment variable
- [ ] Test with `zenus config validate`
- [ ] Remove old `.env` file (optional)
- [ ] Update deployment scripts
- [ ] Document profile usage for team

---

**Next:** See [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) for advanced usage!
