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


# ---------------------------------------------------------------------------
# Phase A-9: thread-safe reload
# ---------------------------------------------------------------------------


def test_reload_picks_up_external_changes(tmp_path):
    """After rewriting the file out-of-band, reload() re-reads it."""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"a": {"x": 1}}), encoding="utf-8")
    store = JsonFileConfigStore(str(config_path))

    assert store.get("a") == {"x": 1}

    # Mutate the file from "outside" (simulating another process or
    # settings_popup_io restoring a backup).
    config_path.write_text(json.dumps({"a": {"x": 999}, "b": {"y": 2}}), encoding="utf-8")

    store.reload()
    assert store.get("a") == {"x": 999}
    assert store.get("b") == {"y": 2}


def test_reload_does_not_corrupt_state_when_called_concurrently_with_put(tmp_path):
    """A concurrent reload() must not observe a half-written put()."""
    import threading

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"init": {"v": 0}}), encoding="utf-8")
    store = JsonFileConfigStore(str(config_path))

    errors: list[str] = []

    def writer() -> None:
        try:
            for i in range(50):
                store.put("writer", value=i)
        except Exception as e:  # pragma: no cover - test instrumentation
            errors.append(f"writer: {e!r}")

    def reloader() -> None:
        try:
            for _ in range(50):
                store.reload()
        except Exception as e:  # pragma: no cover - test instrumentation
            errors.append(f"reloader: {e!r}")

    threads = [threading.Thread(target=writer), threading.Thread(target=reloader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent reload/put raised: {errors}"
    # Final state must reflect the last put().
    assert store.get("writer") == {"value": 49}
