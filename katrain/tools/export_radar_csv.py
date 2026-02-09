"""Export Skill Radar data from multiple SGF files to CSV format.

Usage:
    python -m katrain.tools.export_radar_csv <input_dir> [-o OUTPUT_FILE] [--player PLAYER_NAME]

Example:
    python -m katrain.tools.export_radar_csv ./my_games -o radar_data.csv
    python -m katrain.tools.export_radar_csv ./my_games --player "MyName" -o my_radar.csv

This tool:
1. Recursively finds all SGF files in the input directory
2. Extracts Skill Radar data for each game (19x19 board only)
3. Outputs results in CSV format for easy analysis

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
) -> None:
    """Export Skill Radar data from SGF files to CSV.
    
    Args:
        input_dir: Directory containing SGF files
        output_file: Output CSV file path
        player_filter: Optional player name to filter (case-insensitive partial match)
        verbose: Enable verbose logging
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
            
            try:
                game = BaseGame(katrain=None, move_tree=root_node)
            except Exception as e:
                _logger.warning(f"  Skipped (game creation failed): {rel_path} - {e}")
                skipped += 1
                continue
            
            # Build snapshot
            try:
                snapshot = game.build_eval_snapshot()
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
            date = root_node.get_property("DT", "")
            handicap = int(root_node.get_property("HA", "0") or "0")
            
            # Process each player
            for player_name, color in [(player_black, "B"), (player_white, "W")]:
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
    
    # Write CSV
    if not rows:
        _logger.error("No radar data extracted. CSV not created.")
        sys.exit(1)
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Define column order
    fieldnames = [
        "game_name", "player", "color",
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
    
    _logger.info(f"✓ Exported {processed} radar entries to {output_file}")
    _logger.info(f"  Processed: {processed} | Skipped: {skipped}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export Skill Radar data from SGF files to CSV format",
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
        help="Output CSV file path (default: radar_data.csv)",
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
    
    args = parser.parse_args()
    
    export_radar_csv(
        input_dir=args.input_dir,
        output_file=args.output,
        player_filter=args.player,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
