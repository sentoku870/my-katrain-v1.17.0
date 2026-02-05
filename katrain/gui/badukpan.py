from __future__ import annotations

import copy
import math
import time
from typing import Any

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics.context_instructions import Color, PopMatrix, PushMatrix, Rotate, Translate
from kivy.graphics.texture import Texture
from kivy.graphics.vertex_instructions import Ellipse, Line, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty
from kivy.uix.dropdown import DropDown
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.floatlayout import MDFloatLayout

from katrain.core.analysis import DEFAULT_PV_FILTER_LEVEL, filter_candidates_by_pv_complexity, get_pv_filter_config
from katrain.core.beginner.hints import (
    get_beginner_hint_cached,
    is_coords_valid,
    should_draw_board_highlight,
)
from katrain.core.constants import (
    LEELA_COLOR_BEST,
    LEELA_TOP_MOVE_LOSS,
    LEELA_TOP_MOVE_VISITS,
    LEELA_TOP_MOVE_WINRATE,
    MODE_PLAY,
    OUTPUT_DEBUG,
    OUTPUT_EXTRA_DEBUG,
    STATUS_TEACHING,
    TOP_MOVE_DELTA_SCORE,
    TOP_MOVE_DELTA_WINRATE,
    TOP_MOVE_NOTHING,
    TOP_MOVE_OPTIONS,
    TOP_MOVE_SCORE,
    TOP_MOVE_VISITS,
    TOP_MOVE_WINRATE,
)
from katrain.core.game import Move
from katrain.core.lang import i18n
from katrain.core.leela.presentation import (
    format_loss_est,
    format_winrate_pct,
    loss_to_color,
)
from katrain.core.leela.presentation import (
    format_visits as format_leela_visits,
)
from katrain.core.utils import evaluation_class, format_visits, json_truncate_arrays, var_to_grid
from katrain.gui.kivyutils import cached_texture, draw_circle, draw_text
from katrain.gui.popups import GameReportPopup, I18NPopup, ReAnalyzeGamePopup, TsumegoFramePopup
from katrain.gui.theme import Theme


class BadukPanWidget(Widget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.trainer_config: dict[str, Any] = {}
        self.ghost_stone: tuple[int, int] | None = None
        self.gridpos: Any = None
        self.initial_gridpos_x: list[Any] = []
        self.initial_gridpos_y: list[Any] = []
        self.rotation_degree: int = 0
        self.grid_size: float = 0
        self.stone_size: float = 0
        self.selecting_region_of_interest: bool = False
        self.region_of_interest: list[Any] = []
        self.draw_coords_enabled: bool = True

        self.active_pv_moves: list[Any] = []
        self.animating_pv: Any = None
        self.animating_pv_index: Any = None
        self._animate_interval: Any = None  # ClockEvent reference for PV animation (lazy init)
        self.last_mouse_pos: tuple[float, float] = (0, 0)
        Window.bind(mouse_pos=self.on_mouse_pos)
        self.redraw_board_contents_trigger = Clock.create_trigger(self.draw_board_contents, 0.05)
        self.redraw_trigger = Clock.create_trigger(self.redraw, 0.05)
        self.redraw_hover_contents_trigger = Clock.create_trigger(self.draw_hover_contents, 0.01)
        self.bind(size=self.redraw_trigger, pos=self.redraw_trigger)
        # Removed: Clock.schedule_interval(self.animate_pv, 0.1)
        # PV animation is now started/stopped on demand via _update_pv_animation_state()

    def _start_pv_animation(self) -> None:
        """Start PV animation interval (idempotent).

        Note: Does nothing if already started (prevents double scheduling).
        """
        if self._animate_interval is None:
            self._animate_interval = Clock.schedule_interval(self.animate_pv, 0.1)

    def _stop_pv_animation(self) -> None:
        """Stop PV animation interval (idempotent).

        Note: After cancel(), reset to None to allow restart.
        """
        if self._animate_interval is not None:
            self._animate_interval.cancel()
            self._animate_interval = None

    def _update_pv_animation_state(self) -> None:
        """Update animation state based on active_pv_moves.

        Call this after updating active_pv_animation to start/stop animation.
        """
        if self.active_pv_moves:
            self._start_pv_animation()
        else:
            self._stop_pv_animation()

    def reset_rotation(self) -> None:
        while self.rotation_degree:
            self.rotate_gridpos()

    def toggle_coordinates(self) -> bool:
        self.draw_coords_enabled = not self.draw_coords_enabled
        self.redraw_trigger()
        return self.draw_coords_enabled

    def get_enable_coordinates(self) -> bool:
        return self.draw_coords_enabled

    # stone placement functions
    def _find_closest(self, pos_x: float, pos_y: float) -> tuple[float, int, float, int]:
        if self.gridpos is None:
            return (0.0, 0, 0.0, 0)
        xd = abs(self.gridpos[0][0][0] - pos_x)
        xp = 0
        yd = abs(self.gridpos[0][0][1] - pos_y)
        yp = 0
        for y in range(0, len(self.gridpos)):
            for x in range(0, len(self.gridpos[0])):
                if abs(self.gridpos[y][x][0] - pos_x) <= xd and abs(self.gridpos[y][x][1] - pos_y) <= yd:
                    xd = abs(self.gridpos[y][x][0] - pos_x)
                    xp = x
                    yd = abs(self.gridpos[y][x][1] - pos_y)
                    yp = y
        return xd, xp, yd, yp

    def check_next_move_ghost(self, touch: Any) -> None:
        if not self.initial_gridpos_x:
            return
        xd, xp, yd, yp = self._find_closest(touch.x, touch.y)
        prev_ghost = self.ghost_stone
        if max(yd, xd) < self.grid_size / 2 and (xp, yp) not in [m.coords for m in self.katrain.game.stones]:
            self.ghost_stone = (xp, yp)
        else:
            self.ghost_stone = None
        if prev_ghost != self.ghost_stone:
            self.redraw_hover_contents_trigger()

    def update_box_selection(self, touch: Any, second_point: bool = True) -> None:
        if not self.initial_gridpos_x:
            return
        _, xp, _, yp = self._find_closest(touch.x, touch.y)
        if second_point and len(self.region_of_interest) == 4:
            self.region_of_interest[1] = xp
            self.region_of_interest[3] = yp
        else:
            self.region_of_interest = [xp, xp, yp, yp]
        self.redraw_hover_contents_trigger()

    def on_touch_down(self, touch: Any) -> Any:
        animating_pv = self.animating_pv
        if "button" in touch.profile:
            if touch.button == "left":
                if self.selecting_region_of_interest:
                    self.update_box_selection(touch, second_point=False)
                else:
                    self.check_next_move_ghost(touch)
            elif touch.button == "middle" and animating_pv:
                pv, node, _, _ = animating_pv
                upto = self.animating_pv_index or 1e9
                for i, gtpmove in enumerate(pv):
                    if i <= upto:  # up to move when scrolling, or all
                        node = node.play(Move.from_gtp(gtpmove, node.next_player))
                        node.analyze(self.katrain.engine, analyze_fast=True)
                self.katrain.controls.move_tree.redraw_tree_trigger()

        if ("button" not in touch.profile) or (touch.button not in ["scrollup", "scrolldown", "middle"]):
            self.set_animating_pv(None, None)  # any click/touch kills PV from label/move
        return super().on_touch_down(touch)

    def on_touch_move(self, touch: Any) -> None:
        if "button" in touch.profile and touch.button != "left":
            return
        if self.selecting_region_of_interest:
            self.update_box_selection(touch)
        else:
            self.check_next_move_ghost(touch)

    def on_mouse_pos(self, *args: Any) -> None:  # https://gist.github.com/opqopq/15c707dc4cffc2b6455f
        if self.get_root_window():  # don't proceed if I'm not displayed <=> If have no parent
            pos = args[1]
            rel_pos = self.to_widget(*pos)  # compensate for relative layout
            inside = self.collide_point(*rel_pos)

            if inside and self.active_pv_moves and not self.selecting_region_of_interest and self.gridpos is not None:
                near_move = [
                    (pv, node)
                    for move, pv, node in self.active_pv_moves
                    if move[0] < len(self.gridpos[0])
                    and move[1] < len(self.gridpos)
                    and abs(rel_pos[0] - self.gridpos[move[1]][move[0]][0]) < self.grid_size / 2
                    and abs(rel_pos[1] - self.gridpos[move[1]][move[0]][1]) < self.grid_size / 2
                ]
                if near_move:
                    self.set_animating_pv(near_move[0][0], near_move[0][1])
                elif self.animating_pv is not None:
                    self.set_animating_pv(None, None)  # any click kills PV from label/move
            if inside and self.animating_pv is not None:
                d_sq = (pos[0] - self.animating_pv[3][0]) ** 2 + (pos[1] - self.animating_pv[3][1])
                if d_sq > 2 * self.stone_size**2:  # move too far from where it was activated
                    self.set_animating_pv(None, None)  # any click kills PV from label/move
            self.last_mouse_pos = pos

    def on_touch_up(self, touch: Any) -> Any:
        if ("button" in touch.profile and touch.button != "left") or not self.initial_gridpos_x:
            return
        katrain = self.katrain
        if self.selecting_region_of_interest:
            if len(self.region_of_interest) == 4:
                self.katrain.game.set_region_of_interest(self.region_of_interest)
                self.region_of_interest = []
                self.selecting_region_of_interest = False

        elif self.ghost_stone and ("button" not in touch.profile or touch.button == "left"):
            game = self.katrain and self.katrain.game
            current_node = game and self.katrain.game.current_node
            if (
                current_node
                and not current_node.children
                and not self.katrain.next_player_info.ai
                and not self.katrain.controls.timer.paused
                and self.katrain.play_analyze_mode == MODE_PLAY
                and self.katrain.config("timer/main_time", 0) * 60 - game.main_time_used <= 0
                and current_node.time_used < self.katrain.config("timer/minimal_use", 0)
            ):
                self.katrain.controls.set_status(
                    i18n._("move too fast").format(num=self.katrain.config("timer/minimal_use", 0)), STATUS_TEACHING
                )
            else:
                # Phase 93: Active Review mode intercepts play action
                if katrain.active_review_mode:
                    katrain("active_review_guess", self.ghost_stone)
                else:
                    katrain("play", self.ghost_stone)
        elif not self.ghost_stone:
            xd, xp, yd, yp = self._find_closest(touch.x, touch.y)
            nodes_here = [
                node for node in katrain.game.current_node.nodes_from_root if node.move and node.move.coords == (xp, yp)
            ]
            if nodes_here and max(yd, xd) < self.grid_size / 2:  # load old comment
                if touch.is_double_tap:  # navigate to move
                    katrain.game.set_current_node(nodes_here[-1].parent)
                    katrain.update_state()
                else:  # load comments & pv
                    katrain.log(
                        f"\nAnalysis:\n{json_truncate_arrays(nodes_here[-1].analysis, lim=5)}", OUTPUT_EXTRA_DEBUG
                    )
                    katrain.log(
                        f"\nParent Analysis:\n{json_truncate_arrays(nodes_here[-1].parent.analysis, lim=5)}",
                        OUTPUT_EXTRA_DEBUG,
                    )
                    katrain.log(
                        f"\nRoot Stats:\n{json_truncate_arrays(nodes_here[-1].analysis['root'], lim=5)}", OUTPUT_DEBUG
                    )
                    katrain.controls.info.text = nodes_here[-1].comment(sgf=True)
                    katrain.controls.active_comment_node = nodes_here[-1]
                    if nodes_here[-1].parent.analysis_exists:
                        self.set_animating_pv(nodes_here[-1].parent.candidate_moves[0]["pv"], nodes_here[-1].parent)

        self.ghost_stone = None
        self.redraw_hover_contents_trigger()  # remove ghost

    # drawing functions
    def redraw(self, *_args: Any) -> None:
        self.draw_board()
        self.draw_board_contents()

    def draw_stone(
        self,
        x: int,
        y: int,
        player: str,
        alpha: float = 1,
        innercol: Any = None,
        evalcol: Any = None,
        evalscale: float = 1.0,
        scale: float = 1.0,
        ownership: float | None = None,
        loss: float | None = None,
        depth: int | None = None,
    ) -> None:
        stone_size = self.stone_size * scale
        if ownership is not None:
            (owner, other) = ("B", "W") if ownership > 0 else ("W", "B")
            if Theme.TERRITORY_DISPLAY != "marks":
                if player == owner:
                    alpha = Theme.STONE_MIN_ALPHA + (1.0 - Theme.STONE_MIN_ALPHA) * abs(ownership)
                else:
                    alpha = Theme.STONE_MIN_ALPHA
        else:
            (owner, other) = ("B", "W")  # prevent errors in unused unset vars
        Color(1, 1, 1, alpha)
        Rectangle(
            pos=(self.gridpos[y][x][0] - stone_size, self.gridpos[y][x][1] - stone_size),
            size=(2 * stone_size, 2 * stone_size),
            texture=cached_texture(Theme.STONE_TEXTURE[player]),
        )
        # Draw ownership marks on stones; the mark is a square with an outline.
        if (ownership is not None or loss is not None) and (
            Theme.STONE_MARKS == "all" or (Theme.STONE_MARKS == "weak" and player != owner)
        ):
            if ownership is not None:
                mark_color = *Theme.STONE_COLORS[owner][:3], 1.0
                other_color = *Theme.STONE_COLORS[other][:3], 1.0
                outline_color = tuple(
                    map(lambda y: sum(y) / float(len(y)), zip(*(mark_color, other_color), strict=False))
                )
                mark_value = ownership
            else:
                assert loss is not None
                mark_color = *Theme.EVAL_COLORS[self.trainer_config["theme"]][1][:3], 1
                outline_color = mark_color
                mark_value = min(1.0, loss)

            mark_size = Theme.MARK_SIZE * abs(mark_value) * self.stone_size * 2.0
            Color(*mark_color)
            Rectangle(
                pos=(
                    self.gridpos[y][x][0] - mark_size / 2,
                    self.gridpos[y][x][1] - mark_size / 2,
                ),
                size=(mark_size, mark_size),
            )
            Color(*outline_color)
            Line(
                rectangle=(
                    self.gridpos[y][x][0] - mark_size / 2,
                    self.gridpos[y][x][1] - mark_size / 2,
                    mark_size,
                    mark_size,
                ),
                width=1.0,
            )
        if evalcol:
            eval_radius = math.sqrt(evalscale)  # scale area by evalscale
            evalsize = self.stone_size * (
                Theme.EVAL_DOT_MIN_SIZE + eval_radius * (Theme.EVAL_DOT_MAX_SIZE - Theme.EVAL_DOT_MIN_SIZE)
            )
            Color(*evalcol)
            Rectangle(
                pos=(self.gridpos[y][x][0] - evalsize, self.gridpos[y][x][1] - evalsize),
                size=(2 * evalsize, 2 * evalsize),
                texture=cached_texture(Theme.EVAL_DOT_TEXTURE),
            )
        if innercol:
            Color(*innercol)
            inner_size = stone_size * 0.8
            Rectangle(
                pos=(self.gridpos[y][x][0] - inner_size, self.gridpos[y][x][1] - inner_size),
                size=(2 * inner_size, 2 * inner_size),
                texture=cached_texture(Theme.LAST_MOVE_TEXTURE),
            )

        if depth:
            text = str(depth)
            Color(*Theme.NUMBER_COLOR)
            draw_text(pos=self.gridpos[y][x], text=text, font_size=self.stone_size * 0.9, font_name="Roboto")

    def eval_color(self, points_lost: float, show_dots_for_class: list[bool] | None = None) -> list[float] | None:
        # Use defaults if trainer_config not fully initialized
        eval_thresholds = self.trainer_config.get("eval_thresholds", [12.0, 6.0, 3.0, 1.5, 0.5, 0.0])
        theme = self.trainer_config.get("theme", "theme:normal")
        i = evaluation_class(points_lost, eval_thresholds)
        colors = Theme.EVAL_COLORS[theme]
        if show_dots_for_class is None or show_dots_for_class[i]:
            return colors[i]
        return None

    def draw_board(self, *_args: Any) -> None:
        if not (self.katrain and self.katrain.game):
            return
        katrain = self.katrain
        board_size_x, board_size_y = katrain.game.board_size

        with self.canvas.before:
            self.canvas.before.clear()

            grid_spaces_margin_x, grid_spaces_margin_y = self.get_grid_spaces_margins()
            h = round(self.height, 4)
            w = round(self.width, 4)
            x_grid_spaces, y_grid_spaces = self.calculate_grid_spaces(
                board_size_x, board_size_y, grid_spaces_margin_x, grid_spaces_margin_y
            )
            self.grid_size = self.calculate_grid_size(w, h, x_grid_spaces, y_grid_spaces)
            board_width_with_margins, board_height_with_margins = self.calculate_board_margins(
                x_grid_spaces, y_grid_spaces, self.grid_size
            )
            extra_px_margin_x, extra_px_margin_y = self.calculate_extra_px_margins(
                w, h, board_width_with_margins, board_height_with_margins
            )
            self.stone_size = self.calculate_stone_size(self.grid_size)
            # if not initiated or if changed
            if (
                self.gridpos is None
                or abs(
                    self.pos[0]
                    + extra_px_margin_x
                    + math.floor(grid_spaces_margin_x[0] * self.grid_size + 0.5)
                    - self.initial_gridpos_x[0]
                )
                > 0.001
            ):
                self.initial_gridpos_x, self.initial_gridpos_y = self.initialize_gridpos_x_y(
                    board_size_x,
                    board_size_y,
                    grid_spaces_margin_x,
                    grid_spaces_margin_y,
                    extra_px_margin_x,
                    extra_px_margin_y,
                    self.grid_size,
                )
                if self.rotation_degree == 0:
                    self.initialize_gridpos()

            if (self.rotation_degree == 90 or self.rotation_degree == 270) and board_size_x != board_size_y:
                # Note that we use the board_size_y, board_size_x order for this rotation.
                x_grid_spaces, y_grid_spaces = self.calculate_grid_spaces(
                    board_size_y, board_size_x, grid_spaces_margin_x, grid_spaces_margin_y
                )
                self.grid_size = self.calculate_grid_size(w, h, x_grid_spaces, y_grid_spaces)
                self.stone_size = self.calculate_stone_size(self.grid_size)
                current_gridpos_x, current_gridpos_y = self.calculate_rotated_gridpos()
            else:
                current_gridpos_x = self.initial_gridpos_x[:]
                current_gridpos_y = self.initial_gridpos_y[:]

            # if window size got changed
            if (
                self.gridpos[0][0][0] not in current_gridpos_x
                or self.gridpos[0][0][1] not in current_gridpos_y
                or (
                    self.gridpos[len(self.gridpos) - 1][len(self.gridpos[0]) - 1][0] in current_gridpos_x
                    or self.gridpos[len(self.gridpos) - 1][len(self.gridpos[0]) - 1][1] in current_gridpos_y
                )
            ):
                self.resize_board()

            self.draw_board_background(
                katrain,
                current_gridpos_x,
                current_gridpos_y,
                x_grid_spaces,
                y_grid_spaces,
                grid_spaces_margin_x,
                grid_spaces_margin_y,
            )
            self.draw_lines(current_gridpos_x, current_gridpos_y)
            self.draw_star_points(board_size_x, board_size_y)
            self.draw_coordinates(current_gridpos_x, current_gridpos_y)

    def get_grid_spaces_margins(self) -> tuple[list[float], list[float]]:
        if self.draw_coords_enabled:
            grid_spaces_margin_x: list[float] = [1.5, 0.75]  # left, right
            grid_spaces_margin_y: list[float] = [1.5, 0.75]  # bottom, top
        else:  # no coordinates means remove the offset
            grid_spaces_margin_x = [0.75, 0.75]  # left, right
            grid_spaces_margin_y = [0.75, 0.75]  # bottom, top
        return grid_spaces_margin_x, grid_spaces_margin_y

    def calculate_grid_spaces(
        self, board_size_x: int, board_size_y: int, grid_spaces_margin_x: list[float], grid_spaces_margin_y: list[float]
    ) -> tuple[float, float]:
        x_grid_spaces = board_size_x - 1 + sum(grid_spaces_margin_x)
        y_grid_spaces = board_size_y - 1 + sum(grid_spaces_margin_y)

        return x_grid_spaces, y_grid_spaces

    def calculate_grid_size(self, width: float, height: float, x_grid_spaces: float, y_grid_spaces: float) -> int:
        # grid size is rounded to an integer to avoid rounding errors that
        # produce tiny gaps between shaded grid squares
        return math.floor(min(width / x_grid_spaces, height / y_grid_spaces) + 0.1)

    def calculate_board_margins(
        self, x_grid_spaces: float, y_grid_spaces: float, grid_size: float
    ) -> tuple[float, float]:
        board_width_with_margins = x_grid_spaces * grid_size
        board_height_with_margins = y_grid_spaces * grid_size

        return board_width_with_margins, board_height_with_margins

    def calculate_extra_px_margins(
        self, width: float, height: float, board_width_with_margins: float, board_height_with_margins: float
    ) -> tuple[float, float]:
        extra_px_margin_x = round((width - board_width_with_margins) / 2, 4)
        extra_px_margin_y = round((height - board_height_with_margins) / 2, 4)

        return extra_px_margin_x, extra_px_margin_y

    def calculate_stone_size(self, grid_size: float) -> float:
        return grid_size * Theme.STONE_SIZE

    def initialize_gridpos(self) -> None:
        self.gridpos = [[None for x in range(len(self.initial_gridpos_x))] for y in range(len(self.initial_gridpos_y))]
        # [[None]*len(self.initial_gridpos_x)]*len(self.initial_gridpos_y)
        for y in range(len(self.initial_gridpos_y)):
            for x in range(len(self.initial_gridpos_x)):
                self.gridpos[y][x] = [self.initial_gridpos_x[x], self.initial_gridpos_y[y]]

    def initialize_gridpos_x_y(
        self,
        board_size_x: int,
        board_size_y: int,
        grid_spaces_margin_x: list[float],
        grid_spaces_margin_y: list[float],
        extra_px_margin_x: float,
        extra_px_margin_y: float,
        grid_size: float,
    ) -> tuple[list[float], list[float]]:
        gridpos_x: list[float] = [
            round(self.pos[0] + extra_px_margin_x + math.floor((grid_spaces_margin_x[0] + i) * grid_size + 0.5), 4)
            for i in range(board_size_x)
        ]
        gridpos_y: list[float] = [
            round(self.pos[1] + extra_px_margin_y + math.floor((grid_spaces_margin_y[0] + i) * grid_size + 0.5), 4)
            for i in range(board_size_y)
        ]

        return gridpos_x, gridpos_y

    def calculate_rotated_gridpos(self) -> tuple[list[float], list[float]]:
        board_size_y, board_size_x = self.katrain.game.board_size
        grid_spaces_margin_x, grid_spaces_margin_y = self.get_grid_spaces_margins()
        h = round(self.height, 4)
        w = round(self.width, 4)

        x_grid_spaces, y_grid_spaces = self.calculate_grid_spaces(
            board_size_x, board_size_y, grid_spaces_margin_x, grid_spaces_margin_y
        )
        grid_size = self.calculate_grid_size(w, h, x_grid_spaces, y_grid_spaces)
        board_width_with_margins, board_height_with_margins = self.calculate_board_margins(
            x_grid_spaces, y_grid_spaces, grid_size
        )
        extra_px_margin_x, extra_px_margin_y = self.calculate_extra_px_margins(
            w, h, board_width_with_margins, board_height_with_margins
        )

        return self.initialize_gridpos_x_y(
            board_size_x,
            board_size_y,
            grid_spaces_margin_x,
            grid_spaces_margin_y,
            extra_px_margin_x,
            extra_px_margin_y,
            grid_size,
        )

    def resize_board(self) -> None:
        rotated_gridpos_x, rotated_gridpos_y = self.calculate_rotated_gridpos()

        current_gridpos_x: list[Any] = []
        current_gridpos_y: list[Any] = []

        for yi in range(len(self.gridpos)):
            for xi in range(len(self.gridpos[0])):
                current_gridpos_x.append(self.gridpos[yi][xi][0])
                current_gridpos_y.append(self.gridpos[yi][xi][1])
        sorted_current_gridpos_x: list[Any] = list(set(current_gridpos_x))
        sorted_current_gridpos_x.sort()
        sorted_current_gridpos_y: list[Any] = list(set(current_gridpos_y))
        sorted_current_gridpos_y.sort()

        for yi in range(len(self.gridpos)):
            for xi in range(len(self.gridpos[0])):
                index_x = sorted_current_gridpos_x.index(self.gridpos[yi][xi][0])
                index_y = sorted_current_gridpos_y.index(self.gridpos[yi][xi][1])
                if self.rotation_degree == 90 or self.rotation_degree == 270:
                    self.gridpos[yi][xi] = [rotated_gridpos_x[index_x], rotated_gridpos_y[index_y]]
                else:
                    self.gridpos[yi][xi] = [self.initial_gridpos_x[index_x], self.initial_gridpos_y[index_y]]

    def draw_board_background(
        self,
        katrain: Any,
        gridpos_x: list[float],
        gridpos_y: list[float],
        x_grid_spaces: float,
        y_grid_spaces: float,
        grid_spaces_margin_x: list[float],
        grid_spaces_margin_y: list[float],
    ) -> None:
        if katrain.game.insert_mode:
            Color(*Theme.INSERT_BOARD_COLOR_TINT)  # dreamy
        else:
            Color(*Theme.BOARD_COLOR_TINT)  # image is a bit too light
        Rectangle(
            pos=(
                gridpos_x[0] - self.grid_size * grid_spaces_margin_x[0],
                gridpos_y[0] - self.grid_size * grid_spaces_margin_y[0],
            ),
            size=(self.grid_size * x_grid_spaces, self.grid_size * y_grid_spaces),
            texture=cached_texture(Theme.BOARD_TEXTURE),
        )

    def draw_lines(self, gridpos_x: list[float], gridpos_y: list[float]) -> None:
        Color(*Theme.LINE_COLOR)
        for i in range(len(gridpos_x)):
            Line(points=[(gridpos_x[i], gridpos_y[0]), (gridpos_x[i], gridpos_y[-1])])
        for i in range(len(gridpos_y)):
            Line(points=[(gridpos_x[0], gridpos_y[i]), (gridpos_x[-1], gridpos_y[i])])

    def draw_star_points(self, board_size_x: int, board_size_y: int) -> None:
        def star_point_coords(size: int) -> list[int]:
            star_point_pos = 3 if size <= 11 else 4
            if size < 7:
                return []
            return [star_point_pos - 1, size - star_point_pos] + ([int(size / 2)] if size % 2 == 1 and size > 7 else [])

        starpt_size = self.grid_size * Theme.STARPOINT_SIZE
        for x in star_point_coords(board_size_x):
            for y in star_point_coords(board_size_y):
                draw_circle((self.gridpos[y][x][0], self.gridpos[y][x][1]), starpt_size, Theme.LINE_COLOR)

    def draw_coordinates(self, gridpos_x: list[float], gridpos_y: list[float]) -> None:
        if self.draw_coords_enabled:
            board_size_x, board_size_y = self.katrain.game.board_size
            Color(0.25, 0.25, 0.25)
            coord_offset = round(self.grid_size * 1.5 / 2, 12)

            if (self.rotation_degree == 90 or self.rotation_degree == 270) and board_size_x != board_size_y:
                board_size_y, board_size_x = self.katrain.game.board_size

            for i in range(board_size_x):
                draw_text(
                    pos=(gridpos_x[i], gridpos_y[0] - coord_offset),
                    text=self.get_x_coordinate_text(i, board_size_x),
                    font_size=self.grid_size / 1.5,
                    font_name="Roboto",
                )
            for i in range(board_size_y):
                draw_text(
                    pos=(gridpos_x[0] - coord_offset, gridpos_y[i]),
                    text=self.get_y_coordinate_text(i, board_size_y),
                    font_size=self.grid_size / 1.5,
                    font_name="Roboto",
                )

    def get_x_coordinate_text(self, i: int, board_size_x: int) -> str:
        x_text = Move.GTP_COORD[i]
        if self.rotation_degree == 90:
            x_text = str(i + 1)
        elif self.rotation_degree == 180:
            x_text = Move.GTP_COORD[board_size_x - i - 1]
        elif self.rotation_degree == 270:
            x_text = str(board_size_x - i)
        return x_text

    def get_y_coordinate_text(self, i: int, board_size_y: int) -> str:
        y_text = str(i + 1)
        if self.rotation_degree == 90:
            y_text = Move.GTP_COORD[board_size_y - i - 1]
        elif self.rotation_degree == 180:
            y_text = str(board_size_y - i)
        elif self.rotation_degree == 270:
            y_text = Move.GTP_COORD[i]
        return y_text

    def draw_board_contents(self, *_args: Any) -> None:
        if not (self.katrain and self.katrain.game):
            return
        katrain = self.katrain
        board_size_x, board_size_y = katrain.game.board_size
        if self.gridpos is None or len(self.gridpos) < board_size_y or len(self.gridpos[0]) < board_size_x:
            return  # race condition
        show_n_eval = self.trainer_config.get("eval_on_show_last", 3)
        ownership_grid = None
        loss_grid = None

        with self.canvas:
            self.canvas.clear()
            current_node = katrain.game.current_node

            # ownership - allow one move out of date for smooth animation,
            # drawn first so the board is shaded underneath all other elements.
            ownership = current_node.ownership or (current_node.parent and current_node.parent.ownership)
            if katrain.analysis_controls.ownership.active and ownership and not katrain.is_fog_active():
                if (
                    current_node.children
                    and katrain.controls.status_state[1] == STATUS_TEACHING
                    and current_node.children[-1].auto_undo
                    and current_node.children[-1].ownership
                ):  # loss
                    loss_grid = var_to_grid(
                        [a - b for a, b in zip(current_node.children[-1].ownership, ownership, strict=False)],
                        (board_size_x, board_size_y),
                    )
                    for y in range(board_size_y - 1, -1, -1):
                        for x in range(board_size_x):
                            loss_grid[y][x] = max(
                                0, (-1 if current_node.children[-1].move.player == "B" else 1) * loss_grid[y][x]
                            )
                    self.draw_territory(loss_grid, Theme.EVAL_COLORS[self.trainer_config["theme"]][1][:3])
                else:
                    ownership_grid = var_to_grid(ownership, (board_size_x, board_size_y))
                    self.draw_territory(ownership_grid)
            # stones
            # Phase 93: Fog of War also disables eval dots
            all_dots_off = not katrain.analysis_controls.eval.active or katrain.is_fog_active()
            has_stone: dict[Any, Any] = {}
            drawn_stone: dict[Any, Any] = {}
            for m in katrain.game.stones:
                has_stone[m.coords] = m.player

            show_dots_for = {
                p: self.trainer_config["eval_show_ai"] or katrain.players_info[p].human for p in Move.PLAYERS
            }
            show_dots_for_class = self.trainer_config["show_dots"]
            nodes = katrain.game.current_node.nodes_from_root
            realized_points_lost = None

            for i, node in enumerate(nodes[::-1]):  # reverse order!
                points_lost = node.points_lost
                evalscale = 1
                if points_lost and realized_points_lost:
                    if points_lost <= 0.5 and realized_points_lost <= 1.5:
                        evalscale = 0
                    else:
                        evalscale = min(1, max(0, realized_points_lost / points_lost))
                placements = node.placements
                for m in node.moves + placements:
                    new_move = (
                        current_node.move and m.coords == current_node.move.coords
                    ) and not current_node.ownership
                    if has_stone.get(m.coords) and not drawn_stone.get(m.coords):  # skip captures, last only for
                        move_eval_on = not all_dots_off and show_dots_for.get(m.player) and i < show_n_eval
                        if move_eval_on and points_lost is not None:
                            evalcol = self.eval_color(points_lost, show_dots_for_class)
                        else:
                            evalcol = None
                        inner = Theme.STONE_COLORS[m.opponent] if i == 0 and m not in placements else None
                        drawn_stone[m.coords] = m.player
                        self.draw_stone(
                            x=m.coords[0],
                            y=m.coords[1],
                            player=m.player,
                            innercol=inner,
                            evalcol=evalcol,
                            evalscale=evalscale,
                            ownership=(
                                ownership_grid[m.coords[1]][m.coords[0]]
                                if ownership_grid and not loss_grid and not new_move
                                else None
                            ),
                            loss=loss_grid[m.coords[1]][m.coords[0]] if loss_grid else None,
                            depth=node.depth if katrain.show_move_num else None,
                        )
                realized_points_lost = node.parent_realized_points_lost

            if katrain.game.current_node.is_root and katrain.debug_level >= 3:  # secret ;)
                for y in range(0, board_size_y):
                    evalcol = self.eval_color(16 * y / board_size_y)
                    self.draw_stone(0, y, "B", evalcol=evalcol, evalscale=y / (board_size_y - 1))
                    self.draw_stone(1, y, "B", innercol=Theme.STONE_COLORS["W"], evalcol=evalcol)
                    self.draw_stone(2, y, "W", evalcol=evalcol, evalscale=y / (board_size_y - 1))
                    self.draw_stone(3, y, "W", innercol=Theme.STONE_COLORS["B"], evalcol=evalcol)

            # Phase 92c: Draw beginner hint highlight
            self.draw_beginner_hint_highlight()

            policy = current_node.policy
            if (
                not policy
                and current_node.parent
                and current_node.parent.policy
                and katrain.last_player_info.ai
                and katrain.next_player_info.ai
            ):
                policy = (
                    current_node.parent.policy
                )  # in the case of AI self-play we allow the policy to be one step out of date

            # Guard pass_btn access - may be missing during initialization
            board_controls = getattr(katrain, "board_controls", None)
            pass_btn = getattr(board_controls, "pass_btn", None) if board_controls else None
            if pass_btn:
                pass_btn.canvas.after.clear()
            if katrain.analysis_controls.policy.active and policy and not katrain.is_fog_active():
                policy_grid = var_to_grid(policy, (board_size_x, board_size_y))
                best_move_policy = max(*policy)
                colors = Theme.EVAL_COLORS[self.trainer_config["theme"]]
                text_lb = 0.01 * 0.01
                for y in range(board_size_y - 1, -1, -1):
                    for x in range(board_size_x):
                        move_policy = policy_grid[y][x]
                        if move_policy < 0:
                            continue
                        pol_order = max(0, 5 + int(math.log10(max(1e-9, move_policy - 1e-9))))
                        if move_policy > text_lb:
                            draw_circle(
                                (self.gridpos[y][x][0], self.gridpos[y][x][1]),
                                self.stone_size * Theme.HINT_SCALE * 0.98,
                                Theme.APPROX_BOARD_COLOR,
                            )
                            scale = 0.95
                        else:
                            scale = 0.5
                        draw_circle(
                            (self.gridpos[y][x][0], self.gridpos[y][x][1]),
                            Theme.HINT_SCALE * self.stone_size * scale,
                            (*colors[pol_order][:3], Theme.POLICY_ALPHA),
                        )
                        if move_policy > text_lb:
                            Color(*Theme.HINT_TEXT_COLOR)
                            draw_text(
                                pos=(self.gridpos[y][x][0], self.gridpos[y][x][1]),
                                text=f"{100 * move_policy:.2f}"[:4] + "%",
                                font_name="Roboto",
                                font_size=self.grid_size / 4,
                                halign="center",
                            )
                        if move_policy == best_move_policy:
                            Color(*Theme.TOP_MOVE_BORDER_COLOR[:3], Theme.POLICY_ALPHA)
                            Line(
                                circle=(
                                    self.gridpos[y][x][0],
                                    self.gridpos[y][x][1],
                                    self.stone_size - dp(1.2),
                                ),
                                width=dp(2),
                            )

                if pass_btn:
                    with pass_btn.canvas.after:
                        move_policy = policy[-1]
                        pol_order = 5 - int(-math.log10(max(1e-9, move_policy - 1e-9)))
                        if pol_order >= 0:
                            draw_circle(
                                (pass_btn.pos[0] + pass_btn.width / 2, pass_btn.pos[1] + pass_btn.height / 2),
                                pass_btn.height / 2,
                                (*colors[pol_order][:3], Theme.GHOST_ALPHA),
                            )

        self.redraw_hover_contents_trigger()

    # =========================================================================
    # Phase 92c: Beginner Hint Highlight
    # =========================================================================

    def _should_draw_beginner_highlight(self) -> bool:
        """Check if beginner hint highlight should be drawn (Phase 92c)."""
        katrain = self.katrain
        if not katrain:
            return False
        return should_draw_board_highlight(
            enabled=katrain.config("beginner_hints/enabled", False),
            mode=katrain.play_analyze_mode,
            board_highlight=katrain.config("beginner_hints/board_highlight", True),
        )

    def draw_beginner_hint_highlight(self) -> None:
        """Draw highlight circle at beginner hint coordinate (Phase 92c).

        Draws a semi-transparent circle behind the stone to indicate
        a beginner-relevant mistake or warning.
        """
        if not self._should_draw_beginner_highlight():
            return

        katrain = self.katrain
        node = katrain.game.current_node
        require_reliable = katrain.config("beginner_hints/require_reliable", True)
        hint = get_beginner_hint_cached(katrain.game, node, require_reliable=require_reliable)

        if hint is None or hint.coords is None:
            return

        board_size = katrain.game.board_size
        if not is_coords_valid(hint.coords, board_size):
            return

        x, y = hint.coords
        # gridpos[y][x] - note: y is first index
        pos = (self.gridpos[y][x][0], self.gridpos[y][x][1])
        draw_circle(pos, self.stone_size * 1.1, Theme.BEGINNER_HINT_COLOR)

    def draw_territory(self, grid: Any, loss_color: Any = None) -> None:
        if Theme.TERRITORY_DISPLAY == "marks":
            self.draw_territory_marks(grid, loss_color)
        else:
            self.draw_territory_color(grid, loss_color)

    def draw_territory_marks(self, grid: Any, loss_color: Any = None) -> None:
        board_size_x, board_size_y = self.katrain.game.board_size
        for y in range(board_size_y - 1, -1, -1):
            for x in range(board_size_x):
                if abs(grid[y][x]) < 0.01:
                    continue
                (ix_owner, other) = ("B", "W") if grid[y][x] > 0 else ("W", "B")
                if loss_color is None:
                    Color(*Theme.STONE_COLORS[ix_owner][:3], 1.0)
                else:
                    Color(*loss_color[:3], 1.0)
                rect_size = Theme.MARK_SIZE * min(1.0, abs(grid[y][x])) * self.stone_size * 2.0
                Rectangle(
                    pos=(
                        self.gridpos[y][x][0] - rect_size / 2,
                        self.gridpos[y][x][1] - rect_size / 2,
                    ),
                    # radius=[rect_size / 4],
                    size=(rect_size, rect_size),
                )

    def draw_territory_color(self, grid: Any, loss_color: Any = None) -> None:
        # This draws the expected black and white territories, or the loss during a teching game.
        # We draw a blended territory by creating a small texture of size 19x19 (more precisely board_size)
        # and painting it over the whole board. This causes Kivy to produce a smooth texture.

        # We add extra rows and columns (so the texture for a 19x19 board is actually 21x21)
        # in order to ensure smooth rolloff of the painted area at the edges. The alpha in the
        # extra rows is 0.

        board_size_x, board_size_y = self.katrain.game.board_size
        texture = Texture.create(size=(board_size_x + 2, board_size_y + 2), colorfmt="rgba")
        bytes = bytearray(4 * (board_size_y + 2) * (board_size_x + 2))
        for y in range(board_size_y + 2):
            for x in range(board_size_x + 2):
                x_coord = x - 1
                y_coord = y - 1

                if x_coord < 0 or x_coord > board_size_x - 1 or y_coord < 0 or y_coord > board_size_y - 1:
                    # We're in the extra rows/columns outside the board
                    alpha = 0
                else:
                    alpha = abs(grid[y_coord][x_coord])
                    if alpha > 1:
                        alpha = 1
                    if Theme.TERRITORY_DISPLAY == "blocks":
                        alpha = 1 if alpha > Theme.BLOCKS_THRESHOLD else 0
                alpha = alpha ** (1.0 / Theme.OWNERSHIP_GAMMA)

                x_coord = max(0, min(x_coord, board_size_x - 1))
                y_coord = max(0, min(y_coord, board_size_y - 1))

                ix_owner = "B" if grid[y_coord][x_coord] > 0 else "W"
                if loss_color is None:
                    pixel_list = list(Theme.OWNERSHIP_COLORS[ix_owner][:4])
                    pixel_list[3] *= alpha
                    pixel = tuple(pixel_list)
                else:
                    pixel = (*loss_color, Theme.HINTS_ALPHA * alpha)
                pixel_bytes = tuple(map(lambda p: int(p * 255), pixel))
                idx = 4 * y * (board_size_x + 2) + x * 4
                bytes[idx : idx + 4] = pixel_bytes

        if Theme.TERRITORY_DISPLAY == "blocks" or Theme.TERRITORY_DISPLAY == "shaded":
            texture.mag_filter = "nearest"
        texture.blit_buffer(bytes, colorfmt="rgba", bufferfmt="ubyte")
        Color(1, 1, 1, 1)
        lx = board_size_x - 1
        ly = board_size_y - 1
        left = min(self.gridpos[0][0][1], self.gridpos[ly][lx][1])
        bottom = min(self.gridpos[0][0][0], self.gridpos[ly][lx][0])

        # Our texture is 3 squares larger than the grid of lines: we added 2 rows/columns
        # for the edge blending, and the additional 1 is because the grid of
        # intersections is 1 smaller than the board state. We will shift the texture by 3/2 square
        # to align it.
        left = left - self.grid_size * 3 / 2
        bottom = bottom - self.grid_size * 3 / 2

        PushMatrix()

        Rotate(origin=(bottom, left), axis=(0, 0, 1), angle=-self.rotation_degree)
        if self.rotation_degree in (90, 180):
            Translate(-self.grid_size * (board_size_x + 2), 0, 0)
        if self.rotation_degree in (180, 270):
            Translate(0, -self.grid_size * (board_size_y + 2), 0)

        Rectangle(
            pos=(bottom, left),
            size=(self.grid_size * (board_size_x + 2), self.grid_size * (board_size_y + 2)),
            texture=texture,
        )

        PopMatrix()

    def draw_roi_box(self, region_of_interest: Any, width: float = 2) -> None:
        x1, x2, y1, y2 = region_of_interest
        x_start, y_start = self.gridpos[y1][x1]
        x_end, y_end = self.gridpos[y2][x2]

        Color(*Theme.REGION_BORDER_COLOR)
        Line(
            rectangle=(
                min(x_start, x_end) - self.grid_size / 3,
                min(y_start, y_end) - self.grid_size / 3,
                abs(x_start - x_end) + (2 / 3) * self.grid_size,
                abs(y_start - y_end) + (2 / 3) * self.grid_size,
            ),
            width=width,
        )

    def format_loss(self, x: float) -> str:
        if self.trainer_config.get("extra_precision"):
            if abs(x) < 0.005:
                return "0.0"
            if 0 < x <= 0.995:
                return "+" + f"{x:.2f}"[1:]
            elif -0.995 <= x < 0:
                return "-" + f"{x:.2f}"[2:]
        return f"{x:+.1f}"

    def _format_leela_stat(self, candidate: Any, stat_type: str) -> str:
        """Format a single Leela stat for display.

        Args:
            candidate: LeelaCandidate instance
            stat_type: One of LEELA_TOP_MOVE_* constants

        Returns:
            Formatted string, or "" for NOTHING
        """
        if stat_type == LEELA_TOP_MOVE_LOSS:
            return format_loss_est(candidate.loss_est)
        elif stat_type == LEELA_TOP_MOVE_WINRATE:
            if candidate.winrate is None:
                return "--"
            return format_winrate_pct(candidate.winrate)
        elif stat_type == LEELA_TOP_MOVE_VISITS:
            if candidate.visits is None:
                return "--"
            return format_leela_visits(candidate.visits)
        return ""  # NOTHING or unknown

    def draw_leela_candidates(self, leela_analysis: Any, low_visits_threshold: int = 25) -> tuple[Any, ...] | None:
        """Draw Leela candidate move markers with loss-based coloring.

        Args:
            leela_analysis: LeelaPositionEval from current_node.leela_analysis
            low_visits_threshold: Minimum visits for full-size marker

        Returns:
            Coordinates of the best move (top_move_coords), or None
        """
        if not leela_analysis or not leela_analysis.is_valid:
            return None

        top_move_coords = None
        candidates = leela_analysis.candidates
        current_node = self.katrain.game.current_node  # Phase 16: for PV registration

        # Cache config outside loop for performance (Phase 17, Phase 100: typed config)
        katrain = self.katrain
        leela_cfg = katrain.get_leela_config()
        top_show = leela_cfg.top_moves_show
        top_show_2 = leela_cfg.top_moves_show_secondary

        # Find max visits for scaling
        max((c.visits for c in candidates), default=1)

        # Debug: Print top 5 Leela candidate moves for color distribution analysis
        for idx, cand in enumerate(candidates[:5]):
            loss_val = cand.loss_est if cand.loss_est is not None else 0.0
            katrain.log(f"[DEBUG Leela] #{idx}: {cand.move:3s} Loss: {loss_val:6.2f}", OUTPUT_EXTRA_DEBUG)

        for i, candidate in enumerate(candidates):
            move = Move.from_gtp(candidate.move)
            if move.coords is None:
                continue

            # Phase 16: Register PV for hover display (same pattern as KataGo)
            # candidate.pv is List[str], same type as KataGo's move_dict["pv"]
            if candidate.pv:
                self.active_pv_moves.append((move.coords, candidate.pv, current_node))

            is_best = (i == 0) or (candidate.loss_est is not None and candidate.loss_est == 0.0)
            scale = Theme.HINT_SCALE
            text_on = True
            alpha = Theme.HINTS_ALPHA

            # Scale down low-visit candidates
            if candidate.visits < low_visits_threshold and not is_best:
                scale = Theme.UNCERTAIN_HINT_SCALE
                text_on = False
                alpha = Theme.HINTS_LO_ALPHA

            if scale <= 0:
                continue

            # Calculate marker size
            evalsize = self.stone_size * scale

            # Get color based on loss_est
            evalcol = loss_to_color(candidate.loss_est) if candidate.loss_est is not None else LEELA_COLOR_BEST

            # Draw board-colored circle to cover grid lines
            if text_on:
                draw_circle(
                    (
                        self.gridpos[move.coords[1]][move.coords[0]][0],
                        self.gridpos[move.coords[1]][move.coords[0]][1],
                    ),
                    self.stone_size * scale * 0.98,
                    Theme.APPROX_BOARD_COLOR,
                )

            # Draw colored marker
            Color(*evalcol[:3], alpha)
            Rectangle(
                pos=(
                    self.gridpos[move.coords[1]][move.coords[0]][0] - evalsize,
                    self.gridpos[move.coords[1]][move.coords[0]][1] - evalsize,
                ),
                size=(2 * evalsize, 2 * evalsize),
                texture=cached_texture(Theme.TOP_MOVE_TEXTURE),
            )

            # Draw text label
            if text_on:
                keys = {"size": self.grid_size / 3, "smallsize": self.grid_size / 3.33}

                # Phase 17: Dynamic stat selection
                line1 = self._format_leela_stat(candidate, top_show)
                line2 = self._format_leela_stat(candidate, top_show_2)

                # 2行目が空なら改行なし
                if line2:
                    fmt = "[size={size:.0f}]{line1}[/size]\n[size={smallsize:.0f}]{line2}[/size]"
                else:
                    fmt = "[size={size:.0f}]{line1}[/size]"

                Color(*Theme.HINT_TEXT_COLOR)
                draw_text(
                    pos=(
                        self.gridpos[move.coords[1]][move.coords[0]][0],
                        self.gridpos[move.coords[1]][move.coords[0]][1],
                    ),
                    text=fmt.format(line1=line1, line2=line2, **keys),
                    font_name="Roboto",
                    markup=True,
                    line_height=0.85,
                    halign="center",
                )

            # Mark best move with border
            if is_best:
                top_move_coords = move.coords
                Color(*Theme.TOP_MOVE_BORDER_COLOR)
                Line(
                    circle=(
                        self.gridpos[move.coords[1]][move.coords[0]][0],
                        self.gridpos[move.coords[1]][move.coords[0]][1],
                        self.stone_size - dp(1.2),
                    ),
                    width=dp(1.2),
                )

        return top_move_coords

    def draw_hover_contents(self, *_args: Any) -> None:
        ghost_alpha = Theme.GHOST_ALPHA
        katrain = self.katrain
        game_ended = katrain.game.end_result
        current_node = katrain.game.current_node
        next_player = current_node.next_player

        board_size_x, board_size_y = katrain.game.board_size
        if len(self.gridpos[0]) < board_size_x or len(self.gridpos) < board_size_y:
            return  # race condition

        with self.canvas.after:
            self.canvas.after.clear()

            self.active_pv_moves = []
            # hints or PV
            hint_moves = []
            if (
                katrain.analysis_controls.hints.active
                and not katrain.analysis_controls.policy.active
                and not game_ended
                and not katrain.is_fog_active()  # Phase 93: Fog of War
            ):
                hint_moves = current_node.candidate_moves
            elif katrain.controls.status_state[1] == STATUS_TEACHING:  # show score hint for teaching  undo
                hint_moves = [
                    m
                    for m in current_node.candidate_moves
                    for c in current_node.children
                    if c.move and c.auto_undo and c.move.gtp() == m["move"]
                ]

            # Apply PV filter to hint_moves (Phase 11)
            if hint_moves:
                pv_filter_level = katrain.config("general/pv_filter_level") or DEFAULT_PV_FILTER_LEVEL
                skill_preset = katrain.config("general/skill_preset")
                pv_filter_config = get_pv_filter_config(pv_filter_level, skill_preset=skill_preset)
                if pv_filter_config is not None:
                    hint_moves = filter_candidates_by_pv_complexity(hint_moves, pv_filter_config)

            top_move_coords = None
            child_moves = {c.move.gtp() for c in current_node.children if c.move}

            # Phase 100: Cache typed config for this draw call (no persistent cache)
            leela_cfg = katrain.get_leela_config()
            trainer_cfg = katrain.get_trainer_config()

            # Check if Leela mode is active and has analysis
            leela_enabled = leela_cfg.enabled
            leela_analysis = current_node.leela_analysis if leela_enabled else None

            # Phase 93: Fog of War hides Leela candidates too
            if leela_analysis and leela_analysis.is_valid and not katrain.is_fog_active():
                # Draw Leela candidate markers
                low_visits_threshold = trainer_cfg.low_visits
                top_move_coords = self.draw_leela_candidates(leela_analysis, low_visits_threshold)
            elif hint_moves:
                low_visits_threshold = trainer_cfg.low_visits
                top_moves_show = [
                    opt
                    for opt in [
                        katrain.config("trainer/top_moves_show"),
                        katrain.config("trainer/top_moves_show_secondary"),
                    ]
                    if opt in TOP_MOVE_OPTIONS and opt != TOP_MOVE_NOTHING
                ]
                for move_dict in hint_moves:
                    move = Move.from_gtp(move_dict["move"])
                    if move.coords is not None:
                        engine_best_move = move_dict.get("order", 99) == 0
                        scale = Theme.HINT_SCALE
                        text_on = True
                        alpha = Theme.HINTS_ALPHA
                        if (
                            move_dict["visits"] < low_visits_threshold
                            and not engine_best_move
                            and move_dict["move"] not in child_moves
                        ):
                            scale = Theme.UNCERTAIN_HINT_SCALE
                            text_on = False
                            alpha = Theme.HINTS_LO_ALPHA

                        if scale <= 0:  # if theme turns hints off, do not draw them
                            continue

                        if "pv" in move_dict:
                            self.active_pv_moves.append((move.coords, move_dict["pv"], current_node))
                        else:
                            katrain.log(f"PV missing for move_dict {move_dict}", OUTPUT_DEBUG)
                        evalsize = self.stone_size * scale
                        evalcol = self.eval_color(move_dict["pointsLost"])
                        if text_on and top_moves_show:  # remove grid lines using a board colored circle
                            draw_circle(
                                (
                                    self.gridpos[move.coords[1]][move.coords[0]][0],
                                    self.gridpos[move.coords[1]][move.coords[0]][1],
                                ),
                                self.stone_size * scale * 0.98,
                                Theme.APPROX_BOARD_COLOR,
                            )

                        if evalcol:
                            Color(*evalcol[:3], alpha)
                        else:
                            continue
                        Rectangle(
                            pos=(
                                self.gridpos[move.coords[1]][move.coords[0]][0] - evalsize,
                                self.gridpos[move.coords[1]][move.coords[0]][1] - evalsize,
                            ),
                            size=(2 * evalsize, 2 * evalsize),
                            texture=cached_texture(Theme.TOP_MOVE_TEXTURE),
                        )
                        if text_on and top_moves_show:  # TODO: faster if not sized?
                            keys: dict[str, Any] = {"size": self.grid_size / 3, "smallsize": self.grid_size / 3.33}
                            player_sign = current_node.player_sign(next_player)
                            if len(top_moves_show) == 1:
                                fmt = "[size={size:.0f}]{" + top_moves_show[0] + "}[/size]"
                            else:
                                fmt = (
                                    "[size={size:.0f}]{"
                                    + top_moves_show[0]
                                    + "}[/size]\n[size={smallsize:.0f}]{"
                                    + top_moves_show[1]
                                    + "}[/size]"
                                )

                            keys[TOP_MOVE_DELTA_SCORE] = self.format_loss(-move_dict["pointsLost"])
                            #                           def fmt_maybe_missing(arg,sign,digits=1):
                            #                               return str(round(sign*arg,digits)) if arg is not None else "N/A"

                            keys[TOP_MOVE_SCORE] = f"{player_sign * move_dict['scoreLead']:.1f}"
                            winrate = move_dict["winrate"] if player_sign == 1 else 1 - move_dict["winrate"]
                            keys[TOP_MOVE_WINRATE] = f"{winrate * 100:.1f}"
                            keys[TOP_MOVE_DELTA_WINRATE] = f"{-move_dict['winrateLost']:+.1%}"
                            keys[TOP_MOVE_VISITS] = format_visits(move_dict["visits"])

                            Color(*Theme.HINT_TEXT_COLOR)
                            draw_text(
                                pos=(
                                    self.gridpos[move.coords[1]][move.coords[0]][0],
                                    self.gridpos[move.coords[1]][move.coords[0]][1],
                                ),
                                text=fmt.format(**keys),
                                font_name="Roboto",
                                markup=True,
                                line_height=0.85,
                                halign="center",
                            )

                        if engine_best_move:
                            top_move_coords = move.coords
                            # Use the same color as the move marker for consistency
                            if evalcol:
                                Color(*evalcol)
                            else:
                                Color(*Theme.TOP_MOVE_BORDER_COLOR)
                            Line(
                                circle=(
                                    self.gridpos[move.coords[1]][move.coords[0]][0],
                                    self.gridpos[move.coords[1]][move.coords[0]][1],
                                    self.stone_size - dp(1.2),
                                ),
                                width=dp(1.2),
                            )

            # children of current moves in undo / review
            # Phase 93: Fog of War hides child markers (could reveal next move)
            if katrain.analysis_controls.show_children.active and not katrain.is_fog_active():
                for child_node in current_node.children:
                    move = child_node.move
                    if move and move.coords is not None:
                        if child_node.analysis_exists:
                            self.active_pv_moves.append(
                                (move.coords, [move.gtp()] + child_node.candidate_moves[0]["pv"], current_node)
                            )

                        if move.coords != top_move_coords:  # for contrast
                            dashed_width = 18
                            Color(*Theme.NEXT_MOVE_DASH_CONTRAST_COLORS[child_node.player])
                            Line(
                                circle=(
                                    self.gridpos[move.coords[1]][move.coords[0]][0],
                                    self.gridpos[move.coords[1]][move.coords[0]][1],
                                    self.stone_size - dp(1.2),
                                ),
                                width=dp(1.2),
                            )
                        else:
                            dashed_width = 10
                        Color(*Theme.STONE_COLORS[child_node.player])
                        for s in range(0, 360, 30):
                            Line(
                                circle=(
                                    self.gridpos[move.coords[1]][move.coords[0]][0],
                                    self.gridpos[move.coords[1]][move.coords[0]][1],
                                    self.stone_size - dp(1.2),
                                    s,
                                    s + dashed_width,
                                ),
                                width=dp(1.2),
                            )

            if self.selecting_region_of_interest and len(self.region_of_interest) == 4:
                self.draw_roi_box(self.region_of_interest, width=dp(2))
            else:
                # hover next move ghost stone
                if self.ghost_stone:
                    self.draw_stone(*self.ghost_stone, next_player, alpha=ghost_alpha)

                animating_pv = self.animating_pv
                if animating_pv:
                    pv, node, start_time, _ = animating_pv
                    up_to_move = self.get_animate_pv_index()
                    self.draw_pv(pv, node, up_to_move)

                if getattr(self.katrain.game, "region_of_interest", None):
                    self.draw_roi_box(self.katrain.game.region_of_interest, width=dp(1.25))

            # pass circle
            if current_node.is_pass or game_ended:
                if game_ended:
                    text = game_ended
                    katrain.controls.timer.paused = True
                else:
                    text = i18n._("board-pass")
                Color(*Theme.PASS_CIRCLE_COLOR)
                center = (self.initial_gridpos_x[int(board_size_x / 2)], self.initial_gridpos_y[int(board_size_y / 2)])
                size = min(self.width, self.height) * 0.227
                Ellipse(pos=(center[0] - size / 2, center[1] - size / 2), size=(size, size))
                Color(*Theme.PASS_CIRCLE_TEXT_COLOR)
                draw_text(pos=center, text=text, font_size=size * 0.25, halign="center")

        # Update PV animation state after canvas block
        self._update_pv_animation_state()

    def animate_pv(self, _dt: Any) -> None:
        if self.animating_pv:
            self.redraw_hover_contents_trigger()

    def draw_pv(self, pv: Any, node: Any, up_to_move: Any) -> None:
        katrain = self.katrain
        next_last_player = [node.next_player, Move.opponent_player(node.next_player)]
        cn = katrain.game.current_node
        if node != cn and node.parent != cn:
            hide_node = cn
            while hide_node and hide_node.move and hide_node != node:
                if not hide_node.move.is_pass:
                    pos = (
                        self.gridpos[hide_node.move.coords[1]][hide_node.move.coords[0]][0],
                        self.gridpos[hide_node.move.coords[1]][hide_node.move.coords[0]][1],
                    )
                    draw_circle(pos, self.stone_size, [0.85, 0.68, 0.40, 0.8])
                hide_node = hide_node.parent
        for i, gtpmove in enumerate(pv):
            if i > up_to_move:
                return
            move_player = next_last_player[i % 2]
            coords = Move.from_gtp(gtpmove).coords
            if coords is None:  # tee-hee
                board_controls = getattr(katrain, "board_controls", None)
                pass_btn = getattr(board_controls, "pass_btn", None) if board_controls else None
                if pass_btn:
                    sizefac = pass_btn.size[1] / 2 / self.stone_size
                    board_coords = (
                        pass_btn.pos[0] + pass_btn.size[0] + self.stone_size * sizefac,
                        pass_btn.pos[1] + pass_btn.size[1] / 2,
                    )
                else:
                    continue  # skip this move if pass_btn unavailable
            else:
                board_coords = (self.gridpos[coords[1]][coords[0]][0], self.gridpos[coords[1]][coords[0]][1])
                sizefac = 1

            stone_size = self.stone_size * sizefac
            Color(1, 1, 1, 1)
            Rectangle(  # not sure why the -1 here, but seems to center better
                pos=(board_coords[0] - stone_size - 1, board_coords[1] - stone_size),
                size=(2 * stone_size + 1, 2 * stone_size + 1),
                texture=cached_texture(Theme.STONE_TEXTURE[move_player]),
            )
            Color(*Theme.PV_TEXT_COLORS[move_player])
            draw_text(pos=board_coords, text=str(i + 1), font_size=self.grid_size * sizefac / 1.45, font_name="Roboto")

    def set_animating_pv(self, pv: Any, node: Any) -> None:
        self.animating_pv_index = None
        if pv is None:
            self.animating_pv = None
        elif node is not None and (
            not self.animating_pv or not (self.animating_pv[0] == pv and self.animating_pv[1] == node)
        ):
            self.animating_pv = (pv, node, time.time(), self.last_mouse_pos)
        self.redraw_hover_contents_trigger()

    def adjust_animate_pv_index(self, delta: int = 1) -> None:
        self.animating_pv_index = max(0, self.get_animate_pv_index() + delta)

    def get_animate_pv_index(self) -> float:
        if self.animating_pv_index is None:
            if self.animating_pv:
                pv, node, start_time, _ = self.animating_pv
                delay = self.katrain.config("general/anim_pv_time", 0.5)
                return float(min(len(pv), (time.time() - start_time) / max(delay, 0.1)))
            else:
                return 0.0

        return float(self.animating_pv_index)

    def rotate_gridpos(self) -> None:
        board_size_x, board_size_y = self.katrain.game.board_size
        if board_size_x != board_size_y:
            if self.rotation_degree == 90 or self.rotation_degree == 270:
                rotated_gridpos_x, rotated_gridpos_y = self.calculate_rotated_gridpos()
                diff = round(abs(rotated_gridpos_x[0] - rotated_gridpos_y[0]), 4)
                x0 = rotated_gridpos_x[0]
                y0 = rotated_gridpos_y[0]
            else:
                diff = round(abs(self.initial_gridpos_x[0] - self.initial_gridpos_y[0]), 4)
                x0 = self.initial_gridpos_x[0]
                y0 = self.initial_gridpos_y[0]

            pos = copy.deepcopy(self.gridpos)
            for yi in range(len(self.gridpos)):
                for xi in range(len(self.gridpos[0])):
                    if self.rotation_degree == 90 or self.rotation_degree == 270:
                        gridpos_x = pos[len(self.gridpos) - 1 - yi][:]
                    else:
                        gridpos_x = pos[yi][:]
                        gridpos_x.reverse()
                    x = pos[yi][xi][1]
                    y = gridpos_x[xi][0]
                    if x0 > y0:
                        x = round(x + diff, 4)
                        y = round(y - diff, 4)
                    elif y0 > x0:
                        x = round(x - diff, 4)
                        y = round(y + diff, 4)
                    self.gridpos[yi][xi] = [x, y]
        else:
            # This is a rot90 for list of lists. Based on the code found in
            # stackoverflow.com/questions/8421337/rotating-a-two-dimensional-array-in-python
            self.gridpos = list(list(x) for x in zip(*reversed(self.gridpos), strict=False))

        self.rotation_degree += 90
        if self.rotation_degree == 360:
            self.rotation_degree = 0
        if board_size_x != board_size_y:
            self.resize_board()
        Clock.schedule_once(self.redraw)

    def show_pv_from_comments(self, pv_str: str) -> None:
        self.set_animating_pv(pv_str[1:].split(" "), self.katrain.controls.active_comment_node.parent)


class AnalysisDropDown(DropDown):
    def open_game_analysis_popup(self, *_args: Any) -> None:
        analysis_popup = I18NPopup(
            title_key="analysis:game", size=[dp(500), dp(350)], content=ReAnalyzeGamePopup(MDApp.get_running_app().gui)
        )
        analysis_popup.content.popup = analysis_popup
        analysis_popup.open()

    def open_report_popup(self, *_args: Any) -> None:
        report_popup = I18NPopup(
            title_key="analysis:report",
            size=[dp(750), dp(750)],
            content=GameReportPopup(katrain=MDApp.get_running_app().gui),
        )
        report_popup.content.popup = report_popup
        report_popup.open()

    def open_tsumego_frame_popup(self, *_args: Any) -> None:
        analysis_popup = I18NPopup(
            title_key="analysis:tsumegoframe", size=[dp(500), dp(350)], content=TsumegoFramePopup()
        )
        analysis_popup.content.popup = analysis_popup
        analysis_popup.content.katrain = MDApp.get_running_app().gui
        analysis_popup.open()


class AnalysisControls(MDBoxLayout):
    dropdown = ObjectProperty(None)
    is_open = BooleanProperty(False)
    mykatrain_is_open = BooleanProperty(False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.build_dropdown()

    def on_is_open(self, instance: Any, value: Any) -> None:
        if value:
            max_content_width = max(option.content_width for option in self.dropdown.container.children)
            self.dropdown.width = max_content_width
            self.dropdown.open(self.analysis_button)
        elif self.dropdown.attach_to:
            self.dropdown.dismiss()

    def on_mykatrain_is_open(self, instance: Any, value: Any) -> None:
        if value:
            if not hasattr(self, "mykatrain_dropdown") or not hasattr(self, "mykatrain_button"):
                self.mykatrain_is_open = False
                return
            if self.mykatrain_dropdown.container.children:
                max_content_width = max(option.content_width for option in self.mykatrain_dropdown.container.children)
                self.mykatrain_dropdown.width = max(max_content_width, 250)
            else:
                self.mykatrain_dropdown.width = 250
            self.mykatrain_dropdown.open(self.mykatrain_button)
        elif hasattr(self, "mykatrain_dropdown") and self.mykatrain_dropdown.attach_to:
            self.mykatrain_dropdown.dismiss()

    def close_dropdown(self, *largs: Any) -> None:
        self.is_open = False

    def close_mykatrain_dropdown(self, *largs: Any) -> None:
        self.mykatrain_is_open = False

    def toggle_dropdown(self, *largs: Any) -> None:
        self.is_open = not self.is_open

    def toggle_mykatrain_dropdown(self, *largs: Any) -> None:
        self.mykatrain_is_open = not self.mykatrain_is_open

    def build_dropdown(self) -> None:
        self.dropdown = AnalysisDropDown(auto_width=False)
        self.dropdown.bind(on_dismiss=self.close_dropdown)
        self.mykatrain_dropdown = MyKatrainDropDown(auto_width=False)
        self.mykatrain_dropdown.bind(on_dismiss=self.close_mykatrain_dropdown)


class MyKatrainDropDown(DropDown):
    """Dropdown menu for myKatrain extension features"""

    pass


class BadukPanControls(MDFloatLayout):
    engine_status_col = ListProperty(Theme.ENGINE_DOWN_COLOR)
    engine_status_pondering = NumericProperty(-1)
    queries_remaining = NumericProperty(0)

    def update_controls(self, gui: Any) -> None:
        """Update controls (prisoners, engine status) from GUI state."""
        game = gui.game
        if not game:
            return

        # Update prisoners
        prisoners = game.prisoner_count
        # Handle circle display if available
        circles = getattr(self, "circles", None)
        if circles and len(circles) == 2:
            try:
                top, bot = [w.__self__ for w in circles]
                if gui.next_player_info.player == "W":
                    top, bot = bot, top
                    gui.controls.players["W"].active = True
                    gui.controls.players["B"].active = False
                else:
                    gui.controls.players["W"].active = False
                    gui.controls.players["B"].active = True
                mid_container = getattr(self, "mid_circles_container", None)
                if mid_container:
                    mid_container.clear_widgets()
                    mid_container.add_widget(bot)
                    mid_container.add_widget(top)
            except (ValueError, AttributeError, TypeError) as e:
                gui.log(f"circles parsing failed: {e}", OUTPUT_DEBUG)
        else:
            if gui.next_player_info.player == "W":
                gui.controls.players["W"].active = True
                gui.controls.players["B"].active = False
            else:
                gui.controls.players["W"].active = False
                gui.controls.players["B"].active = True

        gui.controls.players["W"].captures = prisoners["W"]
        gui.controls.players["B"].captures = prisoners["B"]

        # Update engine status dot
        engine = gui.engine
        if not engine or not engine.katago_process or engine.katago_process.poll() is not None:
            self.engine_status_col = Theme.ENGINE_DOWN_COLOR
        elif engine.is_idle():
            self.engine_status_col = Theme.ENGINE_READY_COLOR
        else:
            self.engine_status_col = Theme.ENGINE_BUSY_COLOR
        if engine:
            self.queries_remaining = engine.queries_remaining()
