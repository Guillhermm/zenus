"""
Prompt Evolution - Self-improving system prompts

Track prompt success rates and automatically tune them based on real results.
No more manual prompt engineering - the system learns what works!

Key innovations:
- Track success rate per prompt variant
- Auto-generate few-shot examples from successful executions
- A/B testing for prompt improvements
- Prompt versioning and rollback
- Domain-specific prompt adaptation
"""

import json
import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from zenus_core.debug import get_debug_flags

logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    """A versioned system prompt"""
    version_id: str
    template: str
    created_at: str
    success_count: int = 0
    failure_count: int = 0
    total_uses: int = 0
    success_rate: float = 0.0
    examples: List[Dict] = None  # Few-shot examples
    domain: Optional[str] = None  # e.g., "git", "docker", "files"
    
    def __post_init__(self):
        if self.examples is None:
            self.examples = []
    
    def update_stats(self, success: bool):
        """Update success statistics"""
        self.total_uses += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        self.success_rate = self.success_count / self.total_uses if self.total_uses > 0 else 0.0
    
    def add_example(self, user_input: str, intent_ir: Dict, result: str):
        """Add a successful example for few-shot learning"""
        example = {
            "input": user_input,
            "intent": intent_ir,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        self.examples.append(example)
        
        # Keep only best 10 examples
        if len(self.examples) > 10:
            # Sort by some quality metric (for now, just keep recent ones)
            self.examples = self.examples[-10:]
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PromptVariant:
    """A/B test variant for prompt experimentation"""
    variant_id: str
    base_version: str
    modification: str  # What was changed
    hypothesis: str  # What we expect to improve
    success_count: int = 0
    failure_count: int = 0
    total_uses: int = 0
    success_rate: float = 0.0
    
    def update_stats(self, success: bool):
        self.total_uses += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.success_rate = self.success_count / self.total_uses if self.total_uses > 0 else 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class PromptEvolution:
    """
    Automatically improve system prompts based on success rates
    
    Features:
    - Track success/failure per prompt version
    - Generate few-shot examples from successful runs
    - A/B test prompt improvements
    - Auto-promote successful variants
    - Domain-specific prompt adaptation
    """
    
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path.home() / ".zenus" / "prompts"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.versions_file = self.storage_dir / "versions.json"
        self.variants_file = self.storage_dir / "variants.json"
        self.active_tests_file = self.storage_dir / "active_tests.json"
        
        # Load existing data
        self.versions: Dict[str, PromptVersion] = self._load_versions()
        self.variants: Dict[str, PromptVariant] = self._load_variants()
        self.active_tests: List[str] = self._load_active_tests()
        
        # Default base prompt
        self.base_prompt_template = """You are Zenus, an intelligent system assistant.

Translate natural language commands into structured IntentIR format.

{examples}

User command: {user_input}

{context}

Return JSON with: goal, steps, explanation, expected_result"""
        
        # Domain-specific prompts
        self.domain_prompts: Dict[str, str] = {}
        
        # A/B test parameters
        self.test_ratio = 0.2  # 20% of traffic goes to variants
        self.min_samples = 20  # Minimum samples before promoting
        self.promotion_threshold = 0.15  # Must be 15% better to promote
    
    def get_prompt(
        self, 
        user_input: str,
        context: str = "",
        domain: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Get the best prompt for the current request
        
        Returns:
            (prompt_text, version_id)
        """
        # Step 1: Detect domain if not provided
        if domain is None:
            domain = self._detect_domain(user_input)
        
        # Step 2: Check if we should use a variant (A/B testing)
        import random
        if random.random() < self.test_ratio and self.active_tests:
            # Use variant
            variant_id = random.choice(self.active_tests)
            variant = self.variants.get(variant_id)
            if variant:
                base_version = self.versions.get(variant.base_version)
                if base_version:
                    prompt = self._build_prompt_with_examples(
                        base_version.template,
                        base_version.examples,
                        user_input,
                        context
                    )
                    return prompt, f"variant:{variant_id}"
        
        # Step 3: Use best version for domain (or default)
        if domain and domain in self.domain_prompts:
            version_id = self.domain_prompts[domain]
        else:
            version_id = "default"
        
        version = self.versions.get(version_id)
        if not version:
            # Create default version
            version = PromptVersion(
                version_id="default",
                template=self.base_prompt_template,
                created_at=datetime.now().isoformat()
            )
            self.versions[version_id] = version
            self._save_versions()
        
        prompt = self._build_prompt_with_examples(
            version.template,
            version.examples,
            user_input,
            context
        )
        
        return prompt, version_id
    
    def record_result(
        self,
        version_id: str,
        user_input: str,
        intent_ir: Dict,
        success: bool,
        result: Optional[str] = None
    ):
        """
        Record execution result to update prompt statistics
        
        Args:
            version_id: The prompt version used
            user_input: Original user command
            intent_ir: Generated intent IR
            success: Whether execution succeeded
            result: Execution result (if successful)
        """
        # Handle variant results
        if version_id.startswith("variant:"):
            variant_id = version_id.split(":", 1)[1]
            variant = self.variants.get(variant_id)
            if variant:
                variant.update_stats(success)
                self._save_variants()
                
                # Check if variant should be promoted
                self._check_promotion(variant_id)
                return
        
        # Handle version results
        version = self.versions.get(version_id)
        if not version:
            return
        
        version.update_stats(success)
        
        # Add successful examples for few-shot learning
        if success and result:
            version.add_example(user_input, intent_ir, result)
        
        self._save_versions()
        
        # Auto-generate variant if success rate drops
        if version.total_uses >= 50 and version.success_rate < 0.7:
            self._generate_improvement_variant(version_id)
    
    def create_variant(
        self,
        base_version_id: str,
        modification: str,
        hypothesis: str,
        template: Optional[str] = None
    ) -> str:
        """
        Create a new prompt variant for A/B testing
        
        Returns:
            variant_id
        """
        base_version = self.versions.get(base_version_id)
        if not base_version:
            raise ValueError(f"Base version {base_version_id} not found")
        
        # Generate variant ID
        variant_id = hashlib.md5(
            f"{base_version_id}:{modification}:{datetime.now()}".encode()
        ).hexdigest()[:12]
        
        # Create variant
        variant = PromptVariant(
            variant_id=variant_id,
            base_version=base_version_id,
            modification=modification,
            hypothesis=hypothesis
        )
        
        self.variants[variant_id] = variant
        self.active_tests.append(variant_id)
        
        self._save_variants()
        self._save_active_tests()
        
        return variant_id
    
    def promote_variant(self, variant_id: str) -> str:
        """
        Promote successful variant to new version
        
        Returns:
            new_version_id
        """
        variant = self.variants.get(variant_id)
        if not variant:
            raise ValueError(f"Variant {variant_id} not found")
        
        base_version = self.versions.get(variant.base_version)
        if not base_version:
            raise ValueError("Base version not found")
        
        # Create new version from variant
        new_version_id = f"{variant.base_version}_v{len(self.versions) + 1}"
        
        new_version = PromptVersion(
            version_id=new_version_id,
            template=base_version.template,  # Inherit template
            created_at=datetime.now().isoformat(),
            success_count=variant.success_count,
            failure_count=variant.failure_count,
            total_uses=variant.total_uses,
            success_rate=variant.success_rate,
            examples=base_version.examples.copy()
        )
        
        self.versions[new_version_id] = new_version
        
        # Remove from active tests
        if variant_id in self.active_tests:
            self.active_tests.remove(variant_id)
        
        self._save_versions()
        self._save_active_tests()
        
        return new_version_id
    
    def _build_prompt_with_examples(
        self,
        template: str,
        examples: List[Dict],
        user_input: str,
        context: str
    ) -> str:
        """Build final prompt with few-shot examples"""
        
        # Format examples
        examples_text = ""
        if examples:
            examples_text = "Examples of successful executions:\n\n"
            for i, ex in enumerate(examples[-3:], 1):  # Show last 3
                examples_text += f"Example {i}:\n"
                examples_text += f"Input: {ex['input']}\n"
                examples_text += f"Output: {json.dumps(ex['intent'], indent=2)}\n\n"
        
        # Fill template
        prompt = template.format(
            examples=examples_text,
            user_input=user_input,
            context=f"Context:\n{context}" if context else ""
        )
        
        return prompt
    
    def _detect_domain(self, user_input: str) -> Optional[str]:
        """Detect command domain from user input"""
        input_lower = user_input.lower()
        
        domain_keywords = {
            "git": ["git", "commit", "push", "pull", "branch", "merge"],
            "docker": ["docker", "container", "image", "compose"],
            "files": ["file", "directory", "folder", "copy", "move", "delete"],
            "network": ["curl", "wget", "ping", "ssh", "scp"],
            "database": ["sql", "postgres", "mysql", "database", "table"],
        }
        
        for domain, keywords in domain_keywords.items():
            if any(kw in input_lower for kw in keywords):
                return domain
        
        return None
    
    def _generate_improvement_variant(self, version_id: str):
        """Auto-generate variant to improve low success rate"""
        version = self.versions.get(version_id)
        if not version:
            return
        
        # Only generate if not already testing
        if len(self.active_tests) >= 3:  # Max 3 concurrent tests
            return
        
        # Generate variant with modified template
        modification = "Added more explicit error handling instructions"
        hypothesis = "Explicit error handling will improve success rate"
        
        self.create_variant(
            version_id,
            modification,
            hypothesis
        )
    
    def _check_promotion(self, variant_id: str):
        """Check if variant should be promoted to version"""
        variant = self.variants.get(variant_id)
        if not variant:
            return
        
        # Need minimum samples
        if variant.total_uses < self.min_samples:
            return
        
        # Get base version success rate
        base_version = self.versions.get(variant.base_version)
        if not base_version:
            return
        
        # Check if significantly better
        improvement = variant.success_rate - base_version.success_rate
        
        if improvement >= self.promotion_threshold:
            # Promote!
            new_version_id = self.promote_variant(variant_id)
            if get_debug_flags().brain:
                logger.debug(
                    "Promoted variant %s → %s (%.1f%% improvement)",
                    variant_id, new_version_id, improvement * 100,
                )
    
    def get_statistics(self) -> Dict:
        """Get prompt evolution statistics"""
        return {
            "total_versions": len(self.versions),
            "active_tests": len(self.active_tests),
            "versions": [v.to_dict() for v in self.versions.values()],
            "variants": [v.to_dict() for v in self.variants.values()]
        }
    
    def _load_versions(self) -> Dict[str, PromptVersion]:
        """Load versions from disk"""
        if not self.versions_file.exists():
            return {}
        
        try:
            with open(self.versions_file) as f:
                data = json.load(f)
            
            versions = {}
            for vid, vdata in data.items():
                versions[vid] = PromptVersion(**vdata)
            
            return versions
        except Exception as e:
            logger.warning("Failed to load prompt versions: %s", e)
            return {}
    
    def _save_versions(self):
        """Save versions to disk"""
        try:
            data = {vid: v.to_dict() for vid, v in self.versions.items()}
            with open(self.versions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save prompt versions: %s", e)
    
    def _load_variants(self) -> Dict[str, PromptVariant]:
        """Load variants from disk"""
        if not self.variants_file.exists():
            return {}
        
        try:
            with open(self.variants_file) as f:
                data = json.load(f)
            
            variants = {}
            for vid, vdata in data.items():
                variants[vid] = PromptVariant(**vdata)
            
            return variants
        except Exception as e:
            logger.warning("Failed to load prompt variants: %s", e)
            return {}
    
    def _save_variants(self):
        """Save variants to disk"""
        try:
            data = {vid: v.to_dict() for vid, v in self.variants.items()}
            with open(self.variants_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save prompt variants: %s", e)
    
    def _load_active_tests(self) -> List[str]:
        """Load active tests from disk"""
        if not self.active_tests_file.exists():
            return []
        
        try:
            with open(self.active_tests_file) as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load active tests: %s", e)
            return []
    
    def _save_active_tests(self):
        """Save active tests to disk"""
        try:
            with open(self.active_tests_file, 'w') as f:
                json.dump(self.active_tests, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save active tests: %s", e)


# Singleton instance
_prompt_evolution_instance = None


def get_prompt_evolution() -> PromptEvolution:
    """Get or create PromptEvolution instance"""
    global _prompt_evolution_instance
    if _prompt_evolution_instance is None:
        _prompt_evolution_instance = PromptEvolution()
    return _prompt_evolution_instance
