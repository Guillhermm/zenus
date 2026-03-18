"""
Tests for ProviderOverride parser
"""

import pytest
from zenus_core.brain.provider_override import (
    parse_provider_override,
    describe_override,
    _infer_provider_from_model,
    PROVIDER_ALIASES,
)


# ---------------------------------------------------------------------------
# Tests: _infer_provider_from_model
# ---------------------------------------------------------------------------

class TestInferProviderFromModel:
    def test_claude_model_infers_anthropic(self):
        """Model names containing 'claude' map to anthropic."""
        assert _infer_provider_from_model("claude-opus-4") == "anthropic"

    def test_sonnet_model_infers_anthropic(self):
        """Model names containing 'sonnet' map to anthropic."""
        assert _infer_provider_from_model("claude-sonnet-4-6") == "anthropic"

    def test_haiku_model_infers_anthropic(self):
        """Model names containing 'haiku' map to anthropic."""
        assert _infer_provider_from_model("claude-haiku") == "anthropic"

    def test_opus_model_infers_anthropic(self):
        """Model names containing 'opus' map to anthropic."""
        assert _infer_provider_from_model("claude-opus") == "anthropic"

    def test_gpt_model_infers_openai(self):
        """Model names containing 'gpt' map to openai."""
        assert _infer_provider_from_model("gpt-4o") == "openai"

    def test_o1_model_infers_openai(self):
        """Model names starting with 'o1' map to openai."""
        assert _infer_provider_from_model("o1-mini") == "openai"

    def test_o3_model_infers_openai(self):
        """Model names starting with 'o3' map to openai."""
        assert _infer_provider_from_model("o3-turbo") == "openai"

    def test_o4_model_infers_openai(self):
        """Model names starting with 'o4' map to openai."""
        assert _infer_provider_from_model("o4-mini") == "openai"

    def test_deepseek_model_infers_deepseek(self):
        """Model names containing 'deepseek' map to deepseek."""
        assert _infer_provider_from_model("deepseek-coder") == "deepseek"

    def test_llama_model_infers_ollama(self):
        """Model names containing 'llama' map to ollama."""
        assert _infer_provider_from_model("llama3.1") == "ollama"

    def test_qwen_model_infers_ollama(self):
        """Model names containing 'qwen' map to ollama."""
        assert _infer_provider_from_model("qwen2.5") == "ollama"

    def test_mistral_model_infers_ollama(self):
        """Model names containing 'mistral' map to ollama."""
        assert _infer_provider_from_model("mistral-7b") == "ollama"

    def test_phi_model_infers_ollama(self):
        """Model names containing 'phi' map to ollama."""
        assert _infer_provider_from_model("phi-3") == "ollama"

    def test_gemma_model_infers_ollama(self):
        """Model names containing 'gemma' map to ollama."""
        assert _infer_provider_from_model("gemma-2b") == "ollama"

    def test_unknown_model_returns_none(self):
        """Completely unknown model identifiers return None."""
        assert _infer_provider_from_model("my-custom-llm") is None

    def test_inference_is_case_insensitive(self):
        """Model name matching ignores case."""
        assert _infer_provider_from_model("CLAUDE-3") == "anthropic"
        assert _infer_provider_from_model("GPT-4") == "openai"


# ---------------------------------------------------------------------------
# Tests: @provider: syntax
# ---------------------------------------------------------------------------

class TestAtProviderSyntax:
    def test_at_provider_with_colon_and_space(self):
        """@provider: text strips directive and returns canonical provider."""
        clean, provider, model = parse_provider_override("@deepseek: organize my downloads")
        assert clean == "organize my downloads"
        assert provider == "deepseek"
        assert model is None

    def test_at_claude_alias(self):
        """@claude maps to anthropic."""
        clean, provider, model = parse_provider_override("@claude: summarize this")
        assert provider == "anthropic"
        assert clean == "summarize this"

    def test_at_local_alias(self):
        """@local maps to ollama."""
        clean, provider, model = parse_provider_override("@local: do something")
        assert provider == "ollama"

    def test_at_gpt_alias(self):
        """@gpt maps to openai."""
        clean, provider, model = parse_provider_override("@gpt: write a poem")
        assert provider == "openai"

    def test_at_unknown_provider_no_match(self):
        """@unknown_provider does not set provider (not in PROVIDER_ALIASES)."""
        clean, provider, model = parse_provider_override("@unknownprovider: do stuff")
        assert provider is None

    def test_at_provider_case_insensitive(self):
        """@DEEPSEEK is treated the same as @deepseek."""
        clean, provider, model = parse_provider_override("@DEEPSEEK: sort my files")
        assert provider == "deepseek"


# ---------------------------------------------------------------------------
# Tests: use / using syntax
# ---------------------------------------------------------------------------

class TestUseSyntax:
    def test_use_provider_colon(self):
        """'use provider: text' strips directive and resolves provider."""
        clean, provider, model = parse_provider_override("use claude: organize my downloads")
        assert provider == "anthropic"
        assert clean == "organize my downloads"

    def test_using_provider_comma(self):
        """'using provider, text' strips directive and resolves provider."""
        clean, provider, model = parse_provider_override("using openai, organize my downloads")
        assert provider == "openai"
        assert clean == "organize my downloads"

    def test_using_ollama_alias(self):
        """'using local, ...' maps to ollama."""
        clean, provider, model = parse_provider_override("using local, run stuff")
        assert provider == "ollama"

    def test_use_case_insensitive(self):
        """'USE claude:' is handled the same as 'use claude:'."""
        clean, provider, model = parse_provider_override("USE claude: do something")
        assert provider == "anthropic"

    def test_using_unknown_provider_no_match(self):
        """'using unknown_xyz, ...' leaves provider as None."""
        clean, provider, model = parse_provider_override("using xyz_unknown, do stuff")
        assert provider is None

    def test_use_provider_space_separator(self):
        """'use provider text' (space after alias) resolves correctly."""
        clean, provider, model = parse_provider_override("use deepseek do something")
        assert provider == "deepseek"


# ---------------------------------------------------------------------------
# Tests: --provider flag syntax
# ---------------------------------------------------------------------------

class TestProviderFlagSyntax:
    def test_provider_flag_equals(self):
        """--provider=deepseek strips flag and sets provider."""
        clean, provider, model = parse_provider_override("--provider=deepseek organize my downloads")
        assert provider == "deepseek"
        assert clean == "organize my downloads"

    def test_provider_flag_space(self):
        """'--provider deepseek text' strips flag and sets provider."""
        clean, provider, model = parse_provider_override("--provider deepseek organize my downloads")
        assert provider == "deepseek"
        assert clean == "organize my downloads"

    def test_provider_flag_claude_alias(self):
        """--provider=claude resolves to anthropic."""
        clean, provider, model = parse_provider_override("--provider=claude do stuff")
        assert provider == "anthropic"

    def test_provider_flag_unknown_does_not_override(self):
        """--provider=unknown_xyz leaves provider unchanged from prior parse."""
        # No model flag set prior, so provider stays None
        clean, provider, model = parse_provider_override("--provider=unknown_xyz do stuff")
        assert provider is None

    def test_provider_flag_case_insensitive(self):
        """--PROVIDER=deepseek is handled correctly."""
        clean, provider, model = parse_provider_override("--PROVIDER=deepseek do stuff")
        assert provider == "deepseek"


# ---------------------------------------------------------------------------
# Tests: --model flag syntax
# ---------------------------------------------------------------------------

class TestModelFlagSyntax:
    def test_model_flag_equals(self):
        """--model=claude-opus-4 strips flag and infers provider."""
        clean, provider, model = parse_provider_override("--model=claude-opus-4 do X")
        assert model == "claude-opus-4"
        assert provider == "anthropic"
        assert clean == "do X"

    def test_model_flag_space(self):
        """'--model gpt-4o do X' strips flag and infers provider."""
        clean, provider, model = parse_provider_override("--model gpt-4o do X")
        assert model == "gpt-4o"
        assert provider == "openai"
        assert clean == "do X"

    def test_model_flag_deepseek(self):
        """--model deepseek-chat infers deepseek provider."""
        clean, provider, model = parse_provider_override("--model deepseek-chat do something")
        assert provider == "deepseek"
        assert model == "deepseek-chat"

    def test_model_flag_unknown_model_no_provider(self):
        """--model with an unknown identifier yields model but no provider."""
        clean, provider, model = parse_provider_override("--model my-private-model do something")
        assert model == "my-private-model"
        assert provider is None

    def test_model_flag_case_insensitive(self):
        """--MODEL=claude-haiku is handled correctly."""
        clean, provider, model = parse_provider_override("--MODEL=claude-haiku translate this")
        assert provider == "anthropic"

    def test_model_flag_provider_flag_together(self):
        """--model followed by --provider in the remainder resolves both."""
        # Pattern: --model X --provider Y text
        # First pass: model is extracted.  Remainder: "--provider Y text"
        # Second pass: provider is extracted from remainder.
        clean, provider, model = parse_provider_override("--model gpt-4o --provider openai translate this")
        assert model == "gpt-4o"
        assert provider == "openai"
        assert clean == "translate this"


# ---------------------------------------------------------------------------
# Tests: no directive / edge cases
# ---------------------------------------------------------------------------

class TestNoDirectiveAndEdgeCases:
    def test_plain_text_unchanged(self):
        """Input without any directive is returned as-is."""
        text = "just organize my downloads"
        clean, provider, model = parse_provider_override(text)
        assert clean == text
        assert provider is None
        assert model is None

    def test_empty_string_unchanged(self):
        """Empty string returns empty clean text with no overrides."""
        clean, provider, model = parse_provider_override("")
        assert provider is None
        assert model is None

    def test_only_directive_no_command_restores_original(self):
        """If stripping leaves an empty command the original is restored."""
        # e.g. user typed only "@deepseek:" with no trailing text
        # The regex requires trailing content (.+) so this won't match,
        # meaning clean stays as the original.
        clean, provider, model = parse_provider_override("@deepseek:")
        assert provider is None
        assert clean == "@deepseek:"

    def test_leading_whitespace_stripped(self):
        """Leading and trailing whitespace is stripped from the result."""
        clean, provider, model = parse_provider_override("  just do it  ")
        assert clean == "just do it"

    def test_multiline_command_preserved(self):
        """Multiline text after directive is preserved in clean."""
        clean, provider, model = parse_provider_override("@deepseek: line one\nline two")
        assert provider == "deepseek"
        assert "line one" in clean
        assert "line two" in clean


# ---------------------------------------------------------------------------
# Tests: describe_override
# ---------------------------------------------------------------------------

class TestDescribeOverride:
    def test_provider_and_model(self):
        """Both provider and model produces 'provider/model' string."""
        assert describe_override("anthropic", "claude-opus-4") == "anthropic/claude-opus-4"

    def test_model_only(self):
        """Only model returns the model string."""
        assert describe_override(None, "claude-opus-4") == "claude-opus-4"

    def test_provider_only(self):
        """Only provider returns the provider string."""
        assert describe_override("deepseek", None) == "deepseek"

    def test_neither_returns_empty_string(self):
        """No override returns an empty string."""
        assert describe_override(None, None) == ""


# ---------------------------------------------------------------------------
# Tests: PROVIDER_ALIASES completeness
# ---------------------------------------------------------------------------

class TestProviderAliasesMap:
    def test_all_canonical_names_are_self_mapped(self):
        """Each canonical provider name maps to itself."""
        for canonical in ("anthropic", "openai", "deepseek", "ollama"):
            assert PROVIDER_ALIASES.get(canonical) == canonical

    def test_claude_maps_to_anthropic(self):
        """'claude' alias resolves to anthropic."""
        assert PROVIDER_ALIASES["claude"] == "anthropic"

    def test_llama_maps_to_ollama(self):
        """'llama' alias resolves to ollama."""
        assert PROVIDER_ALIASES["llama"] == "ollama"

    def test_chatgpt_maps_to_openai(self):
        """'chatgpt' alias resolves to openai."""
        assert PROVIDER_ALIASES["chatgpt"] == "openai"
