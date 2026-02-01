# katrain/gui/features/active_review_summary.py
"""Active Review Summary UI (Phase 94).

Provides:
- show_session_summary(): Display session results popup
- format_summary_for_clipboard(): Format summary as Markdown for LLM coaching
"""

from typing import TYPE_CHECKING, Any

from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from katrain.core.lang import i18n
from katrain.core.study.review_session import SessionSummary
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui


def format_summary_for_clipboard(summary: SessionSummary) -> str:
    """Format session summary as Markdown for LLM coaching.

    Args:
        summary: SessionSummary from ReviewSession

    Returns:
        Markdown-formatted string
    """
    lines = [
        "# Active Review Session Summary",
        "",
        f"Total Guesses: {summary.total_guesses}",
        f"- Perfect (AI Best): {summary.perfect_count}",
        f"- Excellent: {summary.excellent_count}",
        f"- Good: {summary.good_count}",
        f"- Slack: {summary.slack_count}",
        f"- Blunder: {summary.blunder_count}",
        f"- Unusual: {summary.not_in_candidates_count}",
        "",
        f"AI Best Match Rate: {summary.ai_best_match_rate:.1f}%",
        f"Game Move Match Rate: {summary.game_move_match_rate:.1f}%",
    ]

    # Average score loss
    if summary.average_score_loss is not None:
        lines.append(f"Average Score Loss: {summary.average_score_loss:.2f}")
    else:
        lines.append("Average Score Loss: N/A")

    # Worst misses
    if summary.worst_misses:
        lines.append("")
        lines.append("Worst Misses:")
        for i, result in enumerate(summary.worst_misses, 1):
            loss = result.score_loss if result.score_loss is not None else "N/A"
            lines.append(f"  {i}. Move {result.move_number}: {result.user_move} (loss: {loss})")

    # Retry/Hint stats
    if summary.total_retries > 0 or summary.hints_used_count > 0:
        lines.append("")
        lines.append(f"Retries Used: {summary.total_retries}")
        lines.append(f"Hints Used: {summary.hints_used_count}")

    return "\n".join(lines)


def show_session_summary(katrain: "KaTrainGui", summary: SessionSummary) -> None:
    """Show session results popup.

    Args:
        katrain: KaTrainGui instance
        summary: SessionSummary from ReviewSession
    """
    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(15))

    # Title
    title_label = Label(
        text=i18n._("active_review:summary:title"),
        font_size=dp(24),
        bold=True,
        color=Theme.TEXT_COLOR,
        size_hint_y=None,
        height=dp(40),
    )
    content.add_widget(title_label)

    # Stats in scrollable area
    scroll = ScrollView(size_hint=(1, 1))
    stats_layout = BoxLayout(orientation="vertical", spacing=dp(5), size_hint_y=None)
    stats_layout.bind(minimum_height=stats_layout.setter("height"))

    # Build stats text using i18n
    stats_text = i18n._("active_review:summary:stats").format(
        total=summary.total_guesses,
        perfect=summary.perfect_count,
        excellent=summary.excellent_count,
        good=summary.good_count,
        slack=summary.slack_count,
        blunder=summary.blunder_count,
        unusual=summary.not_in_candidates_count,
    )

    # Format average loss
    avg_loss = (
        f"{summary.average_score_loss:.2f}"
        if summary.average_score_loss is not None
        else "N/A"
    )

    rates_text = i18n._("active_review:summary:rates").format(
        ai_match=summary.ai_best_match_rate,
        game_match=summary.game_move_match_rate,
        avg_loss=avg_loss,
    )

    # Stats label
    stats_label = Label(
        text=stats_text,
        color=Theme.TEXT_COLOR,
        size_hint_y=None,
        halign="left",
        valign="top",
    )
    stats_label.bind(
        width=lambda lbl, w: setattr(lbl, "text_size", (w - dp(10), None))
    )
    stats_label.bind(
        texture_size=lambda lbl, size: setattr(lbl, "height", size[1] + dp(10))
    )
    stats_layout.add_widget(stats_label)

    # Rates label
    rates_label = Label(
        text=rates_text,
        color=Theme.TEXT_COLOR,
        size_hint_y=None,
        halign="left",
        valign="top",
    )
    rates_label.bind(
        width=lambda lbl, w: setattr(lbl, "text_size", (w - dp(10), None))
    )
    rates_label.bind(
        texture_size=lambda lbl, size: setattr(lbl, "height", size[1] + dp(10))
    )
    stats_layout.add_widget(rates_label)

    scroll.add_widget(stats_layout)
    content.add_widget(scroll)

    # Copy button
    copy_btn = Button(
        text=i18n._("active_review:button:copy_summary"),
        size_hint_y=None,
        height=dp(40),
    )

    # Store popup reference for status update
    popup_ref = {"popup": None}

    def on_copy_pressed(instance: Any) -> None:
        clipboard_text = format_summary_for_clipboard(summary)
        Clipboard.copy(clipboard_text)
        # Show confirmation
        instance.text = i18n._("active_review:copied")
        # Reset button text after delay
        from kivy.clock import Clock

        Clock.schedule_once(
            lambda dt: setattr(instance, "text", i18n._("active_review:button:copy_summary")),
            2.0,
        )

    copy_btn.bind(on_press=on_copy_pressed)
    content.add_widget(copy_btn)

    # Create popup
    popup = I18NPopup(
        title_key="active_review:summary:popup_title",
        size=[dp(350), dp(400)],
        content=content,
        auto_dismiss=True,
    ).__self__

    popup_ref["popup"] = popup

    # Position at center
    popup.size_hint = (None, None)
    popup.pos_hint = {"center_x": 0.5, "center_y": 0.5}

    popup.open()
