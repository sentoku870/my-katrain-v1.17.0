"""Phase 68+: Query building and lifecycle utilities for KataGo analysis.

This module provides standalone functions for building queries and managing
the query lifecycle to keep engine.py focused on process lifecycle. The split
avoids circular imports between engine.py and engine_cmd/commands.py.
"""

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.core.constants import OUTPUT_DEBUG, OUTPUT_ERROR
from katrain.core.sgf_parser import Move

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine
    from katrain.core.game_node import GameNode


# Maximum pending queries before rejecting new ones
MAX_PENDING_QUERIES = 100


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


# =============================================================================
# Phase 158+: Query lifecycle (moved from engine.py)
# =============================================================================


def send_query(
    widget: "KataGoEngine",
    query: dict[str, Any],
    callback: Callable[..., None] | None,
    error_callback: Callable[..., None] | None,
    next_move: Move | None = None,
    node: "GameNode | None" = None,
) -> bool:
    """Send query to engine with safety checks.

    Threading contract:
        - callback: Called from engine read thread. MUST NOT touch Kivy UI directly.
                   Use Clock.schedule_once() if UI update needed.
        - error_callback: Scheduled on Kivy main thread via invoke_error_callback().
                         Safe to touch UI.

    Returns:
        True if query was accepted and queued.
        False if query was rejected (engine dead, pending limit).
    """
    # Safety 1: Engine alive check
    if not widget.check_alive():
        error_msg = {"error": "Engine not alive", "id": query.get("id", "unknown")}
        invoke_error_callback(widget, error_callback, error_msg)
        return False

    # Safety 2: Pending query limit check
    with widget._pending_query_lock:
        if widget._pending_query_count >= MAX_PENDING_QUERIES:
            error_msg = {"error": "Too many pending queries", "id": query.get("id", "unknown")}
            invoke_error_callback(widget, error_callback, error_msg)
            widget.katrain.log(
                f"Query rejected: {widget._pending_query_count} pending (limit: {MAX_PENDING_QUERIES})",
                OUTPUT_ERROR,
            )
            return False
        widget._pending_query_count += 1

    # Queue the query (decrement on completion/error in analysis_read_thread)

    try:
        widget.write_queue.put((query, callback, error_callback, next_move, node))
        return True
    except Exception as e:
        # Queue insertion failed (should not happen, but safety net)
        with widget._pending_query_lock:
            widget._pending_query_count = max(0, widget._pending_query_count - 1)
        widget.katrain.log(f"Failed to queue query: {e}", OUTPUT_ERROR)
        error_msg = {"error": f"Queue error: {e}", "id": query.get("id", "unknown")}
        invoke_error_callback(widget, error_callback, error_msg)
        return False


def request_analysis(
    widget: "KataGoEngine",
    analysis_node: "GameNode",
    callback: Callable[..., None],
    error_callback: Callable[..., None] | None = None,
    visits: int | None = None,
    analyze_fast: bool = False,
    time_limit: bool = True,
    find_alternatives: bool = False,
    region_of_interest: list[int] | None = None,
    priority: int = 0,
    ponder: bool = False,  # infinite visits, cancellable
    ownership: bool | None = None,
    next_move: Move | None = None,
    extra_settings: dict[str, Any] | None = None,
    include_policy: bool = True,
    report_every: float | None = None,
) -> None:
    """Build an analysis query from a GameNode and send it to the engine."""
    # Check for unsupported AE commands (clear_placements is intentionally
    # detected and skipped - we don't send these to KataGo as the engine
    # doesn't have a "clear" placement concept; setup moves are supported
    # via startgame analysis elsewhere).
    nodes = analysis_node.nodes_from_root
    clear_placements = [m for node in nodes for m in node.clear_placements]
    if clear_placements:
        widget.katrain.log(
            f"Not analyzing node {analysis_node} as there are AE commands in the path",
            OUTPUT_DEBUG,
        )
        return

    # Resolve ownership
    if ownership is None:
        ownership = widget.config["_enable_ownership"] and not next_move

    # Resolve visits with analysis_focus and analyze_fast
    if visits is None:
        visits = widget.config["max_visits"]

        # analysis_focus に基づいて visits を調整
        focus = widget.config.get("analysis_focus")
        if focus:
            # 優先しない色のターンの場合、fast_visits を使用
            if (
                (focus == "black" and analysis_node.next_player == "W")
                or (focus == "white" and analysis_node.next_player == "B")
            ) and widget.config.get("fast_visits"):
                visits = widget.config["fast_visits"]
        elif analyze_fast and widget.config.get("fast_visits"):
            # analysis_focus がない場合のデフォルト処理（analyze_fast時）
            visits = widget.config["fast_visits"]

    # Build query using engine_query module (Phase 68)
    query = build_analysis_query(
        analysis_node=analysis_node,
        visits=visits,
        ponder=ponder,
        ownership=ownership,
        rules=widget.get_rules(analysis_node.ruleset),
        base_priority=widget.base_priority,
        priority=priority,
        override_settings=widget.override_settings,
        wide_root_noise=widget.config["wide_root_noise"],
        max_time=widget.config.get("max_time"),
        time_limit=time_limit,
        next_move=next_move,
        find_alternatives=find_alternatives,
        region_of_interest=region_of_interest,
        extra_settings=extra_settings,
        include_policy=include_policy,
        report_every=report_every,
        ponder_key=widget.PONDER_KEY,
    )

    send_query(widget, query, callback, error_callback, next_move, analysis_node)
    analysis_node.analysis_visits_requested = max(analysis_node.analysis_visits_requested, visits)


def terminate_query(widget: "KataGoEngine", query_id: str, ignore_further_results: bool = True) -> None:
    """Terminate a query (thread-safe).

    Args:
        query_id: The query ID to terminate
        ignore_further_results: If True, remove from queries dict (ignore any future results)
    """
    widget.katrain.log(f"Terminating query {query_id}", OUTPUT_DEBUG)

    if query_id is not None:
        # Call via bound method so tests that patch widget.send_query work
        widget.send_query({"action": "terminate", "terminateId": query_id}, None, None)
        if ignore_further_results:
            with widget.thread_lock:
                widget.queries.pop(query_id, None)


def terminate_queries(widget: "KataGoEngine", only_for_node: "GameNode | None" = None, lock: bool = True) -> None:
    """Terminate all outstanding queries, optionally filtered by node."""
    if lock:
        with widget.thread_lock:
            return terminate_queries(widget, only_for_node=only_for_node, lock=False)
    for query_id, (_, _, _, _, node) in list(widget.queries.items()):
        if only_for_node is None or only_for_node is node:
            terminate_query(widget, query_id)


def stop_pondering(widget: "KataGoEngine") -> None:
    """Stop pondering (public API, acquires lock)."""
    with widget.thread_lock:
        pq = stop_pondering_unlocked(widget)
    if pq:
        terminate_query(widget, pq["id"], ignore_further_results=False)


def stop_pondering_unlocked(widget: "KataGoEngine") -> dict[str, Any] | None:
    """Stop pondering without acquiring lock (caller must hold thread_lock)."""
    pq = widget.ponder_query
    widget.ponder_query = None
    return pq


def invoke_error_callback(
    widget: "KataGoEngine",
    error_callback: Callable[..., None] | None,
    error_msg: dict[str, Any],
) -> None:
    """Invoke per-query error callback on the main thread.

    The main_thread_scheduler is injected by the engine owner (e.g. the GUI
    layer passes kivy.clock.Clock.schedule_once). In headless/test contexts
    the default identity scheduler calls the callback inline.

    Thread safety rule: UI-touching callbacks MUST run on main thread.
    Scheduling failures are logged but do not invoke the callback off-thread
    (which could corrupt UI state).
    """
    if error_callback is None:
        return
    try:
        # *args/**kwargs so the wrapper tolerates schedulers that pass _dt (Kivy)
        widget._main_thread_scheduler(lambda *_a, **_kw: error_callback(error_msg))
    except Exception as e:  # noqa: BLE001 - last-resort error path
        widget.katrain.log(f"Error in error_callback: {e}", OUTPUT_ERROR)


def decrement_pending_count(widget: "KataGoEngine") -> None:
    """Decrement pending counter. Called on query completion/error."""
    with widget._pending_query_lock:
        widget._pending_query_count = max(0, widget._pending_query_count - 1)


def get_pending_count(widget: "KataGoEngine") -> int:
    """Get current pending query count (thread-safe).

    Returns:
        Current number of pending queries.
    """
    with widget._pending_query_lock:
        return widget._pending_query_count


def has_query_capacity(widget: "KataGoEngine", headroom: int = 10) -> bool:
    """Check if engine has capacity for more queries.

    Args:
        headroom: Minimum free slots required (default: 10)

    Returns:
        True if pending_count <= MAX_PENDING_QUERIES - headroom
    """
    with widget._pending_query_lock:
        return widget._pending_query_count <= MAX_PENDING_QUERIES - headroom
