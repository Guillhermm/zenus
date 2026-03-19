# This should never change lightly.
# This is the OS contract.
#
# Rules for modifications:
# - All new fields MUST have a default value (backward-compatible)
# - Never rename or remove existing fields without a migration path
# - After any change, run: pytest tests/unit/test_schemas.py
# - Update system_prompt.py in lock-step with any schema change

from pydantic import BaseModel, Field # type: ignore
from typing import List, Dict, Any, Optional


class Step(BaseModel):
    tool: str = Field(..., description="Tool name, e.g. FileOps")
    action: str = Field(..., description="Action name")
    args: Dict[str, Any] = Field(default_factory=dict)
    risk: int = Field(..., ge=0, le=3)


class IntentIR(BaseModel):
    goal: str
    requires_confirmation: bool
    steps: List[Step]
    # When True: no steps are executed; orchestrator answers directly via LLM.
    # Default False so all existing cached intents remain valid.
    is_question: bool = Field(default=False)
    # Optional short description used to build the execution summary.
    # Populated by the LLM for action intents; ignored for questions.
    action_summary: Optional[str] = Field(default=None)
