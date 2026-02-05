"""5-axis radar chart Kivy widget."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line
from kivy.metrics import dp
from kivy.properties import DictProperty, ListProperty, NumericProperty, StringProperty
from katrain.gui.widgets.factory import Label
from kivy.uix.relativelayout import RelativeLayout

from katrain.core.lang import i18n
from katrain.gui.theme import Theme
from katrain.gui.widgets.radar_geometry import (
    AXIS_ORDER,
    NEUTRAL_SCORE,
    NUM_AXES,
    calculate_vertex,
    get_data_polygon,
    get_label_position,
    tier_to_color,
)

AXIS_I18N = {
    "opening": "radar:axis-opening",
    "fighting": "radar:axis-fighting",
    "endgame": "radar:axis-endgame",
    "stability": "radar:axis-stability",
    "awareness": "radar:axis-awareness",
}


class RadarChartWidget(RelativeLayout):
    """5-axis radar chart widget.

    Properties:
        scores: {"opening": 3.5, ...} (1.0-5.0 or None)
        tiers: {"opening": "tier_4", ...}
        overall_tier: "tier_3" etc.
    """

    # DictProperty() with no args for safe initialization
    scores = DictProperty()
    tiers = DictProperty()
    overall_tier = StringProperty("unknown")

    padding = NumericProperty(dp(45))
    grid_color = ListProperty([0.4, 0.4, 0.4, 0.5])
    fill_color = ListProperty([0.3, 0.6, 0.9, 0.25])
    outline_color = ListProperty([0.3, 0.6, 0.9, 0.9])

    # Grid ring fractions (equal intervals, not tier boundaries)
    GRID_FRACTIONS = [0.2, 0.4, 0.6, 0.8, 1.0]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Create new dict per instance
        self.scores = {}
        self.tiers = {}
        self._redraw_trigger = Clock.create_trigger(self._do_redraw, 0)

        # Fixed labels (created once at init, only text updated on redraw)
        self._labels: List[Label] = []
        for _ in range(NUM_AXES):
            lbl = Label(
                text="",
                markup=True,
                font_name=Theme.DEFAULT_FONT,
                font_size=dp(11),
                halign="center",
                valign="middle",
                size_hint=(None, None),
                size=(dp(80), dp(40)),
                text_size=(dp(80), None),  # Enable text wrapping
                shorten=True,
                shorten_from="right",
            )
            self._labels.append(lbl)
            self.add_widget(lbl)

        # Bind property changes to redraw trigger
        for prop in ("pos", "size", "scores", "tiers"):
            self.bind(**{prop: self._schedule_redraw})

    def _schedule_redraw(self, *_: Any) -> None:
        self._redraw_trigger()

    def _get_grid_ring_points(
        self, fraction: float, center: Tuple[float, float], max_r: float
    ) -> List[float]:
        """Get grid ring points (fixed radius fraction)."""
        radius = max_r * fraction
        points: List[float] = []
        for i in range(NUM_AXES):
            angle_deg = 90 - (360 / NUM_AXES) * i  # ANGLE_OFFSET_DEG = 90
            angle_rad = math.radians(angle_deg)
            x = center[0] + radius * math.cos(angle_rad)
            y = center[1] + radius * math.sin(angle_rad)
            points.extend([x, y])
        points.extend(points[:2])
        return points

    def _do_redraw(self, *_: Any) -> None:
        self.canvas.before.clear()

        # Guard: Skip if widget not in window or not properly sized
        if not self.get_root_window():
            return
        if self.width <= 0 or self.height <= 0:
            return

        cx, cy = self.width / 2, self.height / 2
        center = (cx, cy)
        max_r = min(self.width, self.height) / 2 - self.padding
        if max_r <= 0:
            return

        try:
            with self.canvas.before:
                # 1. Grid pentagons (fixed fractions: 20%, 40%, 60%, 80%, 100%)
                for frac in self.GRID_FRACTIONS:
                    Color(*self.grid_color)
                    Line(points=self._get_grid_ring_points(frac, center, max_r), width=1)

                # 2. Axis lines
                for i in range(NUM_AXES):
                    Color(*self.grid_color)
                    vx, vy = calculate_vertex(i, 5.0, center, max_r)
                    Line(points=[cx, cy, vx, vy], width=1)

                # 3. Data polygon - outline only (Mesh disabled for stability)
                if self.scores:
                    poly = get_data_polygon(self.scores, center, max_r)
                    # Skip Mesh fill - just draw outline for now
                    Color(*self.outline_color)
                    Line(points=poly, width=dp(2))

                    # 4. Vertex dots
                    for i, axis in enumerate(AXIS_ORDER):
                        tier = self.tiers.get(axis, "unknown")
                        Color(*tier_to_color(tier))
                        score = self.scores.get(axis) or NEUTRAL_SCORE
                        vx, vy = calculate_vertex(i, score, center, max_r)
                        dot = dp(8)
                        Ellipse(pos=(vx - dot / 2, vy - dot / 2), size=(dot, dot))

            self._update_labels(center, max_r)
        except Exception:
            # If any rendering error occurs, clear canvas and skip drawing
            self.canvas.before.clear()

    def _update_labels(self, center: Tuple[float, float], max_r: float) -> None:
        for i, axis in enumerate(AXIS_ORDER):
            lbl = self._labels[i]
            lx, ly = get_label_position(i, center, max_r)
            lbl.center = (lx, ly)

            name = i18n._(AXIS_I18N[axis])
            score = self.scores.get(axis)
            tier = self.tiers.get(axis, "unknown")

            if score is not None:
                lbl.text = f"{name}\n[b]{score:.1f}[/b]"
            else:
                lbl.text = f"{name}\n[color=888888]N/A[/color]"
            lbl.color = tier_to_color(tier)
