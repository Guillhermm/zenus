"""
Model Router

Routes tasks to appropriate LLM based on complexity:
- Simple tasks → Cheap/fast models (DeepSeek, local)
- Complex tasks → Powerful models (Claude, GPT-4)

Includes fallback cascade and cost tracking.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime

from zenus_core.brain.task_complexity import TaskComplexityAnalyzer, ComplexityScore
from zenus_core.brain.llm.factory import get_llm, get_available_providers


@dataclass
class RoutingDecision:
    """Record of a routing decision"""
    timestamp: str
    user_input: str
    complexity_score: float
    selected_model: str
    reasons: List[str]
    fallback_used: bool = False
    success: bool = True
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None


class ModelRouter:
    """
    Routes tasks to appropriate LLM based on complexity
    
    Features:
    - Complexity-based routing
    - Fallback cascade
    - Cost tracking
    - Performance monitoring
    - Decision logging
    """
    
    # Model costs (per 1M tokens, rough estimates)
    MODEL_COSTS = {
        'deepseek': 0.15,      # $0.15 per 1M tokens (cheap)
        'ollama': 0.0,         # Free (local)
        'openai': 1.0,         # $1 per 1M tokens (medium)
        'anthropic': 3.0,      # $3 per 1M tokens (expensive but best)
    }
    
    # Model capabilities (0.0 = weak, 1.0 = strongest)
    MODEL_CAPABILITIES = {
        'ollama': 0.5,
        'deepseek': 0.7,
        'openai': 0.85,
        'anthropic': 1.0,
    }
    
    def __init__(
        self,
        stats_path: Optional[str] = None,
        enable_fallback: Optional[bool] = None,
        log_decisions: bool = True,
        fallback_providers: Optional[List[str]] = None
    ):
        self.complexity_analyzer = TaskComplexityAnalyzer()
        
        # Try to load from config.yaml if not explicitly provided
        if enable_fallback is None or fallback_providers is None:
            try:
                from zenus_core.config.loader import get_config
                config = get_config()
                if enable_fallback is None:
                    enable_fallback = config.fallback.enabled
                if fallback_providers is None:
                    fallback_providers = config.fallback.providers
            except Exception:
                # Config loading failed, use defaults
                if enable_fallback is None:
                    enable_fallback = False  # Default to disabled for safety
                if fallback_providers is None:
                    fallback_providers = []
        
        self.enable_fallback = enable_fallback
        self.log_decisions = log_decisions
        
        # Detect which providers have API keys
        available_with_keys = get_available_providers()
        
        # Determine which providers to use
        if not enable_fallback:
            # Fallback disabled: ONLY use the primary provider from config
            try:
                from zenus_core.config.loader import get_config
                config = get_config()
                primary_provider = config.llm.provider
                # Only include primary if it has a key
                if primary_provider in available_with_keys:
                    self.available_providers = [primary_provider]
                else:
                    # Primary doesn't have key, use any available
                    self.available_providers = available_with_keys[:1] if available_with_keys else []
            except Exception:
                # Config failed, use first available
                self.available_providers = available_with_keys[:1] if available_with_keys else []
        elif fallback_providers:
            # Fallback enabled: use providers from config that have keys
            self.available_providers = [
                p for p in fallback_providers 
                if p in available_with_keys
            ]
        else:
            # No config, use whatever has keys
            self.available_providers = available_with_keys
        
        # Build capability map only for available providers
        self.available_capabilities = {
            provider: self.MODEL_CAPABILITIES[provider]
            for provider in self.available_providers
            if provider in self.MODEL_CAPABILITIES
        }
        
        # Stats file
        if stats_path is None:
            stats_path = Path.home() / ".zenus" / "router_stats.json"
        self.stats_path = Path(stats_path)
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load stats
        self.stats = self._load_stats()
        
        # Decision log
        self.decisions: List[RoutingDecision] = []
        
        # Current session stats
        self.session_stats = {
            'commands': 0,
            'tokens_used': 0,
            'estimated_cost': 0.0,
            'cache_hits': 0,
        }
    
    def route(
        self,
        user_input: str,
        iterative: bool = False,
        force_model: Optional[str] = None
    ) -> tuple[str, ComplexityScore]:
        """
        Route task to appropriate model
        
        Args:
            user_input: Natural language command
            iterative: Whether iterative mode requested
            force_model: Force specific model (overrides routing)
        
        Returns:
            (selected_model, complexity_score)
        """
        # Analyze complexity
        complexity = self.complexity_analyzer.analyze(user_input, iterative)
        
        # Check for forced model
        if force_model:
            selected_model = force_model
            complexity.reasons.append(f"Forced model: {force_model}")
        else:
            selected_model = complexity.recommended_model
        
        # Log decision
        if self.log_decisions:
            decision = RoutingDecision(
                timestamp=datetime.now().isoformat(),
                user_input=user_input[:100],  # Truncate for privacy
                complexity_score=complexity.score,
                selected_model=selected_model,
                reasons=complexity.reasons,
            )
            self.decisions.append(decision)
        
        # Update stats
        self.session_stats['commands'] += 1
        
        return selected_model, complexity
    
    def execute_with_fallback(
        self,
        user_input: str,
        execute_fn,
        iterative: bool = False,
        max_fallbacks: int = 2
    ):
        """
        Execute with fallback cascade
        
        Tries models in order of capability until success:
        1. Recommended model
        2. More powerful model (if failed)
        3. Most powerful model (if still failed)
        
        Args:
            user_input: Natural language command
            execute_fn: Function to execute (receives model_backend)
            iterative: Whether iterative mode
            max_fallbacks: Maximum fallback attempts
        
        Returns:
            Result from execute_fn
        
        Raises:
            Exception: If all models fail
        """
        # Get initial routing
        selected_model, complexity = self.route(user_input, iterative)
        
        # Build fallback chain
        fallback_chain = self._build_fallback_chain(selected_model, max_fallbacks)
        
        last_error = None
        
        for attempt, model_backend in enumerate(fallback_chain):
            try:
                start_time = time.time()
                
                # Set environment variable for factory
                os.environ['ZENUS_LLM'] = model_backend
                
                # Execute
                result = execute_fn(model_backend)
                
                latency_ms = (time.time() - start_time) * 1000
                
                # Log success
                if self.log_decisions and self.decisions:
                    self.decisions[-1].success = True
                    self.decisions[-1].latency_ms = latency_ms
                    self.decisions[-1].fallback_used = (attempt > 0)
                
                # Update stats
                self._update_stats(model_backend, success=True, latency_ms=latency_ms)
                
                return result
            
            except Exception as e:
                last_error = e
                
                # Log failure
                if self.log_decisions and self.decisions:
                    self.decisions[-1].success = False
                
                # Update stats
                self._update_stats(model_backend, success=False)
                
                # Try next in fallback chain
                if attempt < len(fallback_chain) - 1:
                    print(f"  [Router] {model_backend} failed, trying {fallback_chain[attempt + 1]}...")
                    continue
                else:
                    # All attempts failed
                    break
        
        # All models failed
        raise Exception(f"All models failed. Last error: {last_error}")
    
    def _build_fallback_chain(self, primary_model: str, max_fallbacks: int) -> List[str]:
        """
        Build fallback chain from weakest to strongest
        
        ONLY includes models that are actually configured/available.
        
        Args:
            primary_model: Initially selected model
            max_fallbacks: Maximum number of fallbacks
        
        Returns:
            List of model backends in order to try
        """
        # If fallback disabled or only one model available, just use primary
        if not self.enable_fallback or len(self.available_providers) <= 1:
            return [primary_model]
        
        # Ensure primary model is available
        if primary_model not in self.available_providers:
            # Primary not available, use most powerful available model
            primary_model = max(
                self.available_capabilities.keys(),
                key=lambda m: self.available_capabilities[m]
            )
        
        # Sort ONLY available models by capability (weakest to strongest)
        available_models = sorted(
            self.available_capabilities.keys(),
            key=lambda m: self.available_capabilities[m]
        )
        
        # Start with primary model
        chain = [primary_model]
        
        # Add more powerful models as fallbacks
        primary_capability = self.available_capabilities.get(primary_model, 0.5)
        
        for model in available_models:
            if model == primary_model:
                continue
            
            capability = self.available_capabilities[model]
            
            # Only add more powerful models
            if capability > primary_capability:
                chain.append(model)
            
            # Respect max_fallbacks
            if len(chain) >= max_fallbacks + 1:
                break
        
        return chain
    
    def track_tokens(self, model_backend: str, tokens: int):
        """
        Track token usage for cost estimation
        
        Args:
            model_backend: Which model was used
            tokens: Number of tokens consumed
        """
        self.session_stats['tokens_used'] += tokens
        
        # Estimate cost
        cost_per_1m = self.MODEL_COSTS.get(model_backend, 0.0)
        cost = (tokens / 1_000_000) * cost_per_1m
        self.session_stats['estimated_cost'] += cost
        
        # Update global stats
        if model_backend not in self.stats['models']:
            self.stats['models'][model_backend] = {
                'total_tokens': 0,
                'total_cost': 0.0,
                'total_requests': 0,
                'successes': 0,
                'failures': 0,
            }
        
        self.stats['models'][model_backend]['total_tokens'] += tokens
        self.stats['models'][model_backend]['total_cost'] += cost
        
        # Save stats
        self._save_stats()
    
    def _update_stats(
        self,
        model_backend: str,
        success: bool,
        latency_ms: Optional[float] = None
    ):
        """Update routing statistics"""
        if model_backend not in self.stats['models']:
            self.stats['models'][model_backend] = {
                'total_tokens': 0,
                'total_cost': 0.0,
                'total_requests': 0,
                'successes': 0,
                'failures': 0,
                'avg_latency_ms': 0.0,
            }
        
        model_stats = self.stats['models'][model_backend]
        model_stats['total_requests'] += 1
        
        if success:
            model_stats['successes'] += 1
        else:
            model_stats['failures'] += 1
        
        # Update average latency
        if latency_ms is not None:
            prev_avg = model_stats.get('avg_latency_ms', 0.0)
            prev_count = model_stats['total_requests'] - 1
            
            new_avg = (prev_avg * prev_count + latency_ms) / model_stats['total_requests']
            model_stats['avg_latency_ms'] = new_avg
        
        self._save_stats()
    
    def get_stats(self) -> Dict:
        """Get routing statistics"""
        return {
            'session': self.session_stats,
            'all_time': self.stats,
        }
    
    def _load_stats(self) -> Dict:
        """Load stats from disk"""
        if not self.stats_path.exists():
            return {
                'models': {},
                'total_commands': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
            }
        
        try:
            with open(self.stats_path, 'r') as f:
                return json.load(f)
        except:
            return {
                'models': {},
                'total_commands': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
            }
    
    def _save_stats(self):
        """Save stats to disk"""
        try:
            with open(self.stats_path, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            # Non-critical, just log
            print(f"  [Router] Failed to save stats: {e}")


def get_router() -> ModelRouter:
    """
    Get router instance
    
    Note: Creates a new router each time to ensure config changes are picked up.
    This is intentional - the overhead of reading config is minimal compared to
    the bugs caused by stale singleton instances.
    """
    return ModelRouter()
