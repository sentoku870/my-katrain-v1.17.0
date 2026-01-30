# katrain/gui/features/active_review_ui.py
"""Active Review Mode UI components.

Provides:
- show_guess_feedback(): Display feedback popup after user guess
"""

from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
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


def _format_score_loss(loss):
    """Format score loss for display.

    Args:
        loss: Score loss value, or None for NOT_IN_CANDIDATES

    Returns:
        Formatted string
    """
    if loss is None:
        return i18n._("active_review:feedback:score_loss_na")
    return i18n._("active_review:feedback:score_loss").format(loss=loss)


def show_guess_feedback(katrain: "KaTrainGui", evaluation: GuessEvaluation) -> None:
    """Show feedback popup for user's guess.

    Args:
        katrain: KaTrainGui instance
        evaluation: GuessEvaluation result from ActiveReviewer
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

    # Create popup
    popup = I18NPopup(
        title_key="active_review:title",
        size=[dp(320), dp(280)],
        content=content,
        auto_dismiss=True,
    ).__self__

    # Position at top-right to avoid blocking board
    popup.size_hint = (None, None)
    popup.pos_hint = {"right": 0.98, "top": 0.98}

    popup.open()

    # Auto-dismiss after 3 seconds for good grades
    if evaluation.grade in (GuessGrade.PERFECT, GuessGrade.EXCELLENT, GuessGrade.GOOD):
        Clock.schedule_once(lambda dt: popup.dismiss(), 3.0)
