"""Pattern Mining for Recurring Mistake Detection.

Phase 84: Extracts and aggregates mistake signatures from multiple games
to identify recurring patterns (habits/weaknesses).

Public API:
    - MistakeSignature: Frozen dataclass representing a mistake pattern
    - GameRef: Frozen dataclass for game references
    - PatternCluster: Aggregation of similar mistakes
    - create_signature: Create a signature from a MoveEval
    - mine_patterns: Extract top patterns from multiple games
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from katrain.core.analysis.board_context import classify_area

if TYPE_CHECKING:
    from katrain.core.analysis.models import EvalSnapshot
from katrain.core.analysis.meaning_tags import (
    MeaningTagId,
    get_loss_value,
    is_endgame,
)
from katrain.core.analysis.models import MistakeCategory
from katrain.core.sgf_parser import Move

# =============================================================================
# Constants
# =============================================================================

LOSS_THRESHOLD = 2.5  # Best-effort threshold for mistake detection

# Opening phase thresholds by board size
OPENING_THRESHOLDS = {
    9: 15,  # 9x9: 15 moves
    13: 25,  # 13x13: 25 moves
    19: 40,  # 19x19: 40 moves
}
DEFAULT_OPENING_THRESHOLD = 40

# Area classification thresholds by board size
AREA_THRESHOLDS = {
    9: 3,  # 9x9: 3-line (corner if < 3 from both edges)
    13: 4,  # 13x13: 4-line
    19: 4,  # 19x19: 4-line (default)
}
DEFAULT_AREA_THRESHOLD = 4

# Maximum game references per cluster (memory limit)
MAX_GAME_REFS_PER_CLUSTER = 10


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class MistakeSignature:
    """Frozen signature representing a mistake pattern.

    Attributes:
        phase: Game phase ("opening", "middle", "endgame")
        area: Board area ("corner", "edge", "center")
        primary_tag: MeaningTagId value (e.g., "overplay", "uncertain")
        severity: Mistake severity ("mistake", "blunder")
        player: Player color ("B" or "W")
    """

    phase: str
    area: str
    primary_tag: str
    severity: str
    player: str

    def sort_key(self) -> tuple[str, str, str, str, str]:
        """Return deterministic sort key for stable ordering."""
        return (self.phase, self.area, self.primary_tag, self.severity, self.player)


@dataclass(frozen=True)
class GameRef:
    """Reference to a specific move in a game.

    Attributes:
        game_name: Game identifier (file name or ID)
        move_number: Move number (1-indexed)
        player: Player color ("B" or "W")
    """

    game_name: str
    move_number: int
    player: str


@dataclass
class PatternCluster:
    """Aggregation of similar mistakes.

    Attributes:
        signature: The pattern signature
        count: Number of occurrences
        total_loss: Cumulative loss (points)
        game_refs: References to specific occurrences (max MAX_GAME_REFS_PER_CLUSTER)
    """

    signature: MistakeSignature
    count: int
    total_loss: float
    game_refs: list[GameRef] = field(default_factory=list)

    @property
    def impact_score(self) -> float:
        """Calculate impact score for ranking.

        Formula: total_loss * (1.0 + 0.1 * count)
        This prioritizes high-loss patterns while giving bonus for frequency.
        """
        return self.total_loss * (1.0 + 0.1 * self.count)


# =============================================================================
# Helper Functions
# =============================================================================


def get_severity(mistake_category: MistakeCategory) -> str | None:
    """Convert MistakeCategory to severity string.

    Args:
        mistake_category: The mistake category enum value

    Returns:
        "mistake" or "blunder" for significant mistakes, None for others
    """
    if mistake_category == MistakeCategory.MISTAKE:
        return "mistake"
    if mistake_category == MistakeCategory.BLUNDER:
        return "blunder"
    return None  # GOOD, INACCURACY, or unknown


def normalize_player(player: str | None) -> str:
    """Normalize player to canonical format.

    Args:
        player: Raw player value from MoveEval ('B'/'W'/None or lowercase)

    Returns:
        "B", "W", or "?" (unknown/pass)

    Note:
        MoveEval.player is documented as 'B'/'W'/None.
        Defensive: accepts lowercase, returns "?" for anything else.
    """
    if player is None:
        return "?"
    upper = player.upper()
    if upper == "B":
        return "B"
    if upper == "W":
        return "W"
    return "?"


def normalize_primary_tag(meaning_tag_id: str | None) -> str:
    """Normalize meaning_tag_id to a primary tag string.

    Args:
        meaning_tag_id: The meaning tag ID (may be None or empty)

    Returns:
        The tag ID if valid, otherwise "uncertain"
    """
    if not meaning_tag_id:
        return MeaningTagId.UNCERTAIN.value
    return meaning_tag_id


def get_opening_threshold(board_size: int) -> int:
    """Get the opening phase threshold for a given board size."""
    return OPENING_THRESHOLDS.get(board_size, DEFAULT_OPENING_THRESHOLD)


def get_area_threshold(board_size: int) -> int:
    """Get the area classification threshold for a given board size."""
    return AREA_THRESHOLDS.get(board_size, DEFAULT_AREA_THRESHOLD)


def determine_phase(
    move_number: int,
    total_moves: int | None,
    board_size: int = 19,
) -> str:
    """Determine the game phase for a move.

    Args:
        move_number: The move number (1-indexed)
        total_moves: Total moves in the game (may be None)
        board_size: Board size (9, 13, or 19)

    Returns:
        "opening", "middle", or "endgame"
    """
    opening_threshold = get_opening_threshold(board_size)
    if move_number <= opening_threshold:
        return "opening"
    if is_endgame(move_number, total_moves, has_endgame_hint=False):
        return "endgame"
    return "middle"


def get_area_from_gtp(gtp: str | None, board_size: int = 19) -> str | None:
    """Get board area from GTP coordinate string.

    Handles normalization (lowercase, whitespace) and error cases.

    Args:
        gtp: GTP coordinate (e.g., "D4", "pass", None)
        board_size: Board size for area classification

    Returns:
        "corner", "edge", "center", or None for pass/resign/invalid
    """
    if gtp is None:
        return None

    # Normalize
    gtp = gtp.strip()
    if not gtp:
        return None

    gtp_lower = gtp.lower()
    if gtp_lower in ("pass", "resign"):
        return None

    try:
        move = Move.from_gtp(gtp.upper())
        if move.coords is None:
            return None

        threshold = get_area_threshold(board_size)
        area = classify_area(
            move.coords,
            (board_size, board_size),
            corner_threshold=threshold,
            edge_threshold=threshold,
        )
        return area.value if area else None
    except (ValueError, AttributeError):
        return None


# =============================================================================
# Core Functions
# =============================================================================


def create_signature(
    move_eval: Any,  # MoveEval or duck-typed object
    total_moves: int | None,
    board_size: int = 19,
) -> MistakeSignature | None:
    """Create a mistake signature from a move evaluation.

    Args:
        move_eval: MoveEval object (or duck-typed with required attributes)
        total_moves: Total moves in the game
        board_size: Board size

    Returns:
        MistakeSignature if this is a significant mistake, None otherwise
    """
    # Check loss threshold
    loss = get_loss_value(move_eval)
    if loss is None or loss < LOSS_THRESHOLD:
        return None

    # Check severity (only MISTAKE/BLUNDER)
    severity = get_severity(move_eval.mistake_category)
    if severity is None:
        return None

    # Normalize player (skip if unknown)
    norm_player = normalize_player(move_eval.player)
    if norm_player == "?":
        return None  # Skip pass/unknown moves

    # Get area (skip pass/resign/invalid)
    area = get_area_from_gtp(move_eval.gtp, board_size)
    if area is None:
        return None

    # Determine phase
    phase = determine_phase(move_eval.move_number, total_moves, board_size)

    # Normalize primary tag
    primary_tag = normalize_primary_tag(move_eval.meaning_tag_id)

    return MistakeSignature(
        phase=phase,
        area=area,
        primary_tag=primary_tag,
        severity=severity,
        player=norm_player,
    )


def mine_patterns(
    games: Sequence[tuple[str, "EvalSnapshot"]],
    board_size: int = 19,
    min_count: int = 2,
    top_n: int = 5,
) -> list[PatternCluster]:
    """Extract frequent mistake patterns from multiple games.

    Args:
        games: List of (game_name, snapshot) tuples
        board_size: Board size (assumes all games use same size)
        min_count: Minimum occurrence count to include in results
        top_n: Maximum number of patterns to return

    Returns:
        List of PatternCluster sorted by impact_score (descending),
        then by signature.sort_key() for deterministic ordering
    """
    if not games or top_n <= 0:
        return []

    clusters: dict[MistakeSignature, PatternCluster] = {}

    for game_name, snapshot in games:
        total_moves = len(snapshot.moves)

        for move_eval in snapshot.moves:
            sig = create_signature(move_eval, total_moves, board_size)
            if sig is None:
                continue

            # Get loss for aggregation
            loss = get_loss_value(move_eval)
            if loss is None:
                continue

            # Skip moves without player info
            if move_eval.player is None:
                continue

            # Create game reference
            game_ref = GameRef(
                game_name=game_name,
                move_number=move_eval.move_number,
                player=move_eval.player,
            )

            # Aggregate
            if sig not in clusters:
                clusters[sig] = PatternCluster(
                    signature=sig,
                    count=0,
                    total_loss=0.0,
                    game_refs=[],
                )

            cluster = clusters[sig]
            cluster.count += 1
            cluster.total_loss += loss

            # Add game ref (with cap)
            if len(cluster.game_refs) < MAX_GAME_REFS_PER_CLUSTER:
                cluster.game_refs.append(game_ref)

    # Filter by min_count
    filtered = [c for c in clusters.values() if c.count >= min_count]

    # Sort: primary by -impact_score, secondary by signature.sort_key()
    filtered.sort(key=lambda c: (-c.impact_score, c.signature.sort_key()))

    # Return top N
    return filtered[:top_n]
