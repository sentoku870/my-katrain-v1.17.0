"""Skill radar popup for 5-axis visualization."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from kivy.clock import Clock

_logger = logging.getLogger("katrain.gui.features.skill_radar_popup")
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton

from katrain.core.analysis.skill_radar import (
    MIN_MOVES_FOR_RADAR,
    RadarMetrics,
    SkillTier,
    compute_radar_from_moves,
)
from katrain.core.constants import OUTPUT_ERROR
from katrain.core.lang import i18n
from katrain.gui.theme import Theme
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

    radar: dict[str, RadarMetrics | None] = {}
    for p in ("B", "W"):
        player_moves = [m for m in snapshot.moves if m.player == p]
        print(f"[RADAR DEBUG] Player={p}, num_moves={len(player_moves)}, move_numbers={[m.move_number for m in player_moves[:5]]}")
        _logger.debug(
            "[RADAR DEBUG] Player=%s, num_moves=%d, move_numbers=%s",
            p,
            len(player_moves),
            [m.move_number for m in player_moves[:5]],  # first 5 for brevity
        )
        if len(player_moves) >= MIN_MOVES_FOR_RADAR:
            try:
                metrics = compute_radar_from_moves(snapshot.moves, player=p)
                radar[p] = metrics
                print(f"[RADAR DEBUG] Player={p}, id={id(metrics)}, opening={metrics.opening:.2f}, fighting={metrics.fighting:.2f}, stability={metrics.stability:.2f}")
                _logger.debug(
                    "[RADAR DEBUG] Player=%s, RadarMetrics id=%d, opening=%.2f, fighting=%.2f, stability=%.2f",
                    p,
                    id(metrics),
                    metrics.opening,
                    metrics.fighting,
                    metrics.stability,
                )
            except Exception as e:
                ctx.log(f"{i18n._('radar:calc-error')} ({p}): {e}", OUTPUT_ERROR)
                radar[p] = None
        else:
            radar[p] = None

    # Debug: Check if B and W have different objects
    b_r = radar.get("B")
    w_r = radar.get("W")
    same_obj = b_r is w_r if (b_r and w_r) else "N/A"
    print(f"[RADAR DEBUG] Final: B_id={id(b_r) if b_r else 'None'}, W_id={id(w_r) if w_r else 'None'}, same_object={same_obj}")
    if b_r and w_r:
        print(f"[RADAR DEBUG] B scores: o={b_r.opening}, f={b_r.fighting}, e={b_r.endgame}, s={b_r.stability}, a={b_r.awareness}")
        print(f"[RADAR DEBUG] W scores: o={w_r.opening}, f={w_r.fighting}, e={w_r.endgame}, s={w_r.stability}, a={w_r.awareness}")
    _logger.debug(
        "[RADAR DEBUG] Final radar dict: B_id=%s, W_id=%s, same_object=%s",
        id(radar.get("B")) if radar.get("B") else "None",
        id(radar.get("W")) if radar.get("W") else "None",
        radar.get("B") is radar.get("W") if radar.get("B") and radar.get("W") else "N/A",
    )

    if not any(radar.values()):
        ctx.log(i18n._("radar:insufficient-moves"), OUTPUT_ERROR)
        return

    _build_popup(radar)


class SkillRadarPopup(Popup):
    """Popup with ToggleButton-based player selector."""

    def __init__(self, radar: dict[str, RadarMetrics | None], **kwargs: Any) -> None:
        self.radar = radar
        self.current_side = "B"  # Default to Black

        super().__init__(**kwargs)

        self.title = i18n._("radar:title")
        self.title_font = Theme.DEFAULT_FONT
        self.size_hint = (0.75, 0.85)

        # Main content
        main = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))

        # Player selector (ToggleButtons)
        selector = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(44),
            spacing=dp(8),
        )

        self.btn_black = ToggleButton(
            text=i18n._("mykatrain:batch:filter_black"),
            font_name=Theme.DEFAULT_FONT,
            group="player_select",
            state="down",  # Default selected
            allow_no_selection=False,
        )
        self.btn_white = ToggleButton(
            text=i18n._("mykatrain:batch:filter_white"),
            font_name=Theme.DEFAULT_FONT,
            group="player_select",
            state="normal",
            allow_no_selection=False,
        )

        self.btn_black.bind(on_press=lambda _: self._select_side("B"))
        self.btn_white.bind(on_press=lambda _: self._select_side("W"))

        selector.add_widget(self.btn_black)
        selector.add_widget(self.btn_white)
        main.add_widget(selector)

        # Content container (will be updated when side changes)
        self.content_container = BoxLayout(orientation="vertical", size_hint=(1, 1))
        main.add_widget(self.content_container)

        # Close button
        close_btn = Button(
            text=i18n._("Close"),
            font_name=Theme.DEFAULT_FONT,
            size_hint=(1, None),
            height=dp(44),
        )
        close_btn.bind(on_release=self.dismiss)
        main.add_widget(close_btn)

        self.content = main

        # Initial content
        self._refresh_content()

    def _select_side(self, side: str) -> None:
        """Handle side selection change."""
        print(f"[RADAR DEBUG] _select_side: new_side={side}, current_side={self.current_side}")
        _logger.debug(
            "[RADAR DEBUG] _select_side called: new_side=%s, current_side=%s",
            side,
            self.current_side,
        )
        if side != self.current_side:
            self.current_side = side
            self._refresh_content()

    def _refresh_content(self) -> None:
        """Refresh the content area based on current side."""
        self.content_container.clear_widgets()

        r = self.radar.get(self.current_side)
        print(f"[RADAR DEBUG] _refresh_content: side={self.current_side}, radar_id={id(r) if r else 'None'}")
        if r:
            print(f"[RADAR DEBUG] Displaying: o={r.opening}, f={r.fighting}, e={r.endgame}, s={r.stability}, a={r.awareness}")
        _logger.debug(
            "[RADAR DEBUG] _refresh_content: side=%s, radar_id=%s, opening=%.2f, fighting=%.2f",
            self.current_side,
            id(r) if r else "None",
            r.opening if r else 0,
            r.fighting if r else 0,
        )
        if r:
            self.content_container.add_widget(_player_content(r, self.current_side))
        else:
            self.content_container.add_widget(_no_data_content())


def _build_popup(radar: dict[str, RadarMetrics | None]) -> None:
    """Build and display the popup."""
    popup = SkillRadarPopup(radar)
    popup.open()


def _player_content(r: RadarMetrics, side: str) -> BoxLayout:
    """Create player radar content (text-only mode for stability)."""
    layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))

    # Header with player indication
    side_name = i18n._("mykatrain:batch:filter_black") if side == "B" else i18n._("mykatrain:batch:filter_white")
    header = Label(
        text=f"[b]{i18n._('radar:title')} ({side_name})[/b]",
        markup=True,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(18),
        size_hint_y=None,
        height=dp(36),
        halign="center",
    )
    header.bind(size=header.setter("text_size"))
    layout.add_widget(header)

    # Centered score list container
    center_anchor = AnchorLayout(anchor_x="center", anchor_y="top", size_hint=(1, 0.6))
    scores_box = BoxLayout(
        orientation="vertical",
        size_hint=(None, 1),
        width=dp(280),
        spacing=dp(6),
        padding=(dp(16), dp(8)),
    )

    # Each axis score
    for axis in AXIS_ORDER:
        score = getattr(r, axis)
        tier = getattr(r, f"{axis}_tier")
        tier_color = tier_to_color(tier.value)

        # Stars: filled based on score (1-5)
        filled = min(5, max(1, int(round(score))))
        stars = "★" * filled + "☆" * (5 - filled)
        axis_name = i18n._(f"radar:axis-{axis}")

        row = Label(
            text=f"[b]{axis_name}[/b]: {score:.1f}  {stars}",
            markup=True,
            font_name=Theme.DEFAULT_FONT,
            font_size=dp(15),
            color=tier_color,
            size_hint_y=None,
            height=dp(30),
            halign="left",
            valign="middle",
        )
        row.bind(size=row.setter("text_size"))
        scores_box.add_widget(row)

    center_anchor.add_widget(scores_box)
    layout.add_widget(center_anchor)

    # Summary section
    layout.add_widget(_summary(r))

    return layout


def _summary(r: RadarMetrics) -> BoxLayout:
    """Create summary section with overall tier and weak areas."""
    layout = BoxLayout(orientation="vertical", size_hint=(1, 0.25), padding=dp(8))

    tier_text = i18n._(TIER_I18N.get(r.overall_tier, "radar:tier-unknown"))
    tier_color = tier_to_color(r.overall_tier.value)

    overall = Label(
        text=f"[b]{i18n._('radar:overall')}:[/b] {tier_text}",
        markup=True,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(16),
        color=tier_color,
        size_hint_y=None,
        height=dp(32),
        halign="center",
    )
    overall.bind(size=overall.setter("text_size"))
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
            font_size=dp(14),
            color=tier_to_color("tier_2"),
            size_hint_y=None,
            height=dp(28),
            halign="center",
        )
        weak_lbl.bind(size=weak_lbl.setter("text_size"))
        layout.add_widget(weak_lbl)

    return layout


def _no_data_content() -> BoxLayout:
    """Create content for when there's no radar data."""
    layout = BoxLayout(padding=dp(20))
    lbl = Label(
        text=i18n._("radar:insufficient-moves"),
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(16),
        halign="center",
        valign="middle",
    )
    lbl.bind(size=lbl.setter("text_size"))
    layout.add_widget(lbl)
    return layout
