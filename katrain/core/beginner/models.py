"""Phase 91-92 + Phase 179: Beginner Hint Models

Data models for beginner hint detection system.

Phase 91: 4 priority detectors (SELF_ATARI, IGNORE_ATARI, MISSED_CAPTURE, CUT_RISK)
Phase 92: 6 MeaningTag fallbacks (LOW_LIBERTIES, SELF_CAPTURE_LIKE, BAD_SHAPE,
          HEAVY_GROUP, MISSED_DEFENSE, URGENT_VS_BIG)
Phase 179: 9 summary hint categories — Mistake / Freedom / Difficulty / KataGo
          derived from existing metrics that were already shown as numerical rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HintCategory(Enum):
    """Categories of beginner hints (detection priority order)

    Priority detectors (Phase 91): SELF_ATARI, IGNORE_ATARI, MISSED_CAPTURE, CUT_RISK
    MeaningTag fallbacks (Phase 92): LOW_LIBERTIES, SELF_CAPTURE_LIKE, BAD_SHAPE,
                                     HEAVY_GROUP, MISSED_DEFENSE, URGENT_VS_BIG
    Summary hints (Phase 179): MISTAKE_BLUNDER/MISTAKE/MISTAKE_GOOD,
                               FREEDOM_ONLY_MOVE/NARROW/WIDE,
                               DIFFICULTY_TRICKY/CALM,
                               KATAGO_UNCERTAIN
    Summary hints (Phase 182): OWNERSHIP_DOMINANT,
                               POLICY_CONFLICT, POLICY_CONFIDENT
    Summary hints (Phase 186): CURATOR_WEAK_AXIS
    """

    # Priority detectors (Phase 91)
    SELF_ATARI = "self_atari"
    IGNORE_ATARI = "ignore_atari"
    MISSED_CAPTURE = "missed_capture"
    CUT_RISK = "cut_risk"

    # MeaningTag fallbacks (Phase 92)
    LOW_LIBERTIES = "low_liberties"
    SELF_CAPTURE_LIKE = "self_capture_like"
    BAD_SHAPE = "bad_shape"
    HEAVY_GROUP = "heavy_group"
    MISSED_DEFENSE = "missed_defense"
    URGENT_VS_BIG = "urgent_vs_big"

    # Summary: Mistake (Phase 179) - pointsLost ベース
    MISTAKE_BLUNDER = "mistake_blunder"  # pointsLost >= 8.0
    MISTAKE_MISTAKE = "mistake_mistake"  # 2.0 <= pointsLost < 8.0
    MISTAKE_GOOD = "mistake_good"  # pointsLost < 0.5 かつ 終局近く
    # Summary: Freedom (Phase 179) - candidate_moves ベース
    FREEDOM_ONLY_MOVE = "freedom_only_move"  # good候補 <= 1
    FREEDOM_NARROW = "freedom_narrow"  # good候補 2-3
    FREEDOM_WIDE = "freedom_wide"  # good候補 >= 4
    # Summary: Difficulty (Phase 179) - DifficultyMetrics ベース
    DIFFICULTY_TRICKY = "difficulty_tricky"  # overall >= 0.7
    DIFFICULTY_CALM = "difficulty_calm"  # overall <= 0.3
    # Summary: KataGo uncertainty (Phase 179) - scoreStdev ベース
    KATAGO_UNCERTAIN = "katago_uncertain"  # scoreStdev >= 1.5
    # Summary: Ownership (Phase 182) - 予測 territory ベース
    OWNERSHIP_DOMINANT = "ownership_dominant"  # predicted territory が片側 >= 85%
    # Summary: Policy (Phase 182) - KataGo policy 確率分布ベース
    POLICY_CONFLICT = "policy_conflict"  # top policy value <= 0.15
    POLICY_CONFIDENT = "policy_confident"  # top policy value >= 0.5
    # Summary: Curator (Phase 186) - 棋譜全体の Mistake 傾向
    CURATOR_WEAK_AXIS = "curator_weak_axis"  # node.meaning_tag_id が weak_tags に該当

    @classmethod
    def from_meaning_tag_id(cls, tag_id: str | None) -> HintCategory | None:
        """Map MeaningTagId string to HintCategory.

        Returns None for unknown/unsupported IDs (no crash).

        Args:
            tag_id: MeaningTagId value (e.g., "capture_race_loss")

        Returns:
            Corresponding HintCategory or None if unknown
        """
        if tag_id is None:
            return None

        _MAPPING = {
            "capture_race_loss": cls.LOW_LIBERTIES,
            "life_death_error": cls.SELF_CAPTURE_LIKE,
            "shape_mistake": cls.BAD_SHAPE,
            "overplay": cls.HEAVY_GROUP,
            "connection_miss": cls.MISSED_DEFENSE,
            "endgame_slip": cls.URGENT_VS_BIG,
        }
        return _MAPPING.get(tag_id)  # Returns None for unknown

    @property
    def is_structural(self) -> bool:
        """Phase 91 structural detectors (always reliable, board-state based)."""
        return self in _STRUCTURAL_CATEGORIES

    @property
    def is_meaning_tag(self) -> bool:
        """Phase 92 MeaningTag fallback."""
        return self in _MEANING_TAG_CATEGORIES

    @property
    def is_summary(self) -> bool:
        """Phase 179 summary hint derived from existing metrics."""
        return self in _SUMMARY_CATEGORIES

    @property
    def config_key(self) -> str | None:
        """Settings key under beginner_hints/ for this category group, or None."""
        if self in _STRUCTURAL_CATEGORIES or self in _MEANING_TAG_CATEGORIES:
            return None  # gated by beginner_hints/enabled only
        if self in (
            HintCategory.MISTAKE_BLUNDER,
            HintCategory.MISTAKE_MISTAKE,
            HintCategory.MISTAKE_GOOD,
        ):
            return "summary_mistake"
        if self in (
            HintCategory.FREEDOM_ONLY_MOVE,
            HintCategory.FREEDOM_NARROW,
            HintCategory.FREEDOM_WIDE,
        ):
            return "summary_freedom"
        if self in (
            HintCategory.DIFFICULTY_TRICKY,
            HintCategory.DIFFICULTY_CALM,
        ):
            return "summary_difficulty"
        if self is HintCategory.KATAGO_UNCERTAIN:
            return "katago_uncertain"
        if self is HintCategory.OWNERSHIP_DOMINANT:
            return "summary_ownership"
        if self in (HintCategory.POLICY_CONFLICT, HintCategory.POLICY_CONFIDENT):
            return "summary_policy"
        if self is HintCategory.CURATOR_WEAK_AXIS:
            return "curator_hint"
        return None

    @property
    def i18n_namespace(self) -> str:
        """Phase 179.1: namespace used as the i18n key prefix for this category.

        Returns a string of the form ``"beginner_hint:<value>"`` which
        combined with the ``title``/``body``/``why`` suffix produces the
        full i18n key (e.g. ``beginner_hint:self_atari:title``).
        """
        return f"beginner_hint:{self.value}"

    @property
    def fallback_title(self) -> str:
        """Phase 179.1: English fallback title when the .po key is missing.

        Used by ``gui.controlspanel.ControlsPanel._format_beginner_hint``
        when the localised title is unavailable (e.g. before
        ``pybabel compile`` runs or for languages without a translation).
        """
        return _FALLBACK_TITLES[self]

    @property
    def fallback_body(self) -> str:
        """Phase 179.1: English fallback body when the .po key is missing."""
        return _FALLBACK_BODIES[self]


# Phase 179.1: Centralised fallback strings (English). Previously these
# lived in a hand-maintained dict inside ``controlspanel.py``. Moving them
# here keeps each category's metadata co-located with the enum and turns
# the GUI into a thin i18n lookup.
_FALLBACK_TITLES: dict[HintCategory, str] = {
    HintCategory.SELF_ATARI: "Dangerous Move",
    HintCategory.IGNORE_ATARI: "Atari Ignored",
    HintCategory.MISSED_CAPTURE: "Missed Capture",
    HintCategory.CUT_RISK: "Cut Risk",
    HintCategory.LOW_LIBERTIES: "Low Liberties",
    HintCategory.SELF_CAPTURE_LIKE: "Life and Death",
    HintCategory.BAD_SHAPE: "Bad Shape",
    HintCategory.HEAVY_GROUP: "Heavy Stones",
    HintCategory.MISSED_DEFENSE: "Weak Connection",
    HintCategory.URGENT_VS_BIG: "Slow Move",
    HintCategory.MISTAKE_BLUNDER: "Blunder",
    HintCategory.MISTAKE_MISTAKE: "Mistake",
    HintCategory.MISTAKE_GOOD: "Good Move",
    HintCategory.FREEDOM_ONLY_MOVE: "Only Move",
    HintCategory.FREEDOM_NARROW: "Narrow Choice",
    HintCategory.FREEDOM_WIDE: "Many Choices",
    HintCategory.DIFFICULTY_TRICKY: "Tricky Position",
    HintCategory.DIFFICULTY_CALM: "Calm Position",
    HintCategory.KATAGO_UNCERTAIN: "Even KataGo Is Unsure",
    HintCategory.OWNERSHIP_DOMINANT: "One-Sided Territory",
    HintCategory.POLICY_CONFLICT: "KataGo Is Unsure",
    HintCategory.POLICY_CONFIDENT: "KataGo Is Confident",
    HintCategory.CURATOR_WEAK_AXIS: "Your Weak Pattern",
}

_FALLBACK_BODIES: dict[HintCategory, str] = {
    HintCategory.SELF_ATARI: "Playing here puts your group in atari.",
    HintCategory.IGNORE_ATARI: "Your group is still in atari.",
    HintCategory.MISSED_CAPTURE: "You could have captured opponent's stones.",
    HintCategory.CUT_RISK: "Your groups could be cut apart here.",
    HintCategory.LOW_LIBERTIES: "This group has few liberties and is in danger.",
    HintCategory.SELF_CAPTURE_LIKE: "This position involves life and death of stones.",
    HintCategory.BAD_SHAPE: "This is an inefficient shape.",
    HintCategory.HEAVY_GROUP: "Your stones have become heavy.",
    HintCategory.MISSED_DEFENSE: "Your stones' connection is weak.",
    HintCategory.URGENT_VS_BIG: "There are bigger moves elsewhere.",
    HintCategory.MISTAKE_BLUNDER: "This move lost a lot of points. Look for safer choices.",
    HintCategory.MISTAKE_MISTAKE: "A better candidate was available here.",
    HintCategory.MISTAKE_GOOD: "Solid endgame move — keep this up.",
    HintCategory.FREEDOM_ONLY_MOVE: "There was basically one good move here.",
    HintCategory.FREEDOM_NARROW: "Only a few moves were worth considering.",
    HintCategory.FREEDOM_WIDE: "Several moves were equally good here.",
    HintCategory.DIFFICULTY_TRICKY: "KataGo rates this as a hard position.",
    HintCategory.DIFFICULTY_CALM: "KataGo rates this as an easy position.",
    HintCategory.KATAGO_UNCERTAIN: "The score is unclear even for KataGo here.",
    HintCategory.OWNERSHIP_DOMINANT: "KataGo expects one side to control most of the board.",
    HintCategory.POLICY_CONFLICT: "KataGo's top move has low confidence — multiple candidates.",
    HintCategory.POLICY_CONFIDENT: "KataGo has a clear top move here.",
    HintCategory.CURATOR_WEAK_AXIS: "This pattern appears frequently in your games.",
}


# Phase 179: Category group sets for priority chain.
_STRUCTURAL_CATEGORIES = frozenset(
    {
        HintCategory.SELF_ATARI,
        HintCategory.IGNORE_ATARI,
        HintCategory.MISSED_CAPTURE,
        HintCategory.CUT_RISK,
    }
)
_MEANING_TAG_CATEGORIES = frozenset(
    {
        HintCategory.LOW_LIBERTIES,
        HintCategory.SELF_CAPTURE_LIKE,
        HintCategory.BAD_SHAPE,
        HintCategory.HEAVY_GROUP,
        HintCategory.MISSED_DEFENSE,
        HintCategory.URGENT_VS_BIG,
    }
)
_SUMMARY_CATEGORIES = frozenset(
    {
        HintCategory.MISTAKE_BLUNDER,
        HintCategory.MISTAKE_MISTAKE,
        HintCategory.MISTAKE_GOOD,
        HintCategory.FREEDOM_ONLY_MOVE,
        HintCategory.FREEDOM_NARROW,
        HintCategory.FREEDOM_WIDE,
        HintCategory.DIFFICULTY_TRICKY,
        HintCategory.DIFFICULTY_CALM,
        HintCategory.KATAGO_UNCERTAIN,
        HintCategory.OWNERSHIP_DOMINANT,
        HintCategory.POLICY_CONFLICT,
        HintCategory.POLICY_CONFIDENT,
        HintCategory.CURATOR_WEAK_AXIS,
    }
)


@dataclass(frozen=True)
class BeginnerHint:
    """A single beginner hint for a move

    Attributes:
        category: The type of hint (determines priority)
        coords: Board coordinates to highlight (x, y) or None
        severity: Severity level (higher = more important)
        context: Additional context for display/debugging
    """

    category: HintCategory
    coords: tuple[int, int] | None
    severity: int
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SummaryHintContext:
    """Phase 179: Context for summary hint generation.

    Snapshot of the metrics that feed the Mistake/Freedom/Difficulty/KataGo
    detector family. Decoupled from GameNode so detectors can be unit-tested
    without instantiating a full Game.

    Attributes:
        points_lost: parent.scoreLead - node.scoreLead (None if unknown).
        winrate_lost: parent.winrate - node.winrate (None if unknown).
        good_move_count: Number of candidates with relativePointsLost <= 1.0.
        near_move_count: Number of candidates with relativePointsLost <= 2.0.
        overall_difficulty: DifficultyMetrics.overall_difficulty (None if unknown).
        is_reliable: Whether DifficultyMetrics is reliable (visits sufficient).
        score_stdev: rootInfo.scoreStdev (None if unknown).
        root_visits: rootInfo.visits (0 if unknown).
        move_number: Current move number (1-based).
        is_endgame: True when within ~30 moves of estimated endgame.
        score_loss_threshold_blunder: Phase 179a tunable threshold for blunder
            (default 8.0). Lets users / tests override without patching.
        score_loss_threshold_mistake: Phase 179a tunable threshold for
            mistake (default 2.0).
        score_stdev_threshold: Phase 179a tunable threshold for KATAGO_UNCERTAIN
            (default 1.5).
        predicted_territory: Phase 182 — sum of ``node.ownership`` (flat list
            of -1..+1) divided by board cell count. +1 means the mover's
            opponent owns 100% of the board, -1 means the mover owns 100%.
            None when ownership is unavailable (config disabled or no analysis).
        best_policy: Phase 182 — maximum value of ``node.policy`` flat list
            (probability 0..1 of KataGo's top choice). None when policy
            unavailable.
        best_policy_threshold_conflict: Phase 182 — top policy <= this
            triggers POLICY_CONFLICT (default 0.15).
        best_policy_threshold_confident: Phase 182 — top policy >= this
            triggers POLICY_CONFIDENT (default 0.5).
        territory_dominant_threshold: Phase 182 — |predicted_territory| >=
            this triggers OWNERSHIP_DOMINANT (default 0.85, meaning 85% of
            cells lean one way).
    """

    points_lost: float | None = None
    winrate_lost: float | None = None
    good_move_count: int = 0
    near_move_count: int = 0
    overall_difficulty: float | None = None
    is_reliable: bool = False
    score_stdev: float | None = None
    root_visits: int = 0
    move_number: int = 0
    is_endgame: bool = False
    score_loss_threshold_blunder: float = 8.0
    score_loss_threshold_mistake: float = 2.0
    score_stdev_threshold: float = 1.5
    # Phase 182
    predicted_territory: float | None = None
    best_policy: float | None = None
    best_policy_threshold_conflict: float = 0.15
    best_policy_threshold_confident: float = 0.5
    territory_dominant_threshold: float = 0.85


@dataclass
class DetectorInput:
    """Input data for hint detectors

    Contains all information needed by detection functions,
    gathered from game state at a specific node.

    Attributes:
        node: The GameNode being evaluated (after the move)
        parent: The parent node (before the move)
        move_coords: Coordinates of the move, or None for pass
        player: Player who made the move ("B" or "W")
        groups_after: Group list after the move
        groups_before: Group list before the move
        was_capture: Whether the move captured any stones
        captured_count: Number of stones captured
    """

    node: Any  # GameNode
    parent: Any | None  # GameNode | None
    move_coords: tuple[int, int] | None
    player: str  # "B" or "W"
    groups_after: list[Any]  # list[Group]
    groups_before: list[Any]  # list[Group]
    was_capture: bool
    captured_count: int
