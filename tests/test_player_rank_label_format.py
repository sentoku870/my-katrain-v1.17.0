"""Phase 229: regression test for the i18n format pattern in
``_format_rank_inferred_label``.

The original implementation passed keyword arguments directly to
``i18n._("key", preset=...)`` which raised::

    TypeError: Lang._() got an unexpected keyword argument 'preset'

The fix is to call ``i18n._("key").format(preset=...)`` instead — the
pattern used everywhere else in the codebase (81 callsites across the
gui / core / popup packages).
"""

from __future__ import annotations

import pytest

# Phase 226-D (D1): skip the popup tests only when Kivy itself is
# unimportable.  Same gating as test_llm_coach_popup.
try:
    import kivy  # noqa: F401

    _KIVY_AVAILABLE = True
except ImportError:
    _KIVY_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _KIVY_AVAILABLE,
    reason="Kivy is not installed in this environment",
)


class TestRankInferredLabelFormat:
    """The label helper must produce a non-empty string for both branches."""

    def test_with_rank_returns_non_empty_string(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_rank_inferred_label,
        )

        result = _format_rank_inferred_label("5d", "standard")
        assert isinstance(result, str)
        assert len(result) > 0
        # The rank should appear somewhere in the rendered label.
        assert "5d" in result

    def test_without_rank_returns_non_empty_string(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_rank_inferred_label,
        )

        result = _format_rank_inferred_label("", "standard")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_kanji_rank(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_rank_inferred_label,
        )

        # CJK rank strings must also flow through without raising.
        result = _format_rank_inferred_label("4段", "advanced")
        assert "4段" in result

    def test_unknown_preset_falls_back_to_raw_name(self) -> None:
        """If the preset name isn't in SKILL_PRESET_LABELS, the raw name is used."""
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_rank_inferred_label,
        )

        result = _format_rank_inferred_label("5d", "totally_made_up_preset")
        assert isinstance(result, str)
        assert "totally_made_up_preset" in result