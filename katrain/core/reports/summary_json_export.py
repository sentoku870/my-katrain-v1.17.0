"""JSON export for summary report (multi-game).

Contains:
- build_summary_json(): Build JSON-serializable summary structure for LLM consumption.
"""

from __future__ import annotations

from typing import Any
import time
import hashlib

from katrain.core import eval_metrics
from katrain.core.reports.summary_logic import SummaryAnalyzer
from katrain.core.eval_metrics import (
    GameSummaryData,
    MistakeCategory,
    PositionDifficulty,
)
from katrain.core.reports.definitions import (
    REPORT_SCHEMA_VERSION,
    REPORT_THRESHOLDS,
    DIFFICULTY_LEVELS,
    MISTAKE_TYPES,
    PHASES,
    PHASE_ALIASES,
    PRIMARY_TAGS,
    REASON_CODES,
    REASON_CODE_ALIASES,
    IMPORTANCE_DEF,
)
from katrain.core.reports.schema import (
    SummaryReport,
    Definitions,
    GameMeta,
    SummaryPlayerStats,
    MistakeItem,
    MetaData
)
from katrain.core.reports.extractors import MetaExtractor, MoveExtractor


def build_summary_json(
    game_data_list: list[GameSummaryData],
    focus_player: str | None = None
) -> SummaryReport:
    """Build a JSON-serializable summary structure for LLM consumption.
    
    Adheres to "Pure Data" requirements:
    - No instructional text
    - Explicit units
    - Raw numeric values
    - Full IDs
    """
    
    # Initialize Logic Analyzer
    analyzer = SummaryAnalyzer(game_data_list, focus_player)
    player_stats = analyzer.get_all_player_stats()

    # Meta Section
    all_players = set()
    dates = []
    presets = set()
    
    # Games Metadata List
    games_meta: list[GameMeta] = []
    
    for gd in game_data_list:
        all_players.add(gd.player_black)
        all_players.add(gd.player_white)
        if gd.date:
            dates.append(gd.date)
        if gd.skill_preset:
            presets.add(gd.skill_preset)
            
        games_meta.append(MetaExtractor.extract_game_meta(gd))
            
    # Definitions
    definitions: Definitions = {
        "thresholds": REPORT_THRESHOLDS,
        "mistake_types": MISTAKE_TYPES,
        "difficulty_levels": DIFFICULTY_LEVELS,
        "phases": PHASES,
        "phase_aliases": PHASE_ALIASES,
        "reason_code_aliases": REASON_CODE_ALIASES,
        "primary_tags": PRIMARY_TAGS,
        "reason_codes": REASON_CODES,
        "importance": IMPORTANCE_DEF,
    }

    # Meta - Add run_id
    ts = int(time.time())
    game_ids_str = "".join(sorted([g.game_id or "" for g in game_data_list]))
    run_hash = hashlib.md5(f"{ts}{game_ids_str}".encode()).hexdigest()[:8]
    run_id = f"summary_run_{ts}_{run_hash}"

    # Resolve skill_preset for meta
    if len(presets) == 1:
        skill_preset_meta = list(presets)[0]
    elif len(presets) > 1:
        skill_preset_meta = "mixed"
    else:
        skill_preset_meta = "unknown"

    meta: MetaData = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "games_analyzed": len(game_data_list),
        "date_range": [min(dates), max(dates)] if dates else None,
        "loss_unit": "territory_points",
        "skill_preset": skill_preset_meta,
        "definitions": definitions,
        "game_id": None # Not applicable for summary
    }

    players_data: dict[str, SummaryPlayerStats] = {}

    for player_name, stats in player_stats.items():
        # Confidence
        confidence_level = eval_metrics.compute_confidence_level(stats.all_moves)
        confidence_val = confidence_level.name.lower() # high, medium, low

        # Overall Stats
        overall = {
            "total_games": stats.total_games,
            "total_moves": stats.total_moves,
            "total_loss": round(stats.total_points_lost, 1),
            "avg_loss": round(stats.avg_points_lost_per_move, 3),
            "confidence": confidence_val,
        }

        # Mistake Distribution
        mistake_dist = {}
        for cat in MistakeCategory:
            key = cat.value.lower()
            count = stats.mistake_counts.get(cat, 0)
            avg_loss = stats.get_mistake_avg_loss(cat)
            mistake_dist[key] = {
                "count": count,
                "pct": round(stats.get_mistake_percentage(cat), 1),
                "denominator": stats.total_moves, # Explicit denominator
                "avg_loss": round(avg_loss, 2),
            }

        # Freedom (Difficulty) Distribution
        difficulty_dist = {}
        for diff in PositionDifficulty:
            key = diff.value.lower()
            count = stats.freedom_counts.get(diff, 0)
            difficulty_dist[key] = {
                "count": count,
                "pct": round(stats.get_freedom_percentage(diff), 1),
                "denominator": stats.total_moves, # Explicit denominator
            }

        # Phase Stats
        phase_stats = {}
        # Use canonical names and map yose -> endgame
        phases_to_report = ["opening", "middle", "endgame", "unknown"]
        for phase in phases_to_report:
            internal_phase = "yose" if phase == "endgame" else phase
            count = stats.phase_moves.get(internal_phase, 0)
            loss = stats.phase_loss.get(internal_phase, 0.0)
            avg_loss = stats.get_phase_avg_loss(internal_phase)
            phase_stats[phase] = {
                "moves": count,
                "total_loss": round(loss, 1),
                "avg_loss": round(avg_loss, 2),
            }

        # Reason Tags Statistics (v6: Normalized Aggregation)
        reason_tags_dist = {}
        if stats.tag_occurrences_total > 0:
            # Map raw tags to normalized tags
            normalized_counts = {}
            for tag, count in stats.reason_tags_counts.items():
                norm_tag = REASON_CODE_ALIASES.get(tag, tag)
                normalized_counts[norm_tag] = normalized_counts.get(norm_tag, 0) + count

            # Sort by count desc
            sorted_tags = sorted(normalized_counts.items(), key=lambda x: -x[1])
            for tag, count in sorted_tags:
                reason_tags_dist[tag] = {
                    "count": count,
                    "pct": round(100.0 * count / stats.tag_occurrences_total, 1),
                    "denominator_type": "tag_occurrences",
                    "total_tag_occurrences": stats.tag_occurrences_total,
                }
            
            reason_tags_stats_block = {
                "status": "computed" if reason_tags_dist else "computed_empty",
                "data": reason_tags_dist,
                "stats": {
                    "tagged_moves_count": stats.tagged_moves_count,
                    "tag_occurrences_total": stats.tag_occurrences_total
                }
            }
        else:
             reason_tags_stats_block = {
                "status": "computed_empty",
                "data": {},
                "stats": {
                    "tagged_moves_count": 0,
                    "tag_occurrences_total": 0
                }
            }

        # Mistake Sequences / Patterns (v4 renaming)
        sequences, filtered_moves = analyzer.detect_mistake_sequences(player_name)
        
        mistake_sequences = []
        for seq in sequences:
            mistake_sequences.append({
                "game_name": seq["game"], # Uses full name from SummaryAnalyzer
                "move_range": [seq["start"], seq["end"]],
                "count": seq["count"],
                "total_loss": round(seq["total_loss"], 1),
                "avg_loss": round(seq["total_loss"] / seq["count"], 1),
            })
        
        # Worst Moves (Top candidates)
        # Using filtered_moves which excludes sequences
        top_mistakes: list[MistakeItem] = []
        
        # Logic from _format_top_worst_moves
        max_count = eval_metrics.get_important_moves_limit(confidence_level)
        from katrain.core.reports.constants import SUMMARY_DEFAULT_MAX_WORST_MOVES
        display_limit = min(SUMMARY_DEFAULT_MAX_WORST_MOVES, max_count)
        
        sorted_moves = sorted(
            filtered_moves,
            key=lambda x: x[1].points_lost or x[1].score_loss or 0, 
            reverse=True
        )
        for game_name, move in sorted_moves[:display_limit]:
            # Find game_id
            game_ref = next((g for g in game_data_list if g.game_name == game_name), None)
            game_id = game_ref.game_id if game_ref else None
            
            # Use Extractor
            board_size = game_ref.board_size[0] if game_ref else 19
            item = MoveExtractor.extract(move, game_id, game_name, board_size=board_size)
            top_mistakes.append(item)

        seq_status = "computed" if mistake_sequences else "computed_empty"

        players_data[player_name] = {
            "overall": overall,
            "mistakes": mistake_dist,
            "difficulty": difficulty_dist,
            "phases": phase_stats,
            "reason_tags": reason_tags_stats_block,
            "mistake_sequences": {
                "status": seq_status,
                "data": mistake_sequences
            },
            "top_mistakes": top_mistakes,
        }
        
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "meta": meta,
        "games": games_meta,
        "players": players_data,
    }
