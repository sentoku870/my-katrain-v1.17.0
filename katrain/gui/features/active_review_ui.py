# katrain/gui/features/active_review_ui.py
"""Active Review Mode UI components.

Provides:
- show_guess_feedback(): Display feedback popup after user guess (Phase 93 + 94)
"""

from typing import TYPE_CHECKING, Any, Callable, Optional

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

from katrain.core.lang import i18n
from katrain.core.study.active_review import GuessEvaluation, GuessGrade
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui


# Grade to i18n key mapping
GRADE_I18N_KEYS = {
    GuessGrade.PERFECT: "active_review:grade:perfect",
    GuessGrade.EXCELLENT: "active_review:grade:excellent",
    GuessGrade.GOOD: "active_review:grade:good",
    GuessGrade.SLACK: "active_review:grade:slack",
    GuessGrade.BLUNDER: "active_review:grade:blunder",
    GuessGrade.NOT_IN_CANDIDATES: "active_review:grade:not_in_candidates",
}

# Grade to color mapping (RGB tuples)
GRADE_COLORS = {
    GuessGrade.PERFECT: (0.2, 0.8, 0.2, 1),  # Green
    GuessGrade.EXCELLENT: (0.3, 0.7, 0.3, 1),  # Light green
    GuessGrade.GOOD: (0.5, 0.7, 0.3, 1),  # Yellow-green
    GuessGrade.SLACK: (0.8, 0.6, 0.2, 1),  # Orange
    GuessGrade.BLUNDER: (0.8, 0.2, 0.2, 1),  # Red
    GuessGrade.NOT_IN_CANDIDATES: (0.6, 0.4, 0.2, 1),  # Brown
}


def _format_score_loss(loss: float | None) -> str:
    """Format score loss for display.

    Args:
        loss: Score loss value, or None for NOT_IN_CANDIDATES

    Returns:
        Formatted string
    """
    if loss is None:
        return i18n._("active_review:feedback:score_loss_na")
    return i18n._("active_review:feedback:score_loss").format(loss=loss)


def show_guess_feedback(
    katrain: "KaTrainGui",
    evaluation: GuessEvaluation,
    allow_retry: bool = False,
    on_retry: Optional[Callable[[], None]] = None,
    on_hint_request: Optional[Callable[[], Optional[str]]] = None,
) -> None:
    """Show feedback popup for user's guess.

    Args:
        katrain: KaTrainGui instance
        evaluation: GuessEvaluation result from ActiveReviewer
        allow_retry: If True, show Retry and Hint buttons (Phase 94)
        on_retry: Callback when Retry button is pressed
        on_hint_request: Callback when Hint button is pressed
            - Returns hint string to display
            - Returns None to show "no hint available" message
    """
    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(15))

    # Grade label (large, colored)
    grade_key = GRADE_I18N_KEYS.get(evaluation.grade, "active_review:grade:good")
    grade_text = i18n._(grade_key)
    grade_color = GRADE_COLORS.get(evaluation.grade, Theme.TEXT_COLOR)

    grade_label = Label(
        text=grade_text,
        font_size=dp(32),
        bold=True,
        color=grade_color,
        size_hint_y=None,
        height=dp(50),
    )
    content.add_widget(grade_label)

    # Details
    details_layout = BoxLayout(orientation="vertical", spacing=dp(5), size_hint_y=None)
    details_layout.bind(minimum_height=details_layout.setter("height"))

    # Your move
    your_move_text = i18n._("active_review:feedback:your_move").format(
        move=evaluation.user_move
    )
    your_move_label = Label(
        text=your_move_text,
        color=Theme.TEXT_COLOR,
        size_hint_y=None,
        height=dp(25),
        halign="left",
    )
    your_move_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, None)))
    details_layout.add_widget(your_move_label)

    # AI best
    ai_best_text = i18n._("active_review:feedback:ai_best").format(
        move=evaluation.ai_best_move
    )
    ai_best_label = Label(
        text=ai_best_text,
        color=Theme.TEXT_COLOR,
        size_hint_y=None,
        height=dp(25),
        halign="left",
    )
    ai_best_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, None)))
    details_layout.add_widget(ai_best_label)

    # Score loss
    loss_text = _format_score_loss(evaluation.score_loss)
    loss_label = Label(
        text=loss_text,
        color=Theme.TEXT_COLOR,
        size_hint_y=None,
        height=dp(25),
        halign="left",
    )
    loss_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, None)))
    details_layout.add_widget(loss_label)

    # Matches game move indicator
    if evaluation.matches_game_move:
        matches_text = i18n._("active_review:feedback:matches_game")
        matches_label = Label(
            text=matches_text,
            color=(0.4, 0.7, 0.4, 1),  # Light green
            size_hint_y=None,
            height=dp(25),
            halign="left",
        )
        matches_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, None)))
        details_layout.add_widget(matches_label)

    content.add_widget(details_layout)

    # Hint display area (initially empty, filled when hint is requested)
    hint_label = Label(
        text="",
        color=Theme.INFO_COLOR if hasattr(Theme, "INFO_COLOR") else (0.4, 0.6, 0.8, 1),
        size_hint_y=None,
        height=dp(0),  # Initially hidden
        halign="left",
        text_size=(dp(280), None),
    )
    hint_label.bind(texture_size=lambda lbl, size: setattr(lbl, "height", size[1] if lbl.text else 0))
    content.add_widget(hint_label)

    # Calculate popup height based on whether buttons will be shown
    popup_height = dp(280) if not allow_retry else dp(340)

    # Create popup
    popup = I18NPopup(
        title_key="active_review:title",
        size=[dp(320), popup_height],
        content=content,
        auto_dismiss=True,
    ).__self__

    # Position at top-right to avoid blocking board
    popup.size_hint = (None, None)
    popup.pos_hint = {"right": 0.98, "top": 0.98}

    # Add Retry/Hint buttons if allowed (Phase 94)
    if allow_retry:
        button_layout = BoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            size_hint_y=None,
            height=dp(40),
        )

        # Retry button
        retry_btn = Button(
            text=i18n._("active_review:button:retry"),
            size_hint_x=0.5,
        )

        def on_retry_pressed(instance: Any) -> None:
            popup.dismiss()
            if on_retry:
                on_retry()

        retry_btn.bind(on_press=on_retry_pressed)
        button_layout.add_widget(retry_btn)

        # Hint button
        hint_btn = Button(
            text=i18n._("active_review:button:hint"),
            size_hint_x=0.5,
        )

        def on_hint_pressed(instance: Any) -> None:
            # Request hint from callback
            hint_text = None
            if on_hint_request:
                hint_text = on_hint_request()

            if hint_text:
                hint_label.text = hint_text
            else:
                hint_label.text = i18n._("active_review:hint:unavailable")

            # Disable hint button after use
            hint_btn.disabled = True

        hint_btn.bind(on_press=on_hint_pressed)
        button_layout.add_widget(hint_btn)

        content.add_widget(button_layout)

    popup.open()

    # Auto-dismiss after 3 seconds for good grades (only if no retry buttons)
    if not allow_retry and evaluation.grade in (GuessGrade.PERFECT, GuessGrade.EXCELLENT, GuessGrade.GOOD):
        Clock.schedule_once(lambda dt: popup.dismiss(), 3.0)
