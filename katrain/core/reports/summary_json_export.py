"""JSON export for summary report (multi-game).

Contains:
- build_summary_json(): Build JSON-serializable summary structure for LLM consumption.
"""

from __future__ import annotations

from typing import Any

from katrain.core import eval_metrics
from katrain.core.reports.summary_logic import SummaryAnalyzer
from katrain.core.eval_metrics import (
    GameSummaryData,
    MistakeCategory,
    PositionDifficulty,
)
from katrain.core.reports.constants import (
    BAD_MOVE_LOSS_THRESHOLD,
    URGENT_MISS_MIN_CONSECUTIVE,
    URGENT_MISS_THRESHOLD_LOSS,
)


def build_summary_json(
    game_data_list: list[GameSummaryData],
    focus_player: str | None = None
) -> dict[str, Any]:
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
    all_players = set()
    dates = []
    
    # Stage 2: Games Metadata List
    games_meta = []
    
    for gd in game_data_list:
        all_players.add(gd.player_black)
        all_players.add(gd.player_white)
        if gd.date:
            dates.append(gd.date)
            
        # Calculate total loss for the focus player (or both if None)
        # Note: SummaryData doesn't strictly store per-player total loss in attributes
        # We'd need to iterate moves if not available.
        # But wait, SummaryStats aggregates it.
        # For the game list, let's just output basic info available in GameSummaryData
        games_meta.append({
            "name": gd.game_name,
            "date": gd.date,
            "game_id": gd.game_id,  # Issue 2 fix: Traceability
            "moves": len(gd.snapshot.moves) if gd.snapshot else 0,
            # "result": gd.result ... GameSummaryData doesn't have result field currently?
        })
            
    # Derive thresholds from constants (assuming consistent across games for summary)
    # Note: Summary report aggregates games which might have different thresholds.
    # We report the constants used for detection in this summary logic.
    definitions = {
        "thresholds": {
            "urgent_miss": {
                "loss": URGENT_MISS_THRESHOLD_LOSS,
                "min_consecutive": URGENT_MISS_MIN_CONSECUTIVE,
            },
            "bad_move_loss": BAD_MOVE_LOSS_THRESHOLD,
            "phase": {
                "opening_max": 50,
                "middle_max": 200,
                "endgame_min": 201,
            }
        },
        "mistake_types": [cat.value.lower() for cat in MistakeCategory],
        "difficulty_levels": [d.value.lower() for d in PositionDifficulty],
        "phases": ["opening", "middle", "endgame"],
        "phase_aliases": {"yose": "endgame"},
        "reason_code_aliases": {
            "low_liberties": "liberties",
            "need_connect": "connection",
            "heavy_loss": "heavy",
            "reading_failure": "reading",
            "shape_mistake": "shape",
            "endgame_slip": "endgame_hint",
            "cut_risk": "cut_risk",
            "thin": "thin",
            "chase_mode": "chase_mode"
        },
        "reason_codes": [
            "shape", "atari", "clump", "heavy", "overconcentrated", "liberties",
            "endgame_hint", "connection", "urgent", "tenuki", "cut_risk",
            "thin", "chase_mode", "reading"
        ],
        "importance": {
            "scale": "0.0 to 10.0+",
            "description": "Move interestingness score derived from loss and semantic tags",
            "thresholds": {
              "interesting": 1.0,
              "important": 3.0,
              "critical": 6.0
            }
        },
    }

    # Meta - Add run_id
    import time
    run_id = f"summary_run_{int(time.time())}"

    meta = {
        "games_analyzed": len(game_data_list),
        "run_id": run_id,
        "player_filter": focus_player,
        "all_players": sorted(list(all_players)),
        "date_range": [min(dates), max(dates)] if dates else None,
        "loss_unit": "territory_points",
        "definitions": definitions,
    }

    players_data = {}

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
            aliases = definitions["reason_code_aliases"]
            for tag, count in stats.reason_tags_counts.items():
                norm_tag = aliases.get(tag, tag)
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

        # Removed 'priorities' (coaching text strings) to strictly follow Pure Data
        
        # Worst Moves (Top candidates)
        # Using filtered_moves which excludes sequences
        top_mistakes = []
        
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
            loss = move.points_lost if move.points_lost is not None else move.score_loss
            loss_clamped = max(0, loss) if loss else 0
            
            mistake_type = move.mistake_category.value.lower() if move.mistake_category else "unknown"
            
            # 理由コードの正規化 (Stage 2)
            raw_tags = list(move.reason_tags) if move.reason_tags else []
            aliases = definitions["reason_code_aliases"]
            reason_codes = sorted(list(set(aliases.get(t, t) for t in raw_tags)))
            
            # Primary Tag (Stage 2)
            # Logic similar to Karte: find first matching tag in priority list
            # We don't have primary_tags in definitions here yet, let's add it in Stage 3 or verify if needed.
            # Actually, let's just use the first normalized tag or None for now, as we didn't add primary_tags list to definitions in Summary yet.
            # Wait, implementation plan said "Expand top_mistakes details".
            # Let's check definitions... we added reason_codes list but not primary_tags list in Summary.
            # However, Karte uses a priority list.
            # To be safe and pure, let's just output the list `reason_codes` and `primary_tag` if available.
            # Since we don't have the priority list readily available in this scope without duplication,
            # let's skip primary_tag calculation for now or hardcode a simple one?
            # Better: Output `reason_codes` fully.
            
            # Issue 3 fix: Normalize player names
            player_norm = "black" if move.player == "B" else "white" if move.player == "W" else "unknown"

            # Issue 2 fix: Canonical phase
            phase_norm = move.tag
            if phase_norm == "yose":
                phase_norm = "endgame"

            top_mistakes.append({
                "game_name": game_name,
                "move_number": move.move_number,
                "player": player_norm,  # Normalized
                "coords": move.gtp or "-",
                "phase": phase_norm,  # Normalized
                "difficulty": move.position_difficulty.value.lower() if move.position_difficulty else "normal",
                "loss_clamped": round(loss_clamped, 2),
                "loss_raw": round(loss, 2) if loss is not None else None,
                "importance": round(move.importance_score or 0, 2),
                "mistake_type": mistake_type,
                "reason_codes": reason_codes,
            })

        players_data[player_name] = {
            "overall": overall,
            "mistakes": mistake_dist,
            "difficulty": difficulty_dist,
            "phases": phase_stats,
            "reason_tags": {
                "status": "computed" if reason_tags_dist else "empty_or_not_computed",
                "data": reason_tags_dist
            },
            "mistake_sequences": {
                "status": "computed" if mistake_sequences else "empty_or_not_computed",
                "data": mistake_sequences
            },
            "top_mistakes": top_mistakes,
            # Removed interpretive fields for 100% Pure Data compliance
            "derived_flags": [],
        }
        
    return {
        "schema_version": "2.1",
        "meta": meta,
        "games": games_meta,
        "players": players_data,
    }
