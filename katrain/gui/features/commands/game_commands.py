# katrain/gui/features/commands/game_commands.py
from __future__ import annotations

"""Game-related command handlers extracted from KaTrainGui (Phase 41-B).

These functions handle undo/redo, navigation, and game state changes.
The ctx parameter is expected to be a KaTrainGui instance (satisfies FeatureContext).
"""

from typing import TYPE_CHECKING, Any

from kivy.clock import Clock

from katrain.core.notify_helpers import notify_game_changed

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui
    from katrain.core.sgf_parser import SGFNode


def do_undo(ctx: KaTrainGui, n_times: int | str = 1) -> None:
    """Undo moves.

    Args:
        ctx: KaTrainGui instance
        n_times: Number of moves to undo, or "smart" for automatic detection
    """
    from katrain.core.constants import MODE_PLAY

    if n_times == "smart":
        n_times = 1
        if ctx.play_analyze_mode == MODE_PLAY and ctx.last_player_info.ai and ctx.next_player_info.human:
            n_times = 2
    ctx.board_gui.animating_pv = None
    if ctx.game:
        ctx.game.undo(n_times)


def do_redo(ctx: KaTrainGui, n_times: int = 1) -> None:
    """Redo moves.

    Args:
        ctx: KaTrainGui instance
        n_times: Number of moves to redo
    """
    ctx.board_gui.animating_pv = None
    if ctx.game:
        ctx.game.redo(n_times)


def do_rotate(ctx: KaTrainGui) -> None:
    """Rotate the board view 90 degrees.

    Args:
        ctx: KaTrainGui instance
    """
    ctx.board_gui.rotate_gridpos()


def do_find_mistake(ctx: KaTrainGui, fn: str = "redo") -> None:
    """Advance to the next mistake in the game tree.

    Args:
        ctx: KaTrainGui instance
        fn: Game method to call (typically 'redo' or 'undo')
    """
    ctx.board_gui.animating_pv = None
    threshold = ctx.config("trainer/eval_thresholds")[-4]
    getattr(ctx.game, fn)(9999, stop_on_mistake=threshold)


def do_switch_branch(ctx: KaTrainGui, *args: Any) -> None:
    """Switch to a different SGF branch (variation).

    Args:
        ctx: KaTrainGui instance
        *args: Forwarded to MoveTree.switch_branch
    """
    ctx.board_gui.animating_pv = None
    ctx.controls.move_tree.switch_branch(*args)


def do_selfplay_setup(
    ctx: KaTrainGui,
    until_move: int | float,
    target_b_advantage: float | None = None,
) -> None:
    """Configure the game for self-play mode.

    Args:
        ctx: KaTrainGui instance
        until_move: Stop self-play after this many moves
        target_b_advantage: Target score advantage for black
    """
    if target_b_advantage is None:
        target_b_advantage = 0  # default to even
    ctx.engine.selfplay_until = until_move
    ctx.engine.target_b_advantage = target_b_advantage


def do_ai_move(ctx: KaTrainGui, node: Any = None) -> None:
    """Generate and play an AI move using the next player's strategy.

    Args:
        ctx: KaTrainGui instance
        node: Optional specific node to play from; defaults to current_node
    """
    from katrain.core.ai import generate_ai_move
    from katrain.core.constants import OUTPUT_ERROR

    if not ctx.game or (node is None or ctx.game.current_node == node):
        mode = ctx.next_player_info.strategy
        settings = ctx.config(f"ai/{mode}")
        if settings is not None:
            try:
                if ctx.game:
                    generate_ai_move(ctx.game, mode, settings)
            except Exception as e:
                ctx.log(str(e), OUTPUT_ERROR)
                ctx.controls.set_status(str(e))
        else:
            ctx.log(f"AI Mode {mode} not found!", OUTPUT_ERROR)


def do_play(ctx: KaTrainGui, coords: Any) -> None:
    """Play a stone at the given coordinates.

    Args:
        ctx: KaTrainGui instance
        coords: Board coordinates (tuple) or None for pass
    """
    from katrain.core.game import IllegalMoveException
    from katrain.core.lang import i18n
    from katrain.core.sgf_parser import Move
    from katrain.core.constants import STATUS_ERROR
    from katrain.gui.sound import play_sound
    from katrain.gui.theme import Theme

    ctx.board_gui.animating_pv = None
    if not ctx.game:
        return
    try:
        old_prisoner_count = ctx.game.prisoner_count["W"] + ctx.game.prisoner_count["B"]
        ctx.game.play(Move(coords, player=ctx.next_player_info.player))
        if old_prisoner_count < ctx.game.prisoner_count["W"] + ctx.game.prisoner_count["B"]:
            play_sound(Theme.CAPTURING_SOUND)
        elif ctx.game and not ctx.game.current_node.is_pass:
            ctx._play_stone_sound()
    except IllegalMoveException as e:
        ctx.controls.set_status(f"Illegal Move: {i18n._(str(e))}", STATUS_ERROR)


def do_tsumego_frame(ctx: KaTrainGui, ko: bool, margin: int) -> None:
    """Open a tsumego (life-and-death) frame for the current game.

    Args:
        ctx: KaTrainGui instance
        ko: Whether the tsumego allows ko
        margin: Margin around the tsumego
    """
    from katrain.core.constants import MODE_PLAY
    from katrain.core.tsumego_frame import tsumego_frame_from_katrain_game

    if not ctx.game or not ctx.game.stones:
        return

    black_to_play_p = ctx.next_player_info.player == "B"
    node, analysis_region = tsumego_frame_from_katrain_game(
        ctx.game, ctx.game.komi, black_to_play_p, ko_p=ko, margin=margin
    )
    ctx.game.set_current_node(node)
    if ctx.play_mode.mode == MODE_PLAY:
        ctx.play_mode.switch_ui_mode()  # go to analysis mode
    if analysis_region:
        flattened_region = [
            analysis_region[0][1],
            analysis_region[0][0],
            analysis_region[1][1],
            analysis_region[1][0],
        ]
        ctx.game.set_region_of_interest(tuple(flattened_region))  # type: ignore[arg-type]
    if ctx.game:
        node.analyze(ctx.game.engines[node.next_player])
    ctx.update_state(redraw_board=True)


def do_new_game(
    ctx: KaTrainGui,
    move_tree: SGFNode | None = None,
    analyze_fast: bool = False,
    sgf_filename: str | None = None,
) -> None:
    """Start a new game or load an SGF.

    Args:
        ctx: KaTrainGui instance
        move_tree: Optional move tree for loaded game
        analyze_fast: Whether to use fast analysis
        sgf_filename: Optional SGF filename
    """
    from katrain.core.constants import MODE_ANALYZE, MODE_PLAY, PLAYER_HUMAN, PLAYING_NORMAL
    from katrain.core.game import Game

    ctx.pondering = False
    # Phase 93: Disable Active Review on new game/SGF load - REMOVED (Slimming down)
    # ctx._disable_active_review_if_needed()
    # Phase 16: Clear resign hint tracking on new game
    ctx._leela_manager.clear_resign_hint_tracking()
    mode = ctx.play_analyze_mode
    if not getattr(ctx, "_suppress_play_mode_switch", False) and (
        (move_tree is not None and mode == MODE_PLAY) or (move_tree is None and mode == MODE_ANALYZE)
    ):
        ctx.play_mode.switch_ui_mode()  # for new game, go to play, for loaded, analyze
    ctx.board_gui.animating_pv = None
    ctx.board_gui.reset_rotation()
    if ctx.engine:
        ctx.engine.on_new_game()  # clear queries
    ctx.game = Game(
        ctx,
        ctx.engine,  # type: ignore[arg-type]
        move_tree=move_tree,  # type: ignore[arg-type]
        analyze_fast=analyze_fast or not move_tree,
        sgf_filename=sgf_filename,
    )
    for bw, player_info in ctx.players_info.items():
        player_info.sgf_rank = ctx.game.root.get_property(bw + "R")
        player_info.calculated_rank = None
        if sgf_filename is not None:  # load game->no ai player
            player_info.player_type = PLAYER_HUMAN
            player_info.player_subtype = PLAYING_NORMAL
        ctx.update_player(bw, player_type=player_info.player_type, player_subtype=player_info.player_subtype)
    # Build node list snapshot under game lock, then schedule UI update on main thread
    with ctx.game._lock:
        node_list: list[Any] = [ctx.game.root]
        node: Any = ctx.game.root
        while node.children:
            node = node.ordered_children[0]
            node_list.append(node)
    # Schedule graph update on main thread (this function may run in background thread)
    Clock.schedule_once(lambda _dt: ctx.controls.graph.set_nodes_from_list(node_list), 0)

    # Phase 105: GAME_CHANGED通知（キーワード引数必須）
    notify_game_changed(ctx, source="new_game")

    # update_state is thread-safe: uses message_queue internally
    ctx.update_state(redraw_board=True)
