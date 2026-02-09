"""Export Skill Radar summary from analyzed SGF files to Markdown format.

Usage:
    python -m katrain.tools.export_radar_summary <input_dir> [-o OUTPUT_FILE]

Example:
    python -m katrain.tools.export_radar_summary "C:\\Users\\mono_\\Desktop\\野狐ダウンロード" -o radar_summary.md

This tool:
1. Finds all analyzed SGF files (with KataGo analysis data)
2. Extracts Skill Radar data for each player
3. Outputs a simple Markdown table with:
   - Player name
   - Rank/Level
   - 5-axis scores (Opening, Fighting, Endgame, Stability, Awareness)
   - Overall Tier

Perfect for threshold tuning - no lengthy reports, just the essential data!
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

_logger = logging.getLogger("katrain.tools.export_radar_summary")


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the export tool."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def export_radar_summary(
    input_dir: str | Path,
    output_file: str | Path,
    verbose: bool = False,
) -> None:
    """Export Skill Radar summary from analyzed SGF files to Markdown.
    
    Args:
        input_dir: Directory containing analyzed SGF files
        output_file: Output Markdown file path
        verbose: Enable verbose logging
    """
    from katrain.core.batch import collect_sgf_files_recursive, parse_sgf_with_fallback, has_analysis
    from katrain.core.analysis.skill_radar import MIN_MOVES_FOR_RADAR, radar_from_dict
    from katrain.core.game import BaseGame
    
    setup_logging(verbose)
    
    input_path = Path(input_dir)
    if not input_path.exists():
        _logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)
    
    # Collect analyzed SGF files only
    all_files = collect_sgf_files_recursive(str(input_path))
    analyzed_files = [(abs_path, rel_path) for abs_path, rel_path in all_files if has_analysis(abs_path)]
    
    if not analyzed_files:
        _logger.error(f"No analyzed SGF files found in {input_dir}")
        _logger.info("Please run batch analysis first:")
        _logger.info(f"  python -m katrain.tools.batch_analyze_sgf --input-dir \"{input_dir}\"")
        sys.exit(1)
    
    _logger.info(f"Found {len(analyzed_files)} analyzed SGF files")
    
    # Collect radar data
    rows: list[dict[str, Any]] = []
    skipped = 0
    
    for idx, (sgf_path, rel_path) in enumerate(analyzed_files, 1):
        _logger.debug(f"[{idx}/{len(analyzed_files)}] Processing: {rel_path}")
        
        try:
            # Parse SGF
            root_node = parse_sgf_with_fallback(sgf_path)
            if not root_node:
                _logger.warning(f"  Skipped (parse failed): {rel_path}")
                skipped += 1
                continue
            
            # Check board size
            board_size_prop = root_node.get_property("SZ", "19")
            try:
                board_size = int(board_size_prop)
            except (ValueError, TypeError):
                board_size = 19
            
            if board_size != 19:
                _logger.debug(f"  Skipped (not 19x19): {rel_path}")
                skipped += 1
                continue
            
            # Create BaseGame and extract moves with analysis
            game = BaseGame(katrain=None, move_tree=root_node)
            
            # Get all moves from the game
            all_moves = []
            current_node = game.root
            while current_node:
                # Load analysis from SGF if present
                if hasattr(current_node, 'load_analysis'):
                    current_node.load_analysis()
                all_moves.append(current_node)
                current_node = current_node.children[0] if current_node.children else None
            
            # Check if we have enough analyzed moves
            analyzed_moves = [m for m in all_moves if m.analysis_exists]
            if len(analyzed_moves) < MIN_MOVES_FOR_RADAR:
                _logger.debug(f"  Skipped (insufficient analyzed moves: {len(analyzed_moves)}): {rel_path}")
                skipped += 1
                continue
            
            # Get player names
            player_black = root_node.get_property("PB", "Black")
            player_white = root_node.get_property("PW", "White")
            
            # Process each player
            for player_name, color in [(player_black, "B"), (player_white, "W")]:
                # Filter moves for this player
                player_moves = [m for m in all_moves if m.player == color and m.analysis_exists]
                
                if len(player_moves) < MIN_MOVES_FOR_RADAR:
                    _logger.debug(f"  Skipped ({color}): insufficient moves ({len(player_moves)})")
                    continue
                
                try:
                    # Compute radar directly from moves
                    radar = compute_radar_from_moves(player_moves, player=color)
                    
                    # Add to results
                    rows.append({
                        "game": Path(rel_path).stem,  # Filename without extension
                        "player": player_name,
                        "color": color,
                        "opening": radar.opening,
                        "fighting": radar.fighting,
                        "endgame": radar.endgame,
                        "stability": radar.stability,
                        "awareness": radar.awareness,
                        "overall_tier": radar.overall_tier.value,
                    })
                    _logger.debug(f"  Extracted ({color}): {player_name} - {radar.overall_tier.value}")
                    
                except Exception as e:
                    _logger.warning(f"  Radar failed ({color}): {rel_path} - {e}")
                    continue
                
        except Exception as e:
            _logger.error(f"  Error processing {rel_path}: {e}")
            skipped += 1
            continue
    
    # Write Markdown
    if not rows:
        _logger.error("No radar data extracted. Markdown not created.")
        sys.exit(1)
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with output_path.open("w", encoding="utf-8") as f:
        # Title
        f.write("# Skill Radar Summary (閾値調整用データ)\n\n")
        f.write(f"Total players: {len(rows)}\n\n")
        
        # Table header
        f.write("| Game | Player | Color | Opening | Fighting | Endgame | Stability | Awareness | Overall |\n")
        f.write("|------|--------|-------|---------|----------|---------|-----------|-----------|----------|\n")
        
        # Table rows
        for row in rows:
            f.write(f"| {row['game']} | {row['player']} | {row['color']} | "
                   f"{row['opening']:.1f} | {row['fighting']:.1f} | {row['endgame']:.1f} | "
                   f"{row['stability']:.1f} | {row['awareness']:.1f} | {row['overall_tier']} |\n")
        
        # Summary statistics
        f.write("\n## 統計\n\n")
        
        # Average by axis
        avg_opening = sum(r['opening'] for r in rows) / len(rows)
        avg_fighting = sum(r['fighting'] for r in rows) / len(rows)
        avg_endgame = sum(r['endgame'] for r in rows) / len(rows)
        avg_stability = sum(r['stability'] for r in rows) / len(rows)
        avg_awareness = sum(r['awareness'] for r in rows) / len(rows)
        
        f.write("### 平均スコア\n\n")
        f.write(f"- Opening: {avg_opening:.2f}\n")
        f.write(f"- Fighting: {avg_fighting:.2f}\n")
        f.write(f"- Endgame: {avg_endgame:.2f}\n")
        f.write(f"- Stability: {avg_stability:.2f}\n")
        f.write(f"- Awareness: {avg_awareness:.2f}\n")
        
        # Tier distribution
        from collections import Counter
        tier_counts = Counter(r['overall_tier'] for r in rows)
        
        f.write("\n### Overall Tier分布\n\n")
        for tier, count in sorted(tier_counts.items()):
            f.write(f"- {tier}: {count}人\n")
    
    _logger.info(f"✓ Exported {len(rows)} players to {output_file}")
    _logger.info(f"  Processed: {len(rows)} | Skipped: {skipped}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export Skill Radar summary from analyzed SGF files to Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input_dir",
        help="Directory containing analyzed SGF files",
    )
    parser.add_argument(
        "-o", "--output",
        default="radar_summary.md",
        help="Output Markdown file path (default: radar_summary.md)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    export_radar_summary(
        input_dir=args.input_dir,
        output_file=args.output,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
