"""Player summary formatting for batch statistics.

This module contains:
- build_player_summary()

Dependencies:
- models.py (EvidenceMove)
- aggregation.py (helper functions, i18n getters)

IMPORTANT: Do NOT import from katrain.core.batch.stats (package entry point)
to avoid circular imports. Only import from .models and .aggregation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from katrain.core.analysis.presentation import get_auto_confidence_label
from katrain.core.analysis.skill_radar import (
    RadarMetrics,
    aggregate_radar,
    radar_from_dict,
)
from katrain.core.batch.helpers import (
    escape_markdown_table_cell,
    make_markdown_link_target,
    truncate_game_name,
)
from katrain.core.eval_metrics import (
    DEFAULT_SKILL_PRESET,
    SKILL_PRESET_LABELS,
    SKILL_PRESETS,
    AutoConfidence,
    AutoRecommendation,
    MistakeCategory,
    PositionDifficulty,
    _distance_from_range,
    compute_effective_threshold,
    get_phase_thresholds,
    get_reason_tag_label,
)

from .aggregation import (
    _build_skill_profile_section,
    _format_evidence_with_links,
    _select_evidence_moves,
    build_tag_based_hints,
    detect_color_bias,
    get_color_bias_note,
    get_notes_header,
    get_phase_label_localized,
    get_phase_priority_text,
    get_practice_intro_text,
    get_section_header,
)

# Import from sibling modules (NOT from package entry point)
from .models import EvidenceMove


def build_player_summary(
    player_name: str,
    player_games: list[tuple[dict[str, Any], str]],
    skill_preset: str = DEFAULT_SKILL_PRESET,
    *,
    analysis_settings: dict[str, Any] | None = None,
    karte_path_map: dict[str, str] | None = None,
    summary_dir: str | None = None,
    lang: str = "jp",
) -> str:
    """
    Build summary for a single player across their games.

    Args:
        player_name: Display name of the player
        player_games: List of (game_stats, role) tuples where role is "B" or "W"
        skill_preset: Skill preset for strictness ("auto" or one of SKILL_PRESETS keys)
        analysis_settings: Optional dict with configured analysis settings:
            - config_visits: base visits value
            - variable_visits: bool, whether variable visits is enabled
            - jitter_pct: float, jitter percentage (if variable_visits)
            - deterministic: bool, whether deterministic mode (if variable_visits)
            - timeout: float or None, timeout in seconds
        karte_path_map: Optional mapping from rel_path to absolute karte file path
        summary_dir: Directory where the summary file is being written (for relative links)
        lang: Language code for output ("jp", "en", "ja"). Defaults to "jp".

    Returns:
        Markdown summary string
    """
    lines = [f"# Player Summary: {player_name}\n"]
    lines.append(f"**Games analyzed**: {len(player_games)}\n")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Aggregate only this player's moves across all games
    total_moves = 0
    total_loss = 0.0
    all_worst: list[tuple[str, int, str, float, MistakeCategory | None]] = []
    games_as_black = 0
    games_as_white = 0

    # Aggregated per-player stats
    mistake_counts: dict[MistakeCategory, int] = {cat: 0 for cat in MistakeCategory}
    mistake_total_loss: dict[MistakeCategory, float] = {cat: 0.0 for cat in MistakeCategory}
    freedom_counts: dict[PositionDifficulty, int] = {diff: 0 for diff in PositionDifficulty}
    phase_moves: dict[str, int] = {"opening": 0, "middle": 0, "yose": 0, "unknown": 0}
    phase_loss: dict[str, float] = {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0}
    phase_mistake_counts: dict[tuple[str, str], int] = {}
    phase_mistake_loss: dict[tuple[str, str], float] = {}
    reason_tags_counts: dict[str, int] = {}  # Issue 2: aggregate reason tags
    meaning_tags_counts: dict[str, int] = {}  # Phase 47: aggregate meaning tags
    # PR1-1: Important moves stats for Reason Tags clarity
    important_moves_total = 0
    tagged_moves_total = 0
    tag_occurrences_total = 0

    # Reliability stats for Data Quality section
    reliability_total = 0
    reliability_reliable = 0
    reliability_low_conf = 0
    reliability_total_visits = 0
    reliability_with_visits = 0
    reliability_max_visits = 0  # PR1-2: Track max visits across all games
    board_sizes: set[int] = set()  # Track unique board sizes for Definitions

    # Phase 49: Radar metrics collection for aggregation
    radar_list: list[RadarMetrics] = []

    for stats, role in player_games:
        if role == "B":
            games_as_black += 1
        else:
            games_as_white += 1

        # Only count this player's moves/loss
        total_moves += stats["moves_by_player"].get(role, 0)
        total_loss += stats["loss_by_player"].get(role, 0.0)

        # Aggregate per-player mistake counts
        if "mistake_counts_by_player" in stats and role in stats["mistake_counts_by_player"]:
            for cat, count in stats["mistake_counts_by_player"][role].items():
                mistake_counts[cat] = mistake_counts.get(cat, 0) + count
        if "mistake_total_loss_by_player" in stats and role in stats["mistake_total_loss_by_player"]:
            for cat, loss in stats["mistake_total_loss_by_player"][role].items():
                mistake_total_loss[cat] = mistake_total_loss.get(cat, 0.0) + loss

        # Aggregate per-player freedom counts
        if "freedom_counts_by_player" in stats and role in stats["freedom_counts_by_player"]:
            for diff, count in stats["freedom_counts_by_player"][role].items():
                freedom_counts[diff] = freedom_counts.get(diff, 0) + count

        # Aggregate per-player phase stats
        if "phase_moves_by_player" in stats and role in stats["phase_moves_by_player"]:
            for phase, count in stats["phase_moves_by_player"][role].items():
                phase_moves[phase] = phase_moves.get(phase, 0) + count
        if "phase_loss_by_player" in stats and role in stats["phase_loss_by_player"]:
            for phase, loss in stats["phase_loss_by_player"][role].items():
                phase_loss[phase] = phase_loss.get(phase, 0.0) + loss

        # Aggregate per-player phase x mistake counts
        if "phase_mistake_counts_by_player" in stats and role in stats["phase_mistake_counts_by_player"]:
            for key, count in stats["phase_mistake_counts_by_player"][role].items():
                phase_mistake_counts[key] = phase_mistake_counts.get(key, 0) + count
        if "phase_mistake_loss_by_player" in stats and role in stats["phase_mistake_loss_by_player"]:
            for key, loss in stats["phase_mistake_loss_by_player"][role].items():
                phase_mistake_loss[key] = phase_mistake_loss.get(key, 0.0) + loss

        # Collect worst moves for this player
        for move_num, player, gtp, loss, cat in stats.get("worst_moves", []):
            if player == role:
                all_worst.append((stats["game_name"], move_num, gtp, loss, cat))

        # Aggregate reason tags (Issue 2)
        if "reason_tags_by_player" in stats and role in stats["reason_tags_by_player"]:
            for tag, count in stats["reason_tags_by_player"][role].items():
                reason_tags_counts[tag] = reason_tags_counts.get(tag, 0) + count

        # Phase 47: Aggregate meaning tags for Top 3 Mistake Types
        if "meaning_tags_by_player" in stats and role in stats["meaning_tags_by_player"]:
            for tag, count in stats["meaning_tags_by_player"][role].items():
                meaning_tags_counts[tag] = meaning_tags_counts.get(tag, 0) + count

        # PR1-1: Aggregate important moves stats for Reason Tags clarity
        if "important_moves_stats_by_player" in stats and role in stats["important_moves_stats_by_player"]:
            im_stats = stats["important_moves_stats_by_player"][role]
            important_moves_total += im_stats.get("important_count", 0)
            tagged_moves_total += im_stats.get("tagged_count", 0)
            tag_occurrences_total += im_stats.get("tag_occurrences", 0)

        # Aggregate reliability stats for Data Quality
        if "reliability_by_player" in stats and role in stats["reliability_by_player"]:
            rel = stats["reliability_by_player"][role]
            reliability_total += rel.get("total", 0)
            reliability_reliable += rel.get("reliable", 0)
            reliability_low_conf += rel.get("low_confidence", 0)
            reliability_total_visits += rel.get("total_visits", 0)
            reliability_with_visits += rel.get("with_visits", 0)
            # PR1-2: Track max visits across all games
            game_max = rel.get("max_visits", 0)
            if game_max > reliability_max_visits:
                reliability_max_visits = game_max

        # Track board sizes for Definitions section
        if "board_size" in stats:
            board_sizes.add(stats["board_size"][0])  # (x, y) tuple, use x

        # Phase 49: Collect radar metrics for aggregation
        if "radar_by_player" in stats:
            radar_dict = stats["radar_by_player"].get(role)
            if radar_dict:
                radar = radar_from_dict(radar_dict)
                if radar:
                    radar_list.append(radar)

    # Phase 49: Aggregate radar metrics
    aggregated_radar = aggregate_radar(radar_list)  # Uniform weighting only

    # =========================================================================
    # Compute auto recommendation if skill_preset is "auto"
    # =========================================================================
    game_count = len(player_games)
    auto_recommendation: AutoRecommendation | None = None
    effective_preset = skill_preset

    if skill_preset == "auto" and reliability_total > 0:
        # For multi-game summaries, we use aggregated mistake_counts
        # to compute blunder/important counts without re-scanning moves
        rel_pct = 100.0 * reliability_reliable / reliability_total if reliability_total > 0 else 0.0

        # Count blunders and important moves from aggregated stats
        blunder_count = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        important_count = blunder_count + mistake_counts.get(MistakeCategory.MISTAKE, 0)

        # Target ranges scaled by game count
        target_blunder = (3 * game_count, 10 * game_count)
        target_important = (10 * game_count, 30 * game_count)

        # Calculate scores for each preset
        b_score = _distance_from_range(blunder_count, target_blunder) * 2
        i_score = _distance_from_range(important_count, target_important) * 1
        total_score = b_score + i_score

        # Reliability gate
        if rel_pct < 20.0:
            conf = AutoConfidence.LOW
            effective_preset = "standard"
            reason = f"Low reliability ({rel_pct:.1f}%)"
        else:
            # Determine confidence based on score
            if total_score == 0:
                conf = AutoConfidence.HIGH
            elif total_score <= 5:
                conf = AutoConfidence.MEDIUM
            else:
                conf = AutoConfidence.LOW

            # Heuristic: adjust preset based on blunder density
            blunder_per_game = blunder_count / game_count if game_count > 0 else 0
            if blunder_per_game > 10:
                effective_preset = "advanced"  # Too many blunders, use stricter
            elif blunder_per_game < 3:
                effective_preset = "beginner"  # Too few blunders, use looser
            else:
                effective_preset = "standard"
            reason = f"blunder={blunder_count}, important={important_count}"

        auto_recommendation = AutoRecommendation(
            recommended_preset=effective_preset,
            confidence=conf,
            blunder_count=blunder_count,
            important_count=important_count,
            score=total_score,
            reason=reason,
        )

    # =========================================================================
    # Definitions Section (before Overview)
    # =========================================================================
    preset = SKILL_PRESETS.get(effective_preset, SKILL_PRESETS[DEFAULT_SKILL_PRESET])
    t1, t2, t3 = preset.score_thresholds

    # Build strictness info line using JP labels
    effective_label = SKILL_PRESET_LABELS.get(effective_preset, effective_preset)
    if skill_preset == "auto" and auto_recommendation:
        # Phase 53: Use get_auto_confidence_label for 推定確度 (not 信頼度)
        conf_label = get_auto_confidence_label(auto_recommendation.confidence.value)
        strictness_info = (
            f"自動 → {effective_label} "
            f"({conf_label}, "
            f"大悪手={auto_recommendation.blunder_count}, 重要={auto_recommendation.important_count})"
        )
    else:
        strictness_info = f"{effective_label} (手動)"

    lines.append("\n## Definitions\n")
    lines.append(f"- Strictness: {strictness_info}")

    # Feature 3: Show auto recommendation hint even in manual mode
    if skill_preset != "auto" and game_count > 0:
        # Compute auto recommendation for hint
        blunder_count = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        important_count = blunder_count + mistake_counts.get(MistakeCategory.MISTAKE, 0)
        rel_pct = 100.0 * reliability_reliable / reliability_total if reliability_total > 0 else 0.0

        # Simplified auto recommendation for multi-game context
        target_blunder = (3 * game_count, 10 * game_count)
        target_important = (10 * game_count, 30 * game_count)
        b_score = _distance_from_range(blunder_count, target_blunder) * 2
        i_score = _distance_from_range(important_count, target_important) * 1
        total_score = b_score + i_score

        if rel_pct < 20.0:
            hint_conf = AutoConfidence.LOW
            hint_preset = "standard"
        else:
            if total_score == 0:
                hint_conf = AutoConfidence.HIGH
            elif total_score <= 5:
                hint_conf = AutoConfidence.MEDIUM
            else:
                hint_conf = AutoConfidence.LOW

            blunder_per_game = blunder_count / game_count if game_count > 0 else 0
            if blunder_per_game > 10:
                hint_preset = "advanced"
            elif blunder_per_game < 3:
                hint_preset = "beginner"
            else:
                hint_preset = "standard"

        hint_label = SKILL_PRESET_LABELS.get(hint_preset, hint_preset)
        # Phase 53: Use get_auto_confidence_label for 推定確度
        hint_conf_label = get_auto_confidence_label(hint_conf.value)
        lines.append(f"- Auto recommended: {hint_label} ({hint_conf_label})")

    lines.append("")
    lines.append("| Metric | Definition |")
    lines.append("|--------|------------|")
    lines.append("| Points Lost | Score difference between actual move and best move (clamped to ≥0) |")
    lines.append(f"| Good | Loss < {t1:.1f} pts |")
    lines.append(f"| Inaccuracy | Loss {t1:.1f} - {t2:.1f} pts |")
    lines.append(f"| Mistake | Loss {t2:.1f} - {t3:.1f} pts |")
    lines.append(f"| Blunder | Loss ≥ {t3:.1f} pts |")

    # Phase thresholds - handle mixed board sizes
    if len(board_sizes) == 1:
        board_size = list(board_sizes)[0]
        opening_end, middle_end = get_phase_thresholds(board_size)
        lines.append(
            f"| Phase ({board_size}x{board_size}) | Opening: <{opening_end}, Middle: {opening_end}-{middle_end - 1}, Endgame: ≥{middle_end} |"
        )
    else:
        lines.append("| Phase | Mixed board sizes - thresholds vary |")

    # =========================================================================
    # Analysis Settings Section (configured values)
    # =========================================================================
    if analysis_settings:
        lines.append("\n## Analysis Settings\n")
        # Config visits
        config_visits = analysis_settings.get("config_visits")
        if config_visits is not None:
            lines.append(f"- Config visits: {config_visits:,}")

        # Variable visits settings
        variable_visits = analysis_settings.get("variable_visits", False)
        if variable_visits:
            lines.append("- Variable visits: on")
            jitter_pct = analysis_settings.get("jitter_pct")
            if jitter_pct is not None:
                lines.append(f"- Visits jitter: {jitter_pct}%")
            deterministic = analysis_settings.get("deterministic", False)
            lines.append(f"- Deterministic: {'on' if deterministic else 'off'}")
            # Show actual selected visits distribution (if recorded)
            selected_stats = analysis_settings.get("selected_visits_stats")
            if selected_stats:
                lines.append(
                    f"- Selected visits (per game): "
                    f"min={selected_stats['min']}, "
                    f"avg={selected_stats['avg']:.1f}, "
                    f"max={selected_stats['max']}"
                )
        else:
            lines.append("- Variable visits: off")

        # Timeout
        timeout = analysis_settings.get("timeout")
        if timeout is not None:
            lines.append(f"- Timeout: {timeout}s")
        else:
            lines.append("- Timeout: None")

        # Reliable threshold (Phase 44: relative to config_visits, capped at 200)
        config_visits = analysis_settings.get("config_visits")
        effective_threshold = compute_effective_threshold(config_visits)
        lines.append(f"- Reliable threshold: {effective_threshold} visits")

    # =========================================================================
    # Data Quality Section (PR1-2: Add max visits and measured note)
    # Phase 44: Use effective threshold (relative to config_visits, capped at 200)
    # =========================================================================
    # Compute effective threshold for Data Quality display
    dq_config_visits = analysis_settings.get("config_visits") if analysis_settings else None
    dq_effective_threshold = compute_effective_threshold(dq_config_visits)

    lines.append("\n## Data Quality\n")
    lines.append(f"- Moves analyzed: {reliability_total}")
    if reliability_total > 0:
        rel_pct = 100.0 * reliability_reliable / reliability_total
        low_pct = 100.0 * reliability_low_conf / reliability_total
        lines.append(f"- Reliable (visits ≥ {dq_effective_threshold}): {reliability_reliable} ({rel_pct:.1f}%)")
        lines.append(f"- Low-confidence: {reliability_low_conf} ({low_pct:.1f}%)")
        if reliability_with_visits > 0:
            avg_visits = reliability_total_visits / reliability_with_visits
            lines.append(f"- Avg visits: {avg_visits:,.0f}")
            # PR1-2: Add max visits to help users understand the data
            if reliability_max_visits > 0:
                lines.append(f"- Max visits: {reliability_max_visits:,}")
        if rel_pct < 20.0:
            lines.append("")
            lines.append("⚠ Low analysis reliability (<20%). Results may be unstable.")
    # PR1-2: Add note about measured values
    lines.append("")
    lines.append("*Visits are measured from KataGo analysis (root_visits).*")

    # =========================================================================
    # Phase 49: Skill Profile Section
    # =========================================================================
    lines.extend(_build_skill_profile_section(aggregated_radar, lang=lang))

    # =========================================================================
    # Section 1: Overview
    # =========================================================================
    lines.append("\n## Overview\n")
    lines.append(f"- Games as Black: {games_as_black}")
    lines.append(f"- Games as White: {games_as_white}")
    lines.append(f"- Total moves: {total_moves}")
    lines.append(f"- Total points lost: {total_loss:.1f}")
    if total_moves > 0:
        lines.append(f"- Average loss per move: {total_loss / total_moves:.2f}")

    # Per-game metrics
    games_analyzed = len(player_games)
    if games_analyzed > 0:
        points_per_game = total_loss / games_analyzed
        blunders_total = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        mistakes_total = mistake_counts.get(MistakeCategory.MISTAKE, 0)
        important_total = blunders_total + mistakes_total
        blunders_per_game = blunders_total / games_analyzed
        important_per_game = important_total / games_analyzed
        lines.append("")
        lines.append("**Per-game averages:**")
        lines.append(f"- Points lost/game: {points_per_game:.1f}")
        lines.append(f"- Blunders/game: {blunders_per_game:.1f}")
        lines.append(f"- Mistakes+Blunders/game: {important_per_game:.1f}")
    else:
        lines.append("")
        lines.append("**Per-game averages:** -")

    # =========================================================================
    # Section 2: Mistake Distribution
    # =========================================================================
    lines.append("\n## Mistake Distribution\n")
    lines.append("| Category | Count | Percentage | Avg Loss |")
    lines.append("|----------|------:|------------|----------|")

    category_labels = {
        MistakeCategory.GOOD: "Good",
        MistakeCategory.INACCURACY: "Inaccuracy",
        MistakeCategory.MISTAKE: "Mistake",
        MistakeCategory.BLUNDER: "Blunder",
    }

    total_categorized = sum(mistake_counts.values())
    for cat in [MistakeCategory.GOOD, MistakeCategory.INACCURACY, MistakeCategory.MISTAKE, MistakeCategory.BLUNDER]:
        count = mistake_counts.get(cat, 0)
        pct = (count / total_categorized * 100) if total_categorized > 0 else 0.0
        avg_loss = (mistake_total_loss.get(cat, 0.0) / count) if count > 0 else 0.0
        lines.append(f"| {category_labels[cat]} | {count} | {pct:.1f}% | {avg_loss:.2f} |")

    # =========================================================================
    # Section 3: Phase Breakdown
    # =========================================================================
    lines.append("\n## Phase Breakdown\n")
    lines.append("| Phase | Moves | Points Lost | Avg Loss |")
    lines.append("|-------|------:|------------:|----------|")

    phase_labels = {
        "opening": "Opening",
        "middle": "Middle game",
        "yose": "Endgame",
        "unknown": "Unknown",
    }

    for phase in ["opening", "middle", "yose", "unknown"]:
        count = phase_moves.get(phase, 0)
        loss = phase_loss.get(phase, 0.0)
        avg_loss = (loss / count) if count > 0 else 0.0
        lines.append(f"| {phase_labels.get(phase, phase)} | {count} | {loss:.1f} | {avg_loss:.2f} |")

    # =========================================================================
    # Section 4: Phase × Mistake Breakdown
    # =========================================================================
    lines.append("\n## Phase × Mistake Breakdown\n")
    lines.append("| Phase | Good | Inaccuracy | Mistake | Blunder | Total Loss |")
    lines.append("|-------|------|------------|---------|---------|------------|")

    for phase in ["opening", "middle", "yose"]:
        cells = [phase_labels.get(phase, phase)]

        for cat in [MistakeCategory.GOOD, MistakeCategory.INACCURACY, MistakeCategory.MISTAKE, MistakeCategory.BLUNDER]:
            key = (phase, cat.name)
            count = phase_mistake_counts.get(key, 0)
            loss = phase_mistake_loss.get(key, 0.0)

            if count > 0 and cat != MistakeCategory.GOOD:
                cells.append(f"{count} ({loss:.1f})")
            else:
                cells.append(str(count))

        # Total loss for this phase
        phase_total_loss = phase_loss.get(phase, 0.0)
        cells.append(f"{phase_total_loss:.1f}")

        lines.append("| " + " | ".join(cells) + " |")

    # =========================================================================
    # Section 5: Top 10 Worst Moves (Phase 53: added カルテ column)
    # =========================================================================
    lines.append("\n## Top 10 Worst Moves\n")
    all_worst.sort(key=lambda x: x[3], reverse=True)
    all_worst = all_worst[:10]

    if all_worst:
        lines.append("| Game | Move | Position | Loss | Category | カルテ |")
        lines.append("|------|-----:|----------|-----:|----------|--------|")
        for game_name, move_num, gtp, loss, cat in all_worst:
            cat_name = cat.name if cat else "—"
            display_name = escape_markdown_table_cell(truncate_game_name(game_name))

            # Phase 53: Generate karte link if mapping available
            karte_path = karte_path_map.get(game_name) if karte_path_map else None
            if karte_path and summary_dir:
                link_target = make_markdown_link_target(summary_dir, karte_path)
                karte_cell = f"[表示]({link_target})"
            else:
                karte_cell = "-"

            lines.append(f"| {display_name} | {move_num} | {gtp} | {loss:.1f} | {cat_name} | {karte_cell} |")
    else:
        lines.append("- No significant mistakes found.")

    # =========================================================================
    # Section 6: Reason Tags Distribution (Issue 2 + PR1-1 clarity)
    # =========================================================================
    lines.append("\n## Reason Tags (Top 10)\n")

    # PR1-1: Add explanatory note about what is counted
    if important_moves_total > 0:
        lines.append(
            f"*Tags computed for {important_moves_total} important moves "
            f"(mistakes/blunders with loss ≥ threshold). "
            f"{tagged_moves_total} moves had ≥1 tag.*\n"
        )

    if reason_tags_counts:
        # Sort by count desc, then by tag name asc for deterministic ordering
        sorted_tags = sorted(reason_tags_counts.items(), key=lambda x: (-x[1], x[0]))[:10]  # Top 10

        # PR1-1: Use tag_occurrences_total as denominator (sum of all tag counts)
        # Percentage = this tag's occurrences / total tag occurrences
        for tag, count in sorted_tags:
            pct = (count / tag_occurrences_total * 100) if tag_occurrences_total > 0 else 0.0
            label = get_reason_tag_label(tag, fallback_to_raw=True)
            lines.append(f"- {label}: {count} ({pct:.1f}%)")
    else:
        lines.append("- No reason tags recorded.")

    # =========================================================================
    # Section 6b: Top 3 Mistake Types (Phase 47: Meaning Tags)
    # =========================================================================
    lines.append("\n## Top 3 Mistake Types\n")

    # Phase 66: Filter out UNCERTAIN before counting
    from katrain.core.analysis.meaning_tags.models import MeaningTagId

    uncertain_value = MeaningTagId.UNCERTAIN.value  # "uncertain"
    filtered_counts = {tag_id: count for tag_id, count in meaning_tags_counts.items() if tag_id != uncertain_value}

    if filtered_counts:
        total_classified = sum(filtered_counts.values())
        # Sort by count desc, then by tag name asc for deterministic ordering
        sorted_tags = sorted(filtered_counts.items(), key=lambda x: (-x[1], x[0]))[:3]  # Top 3

        top3_total = sum(count for _, count in sorted_tags)
        other_count = total_classified - top3_total

        for tag_id, count in sorted_tags:
            pct = (count / total_classified * 100) if total_classified > 0 else 0.0
            # Use safe label getter with current UI language
            from katrain.core.analysis.meaning_tags import get_meaning_tag_label_safe

            label = get_meaning_tag_label_safe(tag_id, lang) or tag_id
            lines.append(f"- {label}: {count} ({pct:.1f}%)")

        # Phase 66: Add localized clarification note
        lines.append("")
        uncertain_count = meaning_tags_counts.get(uncertain_value, 0)
        if lang == "jp":
            uncertain_label = "分類困難"
            note = f"*分類済み: {total_classified}件（「{uncertain_label}」{uncertain_count}件を除く）。Top 3 以外: {other_count}件*"
        else:
            uncertain_label = "Uncertain"
            note = f'*Classified: {total_classified} (excluding "{uncertain_label}" {uncertain_count}). Other than Top 3: {other_count}*'
        lines.append(note)
    else:
        lines.append("- No meaning tags classified.")

    # =========================================================================
    # Section 7: Weakness Hypothesis
    # =========================================================================
    lines.append("\n## Weakness Hypothesis\n")

    # Determine weaknesses based on cross-tabulation
    weaknesses = []

    # Check phase with highest average loss
    phase_avg: dict[str, float] = {}
    for phase in ["opening", "middle", "yose"]:
        count = phase_moves.get(phase, 0)
        loss = phase_loss.get(phase, 0.0)
        if count > 0:
            phase_avg[phase] = loss / count

    if phase_avg:
        worst_phase = max(phase_avg.items(), key=lambda x: x[1])
        if worst_phase[1] > 0.5:  # Only if avg loss > 0.5
            weaknesses.append(
                f"**{phase_labels.get(worst_phase[0], worst_phase[0])}** shows highest "
                f"average loss ({worst_phase[1]:.2f} pts/move)"
            )

    # Check for high blunder rate
    total_bad = mistake_counts.get(MistakeCategory.MISTAKE, 0) + mistake_counts.get(MistakeCategory.BLUNDER, 0)
    if total_categorized > 0:
        bad_rate = total_bad / total_categorized * 100
        if bad_rate > 10:
            weaknesses.append(f"High mistake/blunder rate: {bad_rate:.1f}% of moves are mistakes or blunders")

    # Check for phase-specific problems
    for phase in ["opening", "middle", "yose"]:
        blunder_key = (phase, MistakeCategory.BLUNDER.name)
        blunder_count = phase_mistake_counts.get(blunder_key, 0)
        blunder_loss = phase_mistake_loss.get(blunder_key, 0.0)
        if blunder_count >= 3 and blunder_loss >= 10:
            weaknesses.append(
                f"{phase_labels.get(phase, phase)}: {blunder_count} blunders totaling {blunder_loss:.1f} points lost"
            )

    if weaknesses:
        for w in weaknesses:
            lines.append(f"- {w}")

        # Phase 66: Add evidence for weakness hypothesis
        # Collect evidence candidates from already-collected all_worst
        # all_worst has tuples: (game_name, move_num, gtp, loss, cat)
        evidence_candidates = []
        for game_name, move_num, gtp, loss, cat in all_worst:
            if cat in (MistakeCategory.MISTAKE, MistakeCategory.BLUNDER):
                ev = EvidenceMove(
                    game_name=game_name,
                    move_number=move_num,
                    player="",  # Not displayed, single-player context
                    gtp=gtp,
                    points_lost=loss,
                    mistake_category=cat,
                )
                evidence_candidates.append(ev)

        # Select and format evidence (max 2, deduplicated by game)
        evidence = _select_evidence_moves(evidence_candidates, max_count=2)
        evidence_str = _format_evidence_with_links(evidence, karte_path_map, summary_dir, lang)
        lines.append(f"  {evidence_str}")
    else:
        lines.append(f"- {get_phase_priority_text('no_weakness', lang)}")

    # =========================================================================
    # Section 8: Practice Priorities
    # =========================================================================
    lines.append(f"\n{get_section_header('practice_priorities', lang)}\n")
    lines.append(get_practice_intro_text(lang))

    priorities = []

    # Priority 1: Worst phase
    if phase_avg:
        worst_phase = max(phase_avg.items(), key=lambda x: x[1])
        if worst_phase[1] > 0.5:
            priorities.append(get_phase_priority_text(worst_phase[0], lang))

    # Priority 2: High blunder areas
    for phase in ["opening", "middle", "yose"]:
        blunder_key = (phase, MistakeCategory.BLUNDER.name)
        blunder_count = phase_mistake_counts.get(blunder_key, 0)
        if blunder_count >= 3:
            phase_name = get_phase_label_localized(phase, lang)
            priorities.append(get_phase_priority_text("blunder_review", lang, phase=phase_name, count=blunder_count))

    # Priority 3: Life and death if many blunders
    total_blunders = mistake_counts.get(MistakeCategory.BLUNDER, 0)
    if total_blunders >= 5:
        priorities.append(get_phase_priority_text("life_death", lang))

    if priorities:
        for i, p in enumerate(priorities[:5], 1):  # Max 5 priorities
            lines.append(f"{i}. {p}")
    else:
        lines.append(f"- {get_phase_priority_text('no_priority', lang)}")

    # Phase 54: Add tag-based practice hints
    tag_hints = build_tag_based_hints(
        meaning_tags_counts,
        reason_tags_counts,
        lang=lang,
        min_count=3,
        max_hints=4,
    )
    if tag_hints:
        lines.append("")
        lines.append(get_notes_header(lang))
        lines.append("")
        for hint in tag_hints:
            lines.append(f"- {hint}")

    # =========================================================================
    # Section 9: Games Included
    # =========================================================================
    lines.append("\n## Games Included\n")
    for i, (stats, role) in enumerate(player_games, 1):
        game_name = stats["game_name"]
        player_loss = stats["loss_by_player"].get(role, 0.0)
        player_moves = stats["moves_by_player"].get(role, 0)
        color = "Black" if role == "B" else "White"
        lines.append(f"{i}. {game_name} ({color}) — {player_moves} moves, {player_loss:.1f} pts lost")

    # Phase 54: Add color bias note if all games are same color
    color_bias = detect_color_bias(player_games)
    if color_bias:
        lines.append("")
        lines.append(get_color_bias_note(color_bias, lang))

    return "\n".join(lines)
