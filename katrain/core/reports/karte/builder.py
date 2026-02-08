"""Karte report builder - main entry points.

This module contains the main entry functions for karte report generation:
- build_karte_report(): Main entry point (with error handling)
- _build_karte_report_impl(): Implementation
- _build_error_karte(): Error fallback

Also contains internal helpers used by tests:
- _build_tag_counts_from_moves(): Build MeaningTag counts
- _compute_style_safe(): Compute style with graceful fallback
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from typing import Any

from katrain.core import eval_metrics
from katrain.core.analysis.meaning_tags import (
    ClassificationContext,
    MeaningTagId,
    classify_meaning_tag,
)
from katrain.core.analysis.models import EvalSnapshot, MoveEval
from katrain.core.analysis.skill_radar import compute_radar_from_moves
from katrain.core.analysis.style import StyleResult, determine_style
from katrain.core.analysis.time import PacingMetrics, analyze_pacing, parse_time_data
from katrain.core.constants import OUTPUT_DEBUG
from katrain.core.lang import i18n
from katrain.core.reports.karte.helpers import is_single_engine_snapshot
from katrain.core.reports.karte.models import (
    KARTE_ERROR_CODE_GENERATION_FAILED,
    KARTE_ERROR_CODE_MIXED_ENGINE,
    STYLE_CONFIDENCE_THRESHOLD,
    KarteGenerationError,
    MixedEngineSnapshotError,
)
from katrain.core.reports.karte.sections.context import KarteContext
from katrain.core.reports.karte.sections.diagnosis import (
    mistake_streaks_for,
    practice_priorities_for,
    urgent_miss_section_for,
    weakness_hypothesis_for,
)
from katrain.core.reports.karte.sections.important_moves import (
    critical_3_section_for,
    important_lines_for,
    reason_tags_distribution_for,
)
from katrain.core.reports.karte.sections.metadata import (
    data_quality_section,
    definitions_section,

)
from katrain.core.reports.karte.sections.summary import (
    common_difficult_positions,
    distribution_lines_for,
    opponent_summary_for,
    summary_lines_for,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Style Archetype helpers (Phase 57)
# ---------------------------------------------------------------------------


def _build_tag_counts_from_moves(
    moves: list[MoveEval],
    player: str | None,
) -> dict[MeaningTagId, int]:
    """Build MeaningTagId counts from cached meaning_tag_id field."""
    filtered = [m for m in moves if player is None or m.player == player]
    tag_ids = [m.meaning_tag_id for m in filtered if m.meaning_tag_id is not None]

    valid_tags: list[MeaningTagId] = []
    for tid in tag_ids:
        try:
            valid_tags.append(MeaningTagId(tid))
        except ValueError:
            continue
    return dict(Counter(valid_tags))


def _compute_style_safe(
    moves: list[MoveEval],
    player: str | None,
) -> StyleResult | None:
    """Compute style with graceful fallback on error."""
    try:
        radar = compute_radar_from_moves(moves, player=player)
        tag_counts = _build_tag_counts_from_moves(moves, player)
        return determine_style(radar, tag_counts)
    except (ValueError, KeyError) as e:
        # Expected: External data structure issue (optional feature)
        logger.debug(f"Style computation skipped: {e}")
        return None
    except Exception:
        # Unexpected: Internal bug - traceback required (optional feature)
        logger.debug("Unexpected style computation error", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def build_karte_report(
    game: Any,  # Game object (Protocol in future)
    level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
    player_filter: str | None = None,
    raise_on_error: bool = False,
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    target_visits: int | None = None,
    snapshot: Any | None = None,  # Phase 87.5: Accept pre-built snapshot (for Leela)
    lang: str = "ja",
) -> str:
    """Build a compact, markdown-friendly report for the current game.

    Args:
        game: Game object providing game state and analysis data
        level: Important move level setting
        player_filter: Filter by player ("B", "W", or None for both)
                      Can also be a username string to match against player names
        raise_on_error: If True, raise exceptions on failure.
                       If False (default), return error markdown instead.
        skill_preset: Skill preset for strictness ("auto" or one of SKILL_PRESETS keys)
        target_visits: Target visits for effective reliability threshold calculation.
            If None, uses the hardcoded RELIABILITY_VISITS_THRESHOLD (200).
        snapshot: Optional pre-built EvalSnapshot. If provided, uses this instead of
            calling game.build_eval_snapshot(). Used for Leela analysis where
            the snapshot is returned separately from the Game object.

    Returns:
        Markdown-formatted karte report.
        On error with raise_on_error=False, returns a report with ERROR section.

    Raises:
        MixedEngineSnapshotError: If raise_on_error=True and snapshot contains
            both KataGo and Leela analysis data.
        KarteGenerationError: If raise_on_error=True and generation fails
            for other reasons.
    """
    game_id = game.game_id or game.sgf_filename or "unknown"

    # 1. Compute snapshot once (avoid double computation)
    # Phase 87.5: Use provided snapshot or build from game
    if snapshot is None:
        snapshot = game.build_eval_snapshot()

    # 2. Mixed-engine check (Phase 37: enforcement point)
    if not is_single_engine_snapshot(snapshot):
        error_msg = (
            f"{KARTE_ERROR_CODE_MIXED_ENGINE}\n"
            "Mixed-engine analysis detected. "
            "KataGo and Leela data cannot be combined in a single karte."
        )
        if raise_on_error:
            raise MixedEngineSnapshotError(error_msg)
        return _build_error_karte(game_id, player_filter, error_msg)

    # 3. Pass snapshot as argument
    try:
        return _build_karte_report_impl(
            game=game,
            snapshot=snapshot,
            level=level,
            player_filter=player_filter,
            skill_preset=skill_preset,
            target_visits=target_visits,
            lang=lang,
        )
    except Exception as e:
        import traceback
        # Hardcoded debug path for guaranteed visibility
        debug_log_path = "d:/github/katrain-1.17.0/debug_error.log"
        try:
            with open(debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"Error for {game_id}: {e}\n{traceback.format_exc()}\n")
        except:
            pass # Ignore logging failure
        raise


def _build_error_karte(
    game_id: str,
    player_filter: str | None,
    error_msg: str,
) -> str:
    """Build a minimal karte with ERROR section when generation fails."""
    sections = [
        "# Karte (ERROR)",
        "",
        "## Meta",
        f"- Game: {game_id}",
        f"- Player Filter: {player_filter or 'both'}",
        "",
        "## ERROR",
        "",
        "Karte generation failed with the following error:",
        "",
        "```",
        error_msg,
        "```",
        "",
        "Please check:",
        "- The game has been analyzed (KT property present)",
        "- The SGF file is not corrupted",
        "- KataGo engine is running correctly",
        "",
    ]
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


def _fmt_val(val: Any, default: str = "unknown") -> str:
    """Format value or return default."""
    return default if val in [None, ""] else str(val)


def _normalize_name(name: str | None) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    return re.sub(r"[^0-9a-z]+", "", str(name).casefold())


def _read_aliases(value: Any) -> list[str]:
    """Read aliases from config value."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        return [v.strip() for v in re.split(r"[;,]", value) if v.strip()]
    return []


def _build_karte_report_impl(
    game: Any,  # Game object
    snapshot: EvalSnapshot,  # Pre-computed snapshot (avoid double computation)
    level: str,
    player_filter: str | None,
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    target_visits: int | None = None,
    lang: str = "ja",
) -> str:
    """Internal implementation of build_karte_report.

    Args:
        game: Game object providing game state
        snapshot: Pre-computed EvalSnapshot (passed from build_karte_report)
        level: Important move level setting
        player_filter: Filter by player ("B", "W", or None for both)
        skill_preset: Skill preset for strictness
        target_visits: Target visits for effective reliability threshold calculation.
            If None, uses the hardcoded RELIABILITY_VISITS_THRESHOLD (200).
        lang: Language code for localized labels ("ja" or "en"), defaults to "ja".

    Note:
        snapshot is now passed as an argument rather than computed here.
        This avoids double computation since build_karte_report() already
        computes the snapshot for mixed-engine validation.
    """
    thresholds = game.katrain.config("trainer/eval_thresholds") if game.katrain else []

    # Compute confidence level for section gating
    confidence_level = eval_metrics.compute_confidence_level(snapshot.moves)
    settings = eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
        level,
        eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL],
    )

    # Phase 60: Build pacing map for Time column
    # (Pacing map is not currently used in JSON export, but could be added later)
    
    from katrain.core.reports.karte.json_export import build_karte_json
    import json
    
    json_data = build_karte_json(
        game=game,
        level=level,
        player_filter=player_filter,
        skill_preset=skill_preset,
        lang=lang
    )
    
    json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
    return json_str
