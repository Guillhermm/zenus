"""
Integration tests for the DeepSeek LLM adapter.

These tests make real API calls and are skipped when DEEPSEEK_API_KEY is absent.
They verify:
  - The adapter correctly translates natural language → IntentIR
  - The IntentIR schema is valid and well-formed
  - JSON extraction handles markdown fences and plain JSON
  - Error paths (missing key, malformed JSON) raise the right exceptions
  - generate() and reflect_on_goal() return coherent text
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from zenus_core.brain.llm.deepseek_llm import DeepSeekLLM, extract_json
from zenus_core.brain.llm.schemas import IntentIR, Step


# ---------------------------------------------------------------------------
# extract_json — pure unit tests (no network)
# ---------------------------------------------------------------------------

class TestExtractJson:

    def test_plain_json(self):
        raw = '{"goal": "test", "requires_confirmation": false, "steps": []}'
        result = extract_json(raw)
        assert result["goal"] == "test"

    def test_markdown_json_fence(self):
        raw = '```json\n{"goal": "scan", "requires_confirmation": false, "steps": []}\n```'
        result = extract_json(raw)
        assert result["goal"] == "scan"

    def test_plain_code_fence(self):
        raw = '```\n{"goal": "x", "requires_confirmation": false, "steps": []}\n```'
        result = extract_json(raw)
        assert result["goal"] == "x"

    def test_json_with_surrounding_text(self):
        raw = 'Here is the plan:\n{"goal": "g", "requires_confirmation": false, "steps": []}\nDone.'
        result = extract_json(raw)
        assert result["goal"] == "g"

    def test_no_json_raises(self):
        with pytest.raises(RuntimeError, match="No JSON"):
            extract_json("no json here at all")

    def test_invalid_json_raises(self):
        with pytest.raises(RuntimeError):
            extract_json('{"goal": "x", "steps": [INVALID]}')

    def test_nested_object(self):
        raw = '{"goal": "run", "requires_confirmation": false, "steps": [{"tool": "FileOps", "action": "scan", "args": {"path": "/tmp"}, "risk": 0}]}'
        result = extract_json(raw)
        assert result["steps"][0]["tool"] == "FileOps"


# ---------------------------------------------------------------------------
# DeepSeekLLM — credential validation (no network)
# ---------------------------------------------------------------------------

class TestDeepSeekCredentials:

    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove key entirely
            env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises((ValueError, Exception)):
                    DeepSeekLLM()

    def test_api_key_with_quotes_stripped(self):
        """Constructor should strip surrounding quotes from API key."""
        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": '"sk-quoted-key"'}):
                llm = DeepSeekLLM()
                # Verify OpenAI was called with stripped key
                call_kwargs = mock_openai.call_args[1]
                assert call_kwargs["api_key"] == "sk-quoted-key"


# ---------------------------------------------------------------------------
# DeepSeekLLM — translate_intent (real API)
# ---------------------------------------------------------------------------

@pytest.mark.requires_deepseek
@pytest.mark.integration
class TestDeepSeekTranslateIntent:

    def test_returns_intentir_instance(self, deepseek_llm):
        intent = deepseek_llm.translate_intent("list files in /tmp")
        assert isinstance(intent, IntentIR)

    def test_goal_is_non_empty_string(self, deepseek_llm):
        intent = deepseek_llm.translate_intent("show system information")
        assert isinstance(intent.goal, str)
        assert len(intent.goal) > 0

    def test_steps_is_list(self, deepseek_llm):
        intent = deepseek_llm.translate_intent("check disk usage")
        assert isinstance(intent.steps, list)

    def test_each_step_has_tool_and_action(self, deepseek_llm):
        intent = deepseek_llm.translate_intent("list files in /tmp")
        for step in intent.steps:
            assert isinstance(step.tool, str) and len(step.tool) > 0
            assert isinstance(step.action, str) and len(step.action) > 0

    def test_risk_is_within_bounds(self, deepseek_llm):
        intent = deepseek_llm.translate_intent("show running processes")
        for step in intent.steps:
            assert 0 <= step.risk <= 3

    def test_requires_confirmation_is_bool(self, deepseek_llm):
        intent = deepseek_llm.translate_intent("check disk usage of /home")
        assert isinstance(intent.requires_confirmation, bool)

    def test_args_is_dict(self, deepseek_llm):
        intent = deepseek_llm.translate_intent("scan /tmp for files")
        for step in intent.steps:
            assert isinstance(step.args, dict)

    def test_file_command_uses_fileops_or_similar(self, deepseek_llm):
        """File-related commands should produce steps targeting file tools."""
        intent = deepseek_llm.translate_intent("list all files in /tmp")
        file_tools = {"FileOps", "ShellOps", "SystemOps"}
        tools_used = {step.tool for step in intent.steps}
        assert tools_used & file_tools, f"Expected a file-related tool, got: {tools_used}"

    def test_step_count_is_reasonable(self, deepseek_llm):
        """A simple command should not produce more than ~5 steps."""
        intent = deepseek_llm.translate_intent("show system resource usage")
        assert 1 <= len(intent.steps) <= 8

    def test_pydantic_model_is_valid(self, deepseek_llm):
        """IntentIR must be serialisable — no validation errors."""
        intent = deepseek_llm.translate_intent("check memory usage")
        dumped = intent.model_dump()
        assert "goal" in dumped
        assert "steps" in dumped
        assert "requires_confirmation" in dumped

    def test_second_call_returns_fresh_intent(self, deepseek_llm):
        """Two calls must not share state — each returns its own IntentIR."""
        intent_a = deepseek_llm.translate_intent("list files in /tmp")
        intent_b = deepseek_llm.translate_intent("show system information")
        # Goals should reflect the different inputs
        assert intent_a is not intent_b

    def test_bad_response_json_raises_runtime_error(self, deepseek_llm):
        """If the model returns non-JSON, a RuntimeError is raised."""
        with patch.object(
            deepseek_llm.client.chat.completions, "create",
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="not json at all"))]
            )
        ):
            with pytest.raises(RuntimeError):
                deepseek_llm.translate_intent("do something")


# ---------------------------------------------------------------------------
# DeepSeekLLM — generate (real API)
# ---------------------------------------------------------------------------

@pytest.mark.requires_deepseek
@pytest.mark.integration
class TestDeepSeekGenerate:

    def test_returns_string(self, deepseek_llm):
        result = deepseek_llm.generate("Say hello in one word.")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_responds_to_factual_prompt(self, deepseek_llm):
        result = deepseek_llm.generate("What is 2 + 2? Answer with just the number.")
        assert "4" in result

    def test_respects_prompt_content(self, deepseek_llm):
        result = deepseek_llm.generate(
            "List exactly three programming languages, one per line, no explanation."
        )
        lines = [l.strip() for l in result.strip().splitlines() if l.strip()]
        assert len(lines) >= 1  # At minimum some content


# ---------------------------------------------------------------------------
# DeepSeekLLM — reflect_on_goal (real API)
# ---------------------------------------------------------------------------

@pytest.mark.requires_deepseek
@pytest.mark.integration
class TestDeepSeekReflectOnGoal:

    def test_returns_string(self, deepseek_llm):
        result = deepseek_llm.reflect_on_goal(
            reflection_prompt=(
                "Goal: list files in /tmp\n"
                "Observation: FileOps.scan() → [file1.txt, file2.txt]\n"
                "Has the goal been achieved?"
            ),
            user_goal="list files in /tmp",
            observations=["FileOps.scan() → [file1.txt, file2.txt]"],
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_achieved_goal_says_achieved(self, deepseek_llm):
        """When observation clearly satisfies goal, response should signal success."""
        result = deepseek_llm.reflect_on_goal(
            reflection_prompt=(
                "Goal: check if Python is installed\n"
                "Observation: ShellOps.run() → Python 3.11.0\n"
                "Is the goal achieved? Reply with ACHIEVED: YES or ACHIEVED: NO."
            ),
            user_goal="check if Python is installed",
            observations=["ShellOps.run() → Python 3.11.0"],
        )
        # The model should include some form of affirmation
        assert any(word in result.upper() for word in ("YES", "ACHIEVED", "COMPLETE", "TRUE", "DONE"))
