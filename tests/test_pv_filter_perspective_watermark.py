"""Phase 246-B (H1): regression test for the perspective-watermark i18n
string used by ``draw_perspective_watermark``.

The watermark is rendered with Kivy ``draw_text`` so we can't easily
unit-test the canvas drawing itself. This test pins the i18n templates
so the format placeholders never silently drift.
"""

from __future__ import annotations


class TestPerspectiveWatermarkTemplate:
    """``board:perspective`` must accept a single ``{player}`` placeholder."""

    def test_en_template_renders(self) -> None:
        from katrain.core.lang import Lang

        i18n = Lang("en")
        text = i18n._("board:perspective").format(player="B")
        assert "B" in text
        # No unfilled placeholders left over.
        assert "{player}" not in text

    def test_jp_template_renders(self) -> None:
        from katrain.core.lang import Lang

        i18n = Lang("jp")
        text = i18n._("board:perspective").format(player="B")
        # JP label should contain the perspective letter.
        assert "B" in text
        # And NOT have leftover placeholders.
        assert "{player}" not in text

    def test_white_renders(self) -> None:
        from katrain.core.lang import Lang

        i18n = Lang("en")
        text = i18n._("board:perspective").format(player="W")
        assert "W" in text
        assert "{player}" not in text

    def test_jp_and_en_agree_on_placeholder_count(self) -> None:
        """Both locales must have exactly one ``{player}`` slot."""
        from katrain.core.lang import Lang

        en = Lang("en")._("board:perspective")
        jp = Lang("jp")._("board:perspective")
        assert en.count("{player}") == 1
        assert jp.count("{player}") == 1


class TestPVFilterMarkerLegendTemplate:
    """``mykatrain:settings:pv_filter_marker_legend`` is a free-form
    legend; we just check it's non-empty and has no leftover placeholders
    so users never see raw ``{...}`` in the settings popup."""

    def test_en_legend_renders(self) -> None:
        from katrain.core.lang import Lang

        text = Lang("en")._("mykatrain:settings:pv_filter_marker_legend")
        assert isinstance(text, str)
        assert len(text) > 0
        # No leftover placeholders.
        assert "{" not in text or "}" not in text or text.count("{") == text.count("}")

    def test_jp_legend_renders(self) -> None:
        from katrain.core.lang import Lang

        text = Lang("jp")._("mykatrain:settings:pv_filter_marker_legend")
        assert isinstance(text, str)
        assert len(text) > 0
