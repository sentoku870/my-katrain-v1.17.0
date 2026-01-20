# katrain/gui/features/commands/game_commands.py
"""Game-related command handlers extracted from KaTrainGui (Phase 41-B).

These functions handle undo/redo, navigation, and game state changes.
The ctx parameter is expected to be a KaTrainGui instance (satisfies FeatureContext).
"""

from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui


def do_undo(ctx: "KaTrainGui", n_times: Union[int, str] = 1) -> None:
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
    ctx.game.undo(n_times)


def do_redo(ctx: "KaTrainGui", n_times: int = 1) -> None:
    """Redo moves.

    Args:
        ctx: KaTrainGui instance
        n_times: Number of moves to redo
    """
    ctx.board_gui.animating_pv = None
    ctx.game.redo(n_times)


def do_new_game(
    ctx: "KaTrainGui",
    move_tree=None,
    analyze_fast: bool = False,
    sgf_filename: Optional[str] = None,
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
    # Phase 16: Clear resign hint tracking on new game
    ctx._leela_manager.clear_resign_hint_tracking()
    mode = ctx.play_analyze_mode
    if not getattr(ctx, "_suppress_play_mode_switch", False) and (
        (move_tree is not None and mode == MODE_PLAY) or (move_tree is None and mode == MODE_ANALYZE)
    ):
        ctx.play_mode.switch_ui_mode()  # for new game, go to play, for loaded, analyze
    ctx.board_gui.animating_pv = None
    ctx.board_gui.reset_rotation()
    ctx.engine.on_new_game()  # clear queries
    ctx.game = Game(
        ctx,
        ctx.engine,
        move_tree=move_tree,
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
    ctx.controls.graph.initialize_from_game(ctx.game.root)
    ctx.update_state(redraw_board=True)
