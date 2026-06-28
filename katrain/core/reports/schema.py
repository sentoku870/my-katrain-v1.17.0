"""TypedDict schema definitions for KaTrain JSON reports.

This logic ensures that the JSON output structure is strictly defined
and type-checked, preventing missing fields or inconsistent types.
"""
from typing import TypedDict, List, Dict, Any, Optional, Union

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
    thresholds: Dict[str, Any]
    mistake_types: List[str]
    phases: List[str]
    phase_aliases: Dict[str, str]
    category_aliases: Optional[Dict[str, Any]]
    primary_tags: List[str]
    reason_codes: List[str]
    reason_code_aliases: Dict[str, str]
    importance: Dict[str, Any]


class MetaData(TypedDict, total=False):
    schema_version: str
    run_id: str
    date_range: Optional[List[str]]
    games_analyzed: Optional[int] # Summary only
    game_id: Optional[str]        # Karte only
    loss_unit: str
    skill_preset: Optional[str]
    definitions: Optional[Definitions]
    # Karte-specific fields
    generated_at: Optional[str]
    source_filename: Optional[str]
    date: Optional[str]
    players: Optional[Any]  # PlayerGameInfo or similar nested TypedDict
    result: Optional[str]
    komi: Optional[float]
    handicap: Optional[int]
    board_size: Optional[List[int]]

class PlayerGameInfo(TypedDict):
    black: str
    white: str

class GameMeta(TypedDict):
    name: str
    date: str
    game_id: str
    moves: int
    result: Optional[str]
    handicap: int
    komi: float
    board_size: List[int] # [19, 19]
    players: PlayerGameInfo

class MistakeItem(TypedDict):
    game_name: str
    game_id: Optional[str]
    move_number: int
    player: str # "black" | "white"
    coords: str
    phase: str
    loss_clamped: float
    loss_raw: Optional[float]
    importance: float
    mistake_type: str
    reason_codes: List[str]
    primary_tag: Optional[str]

class TopMistakes(TypedDict):
    top_mistakes: List[MistakeItem]

# --- Summary Specific ---

class SummaryPlayerStats(TypedDict):
    overall: Dict[str, Any]
    mistakes: Dict[str, Any]
    phases: Dict[str, Any]
    reason_tags: Dict[str, Any]
    mistake_sequences: Dict[str, Any]
    top_mistakes: List[MistakeItem]

class SummaryReport(TypedDict):
    schema_version: str
    meta: MetaData
    games: List[GameMeta]
    players: Dict[str, SummaryPlayerStats]


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
    evidence: List[MoveEvidence]


class PriorityItem(TypedDict):
    """Reserved for future practice-priority section (Phase 153-B: removed from output).

    Kept as TypedDict so existing callers of the type system do not break at
    static analysis time, but the corresponding KarteReport field has been
    deleted and no JSON section is emitted anymore.
    """

    priority_id: str
    phase: str
    category: str
    anchor_move: Optional[MoveEvidence]


class StreakItem(TypedDict):
    """A run of consecutive mistake moves (mistake_streak / urgent_miss)."""

    start_move: int
    end_move: int
    move_count: int
    total_loss: float
    avg_loss: float
    moves: List[MoveEvidence]


class CriticalMoveItem(TypedDict):
    """A single Critical 3 entry for focused review."""

    move_number: int
    gtp_coord: str
    player: str  # "B" / "W"
    score_loss: float
    meaning_tag_id: Optional[str]
    game_phase: str
    position_difficulty: str
    area: Optional[str]
    reason_tags: List[str]
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
    """Karte JSON v3.1 (Phase 153-A/B/C).

    Schema 3.0 → 3.1:
      - Phase 153-A: Removed `difficulty` from MistakeItem.
      - Phase 153-B: Removed `practice_priorities` and
        `common_difficult_positions` sections.
      - Phase 153-C: Removed `urgent_misses` section (merged into
        `mistake_streaks`).

    The remaining fields are stable since 3.0 (weaknesses, mistake_streaks,
    critical_3, data_quality, reason_tags_distribution).
    """

    schema_version: str
    meta: MetaData
    summary: Dict[str, Any]
    important_moves: List[MistakeItem]
    weaknesses: Optional[Dict[str, List[WeaknessItem]]]
    mistake_streaks: Optional[Dict[str, List[StreakItem]]]
    critical_3: Optional[Dict[str, List[CriticalMoveItem]]]
    data_quality: Optional[DataQualityStats]
    reason_tags_distribution: Optional[Dict[str, Dict[str, int]]]

