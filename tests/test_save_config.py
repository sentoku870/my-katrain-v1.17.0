# tests/test_save_config.py
"""Tests for save_config error handling (Issue 2)."""

from unittest.mock import Mock

from katrain.core.base_katrain import OUTPUT_ERROR, _save_config_with_errors


def test_save_config_continues_on_partial_failure():
    """Verify save continues when one section fails."""
    config = {"good1": {"a": 1}, "bad": {"b": 2}, "good2": {"c": 3}}

    saved_keys = []

    def mock_put(key, **kwargs):
        if key == "bad":
            raise OSError("Simulated error")
        saved_keys.append(key)

    mock_store = Mock()
    mock_store.put = mock_put
    mock_log = Mock()

    failed = _save_config_with_errors(config, mock_store, mock_log, key=None)

    assert "good1" in saved_keys
    assert "good2" in saved_keys
    assert failed == ["bad"]


def test_save_config_logs_each_failure_and_summary():
    """Verify failures are logged with key names and summary."""
    config = {"sec1": {"a": 1}, "sec2": {"b": 2}}
    mock_store = Mock()
    mock_store.put = Mock(side_effect=OSError("disk full"))

    logged = []

    def mock_log(msg, level):
        logged.append((msg, level))

    _save_config_with_errors(config, mock_store, mock_log, key=None)

    # Check per-key errors logged
    assert any("sec1" in msg and "Failed to save" in msg for msg, _ in logged)
    assert any("sec2" in msg and "Failed to save" in msg for msg, _ in logged)
    # Check summary logged
    assert any("2/2 section(s) failed" in msg for msg, _ in logged)
    # Check all logged at ERROR level
    assert all(level == OUTPUT_ERROR for _, level in logged)


def test_save_config_single_key_error():
    """Verify single key save logs error correctly."""
    config = {"mykey": {"data": 1}}
    mock_store = Mock()
    mock_store.put = Mock(side_effect=PermissionError("read-only"))

    logged = []

    def mock_log(msg, level):
        logged.append(msg)

    failed = _save_config_with_errors(config, mock_store, mock_log, key="mykey")

    assert failed == ["mykey"]
    assert any("mykey" in msg for msg in logged)


def test_save_config_success_returns_empty_list():
    """Verify successful save returns empty failed list."""
    config = {"sec1": {"a": 1}}
    mock_store = Mock()
    mock_log = Mock()

    failed = _save_config_with_errors(config, mock_store, mock_log, key=None)

    assert failed == []
    mock_log.assert_not_called()
