from __future__ import annotations

import copy
from typing import Any

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty
from kivy.uix.dropdown import DropDown
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.floatlayout import MDFloatLayout

from katrain.core.board_geometry import (
    compute_board_with_margins,
    compute_extra_px_margins,
    compute_grid_size,
    compute_grid_spaces,
    compute_initial_gridpos,
    compute_stone_size,
)
from katrain.core.constants import (
    MODE_PLAY,
    OUTPUT_DEBUG,
    OUTPUT_EXTRA_DEBUG,
    STATUS_TEACHING,
)
from katrain.core.game import Move
from katrain.core.lang import i18n
from katrain.core.utils import json_truncate_arrays
from katrain.gui.popups import GameReportPopup, I18NPopup, ReAnalyzeGamePopup, TsumegoFramePopup
from katrain.gui.theme import Theme


class BadukPanWidget(Widget):
    """Go board display widget.

    Phase 158+: The implementation of most methods has been extracted to
    sibling modules (badukpan_drawing, badukpan_hints, badukpan_pv) so the
    class itself remains a thin orchestration layer. Each public method is
    a one-line wrapper that delegates to a module-level helper, which
    preserves compatibility with KV files (``<BadukPanWidget>`` rules),
    ``__main__.py`` imports, and tests that instantiate this class directly.
    """

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

    # =================================================================
    # PV animation lifecycle (delegated to badukpan_pv)
    # =================================================================

    def _start_pv_animation(self) -> None:
        from katrain.gui.badukpan_pv import start_pv_animation

        start_pv_animation(self)

    def _stop_pv_animation(self) -> None:
        from katrain.gui.badukpan_pv import stop_pv_animation

        stop_pv_animation(self)

    def _update_pv_animation_state(self) -> None:
        from katrain.gui.badukpan_pv import update_pv_animation_state

        update_pv_animation_state(self)

    # =================================================================
    # Rotation / coordinates toggle (small helpers stay inline)
    # =================================================================

    def reset_rotation(self) -> None:
        while self.rotation_degree:
            self.rotate_gridpos()

    def toggle_coordinates(self) -> bool:
        self.draw_coords_enabled = not self.draw_coords_enabled
        self.redraw_trigger()
        return self.draw_coords_enabled

    def get_enable_coordinates(self) -> bool:
        return self.draw_coords_enabled

    # =================================================================
    # Stone placement / touch input (stays inline - tightly coupled)
    # =================================================================

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

    # =================================================================
    # Drawing primitives (delegated to badukpan_drawing)
    # =================================================================

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
        from katrain.gui.badukpan_drawing import draw_stone as _draw_stone

        _draw_stone(self, x, y, player, alpha, innercol, evalcol, evalscale, scale, ownership, loss, depth)

    def eval_color(self, points_lost: float, show_dots_for_class: list[bool] | None = None) -> list[float] | None:
        from katrain.gui.badukpan_drawing import eval_color as _eval_color

        return _eval_color(self, points_lost, show_dots_for_class)

    def draw_board(self, *_args: Any) -> None:
        from katrain.gui.badukpan_drawing import draw_board as _draw_board

        _draw_board(self, *_args)

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
        return compute_grid_spaces(board_size_x, board_size_y, grid_spaces_margin_x, grid_spaces_margin_y)

    def calculate_grid_size(self, width: float, height: float, x_grid_spaces: float, y_grid_spaces: float) -> int:
        return compute_grid_size(width, height, x_grid_spaces, y_grid_spaces)

    def calculate_board_margins(
        self, x_grid_spaces: float, y_grid_spaces: float, grid_size: float
    ) -> tuple[float, float]:
        return compute_board_with_margins(x_grid_spaces, y_grid_spaces, grid_size)

    def calculate_extra_px_margins(
        self, width: float, height: float, board_width_with_margins: float, board_height_with_margins: float
    ) -> tuple[float, float]:
        return compute_extra_px_margins(width, height, board_width_with_margins, board_height_with_margins)

    def calculate_stone_size(self, grid_size: float) -> float:
        return compute_stone_size(grid_size, Theme.STONE_SIZE)

    def initialize_gridpos(self) -> None:
        self.gridpos = [[None for x in range(len(self.initial_gridpos_x))] for y in range(len(self.initial_gridpos_y))]
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
        return compute_initial_gridpos(
            self.pos,
            board_size_x,
            board_size_y,
            grid_spaces_margin_x,
            grid_spaces_margin_y,
            extra_px_margin_x,
            extra_px_margin_y,
            grid_size,
        )

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
        from katrain.gui.badukpan_drawing import draw_board_background as _draw_bg

        _draw_bg(self, katrain, gridpos_x, gridpos_y, x_grid_spaces, y_grid_spaces, grid_spaces_margin_x, grid_spaces_margin_y)

    def draw_lines(self, gridpos_x: list[float], gridpos_y: list[float]) -> None:
        from katrain.gui.badukpan_drawing import draw_lines as _draw_lines

        _draw_lines(self, gridpos_x, gridpos_y)

    def draw_star_points(self, board_size_x: int, board_size_y: int) -> None:
        from katrain.gui.badukpan_drawing import draw_star_points as _draw_stars

        _draw_stars(self, board_size_x, board_size_y)

    def draw_coordinates(self, gridpos_x: list[float], gridpos_y: list[float]) -> None:
        from katrain.gui.badukpan_drawing import draw_coordinates as _draw_coords

        _draw_coords(self, gridpos_x, gridpos_y)

    def get_x_coordinate_text(self, i: int, board_size_x: int) -> str:
        from katrain.gui.badukpan_drawing import get_x_coordinate_text as _get_x

        return _get_x(self, i, board_size_x)

    def get_y_coordinate_text(self, i: int, board_size_y: int) -> str:
        from katrain.gui.badukpan_drawing import get_y_coordinate_text as _get_y

        return _get_y(self, i, board_size_y)

    def draw_board_contents(self, *_args: Any) -> None:
        from katrain.gui.badukpan_drawing import draw_board_contents as _draw_contents

        _draw_contents(self, *_args)

    def draw_territory(self, grid: Any, loss_color: Any = None) -> None:
        from katrain.gui.badukpan_drawing import draw_territory as _draw_terr

        _draw_terr(self, grid, loss_color)

    def draw_territory_marks(self, grid: Any, loss_color: Any = None) -> None:
        from katrain.gui.badukpan_drawing import draw_territory_marks as _draw_marks

        _draw_marks(self, grid, loss_color)

    def draw_territory_color(self, grid: Any, loss_color: Any = None) -> None:
        from katrain.gui.badukpan_drawing import draw_territory_color as _draw_color

        _draw_color(self, grid, loss_color)

    def draw_roi_box(self, region_of_interest: Any, width: float = 2) -> None:
        from katrain.gui.badukpan_drawing import draw_roi_box as _draw_roi

        _draw_roi(self, region_of_interest, width)

    def format_loss(self, x: float) -> str:
        from katrain.gui.badukpan_drawing import format_loss_str as _format_loss

        return _format_loss(self, x)

    # =================================================================
    # Beginner hint highlight (delegated to badukpan_hints)
    # =================================================================

    def _should_draw_beginner_highlight(self) -> bool:
        from katrain.gui.badukpan_hints import should_draw_beginner_highlight as _should

        return _should(self)

    def draw_beginner_hint_highlight(self) -> None:
        from katrain.gui.badukpan_hints import draw_beginner_hint_highlight as _draw_hl

        _draw_hl(self)

    # =================================================================
    # Hint markers / hover overlay (delegated to badukpan_hints)
    # =================================================================

    def _format_leela_stat(self, candidate: Any, stat_type: str) -> str:
        from katrain.gui.badukpan_hints import format_leela_stat as _format

        return _format(self, candidate, stat_type)

    def draw_leela_candidates(self, leela_analysis: Any, low_visits_threshold: int = 25) -> tuple[Any, ...] | None:
        from katrain.gui.badukpan_hints import draw_leela_candidates as _draw_leela

        return _draw_leela(self, leela_analysis, low_visits_threshold)

    def draw_hover_contents(self, *_args: Any) -> None:
        from katrain.gui.badukpan_hints import draw_hover_contents as _draw_hover

        _draw_hover(self, *_args)

    def _prepare_hint_moves(self, current_node: Any, game_ended: Any) -> list[dict[str, Any]]:
        from katrain.gui.badukpan_hints import prepare_hint_moves as _prepare

        return _prepare(self, current_node, game_ended)

    def _draw_leela_or_kata_hints(
        self, current_node: Any, hint_moves: list[dict[str, Any]], next_player: str
    ) -> Any:
        from katrain.gui.badukpan_hints import draw_leela_or_kata_hints as _draw

        return _draw(self, current_node, hint_moves, next_player)

    def _draw_kata_hint_moves(
        self,
        current_node: Any,
        hint_moves: list[dict[str, Any]],
        next_player: str,
        low_visits_threshold: int,
    ) -> Any:
        from katrain.gui.badukpan_hints import draw_kata_hint_moves as _draw

        return _draw(self, current_node, hint_moves, next_player, low_visits_threshold)

    def _draw_kata_hint_marker(
        self,
        current_node: Any,
        next_player: str,
        move_dict: dict[str, Any],
        child_moves: set[str],
        top_moves_show: list[str],
        low_visits_threshold: int,
        top_move_coords: Any,
    ) -> Any:
        from katrain.gui.badukpan_hints import draw_kata_hint_marker as _draw

        return _draw(self, current_node, next_player, move_dict, child_moves, top_moves_show, low_visits_threshold, top_move_coords)

    def _draw_children_markers(self, current_node: Any, top_move_coords: Any) -> None:
        from katrain.gui.badukpan_hints import draw_children_markers as _draw

        _draw(self, current_node, top_move_coords)

    def _draw_hover_overlay(self, ghost_alpha: float, next_player: str) -> None:
        from katrain.gui.badukpan_hints import draw_hover_overlay as _draw

        _draw(self, ghost_alpha, next_player)

    def _draw_pass_circle(self, current_node: Any, game_ended: Any, board_size_x: int, board_size_y: int) -> None:
        from katrain.gui.badukpan_hints import draw_pass_circle as _draw

        _draw(self, current_node, game_ended, board_size_x, board_size_y)

    # =================================================================
    # PV animation (delegated to badukpan_pv)
    # =================================================================

    def animate_pv(self, _dt: Any) -> None:
        from katrain.gui.badukpan_pv import animate_pv as _animate

        _animate(self, _dt)

    def draw_pv(self, pv: Any, node: Any, up_to_move: Any) -> None:
        from katrain.gui.badukpan_pv import draw_pv as _draw_pv

        _draw_pv(self, pv, node, up_to_move)

    def set_animating_pv(self, pv: Any, node: Any) -> None:
        from katrain.gui.badukpan_pv import set_animating_pv as _set

        _set(self, pv, node)

    def adjust_animate_pv_index(self, delta: int = 1) -> None:
        from katrain.gui.badukpan_pv import adjust_animate_pv_index as _adj

        _adj(self, delta)

    def get_animate_pv_index(self) -> float:
        from katrain.gui.badukpan_pv import get_animate_pv_index as _get

        return _get(self)

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
        from katrain.gui.badukpan_pv import show_pv_from_comments as _show

        _show(self, pv_str)





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
    """myKatrain dropdown menu.

    Kept as an explicit (empty) subclass of DropDown so that the
    ``<MyKatrainDropDown>`` rule in katrain/gui/kv/menu.kv is applied
    via Kivy's class-name-based rule matching. Using a direct alias
    (``MyKatrainDropDown = DropDown``) breaks rule application because
    the instance's ``__name__`` would be ``"DropDown"``.
    """


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
        if not engine or not engine.is_alive():
            self.engine_status_col = Theme.ENGINE_DOWN_COLOR
        elif engine.is_idle():
            self.engine_status_col = Theme.ENGINE_READY_COLOR
        else:
            self.engine_status_col = Theme.ENGINE_BUSY_COLOR
        if engine:
            self.queries_remaining = engine.queries_remaining()
