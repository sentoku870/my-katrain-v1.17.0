"""Tests for JsonFileConfigStore."""
import json
import os
import tempfile
import pytest
from pathlib import Path

from katrain.common.config_store import JsonFileConfigStore


class TestJsonFileConfigStore:
    """Tests for JsonFileConfigStore compatibility with kivy.storage.jsonstore.JsonStore."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary config file path."""
        return str(tmp_path / "config.json")

    def test_put_and_get(self, temp_config):
        """Test basic put and get operations."""
        store = JsonFileConfigStore(temp_config)
        store.put("general", version="1.0", language="en")

        result = store.get("general")
        assert result == {"version": "1.0", "language": "en"}

    def test_get_nonexistent(self, temp_config):
        """Test get returns None for nonexistent keys."""
        store = JsonFileConfigStore(temp_config)
        assert store.get("nonexistent") is None

    def test_exists(self, temp_config):
        """Test exists method."""
        store = JsonFileConfigStore(temp_config)
        store.put("test", value=42)

        assert store.exists("test") is True
        assert store.exists("nonexistent") is False

    def test_delete(self, temp_config):
        """Test delete method."""
        store = JsonFileConfigStore(temp_config)
        store.put("test", value=42)

        assert store.delete("test") is True
        assert store.exists("test") is False
        assert store.delete("test") is False  # Already deleted

    def test_persistence(self, temp_config):
        """Test data persists across instances."""
        store1 = JsonFileConfigStore(temp_config)
        store1.put("general", version="1.0")

        store2 = JsonFileConfigStore(temp_config)
        result = store2.get("general")
        assert result == {"version": "1.0"}

    def test_dict_conversion_works(self, temp_config):
        """Test that dict(store) works correctly (Mapping protocol)."""
        store = JsonFileConfigStore(temp_config)
        store.put("general", version="1.0", language="en")
        store.put("engine", path="/usr/bin/katago")

        result = dict(store)
        assert result == {
            "general": {"version": "1.0", "language": "en"},
            "engine": {"path": "/usr/bin/katago"},
        }

    def test_len(self, temp_config):
        """Test __len__ method."""
        store = JsonFileConfigStore(temp_config)
        assert len(store) == 0

        store.put("section1", a=1)
        assert len(store) == 1

        store.put("section2", b=2)
        assert len(store) == 2

    def test_iter(self, temp_config):
        """Test iteration over keys."""
        store = JsonFileConfigStore(temp_config)
        store.put("general", version="1.0")
        store.put("engine", path="/usr/bin/katago")

        keys = list(store)
        assert "general" in keys
        assert "engine" in keys

    def test_contains(self, temp_config):
        """Test __contains__ method."""
        store = JsonFileConfigStore(temp_config)
        store.put("test", value=42)

        assert "test" in store
        assert "nonexistent" not in store

    def test_getitem(self, temp_config):
        """Test __getitem__ method."""
        store = JsonFileConfigStore(temp_config)
        store.put("test", value=42)

        assert store["test"] == {"value": 42}

        with pytest.raises(KeyError):
            _ = store["nonexistent"]

    def test_keys_method(self, temp_config):
        """Test keys() method returns iterator."""
        store = JsonFileConfigStore(temp_config)
        store.put("a", x=1)
        store.put("b", y=2)

        keys = list(store.keys())
        assert set(keys) == {"a", "b"}

    def test_indent(self, temp_config):
        """Test that indent parameter affects JSON formatting."""
        store = JsonFileConfigStore(temp_config, indent=2)
        store.put("test", value=42)

        with open(temp_config, "r") as f:
            content = f.read()

        # Check that indentation is applied
        assert "  " in content  # 2-space indent

    def test_unicode_support(self, temp_config):
        """Test Unicode content is properly handled."""
        store = JsonFileConfigStore(temp_config)
        store.put("i18n", greeting="こんにちは", name="日本語")

        store2 = JsonFileConfigStore(temp_config)
        result = store2.get("i18n")
        assert result == {"greeting": "こんにちは", "name": "日本語"}

    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directories are created if needed."""
        nested_path = str(tmp_path / "subdir" / "config.json")
        store = JsonFileConfigStore(nested_path)
        store.put("test", value=42)

        assert os.path.exists(nested_path)

    def test_handles_corrupted_json(self, temp_config):
        """Test graceful handling of corrupted JSON file."""
        # Write invalid JSON
        with open(temp_config, "w") as f:
            f.write("{ invalid json }")

        # Should load with empty data instead of crashing
        store = JsonFileConfigStore(temp_config)
        assert len(store) == 0

    def test_put_overwrites_section(self, temp_config):
        """Test that put overwrites entire section."""
        store = JsonFileConfigStore(temp_config)
        store.put("test", a=1, b=2)
        store.put("test", c=3)

        result = store.get("test")
        assert result == {"c": 3}  # a and b are gone
