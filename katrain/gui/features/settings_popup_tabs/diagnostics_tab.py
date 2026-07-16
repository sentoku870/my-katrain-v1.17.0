"""Diagnostics tab (Tab 4) for the myKatrain settings popup.

Phase 230-D: 診断情報メニューを settings popup の第4タブに統合。
ユーザーは myKatrain 設定の「診断」タブからシステム情報の確認、
バグレポート (ZIP) の生成、情報のクリップボードコピーが可能。

収集ロジックと表示ウィジェットは ``diagnostics_popup.py`` の既存関数
(``_collect_diagnostics`` / ``_build_info_display``) を再利用し、
ZIP 生成・コピー処理も同じく既存の ``_on_generate_zip`` /
``_on_copy_info`` を parent_popup=None で呼び出す。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView

from katrain.core.lang import i18n
from katrain.gui.features.diagnostics_popup import (
    _build_info_display,
    _collect_diagnostics,
    _on_copy_info,
    _on_generate_zip,
)
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button

if TYPE_CHECKING:
    from katrain.gui.features.settings_popup_state import _SettingsPopupContext


def _build_diagnostics_tab(state: _SettingsPopupContext) -> BoxLayout:
    """Build the Diagnostics tab content (Tab 4).

    Phase 230-D: メニューの「診断情報」を settings のタブに統合。

    Args:
        state: Shared popup state (provides ``ctx`` for diagnostics collection).

    Returns:
        BoxLayout containing a scrollable info display + action buttons.
        Does NOT return a reset button (diagnostics is read-only).
    """
    inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))

    # Collect diagnostics bundle (system / KataGo / app info).
    bundle = _collect_diagnostics(state.ctx)

    # Scrollable info display — reuses the same builder as the standalone
    # popup so the rendering is identical.
    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(8))
    info_content = _build_info_display(bundle)
    scroll.add_widget(info_content)
    inner.add_widget(scroll)

    # Action buttons: Generate Bug Report + Copy Info.
    # Uses the themed factory Button (same style as other settings tabs)
    # rather than the raw ``kivy.uix.button.Button`` the standalone
    # popup used. Phase 230-D visual consistency improvement.
    button_box = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(48),
        spacing=dp(10),
    )

    generate_btn = Button(
        text=i18n._("Generate Bug Report"),
        size_hint_x=0.5,
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    copy_btn = Button(
        text=i18n._("Copy Info"),
        size_hint_x=0.5,
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )

    # Wire buttons: parent_popup=None so the settings popup is NOT
    # dismissed when the ZIP is generated (the standalone popup used
    # dismiss + success popup; the tab just shows the success popup).
    generate_btn.bind(
        on_release=lambda btn: _on_generate_zip(state.ctx, bundle, btn, None)
    )
    copy_btn.bind(
        on_release=lambda btn: _on_copy_info(state.ctx, bundle, btn)
    )

    button_box.add_widget(generate_btn)
    button_box.add_widget(copy_btn)
    inner.add_widget(button_box)

    return inner
