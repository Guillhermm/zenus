import asyncio
from abc import ABC, abstractmethod
from typing import List
from zenus_core.brain.llm.schemas import IntentIR


class LLM(ABC):
    @abstractmethod
    def translate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        """
        Translate user input to Intent IR

        Args:
            user_input: Natural language command
            stream: Enable streaming output (if supported)

        Returns:
            IntentIR object
        """
        pass

    @abstractmethod
    def reflect_on_goal(
        self,
        reflection_prompt: str,
        user_goal: str,
        observations: List[str],
    ) -> str:
        """
        Reflect on whether a goal has been achieved

        Args:
            reflection_prompt: Full prompt for reflection
            user_goal: Original user goal
            observations: List of observations from execution

        Returns:
            Structured reflection text with ACHIEVED, CONFIDENCE, REASONING, NEXT_STEPS
        """
        pass

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a free-form text response for a given prompt.
        Used by internal systems (e.g. self-reflection) that need a general LLM call.

        Args:
            prompt: Full prompt string

        Returns:
            Model response as plain text
        """
        pass

    # ------------------------------------------------------------------
    # Async API — default implementations delegate to sync via thread pool.
    # Subclasses may override with native async implementations.
    # ------------------------------------------------------------------

    async def atranslate_intent(self, user_input: str, stream: bool = False) -> IntentIR:
        """Async version of translate_intent."""
        return await asyncio.to_thread(self.translate_intent, user_input, stream)

    async def areflect_on_goal(
        self,
        reflection_prompt: str,
        user_goal: str,
        observations: List[str],
    ) -> str:
        """Async version of reflect_on_goal."""
        return await asyncio.to_thread(
            self.reflect_on_goal, reflection_prompt, user_goal, observations
        )

    async def agenerate(self, prompt: str) -> str:
        """Async version of generate."""
        return await asyncio.to_thread(self.generate, prompt)
