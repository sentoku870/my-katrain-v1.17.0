# katrain/gui/badukpan_pv.py
#
# PV (principal variation) animation for BadukPanWidget (Phase 158+).
#
# Handles the animated playback of an engine's principal variation line:
# - Starting/stopping the animation clock
# - Computing the current animation index from elapsed time
# - Drawing the PV stones and move numbers
# - Triggering periodic redraws

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from kivy.clock import Clock
from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Rectangle

from katrain.core.game import Move
from katrain.gui.kivyutils import cached_texture, draw_circle, draw_text
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.badukpan import BadukPanWidget


# =============================================================================
# PV animation lifecycle
# =============================================================================


def start_pv_animation(widget: BadukPanWidget) -> None:
    """Start the PV animation clock (idempotent)."""
    if not widget._animate_interval:
        widget._animate_interval = Clock.schedule_interval(widget.animate_pv, 0.1)


def stop_pv_animation(widget: BadukPanWidget) -> None:
    """Stop the PV animation clock (idempotent)."""
    if widget._animate_interval:
        widget._animate_interval.cancel()
        widget._animate_interval = None


def update_pv_animation_state(widget: BadukPanWidget) -> None:
    """Start or stop the animation clock based on current PV state."""
    if widget.animating_pv:
        start_pv_animation(widget)
    elif widget._animate_interval:
        stop_pv_animation(widget)


# =============================================================================
# PV playback control
# =============================================================================


def set_animating_pv(widget: BadukPanWidget, pv: Any, node: Any) -> None:
    """Set or clear the currently animating PV sequence."""
    widget.animating_pv_index = None
    if pv is None:
        widget.animating_pv = None
    elif node is not None and (
        not widget.animating_pv or not (widget.animating_pv[0] == pv and widget.animating_pv[1] == node)
    ):
        widget.animating_pv = (pv, node, time.time(), widget.last_mouse_pos)
    widget.redraw_hover_contents_trigger()


def adjust_animate_pv_index(widget: BadukPanWidget, delta: int = 1) -> None:
    """Manually advance or rewind the PV animation index."""
    widget.animating_pv_index = max(0, get_animate_pv_index(widget) + delta)


def get_animate_pv_index(widget: BadukPanWidget) -> float:
    """Compute the current PV move index (manual or time-based)."""
    if widget.animating_pv_index is None:
        if widget.animating_pv:
            pv, _node, start_time, _ = widget.animating_pv
            delay = widget.katrain.config("general/anim_pv_time", 0.5)
            return float(min(len(pv), (time.time() - start_time) / max(delay, 0.1)))
        else:
            return 0.0

    return float(widget.animating_pv_index)


def animate_pv(widget: BadukPanWidget, _dt: Any) -> None:
    """Clock callback: trigger a hover redraw on each animation tick."""
    if widget.animating_pv:
        widget.redraw_hover_contents_trigger()


# =============================================================================
# PV rendering
# =============================================================================


def draw_pv(widget: BadukPanWidget, pv: Any, node: Any, up_to_move: Any) -> None:
    """Draw the PV line as a sequence of numbered stones up to up_to_move.

    Also draws a yellow-ish overlay on stones in the current branch that
    are NOT in the PV (to indicate divergence from the suggested line).
    """
    katrain = widget.katrain
    next_last_player = [node.next_player, Move.opponent_player(node.next_player)]
    cn = katrain.game.current_node
    if node != cn and node.parent != cn:
        hide_node = cn
        while hide_node and hide_node.move and hide_node != node:
            if not hide_node.move.is_pass:
                pos = (
                    widget.gridpos[hide_node.move.coords[1]][hide_node.move.coords[0]][0],
                    widget.gridpos[hide_node.move.coords[1]][hide_node.move.coords[0]][1],
                )
                draw_circle(pos, widget.stone_size, [0.85, 0.68, 0.40, 0.8])
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
                sizefac = pass_btn.size[1] / 2 / widget.stone_size
                board_coords = (
                    pass_btn.pos[0] + pass_btn.size[0] + widget.stone_size * sizefac,
                    pass_btn.pos[1] + pass_btn.size[1] / 2,
                )
            else:
                continue  # skip this move if pass_btn unavailable
        else:
            board_coords = (
                widget.gridpos[coords[1]][coords[0]][0],
                widget.gridpos[coords[1]][coords[0]][1],
            )
            sizefac = 1

        stone_size = widget.stone_size * sizefac
        Color(1, 1, 1, 1)
        Rectangle(  # not sure why the -1 here, but seems to center better
            pos=(board_coords[0] - stone_size - 1, board_coords[1] - stone_size),
            size=(2 * stone_size + 1, 2 * stone_size + 1),
            texture=cached_texture(Theme.STONE_TEXTURE[move_player]),
        )
        Color(*Theme.PV_TEXT_COLORS[move_player])
        draw_text(
            pos=board_coords,
            text=str(i + 1),
            font_size=widget.grid_size * sizefac / 1.45,
            font_name="Roboto",
        )


def show_pv_from_comments(widget: BadukPanWidget, pv_str: str) -> None:
    """Trigger PV playback from a comment string ('L B15 W3 ...')."""
    set_animating_pv(widget, pv_str[1:].split(" "), widget.katrain.controls.active_comment_node.parent)
