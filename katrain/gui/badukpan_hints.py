# katrain/gui/badukpan_hints.py
#
# Hint marker drawing for BadukPanWidget (Phase 158+: badukpan.py split).
#
# Handles all overlay / hint / marker rendering on top of the board:
# - Beginner hint highlight (Phase 92c)
# - Leela candidate markers
# - KataGo hint markers
# - Child node markers
# - Hover overlay (ghost stone + ROI)
# - Pass / game-ended circle

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Ellipse, Line, Rectangle
from kivy.metrics import dp

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
from katrain.core.utils import format_visits
from katrain.gui.kivyutils import cached_texture, draw_circle, draw_text
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.badukpan import BadukPanWidget


# =============================================================================
# Beginner hint highlight (Phase 92c)
# =============================================================================


def should_draw_beginner_highlight(widget: BadukPanWidget) -> bool:
    """Check if beginner hint highlight should be drawn (Phase 92c)."""
    katrain = widget.katrain
    if not katrain:
        return False
    return should_draw_board_highlight(
        enabled=katrain.config("beginner_hints/enabled", False),
        mode=katrain.play_analyze_mode,
        board_highlight=katrain.config("beginner_hints/board_highlight", True),
    )


def draw_beginner_hint_highlight(widget: BadukPanWidget) -> None:
    """Draw highlight circle at beginner hint coordinate (Phase 92c)."""
    if not should_draw_beginner_highlight(widget):
        return

    katrain = widget.katrain
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
    pos = (widget.gridpos[y][x][0], widget.gridpos[y][x][1])
    draw_circle(pos, widget.stone_size * 1.1, Theme.BEGINNER_HINT_COLOR)


# =============================================================================
# Leela candidate markers
# =============================================================================


def format_leela_stat(widget: BadukPanWidget, candidate: Any, stat_type: str) -> str:
    """Format a single Leela stat for display."""
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


def draw_leela_candidates(
    widget: BadukPanWidget, leela_analysis: Any, low_visits_threshold: int = 25
) -> tuple[Any, ...] | None:
    """Draw Leela candidate move markers with loss-based coloring.

    Returns:
        Coordinates of the best move, or None
    """
    if not leela_analysis or not leela_analysis.is_valid:
        return None

    top_move_coords = None
    candidates = leela_analysis.candidates
    current_node = widget.katrain.game.current_node  # Phase 16: for PV registration

    # Cache config outside loop for performance (Phase 17, Phase 100: typed config)
    katrain = widget.katrain
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
            widget.active_pv_moves.append((move.coords, candidate.pv, current_node))

        is_best = i == 0
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
        evalsize = widget.stone_size * scale

        # Get color based on loss_est
        evalcol = loss_to_color(candidate.loss_est) if candidate.loss_est is not None else LEELA_COLOR_BEST

        # Draw board-colored circle to cover grid lines
        if text_on:
            draw_circle(
                (
                    widget.gridpos[move.coords[1]][move.coords[0]][0],
                    widget.gridpos[move.coords[1]][move.coords[0]][1],
                ),
                widget.stone_size * scale * 0.98,
                Theme.APPROX_BOARD_COLOR,
            )

        # Draw colored marker
        Color(*evalcol[:3], alpha)
        Rectangle(
            pos=(
                widget.gridpos[move.coords[1]][move.coords[0]][0] - evalsize,
                widget.gridpos[move.coords[1]][move.coords[0]][1] - evalsize,
            ),
            size=(2 * evalsize, 2 * evalsize),
            texture=cached_texture(Theme.TOP_MOVE_TEXTURE),
        )

        # Draw text label
        if text_on:
            keys = {"size": widget.grid_size / 3, "smallsize": widget.grid_size / 3.33}

            # Phase 17: Dynamic stat selection
            line1 = format_leela_stat(widget, candidate, top_show)
            line2 = format_leela_stat(widget, candidate, top_show_2)

            # 2行目が空なら改行なし
            if line2:
                fmt = "[size={size:.0f}]{line1}[/size]\n[size={smallsize:.0f}]{line2}[/size]"
            else:
                fmt = "[size={size:.0f}]{line1}[/size]"

            Color(*Theme.HINT_TEXT_COLOR)
            draw_text(
                pos=(
                    widget.gridpos[move.coords[1]][move.coords[0]][0],
                    widget.gridpos[move.coords[1]][move.coords[0]][1],
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
                    widget.gridpos[move.coords[1]][move.coords[0]][0],
                    widget.gridpos[move.coords[1]][move.coords[0]][1],
                    widget.stone_size - dp(1.2),
                ),
                width=dp(1.2),
            )

    return top_move_coords


# =============================================================================
# Hover overlay orchestration
# =============================================================================


def draw_hover_contents(widget: BadukPanWidget, *_args: Any) -> None:
    """Orchestrator: draw all hover overlays on the board.

    Phase 158+: This was previously a single 239-line method on BadukPanWidget.
    Now delegates to focused helpers in this module and badukpan_pv.
    """
    ghost_alpha = Theme.GHOST_ALPHA
    katrain = widget.katrain
    game_ended = katrain.game.end_result
    current_node = katrain.game.current_node
    next_player = current_node.next_player

    board_size_x, board_size_y = katrain.game.board_size
    if len(widget.gridpos[0]) < board_size_x or len(widget.gridpos) < board_size_y:
        return  # race condition

    with widget.canvas.after:
        widget.canvas.after.clear()
        widget.active_pv_moves = []

        hint_moves = prepare_hint_moves(widget, current_node, game_ended)
        top_move_coords = draw_leela_or_kata_hints(widget, current_node, hint_moves, next_player)
        draw_children_markers(widget, current_node, top_move_coords)

        if widget.selecting_region_of_interest and len(widget.region_of_interest) == 4:
            from katrain.gui.badukpan_drawing import draw_roi_box  # late import

            draw_roi_box(widget, widget.region_of_interest, width=dp(2))
        else:
            draw_hover_overlay(widget, ghost_alpha, next_player)

        draw_pass_circle(widget, current_node, game_ended, board_size_x, board_size_y)

    # Update PV animation state after canvas block
    from katrain.gui.badukpan_pv import update_pv_animation_state

    update_pv_animation_state(widget)


def prepare_hint_moves(widget: BadukPanWidget, current_node: Any, game_ended: Any) -> list[dict[str, Any]]:
    """Collect and filter candidate moves for hover hints."""
    katrain = widget.katrain
    hint_moves: list[dict[str, Any]] = []
    if (
        katrain.analysis_controls.hints.active
        and not katrain.analysis_controls.policy.active
        and not game_ended
        and not katrain.is_fog_active()  # Phase 93: Fog of War
    ):
        hint_moves = current_node.candidate_moves
    elif katrain.controls.status_state[1] == STATUS_TEACHING:  # show score hint for teaching undo
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

    return hint_moves


def draw_leela_or_kata_hints(
    widget: BadukPanWidget, current_node: Any, hint_moves: list[dict[str, Any]], next_player: str
) -> Any:
    """Dispatch to Leela candidate drawing or KataGo hint drawing.

    Returns:
        top_move_coords: coords of the engine's best move (for contrast in child markers)
    """
    katrain = widget.katrain
    # Phase 100: Cache typed config for this draw call (no persistent cache)
    leela_cfg = katrain.get_leela_config()
    trainer_cfg = katrain.get_trainer_config()

    leela_enabled = leela_cfg.enabled
    leela_analysis = current_node.leela_analysis if leela_enabled else None

    # Phase 121: Prioritize Leela candidates. If Leela is enabled, suppress KataGo hints.
    if leela_enabled:
        hint_moves = []

    top_move_coords = None
    # Phase 93: Fog of War hides Leela candidates too
    if leela_analysis and leela_analysis.is_valid and not katrain.is_fog_active():
        low_visits_threshold = trainer_cfg.low_visits
        top_move_coords = draw_leela_candidates(widget, leela_analysis, low_visits_threshold)
    elif hint_moves:
        top_move_coords = draw_kata_hint_moves(
            widget, current_node, hint_moves, next_player, trainer_cfg.low_visits
        )
    return top_move_coords


def draw_kata_hint_moves(
    widget: BadukPanWidget,
    current_node: Any,
    hint_moves: list[dict[str, Any]],
    next_player: str,
    low_visits_threshold: int,
) -> Any:
    """Draw KataGo hint markers for each candidate move."""
    katrain = widget.katrain
    child_moves = {c.move.gtp() for c in current_node.children if c.move}
    top_moves_show = [
        opt
        for opt in [
            katrain.config("trainer/top_moves_show"),
            katrain.config("trainer/top_moves_show_secondary"),
        ]
        if opt in TOP_MOVE_OPTIONS and opt != TOP_MOVE_NOTHING
    ]
    top_move_coords = None
    for move_dict in hint_moves:
        top_move_coords = draw_kata_hint_marker(
            widget, current_node, next_player, move_dict, child_moves, top_moves_show, low_visits_threshold,
            top_move_coords,
        )
    return top_move_coords


def draw_kata_hint_marker(
    widget: BadukPanWidget,
    current_node: Any,
    next_player: str,
    move_dict: dict[str, Any],
    child_moves: set[str],
    top_moves_show: list[str],
    low_visits_threshold: int,
    top_move_coords: Any,
) -> Any:
    """Draw a single KataGo hint marker at the move's coordinates."""
    katrain = widget.katrain
    move = Move.from_gtp(move_dict["move"])
    if move.coords is None:
        return top_move_coords

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
        return top_move_coords

    if "pv" in move_dict:
        widget.active_pv_moves.append((move.coords, move_dict["pv"], current_node))
    else:
        katrain.log(f"PV missing for move_dict {move_dict}", OUTPUT_DEBUG)
    evalsize = widget.stone_size * scale
    from katrain.gui.badukpan_drawing import eval_color as _eval_color_helper

    evalcol = _eval_color_helper(widget, move_dict["pointsLost"])
    if text_on and top_moves_show:  # remove grid lines using a board colored circle
        draw_circle(
            (
                widget.gridpos[move.coords[1]][move.coords[0]][0],
                widget.gridpos[move.coords[1]][move.coords[0]][1],
            ),
            widget.stone_size * scale * 0.98,
            Theme.APPROX_BOARD_COLOR,
        )

    if evalcol:
        Color(*evalcol[:3], alpha)
    else:
        return top_move_coords
    Rectangle(
        pos=(
            widget.gridpos[move.coords[1]][move.coords[0]][0] - evalsize,
            widget.gridpos[move.coords[1]][move.coords[0]][1] - evalsize,
        ),
        size=(2 * evalsize, 2 * evalsize),
        texture=cached_texture(Theme.TOP_MOVE_TEXTURE),
    )
    if text_on and top_moves_show:
        keys: dict[str, Any] = {"size": widget.grid_size / 3, "smallsize": widget.grid_size / 3.33}
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

        from katrain.gui.badukpan_drawing import format_loss_str

        keys[TOP_MOVE_DELTA_SCORE] = format_loss_str(widget, -move_dict["pointsLost"])
        keys[TOP_MOVE_SCORE] = f"{player_sign * move_dict['scoreLead']:.1f}"
        winrate = move_dict["winrate"] if player_sign == 1 else 1 - move_dict["winrate"]
        keys[TOP_MOVE_WINRATE] = f"{winrate * 100:.1f}"
        keys[TOP_MOVE_DELTA_WINRATE] = f"{-move_dict['winrateLost']:+.1%}"
        keys[TOP_MOVE_VISITS] = format_visits(move_dict["visits"])

        Color(*Theme.HINT_TEXT_COLOR)
        draw_text(
            pos=(
                widget.gridpos[move.coords[1]][move.coords[0]][0],
                widget.gridpos[move.coords[1]][move.coords[0]][1],
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
                widget.gridpos[move.coords[1]][move.coords[0]][0],
                widget.gridpos[move.coords[1]][move.coords[0]][1],
                widget.stone_size - dp(1.2),
            ),
            width=dp(1.2),
        )
    return top_move_coords


def draw_children_markers(widget: BadukPanWidget, current_node: Any, top_move_coords: Any) -> None:
    """Show child node markers (next possible moves in undo/review)."""
    katrain = widget.katrain
    # Phase 93: Fog of War hides child markers (could reveal next move)
    if not (katrain.analysis_controls.show_children.active and not katrain.is_fog_active()):
        return
    for child_node in current_node.children:
        move = child_node.move
        if move and move.coords is not None:
            if child_node.analysis_exists:
                widget.active_pv_moves.append(
                    (move.coords, [move.gtp()] + child_node.candidate_moves[0]["pv"], current_node)
                )

            if move.coords != top_move_coords:  # for contrast
                dashed_width = 18
                Color(*Theme.NEXT_MOVE_DASH_CONTRAST_COLORS[child_node.player])
                Line(
                    circle=(
                        widget.gridpos[move.coords[1]][move.coords[0]][0],
                        widget.gridpos[move.coords[1]][move.coords[0]][1],
                        widget.stone_size - dp(1.2),
                    ),
                    width=dp(1.2),
                )
            else:
                dashed_width = 10
            Color(*Theme.STONE_COLORS[child_node.player])
            for s in range(0, 360, 30):
                Line(
                    circle=(
                        widget.gridpos[move.coords[1]][move.coords[0]][0],
                        widget.gridpos[move.coords[1]][move.coords[0]][1],
                        widget.stone_size - dp(1.2),
                        s,
                        s + dashed_width,
                    ),
                    width=dp(1.2),
                )


def draw_hover_overlay(widget: BadukPanWidget, ghost_alpha: float, next_player: str) -> None:
    """Draw hover overlay elements: ghost stone, PV animation, region-of-interest box."""
    # hover next move ghost stone
    if widget.ghost_stone:
        from katrain.gui.badukpan_drawing import draw_stone

        draw_stone(widget, *widget.ghost_stone, next_player, alpha=ghost_alpha)

    from katrain.gui.badukpan_pv import draw_pv, get_animate_pv_index

    animating_pv = widget.animating_pv
    if animating_pv:
        pv, node, _start_time, _ = animating_pv
        up_to_move = get_animate_pv_index(widget)
        draw_pv(widget, pv, node, up_to_move)

    if getattr(widget.katrain.game, "region_of_interest", None):
        from katrain.gui.badukpan_drawing import draw_roi_box

        draw_roi_box(widget, widget.katrain.game.region_of_interest, width=dp(1.25))


def draw_pass_circle(
    widget: BadukPanWidget,
    current_node: Any,
    game_ended: Any,
    board_size_x: int,
    board_size_y: int,
) -> None:
    """Draw the pass / game-ended circle in the center of the board."""
    if not (current_node.is_pass or game_ended):
        return
    katrain = widget.katrain
    if game_ended:
        text = game_ended
        katrain.controls.timer.paused = True
    else:
        text = i18n._("board-pass")
    Color(*Theme.PASS_CIRCLE_COLOR)
    center = (
        widget.initial_gridpos_x[int(board_size_x / 2)],
        widget.initial_gridpos_y[int(board_size_y / 2)],
    )
    size = min(widget.width, widget.height) * 0.227
    Ellipse(pos=(center[0] - size / 2, center[1] - size / 2), size=(size, size))
    Color(*Theme.PASS_CIRCLE_TEXT_COLOR)
    draw_text(pos=center, text=text, font_size=size * 0.25, halign="center")
