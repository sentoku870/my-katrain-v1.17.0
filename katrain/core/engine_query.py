"""Phase 68: Query building utilities for KataGo analysis.

This module provides standalone query building functions to avoid circular imports
between engine.py and engine_cmd/commands.py.
"""

import copy
from typing import TYPE_CHECKING, Any

from katrain.core.sgf_parser import Move

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode


def build_analysis_query(
    analysis_node: "GameNode",
    *,
    visits: int,
    ponder: bool,
    ownership: bool,
    rules: str | dict[str, Any],
    base_priority: int,
    priority: int,
    override_settings: dict[str, Any],
    wide_root_noise: float,
    max_time: float | None = None,
    time_limit: bool = True,
    next_move: Move | None = None,
    find_alternatives: bool = False,
    region_of_interest: list[int] | None = None,
    extra_settings: dict[str, Any] | None = None,
    include_policy: bool = True,
    report_every: float | None = None,
    ponder_key: str = "_kt_continuous",
) -> dict[str, Any]:
    """Build a KataGo analysis query dict.

    This is a pure function with no side effects. It does NOT set the query ID
    (that's done by the engine's write thread) or send the query.

    Args:
        analysis_node: The game node to analyze.
        visits: Maximum visits for this query.
        ponder: Whether this is a continuous pondering query.
        ownership: Whether to include ownership data.
        rules: KataGo rules string (e.g., "japanese", "chinese").
        base_priority: Engine's base priority.
        priority: Additional priority offset for this query.
        override_settings: Engine's override settings dict.
        wide_root_noise: Wide root noise setting.
        max_time: Maximum time limit (used if time_limit=True).
        time_limit: Whether to apply time limit.
        next_move: Optional hypothetical next move to analyze.
        find_alternatives: Whether to find alternative moves (avoid analyzed moves).
        region_of_interest: Optional [xmin, xmax, ymin, ymax] to restrict analysis.
        extra_settings: Additional settings to merge into overrideSettings.
        include_policy: Whether to include policy data.
        report_every: Interval for partial results (None = no partial results).
        ponder_key: Key name for ponder flag (default: "_kt_continuous").

    Returns:
        A dict suitable for sending to KataGo as JSON.

    Note:
        The returned dict does NOT include the "id" field. That is assigned
        by the engine's _write_stdin_thread() after dequeuing.
    """
    nodes = analysis_node.nodes_from_root
    moves = [m for node in nodes for m in node.moves]
    initial_stones = [m for node in nodes for m in node.placements]

    if next_move:
        moves.append(next_move)

    size_x, size_y = analysis_node.board_size

    # Build avoid list
    avoid = _build_avoid_list(
        analysis_node=analysis_node,
        find_alternatives=find_alternatives,
        region_of_interest=region_of_interest,
        size_x=size_x,
        size_y=size_y,
    )

    # Build settings
    settings = copy.copy(override_settings)
    settings["wideRootNoise"] = wide_root_noise
    if time_limit and max_time is not None:
        settings["maxTime"] = max_time

    # Build query
    query: dict[str, Any] = {
        "rules": rules,
        "priority": base_priority + priority,
        "analyzeTurns": [len(moves)],
        "maxVisits": visits,
        "komi": analysis_node.komi,
        "boardXSize": size_x,
        "boardYSize": size_y,
        "includeOwnership": ownership and not next_move,
        "includeMovesOwnership": ownership and not next_move,
        "includePolicy": include_policy,
        "initialStones": [[m.player, m.gtp()] for m in initial_stones],
        "initialPlayer": analysis_node.initial_player,
        "moves": [[m.player, m.gtp()] for m in moves],
        "overrideSettings": {**settings, **(extra_settings or {})},
        ponder_key: ponder,
    }

    if report_every is not None:
        query["reportDuringSearchEvery"] = report_every
    if avoid:
        query["avoidMoves"] = avoid

    return query


def _build_avoid_list(
    analysis_node: "GameNode",
    find_alternatives: bool,
    region_of_interest: list[int] | None,
    size_x: int,
    size_y: int,
) -> list[dict[str, Any]]:
    """Build the avoidMoves list for KataGo query.

    Args:
        analysis_node: The game node being analyzed.
        find_alternatives: If True, avoid moves already in analysis.
        region_of_interest: Optional [xmin, xmax, ymin, ymax] bounds.
        size_x: Board width.
        size_y: Board height.

    Returns:
        A list of avoid specifications for KataGo.
    """
    if find_alternatives:
        # Avoid moves that have already been analyzed
        return [
            {
                "moves": list(analysis_node.analysis["moves"].keys()),
                "player": analysis_node.next_player,
                "untilDepth": 1,
            }
        ]
    elif region_of_interest:
        # Only analyze within the region of interest
        xmin, xmax, ymin, ymax = region_of_interest
        return [
            {
                "moves": [
                    Move((x, y)).gtp()
                    for x in range(0, size_x)
                    for y in range(0, size_y)
                    if x < xmin or x > xmax or y < ymin or y > ymax
                ],
                "player": player,
                "untilDepth": 1,
            }
            for player in "BW"
        ]
    else:
        return []
