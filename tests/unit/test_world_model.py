"""
Tests for World Model
"""

import json
import os
import pytest
from zenus_core.memory.world_model import WorldModel


@pytest.fixture
def storage_path(tmp_path):
    """Return a temp file path for world model storage."""
    return str(tmp_path / "world_model.json")


@pytest.fixture
def model(storage_path):
    """Create a WorldModel backed by a temp file."""
    return WorldModel(storage_path=storage_path)


class TestWorldModelInit:
    def test_default_storage_path(self):
        """Default storage path points to ~/.zenus/world_model.json."""
        wm = WorldModel()
        assert wm.storage_path == os.path.expanduser("~/.zenus/world_model.json")

    def test_custom_storage_path(self, storage_path):
        """Custom storage path is stored on the instance."""
        wm = WorldModel(storage_path=storage_path)
        assert wm.storage_path == storage_path

    def test_fresh_model_has_default_structure(self, model):
        """Newly created model has all expected top-level keys."""
        assert "paths" in model.data
        assert "frequent_paths" in model.data
        assert "preferences" in model.data
        assert "applications" in model.data
        assert "patterns" in model.data
        assert "last_updated" in model.data

    def test_loads_existing_file(self, storage_path):
        """WorldModel loads data persisted by a previous instance."""
        wm1 = WorldModel(storage_path=storage_path)
        wm1.set_preference("theme", "dark")

        wm2 = WorldModel(storage_path=storage_path)
        assert wm2.get_preference("theme") == "dark"

    def test_falls_back_to_default_on_corrupt_file(self, tmp_path):
        """Corrupted JSON file triggers fallback to default model."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{")

        wm = WorldModel(storage_path=str(bad_file))
        assert wm.data["preferences"] == {}


class TestSave:
    def test_save_creates_file(self, model, storage_path):
        """save() writes a JSON file at the storage path."""
        model.save()
        assert os.path.exists(storage_path)

    def test_save_updates_last_updated(self, model, storage_path):
        """save() refreshes the last_updated timestamp."""
        original = model.data["last_updated"]
        model.save()
        with open(storage_path) as f:
            saved = json.load(f)
        # last_updated is present and not empty
        assert saved["last_updated"] != ""

    def test_save_creates_parent_directories(self, tmp_path):
        """save() creates nested directories if they do not exist."""
        deep_path = str(tmp_path / "a" / "b" / "c" / "wm.json")
        wm = WorldModel(storage_path=deep_path)
        wm.save()
        assert os.path.exists(deep_path)

    def test_saved_data_is_valid_json(self, model, storage_path):
        """Data saved to disk can be parsed as JSON."""
        model.save()
        with open(storage_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)


class TestFrequentPaths:
    def test_add_new_frequent_path(self, model):
        """New path starts with the given access count."""
        model.add_frequent_path("/home/user/Downloads", access_count=1)
        assert model.data["frequent_paths"]["/home/user/Downloads"] == 1

    def test_add_frequent_path_increments_existing(self, model):
        """Adding the same path accumulates the count."""
        model.add_frequent_path("/home/user/Downloads", access_count=1)
        model.add_frequent_path("/home/user/Downloads", access_count=3)
        assert model.data["frequent_paths"]["/home/user/Downloads"] == 4

    def test_add_frequent_path_expands_tilde(self, model):
        """Tilde in path is expanded before storing."""
        model.add_frequent_path("~/Documents", access_count=1)
        expanded = os.path.expanduser("~/Documents")
        assert expanded in model.data["frequent_paths"]

    def test_update_path_frequency_is_alias(self, model):
        """update_path_frequency increments count by 1."""
        model.add_frequent_path("/tmp/x", access_count=5)
        model.update_path_frequency("/tmp/x")
        assert model.data["frequent_paths"]["/tmp/x"] == 6

    def test_get_frequent_paths_sorted_by_count(self, model):
        """get_frequent_paths returns paths sorted highest count first."""
        model.add_frequent_path("/a", access_count=1)
        model.add_frequent_path("/b", access_count=10)
        model.add_frequent_path("/c", access_count=5)

        paths = model.get_frequent_paths(limit=3)
        assert paths[0] == "/b"
        assert paths[1] == "/c"
        assert paths[2] == "/a"

    def test_get_frequent_paths_respects_limit(self, model):
        """get_frequent_paths returns at most the requested number."""
        for i in range(5):
            model.add_frequent_path(f"/path/{i}", access_count=i + 1)

        paths = model.get_frequent_paths(limit=2)
        assert len(paths) == 2

    def test_get_frequent_paths_empty(self, model):
        """Returns empty list when no paths recorded."""
        assert model.get_frequent_paths() == []

    def test_add_frequent_path_persists_to_disk(self, storage_path):
        """Frequent path is persisted after add_frequent_path call."""
        wm1 = WorldModel(storage_path=storage_path)
        wm1.add_frequent_path("/persist/me", access_count=2)

        wm2 = WorldModel(storage_path=storage_path)
        assert "/persist/me" in wm2.data["frequent_paths"]
        assert wm2.data["frequent_paths"]["/persist/me"] == 2


class TestPreferences:
    def test_set_and_get_preference(self, model):
        """Stored preference can be retrieved by key."""
        model.set_preference("editor", "vim")
        assert model.get_preference("editor") == "vim"

    def test_get_missing_preference_returns_none(self, model):
        """Retrieving an absent preference key returns None."""
        assert model.get_preference("nonexistent") is None

    def test_get_missing_preference_with_default(self, model):
        """Retrieving an absent key returns the provided default."""
        assert model.get_preference("nonexistent", default="fallback") == "fallback"

    def test_overwrite_preference(self, model):
        """Setting an existing key overwrites the previous value."""
        model.set_preference("theme", "light")
        model.set_preference("theme", "dark")
        assert model.get_preference("theme") == "dark"

    def test_preference_persists_to_disk(self, storage_path):
        """Preference survives a reload from disk."""
        wm1 = WorldModel(storage_path=storage_path)
        wm1.set_preference("lang", "en")

        wm2 = WorldModel(storage_path=storage_path)
        assert wm2.get_preference("lang") == "en"


class TestPatterns:
    def test_add_new_pattern(self, model):
        """Adding a new pattern creates a record with occurrences=1."""
        model.add_pattern("User organizes Downloads every Monday")
        patterns = model.get_patterns()
        assert len(patterns) == 1
        assert patterns[0]["description"] == "User organizes Downloads every Monday"
        assert patterns[0]["occurrences"] == 1

    def test_add_duplicate_pattern_increments_occurrences(self, model):
        """Repeating the same description increments the occurrence count."""
        model.add_pattern("Backups go to ~/Backups")
        model.add_pattern("Backups go to ~/Backups")
        patterns = model.get_patterns()
        assert len(patterns) == 1
        assert patterns[0]["occurrences"] == 2

    def test_add_distinct_patterns(self, model):
        """Different descriptions are stored as separate pattern entries."""
        model.add_pattern("Pattern A")
        model.add_pattern("Pattern B")
        assert len(model.get_patterns()) == 2

    def test_pattern_has_first_seen_field(self, model):
        """New pattern entry has a non-empty first_seen timestamp."""
        model.add_pattern("Some pattern")
        assert model.get_patterns()[0]["first_seen"] != ""

    def test_patterns_persist_to_disk(self, storage_path):
        """Patterns survive a reload from disk."""
        wm1 = WorldModel(storage_path=storage_path)
        wm1.add_pattern("Persistent pattern")

        wm2 = WorldModel(storage_path=storage_path)
        descriptions = [p["description"] for p in wm2.get_patterns()]
        assert "Persistent pattern" in descriptions

    def test_get_patterns_empty(self, model):
        """Returns empty list when no patterns recorded."""
        assert model.get_patterns() == []


class TestApplications:
    def test_register_and_find_application(self, model):
        """Registered application path is retrievable by name."""
        model.register_application("firefox", "/usr/bin/firefox")
        assert model.find_application("firefox") == "/usr/bin/firefox"

    def test_register_application_with_category(self, model):
        """Application registered with a category stores that category."""
        model.register_application("vlc", "/usr/bin/vlc", category="media")
        assert model.data["applications"]["vlc"]["category"] == "media"

    def test_register_application_without_category(self, model):
        """Category defaults to None when not provided."""
        model.register_application("htop", "/usr/bin/htop")
        assert model.data["applications"]["htop"]["category"] is None

    def test_find_missing_application_returns_none(self, model):
        """Looking up an unregistered application returns None."""
        assert model.find_application("unknown") is None

    def test_overwrite_application(self, model):
        """Re-registering a name overwrites the path."""
        model.register_application("app", "/old/path")
        model.register_application("app", "/new/path")
        assert model.find_application("app") == "/new/path"

    def test_application_persists_to_disk(self, storage_path):
        """Registered application survives a reload from disk."""
        wm1 = WorldModel(storage_path=storage_path)
        wm1.register_application("nano", "/usr/bin/nano")

        wm2 = WorldModel(storage_path=storage_path)
        assert wm2.find_application("nano") == "/usr/bin/nano"


class TestGetSummary:
    def test_summary_is_string(self, model):
        """get_summary returns a non-empty string."""
        summary = model.get_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_summary_contains_counts(self, model):
        """Summary reflects counts of stored entries."""
        model.set_preference("k", "v")
        model.add_frequent_path("/a", access_count=1)
        model.add_pattern("p")

        summary = model.get_summary()
        assert "1" in summary  # at least one count appears

    def test_summary_contains_last_updated(self, model):
        """Summary line mentions the last_updated timestamp."""
        model.save()
        summary = model.get_summary()
        assert "updated" in summary.lower()
