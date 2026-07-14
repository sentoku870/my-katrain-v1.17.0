"""Phase 145-C summary markdown generation.

Phase 197 extraction: per-player summary markdown writer.
"""

from __future__ import annotations

import os
import traceback

from katrain.core.batch.filenames import get_unique_filename, sanitize_filename
from katrain.core.batch.io_safe import safe_write_file
from katrain.core.batch.orchestration._context import _BatchSummaryContext


def _generate_summaries(ctx: _BatchSummaryContext) -> None:
    """Generate per-player summary markdown files."""
    from katrain.core.batch.stats import build_player_summary, extract_players_from_stats

    log = ctx.log
    log("Generating per-player summaries...")

    try:
        player_groups = extract_players_from_stats(
            ctx.game_stats_list, min_games=ctx.min_games_per_player
        )
    except (OSError, KeyError, ValueError) as e:
        ctx.result.summary_error = str(e)
        log(f"Summary generation error: {e}")
        return
    except Exception as e:  # noqa: BLE001
        ctx.result.summary_error = str(e)
        log(f"Unexpected summary error: {e}")
        log(f"  {traceback.format_exc()}")
        return

    if not player_groups:
        log(f"No players with >= {ctx.min_games_per_player} games found")
        ctx.result.summary_error = (
            f"No players with >= {ctx.min_games_per_player} games"
        )
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
        except Exception as e:  # noqa: BLE001
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
