"""
LLM Factory

Creates LLM instances based on configuration.
Priority: config.yaml > environment variables (backwards compat)
"""

from dotenv import load_dotenv, find_dotenv # type: ignore
import os
from typing import Optional
from zenus_core.brain.llm.openai_llm import OpenAILLM
from zenus_core.brain.llm.deepseek_llm import DeepSeekLLM
from zenus_core.brain.llm.anthropic_llm import AnthropicLLM
from zenus_core.brain.llm.ollama_llm import OllamaLLM
from zenus_core.config.loader import get_config

# Load secrets - find_dotenv searches up the directory tree for .env
# This works both for running from source and installed packages
load_dotenv(find_dotenv(usecwd=True))

def get_llm(force_provider: Optional[str] = None):
    """
    Get LLM instance based on configuration
    
    Priority:
    1. force_provider argument (router override)
    2. ZENUS_LLM environment variable (backwards compatibility)
    3. config.yaml llm.provider setting
    
    Args:
        force_provider: Override provider (used by router)
    
    Returns:
        LLM instance
    """
    # Try to load from config.yaml first
    backend = None
    model = None
    
    try:
        config = get_config()
        backend = config.llm.provider
        model = config.llm.model
    except Exception:
        # Config loading failed, fall back to env vars
        pass
    
    # Override with force_provider (router)
    if force_provider:
        backend = force_provider
    
    # Fall back to environment variable (backwards compatibility)
    if not backend:
        backend = os.getenv("ZENUS_LLM", "anthropic")
    
    # Create LLM instance
    if backend == "deepseek":
        return DeepSeekLLM()
    elif backend == "anthropic":
        return AnthropicLLM()
    elif backend == "ollama":
        ollama_model = model if model else os.getenv("OLLAMA_MODEL", "phi3:mini")
        return OllamaLLM(model=ollama_model)
    elif backend == "openai":
        return OpenAILLM()
    else:
        # Unknown provider, default to anthropic
        print(f"⚠️  Unknown provider '{backend}', defaulting to anthropic")
        return AnthropicLLM()


def get_available_providers() -> list[str]:
    """
    Detect which LLM providers are configured and available
    
    Checks for:
    - API keys in environment
    - config.yaml settings
    - Ollama service availability
    
    Returns:
        List of available provider names (e.g., ['anthropic', 'deepseek'])
    """
    available = []
    
    # Check Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append("anthropic")
    
    # Check DeepSeek
    if os.getenv("DEEPSEEK_API_KEY"):
        available.append("deepseek")
    
    # Check OpenAI
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")
    
    # Check Ollama (try to connect)
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            available.append("ollama")
    except:
        pass
    
    # If nothing is available, default to anthropic
    # (will fail later with better error message)
    if not available:
        available.append("anthropic")
    
    return available
