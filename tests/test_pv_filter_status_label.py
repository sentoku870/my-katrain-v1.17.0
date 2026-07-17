"""Phase 246-A (H2): regression test for the i18n format pattern in
``_format_pv_filter_status`` from the analysis tab.

The status label is a thin wrapper around
:func:`katrain.core.analysis.get_effective_pv_filter_info` that picks the
right i18n template based on the resolved level. We want to make sure
the three templates (off / auto / explicit) all render a non-empty
string and never raise on the format/keyword combinations.
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


class TestPVFilterStatusLabelFormat:
    """The label helper must produce a non-empty string for all branches."""

    def test_off_returns_off_template(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        result = _format_pv_filter_status("off", "5d")
        assert isinstance(result, str)
        assert len(result) > 0
        # The OFF template should NOT contain "{max_n}" (i.e., no unfilled placeholders).
        assert "{max_n}" not in result
        assert "{level}" not in result
        assert "{preset}" not in result

    def test_explicit_medium_uses_explicit_template(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        result = _format_pv_filter_status("medium", "5d")
        assert isinstance(result, str)
        # Must include the candidate cap number (8) somewhere.
        assert "8" in result
        # No unfilled placeholders.
        assert "{max_n}" not in result
        assert "{level}" not in result
        assert "{preset}" not in result

    def test_explicit_strong_uses_explicit_template(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        result = _format_pv_filter_status("strong", "5d")
        assert "4" in result  # max_candidates=4

    def test_auto_with_rank_uses_auto_template(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        result = _format_pv_filter_status("auto", "5d")
        # 5d → advanced → strong → cap 4
        assert "4" in result
        # No unfilled placeholders.
        assert "{max_n}" not in result
        assert "{level}" not in result
        assert "{preset}" not in result

    def test_auto_with_empty_rank_uses_default_preset(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        result = _format_pv_filter_status("auto", "")
        # empty rank → standard → medium → cap 8
        assert "8" in result

    def test_auto_with_kanji_rank(self) -> None:
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        # CJK rank must not blow up the format() call.
        result = _format_pv_filter_status("auto", "4段")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_level_treated_as_auto(self) -> None:
        """Empty / None level is normalised to 'auto' before templating."""
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        # Empty string
        result_empty = _format_pv_filter_status("", "5d")
        # 5d → strong → cap 4
        assert "4" in result_empty
        # No unfilled placeholders.
        assert "{max_n}" not in result_empty
        assert "{level}" not in result_empty
        assert "{preset}" not in result_empty

    def test_case_insensitive(self) -> None:
        """Uppercase level is normalised (M6 bonus from H2 helpers)."""
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        result = _format_pv_filter_status("MEDIUM", "5d")
        assert "8" in result
        assert "{max_n}" not in result

    def test_unknown_level_renders_without_raising(self) -> None:
        """Unknown level produces a string (with cap=0) but no exception."""
        from katrain.gui.features.settings_popup_tabs.analysis_tab import (
            _format_pv_filter_status,
        )

        # Unknown level → explicit template (since not auto) with cap=0
        result = _format_pv_filter_status("nonexistent", "5d")
        assert isinstance(result, str)
        # Should still render with a 0 (cap) but no crash
        assert "0" in result
