# katrain/gui/badukpan_drawing.py
#
# Drawing helpers for BadukPanWidget (Phase 158+: badukpan.py split).
#
# Module-level functions extracted from BadukPanWidget methods. Each function
# takes ``widget`` as the first argument so the original class methods can
# remain as thin one-line wrappers (preserving the public API used by KV files,
# tests, and __main__.py).
#
# Why module-level functions (not mixins):
# - Avoids circular imports (these helpers don't need BadukPanWidget's class)
# - Easier to unit test with a mock widget
# - Keeps the class hierarchy flat (no MRO surprises)
#
# Imports of BadukPanWidget are TYPE_CHECKING-only to avoid runtime cycles.

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from kivy.graphics.context_instructions import Color, PopMatrix, PushMatrix, Rotate, Translate
from kivy.graphics.texture import Texture
from kivy.graphics.vertex_instructions import Line, Rectangle
from kivy.metrics import dp

from katrain.core.board_geometry import (
    eval_color as _eval_color,
)
from katrain.core.board_geometry import (
    format_loss,
    x_coordinate_text,
    y_coordinate_text,
)
from katrain.core.constants import STATUS_TEACHING
from katrain.core.game import Move
from katrain.core.utils import var_to_grid
from katrain.gui.kivyutils import cached_texture, draw_circle, draw_text
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.badukpan import BadukPanWidget


# =============================================================================
# Stone drawing
# =============================================================================


def draw_stone(
    widget: BadukPanWidget,
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
    """Draw a single stone at grid position (x, y)."""
    stone_size = widget.stone_size * scale
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
        pos=(widget.gridpos[y][x][0] - stone_size, widget.gridpos[y][x][1] - stone_size),
        size=(2 * stone_size, 2 * stone_size),
        texture=cached_texture(Theme.STONE_TEXTURE[player]),
    )
    # Draw ownership marks on stones; the mark is a square with an outline.
    if (ownership is not None or loss is not None) and (
        Theme.STONE_MARKS == "all" or (Theme.STONE_MARKS == "weak" and player != owner)
    ):
        if ownership is not None:
            mark_color = (*Theme.STONE_COLORS[owner][:3], 1.0)
            other_color = (*Theme.STONE_COLORS[other][:3], 1.0)
            outline_color = tuple(
                map(lambda y: sum(y) / float(len(y)), zip(*(mark_color, other_color), strict=False))
            )
            mark_value = ownership
        else:
            assert loss is not None
            mark_color = (*Theme.EVAL_COLORS[widget.trainer_config["theme"]][1][:3], 1)
            outline_color = mark_color
            mark_value = min(1.0, loss)

        mark_size = Theme.MARK_SIZE * abs(mark_value) * widget.stone_size * 2.0
        Color(*mark_color)
        Rectangle(
            pos=(
                widget.gridpos[y][x][0] - mark_size / 2,
                widget.gridpos[y][x][1] - mark_size / 2,
            ),
            size=(mark_size, mark_size),
        )
        Color(*outline_color)
        Line(
            rectangle=(
                widget.gridpos[y][x][0] - mark_size / 2,
                widget.gridpos[y][x][1] - mark_size / 2,
                mark_size,
                mark_size,
            ),
            width=1.0,
        )
    if evalcol:
        eval_radius = math.sqrt(evalscale)  # scale area by evalscale
        evalsize = widget.stone_size * (
            Theme.EVAL_DOT_MIN_SIZE + eval_radius * (Theme.EVAL_DOT_MAX_SIZE - Theme.EVAL_DOT_MIN_SIZE)
        )
        Color(*evalcol)
        Rectangle(
            pos=(widget.gridpos[y][x][0] - evalsize, widget.gridpos[y][x][1] - evalsize),
            size=(2 * evalsize, 2 * evalsize),
            texture=cached_texture(Theme.EVAL_DOT_TEXTURE),
        )
    if innercol:
        Color(*innercol)
        inner_size = stone_size * 0.8
        Rectangle(
            pos=(widget.gridpos[y][x][0] - inner_size, widget.gridpos[y][x][1] - inner_size),
            size=(2 * inner_size, 2 * inner_size),
            texture=cached_texture(Theme.LAST_MOVE_TEXTURE),
        )

    if depth:
        text = str(depth)
        Color(*Theme.NUMBER_COLOR)
        draw_text(
            pos=widget.gridpos[y][x],
            text=text,
            font_size=widget.stone_size * 0.9,
            font_name="Roboto",
        )


def eval_color(
    widget: BadukPanWidget,
    points_lost: float,
    show_dots_for_class: list[bool] | None = None,
) -> list[float] | None:
    """Compute eval color (RGBA) for a given points_lost value."""
    # Use defaults if trainer_config not fully initialized
    eval_thresholds = widget.trainer_config.get("eval_thresholds", [12.0, 6.0, 3.0, 1.5, 0.5, 0.0])
    theme = widget.trainer_config.get("theme", "theme:normal")
    return _eval_color(points_lost, eval_thresholds, Theme.EVAL_COLORS[theme], show_dots_for_class)


# =============================================================================
# Board layout (lines, stars, coordinates)
# =============================================================================


def draw_board(widget: BadukPanWidget, *_args: Any) -> None:
    """Draw the empty board: background, grid lines, star points, coordinates."""
    if not (widget.katrain and widget.katrain.game):
        return
    katrain = widget.katrain
    board_size_x, board_size_y = katrain.game.board_size

    with widget.canvas.before:
        widget.canvas.before.clear()

        grid_spaces_margin_x, grid_spaces_margin_y = widget.get_grid_spaces_margins()
        h = round(widget.height, 4)
        w = round(widget.width, 4)
        x_grid_spaces, y_grid_spaces = widget.calculate_grid_spaces(
            board_size_x, board_size_y, grid_spaces_margin_x, grid_spaces_margin_y
        )
        widget.grid_size = widget.calculate_grid_size(w, h, x_grid_spaces, y_grid_spaces)
        board_width_with_margins, board_height_with_margins = widget.calculate_board_margins(
            x_grid_spaces, y_grid_spaces, widget.grid_size
        )
        extra_px_margin_x, extra_px_margin_y = widget.calculate_extra_px_margins(
            w, h, board_width_with_margins, board_height_with_margins
        )
        widget.stone_size = widget.calculate_stone_size(widget.grid_size)
        # if not initiated or if changed
        if (
            widget.gridpos is None
            or abs(
                widget.pos[0]
                + extra_px_margin_x
                + math.floor(grid_spaces_margin_x[0] * widget.grid_size + 0.5)
                - widget.initial_gridpos_x[0]
            )
            > 0.001
        ):
            widget.initial_gridpos_x, widget.initial_gridpos_y = widget.initialize_gridpos_x_y(
                board_size_x,
                board_size_y,
                grid_spaces_margin_x,
                grid_spaces_margin_y,
                extra_px_margin_x,
                extra_px_margin_y,
                widget.grid_size,
            )
            if widget.rotation_degree == 0:
                widget.initialize_gridpos()

        if (widget.rotation_degree == 90 or widget.rotation_degree == 270) and board_size_x != board_size_y:
            # Note that we use the board_size_y, board_size_x order for this rotation.
            x_grid_spaces, y_grid_spaces = widget.calculate_grid_spaces(
                board_size_y, board_size_x, grid_spaces_margin_x, grid_spaces_margin_y
            )
            widget.grid_size = widget.calculate_grid_size(w, h, x_grid_spaces, y_grid_spaces)
            widget.stone_size = widget.calculate_stone_size(widget.grid_size)
            current_gridpos_x, current_gridpos_y = widget.calculate_rotated_gridpos()
        else:
            current_gridpos_x = widget.initial_gridpos_x[:]
            current_gridpos_y = widget.initial_gridpos_y[:]

        # if window size got changed
        if (
            widget.gridpos[0][0][0] not in current_gridpos_x
            or widget.gridpos[0][0][1] not in current_gridpos_y
            or (
                widget.gridpos[len(widget.gridpos) - 1][len(widget.gridpos[0]) - 1][0]
                in current_gridpos_x
                or widget.gridpos[len(widget.gridpos) - 1][len(widget.gridpos[0]) - 1][1]
                in current_gridpos_y
            )
        ):
            widget.resize_board()

        draw_board_background(
            widget,
            katrain,
            current_gridpos_x,
            current_gridpos_y,
            x_grid_spaces,
            y_grid_spaces,
            grid_spaces_margin_x,
            grid_spaces_margin_y,
        )
        draw_lines(widget, current_gridpos_x, current_gridpos_y)
        draw_star_points(widget, board_size_x, board_size_y)
        draw_coordinates(widget, current_gridpos_x, current_gridpos_y)


def draw_board_background(
    widget: BadukPanWidget,
    katrain: Any,
    gridpos_x: list[float],
    gridpos_y: list[float],
    x_grid_spaces: float,
    y_grid_spaces: float,
    grid_spaces_margin_x: list[float],
    grid_spaces_margin_y: list[float],
) -> None:
    """Draw the wooden board background texture."""
    if katrain.game.insert_mode:
        Color(*Theme.INSERT_BOARD_COLOR_TINT)  # dreamy
    else:
        Color(*Theme.BOARD_COLOR_TINT)  # image is a bit too light
    Rectangle(
        pos=(
            gridpos_x[0] - widget.grid_size * grid_spaces_margin_x[0],
            gridpos_y[0] - widget.grid_size * grid_spaces_margin_y[0],
        ),
        size=(widget.grid_size * x_grid_spaces, widget.grid_size * y_grid_spaces),
        texture=cached_texture(Theme.BOARD_TEXTURE),
    )


def draw_lines(widget: BadukPanWidget, gridpos_x: list[float], gridpos_y: list[float]) -> None:
    """Draw grid lines."""
    Color(*Theme.LINE_COLOR)
    for i in range(len(gridpos_x)):
        Line(points=[(gridpos_x[i], gridpos_y[0]), (gridpos_x[i], gridpos_y[-1])])
    for i in range(len(gridpos_y)):
        Line(points=[(gridpos_x[0], gridpos_y[i]), (gridpos_x[-1], gridpos_y[i])])


def draw_star_points(widget: BadukPanWidget, board_size_x: int, board_size_y: int) -> None:
    """Draw star points (hoshi) on the board."""
    starpt_size = widget.grid_size * Theme.STARPOINT_SIZE

    def star_point_coords(size: int) -> list[int]:
        star_point_pos = 3 if size <= 11 else 4
        if size < 7:
            return []
        return [star_point_pos - 1, size - star_point_pos] + (
            [int(size / 2)] if size % 2 == 1 and size > 7 else []
        )

    for x in star_point_coords(board_size_x):
        for y in star_point_coords(board_size_y):
            draw_circle((widget.gridpos[y][x][0], widget.gridpos[y][x][1]), starpt_size, Theme.LINE_COLOR)


def draw_coordinates(widget: BadukPanWidget, gridpos_x: list[float], gridpos_y: list[float]) -> None:
    """Draw coordinate labels (A-T, 1-19) around the board edge."""
    if widget.draw_coords_enabled:
        board_size_x, board_size_y = widget.katrain.game.board_size
        Color(0.25, 0.25, 0.25)
        coord_offset = round(widget.grid_size * 1.5 / 2, 12)

        if (widget.rotation_degree == 90 or widget.rotation_degree == 270) and board_size_x != board_size_y:
            board_size_y, board_size_x = widget.katrain.game.board_size

        for i in range(board_size_x):
            draw_text(
                pos=(gridpos_x[i], gridpos_y[0] - coord_offset),
                text=get_x_coordinate_text(widget, i, board_size_x),
                font_size=widget.grid_size / 1.5,
                font_name="Roboto",
            )
        for i in range(board_size_y):
            draw_text(
                pos=(gridpos_x[0] - coord_offset, gridpos_y[i]),
                text=get_y_coordinate_text(widget, i, board_size_y),
                font_size=widget.grid_size / 1.5,
                font_name="Roboto",
            )


def get_x_coordinate_text(widget: BadukPanWidget, i: int, board_size_x: int) -> str:
    """Return coordinate label text for column i (with rotation applied)."""
    from katrain.core.game import Move  # local import to avoid top-level cycle

    return x_coordinate_text(i, board_size_x, widget.rotation_degree, Move.GTP_COORD)


def get_y_coordinate_text(widget: BadukPanWidget, i: int, board_size_y: int) -> str:
    """Return coordinate label text for row i (with rotation applied)."""
    from katrain.core.game import Move  # local import to avoid top-level cycle

    return y_coordinate_text(i, board_size_y, widget.rotation_degree, Move.GTP_COORD)


# =============================================================================
# Territory / ownership display
# =============================================================================


def draw_territory(widget: BadukPanWidget, grid: Any, loss_color: Any = None) -> None:
    """Draw territory shading (either as marks or as a colored overlay)."""
    if Theme.TERRITORY_DISPLAY == "marks":
        draw_territory_marks(widget, grid, loss_color)
    else:
        draw_territory_color(widget, grid, loss_color)


def draw_territory_marks(widget: BadukPanWidget, grid: Any, loss_color: Any = None) -> None:
    """Draw territory as small marks on each intersection."""
    board_size_x, board_size_y = widget.katrain.game.board_size
    for y in range(board_size_y - 1, -1, -1):
        for x in range(board_size_x):
            if abs(grid[y][x]) < 0.01:
                continue
            (ix_owner, _other) = ("B", "W") if grid[y][x] > 0 else ("W", "B")
            if loss_color is None:
                Color(*Theme.STONE_COLORS[ix_owner][:3], 1.0)
            else:
                Color(*loss_color[:3], 1.0)
            rect_size = Theme.MARK_SIZE * min(1.0, abs(grid[y][x])) * widget.stone_size * 2.0
            Rectangle(
                pos=(
                    widget.gridpos[y][x][0] - rect_size / 2,
                    widget.gridpos[y][x][1] - rect_size / 2,
                ),
                size=(rect_size, rect_size),
            )


def draw_territory_color(widget: BadukPanWidget, grid: Any, loss_color: Any = None) -> None:
    """Draw a blended territory texture over the whole board."""
    # This draws the expected black and white territories, or the loss during a teaching game.
    # We draw a blended territory by creating a small texture of size 19x19 (more precisely board_size)
    # and painting it over the whole board. This causes Kivy to produce a smooth texture.

    # We add extra rows and columns (so the texture for a 19x19 board is actually 21x21)
    # in order to ensure smooth rolloff of the painted area at the edges. The alpha in the
    # extra rows is 0.

    board_size_x, board_size_y = widget.katrain.game.board_size
    texture = Texture.create(size=(board_size_x + 2, board_size_y + 2), colorfmt="rgba")
    bytes_ = bytearray(4 * (board_size_y + 2) * (board_size_x + 2))
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
            bytes_[idx : idx + 4] = pixel_bytes

    if Theme.TERRITORY_DISPLAY == "blocks" or Theme.TERRITORY_DISPLAY == "shaded":
        texture.mag_filter = "nearest"
    texture.blit_buffer(bytes_, colorfmt="rgba", bufferfmt="ubyte")
    Color(1, 1, 1, 1)
    lx = board_size_x - 1
    ly = board_size_y - 1
    left = min(widget.gridpos[0][0][1], widget.gridpos[ly][lx][1])
    bottom = min(widget.gridpos[0][0][0], widget.gridpos[ly][lx][0])

    # Our texture is 3 squares larger than the grid of lines: we added 2 rows/columns
    # for the edge blending, and the additional 1 is because the grid of
    # intersections is 1 smaller than the board state. We will shift the texture by 3/2 square
    # to align it.
    left = left - widget.grid_size * 3 / 2
    bottom = bottom - widget.grid_size * 3 / 2

    PushMatrix()

    Rotate(origin=(bottom, left), axis=(0, 0, 1), angle=-widget.rotation_degree)
    if widget.rotation_degree in (90, 180):
        Translate(-widget.grid_size * (board_size_x + 2), 0, 0)
    if widget.rotation_degree in (180, 270):
        Translate(0, -widget.grid_size * (board_size_y + 2), 0)

    Rectangle(
        pos=(bottom, left),
        size=(widget.grid_size * (board_size_x + 2), widget.grid_size * (board_size_y + 2)),
        texture=texture,
    )

    PopMatrix()


def draw_roi_box(widget: BadukPanWidget, region_of_interest: Any, width: float = 2) -> None:
    """Draw a region-of-interest rectangle on the board."""
    x1, x2, y1, y2 = region_of_interest
    x_start, y_start = widget.gridpos[y1][x1]
    x_end, y_end = widget.gridpos[y2][x2]

    Color(*Theme.REGION_BORDER_COLOR)
    Line(
        rectangle=(
            min(x_start, x_end) - widget.grid_size / 3,
            min(y_start, y_end) - widget.grid_size / 3,
            abs(x_start - x_end) + (2 / 3) * widget.grid_size,
            abs(y_start - y_end) + (2 / 3) * widget.grid_size,
        ),
        width=width,
    )


# =============================================================================
# Helpers for formatted loss display
# =============================================================================


def format_loss_str(widget: BadukPanWidget, x: float) -> str:
    """Format a loss value (e.g. -1.23) with theme-aware precision."""
    return format_loss(x, extra_precision=bool(widget.trainer_config.get("extra_precision")))


# =============================================================================
# Board contents (the largest single draw routine, ~180 lines)
# =============================================================================


def draw_board_contents(widget: BadukPanWidget, *_args: Any) -> None:
    """Draw all board contents: territory, stones, policy, beginner highlight.

    This is the most expensive draw operation. It clears the canvas and
    re-draws everything from scratch based on the current game state.
    """
    if not (widget.katrain and widget.katrain.game):
        return
    katrain = widget.katrain
    board_size_x, board_size_y = katrain.game.board_size
    if widget.gridpos is None or len(widget.gridpos) < board_size_y or len(widget.gridpos[0]) < board_size_x:
        return  # race condition
    show_n_eval = widget.trainer_config.get("eval_on_show_last", 3)
    ownership_grid = None
    loss_grid = None

    with widget.canvas:
        widget.canvas.clear()
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
                            0,
                            (-1 if current_node.children[-1].move.player == "B" else 1) * loss_grid[y][x],
                        )
                widget.draw_territory(loss_grid, Theme.EVAL_COLORS[widget.trainer_config["theme"]][1][:3])
            else:
                ownership_grid = var_to_grid(ownership, (board_size_x, board_size_y))
                widget.draw_territory(ownership_grid)
        # stones
        # Phase 93: Fog of War also disables eval dots
        all_dots_off = not katrain.analysis_controls.eval.active or katrain.is_fog_active()
        has_stone: dict[Any, Any] = {}
        drawn_stone: dict[Any, Any] = {}
        for m in katrain.game.stones:
            has_stone[m.coords] = m.player

        show_dots_for = {
            p: widget.trainer_config["eval_show_ai"] or katrain.players_info[p].human for p in Move.PLAYERS
        }
        show_dots_for_class = widget.trainer_config["show_dots"]
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
                new_move = (current_node.move and m.coords == current_node.move.coords) and not current_node.ownership
                if has_stone.get(m.coords) and not drawn_stone.get(m.coords):  # skip captures, last only for ...
                    move_eval_on = not all_dots_off and show_dots_for.get(m.player) and i < show_n_eval
                    if move_eval_on and points_lost is not None:
                        evalcol = widget.eval_color(points_lost, show_dots_for_class)
                    else:
                        evalcol = None
                    inner = Theme.STONE_COLORS[m.opponent] if i == 0 and m not in placements else None
                    drawn_stone[m.coords] = m.player
                    draw_stone(
                        widget,
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
                evalcol = widget.eval_color(16 * y / board_size_y)
                draw_stone(widget, 0, y, "B", evalcol=evalcol, evalscale=y / (board_size_y - 1))
                draw_stone(widget, 1, y, "B", innercol=Theme.STONE_COLORS["W"], evalcol=evalcol)
                draw_stone(widget, 2, y, "W", evalcol=evalcol, evalscale=y / (board_size_y - 1))
                draw_stone(widget, 3, y, "W", innercol=Theme.STONE_COLORS["B"], evalcol=evalcol)

        # Phase 92c: Draw beginner hint highlight
        widget.draw_beginner_hint_highlight()

        policy = current_node.policy
        if (
            not policy
            and current_node.parent
            and current_node.parent.policy
            and katrain.last_player_info.ai
            and katrain.next_player_info.ai
        ):
            policy = current_node.parent.policy  # in the case of AI self-play we allow the policy to be one step out of date

        # Guard pass_btn access - may be missing during initialization
        board_controls = getattr(katrain, "board_controls", None)
        pass_btn = getattr(board_controls, "pass_btn", None) if board_controls else None
        if pass_btn:
            pass_btn.canvas.after.clear()
        if katrain.analysis_controls.policy.active and policy and not katrain.is_fog_active():
            policy_grid = var_to_grid(policy, (board_size_x, board_size_y))
            best_move_policy = max(*policy)
            colors = Theme.EVAL_COLORS[widget.trainer_config["theme"]]
            text_lb = 0.01 * 0.01
            for y in range(board_size_y - 1, -1, -1):
                for x in range(board_size_x):
                    move_policy = policy_grid[y][x]
                    if move_policy < 0:
                        continue
                    pol_order = max(0, 5 + int(math.log10(max(1e-9, move_policy - 1e-9))))
                    if move_policy > text_lb:
                        draw_circle(
                            (widget.gridpos[y][x][0], widget.gridpos[y][x][1]),
                            widget.stone_size * Theme.HINT_SCALE * 0.98,
                            Theme.APPROX_BOARD_COLOR,
                        )
                        scale = 0.95
                    else:
                        scale = 0.5
                    draw_circle(
                        (widget.gridpos[y][x][0], widget.gridpos[y][x][1]),
                        Theme.HINT_SCALE * widget.stone_size * scale,
                        (*colors[pol_order][:3], Theme.POLICY_ALPHA),
                    )
                    if move_policy > text_lb:
                        Color(*Theme.HINT_TEXT_COLOR)
                        draw_text(
                            pos=(widget.gridpos[y][x][0], widget.gridpos[y][x][1]),
                            text=f"{100 * move_policy:.2f}"[:4] + "%",
                            font_name="Roboto",
                            font_size=widget.grid_size / 4,
                            halign="center",
                        )
                    if move_policy == best_move_policy:
                        Color(*Theme.TOP_MOVE_BORDER_COLOR[:3], Theme.POLICY_ALPHA)
                        Line(
                            circle=(
                                widget.gridpos[y][x][0],
                                widget.gridpos[y][x][1],
                                widget.stone_size - dp(1.2),
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

    widget.redraw_hover_contents_trigger()
