# tests/test_theme_loader.py
"""Tests for theme loader (Issue 5)."""

import logging

from katrain.gui.theme_loader import load_theme_overrides


def test_theme_loading_applies_known_keys(tmp_path):
    """Verify known theme keys are applied."""
    theme_file = tmp_path / "theme_test.json"
    theme_file.write_text('{"TEXT_COLOR": [0.5, 0.5, 0.5, 1]}', encoding="utf-8")

    class MockTheme:
        TEXT_COLOR = [1, 1, 1, 1]

    load_theme_overrides(str(theme_file), MockTheme)

    assert MockTheme.TEXT_COLOR == [0.5, 0.5, 0.5, 1]


def test_theme_loading_ignores_unknown_keys(tmp_path, caplog):
    """Verify unknown keys are logged and ignored."""
    theme_file = tmp_path / "theme_test.json"
    theme_file.write_text('{"UNKNOWN_KEY": "value", "TEXT_COLOR": [1,1,1,1]}', encoding="utf-8")

    class MockTheme:
        TEXT_COLOR = [0, 0, 0, 1]

    with caplog.at_level(logging.WARNING):
        load_theme_overrides(str(theme_file), MockTheme)

    assert "Unknown theme key 'UNKNOWN_KEY'" in caplog.text
    assert not hasattr(MockTheme, "UNKNOWN_KEY")
    # Known key should still be applied
    assert MockTheme.TEXT_COLOR == [1, 1, 1, 1]


def test_theme_loading_handles_invalid_json(tmp_path, caplog):
    """Verify invalid JSON is handled gracefully."""
    theme_file = tmp_path / "theme_bad.json"
    theme_file.write_text('{"broken":', encoding="utf-8")

    class MockTheme:
        pass

    with caplog.at_level(logging.WARNING):
        load_theme_overrides(str(theme_file), MockTheme)

    assert "Failed to load theme file" in caplog.text


def test_theme_loading_handles_encoding_error(tmp_path, caplog):
    """Verify non-UTF-8 file is handled gracefully."""
    theme_file = tmp_path / "theme_enc.json"
    # Write invalid UTF-8 sequence
    theme_file.write_bytes(b'{"key": "\xff\xfe"}')

    class MockTheme:
        pass

    with caplog.at_level(logging.WARNING):
        load_theme_overrides(str(theme_file), MockTheme)

    assert "Failed to load theme file" in caplog.text


def test_theme_loading_handles_missing_file(tmp_path, caplog):
    """Verify missing file is handled gracefully."""

    class MockTheme:
        pass

    with caplog.at_level(logging.WARNING):
        load_theme_overrides(str(tmp_path / "nonexistent.json"), MockTheme)

    assert "Failed to load theme file" in caplog.text
