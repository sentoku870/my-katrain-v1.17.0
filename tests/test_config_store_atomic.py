# tests/test_config_store_atomic.py
"""Tests for atomic config save (Issue 1)."""

import json

import pytest

from katrain.common.config_store import JsonFileConfigStore


def test_atomic_save_success(tmp_path):
    """Verify successful save creates valid JSON."""
    config_file = tmp_path / "config.json"
    store = JsonFileConfigStore(str(config_file))
    store.put("test", mykey="value")

    with open(config_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["test"]["mykey"] == "value"


def test_atomic_save_preserves_original_on_failure(tmp_path, monkeypatch):
    """Verify original file unchanged when write fails."""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"existing": {"data": 1}}', encoding="utf-8")

    store = JsonFileConfigStore(str(config_file))
    store._data = {"existing": {"data": 1}}

    # Patch json.dump IN THE MODULE UNDER TEST
    def failing_dump(*args, **kwargs):
        raise OSError("Simulated disk error")

    monkeypatch.setattr("katrain.common.config_store.json.dump", failing_dump)

    with pytest.raises(IOError):
        store._save()

    # Original file should be unchanged
    with open(config_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"existing": {"data": 1}}


def test_atomic_save_cleans_temp_on_failure(tmp_path, monkeypatch):
    """Verify temp file is removed on failure."""
    config_file = tmp_path / "config.json"
    store = JsonFileConfigStore(str(config_file))

    def failing_dump(*args, **kwargs):
        raise OSError("Simulated error")

    monkeypatch.setattr("katrain.common.config_store.json.dump", failing_dump)

    with pytest.raises(IOError):
        store._save()

    # No .tmp files should remain
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_atomic_save_with_relative_path(tmp_path, monkeypatch):
    """Verify save works with relative filename (no directory component)."""
    monkeypatch.chdir(tmp_path)
    store = JsonFileConfigStore("config.json")
    store.put("test", value=123)

    with open(tmp_path / "config.json", encoding="utf-8") as f:
        data = json.load(f)
    assert data["test"]["value"] == 123
