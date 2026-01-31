from __future__ import annotations

import math
import threading

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, Clock, ListProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget
from kivymd.app import MDApp

from katrain.gui.theme import Theme
from katrain.core.eval_metrics import classify_mistake, MistakeCategory


class Graph(Widget):
    marker_font_size = NumericProperty(0)
    background_image = StringProperty(Theme.GRAPH_TEXTURE)
    background_color = ListProperty([1, 1, 1, 1])
    highlighted_index = NumericProperty(0)
    nodes = ListProperty([])
    hidden = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._lock = threading.Lock()
        self.bind(pos=self.update_graph, size=self.update_graph)
        self.redraw_trigger = Clock.create_trigger(self.update_graph, 0.1)

    def set_nodes_from_list(self, node_list):
        """Set nodes from a pre-built node list.

        Thread-safe: acquires _lock before modifying state.
        Must be called from Kivy main thread.

        Args:
            node_list: List of GameNode references (snapshot at call time)
        """
        with self._lock:
            self.nodes = node_list
            self.highlighted_index = 0
        self.redraw_trigger()

    def update_graph(self, *args):
        pass

    def update_value(self, node):
        with self._lock:
            self.highlighted_index = index = node.depth
            self.nodes.extend([None] * max(0, index - (len(self.nodes) - 1)))
            self.nodes[index] = node
            if index > 1 and node.parent:  # sometimes there are gaps
                backfill, bfnode = index - 1, node.parent
                while bfnode is not None and self.nodes[backfill] != bfnode:
                    self.nodes[backfill] = bfnode
                    backfill -= 1
                    bfnode = bfnode.parent

            if index + 1 < len(self.nodes) and (
                node is None or not node.children or self.nodes[index + 1] != node.ordered_children[0]
            ):
                self.nodes = self.nodes[: index + 1]  # on branch switching, don't show history from other branch
            if index == len(self.nodes) - 1:  # possibly just switched branch or the line above triggered
                while node.children:  # add children back
                    node = node.ordered_children[0]
                    self.nodes.append(node)
            self.redraw_trigger()


class ScoreGraph(Graph):
    show_score = BooleanProperty(True)
    show_winrate = BooleanProperty(True)
    show_important_line = BooleanProperty(True)

    score_points = ListProperty([])
    winrate_points = ListProperty([])

    score_dot_pos = ListProperty([0, 0])
    winrate_dot_pos = ListProperty([0, 0])
    highlight_size = NumericProperty(dp(6))

    score_scale = NumericProperty(5)
    winrate_scale = NumericProperty(5)

    navigate_move = ListProperty([None, 0, 0, 0])
    important_points = ListProperty([])

    mistake_points = ListProperty([])

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and "scroll" not in getattr(touch, "button", ""):
            ix, _ = min(enumerate(self.score_points[::2]), key=lambda ix_v: abs(ix_v[1] - touch.x))
            self.navigate_move = [
                self.nodes[ix],
                self.score_points[2 * ix],
                self.score_points[2 * ix + 1],
                self.winrate_points[2 * ix + 1],
            ]
        else:
            self.navigate_move = [None, 0, 0, 0]

    def on_touch_move(self, touch):
        return self.on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self.navigate_move[0] and "scroll" not in getattr(touch, "button", ""):
            katrain = MDApp.get_running_app().gui
            if katrain and katrain.game:
                katrain.game.set_current_node(self.navigate_move[0])
                katrain.update_state()
        self.navigate_move = [None, 0, 0, 0]

    def show_graphs(self, keys):
        self.show_score = keys["score"]
        self.show_winrate = keys["winrate"]

    def update_graph(self, *args):
        nodes = self.nodes
        # 重要手ラインは毎回作り直す
        self.important_points = []
        self.mistake_points = []

        if not nodes:
            return

        score_values = [n.score if n and n.score else math.nan for n in nodes]
        score_nn_values = [n.score for n in nodes if n and n.score]
        score_values_range = min(score_nn_values or [0]), max(score_nn_values or [0])

        winrate_values = [
            (n.winrate - 0.5) * 100 if n and n.winrate else math.nan
            for n in nodes
        ]
        winrate_nn_values = [
            (n.winrate - 0.5) * 100 for n in nodes if n and n.winrate
        ]
        winrate_values_range = min(winrate_nn_values or [0]), max(winrate_nn_values or [0])

        score_granularity = 5
        winrate_granularity = 10

        self.score_scale = (
            max(
                math.ceil(
                    max(-score_values_range[0], score_values_range[1]) / score_granularity
                ),
                1,
            )
            * score_granularity
        )
        self.winrate_scale = (
            max(
                math.ceil(
                    max(-winrate_values_range[0], winrate_values_range[1]) / winrate_granularity
                ),
                1,
            )
            * winrate_granularity
        )

        xscale = self.width / max(len(score_values) - 1, 15)
        available_height = self.height

        score_line_points = [
            [
                self.x + i * xscale,
                self.y + self.height / 2 + available_height / 2 * (val / self.score_scale),
            ]
            for i, val in enumerate(score_values)
        ]
        winrate_line_points = [
            [
                self.x + i * xscale,
                self.y + self.height / 2 + available_height / 2 * (val / self.winrate_scale),
            ]
            for i, val in enumerate(winrate_values)
        ]

        self.score_points = sum(score_line_points, [])
        self.winrate_points = sum(winrate_line_points, [])

        if self.highlighted_index is not None:
            self.highlighted_index = min(self.highlighted_index, len(score_values) - 1)
            score_dot_point = score_line_points[self.highlighted_index]
            winrate_dot_point = winrate_line_points[self.highlighted_index]

            if math.isnan(score_dot_point[1]):
                score_dot_point[1] = (
                    self.y
                    + self.height / 2
                    + available_height / 2 * ((score_nn_values or [0])[-1] / self.score_scale)
                )
            self.score_dot_pos = score_dot_point

            if math.isnan(winrate_dot_point[1]):
                winrate_dot_point[1] = (
                    self.y
                    + self.height / 2
                    + available_height / 2 * ((winrate_nn_values or [0])[-1] / self.winrate_scale)
                )
            self.winrate_dot_pos = winrate_dot_point

        # ------------------------------------------------------------------
        # 大悪手（BLUNDER）の縦線を計算（軽めの可視化）
        # ------------------------------------------------------------------
        blunder_points: list[float] = []
        for idx, node in enumerate(nodes):
            if not node:
                continue

            points_lost = getattr(node, "points_lost", None)
            if points_lost is None:
                continue

            # KaTrain の points_lost は「その手でどれだけ損したか（目）」
            score_loss = max(float(points_lost), 0.0)
            if score_loss <= 0.0:
                continue

            mc = classify_mistake(score_loss=score_loss, winrate_loss=None)
            if mc is not MistakeCategory.BLUNDER:
                continue  # 「大悪手」のみを強調

            if 0 <= idx < len(score_line_points):
                x = score_line_points[idx][0]
                # グラフ全体の高さにわたる縦線
                blunder_points.extend([x, self.y, x, self.y + self.height])

        self.mistake_points = blunder_points

        # ------------------------------------------------------------------
        # 重要な手の縦線を計算
        #   ※ Game.get_important_move_numbers() は
        #      「メイン分岐上のインデックス（0=root,1=1手目,2=2手目…）」を返す想定
        # ------------------------------------------------------------------
        katrain_app = MDApp.get_running_app()
        gui = getattr(katrain_app, "gui", None) if katrain_app is not None else None

        important_points: list[float] = []
        if gui is not None and getattr(gui, "game", None) is not None:
            game = gui.game
            get_important = getattr(game, "get_important_move_numbers", None)
            if callable(get_important):
                # 重要局面の「インデックス集合」
                important_indices = {
                    int(i) for i in get_important() if i is not None
                }
                max_idx = len(score_line_points) - 1

                # nodes[i] に対応する x 座標を直接使う
                for idx in sorted(important_indices):
                    if 0 <= idx <= max_idx:
                        x = score_line_points[idx][0]
                        # グラフ全体の高さにわたる縦線
                        important_points.extend(
                            [x, self.y, x, self.y + self.height]
                        )

        self.important_points = important_points


Builder.load_string(
    """
#:import Theme katrain.gui.theme.Theme

<Graph>:
    background_color: Theme.BOX_BACKGROUND_COLOR
    marker_font_size: 0.1 * self.height
    canvas.before:
        Color:
            rgba: root.background_color
        Rectangle:
            size: self.size
            pos: self.pos
        Color:
            rgba: [1,1,1,1]
        Rectangle:
            pos: self.pos
            size: self.size
            source: root.background_image

<ScoreGraph>:
    canvas:
        Color:
            rgba: Theme.SCORE_COLOR
        Line:
            points: root.score_points if root.show_score else []
            width: dp(1.1)
        Color:
            rgba: Theme.WINRATE_COLOR
        Line:
            points: root.winrate_points if root.show_winrate else []
            width: dp(1.1)
        Color:
            rgba: [0.5,0.5,0.5,1] if root.navigate_move[0] else [0,0,0,0]
        Line:
            points: root.navigate_move[1], root.y, root.navigate_move[1], root.y+root.height
            width: 1

        # 大悪手（BLUNDER）の縦線
        Color:
            # 赤より少しオレンジ寄りにして、重要局面ラインと区別しやすくする
            rgba: [1,0.6,0.2,0.9] if root.show_important_line and root.mistake_points else [0,0,0,0]
        Line:
            points: root.mistake_points if root.show_important_line else []
            width: 1.2

        # 重要な手の縦線（トグルで ON/OFF）
        Color:
            rgba: Theme.GRAPH_DOT_COLOR if root.show_important_line and root.important_points else [0,0,0,0]
        Line:
            points: root.important_points if root.show_important_line else []
            width: 1

        Color:
            rgba: Theme.GRAPH_DOT_COLOR
        Ellipse:
            id: score_dot
            pos: [c - self.highlight_size / 2 for c in (self.score_dot_pos if not self.navigate_move[0] else [self.navigate_move[1],self.navigate_move[2]] ) ]
            size: (self.highlight_size,self.highlight_size) if root.show_score else (0.0001,0.0001)
        Color:
            rgba: Theme.GRAPH_DOT_COLOR
        Ellipse:
            id: winrate_dot
            pos: [c - self.highlight_size / 2 for c in (self.winrate_dot_pos if not self.navigate_move[0] else [self.navigate_move[1],self.navigate_move[3]] ) ]
            size: (self.highlight_size,self.highlight_size) if root.show_winrate else (0.0001,0.0001)
    # score ticks
    GraphMarkerLabel:
        font_size: root.marker_font_size
        color: Theme.SCORE_MARKER_COLOR
        pos: root.x + root.width - self.width-1, root.pos[1]+root.height - self.font_size - 1
        text: '{}+{}'.format(i18n._('short color B'), root.score_scale)
        opacity: int(root.show_score)
    GraphMarkerLabel:
        font_size: root.marker_font_size
        color: Theme.SCORE_MARKER_COLOR
        pos: root.x + root.width - self.width-1, root.y + root.height*0.5 - self.height/2 + 2
        text: i18n._('Jigo')
        opacity: int(root.show_score)
    GraphMarkerLabel:
        font_size: root.marker_font_size
        color: Theme.SCORE_MARKER_COLOR
        pos: root.x + root.width - self.width-1, root.pos[1]
        text: '{}+{}'.format(i18n._('short color W'), root.score_scale)
        opacity: int(root.show_score)
    # wr ticks
    GraphMarkerLabel:
        font_size: root.marker_font_size
        color: Theme.WINRATE_MARKER_COLOR
        pos: root.pos[0]+1,  root.pos[1] + root.height - self.font_size - 1
        text: "{}%".format(50 + root.winrate_scale)
        opacity: int(root.show_winrate)
    GraphMarkerLabel:
        font_size: root.marker_font_size
        color: Theme.WINRATE_MARKER_COLOR
        pos:root.pos[0]+1, root.pos[1]
        text: "{}%".format(50 - root.winrate_scale)
        opacity: int(root.show_winrate)
"""
)
