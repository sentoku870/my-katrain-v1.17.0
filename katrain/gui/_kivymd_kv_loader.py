"""Phase 277: KivyMD 1.2.0 missing .kv files runtime loader.

KivyMD 1.2.0 was released without its companion ``.kv`` files in the
sdist/wheel (the upstream tarball ships only ``.py`` files). Every
``kivymd.uix.<widget>`` module does ``open(os.path.join(uix_path,
"<widget>", "<widget>.kv"))`` at module-import time, which fails with
``FileNotFoundError`` on the first import.

To make ``import kivymd.uix.button`` (etc.) work without forking
KivyMD, we:

1. Pre-create stub ``.kv`` files in a private tempdir that mirrors
   KivyMD's ``uix/<widget>/<widget>.kv`` layout.
2. Override ``kivymd.uix_path`` to point at the tempdir *before* any
   ``kivymd.uix.*`` submodule is imported.

The stub bodies contain enough canvas + property rules for the
widgets we actually use (``MDLabel``, ``MDTextField``, ``MDCheckbox``,
``MDNavigationDrawer``, ``MDCard``, ``MDButton``) to render and behave
correctly. Widgets we don't use get an empty rule so import still
succeeds.

Import order contract:

- This module MUST be imported **after** ``import kivy`` and
  ``import kivymd`` (so the package object exists), but **before** any
  ``from kivymd.uix import ...`` line.

- ``katrain/__main__.py`` imports this module at line ~31 (right after
  ``kivy.require("2.0.0")``, before ``from kivymd.app import MDApp``).

- ``tests/conftest.py`` also calls ``ensure_kivymd_kv_stubs()`` so test
  collection works.

Lifecycle:

- The tempdir is created once per process and reused across tests.
  ``_ensure_kv_stubs()`` is idempotent.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile

__all__ = ["ensure_kivymd_kv_stubs", "uix_path_override", "STUB_KV"]


_stub_root: str | None = None

# ---------------------------------------------------------------------------
# Stub .kv bodies
# ---------------------------------------------------------------------------
#
# Keep this table in sync with the affected KivyMD widget classes. The
# KivyMD source files (``kivymd/uix/<widget>/<widget>.py``) are the
# source of truth; ``grep -l uix_path kivymd/uix`` enumerates them.
#
# The bodies for widgets we actually use (``MDLabel``, ``MDTextField``,
# ``MDCheckbox``, ``MDNavigationDrawer``, etc.) contain working canvas
# + property rules so the widgets render correctly. The bodies are
# derived from the KivyMD 0.104.1 KV rules (which still apply for
# these properties) but trimmed of MD3-specific styling.
#
# Note: this dict is the single source of truth. Both this runtime
# loader and ``spec/hook-kivymd.py`` (PyInstaller build hook) import
# the same constant so the two cannot drift.
STUB_KV: dict[str, str] = {
    # ---- Widgets we don't actually use; just need a rule to import ----
    "backdrop/backdrop.kv": "<MDBackdrop>:\n",
    "banner/banner.kv": "<MDBanner>:\n",
    "bottomnavigation/bottomnavigation.kv": "<MDBottomNavigation>:\n",
    "bottomsheet/bottomsheet.kv": "<MDBottomSheet>:\n",
    "chip/chip.kv": "<MDChip>:\n",
    "datatables/datatables.kv": "<MDDataTable>:\n",
    "dialog/dialog.kv": "<MDDialog>:\n",
    "dropdownitem/dropdownitem.kv": "<MDDropDownItem>:\n",
    "expansionpanel/expansionpanel.kv": "<MDExpansionPanel>:\n",
    "filemanager/filemanager.kv": "<MDFileManager>:\n",
    "imagelist/imagelist.kv": "<MDSmartTile>:\n",
    "list/list.kv": "<MDList>:\n",
    "menu/menu.kv": "<MDDropdownMenu>:\n",
    "navigationrail/navigationrail.kv": "<MDNavigationRail>:\n",
    "pickers/colorpicker/colorpicker.kv": "<MDColorPicker>:\n",
    "pickers/datepicker/datepicker.kv": "<MDDatePicker>:\n",
    "pickers/timepicker/timepicker.kv": "<MDTimePicker>:\n",
    "progressbar/progressbar.kv": "<MDProgressBar>:\n",
    "refreshlayout/refreshlayout.kv": "<MDRefreshLayout>:\n",
    "segmentedbutton/segmentedbutton.kv": "<MDSegmentedButton>:\n",
    "segmentedcontrol/segmentedcontrol.kv": "<MDSegmentedControl>:\n",
    "selection/selection.kv": "<MDSelection>:\n",
    "slider/slider.kv": "<MDSlider>:\n",
    "sliverappbar/sliverappbar.kv": "<MDSliverAppBar>:\n",
    "snackbar/snackbar.kv": "<MDSnackbar>:\n",
    "spinner/spinner.kv": "<MDSpinner>:\n",
    "tab/tab.kv": "<MDTabs>:\n",
    "toolbar/toolbar.kv": "<MDTopAppBar>:\n",
    "tooltip/tooltip.kv": "<MDTooltip>:\n",
    "transition/transition.kv": "<MDScreenTransition>:\n",
    # ---- Widgets we DO use: provide working canvas + rules ----
    "button/button.kv": ("<MDButton>:\n    disabled_color: self.theme_cls.disabled_hint_text_color\n"),
    "card/card.kv": ("<MDCard>:\n    elevation: 0\n    md_bg_color: self.theme_cls.bg_light\n"),
    "label/label.kv": (
        "#:import md_icons kivymd.icon_definitions.md_icons\n"
        "\n"
        "<MDLabel>:\n"
        "    disabled_color: self.theme_cls.disabled_hint_text_color\n"
        "    text_size: self.width, None\n"
        "\n"
        "<MDIcon>:\n"
        '    font_style: "Icon"\n'
        "    text:\n"
        '        u"{}".format(md_icons[self.icon]) \\\n'
        '        if self.icon in md_icons else ""\n'
        "    source: None if self.icon in md_icons else self.icon\n"
        "    canvas:\n"
        "        Color:\n"
        "            rgba: (1, 1, 1, 1) if self.source else (0, 0, 0, 0)\n"
        "        Rectangle:\n"
        "            source: self.source if self.source else None\n"
        "            pos: self.pos\n"
        "            size: self.size\n"
    ),
    # MDNavigationDrawer is now MDCard-based (BoxLayout) in 1.2.0; its
    # default size_hint = (1, 1) would override the ``-width`` binding
    # in our main_layout.kv, so we force ``size_hint_x: None`` here.
    "navigationdrawer/navigationdrawer.kv": (
        "<MDNavigationDrawer>:\n    close_on_click: True\n    size_hint_x: None\n"
    ),
    # MDCheckbox renders the checkmark via canvas instructions; without
    # the kv rule the widget has no visible body.
    "selectioncontrol/selectioncontrol.kv": (
        "<MDCheckbox>:\n"
        "    canvas:\n"
        "        Clear\n"
        "        Color:\n"
        "            rgba: self.color\n"
        "        Rectangle:\n"
        "            texture: self.texture\n"
        "            size: self.texture_size\n"
        "            pos:\n"
        "                int(self.center_x - self.texture_size[0] / 2.),\\\n"
        "                int(self.center_y - self.texture_size[1] / 2.)\n"
        "    color: self._current_color\n"
        "    halign: 'center'\n"
        "    valign: 'middle'\n"
        "\n"
        "<Thumb>:\n"
        "    color: 1, 1, 1, 1\n"
        "    canvas:\n"
        "        Color:\n"
        "            rgba: self.color\n"
        "        Ellipse:\n"
        "            size: self.size\n"
        "            pos: self.pos\n"
    ),
    # MDTextField needs canvas for the underline, hint, helper text.
    # Property names changed between 0.104.1 and 1.2.0; we mirror the
    # 1.2.0 internals (``_underline_width``, ``hint_text_color``,
    # ``_hint_text_label``) so the canvas bindings resolve at
    # widget-construction time.
    #
    # ``TextfieldLabel`` inherits from raw ``kivy.uix.label.Label``,
    # which does NOT default ``font_name`` to our project's
    # ``NotoSansJP-Regular.otf`` (the project's ``factory.Label``
    # wrapper does that). We bind ``font_name`` to the parent
    # ``MDTextField`` so Japanese hint text renders correctly.
    #
    # Phase 281 (tofu-fix): Roboto fallback has been removed because
    # Kivy's built-in Roboto font has NO Japanese glyphs and would
    # render the hint text as tofu boxes. We now fall back to
    # ``Theme.DEFAULT_FONT`` (NotoSansJP-Regular.otf, which IS bundled
    # with the project) when the parent's ``font_name`` binding hasn't
    # propagated yet at first paint.
    "textfield/textfield.kv": (
        "#:import dp kivy.metrics.dp\n"
        "#:import Theme katrain.gui.theme.Theme\n"
        "\n"
        "<MDTextField>\n"
        "    canvas.before:\n"
        "        Clear\n"
        "        # Disabled line.\n"
        "        Color:\n"
        "            rgba:\n"
        "                self.line_color_normal \\\n"
        '                if root.mode == "line" else (0, 0, 0, 0)\n'
        "        Line:\n"
        "            points:\n"
        "                self.x, self.y + dp(16), \\\n"
        "                self.x + self.width, self.y + dp(16)\n"
        "            width: 1\n"
        "            dash_length: dp(3)\n"
        "            dash_offset: 2 if self.disabled else 0\n"
        "        # Active line.\n"
        "        Color:\n"
        "            rgba:\n"
        "                self._line_color_focus \\\n"
        '                if self.mode == "line" else (0, 0, 0, 0)\n'
        "        Rectangle:\n"
        "            size: self._underline_width, dp(2)\n"
        "            pos:\n"
        "                self.center_x - (self._underline_width / 2), \\\n"
        "                self.y + dp(16)\n"
        "        # Phase 280: rectangle モード用の周囲枠線。\n"
        "        # KivyMD 1.2.0 公式の canvas.after 「rectangle」グループは\n"
        "        # スタブライブラリに含まれていないため、自前で canvas.before に描画する。\n"
        "        # フォーカス時は ``line_color_focus`` で枠線をハイライトし、\n"
        "        # 「いまどのフィールドが選択中か」を視覚的に明示する。\n"
        "        # 通常時は ``line_color_normal`` (薄いグレー) で控えめに。\n"
        "        Color:\n"
        "            rgba: self.line_color_focus if self.focus else self.line_color_normal\n"
        "            group: 'rectangle_border'\n"
        "        Line:\n"
        "            points:\n"
        "                (\n"
        "                self.x, self.y, self.right, self.y,\n"
        "                self.right, self.top, self.x, self.top,\n"
        "                self.x, self.y\n"
        "                )\n"
        "            width: dp(1.2) if self.focus else dp(1)\n"
        "            close: True\n"
        "            group: 'rectangle_border'\n"
        "        # Hint text.\n"
        "        Color:\n"
        "            rgba: self._hint_text_color\n"
        "        Rectangle:\n"
        "            texture: self._hint_text_label.texture\n"
        "            size: self._hint_text_label.texture_size\n"
        "            pos:\n"
        "                self.x, \\\n"
        "                self.y + self.height - self._hint_y\n"
        "    # Phase 280: カーソル描画は ``_base.py`` の ``LabelledTextInput.on_kv_post``\n"
        "    # 内で Python コードから canvas.after に Color + Rectangle を追加し、\n"
        "    # ``cursor_color`` / ``cursor_pos`` / ``cursor_width`` / ``line_height``\n"
        "    # を ``bind`` して動的更新している。 KV rule での ``self.cursor_color``\n"
        "    # binding は初回評価時に TextInput デフォルトの ``[1, 0, 0, 1]``\n"
        "    # (赤) がキャッシュされる問題があったため、Python 側で明示的に\n"
        "    # bind する方式を採用。\n"
        "    # Phase 281: prefer Theme.DEFAULT_FONT over Roboto when the\n"
        "    # parent's font_name binding has not yet propagated.\n"
        "    font_name: root.font_name if root.font_name else Theme.DEFAULT_FONT\n"
        "    # Phase 280: 直接 ``foreground_color`` をテーマ由来ではなく\n"
        "    # ``Theme.TEXT_COLOR`` 固定に変更。KivyMD 1.2.0 の stub KV は元々\n"
        "    # ``theme_cls.on_primary_container_color`` (青) を返していたため、\n"
        "    # フォーカス時に文字がシアン色で描画される副作用があった。\n"
        "    # 派生 ``<LabelledTextInput>`` (popup_widgets.kv) の override だけに\n"
        "    # 頼るとタイミング次第で反映漏れが起きるため、MDTextField 直下で固定。\n"
        "    foreground_color: Theme.TEXT_COLOR\n"
        "    # Phase 280: フォーカス付きで MDTextField でテキストを選択すると\n"
        "    # KivyMD 1.2.0 が親 <MDTextField> の selection_color を\n"
        "    # 暗黙の ``[0.184, 0.655, 0.831, 0.5]`` (青 50% 透明) に戻し、\n"
        "    # パス部分選択時に「青文字で読みにくい」問題が発生する。\n"
        "    # 派生 ``<LabelledTextInput>`` 側でも override するが、\n"
        "    # タイミング次第で反映漏れが起きるため MDTextField 直下でも固定。\n"
        "    selection_color: [0, 0, 0, 0]\n"
        "    # Phase 280: カーソルは白 ``[1, 1, 1, 1]`` で固定。_box の暗い BOX_BACKGROUND_COLOR\n"
        "    # 背景とのコントラストで 2.5sp 幅の縦線として視認可能。\n"
        "    cursor_color: [1, 1, 1, 1]\n"
        '    font_size: "16sp"\n'
        '    padding: 0, "16dp", 0, "10dp"\n'
        "    multiline: False\n"
        "    size_hint_y: None\n"
        "    height: self.minimum_height\n"
        "\n"
        "<TextfieldLabel>\n"
        "    # Phase 281: removed the 'Roboto' fallback (no JP glyphs =\n"
        "    # tofu). Always prefer the parent's font_name, then fall back\n"
        "    # to Theme.DEFAULT_FONT (NotoSansJP).\n"
        "    font_name: root.font_name if root.font_name else Theme.DEFAULT_FONT\n"
        "    size_hint_x: None\n"
        "    width: self.texture_size[0]\n"
        "    shorten: True\n"
        '    shorten_from: "right"\n'
    ),
}


def _ensure_kv_stubs() -> str:
    """Create stub ``.kv`` files in a tempdir and return its path.

    The function is idempotent: subsequent calls return the same path
    without re-creating files.
    """
    global _stub_root
    if _stub_root is not None and os.path.isdir(_stub_root):
        return _stub_root

    _stub_root = tempfile.mkdtemp(prefix="kivymd_1_2_kv_stubs_")
    for relpath, body in STUB_KV.items():
        full = os.path.join(_stub_root, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body)

    def _cleanup() -> None:
        global _stub_root
        if _stub_root is not None:
            shutil.rmtree(_stub_root, ignore_errors=True)
            _stub_root = None

    atexit.register(_cleanup)
    return _stub_root


def ensure_kivymd_kv_stubs() -> str:
    """Patch ``kivymd.uix_path`` to point at the stub tempdir.

    Returns the new ``uix_path`` value. Idempotent.

    Raises:
        ImportError: if ``kivymd`` cannot be imported (very early call).
    """
    import kivymd  # noqa: WPS433 — lazy import is intentional

    stub_root = _ensure_kv_stubs()
    if kivymd.uix_path != stub_root:
        kivymd.uix_path = stub_root

    # Phase 280: TextInput._draw_selection() が ``self.selection_color``
    # のスナップショットを取って ``canvas.add(Color(*selection_color,
    # group='selection'))`` するため、``__setattr__`` 横取りで
    # ``selection_color`` を ``[0, 0, 0, 0]`` にしても、青い ``Color``
    # 命令が ``canvas`` に追加され続けてしまう。
    #
    # 確実に防ぐため ``_draw_selection`` を monkey patch して、
    # 内部で ``selection_color = [0, 0, 0, 0]`` を強制する
    # ``_patched_draw_selection`` に置換する。これでウィジェット個別
    # の ``__setattr__`` 横取りが効かないケース (キャッシュ古い /
    # 別経路) でも、TextInput 全体で青い選択ハイライトが出なくなる。
    #
    # このパッチは ``_draw_selection_lines`` 経由でも呼ばれるため、
    # 1 箇所 monkey patch すれば全 TextInput (派生含む) で適用される。
    from kivy.uix.textinput import TextInput

    if getattr(TextInput, "_katrain_selection_disabled", False):
        return stub_root  # 既にパッチ済み

    _original_draw_selection = TextInput._draw_selection

    def _katrain_patched_draw_selection(self, *args, **kwargs):
        # ``_draw_selection`` 呼び出し時に ``self.selection_color`` を
        # 強制的に ``[0, 0, 0, 0]`` (完全透明) にする。元の値は
        # 関数終了後に復元 (副作用を最小化)。
        original = self.selection_color
        self.selection_color = [0, 0, 0, 0]
        try:
            return _original_draw_selection(self, *args, **kwargs)
        finally:
            self.selection_color = original

    TextInput._draw_selection = _katrain_patched_draw_selection
    TextInput._katrain_selection_disabled = True

    return stub_root


# Convenience for the rare call site that wants the resolved path
# without forcing the import (e.g. unit tests that mock kivymd).
uix_path_override: str | None = None
