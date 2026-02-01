"""Phase 68: Command classes for KataGo engine operations.

This module defines the command hierarchy for engine query management.
Commands encapsulate query preparation, result handling, and lifecycle state.
"""

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from katrain.core.engine_query import build_analysis_query

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine
    from katrain.core.game_node import GameNode
    from katrain.core.sgf_parser import Move


@dataclass(eq=False)
class AnalysisCommand(ABC):
    """Abstract base class for engine analysis commands.

    Uses eq=False to enable identity-based hashing (required for Set membership).
    Each command instance is unique even if attributes are identical.

    Attributes:
        node: The GameNode to analyze.
        query_id: Assigned by engine after query is sent (None until then).
        start_time: Timestamp when command was submitted.
        status: Current state (pending, executing, completed, failed, cancelled).
        error: Error details if status is "failed".
        result: Final analysis result if status is "completed".

    Thread Safety:
        - _cancelled is a threading.Event for race-safe cancel detection
        - Status transitions should be protected by executor's lock
        - on_result/on_error/on_cancel are called outside the lock
    """

    node: "GameNode"
    query_id: Optional[str] = field(default=None)
    start_time: Optional[float] = field(default=None)
    status: str = field(default="pending")
    error: Optional[dict[str, Any]] = field(default=None)
    result: Optional[dict[str, Any]] = field(default=None)
    _cancelled: threading.Event = field(default_factory=threading.Event, repr=False)

    @abstractmethod
    def prepare(self) -> dict[str, Any]:
        """Build and return the KataGo query dict.

        This method is called by the executor before sending the query.
        It should NOT set the query ID (that's assigned by the engine).
        It should NOT set PONDER_KEY (that's set by the executor).

        Returns:
            A dict suitable for JSON serialization and sending to KataGo.
        """
        pass

    @abstractmethod
    def on_result(self, analysis: dict[str, Any], partial: bool) -> bool:
        """Handle analysis result from KataGo.

        Called by the executor when a result is received. May be called
        multiple times for partial results (isDuringSearch=True).

        Args:
            analysis: The analysis result dict from KataGo.
            partial: True if this is a partial result (isDuringSearch).

        Returns:
            True if the result was accepted and processed.
            False if the result should be ignored (e.g., noResults=True).

        Note:
            This is called outside the executor's lock. Check is_cancelled()
            if you need to guard against late delivery.
        """
        pass

    def on_error(self, error: dict[str, Any]) -> None:
        """Handle error from KataGo.

        Called by the executor when an error is received for this query.
        Default implementation stores the error and sets status to "failed".

        Args:
            error: The error dict from KataGo.
        """
        self.error = error
        self.status = "failed"

    def on_cancel(self) -> None:
        """Called when the command is cancelled.

        Override to perform cleanup. Default implementation does nothing.
        Note: status is already set to "cancelled" before this is called.
        """
        pass

    def is_cancelled(self) -> bool:
        """Check if this command has been cancelled.

        Thread-safe. Can be called from callbacks to guard against late delivery.

        Returns:
            True if mark_cancelled() has been called.
        """
        return self._cancelled.is_set()

    def mark_cancelled(self) -> None:
        """Mark this command as cancelled.

        Called by the executor when cancel is successful.
        This sets the _cancelled Event which is visible to all threads.
        """
        self._cancelled.set()


@dataclass(eq=False)
class StandardAnalysisCommand(AnalysisCommand):
    """Standard analysis command for single-position queries.

    This is the most common command type, used for analyzing a single
    game position with optional hypothetical next move.

    Attributes:
        engine: Reference to the KataGoEngine (for config access).
        callback: Called with (analysis, partial) on each result.
        error_callback: Called with (error) on error.
        visits: Maximum visits (None uses engine default).
        next_move: Optional hypothetical next move to analyze.
        extra_settings: Additional KataGo settings to merge.
        ponder: Whether this is a pondering (continuous) query.
        find_alternatives: Whether to find alternative moves.
        region_of_interest: Optional [xmin, xmax, ymin, ymax] bounds.
        time_limit: Whether to apply time limit.
        ownership: Whether to include ownership data (None=auto).
        include_policy: Whether to include policy data.
        report_every: Interval for partial results.
        priority: Priority offset for this query.
    """

    engine: Optional["KataGoEngine"] = field(default=None)
    callback: Optional[Callable[[dict[str, Any], bool], None]] = field(default=None)
    error_callback: Optional[Callable[[dict[str, Any]], None]] = field(default=None)
    visits: Optional[int] = field(default=None)
    next_move: Optional["Move"] = field(default=None)
    extra_settings: Optional[dict[str, Any]] = field(default=None)
    ponder: bool = field(default=False)
    find_alternatives: bool = field(default=False)
    region_of_interest: Optional[list[int]] = field(default=None)
    time_limit: bool = field(default=True)
    ownership: Optional[bool] = field(default=None)
    include_policy: bool = field(default=True)
    report_every: Optional[float] = field(default=None)
    priority: int = field(default=0)

    def prepare(self) -> dict[str, Any]:
        """Build the KataGo query dict.

        Uses the engine's config for default values. Does NOT set PONDER_KEY
        (that's the executor's responsibility).

        Returns:
            A dict suitable for sending to KataGo.

        Raises:
            ValueError: If engine is not set.
        """
        if self.engine is None:
            raise ValueError("engine must be set before calling prepare()")

        config = self.engine.config

        # Resolve visits
        visits = self.visits
        if visits is None:
            visits = config.get("max_visits", 100)

            # Apply analysis_focus adjustments
            focus = config.get("analysis_focus")
            if focus:
                if (focus == "black" and self.node.next_player == "W") or \
                   (focus == "white" and self.node.next_player == "B"):
                    if config.get("fast_visits"):
                        visits = config["fast_visits"]

        # Resolve ownership
        ownership = self.ownership
        if ownership is None:
            ownership = config.get("_enable_ownership", True) and not self.next_move

        # Build query (without PONDER_KEY - executor sets that)
        query = build_analysis_query(
            analysis_node=self.node,
            visits=visits,
            ponder=False,  # Placeholder, executor will override with PONDER_KEY
            ownership=ownership,
            rules=self.engine.get_rules(self.node.ruleset),
            base_priority=self.engine.base_priority,
            priority=self.priority,
            override_settings=self.engine.override_settings,
            wide_root_noise=config.get("wide_root_noise", 0.0),
            max_time=config.get("max_time"),
            time_limit=self.time_limit,
            next_move=self.next_move,
            find_alternatives=self.find_alternatives,
            region_of_interest=self.region_of_interest,
            extra_settings=self.extra_settings,
            include_policy=self.include_policy,
            report_every=self.report_every,
            ponder_key=self.engine.PONDER_KEY,
        )

        # Remove the placeholder ponder value - executor will set it
        del query[self.engine.PONDER_KEY]

        return query

    def on_result(self, analysis: dict[str, Any], partial: bool) -> bool:
        """Handle analysis result.

        Calls the callback if set and result is valid (not noResults).

        Args:
            analysis: The analysis result dict.
            partial: True if this is a partial result.

        Returns:
            True if the result was accepted, False if ignored.
        """
        # Ignore noResults responses
        if analysis.get("noResults"):
            return False

        self.result = analysis

        if self.callback:
            self.callback(analysis, partial)

        return True

    def on_error(self, error: dict[str, Any]) -> None:
        """Handle error, calling error_callback if set."""
        super().on_error(error)
        if self.error_callback:
            self.error_callback(error)
