"""Settings popup reset tab action (Phase 173).

Extracted from ``katrain.gui.features.settings_popup`` so the orchestrator
file can stay focused on popup layout and tab wiring.

Public surface (kept intact for backward compatibility):

- ``_reset_tab_settings`` — confirms with the user and restores default
  values for the keys associated with a tab (``analysis``, ``export``).

This helper still imports Kivy widgets lazily inside the function body so
importing this module at package load time does not initialise Kivy.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.common.settings_export import TAB_RESET_KEYS, get_default_value
from katrain.core.constants import STATUS_INFO
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext
    from katrain.gui.widgets.factory import Popup


def _reset_tab_settings(
    ctx: "FeatureContext",
    tab_id: str,
    popup: "Popup",
    on_reset_complete: Callable[[], None],
) -> None:
    """タブの設定をデフォルトに戻す (Phase 27 / Phase 173 でファイル分割)

    Args:
        ctx: FeatureContext providing config, save_config, controls
        tab_id: タブID ("analysis", "export")
        popup: 親ポップアップ（リセット後に閉じてリロード用）
        on_reset_complete: リセット完了後に呼ばれるコールバック
    """
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout

    from katrain.gui.popups import I18NPopup
    from katrain.gui.theme import Theme
    from katrain.gui.widgets.factory import Button, Label

    keys = TAB_RESET_KEYS.get(tab_id, [])
    if not keys:
        logging.info("[settings_popup_reset] No reset keys for tab_id=%r; skipping", tab_id)
        return

    # リセット対象のキー名を表示用に整形
    target_names = [key for _, key in keys]
    tab_display_name = i18n._(f"mykatrain:settings:tab_{tab_id}")

    # 確認ダイアログ
    confirm_layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
    message_label = Label(
        text=i18n._("mykatrain:settings:reset_confirm_message").format(
            tab=tab_display_name, targets=", ".join(target_names)
        ),
        halign="center",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    message_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width * 0.9, None)))
    confirm_layout.add_widget(message_label)

    buttons_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(40))
    confirm_btn = Button(
        text=i18n._("OK"),
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    cancel_btn = Button(
        text=i18n._("Cancel"),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    buttons_layout.add_widget(confirm_btn)
    buttons_layout.add_widget(cancel_btn)
    confirm_layout.add_widget(buttons_layout)

    confirm_popup = I18NPopup(
        title_key="mykatrain:settings:reset_confirm_title",
        size=[dp(450), dp(200)],
        content=confirm_layout,
    ).__self__

    def do_reset(*_args: Any) -> None:
        """実際のリセット処理"""
        affected_sections: set[str] = set()

        for section, key in keys:
            default_val = get_default_value(section, key)
            if default_val is not None:
                # config section を取得または作成
                section_config = ctx.config(section) or {}
                section_config[key] = default_val
                ctx.set_config_section(section, section_config)
                affected_sections.add(section)

        # 影響セクションのみ保存
        for section in affected_sections:
            ctx.save_config(section)

        ctx.controls.set_status(
            i18n._("mykatrain:settings:reset_success").format(tab=tab_display_name),
            STATUS_INFO,
        )
        confirm_popup.dismiss()

        # 設定ポップアップをリロード
        popup.dismiss()
        on_reset_complete()

    confirm_btn.bind(on_release=do_reset)
    cancel_btn.bind(on_release=lambda *_args: confirm_popup.dismiss())
    confirm_popup.open()
