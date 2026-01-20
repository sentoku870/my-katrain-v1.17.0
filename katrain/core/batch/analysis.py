"""Single file analysis functions for batch processing.

This module contains functions to analyze individual SGF files using
either KataGo or Leela Zero engines.

All functions are Kivy-independent and can be used in headless contexts.
"""

from __future__ import annotations

import os
import time
import traceback
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, Union

from katrain.core.batch.helpers import parse_sgf_with_fallback

if TYPE_CHECKING:
    from katrain.core.base_katrain import KaTrainBase
    from katrain.core.engine import KataGoEngine
    from katrain.core.game import Game
    from katrain.core.leela.engine import LeelaEngine
    from katrain.core.leela.models import LeelaPositionEval
    from katrain.core.analysis.models import EvalSnapshot, MoveEval


def analyze_single_file(
    katrain: "KaTrainBase",
    engine: "KataGoEngine",
    sgf_path: str,
    output_path: Optional[str] = None,
    visits: Optional[int] = None,
    timeout: float = 600.0,
    cancel_flag: Optional[List[bool]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    save_sgf: bool = True,
    return_game: bool = False,
) -> "Union[bool, Optional[Game]]":
    """
    Analyze a single SGF file and optionally save with analysis data.

    Args:
        katrain: KaTrainBase instance
        engine: KataGo engine instance
        sgf_path: Path to input SGF file
        output_path: Path to save analyzed SGF (required if save_sgf=True)
        visits: Number of visits per move (None = use default)
        timeout: Maximum time to wait for analysis
        cancel_flag: Optional list [bool] - if cancel_flag[0] is True, abort
        log_cb: Optional callback for logging messages
        save_sgf: If True, save the analyzed SGF to output_path
        return_game: If True, return the Game object instead of bool

    Returns:
        If return_game=False: True if successful, False otherwise
        If return_game=True: Game object on success, None on failure
    """
    # Import here to avoid circular imports
    from katrain.core.game import Game

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    def fail_result() -> Union[bool, None]:
        return None if return_game else False

    def success_result(game_obj: "Game") -> Union[bool, "Game"]:
        return game_obj if return_game else True

    try:
        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("    Cancelled before start")
            return fail_result()

        # Determine step count based on options
        total_steps = 3 if not save_sgf else 4

        # Step 1: Parse SGF
        log(f"    [1/{total_steps}] Parsing SGF...")
        move_tree = parse_sgf_with_fallback(sgf_path, log_cb)
        if move_tree is None:
            log("    ERROR: Failed to parse SGF file")
            return fail_result()

        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("    Cancelled after parse")
            return fail_result()

        # Step 2: Create Game instance (this triggers analysis of all nodes)
        log(f"    [2/{total_steps}] Creating game and starting analysis...")
        game = Game(
            katrain=katrain,
            engine=engine,
            move_tree=move_tree,
            analyze_fast=False,
            sgf_filename=sgf_path,
        )
        katrain.game = game

        # If custom visits specified, trigger re-analysis with that visit count
        if visits is not None:
            game.analyze_extra("game", visits=visits)

        # Step 3: Wait for analysis to complete (with cancellation check)
        log(f"    [3/{total_steps}] Waiting for analysis to complete...")
        start_time = time.time()
        poll_interval = 0.5
        while not engine.is_idle():
            if cancel_flag and cancel_flag[0]:
                log("    Cancelled during analysis")
                return fail_result()
            if time.time() - start_time > timeout:
                log(f"    ERROR: Analysis timed out after {timeout}s")
                return fail_result()
            time.sleep(poll_interval)

        # Give a moment for final processing
        time.sleep(0.5)

        # Step 4: Save with analysis (KT property) - only if save_sgf is True
        if save_sgf:
            if not output_path:
                log("    ERROR: output_path required when save_sgf=True")
                return fail_result()

            log(f"    [4/{total_steps}] Saving analyzed SGF...")

            # Ensure output directory exists
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            # Get trainer config and enable analysis saving
            # Note: save_feedback must be a list of bools (one per evaluation class),
            # not a single bool. We use the existing config which already has the correct format.
            trainer_config = katrain.config("trainer", {})
            trainer_config["save_analysis"] = True
            trainer_config["save_marks"] = True
            # Ensure save_feedback is a list (enable all classes if not already set)
            if "save_feedback" not in trainer_config or not isinstance(trainer_config["save_feedback"], list):
                # Default: save feedback for all evaluation classes
                trainer_config["save_feedback"] = [True, True, True, True, True, True]

            game.write_sgf(output_path, trainer_config=trainer_config)

        return success_result(game)

    except Exception as e:
        # Never swallow exceptions silently - log full traceback
        error_tb = traceback.format_exc()
        log(f"    ERROR: {e}")
        log(f"    Traceback:\n{error_tb}")
        return fail_result()


def analyze_single_file_leela(
    katrain: "KaTrainBase",
    leela_engine: "LeelaEngine",
    sgf_path: str,
    output_path: Optional[str] = None,
    visits: Optional[int] = None,
    file_timeout: float = 600.0,
    per_move_timeout: float = 30.0,
    cancel_flag: Optional[List[bool]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    save_sgf: bool = True,
    return_game: bool = False,
) -> "Union[bool, Tuple[Optional[Game], EvalSnapshot]]":
    """
    Analyze a single SGF file using Leela Zero engine.

    Unlike KataGo which analyzes all moves in one request, Leela Zero
    analyzes positions one at a time. This function iterates through
    each move in the SGF and collects analysis.

    Args:
        katrain: KaTrainBase instance
        leela_engine: LeelaEngine instance
        sgf_path: Path to input SGF file
        output_path: Path to save analyzed SGF (required if save_sgf=True)
        visits: Number of visits per move (None = use engine default)
        file_timeout: Maximum total time for the entire file
        per_move_timeout: Maximum time per move analysis
        cancel_flag: Optional list [bool] - if cancel_flag[0] is True, abort
        log_cb: Optional callback for logging messages
        save_sgf: If True, save the analyzed SGF to output_path
        return_game: If True, return (Game, EvalSnapshot) instead of bool

    Returns:
        If return_game=False: True if successful, False otherwise
        If return_game=True: (Game, EvalSnapshot) on success, (None, empty) on failure

    Note:
        Leela Zero doesn't provide scoreLead, so MoveEval.score_loss will be None.
        Use MoveEval.leela_loss_est for loss-based analysis.
    """
    import threading

    # Import here to avoid circular imports
    from katrain.core.game import Game
    from katrain.core.analysis.models import EvalSnapshot, MoveEval
    from katrain.core.leela.models import LeelaPositionEval
    from katrain.core.leela.conversion import leela_position_to_move_eval

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    def fail_result() -> Union[bool, Tuple[None, EvalSnapshot]]:
        if return_game:
            return None, EvalSnapshot(moves=[])
        return False

    def success_result(game_obj: "Game", snapshot: "EvalSnapshot") -> Union[bool, Tuple["Game", "EvalSnapshot"]]:
        if return_game:
            return game_obj, snapshot
        return True

    try:
        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("    Cancelled before start")
            return fail_result()

        file_start_time = time.time()

        # Step 1: Parse SGF
        log("    [1/4] Parsing SGF...")
        move_tree = parse_sgf_with_fallback(sgf_path, log_cb)
        if move_tree is None:
            log("    ERROR: Failed to parse SGF file")
            return fail_result()

        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("    Cancelled after parse")
            return fail_result()

        # Step 2: Create Game instance (without triggering KataGo analysis)
        log("    [2/4] Creating game...")
        game = Game(
            katrain=katrain,
            engine=None,  # No KataGo engine
            move_tree=move_tree,
            analyze_fast=False,
            sgf_filename=sgf_path,
        )
        katrain.game = game

        # Get game info for analysis
        board_size = game.board_size[0]  # Assumes square board
        komi = game.komi

        # Step 3: Analyze each move with Leela
        log("    [3/4] Analyzing moves with Leela Zero...")

        # Collect all moves from main branch
        main_branch_nodes = []
        current = game.root
        while current:
            main_branch_nodes.append(current)
            children = current.children
            current = children[0] if children else None

        # Skip root node, process only move nodes
        move_nodes = [n for n in main_branch_nodes if n.move is not None]
        total_moves = len(move_nodes)

        if total_moves == 0:
            log("    No moves to analyze")
            return success_result(game, EvalSnapshot(moves=[]))

        log(f"    Found {total_moves} moves to analyze")

        # Collect evaluations for each position
        move_evals: List["MoveEval"] = []
        position_evals: List["LeelaPositionEval"] = []

        # Build position sequence (moves leading to each position)
        moves_sequence: List[List[Tuple[str, str]]] = []  # List of move lists
        current_moves: List[Tuple[str, str]] = []

        for node in move_nodes:
            player = node.player
            gtp_coord = node.move.gtp()
            current_moves = current_moves + [(player, gtp_coord)]
            moves_sequence.append(current_moves.copy())

        # Analyze each position
        for i, (node, moves_to_position) in enumerate(zip(move_nodes, moves_sequence)):
            # Check file timeout
            if time.time() - file_start_time > file_timeout:
                log(f"    ERROR: File timeout after {file_timeout}s at move {i + 1}")
                return fail_result()

            # Check for cancellation
            if cancel_flag and cancel_flag[0]:
                log(f"    Cancelled at move {i + 1}")
                return fail_result()

            # Request analysis
            result_holder: List[Optional["LeelaPositionEval"]] = [None]
            result_event = threading.Event()

            def on_result(eval_result: "LeelaPositionEval") -> None:
                result_holder[0] = eval_result
                result_event.set()

            # Analyze position AFTER the move was played
            leela_engine.request_analysis(
                moves=moves_to_position,
                callback=on_result,
                visits=visits,
                board_size=board_size,
                komi=komi,
            )

            # Wait for result with timeout
            if not result_event.wait(timeout=per_move_timeout):
                log(f"    WARNING: Move {i + 1} timed out, skipping")
                leela_engine.cancel_analysis()
                # Add empty eval
                position_evals.append(LeelaPositionEval(parse_error="timeout"))
                continue

            position_eval = result_holder[0]
            if position_eval is None:
                position_evals.append(LeelaPositionEval(parse_error="no result"))
            else:
                position_evals.append(position_eval)

            # Progress logging every 10 moves
            if (i + 1) % 10 == 0 or i + 1 == total_moves:
                log(f"    Analyzed {i + 1}/{total_moves} moves...")

        # Step 4: Convert to MoveEval
        log("    [4/4] Converting to evaluation data...")

        for i, (node, current_eval) in enumerate(zip(move_nodes, position_evals)):
            # Get parent eval (position before this move)
            parent_eval = position_evals[i - 1] if i > 0 else None

            # Skip if current eval has error
            if current_eval.parse_error:
                continue

            move_number = i + 1
            player = node.player
            gtp_coord = node.move.gtp()

            move_eval = leela_position_to_move_eval(
                parent_eval=parent_eval if parent_eval and not parent_eval.parse_error else None,
                current_eval=current_eval,
                move_number=move_number,
                player=player,
                played_move=gtp_coord,
            )
            move_evals.append(move_eval)

        # Create EvalSnapshot
        snapshot = EvalSnapshot(moves=move_evals)

        # Save SGF if requested (note: Leela analysis is in snapshot, not in game nodes)
        if save_sgf:
            if not output_path:
                log("    ERROR: output_path required when save_sgf=True")
                return fail_result()

            log("    Saving analyzed SGF...")

            # Ensure output directory exists
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            # Get trainer config for saving
            trainer_config = katrain.config("trainer", {})
            trainer_config["save_analysis"] = True
            trainer_config["save_marks"] = True
            if "save_feedback" not in trainer_config or not isinstance(trainer_config["save_feedback"], list):
                trainer_config["save_feedback"] = [True, True, True, True, True, True]

            game.write_sgf(output_path, trainer_config=trainer_config)

        return success_result(game, snapshot)

    except Exception as e:
        error_tb = traceback.format_exc()
        log(f"    ERROR: {e}")
        log(f"    Traceback:\n{error_tb}")
        return fail_result()
