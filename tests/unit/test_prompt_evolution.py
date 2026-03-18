"""
Tests for PromptEvolution - versioning, A/B testing, promotion, and rollback
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from zenus_core.brain.prompt_evolution import (
    PromptEvolution,
    PromptVersion,
    PromptVariant,
    get_prompt_evolution,
)


def make_evolution(tmp_path: Path) -> PromptEvolution:
    """Build a PromptEvolution instance backed by a temp directory."""
    return PromptEvolution(storage_dir=tmp_path / "prompts")


def make_version(
    version_id="v1",
    template="Hello {examples} {user_input} {context}",
    success_count=0,
    failure_count=0,
    total_uses=0,
    success_rate=0.0,
    examples=None,
    domain=None,
) -> PromptVersion:
    """Build a PromptVersion for testing."""
    return PromptVersion(
        version_id=version_id,
        template=template,
        created_at=datetime.now().isoformat(),
        success_count=success_count,
        failure_count=failure_count,
        total_uses=total_uses,
        success_rate=success_rate,
        examples=examples or [],
        domain=domain,
    )


class TestPromptVersionStats:
    """Test PromptVersion.update_stats and add_example"""

    def test_update_stats_success_increments_counters(self):
        """Success increments success_count and total_uses"""
        v = make_version()
        v.update_stats(success=True)
        assert v.success_count == 1
        assert v.total_uses == 1
        assert v.failure_count == 0

    def test_update_stats_failure_increments_failure_count(self):
        """Failure increments failure_count and total_uses"""
        v = make_version()
        v.update_stats(success=False)
        assert v.failure_count == 1
        assert v.total_uses == 1
        assert v.success_count == 0

    def test_success_rate_calculated_correctly(self):
        """success_rate = success_count / total_uses"""
        v = make_version()
        v.update_stats(True)
        v.update_stats(True)
        v.update_stats(False)
        assert v.success_rate == pytest.approx(2 / 3)

    def test_success_rate_zero_when_no_uses(self):
        """success_rate stays 0.0 with no uses"""
        v = make_version()
        assert v.success_rate == 0.0

    def test_add_example_appends(self):
        """add_example adds entry to examples list"""
        v = make_version()
        v.add_example("do X", {"goal": "X"}, "success")
        assert len(v.examples) == 1
        assert v.examples[0]["input"] == "do X"

    def test_add_example_keeps_at_most_10(self):
        """examples list is capped at 10 entries"""
        v = make_version()
        for i in range(15):
            v.add_example(f"cmd {i}", {}, "ok")
        assert len(v.examples) == 10

    def test_add_example_keeps_most_recent(self):
        """When capped, most recent 10 examples are retained"""
        v = make_version()
        for i in range(12):
            v.add_example(f"cmd {i}", {}, "ok")
        assert v.examples[-1]["input"] == "cmd 11"
        assert v.examples[0]["input"] == "cmd 2"

    def test_to_dict_returns_dict(self):
        """PromptVersion.to_dict returns a dictionary"""
        v = make_version()
        d = v.to_dict()
        assert isinstance(d, dict)
        assert d["version_id"] == "v1"


class TestPromptVariantStats:
    """Test PromptVariant.update_stats"""

    def test_update_stats_success(self):
        """Success increments success_count and total_uses"""
        pv = PromptVariant(
            variant_id="var1",
            base_version="v1",
            modification="added context",
            hypothesis="better",
        )
        pv.update_stats(success=True)
        assert pv.success_count == 1
        assert pv.total_uses == 1

    def test_update_stats_success_rate(self):
        """success_rate is computed correctly"""
        pv = PromptVariant(
            variant_id="var1",
            base_version="v1",
            modification="mod",
            hypothesis="hyp",
        )
        pv.update_stats(True)
        pv.update_stats(False)
        assert pv.success_rate == pytest.approx(0.5)

    def test_to_dict(self):
        """PromptVariant.to_dict returns a dict"""
        pv = PromptVariant(
            variant_id="var1",
            base_version="v1",
            modification="mod",
            hypothesis="hyp",
        )
        d = pv.to_dict()
        assert d["variant_id"] == "var1"


class TestPromptEvolutionInit:
    """Test PromptEvolution initialization with temp storage"""

    def test_storage_dir_created(self, tmp_path):
        """Storage directory is created on init"""
        pe = make_evolution(tmp_path)
        assert pe.storage_dir.exists()

    def test_versions_empty_initially(self, tmp_path):
        """No versions loaded when storage is fresh"""
        pe = make_evolution(tmp_path)
        assert pe.versions == {}

    def test_variants_empty_initially(self, tmp_path):
        """No variants loaded when storage is fresh"""
        pe = make_evolution(tmp_path)
        assert pe.variants == {}

    def test_active_tests_empty_initially(self, tmp_path):
        """No active tests when storage is fresh"""
        pe = make_evolution(tmp_path)
        assert pe.active_tests == []


class TestGetPrompt:
    """Test get_prompt returns the best prompt and version_id"""

    def test_returns_tuple_of_prompt_and_version(self, tmp_path):
        """get_prompt returns (str, str)"""
        pe = make_evolution(tmp_path)
        prompt, version_id = pe.get_prompt("list files", context="")
        assert isinstance(prompt, str)
        assert isinstance(version_id, str)

    def test_creates_default_version_if_absent(self, tmp_path):
        """get_prompt creates 'default' version if not yet persisted"""
        pe = make_evolution(tmp_path)
        _, version_id = pe.get_prompt("list files")
        assert version_id == "default"
        assert "default" in pe.versions

    def test_prompt_contains_user_input(self, tmp_path):
        """Returned prompt contains the user input"""
        pe = make_evolution(tmp_path)
        prompt, _ = pe.get_prompt("show me the files")
        assert "show me the files" in prompt

    def test_prompt_contains_context_when_provided(self, tmp_path):
        """Returned prompt includes context string"""
        pe = make_evolution(tmp_path)
        prompt, _ = pe.get_prompt("list files", context="production server")
        assert "production server" in prompt

    def test_domain_specific_version_used(self, tmp_path):
        """Domain prompt version is selected when available"""
        pe = make_evolution(tmp_path)
        # Register a git-specific version
        v = make_version(version_id="git_v1", template="git prompt {examples} {user_input} {context}")
        pe.versions["git_v1"] = v
        pe.domain_prompts["git"] = "git_v1"
        _, version_id = pe.get_prompt("git commit changes", domain="git")
        assert version_id == "git_v1"

    def test_few_shot_examples_included_in_prompt(self, tmp_path):
        """Stored examples appear in the prompt"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")  # Ensure default version is created
        pe.versions["default"].add_example("previous cmd", {"goal": "x"}, "ok")
        prompt, _ = pe.get_prompt("new cmd")
        assert "previous cmd" in prompt

    def test_variant_used_when_active_test_exists(self, tmp_path):
        """A/B variant is returned for some traffic"""
        pe = make_evolution(tmp_path)
        # Pre-create default version and a variant
        pe.get_prompt("cmd")  # Creates default
        variant_id = pe.create_variant("default", "more examples", "better")
        # Force variant selection by patching random at module level
        with patch("random.random", return_value=0.0):
            with patch("random.choice", return_value=variant_id):
                _, version_id = pe.get_prompt("cmd")
        assert version_id == f"variant:{variant_id}"


class TestDomainDetection:
    """Test _detect_domain keyword matching"""

    def setup_method(self, tmp_path=None):
        """Build PromptEvolution for testing."""
        # Use a real tmp path via pytest fixture instead
        pass

    def test_detects_git_domain(self, tmp_path):
        """git keyword maps to 'git' domain"""
        pe = make_evolution(tmp_path)
        assert pe._detect_domain("git push origin main") == "git"

    def test_detects_docker_domain(self, tmp_path):
        """docker keyword maps to 'docker' domain"""
        pe = make_evolution(tmp_path)
        assert pe._detect_domain("docker build the image") == "docker"

    def test_detects_files_domain(self, tmp_path):
        """file keyword maps to 'files' domain"""
        pe = make_evolution(tmp_path)
        assert pe._detect_domain("copy the file to the folder") == "files"

    def test_detects_network_domain(self, tmp_path):
        """curl keyword maps to 'network' domain"""
        pe = make_evolution(tmp_path)
        assert pe._detect_domain("curl the API endpoint") == "network"

    def test_detects_database_domain(self, tmp_path):
        """postgres keyword maps to 'database' domain"""
        pe = make_evolution(tmp_path)
        assert pe._detect_domain("connect to the postgres database") == "database"

    def test_returns_none_for_unknown_domain(self, tmp_path):
        """Unknown input returns None"""
        pe = make_evolution(tmp_path)
        assert pe._detect_domain("say hello world") is None


class TestRecordResult:
    """Test record_result updates stats for versions and variants"""

    def test_records_success_for_version(self, tmp_path):
        """Successful execution increments version success_count"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")  # Creates default
        pe.record_result("default", "cmd", {}, success=True, result="ok")
        assert pe.versions["default"].success_count == 1

    def test_records_failure_for_version(self, tmp_path):
        """Failed execution increments version failure_count"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        pe.record_result("default", "cmd", {}, success=False)
        assert pe.versions["default"].failure_count == 1

    def test_adds_example_on_success_with_result(self, tmp_path):
        """Successful result with non-None result adds a few-shot example"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        pe.record_result("default", "list files", {"goal": "x"}, success=True, result="done")
        assert len(pe.versions["default"].examples) == 1

    def test_no_example_added_on_failure(self, tmp_path):
        """Failed result does not add a few-shot example"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        pe.record_result("default", "cmd", {}, success=False)
        assert len(pe.versions["default"].examples) == 0

    def test_records_result_for_variant(self, tmp_path):
        """Variant stats updated when version_id starts with 'variant:'"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        pe.record_result(f"variant:{variant_id}", "cmd", {}, success=True)
        assert pe.variants[variant_id].success_count == 1

    def test_ignores_unknown_version_id(self, tmp_path):
        """record_result silently ignores unknown version IDs"""
        pe = make_evolution(tmp_path)
        pe.record_result("nonexistent_version", "cmd", {}, success=True)  # Should not raise

    def test_saves_versions_to_disk_after_record(self, tmp_path):
        """record_result persists updated stats to disk"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        pe.record_result("default", "cmd", {}, success=True, result="ok")
        # Reload from disk
        pe2 = PromptEvolution(storage_dir=pe.storage_dir)
        assert pe2.versions["default"].success_count == 1


class TestCreateVariant:
    """Test create_variant A/B test creation"""

    def test_returns_variant_id_string(self, tmp_path):
        """create_variant returns a non-empty string variant ID"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "added examples", "will improve")
        assert isinstance(variant_id, str)
        assert len(variant_id) > 0

    def test_variant_added_to_variants_dict(self, tmp_path):
        """New variant is stored in pe.variants"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        assert variant_id in pe.variants

    def test_variant_added_to_active_tests(self, tmp_path):
        """New variant is included in active_tests"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        assert variant_id in pe.active_tests

    def test_variant_stores_base_version(self, tmp_path):
        """Variant records which base version it was derived from"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        assert pe.variants[variant_id].base_version == "default"

    def test_variant_stores_modification(self, tmp_path):
        """Variant records the modification description"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "my modification", "hyp")
        assert pe.variants[variant_id].modification == "my modification"

    def test_raises_on_unknown_base_version(self, tmp_path):
        """create_variant raises ValueError for unknown base version"""
        pe = make_evolution(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            pe.create_variant("nonexistent", "mod", "hyp")

    def test_persists_variant_to_disk(self, tmp_path):
        """create_variant saves variant file to disk"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        pe2 = PromptEvolution(storage_dir=pe.storage_dir)
        assert variant_id in pe2.variants


class TestPromoteVariant:
    """Test promote_variant creates new version from variant"""

    def test_returns_new_version_id(self, tmp_path):
        """promote_variant returns a new version ID string"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        new_id = pe.promote_variant(variant_id)
        assert isinstance(new_id, str)
        assert new_id != "default"

    def test_new_version_added_to_versions(self, tmp_path):
        """Promoted version appears in pe.versions"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        new_id = pe.promote_variant(variant_id)
        assert new_id in pe.versions

    def test_variant_removed_from_active_tests(self, tmp_path):
        """Promoted variant is removed from active_tests"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        pe.promote_variant(variant_id)
        assert variant_id not in pe.active_tests

    def test_new_version_inherits_stats(self, tmp_path):
        """Promoted version inherits success/failure stats from variant"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        pe.variants[variant_id].update_stats(True)
        pe.variants[variant_id].update_stats(True)
        new_id = pe.promote_variant(variant_id)
        assert pe.versions[new_id].success_count == 2

    def test_new_version_inherits_examples_from_base(self, tmp_path):
        """Promoted version gets a copy of the base version's examples"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        pe.versions["default"].add_example("example cmd", {"goal": "x"}, "ok")
        variant_id = pe.create_variant("default", "mod", "hyp")
        new_id = pe.promote_variant(variant_id)
        assert len(pe.versions[new_id].examples) == 1

    def test_raises_on_unknown_variant(self, tmp_path):
        """promote_variant raises ValueError for unknown variant ID"""
        pe = make_evolution(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            pe.promote_variant("nonexistent_variant")


class TestAutoPromotionOnSufficientSamples:
    """Test _check_promotion auto-promotes when criteria met"""

    def test_no_promotion_below_min_samples(self, tmp_path):
        """Variant is not promoted when total_uses < min_samples"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        variant_id = pe.create_variant("default", "mod", "hyp")
        # Add fewer uses than min_samples (20)
        for _ in range(5):
            pe.variants[variant_id].update_stats(True)
        initial_version_count = len(pe.versions)
        pe._check_promotion(variant_id)
        assert len(pe.versions) == initial_version_count

    def test_no_promotion_when_not_significantly_better(self, tmp_path):
        """Variant is not promoted when improvement < promotion_threshold"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        # Set base version success rate to 0.8
        pe.versions["default"].success_count = 80
        pe.versions["default"].failure_count = 20
        pe.versions["default"].total_uses = 100
        pe.versions["default"].success_rate = 0.8

        variant_id = pe.create_variant("default", "mod", "hyp")
        v = pe.variants[variant_id]
        # Variant at 0.85 — only 5% better, below 15% threshold
        for _ in range(17):
            v.update_stats(True)
        for _ in range(3):
            v.update_stats(False)
        initial_count = len(pe.versions)
        pe._check_promotion(variant_id)
        assert len(pe.versions) == initial_count

    def test_auto_promotes_when_significantly_better(self, tmp_path):
        """Variant is auto-promoted when it exceeds promotion_threshold"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        # Base version at 0.5 success rate
        pe.versions["default"].success_count = 10
        pe.versions["default"].failure_count = 10
        pe.versions["default"].total_uses = 20
        pe.versions["default"].success_rate = 0.5

        variant_id = pe.create_variant("default", "mod", "hyp")
        v = pe.variants[variant_id]
        # Variant at 0.9 — 40% improvement, above threshold
        for _ in range(18):
            v.update_stats(True)
        for _ in range(2):
            v.update_stats(False)
        initial_count = len(pe.versions)
        pe._check_promotion(variant_id)
        assert len(pe.versions) == initial_count + 1


class TestAutoImprovementVariantGeneration:
    """Test _generate_improvement_variant triggers on low success rate"""

    def test_generates_variant_when_success_rate_low(self, tmp_path):
        """_generate_improvement_variant creates a variant when success rate is low"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        v = pe.versions["default"]
        v.total_uses = 60
        v.success_count = 30
        v.failure_count = 30
        v.success_rate = 0.5  # Below 0.7 threshold
        pe._generate_improvement_variant("default")
        assert len(pe.variants) == 1

    def test_does_not_generate_when_max_tests_reached(self, tmp_path):
        """_generate_improvement_variant skips when 3 tests already active"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        # Manually add 3 active tests
        pe.active_tests = ["t1", "t2", "t3"]
        pe._generate_improvement_variant("default")
        assert len(pe.variants) == 0


class TestGetStatistics:
    """Test get_statistics summary output"""

    def test_returns_statistics_dict(self, tmp_path):
        """get_statistics returns a dictionary"""
        pe = make_evolution(tmp_path)
        stats = pe.get_statistics()
        assert isinstance(stats, dict)

    def test_statistics_includes_version_count(self, tmp_path):
        """Statistics includes total_versions key"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        stats = pe.get_statistics()
        assert stats["total_versions"] == 1

    def test_statistics_includes_active_tests(self, tmp_path):
        """Statistics includes active_tests count"""
        pe = make_evolution(tmp_path)
        stats = pe.get_statistics()
        assert "active_tests" in stats

    def test_statistics_versions_list(self, tmp_path):
        """Statistics versions list is serializable"""
        pe = make_evolution(tmp_path)
        pe.get_prompt("cmd")
        stats = pe.get_statistics()
        assert isinstance(stats["versions"], list)


class TestPersistence:
    """Test load/save round-trips for versions, variants, and active tests"""

    def test_versions_persist_across_instances(self, tmp_path):
        """Versions saved by one instance are loaded by a new instance"""
        pe1 = make_evolution(tmp_path)
        pe1.get_prompt("cmd")
        pe1._save_versions()

        pe2 = PromptEvolution(storage_dir=pe1.storage_dir)
        assert "default" in pe2.versions

    def test_variants_persist_across_instances(self, tmp_path):
        """Variants saved by one instance are loaded by a new instance"""
        pe1 = make_evolution(tmp_path)
        pe1.get_prompt("cmd")
        vid = pe1.create_variant("default", "mod", "hyp")

        pe2 = PromptEvolution(storage_dir=pe1.storage_dir)
        assert vid in pe2.variants

    def test_active_tests_persist_across_instances(self, tmp_path):
        """Active tests saved by one instance are loaded by a new instance"""
        pe1 = make_evolution(tmp_path)
        pe1.get_prompt("cmd")
        vid = pe1.create_variant("default", "mod", "hyp")

        pe2 = PromptEvolution(storage_dir=pe1.storage_dir)
        assert vid in pe2.active_tests

    def test_load_versions_returns_empty_on_missing_file(self, tmp_path):
        """_load_versions returns {} when file does not exist"""
        pe = PromptEvolution(storage_dir=tmp_path / "fresh")
        assert pe.versions == {}

    def test_load_versions_handles_corrupt_file(self, tmp_path):
        """_load_versions returns {} on corrupt JSON without raising"""
        storage = tmp_path / "prompts"
        storage.mkdir()
        (storage / "versions.json").write_text("not valid json")
        pe = PromptEvolution(storage_dir=storage)
        assert pe.versions == {}

    def test_load_variants_handles_corrupt_file(self, tmp_path):
        """_load_variants returns {} on corrupt JSON without raising"""
        storage = tmp_path / "prompts"
        storage.mkdir()
        (storage / "variants.json").write_text("{bad json")
        pe = PromptEvolution(storage_dir=storage)
        assert pe.variants == {}

    def test_load_active_tests_handles_corrupt_file(self, tmp_path):
        """_load_active_tests returns [] on corrupt JSON without raising"""
        storage = tmp_path / "prompts"
        storage.mkdir()
        (storage / "active_tests.json").write_text("not json")
        pe = PromptEvolution(storage_dir=storage)
        assert pe.active_tests == []


class TestGetPromptEvolution:
    """Test singleton factory"""

    def test_returns_instance(self):
        """get_prompt_evolution returns a PromptEvolution"""
        import zenus_core.brain.prompt_evolution as module
        original = module._prompt_evolution_instance
        module._prompt_evolution_instance = None
        try:
            instance = get_prompt_evolution()
            assert isinstance(instance, PromptEvolution)
        finally:
            module._prompt_evolution_instance = original

    def test_returns_same_singleton(self):
        """get_prompt_evolution returns same instance on repeat calls"""
        import zenus_core.brain.prompt_evolution as module
        original = module._prompt_evolution_instance
        module._prompt_evolution_instance = None
        try:
            a = get_prompt_evolution()
            b = get_prompt_evolution()
            assert a is b
        finally:
            module._prompt_evolution_instance = original
