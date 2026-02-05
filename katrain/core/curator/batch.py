"""Batch output generation for Curator (Phase 64).

This module generates curator_ranking.json and replay_guide.json
from batch-analyzed games.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .guide_extractor import extract_replay_guide
from .models import UNCERTAIN_TAG, SuitabilityScore
from .scoring import score_batch_suitability

if TYPE_CHECKING:
    from katrain.core.analysis.skill_radar import AggregatedRadarResult
    from katrain.core.game import Game


# =============================================================================
# Constants
# =============================================================================

FLOAT_PRECISION = 3
JSON_VERSION = "1.0"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CuratorBatchResult:
    """Result of curator batch output generation.

    Attributes:
        ranking_path: Path to curator_ranking.json (str, not Path)
        guide_path: Path to replay_guide.json (str, not Path)
        games_scored: Number of games scored
        guides_generated: Number of replay guides generated
        errors: List of error messages
    """

    ranking_path: str | None = None
    guide_path: str | None = None
    games_scored: int = 0
    guides_generated: int = 0
    errors: list[str] = field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================


def _round_float(value: float) -> float:
    """Round float to FLOAT_PRECISION decimal places for JSON output."""
    return round(value, FLOAT_PRECISION)


def _normalize_percentile(score: SuitabilityScore) -> int:
    """Normalize Optional[int] percentile to int for JSON output.

    Returns 0 if percentile is None (should not happen in batch context).
    """
    return score.percentile if score.percentile is not None else 0


def _get_iso_generated_timestamp() -> str:
    """Get timezone-aware ISO timestamp for JSON.

    Format: 2026-01-26T15:30:00+09:00 (with seconds precision)
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _build_game_title(stats: dict[str, Any]) -> str:
    """Build display title from game stats.

    Uses player names if available, otherwise falls back to game_name.
    Format: "Player B vs Player W" or game_name as fallback.
    """
    player_b = stats.get("player_b", "")
    player_w = stats.get("player_w", "")

    if player_b and player_w:
        return f"{player_b} vs {player_w}"

    # Fallback to game name without path/extension
    game_name = stats.get("game_name", "Unknown")
    return Path(game_name).stem


def _extract_recommended_tags(
    stats: dict[str, Any],
    max_tags: int = 3,
) -> list[str]:
    """Extract recommended tags from game stats.

    Tags are sorted by occurrence count (descending), then alphabetically for ties.
    UNCERTAIN tags are excluded.

    Args:
        stats: Game stats dict with meaning_tags_by_player
        max_tags: Maximum number of tags to return

    Returns:
        List of tag IDs, sorted by count desc then alphabetically
    """
    meaning_tags_by_player = stats.get("meaning_tags_by_player", {})

    # Combine tags from both players
    combined: dict[str, int] = {}
    for player_tags in meaning_tags_by_player.values():
        for tag, count in player_tags.items():
            if tag == UNCERTAIN_TAG:
                continue  # Skip UNCERTAIN
            combined[tag] = combined.get(tag, 0) + count

    if not combined:
        return []

    # Sort by count desc, then alphabetically for deterministic output
    sorted_tags = sorted(
        combined.items(),
        key=lambda x: (-x[1], x[0]),
    )

    return [tag for tag, _ in sorted_tags[:max_tags]]


def _get_user_weak_axes_sorted(
    user_aggregate: AggregatedRadarResult | None,
) -> list[str]:
    """Get user's weak axes as sorted list of axis values.

    Returns empty list if no user aggregate.
    Axes are sorted alphabetically for deterministic output.
    """
    if user_aggregate is None:
        return []

    from katrain.core.curator.models import SUPPORTED_AXES

    weak_axes = [axis.value for axis in SUPPORTED_AXES if user_aggregate.is_weak_axis(axis)]
    return sorted(weak_axes)


# =============================================================================
# Main Function
# =============================================================================


def generate_curator_outputs(
    games_and_stats: list[tuple[Game, dict[str, Any]]],
    curator_dir: str,
    batch_timestamp: str,
    user_aggregate: AggregatedRadarResult | None = None,
    lang: str = "jp",
    log_cb: Callable[[str], None] | None = None,
) -> CuratorBatchResult:
    """Generate curator_ranking.json and replay_guide.json.

    Args:
        games_and_stats: List of (Game, stats dict) tuples
        curator_dir: Output directory (created if not exists)
        batch_timestamp: Timestamp string for filename (e.g., "20260126-153000")
        user_aggregate: User's aggregated radar for scoring (optional)
        lang: Internal language code ("jp" or "en")
        log_cb: Optional callback for logging

    Returns:
        CuratorBatchResult with paths and counts

    Directory Creation:
        curator_dir is created if it doesn't exist (parents=True, exist_ok=True).

    Float Precision:
        needs_match, stability, total are rounded to 3 decimal places.
        score_loss in highlight_moments is rounded to 2 decimal places.

    Percentile Handling:
        If score.percentile is None, it is normalized to 0 in JSON output.

    Empty Batch Rule:
        When games_and_stats is empty, write valid empty JSON files.
    """
    result = CuratorBatchResult()

    # Create output directory
    Path(curator_dir).mkdir(parents=True, exist_ok=True)

    # Log callback helper
    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    log(f"Generating curator outputs for {len(games_and_stats)} games...")

    # Score all games
    scores = score_batch_suitability(user_aggregate, games_and_stats)
    result.games_scored = len(scores)

    # Build rankings
    rankings: list[dict[str, Any]] = []
    for i, ((_game, stats), score) in enumerate(zip(games_and_stats, scores, strict=False)):
        game_id = stats.get("game_name", f"game_{i}")
        rankings.append(
            {
                "game_id": game_id,
                "title": _build_game_title(stats),
                "score_percentile": _normalize_percentile(score),
                "needs_match": _round_float(score.needs_match),
                "stability": _round_float(score.stability),
                "total": _round_float(score.total),
                "recommended_tags": _extract_recommended_tags(stats),
            }
        )

    # Sort rankings by percentile desc, total desc, game_id asc
    sorted_rankings = sorted(
        rankings,
        key=lambda r: (
            -r["score_percentile"],
            -r["total"],
            r["game_id"],
        ),
    )

    # Assign ranks after sorting
    for i, ranking in enumerate(sorted_rankings, start=1):
        ranking["rank"] = i

    # Generate timestamp
    generated_ts = _get_iso_generated_timestamp()

    # Build ranking JSON
    ranking_data = {
        "version": JSON_VERSION,
        "generated": generated_ts,
        "total_games": len(games_and_stats),
        "user_weak_axes": _get_user_weak_axes_sorted(user_aggregate),
        "rankings": sorted_rankings,
    }

    # Write ranking file
    ranking_filename = f"curator_ranking_{batch_timestamp}.json"
    ranking_path = Path(curator_dir) / ranking_filename
    try:
        with open(ranking_path, "w", encoding="utf-8") as f:
            json.dump(ranking_data, f, ensure_ascii=False, indent=2)
        result.ranking_path = str(ranking_path)
        log(f"Written: {ranking_filename}")
    except OSError as e:
        # Expected: File I/O error
        result.errors.append(f"Failed to write {ranking_filename}: {e}")
        log(f"Error writing {ranking_filename}: {e}")
    except Exception as e:
        # Unexpected: Internal bug - traceback required
        import traceback

        result.errors.append(f"Unexpected error writing {ranking_filename}: {e}")
        log(f"Unexpected error writing {ranking_filename}: {e}\n{traceback.format_exc()}")

    # Generate replay guides
    guides: list[dict[str, Any]] = []
    for game, stats in games_and_stats:
        game_id = stats.get("game_name", "unknown")
        try:
            guide = extract_replay_guide(
                game=game,
                game_id=game_id,
                game_title=_build_game_title(stats),
                total_moves=stats.get("total_moves", 0),
                max_highlights=5,
                lang=lang,
                level="normal",
            )
            guides.append(guide.to_dict())
            result.guides_generated += 1
        except (KeyError, ValueError) as e:
            # Expected: Game data structure or value issue
            result.errors.append(f"Guide extraction skipped for {game_id}: {e}")
            log(f"Guide extraction skipped for {game_id}: {e}")
        except Exception as e:
            # Unexpected: Internal bug - traceback required
            import traceback

            result.errors.append(f"Unexpected error extracting guide for {game_id}: {e}")
            log(f"Unexpected error extracting guide for {game_id}: {e}\n{traceback.format_exc()}")

    # Build guide JSON
    guide_data = {
        "version": JSON_VERSION,
        "generated": generated_ts,
        "total_games": len(games_and_stats),
        "games": guides,
    }

    # Write guide file
    guide_filename = f"replay_guide_{batch_timestamp}.json"
    guide_path = Path(curator_dir) / guide_filename
    try:
        with open(guide_path, "w", encoding="utf-8") as f:
            json.dump(guide_data, f, ensure_ascii=False, indent=2)
        result.guide_path = str(guide_path)
        log(f"Written: {guide_filename}")
    except OSError as e:
        # Expected: File I/O error
        result.errors.append(f"Failed to write {guide_filename}: {e}")
        log(f"Error writing {guide_filename}: {e}")
    except Exception as e:
        # Unexpected: Internal bug - traceback required
        import traceback

        result.errors.append(f"Unexpected error writing {guide_filename}: {e}")
        log(f"Unexpected error writing {guide_filename}: {e}\n{traceback.format_exc()}")

    log(
        f"Curator outputs complete: {result.games_scored} scored, "
        f"{result.guides_generated} guides, {len(result.errors)} errors"
    )

    return result
