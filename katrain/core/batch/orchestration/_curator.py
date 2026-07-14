"""Phase 64 curator ranking and guide generation."""

from __future__ import annotations

import json
import os
import traceback

from katrain.core.batch.orchestration._context import _BatchCuratorContext


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
    except Exception as e:  # noqa: BLE001
        ctx.result.curator_errors.append(f"Curator unexpected error: {e}")
        ctx.log(f"Unexpected curator error: {e}")
        ctx.log(f"  {traceback.format_exc()}")
