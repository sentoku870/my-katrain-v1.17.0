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
    difficulty_levels: Dict[str, str]
    phases: List[str]
    phase_aliases: Dict[str, str]
    primary_tags: List[str]
    reason_codes: List[str]
    reason_code_aliases: Dict[str, str]
    importance: Dict[str, Any]

class MetaData(TypedDict):
    schema_version: str
    run_id: str
    date_range: Optional[List[str]]
    games_analyzed: Optional[int] # Summary only
    game_id: Optional[str]        # Karte only
    loss_unit: str
    skill_preset: Optional[str]
    definitions: Definitions
    # Other fields allowed

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
    difficulty: str
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
    difficulty: Dict[str, Any]
    phases: Dict[str, Any]
    reason_tags: Dict[str, Any]
    mistake_sequences: Dict[str, Any]
    top_mistakes: List[MistakeItem]

class SummaryReport(TypedDict):
    schema_version: str
    meta: MetaData
    games: List[GameMeta]
    players: Dict[str, SummaryPlayerStats]

# --- Karte Specific ---

class KarteReport(TypedDict):
    schema_version: str
    meta: MetaData
    summary: Dict[str, Any] # Loose for now, mirrors SummaryPlayerStats but per game
    important_moves: List[MistakeItem]
