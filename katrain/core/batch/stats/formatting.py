"""Player summary formatting for batch statistics.

This module is a bridge to the unified JSON-based reporting logic.
"""

from __future__ import annotations

from typing import Any

from katrain.core.eval_metrics import DEFAULT_SKILL_PRESET
from katrain.core.reports.summary_report import build_summary_report


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
    Build summary for a single player across their games using the unified JSON reporting logic.

    Args:
        player_name: Display name of the player
        player_games: List of (game_stats, role) tuples where role is "B" or "W"
        skill_preset: Skill preset for strictness (unused in current JSON logic, preserved for API)
        analysis_settings: Optional dict with configured analysis settings (preserved for API)
        karte_path_map: Optional mapping from rel_path to absolute karte file path
        summary_dir: Directory where the summary file is being written
        lang: Language code for output ("jp", "en", "ja")

    Returns:
        Markdown summary string containing a JSON code block
    """
    # Extract GameSummaryData from player_games (list of (stats_dict, role))
    game_data_list = []
    for stats, _role in player_games:
        if "summary_data" in stats:
            game_data_list.append(stats["summary_data"])

    return build_summary_report(game_data_list, focus_player=player_name)
