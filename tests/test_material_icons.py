"""Phase 287-G: Material Design Icons 移行の回帰テスト.

このファイルではアイコン解決ロジックとテーマ定数の整合性に絞ったテストを
実施する。Widget のインスタンス化は Kivy の GL/window を要求するため、
GUI 起動確認は手動 / xvfb-run で行う (本テストでは行わない)。
"""

from __future__ import annotations

from tests.kivy_test_base import KivyUnitTest


class TestMaterialIconMapping(KivyUnitTest):
    def test_legacy_png_resolves_to_known_mdi_name(self):
        """Common legacy PNG names resolve to a valid MDI icon name."""
        import kivymd.icon_definitions as kd

        from katrain.gui.theme_loader import LEGACY_ICON_TO_MDI

        for png in ("hamburger.png", "Save-Game.png", "Rotate.png", "Previous.png"):
            resolved = LEGACY_ICON_TO_MDI.get(png, png)
            assert resolved in kd.md_icons, f"{png} -> {resolved} is not in md_icons"

    def test_default_icon_font_is_material_design_icons(self):
        from katrain.gui.theme import Theme

        # KivyMD 1.2.0 registers the MDI font with the logical name
        # ``Icons`` via LabelBase.register; using the file name directly
        # fails with ``OSError: Label: File ... not found`` because Kivy
        # resolves ``font_name`` against LabelBase first, not as a path.
        assert Theme.DEFAULT_ICON_FONT == "Icons"

    def test_mdi_or_image_resolves_png_to_image(self):
        """MdiIconOrImage detects PNG paths via the static helper."""
        from katrain.gui.widgets.mdi_or_image import MdiIconOrImage

        assert MdiIconOrImage.is_png_path("flags/flag-jp.png") is True
        assert MdiIconOrImage.is_png_path("menu") is False

    def test_mdi_or_image_resolves_mdi_name(self):
        """MdiIconOrImage returns the MDI glyph for a known name."""
        import kivymd.icon_definitions as kd

        from katrain.gui.widgets.mdi_or_image import MdiIconOrImage

        glyph = MdiIconOrImage.resolve_mdi_glyph("menu")
        assert glyph == kd.md_icons["menu"]

    def test_mdi_or_image_resolves_legacy_png_to_glyph(self):
        """Legacy PNG names are translated via LEGACY_ICON_TO_MDI."""
        import kivymd.icon_definitions as kd

        from katrain.gui.widgets.mdi_or_image import MdiIconOrImage

        glyph = MdiIconOrImage.resolve_mdi_glyph("Save-Game.png")
        assert glyph == kd.md_icons["content-save"]

    def test_mdi_or_image_returns_empty_for_unknown(self):
        from katrain.gui.widgets.mdi_or_image import MdiIconOrImage

        assert MdiIconOrImage.resolve_mdi_glyph("") == ""
        # Unknown PNG stays a PNG fallback and yields empty glyph.
        assert MdiIconOrImage.resolve_mdi_glyph("flags/flag-jp.png") == ""


class TestMdiToPngFallback(KivyUnitTest):
    """Phase 287-G: ``MaterialIconButton`` rendering reliability fallback.

    Kivy Label-based MDI rendering proved unreliable inside KivyMD 1.2.0
    ``CircularRippleBehavior, Button`` (texture generated but display layer
    failed to show it). The pragmatic fix: keep using the proven Image
    widget path by mapping MDI names back to existing PNG files via
    ``MDI_TO_PNG_FALLBACK``.
    """

    def test_mdi_to_png_fallback_covers_all_kv_mdi_names(self):
        """Every MDI name used in board.kv / menu.kv must have a PNG fallback."""
        from katrain.gui.theme_loader import MDI_TO_PNG_FALLBACK

        expected = {
            "menu",
            "chevron-left",
            "chevron-right",
            "rewind-10",
            "fast-forward-10",
            "page-first",
            "page-last",
            "rotate-right",
            "arrow-left-circle",
            "arrow-right-circle",
            "delete",
            "source-branch",
            "unfold-less-horizontal",
            "source-branch-remove",
            "file-plus-outline",
            "format-list-numbered",
            "content-save",
            "content-save-edit",
            "folder-open",
            "clock-outline",
            "school-outline",
            "robot-outline",
            "cog-outline",
            "plus-circle-outline",
            "plus-box-outline",
            "scale-balance",
            "magnify-scan",
            "selection-drag",
            "refresh",
            "skip-forward",
            "chart-line",
            "chart-box-outline",
            "puzzle-outline",
            "play",
            "robot-happy-outline",
            "file-export-outline",
            "chat-processing-outline",
        }
        missing = expected - set(MDI_TO_PNG_FALLBACK)
        assert not missing, f"Missing MDI -> PNG mappings: {sorted(missing)}"

    def test_mdi_to_png_targets_existing_files(self):
        """Every PNG fallback must exist on disk under ``katrain/img/``."""
        from pathlib import Path

        from katrain.gui.theme_loader import MDI_TO_PNG_FALLBACK

        img_dir = Path("katrain/img")
        for mdi, png in MDI_TO_PNG_FALLBACK.items():
            assert (img_dir / png).exists(), f"{mdi} -> {png} not found under {img_dir}"


class TestNavIconMigration(KivyUnitTest):
    """board.kv の棋譜ナビゲーションが全て MDI 名に置き換わったことを保証する。"""

    def test_board_kv_has_no_legacy_png_navigation(self):
        from pathlib import Path

        board_kv = Path("katrain/gui/kv/board.kv").read_text(encoding="utf-8")
        legacy_navigation_icons = (
            "Previous-Mistake.png",
            "Previous-End.png",
            "Previous-5.png",
            "Previous.png",
            "Next.png",
            "Next-5.png",
            "Next-End.png",
            "Next-Mistake.png",
            "Rotate.png",
        )
        for png in legacy_navigation_icons:
            assert f"'{png}'" not in board_kv, f"board.kv still references legacy icon {png}. Use the MDI name instead."

    def test_menu_kv_has_no_legacy_main_icons(self):
        from pathlib import Path

        menu_kv = Path("katrain/gui/kv/menu.kv").read_text(encoding="utf-8")
        legacy_menu_icons = (
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
            "hamburger.png",
        )
        for png in legacy_menu_icons:
            assert f"'{png}'" not in menu_kv, f"menu.kv still references legacy icon {png}. Use the MDI name instead."


class TestThemeFontTokens(KivyUnitTest):
    def test_default_font_is_noto_sans_jp(self):
        from katrain.gui.theme import Theme

        assert "NotoSansJP" in Theme.DEFAULT_FONT
        assert Theme.DEFAULT_FONT.endswith(".otf") or Theme.DEFAULT_FONT.endswith(".ttf")

    def test_default_font_bold_falls_back_to_regular(self):
        """Bold OTF is not bundled; both tokens point to the regular file."""
        from katrain.gui.theme import Theme

        # When no dedicated Bold OTF is present the canonical value points
        # to the regular file (Kivy's ``bold: True`` synthesises bold via
        # the same glyphs).
        assert Theme.DEFAULT_FONT_BOLD == Theme.DEFAULT_FONT

    def test_common_default_font_bold_imported(self):
        from katrain.common import DEFAULT_FONT_BOLD

        assert DEFAULT_FONT_BOLD == "NotoSansJP-Regular.otf"

    def test_default_icon_font_imported(self):
        from katrain.common import DEFAULT_ICON_FONT

        assert DEFAULT_ICON_FONT == "Icons"
