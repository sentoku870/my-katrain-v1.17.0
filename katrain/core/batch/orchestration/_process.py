"""Phase 145-C per-file processing helpers (process loop + circuit breaker).

Phase 197 extraction: the 5 helpers that drive a single SGF through the
batch pipeline. ``_process_single_file`` stays a small orchestrator;
the heavier branches (analysis routing, abort bookkeeping) live here.
"""

from __future__ import annotations

import os
import re
import traceback
from collections.abc import Callable
from typing import Any

from katrain.core.batch.orchestration import _handle
from katrain.core.batch.orchestration._context import (
    _AnalysisAborted,
    _BatchFileContext,
)
from katrain.core.batch.visits import choose_visits_for_sgf
from katrain.core.errors import AnalysisTimeoutError, EngineError, SGFError


def _process_single_file(ctx: _BatchFileContext, log: Callable[[str], None]) -> None:
    """Analyze one SGF file and (optionally) generate its karte + stats."""
    base_name, sgf_output_path, effective_visits, need_game = _prepare_file_processing(ctx, log)

    try:
        success, game = _run_analysis_with_circuit_breaker(ctx, sgf_output_path, effective_visits, need_game, log)
    except _AnalysisAborted:
        return

    if not success:
        _handle_analysis_failure(ctx, log)
        return

    _handle._post_success_processing(
        ctx=ctx,
        game=game,
        base_name=base_name,
        sgf_output_path=sgf_output_path,
        effective_visits=effective_visits,
        log=log,
    )


def _prepare_file_processing(
    ctx: _BatchFileContext, log: Callable[[str], None]
) -> tuple[str, str | None, int | None, bool]:
    """Compute output paths, base name, and effective visits."""
    base_name = os.path.splitext(os.path.basename(ctx.rel_path))[0]
    base_name = re.sub(r'[<>:"/\\|?*]', "_", base_name)[:50]

    output_rel_path = ctx.rel_path
    if output_rel_path.lower().endswith((".gib", ".ngf")):
        output_rel_path = output_rel_path[:-4] + ".sgf"
    sgf_output_path = os.path.join(ctx.output_dir, "analyzed", output_rel_path) if ctx.save_analyzed_sgf else None

    need_game = ctx.generate_karte or ctx.generate_summary or ctx.generate_curator

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
    return base_name, sgf_output_path, effective_visits, need_game


def _run_analysis_with_circuit_breaker(
    ctx: _BatchFileContext,
    sgf_output_path: str | None,
    effective_visits: int | None,
    need_game: bool,
    log: Callable[[str], None],
) -> tuple[bool, Any]:
    """Run KataGo analysis and route engine / file errors to the circuit breaker."""
    from katrain.core.batch.analysis import analyze_single_file

    game: Any = None
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
        _record_engine_failure_and_maybe_abort(ctx, log, f"TIMEOUT ({ctx.rel_path}): {e}")
    except EngineError as e:
        _record_engine_failure_and_maybe_abort(ctx, log, f"ENGINE ERROR ({ctx.rel_path}): {e}")
    except (SGFError, OSError, UnicodeDecodeError) as e:
        ctx.result.file_error_count += 1
        ctx.tracker.record_file_error()
        log(f"  FILE ERROR ({ctx.rel_path}): {e}")
    except Exception as e:  # noqa: BLE001
        ctx.result.file_error_count += 1
        ctx.tracker.record_file_error()
        log(f"  UNEXPECTED ({ctx.rel_path}): {e}")
        log(f"    {traceback.format_exc()}")

    if ctx.result.aborted:
        raise _AnalysisAborted
    return success, game


def _record_engine_failure_and_maybe_abort(ctx: _BatchFileContext, log: Callable[[str], None], message: str) -> None:
    """Record an engine failure; trip circuit breaker if threshold reached."""
    ctx.result.engine_failure_count += 1
    log(message)
    if ctx.tracker.record_engine_failure(ctx.rel_path, message):
        log(ctx.tracker.get_abort_message())
        ctx.result.aborted = True
        ctx.result.abort_reason = ctx.tracker.get_abort_message()


def _handle_analysis_failure(ctx: _BatchFileContext, log: Callable[[str], None]) -> None:
    """Record a non-aborting failure (analysis returned False)."""
    if ctx.cancel_flag and ctx.cancel_flag[0]:
        log("Cancelled by user")
        ctx.result.cancelled = True
        return
    ctx.result.fail_count += 1
    if ctx.generate_karte:
        ctx.result.karte_failed += 1
