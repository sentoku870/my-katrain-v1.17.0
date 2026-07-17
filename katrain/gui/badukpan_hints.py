# katrain/gui/badukpan_hints.py
#
# Hint marker drawing for BadukPanWidget (Phase 158+: badukpan.py split).
#
# Handles all overlay / hint / marker rendering on top of the board:
# - Beginner hint highlight (Phase 92c)
# - KataGo hint markers
# - Child node markers
# - Hover overlay (ghost stone + ROI)
# - Pass / game-ended circle
#
# Phase 171: Leela 経路（format_leela_stat, draw_leela_candidates,
# draw_leela_or_kata_hints）を削除し、KataGo 専用に整理。

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Ellipse, Line, Rectangle
from kivy.metrics import dp

from katrain.core.analysis import (
    DEFAULT_PV_FILTER_LEVEL,
    clip_pv_for_animation,
    filter_candidates_by_pv_complexity,
    get_pv_filter_config,
    resolve_skill_preset,
)
from katrain.core.beginner.hints import (
    get_beginner_hint_cached,
    is_coords_valid,
    should_draw_board_highlight,
)
from katrain.core.constants import (
    OUTPUT_DEBUG,
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
from katrain.core.study.kifunarabe import build_kifunarabe_options
from katrain.core.study.kifunarabe_constants import (
    KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT,
    KIFUNARABE_SHOW_ACTUAL_BORDER_KEY,
    KIFUNARABE_SHOW_DIGITS_DEFAULT,
    KIFUNARABE_SHOW_DIGITS_KEY,
    KIFUNARABE_UNIFORM_COLOR_DEFAULT,
    KIFUNARABE_UNIFORM_COLOR_KEY,
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
# Hover overlay orchestration
# =============================================================================


def draw_hover_contents(widget: BadukPanWidget, *_args: Any) -> None:
    """Orchestrator: draw all hover overlays on the board.

    Phase 158+: This was previously a single 239-line method on BadukPanWidget.
    Now delegates to focused helpers in this module and badukpan_pv.
    Phase 171: Leela 分岐を削除。常に KataGo のヒントを描画する。
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
        top_move_coords = draw_kata_hint_moves(
            widget, current_node, hint_moves, next_player, katrain.get_trainer_config().low_visits
        )
        draw_children_markers(widget, current_node, top_move_coords)
        # Phase 246-B (H1): draw a small "視点: B/W" watermark in the
        # bottom-left of the board whenever candidate markers are visible.
        # This makes explicit that ``pointsLost`` / ``winrateLost`` are
        # computed from the perspective of ``next_player`` (the player
        # about to move), so users don't mis-read the colours during
        # review / teaching.
        if hint_moves:
            draw_perspective_watermark(widget, next_player)

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

    # Phase 177: kifunarabe (棋譜並べ) mode drives its own choice set:
    # the recorded (actual) move plus (max_hints-1) KataGo top candidates.
    # Independent of the regular "Top Moves" toggle so the existing UX
    # stays exactly as before.
    kifu_max_hints = _kifunarabe_max_hints(katrain)
    in_kifu = bool(getattr(katrain, "kifunarabe_mode", False))
    if in_kifu and kifu_max_hints > 0 and not game_ended and not katrain.is_fog_active():
        option_gtps = build_kifunarabe_options(current_node, kifu_max_hints)
        hint_moves = _kifunarabe_options_to_hint_moves(current_node, option_gtps)
    elif (
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

    # Phase 177-G: kifu-mode markers are the user's *choice set*. Skip the
    # PV-complexity filter so the user always sees ``max_hints`` options,
    # not a filtered subset.
    if hint_moves and not in_kifu:
        pv_filter_level = katrain.config("general/pv_filter_level") or DEFAULT_PV_FILTER_LEVEL
        # Phase 229: derive skill preset from override + player_rank.
        skill_preset = resolve_skill_preset(
            katrain.config("general/skill_preset"),
            katrain.config("general/player_rank"),
        )
        # Phase 246-D (M1): pass board_size so the PV-length threshold
        # scales down for 9/13路 boards. Otherwise STRONG/EXPERT would
        # drop nearly all candidates on small boards.
        # Phase 246-E (L7): pass player_rank so the API can resolve the
        # preset internally — the manual ``resolve_skill_preset`` call
        # above is kept for back-compat with the analysis-side code.
        board_size_x, _ = katrain.game.board_size
        player_rank = katrain.config("general/player_rank")
        pv_filter_config = get_pv_filter_config(
            pv_filter_level,
            skill_preset=skill_preset,
            board_size=board_size_x,
            player_rank=player_rank,
        )
        if pv_filter_config is not None:
            hint_moves = filter_candidates_by_pv_complexity(hint_moves, pv_filter_config)

    return hint_moves


def _kifunarabe_options_to_hint_moves(current_node: Any, option_gtps: list[str]) -> list[dict[str, Any]]:
    """Convert a list of option GTPs into the marker-dict shape.

    Each output dict matches the schema that ``draw_kata_hint_marker``
    expects (``move``, ``order``, ``scoreLead``, ``winrate``,
    ``pointsLost``, ``relativePointsLost``, ``winrateLost``, ``visits``,
    ``pv``). When KataGo analysis is missing for an option we still emit a
    minimal dict so the marker draws.
    """
    if not option_gtps:
        return []

    # Build a lookup keyed by GTP for fast enrichment from KataGo results.
    candidates: list[dict[str, Any]] = []
    if getattr(current_node, "analysis_exists", False):
        raw = getattr(current_node, "candidate_moves", []) or []
        candidates = [c for c in raw if isinstance(c, dict)]
    by_gtp = {c.get("move"): c for c in candidates if c.get("move")}

    hint_moves: list[dict[str, Any]] = []
    for i, gtp in enumerate(option_gtps):
        cand = by_gtp.get(gtp, {})
        hint_moves.append(
            {
                "move": gtp,
                "order": i,
                "scoreLead": cand.get("scoreLead", 0),
                "winrate": cand.get("winrate", 0.5),
                "pointsLost": cand.get("pointsLost", 0.0),
                "relativePointsLost": cand.get("relativePointsLost", 0.0),
                "winrateLost": cand.get("winrateLost", 0.0),
                "visits": cand.get("visits", 0),
                "pv": cand.get("pv", []),
                "_kifunarabe_actual": (i == 0),
            }
        )
    return hint_moves


def _kifunarabe_max_hints(katrain: Any) -> int:
    """Return the active kifunarabe session's ``max_hints`` (0 if no session).

    Used by :func:`prepare_hint_moves` to decide whether to force candidate
    markers on regardless of the user's "Top Moves" toggle.
    """
    controller = getattr(katrain, "_kifunarabe_controller", None)
    if controller is None:
        return 0
    session = getattr(controller, "session", None)
    if session is None:
        return 0
    return int(getattr(getattr(session, "config", None), "max_hints", 0) or 0)


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

    # Phase 177-E: kifunarabe mode overrides text display / special border
    # so the choice set looks like a clean multiple-choice puzzle.
    in_kifu = any(m.get("_kifunarabe_actual") is not None for m in hint_moves)
    if in_kifu:
        show_digits = bool(katrain.config(KIFUNARABE_SHOW_DIGITS_KEY, KIFUNARABE_SHOW_DIGITS_DEFAULT))
        if show_digits:
            # Inherit the user's regular "trainer/top_moves_show" settings
            # so that flipping kifu digits ON renders the same numbers as
            # the regular KataGo hint path.
            top_moves_show: list[str] = [
                opt
                for opt in [
                    katrain.config("trainer/top_moves_show"),
                    katrain.config("trainer/top_moves_show_secondary"),
                ]
                if opt in TOP_MOVE_OPTIONS and opt != TOP_MOVE_NOTHING
            ]
        else:
            top_moves_show = []
    else:
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
            widget,
            current_node,
            next_player,
            move_dict,
            child_moves,
            top_moves_show,
            low_visits_threshold,
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
    move_gtp = move_dict.get("move")
    if not move_gtp:
        return top_move_coords
    move = Move.from_gtp(move_gtp)
    if move.coords is None:
        return top_move_coords

    # Phase 177-E: kifunarabe marker overrides -- the choice set must NOT
    # reveal the actual move, so ``engine_best_move`` is suppressed unless
    # the user explicitly opted back in via ``show_actual_border``.
    is_kifu_marker = move_dict.get("_kifunarabe_actual") is not None
    if is_kifu_marker:
        uniform_color = bool(katrain.config(KIFUNARABE_UNIFORM_COLOR_KEY, KIFUNARABE_UNIFORM_COLOR_DEFAULT))
        show_actual_border = bool(
            katrain.config(KIFUNARABE_SHOW_ACTUAL_BORDER_KEY, KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT)
        )
    else:
        uniform_color = False
        show_actual_border = True

    is_order_zero = move_dict.get("order", 99) == 0
    engine_best_move = is_order_zero and (not is_kifu_marker or show_actual_border)
    scale = Theme.HINT_SCALE
    text_on = True
    alpha = Theme.HINTS_ALPHA
    # Phase 177-G: kifu-mode markers must all render at the same scale.
    # Skip the visits-based size shrink so the choice set is uniform and
    # the "actual" move no longer stands out by being a touch larger.
    if (
        not is_kifu_marker
        and move_dict.get("visits", 0) < low_visits_threshold
        and not engine_best_move
        and move_gtp not in child_moves
    ):
        scale = Theme.UNCERTAIN_HINT_SCALE
        text_on = False
        alpha = Theme.HINTS_LO_ALPHA

    if scale <= 0:  # if theme turns hints off, do not draw them
        return top_move_coords

    if "pv" in move_dict and not is_kifu_marker:
        # Phase 246-C (M5): clip excessively long PV sequences via the
        # shared ``clip_pv_for_animation`` helper. Tests cover the
        # helper directly; the call site stays one-liner.
        pv = clip_pv_for_animation(move_dict["pv"])
        widget.active_pv_moves.append((move.coords, pv, current_node))
    elif "pv" not in move_dict and not is_kifu_marker:
        katrain.log(f"PV missing for move_dict {move_dict}", OUTPUT_DEBUG)
    evalsize = widget.stone_size * scale
    from katrain.gui.badukpan_drawing import eval_color as _eval_color_helper

    if uniform_color:
        # Phase 177-F: kifunarabe markers use a uniform translucent-black
        # colour so they read as "choice markers" without revealing any
        # KataGo ranking information.
        fill_rgba = Theme.KIFUNARABE_MARKER_FILL
        # The Kivy ``Color`` instruction wants rgb+alpha, and our
        # downstream alpha (``alpha`` below) is also taken from the same
        # fill. Collapse two redundancies to keep behaviour consistent.
        evalcol: tuple[float, ...] = tuple(fill_rgba)
        alpha = float(fill_rgba[3]) if len(fill_rgba) > 3 else 1.0
    else:
        ec = _eval_color_helper(widget, move_dict.get("pointsLost", 0.0))
        evalcol = tuple(ec) if ec is not None else (0.0, 0.0, 0.0, 1.0)
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

        keys[TOP_MOVE_DELTA_SCORE] = format_loss_str(widget, -move_dict.get("pointsLost", 0.0))
        keys[TOP_MOVE_SCORE] = f"{player_sign * move_dict.get('scoreLead', 0):.1f}"
        winrate = move_dict.get("winrate", 0.5) if player_sign == 1 else 1 - move_dict.get("winrate", 0.5)
        keys[TOP_MOVE_WINRATE] = f"{winrate * 100:.1f}"
        keys[TOP_MOVE_DELTA_WINRATE] = f"{-move_dict.get('winrateLost', 0.0):+.1%}"
        keys[TOP_MOVE_VISITS] = format_visits(move_dict.get("visits", 0))

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


# =============================================================================
# Phase 246-B (H1): Perspective watermark
# =============================================================================


def draw_perspective_watermark(widget: BadukPanWidget, next_player: str) -> None:
    """Draw a small "視点: B/W" watermark in the bottom-left of the board.

    Phase 246-B (H1): ``pointsLost`` / ``winrateLost`` on the candidate
    markers are computed from the perspective of the player about to
    move. This is implicit in the runtime but easy for a reviewer to
    misread. The watermark makes the perspective explicit whenever
    candidate markers are visible, without adding a new Kivy widget
    (canvas-only).

    Position: ~3% from the bottom-left of the widget, above the bottom
    coordinate gutter. Stays small enough not to obscure the board.
    """
    from katrain.core.lang import i18n as _i18n

    label = "B" if next_player == "B" else "W"
    text = _i18n._("board:perspective").format(player=label)
    pos_x = widget.x + widget.width * 0.02
    pos_y = widget.y + widget.height * 0.02
    Color(*Theme.PASS_CIRCLE_TEXT_COLOR)  # reuse pass-circle text colour (subtle grey/white)
    draw_text(
        pos=(pos_x, pos_y),
        text=text,
        font_size=widget.grid_size / 3.5,
        font_name=Theme.DEFAULT_FONT,
        halign="left",
        valign="bottom",
    )
