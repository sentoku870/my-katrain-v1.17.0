# katrain/gui/features/resign_hint_popup.py
#
# Phase 16: Resign Hint Popup
#
# Displays a popup when the resign condition is met (low winrate for
# consecutive moves). The popup suggests the user consider resigning.

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from katrain.core.lang import i18n
from katrain.core.leela.logic import ResignConditionResult
from katrain.gui.kivyutils import SizedRectangleButton
from katrain.gui.popups import I18NPopup


def show_resign_hint_popup(katrain, result: ResignConditionResult) -> None:
    """Show resign hint popup (must be called on UI thread).

    Args:
        katrain: KaTrainGui instance
        result: ResignConditionResult with winrate info
    """
    content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

    # i18n variables: winrate_pct (0-100 scale), moves (count)
    message = i18n._("leela:resign_hint:message").format(
        winrate_pct=int(result.winrate_pct),
        moves=result.consecutive_count
    )
    content.add_widget(Label(
        text=message,
        size_hint_y=None,
        height=dp(60),
        halign="center",
        valign="middle",
    ))
    # Ensure text wraps properly
    content.children[0].bind(size=content.children[0].setter('text_size'))

    ok_btn = SizedRectangleButton(
        text=i18n._("leela:resign_hint:ok"),
        size_hint_y=None,
        height=dp(40),
    )
    content.add_widget(ok_btn)

    popup = I18NPopup(
        title_key="leela:resign_hint:title",
        content=content,
        size_hint=(0.6, 0.4),
    )
    ok_btn.bind(on_release=popup.dismiss)
    popup.open()


def schedule_resign_hint_popup(katrain, result: ResignConditionResult) -> None:
    """Schedule resign hint popup on UI thread (for callbacks from non-UI threads).

    Args:
        katrain: KaTrainGui instance
        result: ResignConditionResult with winrate info
    """
    Clock.schedule_once(lambda dt: show_resign_hint_popup(katrain, result))
