"""Phase 145-C post-success handling (karte generation + stats collection).

Phase 197 extraction: ``_post_success_processing`` (the success path of
the per-file loop) plus its two helpers — single-file Karte
generation and per-file Stats extraction. Lives here because both
operate on a successful analysis result; the analysis routing itself
lives in :mod:`._process`.
"""

from __future__ import annotations

import os
import traceback
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.common.short_hash import short_hash
from katrain.core.analysis import DEFAULT_SKILL_PRESET
from katrain.core.batch.io_safe import safe_write_file
from katrain.core.batch.models import WriteError
from katrain.core.batch.orchestration._context import _BatchFileContext
from katrain.core.reports.karte.builder import build_karte_json_string
from katrain.core.reports.karte.models import KarteGenerationError

if TYPE_CHECKING:
    from katrain.core.game import Game


def _post_success_processing(
    ctx: _BatchFileContext,
    game: Any,
    base_name: str,
    sgf_output_path: str | None,
    effective_visits: int | None,
    log: Callable[[str], None],
) -> None:
    """Generate karte and/or collect stats for a successful analysis."""
    ctx.tracker.record_success()
    ctx.result.success_count += 1

    if effective_visits is not None:
        ctx.selected_visits_list.append(effective_visits)

    if ctx.save_analyzed_sgf and sgf_output_path:
        ctx.result.analyzed_sgf_written += 1
        log(f"  Saved SGF: {sgf_output_path}")

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


def _generate_karte_for_file(
    game: Game,
    abs_path: str,
    rel_path: str,
    base_name: str,
    output_dir: str,
    player_filter: str | None,
    visits: int | None,
    batch_timestamp: str,
    result: Any,
    karte_path_map: dict[str, str],
    log: Callable[[str], None],
    log_cb: Callable[[str], None] | None,
    skill_preset: str | None = None,
) -> None:
    """Generate and write a single karte file. Updates result in place."""
    try:
        karte_text = build_karte_json_string(
            game,
            player_filter=player_filter,
            target_visits=visits,
            skill_preset=skill_preset or DEFAULT_SKILL_PRESET,
        )
        path_hash = short_hash(rel_path, 6)
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
            karte_path_map[rel_path] = karte_path

    except KarteGenerationError as e:
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
    except Exception as e:  # noqa: BLE001
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
    except Exception as e:  # noqa: BLE001
        log(f"  Unexpected stats error ({rel_path}): {e}")
        log(f"    {traceback.format_exc()}")
