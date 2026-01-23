"""Skill radar popup for 5-axis visualization."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem

from katrain.core.analysis.skill_radar import (
    MIN_MOVES_FOR_RADAR,
    RadarMetrics,
    SkillTier,
    compute_radar_from_moves,
)
from katrain.core.constants import OUTPUT_ERROR
from katrain.core.lang import i18n
from katrain.gui.theme import Theme
from katrain.gui.widgets.radar_chart import RadarChartWidget
from katrain.gui.widgets.radar_geometry import AXIS_ORDER, tier_to_color

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext

TIER_I18N = {
    SkillTier.TIER_1: "radar:tier-1",
    SkillTier.TIER_2: "radar:tier-2",
    SkillTier.TIER_3: "radar:tier-3",
    SkillTier.TIER_4: "radar:tier-4",
    SkillTier.TIER_5: "radar:tier-5",
    SkillTier.TIER_UNKNOWN: "radar:tier-unknown",
}


def show_skill_radar_popup(ctx: "FeatureContext") -> None:
    """Show skill radar popup (main entry point)."""
    Clock.schedule_once(lambda _: _show_impl(ctx), 0)


def _show_impl(ctx: "FeatureContext") -> None:
    """Implementation of skill radar popup display."""
    game = getattr(ctx, "game", None)
    if not game:
        ctx.log(i18n._("radar:no-game"), OUTPUT_ERROR)
        return

    bx, by = game.board_size
    if bx != 19 or by != 19:
        ctx.log(i18n._("radar:not-19x19"), OUTPUT_ERROR)
        return

    try:
        snapshot = game.build_eval_snapshot()
    except Exception as e:
        ctx.log(f"{i18n._('radar:build-error')}: {e}", OUTPUT_ERROR)
        return

    if not snapshot or not snapshot.moves:
        ctx.log(i18n._("radar:no-data"), OUTPUT_ERROR)
        return

    radar: Dict[str, Optional[RadarMetrics]] = {}
    for p in ("B", "W"):
        player_moves = [m for m in snapshot.moves if m.player == p]
        if len(player_moves) >= MIN_MOVES_FOR_RADAR:
            try:
                radar[p] = compute_radar_from_moves(snapshot.moves, player=p)
            except Exception as e:
                ctx.log(f"{i18n._('radar:calc-error')} ({p}): {e}", OUTPUT_ERROR)
                radar[p] = None
        else:
            radar[p] = None

    if not any(radar.values()):
        ctx.log(i18n._("radar:insufficient-moves"), OUTPUT_ERROR)
        return

    _build_popup(radar)


def _build_popup(radar: Dict[str, Optional[RadarMetrics]]) -> None:
    """Build and display the popup."""
    content = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(8))

    tabbed = TabbedPanel(do_default_tab=False, tab_pos="top_mid")
    for p, name in [
        ("B", i18n._("mykatrain:batch:filter_black")),
        ("W", i18n._("mykatrain:batch:filter_white")),
    ]:
        tab = TabbedPanelItem(text=name)
        r = radar.get(p)
        tab.add_widget(_player_content(r) if r else _no_data_content())
        tabbed.add_widget(tab)

    if tabbed.tab_list:
        tabbed.default_tab = tabbed.tab_list[0]  # Black first

    content.add_widget(tabbed)

    close = Button(
        text=i18n._("Close"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(1, None),
        height=dp(40),
    )
    content.add_widget(close)

    popup = Popup(
        title=i18n._("radar:title"),
        content=content,
        size_hint=(0.75, 0.8),
    )
    close.bind(on_release=popup.dismiss)
    popup.open()


def _player_content(r: RadarMetrics) -> BoxLayout:
    """Create player radar content."""
    layout = BoxLayout(orientation="vertical", spacing=dp(8))

    chart = RadarChartWidget(size_hint=(1, 0.75))
    chart.scores = {
        "opening": r.opening,
        "fighting": r.fighting,
        "endgame": r.endgame,
        "stability": r.stability,
        "awareness": r.awareness,
    }
    chart.tiers = {
        "opening": r.opening_tier.value,
        "fighting": r.fighting_tier.value,
        "endgame": r.endgame_tier.value,
        "stability": r.stability_tier.value,
        "awareness": r.awareness_tier.value,
    }
    chart.overall_tier = r.overall_tier.value
    layout.add_widget(chart)

    layout.add_widget(_summary(r))
    return layout


def _summary(r: RadarMetrics) -> BoxLayout:
    """Create summary section with overall tier and weak areas."""
    layout = BoxLayout(orientation="vertical", size_hint=(1, 0.25), padding=dp(5))

    tier_text = i18n._(TIER_I18N.get(r.overall_tier, "radar:tier-unknown"))
    tier_color = tier_to_color(r.overall_tier.value)

    overall = Label(
        text=f"[b]{i18n._('radar:overall')}:[/b] {tier_text}",
        markup=True,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(15),
        color=tier_color,
        size_hint_y=None,
        height=dp(28),
    )
    layout.add_widget(overall)

    # Weak areas (Tier 1-2)
    weak = []
    for axis in AXIS_ORDER:
        tier = getattr(r, f"{axis}_tier")
        score = getattr(r, axis)
        if tier in (SkillTier.TIER_1, SkillTier.TIER_2):
            weak.append(f"{i18n._(f'radar:axis-{axis}')} ({score:.1f})")

    if weak:
        weak_lbl = Label(
            text=f"[b]{i18n._('radar:weak-areas')}:[/b] {', '.join(weak)}",
            markup=True,
            font_name=Theme.DEFAULT_FONT,
            font_size=dp(13),
            color=tier_to_color("tier_2"),
            size_hint_y=None,
            height=dp(24),
        )
        layout.add_widget(weak_lbl)

    return layout


def _no_data_content() -> BoxLayout:
    """Create content for when there's no radar data."""
    layout = BoxLayout()
    layout.add_widget(
        Label(
            text=i18n._("radar:insufficient-moves"),
            font_name=Theme.DEFAULT_FONT,
            font_size=dp(14),
            halign="center",
        )
    )
    return layout
