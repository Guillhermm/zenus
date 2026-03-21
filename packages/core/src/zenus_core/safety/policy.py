"""
Safety Policy

Defines rules for what operations are allowed and enforces them.
"""

from zenus_core.brain.llm.schemas import IntentIR, Step


class SafetyError(Exception):
    """Raised when a step violates safety policy"""
    pass


def check_step(step: Step) -> bool:
    """
    Verify that a step is safe to execute.

    Args:
        step: The step to validate

    Returns:
        True if safe

    Raises:
        SafetyError: If step violates policy
    """
    if step.risk >= 3:
        raise SafetyError(
            f"High risk operation blocked: {step.tool}.{step.action} (risk={step.risk}). "
            "Delete operations require explicit user confirmation."
        )

    return True


def enforce_confirmation_policy(intent: IntentIR) -> IntentIR:
    """Ensure that any intent containing risk>=2 steps has requires_confirmation=True.

    This is a defence-in-depth measure: even if the LLM returns
    ``requires_confirmation: false`` for a destructive or modifying plan, we
    override it here so the orchestrator always prompts the user.

    Returns the (potentially updated) intent.
    """
    if not intent.requires_confirmation and any(step.risk >= 2 for step in intent.steps):
        return intent.model_copy(update={"requires_confirmation": True})
    return intent
