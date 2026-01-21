"""Batch analysis orchestration.

This module contains the main `run_batch()` function that orchestrates
batch SGF analysis across multiple files.

All functions are Kivy-independent and can be used in headless contexts.
Callbacks (progress_cb, log_cb) are used for UI integration - GUI code
should wrap these with Clock.schedule_once() for thread safety.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from katrain.core.batch.models import BatchResult, WriteError
from katrain.core.batch.helpers import (
    collect_sgf_files_recursive,
    has_analysis,
    choose_visits_for_sgf,
    safe_write_file,
    sanitize_filename,
    get_unique_filename,
    DEFAULT_TIMEOUT_SECONDS,
)
from katrain.core.eval_metrics import DEFAULT_SKILL_PRESET

if TYPE_CHECKING:
    from katrain.core.base_katrain import KaTrainBase
    from katrain.core.engine import KataGoEngine
    from katrain.core.leela.engine import LeelaEngine


def run_batch(
    katrain: "KaTrainBase",
    engine: "KataGoEngine",
    input_dir: str,
    output_dir: Optional[str] = None,
    visits: Optional[int] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    skip_analyzed: bool = False,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    cancel_flag: Optional[List[bool]] = None,
    # Extended options for karte/summary generation
    save_analyzed_sgf: bool = True,
    generate_karte: bool = False,
    generate_summary: bool = False,
    karte_player_filter: Optional[str] = None,
    min_games_per_player: int = 3,
    skill_preset: str = DEFAULT_SKILL_PRESET,
    # Variable visits options
    variable_visits: bool = False,
    jitter_pct: float = 10.0,
    deterministic: bool = True,
    # Engine selection (Phase 36)
    analysis_engine: str = "katago",
    leela_engine: Optional["LeelaEngine"] = None,
    per_move_timeout: float = 30.0,
) -> BatchResult:
    """
    Run batch analysis on a folder of SGF files (including subfolders).

    This is the GUI-callable API for batch analysis. It uses an existing
    KaTrain and engine instance (no new engine startup required).

    Args:
        katrain: KaTrainBase instance (can be the running GUI instance)
        engine: KataGoEngine instance (can be the running engine)
        input_dir: Directory containing SGF files to analyze
        output_dir: Directory to save analyzed files (default: same as input_dir)
        visits: Number of visits per move (None = use default)
        timeout: Timeout per file in seconds
        skip_analyzed: Skip files that already have analysis
        progress_cb: Callback(current, total, filename) for progress updates.
            NOTE: Called from background thread. GUI code must use Clock.schedule_once.
        log_cb: Callback(message) for log messages.
            NOTE: Called from background thread. GUI code must use Clock.schedule_once.
        cancel_flag: List[bool] - set cancel_flag[0] = True to cancel.
            Caller sets cancel_flag[0] = True to request cancellation.
            This function checks periodically and sets result.cancelled = True.
        save_analyzed_sgf: If True, save analyzed SGF files (default: True for backward compat)
        generate_karte: If True, generate karte markdown for each game
        generate_summary: If True, generate a multi-game summary at the end
        karte_player_filter: Filter for karte ("B", "W", or None for both)
        min_games_per_player: Minimum games for player to appear in summary
        skill_preset: Skill preset for summaries ("auto", "beginner", "standard", "advanced")
        variable_visits: If True, vary visits per file using hash-based jitter
        jitter_pct: Jitter percentage for variable visits (default: 10.0)
        deterministic: If True, use deterministic hash for variable visits
        analysis_engine: Engine to use ("katago" or "leela", default: "katago")
        leela_engine: LeelaEngine instance (required if analysis_engine="leela")
        per_move_timeout: Timeout per move for Leela analysis (default: 30.0)

    Returns:
        BatchResult with success/fail/skip counts, output counts, and error information
    """
    # Import here to avoid circular imports
    from katrain.core.batch.analysis import analyze_single_file, analyze_single_file_leela
    from katrain.core.batch.stats import (
        extract_game_stats,
        extract_players_from_stats,
        build_player_summary,
    )

    result = BatchResult()

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    # Validate input directory
    if not os.path.isdir(input_dir):
        log(f"Error: Input directory does not exist: {input_dir}")
        return result

    # Validate engine selection (Phase 36)
    if analysis_engine == "leela":
        if leela_engine is None:
            log("Error: Leela Zero selected but no leela_engine provided")
            return result
        if not leela_engine.is_alive():
            log("Error: Leela Zero engine is not running")
            return result
        log("Using Leela Zero for analysis")
        # Note: Karte generation is limited for Leela in Phase 36 MVP
        if generate_karte:
            log("Note: Karte generation is not yet supported for Leela analysis")
    else:
        log("Using KataGo for analysis")

    # Set output directory
    output_dir = output_dir if output_dir else input_dir
    result.output_dir = output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Create output subdirectories if needed
    if save_analyzed_sgf:
        analyzed_dir = os.path.join(output_dir, "analyzed")
        os.makedirs(analyzed_dir, exist_ok=True)
    if generate_karte:
        karte_dir = os.path.join(output_dir, "reports", "karte")
        os.makedirs(karte_dir, exist_ok=True)
    if generate_summary:
        summary_dir = os.path.join(output_dir, "reports", "summary")
        os.makedirs(summary_dir, exist_ok=True)

    # Log enabled options
    enabled_outputs = []
    if save_analyzed_sgf:
        enabled_outputs.append("Analyzed SGF")
    if generate_karte:
        enabled_outputs.append("Karte")
    if generate_summary:
        enabled_outputs.append("Summary")
    if enabled_outputs:
        log(f"Enabled outputs: {', '.join(enabled_outputs)}")

    # Collect SGF files recursively (with relative path preservation)
    log(f"Scanning for SGF files in: {input_dir}")

    # First pass: count files and check for skips
    all_files = collect_sgf_files_recursive(input_dir, skip_analyzed=False, log_cb=None)
    sgf_files = []
    skip_count = 0

    for abs_path, rel_path in all_files:
        if skip_analyzed and has_analysis(abs_path):
            log(f"Skipping (already analyzed): {rel_path}")
            skip_count += 1
        else:
            sgf_files.append((abs_path, rel_path))

    result.skip_count = skip_count

    if not sgf_files:
        log(f"No SGF files to analyze in {input_dir}")
        return result

    log(f"Found {len(sgf_files)} SGF file(s) to analyze")
    if skip_count > 0:
        log(f"Skipped {skip_count} already-analyzed file(s)")
        log("  (Note: Skip checks KT property only, not visits/engine settings)")
    total = len(sgf_files)

    # For summary generation, collect game stats
    game_stats_list = [] if generate_summary else None

    # Track actual effective visits used per successful analysis (for variable visits stats)
    selected_visits_list: List[int] = []

    # Timestamp for filenames (includes seconds to reduce collision risk)
    batch_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Process each file
    for i, (abs_path, rel_path) in enumerate(sgf_files):
        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("Cancelled by user")
            result.cancelled = True
            break

        # Progress callback
        if progress_cb:
            progress_cb(i + 1, total, rel_path)

        log(f"[{i + 1}/{total}] Analyzing: {rel_path}")

        # Determine base name for output files
        base_name = os.path.splitext(os.path.basename(rel_path))[0]
        # Sanitize filename
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)[:50]

        # Determine SGF output path (preserve relative path structure)
        output_rel_path = rel_path
        if output_rel_path.lower().endswith(('.gib', '.ngf')):
            output_rel_path = output_rel_path[:-4] + '.sgf'

        sgf_output_path = None
        if save_analyzed_sgf:
            sgf_output_path = os.path.join(output_dir, "analyzed", output_rel_path)

        # Analyze the file
        # We need the Game object if generating karte or summary
        need_game = generate_karte or generate_summary

        # Calculate effective visits (with optional jitter)
        effective_visits = visits
        if variable_visits and visits is not None:
            effective_visits = choose_visits_for_sgf(
                abs_path,
                visits,
                jitter_pct=jitter_pct,
                deterministic=deterministic,
            )
            if effective_visits != visits:
                log(f"  Variable visits: {visits} -> {effective_visits}")

        # Select analysis function based on engine type
        leela_snapshot = None
        if analysis_engine == "leela" and leela_engine is not None:
            # Phase 36 MVP: Leela batch always uses QUICK (fast_visits)
            # UI visits_input is ignored for Leela (spec: Batch Leela visits)
            from katrain.core.analysis.models import AnalysisStrength, resolve_visits
            leela_config = katrain.config("leela") or {}
            effective_visits = resolve_visits(AnalysisStrength.QUICK, leela_config, "leela")
            log(f"  Leela visits: {effective_visits} (from leela.fast_visits)")

            # Leela Zero analysis
            game_result = analyze_single_file_leela(
                katrain=katrain,
                leela_engine=leela_engine,
                sgf_path=abs_path,
                output_path=sgf_output_path,
                visits=effective_visits,
                file_timeout=timeout,
                per_move_timeout=per_move_timeout,
                cancel_flag=cancel_flag,
                log_cb=log_cb,
                save_sgf=save_analyzed_sgf,
                return_game=True,  # Always return game for Leela (need snapshot)
            )
            # Leela returns (Game, EvalSnapshot) tuple
            if isinstance(game_result, tuple):
                game, leela_snapshot = game_result
                success = game is not None
            else:
                game = None
                leela_snapshot = None
                success = False
        else:
            # KataGo analysis (default)
            game_result = analyze_single_file(
                katrain=katrain,
                engine=engine,
                sgf_path=abs_path,
                output_path=sgf_output_path,
                visits=effective_visits,
                timeout=timeout,
                cancel_flag=cancel_flag,
                log_cb=log_cb,
                save_sgf=save_analyzed_sgf,
                return_game=need_game,
            )

            # Handle result based on return type
            if need_game:
                game = game_result
                success = game is not None
            else:
                success = game_result
                game = None

        if success:
            result.success_count += 1

            # Record effective visits used (only numeric, for variable visits stats)
            if effective_visits is not None:
                selected_visits_list.append(effective_visits)

            if save_analyzed_sgf and sgf_output_path:
                result.analyzed_sgf_written += 1
                log(f"  Saved SGF: {sgf_output_path}")

            # Generate karte if requested
            # Note: Leela karte generation is limited in Phase 36 MVP (no leela_loss_est in Game nodes)
            # Phase 44: Pass target_visits for consistent reliability threshold in karte
            if generate_karte and game is not None and analysis_engine != "leela":
                try:
                    karte_text = game.build_karte_report(player_filter=karte_player_filter, target_visits=visits)
                    # Include path hash to avoid filename collisions for files with same basename
                    path_hash = hashlib.md5(rel_path.encode()).hexdigest()[:6]
                    karte_filename = f"karte_{base_name}_{path_hash}_{batch_timestamp}.md"
                    karte_path = os.path.join(output_dir, "reports", "karte", karte_filename)

                    # Use safe write with error handling (A3)
                    write_error = safe_write_file(
                        path=karte_path,
                        content=karte_text,
                        file_kind="karte",
                        sgf_id=rel_path,
                        log_cb=log_cb,
                    )
                    if write_error:
                        result.karte_failed += 1
                        result.write_errors.append(write_error)
                    else:
                        result.karte_written += 1
                        log(f"  Saved Karte: {karte_filename}")

                except Exception as e:
                    import traceback
                    result.karte_failed += 1
                    error_details = traceback.format_exc()
                    log(f"  ERROR generating karte: {e}\n{error_details}")
                    # Record as a structured error too
                    result.write_errors.append(WriteError(
                        file_kind="karte",
                        sgf_id=rel_path,
                        target_path="(generation failed)",
                        exception_type=type(e).__name__,
                        message=str(e),
                    ))

            # Collect stats for summary
            # Phase 44: Pass target_visits for consistent reliability threshold
            if generate_summary and game is not None:
                try:
                    stats = extract_game_stats(game, rel_path, target_visits=visits)
                    if stats:
                        game_stats_list.append(stats)
                except Exception as e:
                    log(f"  ERROR extracting stats: {e}")

        else:
            if cancel_flag and cancel_flag[0]:
                log("Cancelled by user")
                result.cancelled = True
                break
            result.fail_count += 1

    # Generate per-player summaries if requested and not cancelled
    if generate_summary and game_stats_list and not result.cancelled:
        try:
            log("Generating per-player summaries...")

            # Extract and group by player
            player_groups = extract_players_from_stats(game_stats_list, min_games=min_games_per_player)

            if player_groups:
                summary_count = 0
                summary_failed = 0
                for player_name, player_games in player_groups.items():
                    # Sanitize filename
                    safe_name = sanitize_filename(player_name)
                    base_path = os.path.join(output_dir, "reports", "summary", f"summary_{safe_name}_{batch_timestamp}")
                    summary_path = get_unique_filename(base_path, ".md")
                    summary_filename = os.path.basename(summary_path)

                    # Build analysis_settings for the summary
                    # Compute selected visits stats if variable visits enabled and have data
                    selected_visits_stats = None
                    if variable_visits and selected_visits_list:
                        selected_visits_stats = {
                            "min": min(selected_visits_list),
                            "avg": sum(selected_visits_list) / len(selected_visits_list),
                            "max": max(selected_visits_list),
                        }

                    analysis_settings = {
                        "config_visits": visits,
                        "variable_visits": variable_visits,
                        "jitter_pct": jitter_pct if variable_visits else None,
                        "deterministic": deterministic if variable_visits else None,
                        "timeout": timeout,
                        "selected_visits_stats": selected_visits_stats,
                    }
                    summary_text = build_player_summary(
                        player_name,
                        player_games,
                        skill_preset=skill_preset,
                        analysis_settings=analysis_settings,
                    )

                    # Use safe write with error handling (A3)
                    write_error = safe_write_file(
                        path=summary_path,
                        content=summary_text,
                        file_kind="summary",
                        sgf_id=player_name,
                        log_cb=log_cb,
                    )
                    if write_error:
                        summary_failed += 1
                        result.write_errors.append(write_error)
                    else:
                        log(f"  [{player_name}] {len(player_games)} games -> {summary_filename}")
                        summary_count += 1

                if summary_count > 0:
                    result.summary_written = True
                    log(f"Generated {summary_count} player summaries")
                if summary_failed > 0:
                    log(f"WARNING: {summary_failed} summary file(s) failed to write")
            else:
                log(f"No players with >= {min_games_per_player} games found")
                result.summary_error = f"No players with >= {min_games_per_player} games"

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            result.summary_error = str(e)
            log(f"ERROR generating summary: {e}\n{error_details}")
    elif generate_summary and not game_stats_list and not result.cancelled:
        # No games were successfully analyzed for summary
        result.summary_error = "No valid game statistics available"
        log("WARNING: Summary generation requested but no valid game statistics available")

    return result
