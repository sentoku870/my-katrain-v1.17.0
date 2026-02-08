"""Single file analysis functions for batch processing.

This module contains functions to analyze individual SGF files using
the KataGo engine.

All functions are Kivy-independent and can be used in headless contexts.
"""

from __future__ import annotations

import os
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from katrain.core.batch.helpers import parse_sgf_with_fallback
from katrain.core.errors import AnalysisTimeoutError, SGFError
from katrain.core.game_node import GameNode


if TYPE_CHECKING:
    from katrain.core.base_katrain import KaTrainBase
    from katrain.core.engine import KataGoEngine
    from katrain.core.game import Game


def analyze_single_file(
    katrain: KaTrainBase,
    engine: KataGoEngine,
    sgf_path: str,
    output_path: str | None = None,
    visits: int | None = None,
    timeout: float = 600.0,
    cancel_flag: list[bool] | None = None,
    log_cb: Callable[[str], None] | None = None,
    save_sgf: bool = True,
    return_game: bool = False,
) -> bool | Game | None:
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

    def fail_result() -> bool | None:
        return None if return_game else False

    def success_result(game_obj: Game) -> bool | Game:
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
                raise AnalysisTimeoutError(
                    f"Analysis timed out after {timeout}s", user_message="Analysis timeout - engine may be unresponsive"
                )
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

    except SGFError as e:
        # Expected: External SGF file parse/structure error
        sgf_name = Path(sgf_path).name
        log(f"    SGF parse error ({sgf_name}): {e}")
        return fail_result()
    except OSError as e:
        # Expected: File I/O error (includes PermissionError, FileNotFoundError)
        sgf_name = Path(sgf_path).name
        log(f"    File I/O error ({sgf_name}): {e}")
        return fail_result()
    except UnicodeDecodeError as e:
        # Expected: Encoding mismatch in SGF file
        sgf_name = Path(sgf_path).name
        log(f"    Encoding error ({sgf_name}): {e}")
        return fail_result()
    except Exception as e:
        # Unexpected: Internal bug - traceback required
        sgf_name = Path(sgf_path).name
        log(f"    Unexpected error ({sgf_name}): {e}")
        log(f"    {traceback.format_exc()}")
        return fail_result()
