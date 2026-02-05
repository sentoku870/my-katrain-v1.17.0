# katrain/gui/features/quiz_session.py
#
# クイズセッション機能モジュール
#
# __main__.py から抽出したクイズセッション関連の関数を配置します。
# - start_quiz_session: クイズセッションの開始と問題表示
#
# Note: Kivy imports are deferred inside the function to allow
# patching this module in headless CI environment (Phase 101 fix).

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from katrain.core import eval_metrics
from katrain.core.constants import STATUS_INFO
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def start_quiz_session(
    ctx: "FeatureContext",
    quiz_items: list[eval_metrics.QuizItem],
    format_points_loss_fn: Callable[[float | None], str],
    update_state_fn: Callable[[], None],
) -> None:
    """クイズセッションを開始

    Args:
        ctx: FeatureContext providing game, controls
        quiz_items: クイズアイテムのリスト
        format_points_loss_fn: 損失ポイントフォーマット関数
        update_state_fn: UI状態更新コールバック
    """
    # Lazy imports to avoid Kivy initialization in headless CI
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from katrain.gui.widgets.factory import Button, Label
    from kivy.uix.scrollview import ScrollView

    from katrain.gui.popups import I18NPopup
    from katrain.gui.theme import Theme

    if not ctx.game:
        return
    if not quiz_items:
        ctx.controls.set_status(i18n._("No quiz items to show."), STATUS_INFO)
        return

    questions = ctx.game.build_quiz_questions(quiz_items)

    content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))

    question_label = Label(
        text="",
        halign="left",
        valign="middle",
        size_hint_y=None,
        height=dp(60),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    question_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, None)))
    content.add_widget(question_label)

    choices_layout = BoxLayout(
        orientation="vertical",
        spacing=dp(6),
        size_hint_y=None,
    )
    choices_layout.bind(minimum_height=choices_layout.setter("height"))
    scroll = ScrollView(size_hint=(1, 1))
    scroll.add_widget(choices_layout)
    content.add_widget(scroll)

    result_label = Label(
        text="",
        halign="left",
        valign="top",
        size_hint_y=None,
        height=dp(70),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    result_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, None)))
    content.add_widget(result_label)

    nav_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))
    prev_button = Button(
        text=i18n._("Prev"),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    next_button = Button(
        text=i18n._("Next"),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    close_button = Button(
        text=i18n._("Close"),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    nav_layout.add_widget(prev_button)
    nav_layout.add_widget(next_button)
    nav_layout.add_widget(close_button)
    content.add_widget(nav_layout)

    popup = I18NPopup(
        title_key="Quiz mode (beta)",
        size=[dp(540), dp(640)],
        content=content,
    ).__self__
    # 右下の分析パネルを残すため、右上に寄せて高さを抑える
    popup.size_hint = (0.38, 0.55)
    popup.pos_hint = {"right": 0.99, "top": 0.99}

    answers: dict[int, str] = {}
    current_index = 0
    total_questions = len(questions)

    def on_select(choice: eval_metrics.QuizChoice) -> None:
        nonlocal answers, current_index
        question = questions[current_index]

        # Backward-compatible: older QuizQuestion may not have played_loss/played_move
        item = getattr(question, "item", None)
        best_move = getattr(question, "best_move", None)
        played_loss_q = getattr(question, "played_loss", None)
        played_loss_item = getattr(item, "loss", None)
        played_loss = played_loss_q if played_loss_q is not None else played_loss_item

        played_move_q = getattr(question, "played_move", None)
        played_move_item = getattr(item, "played_move", None)
        played_move = played_move_q if played_move_q is not None else played_move_item

        def display_move(move_id: str | None) -> str:
            if move_id is None:
                return i18n._("Unknown move")
            return move_id or i18n._("Pass")

        loss_text = format_points_loss_fn(choice.points_lost)
        played_loss_text = format_points_loss_fn(played_loss)
        is_best = best_move is not None and choice.move == best_move

        lines = [
            i18n._("Correct!") if is_best else i18n._("Incorrect"),
            i18n._("Best move: {move}").format(
                move=display_move(best_move)
            ),
            i18n._("Selected move loss: {loss_text}").format(
                loss_text=loss_text
            ),
            i18n._("Played move {move} loss: {loss_text}").format(
                move=display_move(played_move),
                loss_text=played_loss_text,
            ),
        ]

        if choice.points_lost is not None and played_loss is not None:
            delta = choice.points_lost - played_loss
            lines.append(
                i18n._("Delta vs played: {delta:+.1f} points").format(delta=delta)
            )

        text = "\n".join(lines)
        answers[current_index] = text
        result_label.text = text

    def show_question() -> None:
        nonlocal current_index
        if not questions:
            ctx.controls.set_status(i18n._("No analysis data for this position."), STATUS_INFO)
            popup.dismiss()
            return

        question = questions[current_index]
        color_label = "B" if question.item.player == "B" else "W" if question.item.player == "W" else "?"
        question_label.text = i18n._("Question {idx}/{total}: Move {move} ({player})").format(
            idx=current_index + 1,
            total=total_questions,
            move=question.item.move_number,
            player=color_label,
        )

        choices_layout.clear_widgets()
        result_label.text = answers.get(current_index, "")

        node_before = question.node_before_move
        if node_before is not None and ctx.game is not None:
            ctx.game.set_current_node(node_before)
            update_state_fn()

        if not question.has_analysis:
            no_data_label = Label(
                text=i18n._("No analysis data for this position."),
                halign="center",
                valign="middle",
                size_hint_y=None,
                height=dp(80),
                color=Theme.TEXT_COLOR,
                font_name=Theme.DEFAULT_FONT,
            )
            no_data_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, None)))
            choices_layout.add_widget(no_data_label)
        else:
            for choice in question.choices:
                btn = Button(
                    text=choice.move or i18n._("Pass"),
                    size_hint_y=None,
                    height=dp(44),
                    background_color=Theme.BOX_BACKGROUND_COLOR,
                    color=Theme.TEXT_COLOR,
                    font_name=Theme.DEFAULT_FONT,
                )
                btn.bind(on_release=lambda _btn, c=choice: on_select(c))
                choices_layout.add_widget(btn)

        prev_button.disabled = current_index <= 0
        next_button.disabled = current_index >= total_questions - 1

    def go_next(delta: int) -> None:
        nonlocal current_index
        new_index = current_index + delta
        new_index = max(0, min(total_questions - 1, new_index))
        if new_index != current_index:
            current_index = new_index
            show_question()

    prev_button.bind(on_release=lambda *_args: go_next(-1))
    next_button.bind(on_release=lambda *_args: go_next(1))
    close_button.bind(on_release=lambda *_args: popup.dismiss())

    show_question()
    popup.open()
