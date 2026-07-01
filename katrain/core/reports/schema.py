"""TypedDict schema definitions for KaTrain JSON reports.

This logic ensures that the JSON output structure is strictly defined
and type-checked, preventing missing fields or inconsistent types.
"""
from typing import Any, NotRequired, TypedDict

# --- Common Sub-structures ---

class ThresholdsLoss(TypedDict):
    inaccuracy: float
    mistake: float
    blunder: float

class ThresholdsDefinition(TypedDict):
    loss: ThresholdsLoss
    bad_move_loss: float
    # Other specific thresholds can be added here loosely or strictly
    # adhering to the structure in definitions.py

class Definitions(TypedDict):
    thresholds: dict[str, Any]
    mistake_types: list[str]
    phases: list[str]
    phase_aliases: dict[str, str]
    category_aliases: dict[str, Any] | None
    primary_tags: list[str]
    reason_codes: list[str]
    reason_code_aliases: dict[str, str]
    importance: dict[str, Any]


class MetaData(TypedDict, total=False):
    schema_version: str
    run_id: str
    date_range: list[str] | None
    games_analyzed: int | None # Summary only
    game_id: str | None        # Karte only
    loss_unit: str
    skill_preset: str | None
    definitions: Definitions | None
    # Karte-specific fields
    generated_at: str | None
    source_filename: str | None
    date: str | None
    players: Any | None  # PlayerGameInfo or similar nested TypedDict
    result: str | None
    komi: float | None
    handicap: int | None
    board_size: list[int] | None
    # Phase 157-C: Summary-only. Counts of games by ``GameType``
    # (``"even"`` / ``"handicapped"`` / ``"unknown"``). Empty / absent
    # on Karte output.
    games_by_type: dict[str, int] | None

class PlayerGameInfo(TypedDict):
    black: str
    white: str

class GameMeta(TypedDict):
    name: str
    date: str
    game_id: str
    moves: int
    result: str | None
    handicap: int
    komi: float
    board_size: list[int] # [19, 19]
    players: PlayerGameInfo

class MistakeItem(TypedDict):
    game_name: str
    game_id: str | None
    move_number: int
    player: str # "black" | "white"
    coords: str
    phase: str
    loss_clamped: float
    loss_raw: float | None
    importance: float
    mistake_type: str
    reason_codes: list[str]
    primary_tag: str | None

class TopMistakes(TypedDict):
    top_mistakes: list[MistakeItem]

# --- Summary Specific ---

class SummaryPlayerStats(TypedDict):
    overall: dict[str, Any]
    mistakes: dict[str, Any]
    phases: dict[str, Any]
    reason_tags: dict[str, Any]
    mistake_sequences: dict[str, Any]
    top_mistakes: list[MistakeItem]
    # Phase 154-D: per-player win/loss aggregation (typed loosely for forward compat)
    win_loss_analysis: NotRequired[dict[str, Any]]
    # Phase 155-D: opponent-strength loss correlation
    opponent_strength_loss_correlation: NotRequired[dict[str, Any]]
    # Phase 157-C: per-game-type sub-stats (even / handicapped). Each
    # sub-stat block mirrors the top-level layout (``overall`` /
    # ``win_loss_analysis``) so LLM consumers can drill down into a
    # specific regime without re-running the whole pipeline.
    even: NotRequired[dict[str, Any]]
    handicapped: NotRequired[dict[str, Any]]


# Phase 157-C: ``SummaryReport.loss_progression`` is now a dict keyed by
# ``"all"`` / ``"even"`` / ``"handicapped"``. ``"all"`` is always present
# (cross-game aggregate); the others are only emitted when at least one
# game of that type exists in the run.
LossProgressionByType = dict[str, list[dict[str, Any]]]


class SummaryReport(TypedDict):
    schema_version: str
    meta: MetaData
    games: list[GameMeta]
    players: dict[str, SummaryPlayerStats]
    # Phase 157-D: top-level ``win_loss_analysis`` field was removed
    # (was hardcoded as ``None`` in Phase 154-D). Per-player win/loss
    # aggregation is still available under
    # ``players[...].win_loss_analysis``.
    # Phase 154-B / Phase 157-C: per-game loss progression (bucketed by
    # move-number window). Phase 157-C: dict of per-type lists
    # (``{"all": [...], "even": [...], "handicapped": [...]}``).
    loss_progression: LossProgressionByType | None


# --- Phase 149 C-1: Extended Karte sections (revived from dead code) ---


class MoveEvidence(TypedDict):
    """Representative move used as evidence for a weakness/priority/streak."""

    move_number: int
    gtp: str
    loss: float  # canonical loss (>= 0)
    category: str  # INACCURACY / MISTAKE / BLUNDER


class WeaknessItem(TypedDict):
    """One phase × category weakness identified by aggregation."""

    phase: str  # opening / middle / endgame
    category: str  # INACCURACY / MISTAKE / BLUNDER
    count: int
    total_loss: float
    avg_loss: float
    confidence: str  # low / medium / high (overall karte confidence)
    evidence: list[MoveEvidence]


class PriorityItem(TypedDict):
    """Reserved for future practice-priority section (Phase 153-B: removed from output).

    Kept as TypedDict so existing callers of the type system do not break at
    static analysis time, but the corresponding KarteReport field has been
    deleted and no JSON section is emitted anymore.
    """

    priority_id: str
    phase: str
    category: str
    anchor_move: MoveEvidence | None


class StreakItem(TypedDict):
    """A run of consecutive mistake moves (mistake_streak / urgent_miss)."""

    start_move: int
    end_move: int
    move_count: int
    total_loss: float
    avg_loss: float
    moves: list[MoveEvidence]


class CriticalMoveItem(TypedDict):
    """A single Critical 3 entry for focused review."""

    move_number: int
    gtp_coord: str
    player: str  # "B" / "W"
    score_loss: float
    meaning_tag_id: str | None
    game_phase: str
    position_difficulty: str
    area: str | None
    reason_tags: list[str]
    complexity_discounted: bool


class DataQualityStats(TypedDict):
    """Reliability / confidence statistics for the analysis run."""

    confidence_level: str  # high / medium / low
    total_moves: int
    moves_with_visits: int
    coverage_pct: float
    reliable_count: int
    reliability_pct: float
    low_confidence_count: int
    low_confidence_pct: float
    avg_visits: int
    max_visits: int
    effective_threshold: int
    is_low_reliability: bool


# --- Karte Specific (Phase 149 C-3: v3.0 with extended sections) ---


class KarteReport(TypedDict):
    """Karte JSON v3.3 (Phase 153-A/B/C + Phase 154-D + Phase 155-D).

    Schema 3.2 → 3.3: Added ``opponent_strength_loss_correlation`` section
    for per-player opponent-rank correlation.

    The remaining fields are stable since 3.0 (weaknesses, mistake_streaks,
    critical_3, data_quality, reason_tags_distribution).
    """

    schema_version: str
    meta: MetaData
    summary: dict[str, Any]
    important_moves: list[MistakeItem]
    weaknesses: dict[str, list[WeaknessItem]] | None
    mistake_streaks: dict[str, list[StreakItem]] | None
    critical_3: dict[str, list[CriticalMoveItem]] | None
    data_quality: DataQualityStats | None
    reason_tags_distribution: dict[str, dict[str, int]] | None
    # Phase 154-D: per-game win/loss analysis + per-game loss progression.
    win_loss_analysis: dict[str, Any] | None
    loss_progression: list[dict[str, Any]] | None
    # Phase 155-D: opponent-strength loss correlation (per-player).
    opponent_strength_loss_correlation: dict[str, dict[str, Any]] | None

