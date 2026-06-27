"""Phase 148-D2: Tests for skill preset reason_tag_thresholds (Phase 148-C3)."""
from __future__ import annotations

from katrain.core.eval_metrics import get_skill_preset


def test_standard_preset_reason_tag_thresholds_tightened():
    """Phase 148-C3: standard preset tightened (heavy_loss 15→5, reading_failure 20→8)."""
    standard = get_skill_preset("standard")
    assert standard.reason_tag_thresholds.heavy_loss == 5.0
    assert standard.reason_tag_thresholds.reading_failure == 8.0


def test_other_presets_reason_tag_thresholds_unchanged():
    """Other presets retain original thresholds."""
    expected = [
        ("relaxed", 45.0, 60.0),
        ("beginner", 30.0, 40.0),
        ("advanced", 10.0, 15.0),
        ("pro", 3.0, 4.0),
    ]
    for name, expected_hl, expected_rf in expected:
        preset = get_skill_preset(name)
        assert preset.reason_tag_thresholds.heavy_loss == expected_hl, (
            f"{name} heavy_loss"
        )
        assert preset.reason_tag_thresholds.reading_failure == expected_rf, (
            f"{name} reading_failure"
        )