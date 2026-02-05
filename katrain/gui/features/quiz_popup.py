# katrain/gui/features/quiz_popup.py
#
# クイズポップアップ機能モジュール
#
# __main__.py から抽出したクイズポップアップ関連の関数を配置します。
# - do_quiz_popup: クイズ選択ポップアップの表示
# - format_points_loss: 損失ポイントの表示フォーマット
#
# Note: Kivy imports are deferred inside functions to allow
# importing this module in headless CI environment (Phase 101 fix).

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics
from katrain.core.constants import STATUS_INFO
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def format_points_loss(loss: float | None) -> str:
    """損失ポイントの表示フォーマット

    Args:
        loss: 損失ポイント（Noneの場合は不明として表示）

    Returns:
        フォーマット済み文字列
    """
    if loss is None:
        return i18n._("Points lost unknown")
    return i18n._("{loss:.1f} points lost").format(loss=loss)


def do_quiz_popup(
    ctx: FeatureContext,
    start_quiz_session_fn: Callable[[list[eval_metrics.QuizItem]], None],
    update_state_fn: Callable[[], None],
) -> None:
    """クイズ選択ポップアップを表示

    Args:
        ctx: FeatureContext providing game, controls
        start_quiz_session_fn: クイズセッション開始コールバック
        update_state_fn: UI状態更新コールバック
    """
    # Lazy imports to avoid Kivy initialization in headless CI
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.scrollview import ScrollView

    from katrain.gui.popups import I18NPopup
    from katrain.gui.theme import Theme
    from katrain.gui.widgets.factory import Button, Label

    if not ctx.game:
        return

    # Use QuizConfig so we can add presets later.
    cfg = getattr(eval_metrics, "QUIZ_CONFIG_DEFAULT", None)
    if cfg is None:
        # Fallback for safety.
        loss_threshold = eval_metrics.DEFAULT_QUIZ_LOSS_THRESHOLD
        limit = eval_metrics.DEFAULT_QUIZ_ITEM_LIMIT
    else:
        loss_threshold = cfg.loss_threshold
        limit = cfg.limit

    quiz_items = ctx.game.get_quiz_items(loss_threshold=loss_threshold, limit=limit)

    popup_content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

    if quiz_items:
        header_text = i18n._(
            "Review the worst moves on the main line.\n"
            "Showing up to {limit} moves with loss > {loss:.1f} points.\n"
            "Click a row to jump to the position before the move."
        ).format(limit=limit, loss=loss_threshold)
    else:
        header_text = i18n._("No moves with loss greater than {loss:.1f} points were found on the main line.").format(
            loss=loss_threshold
        )

    header_label = Label(
        text=header_text,
        halign="left",
        valign="top",
        size_hint_y=None,
        height=dp(70),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    header_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, None)))
    popup_content.add_widget(header_label)

    scroll = ScrollView(size_hint=(1, 1))
    items_layout = BoxLayout(
        orientation="vertical",
        spacing=dp(6),
        size_hint_y=None,
    )
    items_layout.bind(minimum_height=items_layout.setter("height"))

    def jump_to_move(move_number: int) -> None:
        if ctx.game is None:
            ctx.controls.set_status("No game loaded.", STATUS_INFO)
            return
        node = ctx.game.get_main_branch_node_before_move(move_number)
        if node is None:
            ctx.controls.set_status(f"Could not navigate to move {move_number}.", STATUS_INFO)
            return
        ctx.game.set_current_node(node)
        update_state_fn()

    for item in quiz_items:
        color_label = "Black" if item.player == "B" else "White" if item.player == "W" else "?"
        btn = Button(
            text=f"Move {item.move_number} ({color_label}), loss: {item.loss:.1f} points",
            size_hint_y=None,
            height=dp(44),
            background_color=Theme.BOX_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        btn.bind(on_release=lambda _btn, mv=item.move_number: jump_to_move(mv))
        items_layout.add_widget(btn)

    scroll.add_widget(items_layout)
    popup_content.add_widget(scroll)

    buttons_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))
    start_button = Button(
        text=i18n._("Start quiz"),
        size_hint=(0.5, None),
        height=dp(48),
        disabled=not quiz_items,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    close_button = Button(
        text=i18n._("Close"),
        size_hint=(0.5, None),
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    buttons_layout.add_widget(start_button)
    buttons_layout.add_widget(close_button)
    popup_content.add_widget(buttons_layout)

    popup = I18NPopup(
        title_key="Generate quiz (beta)",
        size=[dp(520), dp(620)],
        content=popup_content,
    ).__self__
    # 右下の分析パネルを残すため、右上に寄せて高さを抑える
    popup.size_hint = (0.38, 0.55)
    popup.pos_hint = {"right": 0.99, "top": 0.99}
    close_button.bind(on_release=lambda *_args: popup.dismiss())

    def start_quiz(*_args: Any) -> None:
        popup.dismiss()
        start_quiz_session_fn(quiz_items)

    start_button.bind(on_release=start_quiz)
    popup.open()
