"""Batch analysis orchestration.

This module contains the main `run_batch()` function that orchestrates
batch SGF analysis across multiple files.

All functions are Kivy-independent and can be used in headless contexts.
Callbacks (progress_cb, log_cb) are used for UI integration - GUI code
should wrap these with Clock.schedule_once() for thread safety.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from katrain.core.batch.models import BatchResult, WriteError
from katrain.core.errors import AnalysisTimeoutError, EngineError, SGFError
from katrain.core.reports.karte.models import (
    KarteGenerationError,
    MixedEngineSnapshotError,
)
from katrain.core.reports.karte.builder import build_karte_report
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
    from katrain.core.analysis.skill_radar import AggregatedRadarResult
    from katrain.core.base_katrain import KaTrainBase
    from katrain.core.engine import KataGoEngine
    from katrain.core.game import Game
    from katrain.core.leela.engine import LeelaEngine


class EngineFailureTracker:
    """Track consecutive engine-related failures for circuit breaker.

    Engine failures: TIMEOUT, ENGINE_DEAD, EngineError exception
    File failures: FILE_ERROR (do not count toward abort)
    """

    def __init__(self, max_failures: int = 3):
        self.consecutive_engine_failures = 0
        self.max_failures = max_failures
        self.last_failure_file: str | None = None
        self.last_failure_reason: str | None = None

    def record_engine_failure(self, file_path: str, reason: str) -> bool:
        """Record engine failure. Returns True if should abort."""
        self.consecutive_engine_failures += 1
        self.last_failure_file = file_path
        self.last_failure_reason = reason
        return self.consecutive_engine_failures >= self.max_failures

    def record_file_error(self) -> None:
        """Record file error. Does NOT count toward abort, does NOT reset counter."""
        pass

    def record_success(self) -> None:
        """Record success. Resets consecutive failure count."""
        self.consecutive_engine_failures = 0
        self.last_failure_file = None
        self.last_failure_reason = None

    def should_abort(self) -> bool:
        return self.consecutive_engine_failures >= self.max_failures

    def get_abort_message(self) -> str:
        return (
            f"Batch aborted: {self.consecutive_engine_failures} consecutive engine failures. "
            f"Last: {self.last_failure_file} ({self.last_failure_reason})"
        )


def run_batch(
    katrain: "KaTrainBase",
    engine: "KataGoEngine",
    input_dir: str,
    output_dir: str | None = None,
    visits: int | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    skip_analyzed: bool = False,
    progress_cb: Callable[[int, int, str], None] | None = None,
    log_cb: Callable[[str], None] | None = None,
    cancel_flag: list[bool] | None = None,
    # Extended options for karte/summary generation
    save_analyzed_sgf: bool = True,
    generate_karte: bool = False,
    generate_summary: bool = False,
    karte_player_filter: str | None = None,
    min_games_per_player: int = 3,
    skill_preset: str = DEFAULT_SKILL_PRESET,
    # Variable visits options
    variable_visits: bool = False,
    jitter_pct: float = 10.0,
    deterministic: bool = True,
    # Engine selection (Phase 36)
    analysis_engine: str = "katago",
    leela_engine: "LeelaEngine | None" = None,
    per_move_timeout: float = 30.0,
    # Phase 54: Output language
    lang: str = "jp",
    # Phase 64: Curator outputs
    generate_curator: bool = False,
    user_aggregate: "AggregatedRadarResult | None" = None,
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
        lang: Language code for output ("jp", "en", "ja"). Defaults to "jp".

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
    if generate_curator:
        enabled_outputs.append("Curator")
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
    game_stats_list: list[dict[str, Any]] | None = [] if generate_summary else None

    # Track (game, stats) tuples for curator output (Phase 64)
    games_for_curator: list[tuple[Game, dict[str, Any]]] | None = [] if generate_curator else None

    # Track actual effective visits used per successful analysis (for variable visits stats)
    selected_visits_list: list[int] = []

    # Timestamp for filenames (includes seconds to reduce collision risk)
    batch_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Phase 53: Map rel_path -> full karte file path for summary links
    karte_path_map: dict[str, str] = {}

    # Phase 95C: Circuit breaker for consecutive engine failures
    tracker = EngineFailureTracker(max_failures=3)

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
        need_game = generate_karte or generate_summary or generate_curator

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
        # Phase 95C: Wrap in try/except for circuit breaker
        leela_snapshot = None
        game = None
        success = False
        try:
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
                # Leela returns (Game, EvalSnapshot) tuple per contract (analysis.py:207-211)
                if isinstance(game_result, tuple) and len(game_result) == 2:
                    game, leela_snapshot = game_result
                    # Phase 87.6: Success requires both game and valid analysis data
                    if game is None:
                        success = False
                        # fail_result() was called - detailed error already logged in analysis.py
                        # Log file identification here for consistency
                        log(f"  FAILED: Analysis error for {rel_path}")
                    elif leela_snapshot is None or len(leela_snapshot.moves) == 0:
                        success = False
                        # Could be: empty SGF (0 moves) or all moves failed
                        # Detailed reason already logged by analysis.py
                        log(f"  FAILED: No valid analysis data for {rel_path}")
                    else:
                        success = True
                else:
                    # Defensive: unexpected return type from analyze_single_file_leela
                    game = None
                    leela_snapshot = None
                    success = False
                    log(f"  ERROR: Unexpected return type from Leela analysis for {rel_path}: {type(game_result)}")
            else:
                # KataGo analysis (default)
                katago_result = analyze_single_file(
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
                    # When return_game=True, result is Game | None
                    if isinstance(katago_result, bool):
                        # Shouldn't happen, but handle gracefully
                        game = None
                        success = katago_result
                    else:
                        game = katago_result
                        success = game is not None
                else:
                    # When return_game=False, result is bool
                    success = bool(katago_result)
                    game = None

        except AnalysisTimeoutError as e:
            # Phase 95C: Timeout = engine failure
            result.engine_failure_count += 1
            log(f"  TIMEOUT ({rel_path}): {e}")
            if tracker.record_engine_failure(rel_path, str(e)):
                log(tracker.get_abort_message())
                result.aborted = True
                result.abort_reason = tracker.get_abort_message()
                break

        except EngineError as e:
            # Phase 95C: Other engine errors
            result.engine_failure_count += 1
            log(f"  ENGINE ERROR ({rel_path}): {e}")
            if tracker.record_engine_failure(rel_path, str(e)):
                log(tracker.get_abort_message())
                result.aborted = True
                result.abort_reason = tracker.get_abort_message()
                break

        except (SGFError, OSError, UnicodeDecodeError) as e:
            # File-related errors - do not count toward circuit breaker
            result.file_error_count += 1
            tracker.record_file_error()
            log(f"  FILE ERROR ({rel_path}): {e}")

        except Exception as e:
            # Unexpected error - treat as file error (safer)
            result.file_error_count += 1
            tracker.record_file_error()
            log(f"  UNEXPECTED ({rel_path}): {e}")
            log(f"    {traceback.format_exc()}")

        # Track success for circuit breaker
        if success:
            tracker.record_success()
            result.success_count += 1

            # Record effective visits used (only numeric, for variable visits stats)
            if effective_visits is not None:
                selected_visits_list.append(effective_visits)

            if save_analyzed_sgf and sgf_output_path:
                result.analyzed_sgf_written += 1
                log(f"  Saved SGF: {sgf_output_path}")

            # Generate karte if requested
            # Phase 87.5: Leela karte now supported via snapshot parameter
            # Phase 44: Pass target_visits for consistent reliability threshold in karte
            if generate_karte and game is not None:
                try:
                    karte_text = build_karte_report(
                        game,
                        player_filter=karte_player_filter,
                        target_visits=visits,
                        snapshot=leela_snapshot,  # Phase 87.5: Pass pre-built snapshot for Leela
                    )
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
                        # Phase 53: Store mapping for summary link generation
                        karte_path_map[rel_path] = karte_path

                except (KarteGenerationError, MixedEngineSnapshotError) as e:
                    # Expected: Karte generation domain error
                    result.karte_failed += 1
                    log(f"  Karte generation error ({rel_path}): {e}")
                    result.write_errors.append(WriteError(
                        file_kind="karte",
                        sgf_id=rel_path,
                        target_path="(generation failed)",
                        exception_type=type(e).__name__,
                        message=f"[generation] {e}",
                    ))
                except OSError as e:
                    # Expected: File write I/O error
                    result.karte_failed += 1
                    log(f"  Karte write error ({rel_path}): {e}")
                    result.write_errors.append(WriteError(
                        file_kind="karte",
                        sgf_id=rel_path,
                        target_path=str(karte_path) if "karte_path" in dir() else "(path unknown)",
                        exception_type=type(e).__name__,
                        message=f"[write] {e}",
                    ))
                except Exception as e:
                    # Unexpected: Internal bug - traceback required
                    result.karte_failed += 1
                    log(f"  Unexpected karte error ({rel_path}): {e}")
                    log(f"    {traceback.format_exc()}")
                    result.write_errors.append(WriteError(
                        file_kind="karte",
                        sgf_id=rel_path,
                        target_path="(generation failed)",
                        exception_type=type(e).__name__,
                        message=f"[unexpected] {e}",
                    ))

            # Collect stats for summary and/or curator
            # Phase 44: Pass target_visits for consistent reliability threshold
            # Phase 85: Pass source_index for deterministic sorting
            # Phase 87.5: Pass leela_snapshot for Leela analysis
            if (generate_summary or generate_curator) and game is not None:
                try:
                    stats = extract_game_stats(
                        game, rel_path,
                        log_cb=log_cb,  # Phase 87.6: Wire logging callback
                        target_visits=visits,
                        source_index=i,
                        snapshot=leela_snapshot,  # Phase 87.5: Use pre-built snapshot for Leela
                    )
                    if stats:
                        if generate_summary and game_stats_list is not None:
                            game_stats_list.append(stats)
                        # Phase 64: Collect (game, stats) for curator
                        if generate_curator and games_for_curator is not None and game is not None:
                            games_for_curator.append((game, stats))
                except (KeyError, ValueError) as e:
                    # Expected: External SGF data structure issue
                    log(f"  Stats extraction error ({rel_path}): {e}")
                except Exception as e:
                    # Unexpected: Internal bug - traceback required
                    log(f"  Unexpected stats error ({rel_path}): {e}")
                    log(f"    {traceback.format_exc()}")

        else:
            if cancel_flag and cancel_flag[0]:
                log("Cancelled by user")
                result.cancelled = True
                break
            result.fail_count += 1
            # Phase 87.6: Track karte_failed for files that couldn't be analyzed
            # This ensures karte_total reflects input count, not just successful analyses
            if generate_karte:
                result.karte_failed += 1

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
                        # Phase 53: Pass karte mapping for link generation
                        karte_path_map=karte_path_map,
                        summary_dir=os.path.dirname(summary_path),
                        # Phase 54: Output language
                        lang=lang,
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

        except (OSError, KeyError, ValueError) as e:
            # Expected: File I/O or stats structure issue
            result.summary_error = str(e)
            log(f"Summary generation error: {e}")
        except Exception as e:
            # Unexpected: Internal bug - traceback required
            result.summary_error = str(e)
            log(f"Unexpected summary error: {e}")
            log(f"  {traceback.format_exc()}")
    elif generate_summary and not game_stats_list and not result.cancelled:
        # No games were successfully analyzed for summary
        result.summary_error = "No valid game statistics available"
        log("WARNING: Summary generation requested but no valid game statistics available")

    # Phase 64: Generate curator outputs if requested
    if generate_curator and games_for_curator and not result.cancelled:
        try:
            from katrain.core.curator import generate_curator_outputs

            curator_dir = os.path.join(output_dir, "reports", "curator")
            log("Generating curator outputs...")

            curator_result = generate_curator_outputs(
                games_and_stats=games_for_curator,
                curator_dir=curator_dir,
                batch_timestamp=batch_timestamp,
                user_aggregate=user_aggregate,
                lang=lang,
                log_cb=log_cb,
            )

            # Update BatchResult with curator results
            result.curator_ranking_written = curator_result.ranking_path is not None
            result.curator_guide_written = curator_result.guide_path is not None
            result.curator_games_scored = curator_result.games_scored
            result.curator_guides_generated = curator_result.guides_generated
            result.curator_errors.extend(curator_result.errors)

            if curator_result.errors:
                log(f"WARNING: {len(curator_result.errors)} curator error(s)")

        except (OSError, json.JSONDecodeError) as e:
            # Expected: File I/O or JSON processing error
            result.curator_errors.append(f"Curator I/O error: {e}")
            log(f"Curator I/O error: {e}")
        except Exception as e:
            # Unexpected: Internal bug - traceback required
            result.curator_errors.append(f"Curator unexpected error: {e}")
            log(f"Unexpected curator error: {e}")
            log(f"  {traceback.format_exc()}")

    elif generate_curator and not games_for_curator and not result.cancelled:
        log("WARNING: Curator generation requested but no valid games available")
        result.curator_errors.append("No valid games available for curator")

    return result
