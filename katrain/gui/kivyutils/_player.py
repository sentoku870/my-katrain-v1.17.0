"""Kivy player-setup and player-info widgets (Phase 144-A split).

Extracted from katrain/gui/kivyutils/widgets.py:
- PlayerSetup: Single player (B/W) configuration with player_type/subtype spinners.
- PlayerSetupBlock: Block layout containing both B and W PlayerSetup widgets.
- PlayerInfo: Display-only box showing player captures, name, rank, etc.
"""
from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, OptionProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout

from katrain.core.constants import (
    AI_STRATEGIES_RECOMMENDED_ORDER,
    GAME_TYPES,
    PLAYER_AI,
    PLAYER_HUMAN,
    PLAYING_NORMAL,
    PLAYING_TEACHING,
)
from katrain.core.lang import i18n
from katrain.gui.kivyutils.mixins import BackgroundMixin


class PlayerSetup(MDBoxLayout):
    player = OptionProperty("B", options=["B", "W"])
    mode = StringProperty("")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.player_subtype_ai.value_refs = AI_STRATEGIES_RECOMMENDED_ORDER
        self.player_subtype_human.value_refs = GAME_TYPES
        self.setup_options()

    def setup_options(self, *_args: Any) -> None:
        if self.player_type.selected[1] == self.mode:
            return
        self.mode = self.player_type.selected[1]
        self.update_global_player_info()

    @property
    def player_type_dump(self) -> dict[str, Any]:
        if self.mode == PLAYER_AI:
            return {"player_type": self.player_type.selected[1], "player_subtype": self.player_subtype_ai.selected[1]}
        else:
            return {
                "player_type": self.player_type.selected[1],
                "player_subtype": self.player_subtype_human.selected[1],
            }

    def update_widget(self, player_type: str, player_subtype: str) -> None:
        self.player_type.select_key(player_type)  # should trigger setup options
        if self.mode == PLAYER_AI:
            self.player_subtype_ai.select_key(player_subtype)  # should trigger setup options
        else:
            self.player_subtype_human.select_key(player_subtype)  # should trigger setup options

    def update_global_player_info(self) -> None:
        if self.parent and self.parent.update_global:
            katrain = MDApp.get_running_app().gui
            if katrain.game and katrain.game.current_node:
                katrain.update_player(self.player, **self.player_type_dump)


class PlayerSetupBlock(MDBoxLayout):
    players = ObjectProperty(None)
    black = ObjectProperty(None)
    white = ObjectProperty(None)
    update_global = BooleanProperty(False)
    INSTANCES: list[Any] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.black = PlayerSetup(player="B")
        self.white = PlayerSetup(player="W")
        self.players = {"B": self.black, "W": self.white}
        self.add_widget(self.black)
        self.add_widget(self.white)
        PlayerSetupBlock.INSTANCES.append(self)

    def swap_players(self) -> None:
        player_dump = {bw: p.player_type_dump for bw, p in self.players.items()}
        for bw in "BW":
            self.update_player_params(bw, player_dump["B" if bw == "W" else "W"])

    def update_player_params(self, bw: str, params: dict[str, Any]) -> None:
        self.players[bw].update_widget(**params)

    def update_player_info(self, bw: str, player_info: Any) -> None:  # update sub widget based on gui state change
        Clock.schedule_once(
            lambda _dt: self.players[bw].update_widget(
                player_type=player_info.player_type, player_subtype=player_info.player_subtype
            ),
            -1,
        )


class PlayerInfo(MDBoxLayout, BackgroundMixin):
    captures = ObjectProperty(0)
    player = OptionProperty("B", options=["B", "W"])
    player_type = StringProperty("Player")
    komi = NumericProperty(0)
    player_subtype = StringProperty("")
    name = StringProperty("", allownone=True)
    rank = StringProperty("", allownone=True)
    active = BooleanProperty(True)
    alignment = StringProperty("right")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.bind(player_type=self.set_label, player_subtype=self.set_label, name=self.set_label, rank=self.set_label)

    def set_label(self, *args: Any) -> None:
        if not self.subtype_label:  # building
            return
        show_player_name = self.name and self.player_type == PLAYER_HUMAN and self.player_subtype == PLAYING_NORMAL
        text = self.name if show_player_name else i18n._(self.player_subtype)
        if (
            self.rank
            and self.player_subtype != PLAYING_TEACHING
            and (show_player_name or self.player_type == PLAYER_AI)
        ):
            text += f" ({self.rank})"
        self.subtype_label.text = text
