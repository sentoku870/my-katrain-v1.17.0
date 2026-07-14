"""Phase 145-C context dataclasses + EngineFailureTracker for ``run_batch``.

Phase 197 extraction: ``EngineFailureTracker`` + ``_AnalysisAborted`` +
``_BatchFileContext`` / ``_BatchSummaryContext`` / ``_BatchCuratorContext``
all live here so every sub-module of the orchestration pipeline can
import them without producing a cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.core.base_katrain import KaTrainBase
    from katrain.core.engine import KataGoEngine
    from katrain.core.game import Game


class EngineFailureTracker:
    """Track consecutive engine-related failures for circuit breaker.

    Engine failures: TIMEOUT, ENGINE_DEAD, EngineError exception
    File failures: FILE_ERROR (do not count toward abort)
    """

    def __init__(self, max_failures: int = 3):
        self.consecutive_engine_failures = 0
        self.max_failures = max_failures
        self.last_failure_file: str | None = None
        self.last_failure_reason: str | None = None

    def record_engine_failure(self, file_path: str, reason: str) -> bool:
        """Record engine failure. Returns True if should abort."""
        self.consecutive_engine_failures += 1
        self.last_failure_file = file_path
        self.last_failure_reason = reason
        return self.consecutive_engine_failures >= self.max_failures

    def record_file_error(self) -> None:
        """Record file error. Does NOT count toward abort, does NOT reset counter."""
        pass

    def record_success(self) -> None:
        """Record success. Resets consecutive failure count."""
        self.consecutive_engine_failures = 0
        self.last_failure_file = None
        self.last_failure_reason = None

    def should_abort(self) -> bool:
        return self.consecutive_engine_failures >= self.max_failures

    def get_abort_message(self) -> str:
        return (
            f"Batch aborted: {self.consecutive_engine_failures} consecutive engine failures. "
            f"Last: {self.last_failure_file} ({self.last_failure_reason})"
        )


class _AnalysisAborted(Exception):
    """Internal sentinel raised when the engine circuit breaker trips."""


@dataclass
class _BatchFileContext:
    """Parameters needed to process a single batch file."""

    katrain: KaTrainBase
    engine: KataGoEngine
    result: Any
    i: int
    total: int
    abs_path: str
    rel_path: str
    output_dir: str
    visits: int | None
    effective_visits: int | None
    timeout: float
    cancel_flag: list[bool] | None
    log_cb: Callable[[str], None] | None
    save_analyzed_sgf: bool
    generate_karte: bool
    generate_summary: bool
    generate_curator: bool
    karte_player_filter: str | None
    tracker: EngineFailureTracker
    game_stats_list: list[dict[str, Any]] | None
    games_for_curator: list[tuple[Game, dict[str, Any]]] | None
    karte_path_map: dict[str, str]
    selected_visits_list: list[int]
    variable_visits: bool
    jitter_pct: float
    deterministic: bool
    batch_timestamp: str
    skill_preset: str


@dataclass
class _BatchSummaryContext:
    """Parameters needed for summary generation."""

    result: Any
    output_dir: str
    game_stats_list: list[dict[str, Any]]
    min_games_per_player: int
    visits: int | None
    variable_visits: bool
    jitter_pct: float
    deterministic: bool
    timeout: float
    selected_visits_list: list[int]
    skill_preset: str
    karte_path_map: dict[str, str]
    batch_timestamp: str
    lang: str
    log_cb: Callable[[str], None] | None
    log: Callable[[str], None]


@dataclass
class _BatchCuratorContext:
    """Parameters needed for curator generation."""

    result: Any
    output_dir: str
    games_for_curator: list[tuple[Game, dict[str, Any]]]
    batch_timestamp: str
    user_aggregate: Any
    lang: str
    log_cb: Callable[[str], None] | None
    log: Callable[[str], None]
