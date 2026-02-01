"""Aggregation functions and i18n helpers for batch statistics.

This module contains:
- build_batch_summary()
- Evidence support functions
- i18n getter functions
- Helper functions for formatting

Dependencies:
- models.py (constants only)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from katrain.core.batch.helpers import (
    escape_markdown_table_cell,
    format_game_display_label,
    format_game_link_target,
    truncate_game_name,
)
from katrain.common.locale_utils import normalize_lang_code

from .models import (
    EvidenceMove,
    TIER_LABELS,
    AXIS_LABELS,
    AXIS_PRACTICE_HINTS,
    AXIS_PRACTICE_HINTS_LOCALIZED,
    MTAG_PRACTICE_HINTS,
    RTAG_PRACTICE_HINTS,
    PRACTICE_INTRO_TEXTS,
    NOTES_HEADERS,
    HINT_LINE_FORMATS,
    PERCENTAGE_NOTES,
    COLOR_BIAS_NOTES,
    PHASE_PRIORITY_TEXTS,
    PHASE_LABELS_LOCALIZED,
    SECTION_HEADERS,
)

# Import types for type hints
from katrain.core.analysis.skill_radar import (
    RadarAxis,
    SkillTier,
    AggregatedRadarResult,
    round_score,
)
from katrain.core.eval_metrics import (
    MistakeCategory,
    get_reason_tag_label,
)

_logger = logging.getLogger("katrain.core.batch.stats")

if TYPE_CHECKING:
    pass


# =============================================================================
# Evidence Support (Phase 66)
# =============================================================================


def _select_evidence_moves(
    candidates: list[EvidenceMove],
    max_count: int = 2,
) -> list[EvidenceMove]:
    """Select representative evidence moves with game deduplication.

    Args:
        candidates: List of EvidenceMove objects
        max_count: Maximum moves to return

    Returns:
        Selected moves, deduplicated by game, sorted by loss descending

    Selection criteria:
        - Only MISTAKE or BLUNDER categories (already filtered by caller)
        - points_lost is not None (already guaranteed by worst_moves source)
        - Stable sort: loss desc, move_number asc, game_name asc
    """
    # Sort: loss desc, move_number asc, game_name asc (deterministic)
    sorted_candidates = sorted(
        candidates,
        key=lambda e: (-e.points_lost, e.move_number, e.game_name),
    )

    # Dedupe by game_name
    seen_games: set[str] = set()
    selected = []
    for ev in sorted_candidates:
        if ev.game_name not in seen_games:
            selected.append(ev)
            seen_games.add(ev.game_name)
        if len(selected) >= max_count:
            break

    return selected


def _format_evidence_with_links(
    evidence: list[EvidenceMove],
    karte_path_map: dict[str, str] | None,
    summary_dir: str | None,
    lang: str = "jp",
) -> str:
    """Format evidence moves with karte links (Markdown-safe).

    Args:
        evidence: List of EvidenceMove objects
        karte_path_map: Mapping from game_name to karte file path
        summary_dir: Directory containing the summary file (for relative links)
        lang: Language code

    Returns:
        Formatted string like "例: `Game1` #12 Q16 (-8.5目) [カルテ](link), ..."
        or "(該当する代表例なし)" if empty

    Note:
        - Game name wrapped in backticks (`) to avoid bracket issues in Markdown
        - Uses format_game_link_target() for consistent URL encoding
    """
    import os

    if not evidence:
        return "(該当する代表例なし)" if lang == "jp" else "(no representative examples)"

    prefix = "例: " if lang == "jp" else "e.g.: "
    parts = []

    for ev in evidence:
        # Format loss as points (already in points unit from worst_moves)
        loss_label = f"-{ev.points_lost:.1f}目" if lang == "jp" else f"-{ev.points_lost:.1f}pt"

        # Build display label (short) - NO escaping needed, will be wrapped in backticks
        display = format_game_display_label(ev.game_name, max_len=20, escape_mode="none")

        # Build link if available
        karte_path = karte_path_map.get(ev.game_name) if karte_path_map else None
        if karte_path and summary_dir:
            # Make relative to summary_dir
            try:
                rel_path = os.path.relpath(karte_path, summary_dir)
            except ValueError:
                # Cross-drive on Windows
                rel_path = os.path.basename(karte_path)
            rel_path = rel_path.replace("\\", "/")
            link_target = format_game_link_target(rel_path, preserve_path=True)

            link_text = "カルテ" if lang == "jp" else "karte"
            # Wrap display in backticks for Markdown safety
            parts.append(
                f"`{display}` #{ev.move_number} {ev.gtp or '-'} ({loss_label}) [{link_text}]({link_target})"
            )
        else:
            parts.append(f"`{display}` #{ev.move_number} {ev.gtp or '-'} ({loss_label})")

    return prefix + ", ".join(parts)


# =============================================================================
# Batch Summary
# =============================================================================


def build_batch_summary(
    game_stats_list: list[dict[str, Any]],
    focus_player: str | None = None,
) -> str:
    """Build a multi-game summary markdown from collected stats.

    Args:
        game_stats_list: List of game stats dictionaries
        focus_player: Optional player name to focus on

    Returns:
        Markdown string with the summary
    """
    if not game_stats_list:
        return "# Multi-Game Summary\n\nNo games processed."

    lines = ["# Multi-Game Summary\n"]
    lines.append(f"**Games analyzed**: {len(game_stats_list)}\n")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Aggregate stats
    total_moves = sum(s["total_moves"] for s in game_stats_list)
    total_loss = sum(s["total_points_lost"] for s in game_stats_list)

    lines.append("\n## Overview\n")
    lines.append(f"- Total moves: {total_moves}")
    lines.append(f"- Total points lost: {total_loss:.1f}")
    if total_moves > 0:
        lines.append(f"- Average loss per move: {total_loss / total_moves:.2f}")

    # Phase x Mistake breakdown
    lines.append("\n## Phase x Mistake Breakdown\n")

    phase_mistake_counts: dict[tuple[str, str], int] = {}
    phase_mistake_loss: dict[tuple[str, str], float] = {}
    for stats in game_stats_list:
        for key, count in stats.get("phase_mistake_counts", {}).items():
            phase_mistake_counts[key] = phase_mistake_counts.get(key, 0) + count
        for key, loss in stats.get("phase_mistake_loss", {}).items():
            phase_mistake_loss[key] = phase_mistake_loss.get(key, 0.0) + loss

    if phase_mistake_counts:
        lines.append("| Phase | Mistake | Count | Total Loss |")
        lines.append("|-------|---------|------:|----------:|")
        for key in sorted(phase_mistake_counts.keys(), key=lambda x: phase_mistake_loss.get(x, 0), reverse=True):
            phase, category = key
            count = phase_mistake_counts[key]
            loss = phase_mistake_loss.get(key, 0.0)
            lines.append(f"| {phase} | {category} | {count} | {loss:.1f} |")

    # Worst moves across all games
    lines.append("\n## Top 10 Worst Moves (All Games)\n")
    all_worst: list[tuple[str, int, str, str, float, MistakeCategory | None]] = []
    for stats in game_stats_list:
        game_name = stats["game_name"]
        for move_num, player, gtp, loss, cat in stats.get("worst_moves", []):
            all_worst.append((game_name, move_num, player, gtp, loss, cat))

    all_worst.sort(key=lambda x: x[4], reverse=True)
    all_worst = all_worst[:10]

    if all_worst:
        lines.append("| Game | Move | Player | Position | Loss | Category |")
        lines.append("|------|-----:|:------:|----------|-----:|----------|")
        for game_name, move_num, player, gtp, loss, cat in all_worst:
            cat_name = cat.name if cat else "—"
            display_name = escape_markdown_table_cell(truncate_game_name(game_name))
            lines.append(f"| {display_name} | {move_num} | {player} | {gtp} | {loss:.1f} | {cat_name} |")

    # Games list
    lines.append("\n## Games Included\n")
    for i, stats in enumerate(game_stats_list, 1):
        game_name = stats["game_name"]
        loss = stats["total_points_lost"]
        moves = stats["total_moves"]
        lines.append(f"{i}. {game_name} — {moves} moves, {loss:.1f} pts lost")

    return "\n".join(lines)


# =============================================================================
# i18n Getter Functions
# =============================================================================


def get_phase_priority_text(key: str, lang: str = "jp", **kwargs: Any) -> str:
    """Get localized phase priority text with optional formatting."""
    normalized = normalize_lang_code(lang)
    texts = PHASE_PRIORITY_TEXTS.get(normalized, PHASE_PRIORITY_TEXTS["en"])
    template = texts.get(key, "")
    if kwargs:
        return template.format(**kwargs)
    return template


def get_phase_label_localized(phase: str, lang: str = "jp") -> str:
    """Get localized phase label."""
    normalized = normalize_lang_code(lang)
    labels = PHASE_LABELS_LOCALIZED.get(normalized, PHASE_LABELS_LOCALIZED["en"])
    return labels.get(phase, phase)


def get_section_header(key: str, lang: str = "jp") -> str:
    """Get localized section header."""
    normalized = normalize_lang_code(lang)
    headers = SECTION_HEADERS.get(normalized, SECTION_HEADERS["en"])
    return headers.get(key, key)


def get_practice_intro_text(lang: str = "jp") -> str:
    """Get localized practice intro text."""
    normalized = normalize_lang_code(lang)
    return PRACTICE_INTRO_TEXTS.get(normalized, PRACTICE_INTRO_TEXTS["en"])


def get_notes_header(lang: str = "jp") -> str:
    """Get localized notes header."""
    normalized = normalize_lang_code(lang)
    return NOTES_HEADERS.get(normalized, NOTES_HEADERS["en"])


def get_axis_practice_hint(axis: RadarAxis, lang: str = "jp") -> str:
    """Get localized practice hint for a radar axis."""
    normalized = normalize_lang_code(lang)
    hints = AXIS_PRACTICE_HINTS_LOCALIZED.get(normalized, AXIS_PRACTICE_HINTS_LOCALIZED["en"])
    return hints.get(axis, "")


def get_mtag_practice_hint(tag_id: str, lang: str = "jp") -> str | None:
    """Get localized practice hint for a meaning tag ID.

    Args:
        tag_id: Meaning tag ID (lowercase snake_case, e.g., "connection_miss")
        lang: Language code ("jp", "en", "ja")

    Returns:
        Hint text or None if tag not found
    """
    normalized = normalize_lang_code(lang)
    hints = MTAG_PRACTICE_HINTS.get(normalized, MTAG_PRACTICE_HINTS["en"])
    return hints.get(tag_id.lower())


def get_rtag_practice_hint(tag: str, lang: str = "jp") -> str | None:
    """Get localized practice hint for a reason tag.

    Args:
        tag: Reason tag (lowercase snake_case, e.g., "need_connect")
        lang: Language code ("jp", "en", "ja")

    Returns:
        Hint text or None if tag not found
    """
    normalized = normalize_lang_code(lang)
    hints = RTAG_PRACTICE_HINTS.get(normalized, RTAG_PRACTICE_HINTS["en"])
    return hints.get(tag.lower())


def format_hint_line(label: str, count: int, hint: str, lang: str = "jp") -> str:
    """Format a practice hint line with localized format.

    Args:
        label: Tag label (localized)
        count: Occurrence count
        hint: Practice hint text
        lang: Language code

    Returns:
        Formatted hint line (JP: "**label**（N回）→ hint", EN: "**label** (Nx) -> hint")
    """
    normalized = normalize_lang_code(lang)
    fmt = HINT_LINE_FORMATS.get(normalized, HINT_LINE_FORMATS["en"])
    return fmt.format(label=label, count=count, hint=hint)


def get_percentage_note(lang: str = "jp") -> str:
    """Get localized percentage explanation note."""
    normalized = normalize_lang_code(lang)
    return PERCENTAGE_NOTES.get(normalized, PERCENTAGE_NOTES["en"])


def get_color_bias_note(bias: str, lang: str = "jp") -> str:
    """Get localized color bias note.

    Args:
        bias: "B" for all-Black, "W" for all-White
        lang: Language code

    Returns:
        Localized note text
    """
    normalized = normalize_lang_code(lang)
    notes = COLOR_BIAS_NOTES.get(normalized, COLOR_BIAS_NOTES["en"])
    return notes.get(bias, "")


# =============================================================================
# Helper Functions
# =============================================================================


def detect_color_bias(player_games: list[tuple[dict[str, Any], str]]) -> str | None:
    """Detect if all games are played as one color.

    Args:
        player_games: List of (stats, role) tuples

    Returns:
        "B" if all Black, "W" if all White, None if mixed
    """
    if not player_games:
        return None
    b_games = sum(1 for _, role in player_games if role == "B")
    w_games = sum(1 for _, role in player_games if role == "W")
    if b_games > 0 and w_games == 0:
        return "B"
    elif w_games > 0 and b_games == 0:
        return "W"
    return None


def get_dominant_tags(
    tag_counts: dict[str, int],
    min_count: int = 3,
    max_tags: int = 3,
) -> list[tuple[str, int]]:
    """Get dominant tags sorted by count.

    Args:
        tag_counts: Dict of tag -> count
        min_count: Minimum count to include
        max_tags: Maximum number of tags to return

    Returns:
        List of (tag, count) tuples, sorted by count descending
    """
    qualified = [(tag, count) for tag, count in tag_counts.items() if count >= min_count]
    qualified.sort(key=lambda x: -x[1])
    return qualified[:max_tags]


def build_tag_based_hints(
    mtag_counts: dict[str, int],
    rtag_counts: dict[str, int],
    lang: str = "jp",
    min_count: int = 3,
    max_hints: int = 4,
) -> list[str]:
    """Build practice hint lines based on dominant meaning/reason tags.

    Args:
        mtag_counts: Meaning tag ID -> count
        rtag_counts: Reason tag -> count
        lang: Language code
        min_count: Minimum occurrences to include
        max_hints: Maximum total hints to generate

    Returns:
        List of formatted hint lines (empty if no qualified tags with hints)
    """
    from katrain.core.analysis.meaning_tags.integration import get_meaning_tag_label_safe
    from katrain.common.locale_utils import to_iso_lang_code

    hints = []

    # Get dominant meaning tags
    top_mtags = get_dominant_tags(mtag_counts, min_count, max_hints)
    for tag_id, count in top_mtags:
        hint = get_mtag_practice_hint(tag_id, lang)
        if hint:
            # Get localized label for meaning tag (needs ISO code for lookup)
            iso_lang = to_iso_lang_code(lang)
            label = get_meaning_tag_label_safe(tag_id, iso_lang)
            if label:
                hints.append(format_hint_line(label, count, hint, lang))

    # Get dominant reason tags if we have room
    remaining = max_hints - len(hints)
    if remaining > 0:
        top_rtags = get_dominant_tags(rtag_counts, min_count, remaining)
        for tag, count in top_rtags:
            hint = get_rtag_practice_hint(tag, lang)
            if hint:
                label = get_reason_tag_label(tag, fallback_to_raw=True)
                hints.append(format_hint_line(label, count, hint, lang))

    return hints


def _get_tier_label(tier: SkillTier) -> str:
    """Get display label for a tier."""
    return TIER_LABELS.get(tier, "N/A")


def _get_axis_label(axis: RadarAxis) -> str:
    """Get display label for an axis."""
    return AXIS_LABELS.get(axis, axis.value)


def _build_skill_profile_section(
    radar: AggregatedRadarResult | None,
    lang: str = "jp",
) -> list[str]:
    """Build Skill Profile section for player summary.

    Args:
        radar: Aggregated radar result, or None if no data
        lang: Language code for output ("jp", "en", "ja")

    Returns:
        List of markdown lines to append to summary
    """
    lines = [f"\n{get_section_header('skill_profile', lang)}\n"]

    if not radar:
        lines.append("*No radar data available (requires 19x19 games with analysis)*\n")
        return lines

    # Overall tier header
    overall_label = _get_tier_label(radar.overall_tier)
    lines.append(f"**Overall: {overall_label}** ({radar.games_aggregated} games aggregated)\n")

    # 5-axis table
    lines.append("| Axis | Score | Tier | Moves |")
    lines.append("|------|------:|------|------:|")

    for axis in RadarAxis:
        axis_label = _get_axis_label(axis)
        score = getattr(radar, axis.value)
        tier = getattr(radar, f"{axis.value}_tier")
        count = radar.valid_move_counts.get(axis, 0)

        # Format score (use round_score for display)
        score_str = "N/A" if score is None else f"{round_score(score)}"
        tier_str = _get_tier_label(tier)

        lines.append(f"| {axis_label} | {score_str} | {tier_str} | {count} |")

    # Weak areas (score < 2.5)
    weak_axes = [
        (axis, getattr(radar, axis.value))
        for axis in RadarAxis
        if radar.is_weak_axis(axis)
    ]

    if weak_axes:
        # Sort by score (lowest first)
        weak_axes.sort(key=lambda x: x[1])
        weak_list = [
            f"{_get_axis_label(axis)} ({round_score(score)})"
            for axis, score in weak_axes
        ]
        lines.append("")
        lines.append(f"{get_section_header('weak_areas', lang)}: {', '.join(weak_list)}")

        # Practice priorities (max 2)
        lines.append("")
        lines.append(get_section_header("practice_label", lang))
        for axis, _ in weak_axes[:2]:
            hint = get_axis_practice_hint(axis, lang)
            if hint:
                lines.append(f"- {_get_axis_label(axis)}: {hint}")

    # JSON output block
    lines.extend(_build_radar_json_section(radar))

    return lines


def _build_radar_json_section(
    radar: AggregatedRadarResult | None,
) -> list[str]:
    """Build JSON output block for radar data.

    Args:
        radar: Aggregated radar result, or None

    Returns:
        List of markdown lines with JSON block
    """
    if not radar:
        return []

    import json

    # Use canonical to_dict() - single source of truth
    data = radar.to_dict()

    return [
        "\n### Radar Data (JSON)\n",
        "```json",
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
    ]
