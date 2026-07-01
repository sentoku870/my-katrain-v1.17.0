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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from katrain.core.batch.discovery import collect_sgf_files_recursive
from katrain.core.batch.filenames import get_unique_filename, sanitize_filename
from katrain.core.batch.inputs import DEFAULT_TIMEOUT_SECONDS
from katrain.core.batch.io_safe import safe_write_file
from katrain.core.batch.sgf_io import has_analysis
from katrain.core.batch.visits import choose_visits_for_sgf
from katrain.core.batch.models import BatchResult, WriteError
from katrain.core.errors import AnalysisTimeoutError, EngineError, SGFError
from katrain.core.eval_metrics import DEFAULT_SKILL_PRESET
from katrain.core.reports.karte.builder import build_karte_report
from katrain.core.reports.karte.models import (
    KarteGenerationError,
    MixedEngineSnapshotError,
)

if TYPE_CHECKING:
    from katrain.core.base_katrain import KaTrainBase
    from katrain.core.engine import KataGoEngine
    from katrain.core.game import Game


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
    katrain: KaTrainBase,
    engine: KataGoEngine,
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
    # Phase 54: Output language
    lang: str = "jp",
    # Phase 64: Curator outputs
    generate_curator: bool = False,
    user_aggregate: Any = None,
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
        lang: Language code for output ("jp", "en", "ja"). Defaults to "jp".

    Returns:
        BatchResult with success/fail/skip counts, output counts, and error information
    """
    # Import here to avoid circular imports

    result = BatchResult()

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    # Setup: validate inputs, create output dirs, collect SGF files
    setup = _setup_batch(
        result=result,
        katrain=katrain,
        input_dir=input_dir,
        output_dir=output_dir,
        save_analyzed_sgf=save_analyzed_sgf,
        generate_karte=generate_karte,
        generate_summary=generate_summary,
        generate_curator=generate_curator,
        skip_analyzed=skip_analyzed,
        log_cb=log_cb,
    )
    if setup is None:
        return result
    output_dir, sgf_files, total, batch_timestamp, game_stats_list, games_for_curator, selected_visits_list, karte_path_map, tracker = (
        setup
    )

    # Process each file
    for i, (abs_path, rel_path) in enumerate(sgf_files):
        if cancel_flag and cancel_flag[0]:
            log("Cancelled by user")
            result.cancelled = True
            break

        if progress_cb:
            progress_cb(i + 1, total, rel_path)

        _process_single_file(
            ctx=_BatchFileContext(
                katrain=katrain,
                engine=engine,
                result=result,
                i=i,
                total=total,
                abs_path=abs_path,
                rel_path=rel_path,
                output_dir=output_dir,
                visits=visits,
                effective_visits=None,  # computed inside
                timeout=timeout,
                cancel_flag=cancel_flag,
                log_cb=log_cb,
                save_analyzed_sgf=save_analyzed_sgf,
                generate_karte=generate_karte,
                generate_summary=generate_summary,
                generate_curator=generate_curator,
                karte_player_filter=karte_player_filter,
                tracker=tracker,
                game_stats_list=game_stats_list,
                games_for_curator=games_for_curator,
                karte_path_map=karte_path_map,
                selected_visits_list=selected_visits_list,
                variable_visits=variable_visits,
                jitter_pct=jitter_pct,
                deterministic=deterministic,
                batch_timestamp=batch_timestamp,
                skill_preset=skill_preset,
            ),
            log=log,
        )

    # Generate per-player summaries
    if generate_summary and game_stats_list and not result.cancelled:
        _generate_summaries(
            ctx=_BatchSummaryContext(
                result=result,
                output_dir=output_dir,
                game_stats_list=game_stats_list,
                min_games_per_player=min_games_per_player,
                visits=visits,
                variable_visits=variable_visits,
                jitter_pct=jitter_pct,
                deterministic=deterministic,
                timeout=timeout,
                selected_visits_list=selected_visits_list,
                skill_preset=skill_preset,
                karte_path_map=karte_path_map,
                batch_timestamp=batch_timestamp,
                lang=lang,
                log_cb=log_cb,
                log=log,
            )
        )
    elif generate_summary and not game_stats_list and not result.cancelled:
        result.summary_error = "No valid game statistics available"
        log("WARNING: Summary generation requested but no valid game statistics available")

    # Generate curator outputs (Phase 64)
    if generate_curator and games_for_curator and not result.cancelled:
        _generate_curator_outputs(
            ctx=_BatchCuratorContext(
                result=result,
                output_dir=output_dir,
                games_for_curator=games_for_curator,
                batch_timestamp=batch_timestamp,
                user_aggregate=user_aggregate,
                lang=lang,
                log_cb=log_cb,
                log=log,
            )
        )
    elif generate_curator and not games_for_curator and not result.cancelled:
        log("WARNING: Curator generation requested but no valid games available")
        result.curator_errors.append("No valid games available for curator")

    return result


# =============================================================================
# Phase 145-C: run_batch split into setup / per-file / summaries / curator
# =============================================================================


def _setup_batch(
    result: BatchResult,
    katrain: KaTrainBase,
    input_dir: str,
    output_dir: str | None,
    save_analyzed_sgf: bool,
    generate_karte: bool,
    generate_summary: bool,
    generate_curator: bool,
    skip_analyzed: bool,
    log_cb: Callable[[str], None] | None,
) -> tuple[Any, Any, int, str, Any, Any, list[int], dict[str, str], EngineFailureTracker] | None:
    """Validate input, create output subdirs, collect SGF files, init trackers.

    Returns:
        Tuple of (output_dir, sgf_files, total, batch_timestamp, game_stats_list,
                  games_for_curator, selected_visits_list, karte_path_map, tracker)
        or None if validation failed.
    """

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    if not os.path.isdir(input_dir):
        log(f"Error: Input directory does not exist: {input_dir}")
        return None

    log("Using KataGo for analysis")

    output_dir = output_dir if output_dir else input_dir
    result.output_dir = output_dir
    os.makedirs(output_dir, exist_ok=True)

    if save_analyzed_sgf:
        os.makedirs(os.path.join(output_dir, "analyzed"), exist_ok=True)
    if generate_karte:
        os.makedirs(os.path.join(output_dir, "reports", "karte"), exist_ok=True)
    if generate_summary:
        os.makedirs(os.path.join(output_dir, "reports", "summary"), exist_ok=True)

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

    log(f"Scanning for SGF files in: {input_dir}")

    all_files = collect_sgf_files_recursive(input_dir, skip_analyzed=False, log_cb=None)
    sgf_files: list[tuple[str, str]] = []
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
        return None

    log(f"Found {len(sgf_files)} SGF file(s) to analyze")
    if skip_count > 0:
        log(f"Skipped {skip_count} already-analyzed file(s)")
        log("  (Note: Skip checks KT property only, not visits/engine settings)")
    total = len(sgf_files)

    game_stats_list: list[dict[str, Any]] | None = [] if generate_summary else None
    games_for_curator: list[tuple[Game, dict[str, Any]]] | None = [] if generate_curator else None
    selected_visits_list: list[int] = []
    batch_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    karte_path_map: dict[str, str] = {}
    tracker = EngineFailureTracker(max_failures=3)

    return (
        output_dir,
        sgf_files,
        total,
        batch_timestamp,
        game_stats_list,
        games_for_curator,
        selected_visits_list,
        karte_path_map,
        tracker,
    )


def _process_single_file(ctx: _BatchFileContext, log: Callable[[str], None]) -> None:
    """Analyze one SGF file and (optionally) generate its karte + stats.

    Modifies ctx.result in place. May set ctx.result.cancelled/aborted on
    cancellation or circuit-breaker trip.
    """
    # Import here to avoid circular imports
    from katrain.core.batch.analysis import analyze_single_file
    # Determine base name for output files
    base_name = os.path.splitext(os.path.basename(ctx.rel_path))[0]
    base_name = re.sub(r'[<>:"/\\|?*]', "_", base_name)[:50]

    # Determine SGF output path (preserve relative path structure)
    output_rel_path = ctx.rel_path
    if output_rel_path.lower().endswith((".gib", ".ngf")):
        output_rel_path = output_rel_path[:-4] + ".sgf"
    sgf_output_path = (
        os.path.join(ctx.output_dir, "analyzed", output_rel_path) if ctx.save_analyzed_sgf else None
    )

    # We need the Game object if generating karte or summary
    need_game = ctx.generate_karte or ctx.generate_summary or ctx.generate_curator

    # Calculate effective visits (with optional jitter)
    effective_visits = ctx.visits
    if ctx.variable_visits and ctx.visits is not None:
        effective_visits = choose_visits_for_sgf(
            ctx.abs_path,
            ctx.visits,
            jitter_pct=ctx.jitter_pct,
            deterministic=ctx.deterministic,
        )
        if effective_visits != ctx.visits:
            log(f"  Variable visits: {ctx.visits} -> {effective_visits}")

    log(f"[{ctx.i + 1}/{ctx.total}] Analyzing: {ctx.rel_path}")

    # KataGo analysis (Phase 95C: wrapped in try/except for circuit breaker)
    game = None
    success = False
    try:
        katago_result = analyze_single_file(
            katrain=ctx.katrain,
            engine=ctx.engine,
            sgf_path=ctx.abs_path,
            output_path=sgf_output_path,
            visits=effective_visits,
            timeout=ctx.timeout,
            cancel_flag=ctx.cancel_flag,
            log_cb=ctx.log_cb,
            save_sgf=ctx.save_analyzed_sgf,
            return_game=need_game,
        )

        if need_game:
            if isinstance(katago_result, bool):
                game = None
                success = katago_result
            else:
                game = katago_result
                success = game is not None
        else:
            success = bool(katago_result)
            game = None

    except AnalysisTimeoutError as e:
        ctx.result.engine_failure_count += 1
        log(f"  TIMEOUT ({ctx.rel_path}): {e}")
        if ctx.tracker.record_engine_failure(ctx.rel_path, str(e)):
            log(ctx.tracker.get_abort_message())
            ctx.result.aborted = True
            ctx.result.abort_reason = ctx.tracker.get_abort_message()
            return

    except EngineError as e:
        ctx.result.engine_failure_count += 1
        log(f"  ENGINE ERROR ({ctx.rel_path}): {e}")
        if ctx.tracker.record_engine_failure(ctx.rel_path, str(e)):
            log(ctx.tracker.get_abort_message())
            ctx.result.aborted = True
            ctx.result.abort_reason = ctx.tracker.get_abort_message()
            return

    except (SGFError, OSError, UnicodeDecodeError) as e:
        ctx.result.file_error_count += 1
        ctx.tracker.record_file_error()
        log(f"  FILE ERROR ({ctx.rel_path}): {e}")

    except Exception as e:
        ctx.result.file_error_count += 1
        ctx.tracker.record_file_error()
        log(f"  UNEXPECTED ({ctx.rel_path}): {e}")
        log(f"    {traceback.format_exc()}")

    if success:
        ctx.tracker.record_success()
        ctx.result.success_count += 1

        if effective_visits is not None:
            ctx.selected_visits_list.append(effective_visits)

        if ctx.save_analyzed_sgf and sgf_output_path:
            ctx.result.analyzed_sgf_written += 1
            log(f"  Saved SGF: {sgf_output_path}")

        # Generate karte if requested
        if ctx.generate_karte and game is not None:
            _generate_karte_for_file(
                game=game,
                abs_path=ctx.abs_path,
                rel_path=ctx.rel_path,
                base_name=base_name,
                output_dir=ctx.output_dir,
                player_filter=ctx.karte_player_filter,
                visits=ctx.visits,
                batch_timestamp=ctx.batch_timestamp,
                result=ctx.result,
                karte_path_map=ctx.karte_path_map,
                log=log,
                log_cb=ctx.log_cb,
                skill_preset=ctx.skill_preset,
            )

        # Collect stats for summary and/or curator
        if (ctx.generate_summary or ctx.generate_curator) and game is not None:
            _collect_stats_for_file(
                game=game,
                rel_path=ctx.rel_path,
                source_index=ctx.i,
                visits=ctx.visits,
                log_cb=ctx.log_cb,
                generate_summary=ctx.generate_summary,
                generate_curator=ctx.generate_curator,
                game_stats_list=ctx.game_stats_list,
                games_for_curator=ctx.games_for_curator,
                skill_preset=ctx.skill_preset,
                log=log,
            )
    else:
        if ctx.cancel_flag and ctx.cancel_flag[0]:
            log("Cancelled by user")
            ctx.result.cancelled = True
            return
        ctx.result.fail_count += 1
        if ctx.generate_karte:
            ctx.result.karte_failed += 1


def _generate_karte_for_file(
    game: Game,
    abs_path: str,
    rel_path: str,
    base_name: str,
    output_dir: str,
    player_filter: str | None,
    visits: int | None,
    batch_timestamp: str,
    result: BatchResult,
    karte_path_map: dict[str, str],
    log: Callable[[str], None],
    log_cb: Callable[[str], None] | None,
    skill_preset: str | None = None,
) -> None:
    """Generate and write a single karte file. Updates result in place."""
    try:
        # Phase 149 A-1: pass skill_preset (may be None -> uses default in build_karte_report)
        karte_text = build_karte_report(
            game,
            player_filter=player_filter,
            target_visits=visits,
            skill_preset=skill_preset or DEFAULT_SKILL_PRESET,
        )
        # Include path hash to avoid filename collisions for files with same basename
        path_hash = hashlib.md5(rel_path.encode()).hexdigest()[:6]
        karte_filename = f"karte_{base_name}_{path_hash}_{batch_timestamp}.json"
        karte_path = os.path.join(output_dir, "reports", "karte", karte_filename)

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
        result.karte_failed += 1
        log(f"  Karte generation error ({rel_path}): {e}")
        result.write_errors.append(
            WriteError(
                file_kind="karte",
                sgf_id=rel_path,
                target_path="(generation failed)",
                exception_type=type(e).__name__,
                message=f"[generation] {e}",
            )
        )
    except OSError as e:
        result.karte_failed += 1
        log(f"  Karte write error ({rel_path}): {e}")
        result.write_errors.append(
            WriteError(
                file_kind="karte",
                sgf_id=rel_path,
                target_path="(path unknown)",
                exception_type=type(e).__name__,
                message=f"[write] {e}",
            )
        )
    except Exception as e:
        result.karte_failed += 1
        log(f"  Unexpected karte error ({rel_path}): {e}")
        log(f"    {traceback.format_exc()}")
        result.write_errors.append(
            WriteError(
                file_kind="karte",
                sgf_id=rel_path,
                target_path="(generation failed)",
                exception_type=type(e).__name__,
                message=f"[unexpected] {e}",
            )
        )


def _collect_stats_for_file(
    game: Game,
    rel_path: str,
    source_index: int,
    visits: int | None,
    log_cb: Callable[[str], None] | None,
    generate_summary: bool,
    generate_curator: bool,
    game_stats_list: list[dict[str, Any]] | None,
    games_for_curator: list[tuple[Game, dict[str, Any]]] | None,
    log: Callable[[str], None],
    skill_preset: str | None = None,
) -> None:
    """Extract per-game stats for summary and/or curator output."""
    # Import here to avoid circular imports
    from katrain.core.batch.stats import extract_game_stats

    try:
        stats = extract_game_stats(
            game,
            rel_path,
            log_cb=log_cb,
            target_visits=visits,
            source_index=source_index,
            skill_preset=skill_preset,
        )
        if stats:
            if generate_summary and game_stats_list is not None:
                game_stats_list.append(stats)
            if generate_curator and games_for_curator is not None and game is not None:
                games_for_curator.append((game, stats))
    except (KeyError, ValueError) as e:
        log(f"  Stats extraction error ({rel_path}): {e}")
    except Exception as e:
        log(f"  Unexpected stats error ({rel_path}): {e}")
        log(f"    {traceback.format_exc()}")


def _generate_summaries(ctx: _BatchSummaryContext) -> None:
    """Generate per-player summary markdown files."""
    # Import here to avoid circular imports
    from katrain.core.batch.stats import build_player_summary, extract_players_from_stats

    log = ctx.log
    log("Generating per-player summaries...")

    try:
        player_groups = extract_players_from_stats(ctx.game_stats_list, min_games=ctx.min_games_per_player)
    except (OSError, KeyError, ValueError) as e:
        ctx.result.summary_error = str(e)
        log(f"Summary generation error: {e}")
        return
    except Exception as e:
        ctx.result.summary_error = str(e)
        log(f"Unexpected summary error: {e}")
        log(f"  {traceback.format_exc()}")
        return

    if not player_groups:
        log(f"No players with >= {ctx.min_games_per_player} games found")
        ctx.result.summary_error = f"No players with >= {ctx.min_games_per_player} games"
        return

    summary_count = 0
    summary_failed = 0
    for player_name, player_games in player_groups.items():
        safe_name = sanitize_filename(player_name)
        base_path = os.path.join(
            ctx.output_dir, "reports", "summary", f"summary_{safe_name}_{ctx.batch_timestamp}"
        )
        summary_path = get_unique_filename(base_path, ".json")
        summary_filename = os.path.basename(summary_path)

        # Compute selected visits stats if variable visits enabled and have data
        selected_visits_stats = None
        if ctx.variable_visits and ctx.selected_visits_list:
            selected_visits_stats = {
                "min": min(ctx.selected_visits_list),
                "avg": sum(ctx.selected_visits_list) / len(ctx.selected_visits_list),
                "max": max(ctx.selected_visits_list),
            }

        analysis_settings = {
            "config_visits": ctx.visits,
            "variable_visits": ctx.variable_visits,
            "jitter_pct": ctx.jitter_pct if ctx.variable_visits else None,
            "deterministic": ctx.deterministic if ctx.variable_visits else None,
            "timeout": ctx.timeout,
            "selected_visits_stats": selected_visits_stats,
        }
        try:
            summary_text = build_player_summary(
                player_name,
                player_games,
                skill_preset=ctx.skill_preset,
                analysis_settings=analysis_settings,
                karte_path_map=ctx.karte_path_map,
                summary_dir=os.path.dirname(summary_path),
                lang=ctx.lang,
            )
        except (OSError, KeyError, ValueError) as e:
            log(f"  Summary build error ({player_name}): {e}")
            summary_failed += 1
            continue
        except Exception as e:
            log(f"  Unexpected summary build error ({player_name}): {e}")
            log(f"    {traceback.format_exc()}")
            summary_failed += 1
            continue

        write_error = safe_write_file(
            path=summary_path,
            content=summary_text,
            file_kind="summary",
            sgf_id=player_name,
            log_cb=ctx.log_cb,
        )
        if write_error:
            summary_failed += 1
            ctx.result.write_errors.append(write_error)
        else:
            log(f"  [{player_name}] {len(player_games)} games -> {summary_filename}")
            summary_count += 1

    if summary_count > 0:
        ctx.result.summary_written = True
        log(f"Generated {summary_count} player summaries")
    if summary_failed > 0:
        log(f"WARNING: {summary_failed} summary file(s) failed to write")


def _generate_curator_outputs(ctx: _BatchCuratorContext) -> None:
    """Generate curator ranking and guide outputs (Phase 64)."""
    from katrain.core.curator import generate_curator_outputs

    curator_dir = os.path.join(ctx.output_dir, "reports", "curator")
    ctx.log("Generating curator outputs...")

    try:
        curator_result = generate_curator_outputs(
            games_and_stats=ctx.games_for_curator,
            curator_dir=curator_dir,
            batch_timestamp=ctx.batch_timestamp,
            user_aggregate=ctx.user_aggregate,
            lang=ctx.lang,
            log_cb=ctx.log_cb,
        )

        ctx.result.curator_ranking_written = curator_result.ranking_path is not None
        ctx.result.curator_guide_written = curator_result.guide_path is not None
        ctx.result.curator_games_scored = curator_result.games_scored
        ctx.result.curator_guides_generated = curator_result.guides_generated
        ctx.result.curator_errors.extend(curator_result.errors)

        if curator_result.errors:
            ctx.log(f"WARNING: {len(curator_result.errors)} curator error(s)")

    except (OSError, json.JSONDecodeError) as e:
        ctx.result.curator_errors.append(f"Curator I/O error: {e}")
        ctx.log(f"Curator I/O error: {e}")
    except Exception as e:
        ctx.result.curator_errors.append(f"Curator unexpected error: {e}")
        ctx.log(f"Unexpected curator error: {e}")
        ctx.log(f"  {traceback.format_exc()}")


# Context dataclasses for Phase 145-C split (avoids huge parameter lists)


@dataclass
class _BatchFileContext:
    """Parameters needed to process a single batch file."""

    katrain: KaTrainBase
    engine: KataGoEngine
    result: BatchResult
    i: int
    total: int
    abs_path: str
    rel_path: str
    output_dir: str
    visits: int | None
    effective_visits: int | None
    timeout: float
    cancel_flag: list[bool] | None
    log_cb: Callable[[str], None] | None
    save_analyzed_sgf: bool
    generate_karte: bool
    generate_summary: bool
    generate_curator: bool
    karte_player_filter: str | None
    tracker: EngineFailureTracker
    game_stats_list: list[dict[str, Any]] | None
    games_for_curator: list[tuple[Game, dict[str, Any]]] | None
    karte_path_map: dict[str, str]
    selected_visits_list: list[int]
    variable_visits: bool
    jitter_pct: float
    deterministic: bool
    batch_timestamp: str
    skill_preset: str


@dataclass
class _BatchSummaryContext:
    """Parameters needed for summary generation."""

    result: BatchResult
    output_dir: str
    game_stats_list: list[dict[str, Any]]
    min_games_per_player: int
    visits: int | None
    variable_visits: bool
    jitter_pct: float
    deterministic: bool
    timeout: float
    selected_visits_list: list[int]
    skill_preset: str
    karte_path_map: dict[str, str]
    batch_timestamp: str
    lang: str
    log_cb: Callable[[str], None] | None
    log: Callable[[str], None]


@dataclass
class _BatchCuratorContext:
    """Parameters needed for curator generation."""

    result: BatchResult
    output_dir: str
    games_for_curator: list[tuple[Game, dict[str, Any]]]
    batch_timestamp: str
    user_aggregate: Any
    lang: str
    log_cb: Callable[[str], None] | None
    log: Callable[[str], None]
