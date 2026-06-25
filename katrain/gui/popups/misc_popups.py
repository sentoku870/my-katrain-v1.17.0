"""Misc popups (tsumego, game report).

Phase 140 P2-1: Extracted from katrain/gui/popups.py.
"""
from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import DictProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout

from katrain.core.ai import game_report
from katrain.core.constants import PLAYER_HUMAN
from katrain.core.lang import i18n, rank_label
from katrain.core.sgf_parser import Move
from katrain.gui.kivyutils import TableCellLabel, TableHeaderLabel, TableStatLabel
from katrain.gui.theme import Theme


class TsumegoFramePopup(BoxLayout):
    katrain = ObjectProperty(None)
    popup = ObjectProperty(None)
    button = ObjectProperty(None)

    def on_submit(self) -> None:
        self.button.trigger_action(duration=0)


class GameReportPopup(BoxLayout):
    stats = ObjectProperty(None)
    player_infos = DictProperty({})
    button = ObjectProperty(None)

    def __init__(self, katrain: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.katrain = katrain
        self.depth_filter = None
        Clock.schedule_once(self._refresh, 0)

    def set_depth_filter(self, filter: Any) -> None:
        self.depth_filter = filter
        Clock.schedule_once(self._refresh, 0)

    def _refresh(self, _dt: float = 0) -> None:
        game = self.katrain.game
        thresholds = self.katrain.config("trainer/eval_thresholds")

        sum_stats, histogram, player_ptloss = game_report(game, depth_filter=self.depth_filter, thresholds=thresholds)
        labels = [f"≥ {pt}" if pt > 0 else f"< {thresholds[-2]}" for pt in thresholds]

        table = GridLayout(cols=3, rows=6 + len(thresholds), size_hint=(1, None))
        table.row_default_height = dp(40)
        table.row_force_default = True
        table.bind(minimum_height=table.setter("height"))
        colors = [
            [cp * 0.75 for cp in col[:3]] + [1] for col in Theme.EVAL_COLORS[self.katrain.config("trainer/theme")]
        ]

        table.add_widget(TableHeaderLabel(text="", background_color=Theme.BACKGROUND_COLOR))
        table.add_widget(TableHeaderLabel(text=i18n._("header:keystats"), background_color=Theme.BACKGROUND_COLOR))
        table.add_widget(TableHeaderLabel(text="", background_color=Theme.BACKGROUND_COLOR))

        for _i, (label, fmt, stat, scale, more_is_better) in enumerate(
            [
                ("accuracy", "{:.1f}", "accuracy", 100, True),
                ("meanpointloss", "{:.2f}", "mean_ptloss", 5, False),
                ("aitopmove", "{:.1%}", "ai_top_move", 1, True),
                ("aitop5", "{:.1%}", "ai_top5_move", 1, True),
            ]
        ):
            statcell = {
                bw: TableStatLabel(
                    text=fmt.format(sum_stats[bw][stat]) if stat in sum_stats[bw] else "",
                    side=side,
                    value=sum_stats[bw].get(stat, 0),
                    scale=scale,
                    bar_color=(
                        Theme.STAT_BETTER_COLOR
                        if (sum_stats[bw].get(stat, 0) < sum_stats[Move.opponent_player(bw)].get(stat, 0))
                        ^ more_is_better
                        else Theme.STAT_WORSE_COLOR
                    ),
                    background_color=Theme.BOX_BACKGROUND_COLOR,
                )
                for (bw, side) in zip("BW", ["left", "right"], strict=False)
            }
            table.add_widget(statcell["B"])
            table.add_widget(TableCellLabel(text=i18n._(f"stat:{label}"), background_color=Theme.BOX_BACKGROUND_COLOR))
            table.add_widget(statcell["W"])

        table.add_widget(TableHeaderLabel(text=i18n._("header:num moves"), background_color=Theme.BACKGROUND_COLOR))
        table.add_widget(TableHeaderLabel(text=i18n._("stats:pointslost"), background_color=Theme.BACKGROUND_COLOR))
        table.add_widget(TableHeaderLabel(text=i18n._("header:num moves"), background_color=Theme.BACKGROUND_COLOR))

        for i, (col, label, _pt) in enumerate(zip(colors[::-1], labels[::-1], thresholds[::-1], strict=False)):
            statcell = {
                bw: TableStatLabel(
                    text=str(histogram[i][bw]),
                    side=side,
                    value=histogram[i][bw],
                    scale=len(player_ptloss[bw]) + 1e-6,
                    bar_color=col,
                    background_color=Theme.BOX_BACKGROUND_COLOR,
                )
                for (bw, side) in zip("BW", ["left", "right"], strict=False)
            }
            table.add_widget(statcell["B"])
            table.add_widget(TableCellLabel(text=label, background_color=col))
            table.add_widget(statcell["W"])

        self.stats.clear_widgets()
        self.stats.add_widget(table)

        for bw, player_info in self.katrain.players_info.items():
            self.player_infos[bw].player_type = player_info.player_type
            self.player_infos[bw].captures = ""  # ;)
            self.player_infos[bw].player_subtype = player_info.player_subtype
            self.player_infos[bw].name = player_info.name
            self.player_infos[bw].rank = (
                player_info.sgf_rank
                if player_info.player_type == PLAYER_HUMAN
                else rank_label(player_info.calculated_rank)
            )

        # if not done analyzing, check again in 1s
        if not self.katrain.engine.is_idle():
            Clock.schedule_once(self._refresh, 1)
