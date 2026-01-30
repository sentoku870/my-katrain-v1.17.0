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
from typing import Any, Dict, List, Optional

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
    risk_management_section,
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
    moves: List[MoveEval],
    player: Optional[str],
) -> Dict[MeaningTagId, int]:
    """Build MeaningTagId counts from cached meaning_tag_id field."""
    filtered = [m for m in moves if player is None or m.player == player]
    tag_ids = [m.meaning_tag_id for m in filtered if m.meaning_tag_id is not None]

    valid_tags: List[MeaningTagId] = []
    for tid in tag_ids:
        try:
            valid_tags.append(MeaningTagId(tid))
        except ValueError:
            continue
    return dict(Counter(valid_tags))


def _compute_style_safe(
    moves: List[MoveEval],
    player: Optional[str],
) -> Optional[StyleResult]:
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
    player_filter: Optional[str] = None,
    raise_on_error: bool = False,
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    target_visits: Optional[int] = None,
    snapshot: Optional[Any] = None,  # Phase 87.5: Accept pre-built snapshot (for Leela)
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

    try:
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

        # 3. Pass snapshot as argument (avoid recomputation in impl)
        return _build_karte_report_impl(
            game,
            snapshot,
            level,
            player_filter,
            skill_preset,
            target_visits=target_visits,
        )

    except MixedEngineSnapshotError:
        # Re-raise dedicated exception (explicitly requested)
        raise

    except Exception as e:
        # Unexpected: Internal bug - traceback required
        import traceback
        error_msg = (
            f"{KARTE_ERROR_CODE_GENERATION_FAILED}\n"
            f"Failed to generate karte: {type(e).__name__}: {e}"
        )
        if game.katrain:
            game.katrain.log(
                f"{error_msg}\n{traceback.format_exc()}", OUTPUT_DEBUG
            )

        if raise_on_error:
            raise KarteGenerationError(
                message=error_msg,
                game_id=game_id,
                focus_player=player_filter,
                context="build_karte_report",
                original_error=e,
            ) from e

        # Return error markdown instead of crashing
        return _build_error_karte(game_id, player_filter, error_msg)


def _build_error_karte(
    game_id: str,
    player_filter: Optional[str],
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


def _normalize_name(name: Optional[str]) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    return re.sub(r"[^0-9a-z]+", "", str(name).casefold())


def _read_aliases(value: Any) -> List[str]:
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
    player_filter: Optional[str],
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    target_visits: Optional[int] = None,
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
        eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[
            eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL
        ],
    )

    # Phase 60: Build pacing map for Time column
    pacing_map: Optional[Dict[int, PacingMetrics]] = None
    try:
        time_data = parse_time_data(game.root)
        if time_data.has_time_data:
            pacing_result = analyze_pacing(time_data, list(snapshot.moves))
            pacing_map = {m.move_number: m for m in pacing_result.pacing_metrics}
    except (ValueError, KeyError) as e:
        # Expected: Time data missing or malformed in SGF (common case)
        logger.debug(f"Time analysis skipped: {e}")
        # pacing_map remains None → all Time columns show "-"
    except Exception:
        # Unexpected: Internal bug - traceback required (optional feature)
        logger.debug("Unexpected time analysis error", exc_info=True)
        # pacing_map remains None → all Time columns show "-"

    # Meta
    board_x, board_y = game.board_size
    filename = os.path.splitext(os.path.basename(game.sgf_filename or ""))[0] or _fmt_val(
        game.root.get_property("GN", None), default=game.game_id
    )
    meta_lines = [
        f"- Board: {board_x}x{board_y}",
        f"- Komi: {_fmt_val(game.komi)}",
        f"- Rules: {_fmt_val(game.rules)}",
        f"- Handicap: {_fmt_val(getattr(game.root, 'handicap', None), default='none')}",
        f"- Game: {filename}",
        f"- Date: {_fmt_val(game.root.get_property('DT', None), default=game.game_id)}",
    ]

    pb = _fmt_val(game.root.get_property("PB", None))
    pw = _fmt_val(game.root.get_property("PW", None))
    br = game.root.get_property("BR", None)
    wr = game.root.get_property("WR", None)
    players_lines = [
        f"- Black: {pb}" + (f" ({br})" if br else ""),
        f"- White: {pw}" + (f" ({wr})" if wr else ""),
    ]

    focus_color: Optional[str] = None
    if game.katrain:
        focus_name = game.katrain.config("general/my_player_name")
        focus_aliases = _read_aliases(game.katrain.config("general/my_player_aliases"))
        focus_names = [n for n in [focus_name, *focus_aliases] if n]
        if focus_names:
            focus_tokens = {_normalize_name(n) for n in focus_names if _normalize_name(n)}
            pb_norm = _normalize_name(pb)
            pw_norm = _normalize_name(pw)
            match_black = pb_norm and any(n in pb_norm for n in focus_tokens)
            match_white = pw_norm and any(n in pw_norm for n in focus_tokens)
            if match_black != match_white:
                focus_color = "B" if match_black else "W"

    # Phase 3: Process player_filter parameter
    filtered_player: Optional[str] = None
    if player_filter:
        if player_filter in ("B", "W"):
            filtered_player = player_filter
        else:
            # Try to match against player names
            user_norm = _normalize_name(player_filter)
            pb_norm = _normalize_name(pb)
            pw_norm = _normalize_name(pw)
            match_black = pb_norm and user_norm in pb_norm
            match_white = pw_norm and user_norm in pw_norm
            if match_black and not match_white:
                filtered_player = "B"
            elif match_white and not match_black:
                filtered_player = "W"
            # If both or neither match, filtered_player stays None (show both)

    # Style Archetype (Phase 57, confidence gating added Phase 66)
    style_result = _compute_style_safe(snapshot.moves, filtered_player)
    if style_result is not None:
        confidence = style_result.confidence
        if confidence >= STYLE_CONFIDENCE_THRESHOLD:
            style_name = i18n._(style_result.archetype.name_key)
            meta_lines.append(f"- Style: {style_name}")
            meta_lines.append(f"- Style Confidence: {confidence:.0%}")
        else:
            # Low confidence: show "Unknown" with data insufficiency note
            unknown_label = i18n._("style:unknown")
            insufficient_label = i18n._("style:insufficient_data")
            meta_lines.append(f"- Style: {unknown_label}")
            meta_lines.append(f"- Style Confidence: {confidence:.0%} ({insufficient_label})")
    else:
        # style_result is None (computation failed)
        unknown_label = i18n._("style:unknown")
        meta_lines.append(f"- Style: {unknown_label}")

    # Compute auto recommendation if skill_preset is "auto"
    auto_recommendation: Optional[eval_metrics.AutoRecommendation] = None
    effective_preset = skill_preset
    if skill_preset == "auto":
        # Use focus_color if available, otherwise use all moves
        if focus_color:
            focus_moves = [m for m in snapshot.moves if m.player == focus_color]
        else:
            focus_moves = list(snapshot.moves)
        auto_recommendation = eval_metrics.recommend_auto_strictness(focus_moves, game_count=1)
        effective_preset = auto_recommendation.recommended_preset

    # Get effective thresholds for classification
    effective_thresholds = eval_metrics.get_skill_preset(effective_preset).score_thresholds

    # Build histogram for distribution section
    histogram = None
    if thresholds:
        try:
            from katrain.core import ai as ai_module

            _sum_stats, histogram, _ptloss = ai_module.game_report(
                game, thresholds=thresholds, depth_filter=None
            )
        except (ValueError, KeyError) as exc:  # pragma: no cover - defensive fallback
            # Expected: Threshold config or game data structure issue
            game.katrain.log(
                f"Histogram generation skipped: {exc}", OUTPUT_DEBUG
            )
            histogram = None
        except Exception as exc:  # pragma: no cover - defensive fallback
            # Unexpected: Internal bug - traceback required
            import traceback
            game.katrain.log(
                f"Unexpected histogram error: {exc}\n{traceback.format_exc()}", OUTPUT_DEBUG
            )
            histogram = None

    # Bucket label function for distribution
    def bucket_label(bucket_idx: int) -> str:
        cls_idx = len(thresholds) - 1 - bucket_idx
        if cls_idx == 0:
            return f">= {thresholds[0]}"
        if cls_idx == len(thresholds) - 1:
            return f"< {thresholds[-2]}"
        upper = thresholds[cls_idx - 1]
        lower = thresholds[cls_idx]
        return f"{lower} - {upper}"

    # Important moves table (top N derived from existing settings)
    important_moves = game.get_important_move_evals(level=level)

    # Phase 47: Classify meaning tags for each important move
    total_moves = len(snapshot.moves)
    classification_context = ClassificationContext(total_moves=total_moves)
    for mv in important_moves:
        if mv.meaning_tag_id is None:
            meaning_tag = classify_meaning_tag(mv, context=classification_context)
            mv.meaning_tag_id = meaning_tag.id.value

    # Build KarteContext for section generators
    ctx = KarteContext(
        snapshot=snapshot,
        game=game,
        thresholds=thresholds,
        effective_thresholds=effective_thresholds,
        effective_preset=effective_preset,
        auto_recommendation=auto_recommendation,
        confidence_level=confidence_level,
        pacing_map=pacing_map,
        histogram=histogram,
        board_x=board_x,
        board_y=board_y,
        pb=pb,
        pw=pw,
        focus_color=focus_color,
        important_moves=important_moves,
        total_moves=total_moves,
        settings=settings,
        skill_preset=skill_preset,
        target_visits=target_visits,
        lang=lang,
    )

    # Assemble sections
    sections: List[str] = ["## Meta", *meta_lines, ""]
    sections += ["## Players", *players_lines, ""]
    sections += ["## Notes", "- loss is measured for the player who played the move.", ""]
    sections += definitions_section(ctx, auto_recommendation)
    sections += data_quality_section(ctx)

    # Phase 62: Risk Management - only include if style confidence is sufficient (Phase 66)
    if style_result is not None and style_result.confidence >= STYLE_CONFIDENCE_THRESHOLD:
        sections += risk_management_section(ctx)

    # Phase 3: Apply player filter to sections
    if filtered_player is None:
        # Show both players (current behavior)
        if focus_color:
            focus_name = "Black" if focus_color == "B" else "White"
            sections += [
                f"## Summary (Focus: {focus_name})",
                *summary_lines_for(ctx, focus_color),
                "",
            ]
            # Phase 4: focus_color がある場合、相手サマリーを追加
            sections += opponent_summary_for(ctx, focus_color)
        sections += ["## Summary (Black)", *summary_lines_for(ctx, "B"), ""]
        sections += ["## Summary (White)", *summary_lines_for(ctx, "W"), ""]
        if focus_color:
            focus_name = "Black" if focus_color == "B" else "White"
            sections += [
                f"## Distributions (Focus: {focus_name})",
                *distribution_lines_for(ctx, focus_color, bucket_label),
                "",
            ]
        sections += [
            "## Distributions (Black)",
            *distribution_lines_for(ctx, "B", bucket_label),
            "",
        ]
        sections += [
            "## Distributions (White)",
            *distribution_lines_for(ctx, "W", bucket_label),
            "",
        ]
        # Phase 4: focus_color がある場合、共通困難局面を追加
        if focus_color:
            sections += common_difficult_positions(ctx)
    else:
        # Show only filtered player
        filtered_name = "Black" if filtered_player == "B" else "White"
        # Show focus section only if it matches the filter
        if focus_color and focus_color == filtered_player:
            sections += [
                f"## Summary (Focus: {filtered_name})",
                *summary_lines_for(ctx, focus_color),
                "",
            ]
        sections += [
            f"## Summary ({filtered_name})",
            *summary_lines_for(ctx, filtered_player),
            "",
        ]
        # Phase 4: 相手サマリーを追加
        sections += opponent_summary_for(ctx, filtered_player)
        if focus_color and focus_color == filtered_player:
            sections += [
                f"## Distributions (Focus: {filtered_name})",
                *distribution_lines_for(ctx, focus_color, bucket_label),
                "",
            ]
        sections += [
            f"## Distributions ({filtered_name})",
            *distribution_lines_for(ctx, filtered_player, bucket_label),
            "",
        ]
        # Phase 4: 共通困難局面を追加
        sections += common_difficult_positions(ctx)

    focus_label = "Focus"

    # Diagnosis sections
    if filtered_player is None:
        # Show both players
        if focus_color:
            focus_name = "Black" if focus_color == "B" else "White"
            # Urgent Miss Detection first
            sections += urgent_miss_section_for(ctx, focus_color, focus_name)
            sections += weakness_hypothesis_for(ctx, focus_color, focus_name)
            sections += practice_priorities_for(ctx, focus_color, focus_name)
            sections += mistake_streaks_for(ctx, focus_color, focus_name)

        if focus_color:
            sections += important_lines_for(ctx, focus_color, focus_label)
            sections.append("")
            # Phase 50: Critical 3 (Focus player)
            sections += critical_3_section_for(ctx, focus_color, focus_label, level)
            # Phase 12: Tag distribution for Focus player
            sections += reason_tags_distribution_for(ctx, focus_color, focus_label)
        sections += important_lines_for(ctx, "B", "Black")
        sections.append("")
        # Phase 50: Critical 3 (Black)
        sections += critical_3_section_for(ctx, "B", "Black", level)
        # Phase 12: Tag distribution for Black
        sections += reason_tags_distribution_for(ctx, "B", "Black")
        sections += important_lines_for(ctx, "W", "White")
        sections.append("")
        # Phase 50: Critical 3 (White)
        sections += critical_3_section_for(ctx, "W", "White", level)
        # Phase 12: Tag distribution for White
        sections += reason_tags_distribution_for(ctx, "W", "White")
    else:
        # Show only filtered player
        filtered_name = "Black" if filtered_player == "B" else "White"
        if focus_color and focus_color == filtered_player:
            # Urgent Miss Detection first
            sections += urgent_miss_section_for(ctx, focus_color, filtered_name)
            sections += weakness_hypothesis_for(ctx, focus_color, filtered_name)
            sections += practice_priorities_for(ctx, focus_color, filtered_name)
            sections += mistake_streaks_for(ctx, focus_color, filtered_name)

        if focus_color and focus_color == filtered_player:
            sections += important_lines_for(ctx, focus_color, focus_label)
            sections.append("")
            # Phase 50: Critical 3 (Focus player)
            sections += critical_3_section_for(ctx, focus_color, focus_label, level)
            sections += reason_tags_distribution_for(ctx, focus_color, focus_label)
        sections += important_lines_for(ctx, filtered_player, filtered_name)
        sections.append("")
        # Phase 50: Critical 3 (filtered player)
        sections += critical_3_section_for(ctx, filtered_player, filtered_name, level)
        sections += reason_tags_distribution_for(ctx, filtered_player, filtered_name)

    return "\n".join(sections)
