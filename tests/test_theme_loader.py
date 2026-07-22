# tests/test_theme_loader.py
"""Tests for theme loader (Issue 5, Phase 287-G extensions)."""

import logging

import pytest

from katrain.gui.theme import Theme
from katrain.gui.theme_loader import (
    LEGACY_ICON_TO_MDI,
    _validate_color_value,
    load_theme_overrides,
)


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


# ---------------------------------------------------------------------- #
# Phase 287-G: カラートークン検証 + Material Icon マッピング            #
# ---------------------------------------------------------------------- #


def test_color_validator_accepts_rgba_unit_list():
    assert _validate_color_value([0.0, 0.0, 0.0, 0.0]) is True
    assert _validate_color_value([1.0, 1.0, 1.0, 1.0]) is True
    assert _validate_color_value([0.5, 0.5, 0.5, 1.0]) is True


def test_color_validator_rejects_invalid_shapes():
    assert _validate_color_value([1, 1, 1]) is False  # 3 components
    assert _validate_color_value([1, 1, 1, 1, 1]) is False  # 5 components
    assert _validate_color_value("white") is False
    assert _validate_color_value({"r": 1, "g": 1, "b": 1, "a": 1}) is False


def test_color_validator_rejects_out_of_range():
    assert _validate_color_value([1.5, 0, 0, 1]) is False
    assert _validate_color_value([-0.1, 0, 0, 1]) is False


def test_theme_loader_rejects_invalid_color_value(tmp_path, caplog):
    theme_file = tmp_path / "bad_color.json"
    theme_file.write_text('{"COLOR_PRIMARY": [2, 0, 0, 1]}', encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        load_theme_overrides(str(theme_file), Theme)
    assert "invalid color value" in caplog.text
    # Original color must be preserved when override is rejected.
    assert all(0.0 <= c <= 1.0 for c in Theme.COLOR_PRIMARY)


def test_legacy_icon_table_covers_all_kv_icons():
    """Every PNG file referenced in menu.kv / board.kv must be mapped to MDI."""
    expected_icons = {
        "hamburger.png",
        "New-Game.png",
        "Insert-Move.png",
        "Save-Game.png",
        "Save-Game-As.png",
        "Load-Game.png",
        "Time-Settings.png",
        "Teaching-Settings.png",
        "AI-Settings.png",
        "General-Settings.png",
        "Extra.png",
        "Equalize.png",
        "Sweep.png",
        "Alternative.png",
        "local.png",
        "reset.png",
        "Finish.png",
        "Deeper all.png",
        "analysis.png",
        "play.png",
        "ai.png",
        "Previous.png",
        "Previous-5.png",
        "Previous-End.png",
        "Previous-Mistake.png",
        "Next.png",
        "Next-5.png",
        "Next-End.png",
        "Next-Mistake.png",
        "Rotate.png",
        "delete.png",
        "Branch.png",
        "Collapse.png",
        "Prune.png",
    }
    missing = expected_icons - set(LEGACY_ICON_TO_MDI)
    assert not missing, f"Missing icon mappings: {sorted(missing)}"


def test_legacy_icon_mapping_targets_valid_mdi_names():
    """Every mapped MDI name must exist in KivyMD's md_icons dictionary."""
    kivy = pytest.importorskip("kivymd.icon_definitions")
    md_icons = kivy.md_icons
    bad = [png for png, mdi in LEGACY_ICON_TO_MDI.items() if mdi not in md_icons]
    assert not bad, f"Invalid MDI names: {bad}"


def test_theme_semantic_tokens_within_unit_range():
    """All semantic COLOR_* tokens must be RGBA values in [0, 1]."""
    for name in vars(Theme):
        if not name.startswith("COLOR_"):
            continue
        value = getattr(Theme, name)
        assert isinstance(value, list), f"{name} is not a list"
        assert len(value) == 4, f"{name} must have 4 components"
        for c in value:
            assert isinstance(c, (int, float)), f"{name} contains non-numeric: {c}"
            assert 0.0 <= c <= 1.0, f"{name} out of range: {c}"


def test_font_constants_point_to_existing_or_safe_files():
    """DEFAULT_FONT must be a Noto Sans JP file we actually ship."""
    assert Theme.DEFAULT_FONT.endswith(".otf") or Theme.DEFAULT_FONT.endswith(".ttf")
    # KivyMD 1.2.0 registers the MDI font with the logical name ``Icons``
    # via LabelBase.register; using the file name directly breaks
    # ``Label: File ... not found`` because Kivy resolves ``font_name``
    # against LabelBase first, not as a filesystem path.
    assert Theme.DEFAULT_ICON_FONT == "Icons"
