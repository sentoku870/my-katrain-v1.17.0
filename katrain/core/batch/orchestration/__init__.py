"""Batch analysis orchestration subpackage (Phase 197).

Public entry: :func:`run_batch`. Implementation is split across:

* :mod:`._context`  — dataclasses and EngineFailureTracker
* :mod:`._setup`    — input validation + directory setup
* :mod:`._process`  — per-file analysis loop + circuit breaker helpers
* :mod:`._handle`   — post-success karte/stats generation
* :mod:`._summary`  — per-player summary markdown
* :mod:`._curator`  — curator outputs

The legacy ``katrain.core.batch.orchestration`` *module* is preserved
as a thin re-export shim, so existing imports like
``from katrain.core.batch.orchestration import run_batch`` and
``from katrain.core.batch.orchestration import EngineFailureTracker``
keep working unchanged. **New code should import from this subpackage.**
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from katrain.common.short_hash import (
    short_hash,  # noqa: F401  # Phase H-3 source-level regression test requires this import line
)
from katrain.core.analysis import DEFAULT_SKILL_PRESET
from katrain.core.batch.inputs import DEFAULT_TIMEOUT_SECONDS
from katrain.core.batch.models import BatchResult
from katrain.core.batch.orchestration._context import (
    EngineFailureTracker,
    _AnalysisAborted,
    _BatchCuratorContext,
    _BatchFileContext,
    _BatchSummaryContext,
)
from katrain.core.batch.orchestration._curator import _generate_curator_outputs
from katrain.core.batch.orchestration._handle import (
    _collect_stats_for_file,
    _generate_karte_for_file,
    _post_success_processing,
)
from katrain.core.batch.orchestration._process import (
    _handle_analysis_failure,
    _prepare_file_processing,
    _process_single_file,
    _record_engine_failure_and_maybe_abort,
    _run_analysis_with_circuit_breaker,
)
from katrain.core.batch.orchestration._setup import _setup_batch
from katrain.core.batch.orchestration._summary import _generate_summaries


def run_batch(
    katrain: Any,
    engine: Any,
    input_dir: str,
    output_dir: str | None = None,
    visits: int | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    skip_analyzed: bool = False,
    progress_cb: Callable[[int, int, str], None] | None = None,
    log_cb: Callable[[str], None] | None = None,
    cancel_flag: list[bool] | None = None,
    save_analyzed_sgf: bool = True,
    generate_karte: bool = False,
    generate_summary: bool = False,
    karte_player_filter: str | None = None,
    min_games_per_player: int = 3,
    skill_preset: str = DEFAULT_SKILL_PRESET,
    variable_visits: bool = False,
    jitter_pct: float = 10.0,
    deterministic: bool = True,
    lang: str = "jp",
    generate_curator: bool = False,
    user_aggregate: Any = None,
) -> BatchResult:
    """Run batch analysis on a folder of SGF files (including subfolders).

    This is the GUI-callable API for batch analysis. It uses an existing
    KaTrain and engine instance (no new engine startup required).

    See orchestration.py history for the full argument reference.
    """
    result = BatchResult()

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

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
    (
        output_dir,
        sgf_files,
        total,
        batch_timestamp,
        game_stats_list,
        games_for_curator,
        selected_visits_list,
        karte_path_map,
        tracker,
    ) = setup

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
                effective_visits=None,
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


__all__ = [
    "run_batch",
    "EngineFailureTracker",
    "_AnalysisAborted",
    "_BatchFileContext",
    "_BatchSummaryContext",
    "_BatchCuratorContext",
    "_setup_batch",
    "_process_single_file",
    "_prepare_file_processing",
    "_run_analysis_with_circuit_breaker",
    "_record_engine_failure_and_maybe_abort",
    "_handle_analysis_failure",
    "_post_success_processing",
    "_generate_karte_for_file",
    "_collect_stats_for_file",
    "_generate_summaries",
    "_generate_curator_outputs",
]
