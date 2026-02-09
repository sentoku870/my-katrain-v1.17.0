"""Export Skill Radar data from multiple SGF files to CSV or text format.

Usage:
    python -m katrain.tools.export_radar_csv <input_dir> [-o OUTPUT_FILE] [--player PLAYER_NAME] [-f FORMAT]

Examples:
    # CSV format (default)
    python -m katrain.tools.export_radar_csv ./my_games -o radar_data.csv
    
    # Text format (readable)
    python -m katrain.tools.export_radar_csv ./my_games -o radar_data.txt -f text
    
    # Filter by player name
    python -m katrain.tools.export_radar_csv ./my_games --player "やまぽうし" -o my_radar.txt -f text

This tool:
1. Recursively finds all SGF files in the input directory
2. Extracts Skill Radar data for each game (19x19 board only)
3. Outputs results in CSV or text format for easy analysis

CSV columns:
- game_name: Relative path to SGF file
- player: Player name
- color: "B" (Black) or "W" (White)
- opening_score, opening_tier: Opening axis evaluation
- fighting_score, fighting_tier: Fighting axis evaluation
- endgame_score, endgame_tier: Endgame axis evaluation
- stability_score, stability_tier: Stability axis evaluation
- awareness_score, awareness_tier: Awareness axis evaluation
- overall_tier: Overall tier classification
- opening_moves, fighting_moves, endgame_moves, stability_moves, awareness_moves: Valid move counts
- total_moves: Total moves in game
- date: Game date (from SGF)
- handicap: Handicap stones

Text format:
- Human-readable format with Japanese tier names
- Includes overall tier (総合棋力) with rank range
- Shows all 5 axes with scores, tiers, and valid move counts
- Perfect for reviewing multiple games at a glance
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Any

_logger = logging.getLogger("katrain.tools.export_radar_csv")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the export tool."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def export_radar_csv(
    input_dir: str | Path,
    output_file: str | Path,
    player_filter: str | None = None,
    verbose: bool = False,
    format_type: str = "csv",
) -> None:
    """Export Skill Radar data from SGF files to CSV or text format.
    
    Args:
        input_dir: Directory containing SGF files
        output_file: Output file path
        player_filter: Optional player name to filter (case-insensitive partial match)
        verbose: Enable verbose logging
        format_type: Output format - "csv" or "text" (default: "csv")
    """
    from katrain.core.batch import collect_sgf_files_recursive, parse_sgf_with_fallback
    from katrain.core.analysis.skill_radar import MIN_MOVES_FOR_RADAR, compute_radar_from_moves
    
    setup_logging(verbose)
    
    input_path = Path(input_dir)
    if not input_path.exists():
        _logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)
    
    # Collect SGF files
    sgf_files = collect_sgf_files_recursive(str(input_path))
    if not sgf_files:
        _logger.error(f"No SGF files found in {input_dir}")
        sys.exit(1)
    
    _logger.info(f"Found {len(sgf_files)} SGF files")
    
    # CSV output structure
    rows: list[dict[str, Any]] = []
    skipped = 0
    processed = 0
    
    for idx, (sgf_path, rel_path) in enumerate(sgf_files, 1):
        _logger.debug(f"[{idx}/{len(sgf_files)}] Processing: {rel_path}")
        
        try:
            # Parse SGF
            root_node = parse_sgf_with_fallback(sgf_path)
            if not root_node:
                _logger.warning(f"  Skipped (parse failed): {rel_path}")
                skipped += 1
                continue
            
            # Check board size (19x19 only)
            board_size_prop = root_node.get_property("SZ", "19")
            try:
                board_size = int(board_size_prop)
            except (ValueError, TypeError):
                board_size = 19
            
            if board_size != 19:
                _logger.debug(f"  Skipped (not 19x19): {rel_path}")
                skipped += 1
                continue
            
            # Use BaseGame instead of Game (doesn't require katrain/engine)
            from katrain.core.game import BaseGame
            from katrain.core.analysis.logic import snapshot_from_game
            
            try:
                game = BaseGame(katrain=None, move_tree=root_node)
            except Exception as e:
                _logger.warning(f"  Skipped (game creation failed): {rel_path} - {e}")
                skipped += 1
                continue
            
            # Build snapshot using the direct function instead of Game method
            try:
                snapshot = snapshot_from_game(game)
            except Exception as e:
                _logger.warning(f"  Skipped (snapshot failed): {rel_path} - {e}")
                skipped += 1
                continue
            
            if not snapshot or not snapshot.moves:
                _logger.warning(f"  Skipped (no moves): {rel_path}")
                skipped += 1
                continue
            
            # Extract metadata
            player_black = root_node.get_property("PB", "Black")
            player_white = root_node.get_property("PW", "White")
            rank_black = root_node.get_property("BR", "")
            rank_white = root_node.get_property("WR", "")
            date = root_node.get_property("DT", "")
            handicap = int(root_node.get_property("HA", "0") or "0")
            
            # Process each player
            for player_name, color, rank in [(player_black, "B", rank_black), (player_white, "W", rank_white)]:
                # Apply player filter
                if player_filter and player_filter.lower() not in player_name.lower():
                    continue
                
                # Get moves for this player
                player_moves = [m for m in snapshot.moves if m.player == color]
                
                if len(player_moves) < MIN_MOVES_FOR_RADAR:
                    _logger.debug(f"  Skipped ({color}): {rel_path} - insufficient moves ({len(player_moves)})")
                    continue
                
                # Compute radar
                try:
                    radar = compute_radar_from_moves(player_moves, player=color)
                except Exception as e:
                    _logger.warning(f"  Radar failed ({color}): {rel_path} - {e}")
                    continue
                
                # Build row
                row = {
                    "game_name": rel_path,
                    "player": player_name,
                    "rank": rank,
                    "color": color,
                    "opening_score": radar.opening,
                    "opening_tier": radar.opening_tier.value,
                    "fighting_score": radar.fighting,
                    "fighting_tier": radar.fighting_tier.value,
                    "endgame_score": radar.endgame,
                    "endgame_tier": radar.endgame_tier.value,
                    "stability_score": radar.stability,
                    "stability_tier": radar.stability_tier.value,
                    "awareness_score": radar.awareness,
                    "awareness_tier": radar.awareness_tier.value,
                    "overall_tier": radar.overall_tier.value,
                    "opening_moves": radar.valid_move_counts.get("opening", 0),
                    "fighting_moves": radar.valid_move_counts.get("fighting", 0),
                    "endgame_moves": radar.valid_move_counts.get("endgame", 0),
                    "stability_moves": radar.valid_move_counts.get("stability", 0),
                    "awareness_moves": radar.valid_move_counts.get("awareness", 0),
                    "total_moves": len(player_moves),
                    "date": date,
                    "handicap": handicap if color == "B" else 0,
                }
                rows.append(row)
                processed += 1
                _logger.debug(f"  Exported ({color}): {player_name} - Overall {radar.overall_tier.value}")
        
        except Exception as e:
            _logger.error(f"  Error processing {rel_path}: {e}")
            skipped += 1
            continue
    
    # Write output
    if not rows:
        _logger.error("No radar data extracted. Output not created.")
        sys.exit(1)
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format_type == "text":
        # Text format output
        _write_text_format(output_path, rows)
    else:
        # CSV format output (default)
        # Define column order
        fieldnames = [
            "game_name", "player", "rank", "color",
            "opening_score", "opening_tier",
            "fighting_score", "fighting_tier",
            "endgame_score", "endgame_tier",
            "stability_score", "stability_tier",
            "awareness_score", "awareness_tier",
            "overall_tier",
            "opening_moves", "fighting_moves", "endgame_moves", "stability_moves", "awareness_moves",
            "total_moves", "date", "handicap",
        ]
        
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    
    format_name = "text" if format_type == "text" else "CSV"
    _logger.info(f"✓ Exported {processed} radar entries to {output_file} ({format_name} format)")
    _logger.info(f"  Processed: {processed} | Skipped: {skipped}")


def _write_text_format(output_path: Path, rows: list[dict[str, Any]]) -> None:
    """Write radar data in AI-friendly structured markdown format.
    
    Args:
        output_path: Output file path
        rows: List of radar data dictionaries
    """
    # Import threshold constants
    from katrain.core.analysis.skill_radar import (
        APL_TIER_THRESHOLDS,
        OPENING_APL_THRESHOLDS,
        FIGHTING_APL_THRESHOLDS,
        ENDGAME_APL_THRESHOLDS,
        STABILITY_APL_THRESHOLDS,
        BLUNDER_RATE_TIER_THRESHOLDS,
        MATCH_RATE_TIER_THRESHOLDS,
        SkillTier,
    )
    
    tier_names = {
        "tier_1": "Tier 1 (20k-15k)",
        "tier_2": "Tier 2 (15k-12k)",
        "tier_3": "Tier 3 (12k-8k)",
        "tier_4": "Tier 4 (8k-5k)",
        "tier_5": "Tier 5 (5k-3k)",
        "tier_6": "Tier 6 (3k-初段)",
        "tier_7": "Tier 7 (初段-三段)",
        "tier_8": "Tier 8 (三段-五段)",
        "tier_9": "Tier 9 (五段-七段)",
        "tier_10": "Tier 10 (プロ級)",
        "unknown": "不明",
    }
    
    with output_path.open("w", encoding="utf-8") as f:
        # Header
        f.write("# スキルレーダー分析結果\n\n")
        f.write("> AI解析用の構造化データ\n\n")
        
        # Tier definitions
        f.write("## 評価基準\n\n")
        
        # Overall tier calculation
        f.write("### 総合棋力計算方法\n\n")
        f.write("- 各軸のスコア（1.0〜10.0）を平均し、四捨五入で整数化\n")
        f.write("- 整数スコアをTierにマッピング（例: 平均6.2 → 6 → Tier 6）\n\n")
        
        # Missing value handling
        f.write("### 欠損値処理\n\n")
        f.write("- 有効手数が5手未満の軸は評価対象外（N/A表示）\n")
        f.write("- N/A軸は総合棋力計算から除外\n\n")
        
        # Valid move count definitions
        f.write("### 有効手数の定義\n\n")
        f.write("- **序盤力**: 手数1〜50の手（序盤定石・布石局面）\n")
        f.write("- **戦闘力**: 難しい局面（position_difficulty=HARD）での手\n")
        f.write("- **終盤力**: 手数150以降、またはヨセタグ付き局面の手\n")
        f.write("- **安定性**: 全手数（全局面、ガベージタイムも含む）\n")
        f.write("- **感性**: AI最善手一致率を評価（mistake_category=GOOD）\n\n")
        
        # Tier definitions table
        f.write("### Tier定義\n\n")
        f.write("| Tier | 棋力範囲 | スコア |\n")
        f.write("|------|----------|--------|\n")
        f.write("| Tier 1  | 20k-15k  | 1.0    |\n")
        f.write("| Tier 2  | 15k-12k  | 2.0    |\n")
        f.write("| Tier 3  | 12k-8k   | 3.0    |\n")
        f.write("| Tier 4  | 8k-5k    | 4.0    |\n")
        f.write("| Tier 5  | 5k-3k    | 5.0    |\n")
        f.write("| Tier 6  | 3k-初段  | 6.0    |\n")
        f.write("| Tier 7  | 初段-三段 | 7.0    |\n")
        f.write("| Tier 8  | 三段-五段 | 8.0    |\n")
        f.write("| Tier 9  | 五段-七段 | 9.0    |\n")
        f.write("| Tier 10 | プロ級   | 10.0   |\n")
        f.write("\n")
        
        # Threshold settings
        f.write("### 閾値設定\n\n")
        
        # Opening thresholds
        f.write("#### 序盤力 (Opening - APL)\n\n")
        f.write("| APL範囲 | Tier | スコア |\n")
        f.write("|---------|------|--------|\n")
        prev_threshold = 0.0
        for threshold, tier, score in OPENING_APL_THRESHOLDS:
            if threshold == float("inf"):
                f.write(f"| {prev_threshold:.2f}+ | {tier.value} | {score:.1f} |\n")
            else:
                f.write(f"| {prev_threshold:.2f}-{threshold:.2f} | {tier.value} | {score:.1f} |\n")
                prev_threshold = threshold
        f.write("\n")
        
        # Fighting thresholds
        f.write("#### 戦闘力 (Fighting - APL)\n\n")
        f.write("| APL範囲 | Tier | スコア |\n")
        f.write("|---------|------|--------|\n")
        prev_threshold = 0.0
        for threshold, tier, score in FIGHTING_APL_THRESHOLDS:
            if threshold == float("inf"):
                f.write(f"| {prev_threshold:.2f}+ | {tier.value} | {score:.1f} |\n")
            else:
                f.write(f"| {prev_threshold:.2f}-{threshold:.2f} | {tier.value} | {score:.1f} |\n")
                prev_threshold = threshold
        f.write("\n")
        
        # Endgame thresholds
        f.write("#### 終盤力 (Endgame - APL)\n\n")
        f.write("| APL範囲 | Tier | スコア |\n")
        f.write("|---------|------|--------|\n")
        prev_threshold = 0.0
        for threshold, tier, score in ENDGAME_APL_THRESHOLDS:
            if threshold == float("inf"):
                f.write(f"| {prev_threshold:.2f}+ | {tier.value} | {score:.1f} |\n")
            else:
                f.write(f"| {prev_threshold:.2f}-{threshold:.2f} | {tier.value} | {score:.1f} |\n")
                prev_threshold = threshold
        f.write("\n")
        
        # Stability thresholds
        f.write("#### 安定性 (Stability - APL)\n\n")
        f.write("| APL範囲 | Tier | スコア |\n")
        f.write("|---------|------|--------|\n")
        prev_threshold = 0.0
        for threshold, tier, score in STABILITY_APL_THRESHOLDS:
            if threshold == float("inf"):
                f.write(f"| {prev_threshold:.2f}+ | {tier.value} | {score:.1f} |\n")
            else:
                f.write(f"| {prev_threshold:.2f}-{threshold:.2f} | {tier.value} | {score:.1f} |\n")
                prev_threshold = threshold
        f.write("\n")
        
        # Awareness (Match Rate) thresholds
        f.write("#### 感性 (Awareness - Match Rate)\n\n")
        f.write("| Match Rate範囲 | Tier | スコア |\n")
        f.write("|----------------|------|--------|\n")
        prev_threshold = 0.0
        for threshold, tier, score in MATCH_RATE_TIER_THRESHOLDS:
            if threshold == float("inf"):
                f.write(f"| {prev_threshold:.2f}+ | {tier.value} | {score:.1f} |\n")
            else:
                f.write(f"| {prev_threshold:.2f}-{threshold:.2f} | {tier.value} | {score:.1f} |\n")
                prev_threshold = threshold
        f.write("\n")
        
        # Player data
        f.write("---\n\n")
        f.write("## 対局データ\n\n")
        
        for idx, row in enumerate(rows, 1):
            # Game header
            f.write(f"### 対局 {idx}: {row['game_name']}\n\n")
            
            # Player info
            player_display = row['player']
            if row.get('rank'):
                player_display = f"{row['player']} ({row['rank']})"
            f.write(f"**プレイヤー**: {player_display}  \n")
            f.write(f"**番**: {row['color']}番  \n")
            if row['date']:
                f.write(f"**日付**: {row['date']}  \n")
            if row['handicap'] > 0:
                f.write(f"**ハンデ**: {row['handicap']}子  \n")
            f.write(f"**総手数**: {row['total_moves']}手\n\n")
            
            # Skill evaluation table
            f.write("#### スキル評価\n\n")
            f.write("| 項目 | スコア | Tier | 棋力 | 有効手数 |\n")
            f.write("|------|--------|------|------|----------|\n")
            
            axes = [
                ("序盤力 (Opening)", "opening"),
                ("戦闘力 (Fighting)", "fighting"),
                ("終盤力 (Endgame)", "endgame"),
                ("安定性 (Stability)", "stability"),
                ("感性 (Awareness)", "awareness"),
            ]
            
            for jp_name, axis_key in axes:
                score = row[f"{axis_key}_score"]
                tier = row[f"{axis_key}_tier"]
                tier_name = tier_names.get(tier, tier)
                moves = row[f"{axis_key}_moves"]
                f.write(f"| {jp_name} | {score:.1f} | {tier} | {tier_name} | {moves} |\n")
            
            # Overall tier
            overall_tier_name = tier_names.get(row['overall_tier'], row['overall_tier'])
            f.write(f"\n**総合棋力**: {overall_tier_name}\n\n")
            f.write("---\n\n")
        
        # Summary
        f.write(f"**総計**: {len(rows)} 件の分析結果\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export Skill Radar data from SGF files to CSV or text format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input_dir",
        help="Directory containing SGF files (searches recursively)",
    )
    parser.add_argument(
        "-o", "--output",
        default="radar_data.csv",
        help="Output file path (default: radar_data.csv)",
    )
    parser.add_argument(
        "--player",
        help="Filter by player name (case-insensitive partial match)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["csv", "text"],
        default="csv",
        help="Output format: csv or text (default: csv)",
    )
    
    args = parser.parse_args()
    
    export_radar_csv(
        input_dir=args.input_dir,
        output_file=args.output,
        player_filter=args.player,
        verbose=args.verbose,
        format_type=args.format,
    )


if __name__ == "__main__":
    main()
