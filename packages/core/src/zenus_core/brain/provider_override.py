"""
Provider Override Parser

Detects and strips on-the-fly provider/model override directives from user
input so any command can target a specific LLM without changing defaults.

Supported syntaxes (case-insensitive):
    @deepseek: organize my downloads          → provider=deepseek
    use claude: organize my downloads         → provider=anthropic
    using openai, organize my downloads       → provider=openai
    --provider deepseek organize my downloads → provider=deepseek
    --provider=deepseek organize my downloads → provider=deepseek
    --model claude-opus-4-6 do X             → provider=anthropic, model=claude-opus-4-6
    --model=gpt-4o do X                      → provider=openai, model=gpt-4o
"""

import re
from typing import Optional, Tuple

# Canonical provider names and their common aliases
PROVIDER_ALIASES: dict[str, str] = {
    # Anthropic
    "anthropic": "anthropic",
    "claude": "anthropic",
    "sonnet": "anthropic",
    "haiku": "anthropic",
    "opus": "anthropic",
    # OpenAI
    "openai": "openai",
    "gpt": "openai",
    "chatgpt": "openai",
    "o1": "openai",
    "o3": "openai",
    # DeepSeek
    "deepseek": "deepseek",
    # Ollama
    "ollama": "ollama",
    "local": "ollama",
    "llama": "ollama",
}


def _infer_provider_from_model(model: str) -> Optional[str]:
    """Guess provider from a model identifier string."""
    m = model.lower()
    if "claude" in m or "haiku" in m or "sonnet" in m or "opus" in m:
        return "anthropic"
    if "gpt" in m or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
        return "openai"
    if "deepseek" in m:
        return "deepseek"
    if any(x in m for x in ("llama", "qwen", "mistral", "phi", "gemma")):
        return "ollama"
    return None


def parse_provider_override(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Extract an inline provider/model override from user input.

    Returns:
        (clean_text, provider, model)
        - clean_text:  original input with the override directive removed
        - provider:    canonical provider name ('anthropic', 'openai', 'deepseek', 'ollama') or None
        - model:       explicit model identifier or None
    """
    provider: Optional[str] = None
    model: Optional[str] = None
    clean = text.strip()

    # --model=X  or  --model X  (must come before --provider so we can infer provider)
    m = re.match(
        r'^--model[=\s]+(\S+)\s*(.*)',
        clean,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        model = m.group(1)
        clean = m.group(2).strip()
        provider = _infer_provider_from_model(model)

    # --provider=X  or  --provider X
    m = re.match(
        r'^--provider[=\s]+(\S+)\s*(.*)',
        clean,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        alias = m.group(1).lower().rstrip(':,')
        resolved = PROVIDER_ALIASES.get(alias)
        if resolved:
            provider = resolved
            clean = m.group(2).strip()

    # @provider:  text
    m = re.match(r'^@(\w+)[:\s]+(.+)', clean, re.IGNORECASE | re.DOTALL)
    if m:
        alias = m.group(1).lower()
        resolved = PROVIDER_ALIASES.get(alias)
        if resolved:
            provider = resolved
            clean = m.group(2).strip()

    # "use provider:"  or  "using provider,"  at start of input
    m = re.match(
        r'^using?\s+(\w+)[:\s,]+(.+)',
        clean,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        alias = m.group(1).lower()
        resolved = PROVIDER_ALIASES.get(alias)
        if resolved:
            provider = resolved
            clean = m.group(2).strip()

    # If we extracted everything and clean is now empty, restore original
    if not clean:
        return text.strip(), None, None

    return clean, provider, model


def describe_override(provider: Optional[str], model: Optional[str]) -> str:
    """Return a short human-readable description of the override for display."""
    if model and provider:
        return f"{provider}/{model}"
    if model:
        return model
    if provider:
        return provider
    return ""
