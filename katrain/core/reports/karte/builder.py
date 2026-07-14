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
import re
from collections import Counter
from typing import Any

from katrain.core import analysis as eval_metrics
from katrain.core.analysis.meaning_tags import (
    MeaningTagId,
)
from katrain.core.analysis.models import EvalSnapshot, MoveEval
from katrain.core.reports.karte.models import (
    KARTE_ERROR_CODE_GENERATION_FAILED,
    KarteGenerationError,
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

    Returns:
        Markdown-formatted karte report.
        On error with raise_on_error=False, returns a report with ERROR section.

    Raises:
        KarteGenerationError: If raise_on_error=True and generation fails.

    Note:
        Phase B-4: removed the previously-accepted ``snapshot`` parameter.
        No production caller passed one, and the parameter was effectively
        dead since the snapshot is now always built inside this function
        (the only test that passed one — tests/test_logging.py — was
        updated to omit the argument).
    """
    game_id = game.game_id or game.sgf_filename or "unknown"

    # 1. Build snapshot. Phase 138: wrap in try/except so this function
    # honors its contract of returning error markdown (or raising
    # KarteGenerationError) even when snapshot construction itself fails.
    try:
        snapshot = game.build_eval_snapshot()
    except Exception as e:
        error_msg = f"{KARTE_ERROR_CODE_GENERATION_FAILED}\nSnapshot construction failed: {type(e).__name__}: {e}"
        if raise_on_error:
            raise KarteGenerationError(error_msg, game_id=game_id) from e
        return _build_error_karte(game_id, player_filter, error_msg)

    # 2. Phase 171: KataGo 専用化により mixed-engine check を削除。
    # 以前は is_single_engine_snapshot() で Leela データを弾いていたが、
    # Leela 自体が廃止されたため不要。

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
        error_msg = f"{KARTE_ERROR_CODE_GENERATION_FAILED}\n{type(e).__name__}: {e}"
        if raise_on_error:
            raise KarteGenerationError(error_msg, game_id=game_id) from e
        return _build_error_karte(game_id, player_filter, error_msg)


def _build_error_karte(
    game_id: str,
    player_filter: str | None,
    error_msg: str,
) -> str:
    """Build a minimal karte with ERROR section when generation fails.

    Phase G-2: the user-facing strings in this template go through
    ``i18n._()`` so the Japanese locale gets a properly translated
    error karte. The original strings remain as the default (English)
    catalog entry in :mod:`katrain.i18n.locales` so a locale switch
    failure (or running outside the GUI) does not break this path.
    """
    from katrain.core.lang import i18n

    sections = [
        f"# {i18n._('karte:error:title')}",
        "",
        i18n._("karte:error:meta_header"),
        f"- {i18n._('karte:error:game_label')}: {game_id}",
        f"- {i18n._('karte:error:player_filter_label')}: {player_filter or i18n._('karte:error:player_filter_both')}",
        "",
        i18n._("karte:error:section_title"),
        "",
        i18n._("karte:error:intro"),
        "",
        "```",
        error_msg,
        "```",
        "",
        i18n._("karte:error:checklist_header"),
        f"- {i18n._('karte:error:check_analyzed')}",
        f"- {i18n._('karte:error:check_sgf')}",
        f"- {i18n._('karte:error:check_katago')}",
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

        This wrapper delegates entirely to build_karte_json (Phase 149 A-8:
        removed unused local vars; markdown section code is being revived
        as JSON data in Sub-phase C).
    """
    import json

    from katrain.core.reports.karte.json_export import build_karte_json

    json_data = build_karte_json(
        game=game,
        level=level,
        player_filter=player_filter,
        skill_preset=skill_preset,
        lang=lang,
    )

    json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
    return json_str
