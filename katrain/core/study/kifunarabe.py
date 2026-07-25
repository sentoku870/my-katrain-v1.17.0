# katrain/core/study/kifunarabe.py
"""Kifunarabe (棋譜並べ / pro-move prediction) core logic.

This module provides:
- KifunarabeConfig: user-selected settings for a session
- KifunarabeGuessResult: record of a single position's final answer
- KifunarabeSummary: aggregated statistics for a session
- KifunarabeSession: manager for tracking guesses and summaries
- evaluate_guess(): judge a guessed coordinate against the recorded move
- should_auto_advance(): decide whether the engine should auto-play a side
- build_kifunarabe_options(): assemble the on-board choice set
  (Phase 290 supports a ``near_actual`` pool that picks candidates
  within ``near_threshold_points`` of the actual move's ``pointsLost``,
  in addition to the legacy ``top_kata`` order-based selection)

The module is Kivy-independent and operates on GameNode data only through
type hints (TYPE_CHECKING) so that tests can run without the GUI.
"""

import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from katrain.core.study.kifunarabe_constants import (
    KIFUNARABE_CANDIDATE_POOL_DEFAULT,
    KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL,
    KIFUNARABE_CANDIDATE_POOL_TOP_KATA,
    KIFUNARABE_NEAR_THRESHOLD_DEFAULT,
    VALID_CANDIDATE_POOLS,
)

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode

_log = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

#: Minimum KataGo visits required for a node's candidate moves to be used
#: as the multiple-choice options for the user.
MIN_CANDIDATE_VISITS = 100

#: Side identifiers used in this module.
SIDE_BOTH = "both"
SIDE_BLACK = "B"
SIDE_WHITE = "W"

#: Allowed values for KifunarabeConfig.turn (kept as constants for clarity).
VALID_TURNS: tuple[str, ...] = (SIDE_BOTH, SIDE_BLACK, SIDE_WHITE)

#: Allowed hint counts. 0 = no hint, 1..5 = top-N candidates shown.
VALID_HINT_COUNTS: tuple[int, ...] = (0, 1, 2, 3, 4, 5)

#: Allowed values for KifunarabeConfig.max_moves.
#: 0 = play through the entire mainline, otherwise capped at this many moves.
VALID_MAX_MOVES: tuple[int, ...] = (0, 50, 100, 150)

#: Phase 179-B1: maximum number of Critical 3 entries per player (B and W).
CRITICAL_3_PER_PLAYER = 3

#: Phase 290: re-export the candidate pool constants for callers that
#: already import from this module (avoids forcing a switch to
#: ``kifunarabe_constants`` just to read the pool name).
POOL_TOP_KATA = KIFUNARABE_CANDIDATE_POOL_TOP_KATA
POOL_NEAR_ACTUAL = KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL


# =============================================================================
# Enums
# =============================================================================


class GuessOutcome(Enum):
    """Outcome classification for a single guess.

    CORRECT         - the user's guess matches the recorded move.
    WRONG_GUESS     - the user's click did NOT match the recorded move
                      ("this counts as a failure, distinct from a skip).
    AUTO_ADVANCE    - the user's side was skipped (turn=B/W) and engine played.
    SKIPPED         - the position was neither guessed nor auto-advanced
                      (e.g. node had no continuation, or session ended
                      before the user clicked).
    """

    CORRECT = "correct"
    WRONG_GUESS = "wrong_guess"
    AUTO_ADVANCE = "auto_advance"
    SKIPPED = "skipped"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class KifunarabeConfig:
    """User-selected configuration for a kifunarabe session.

    Attributes:
        turn: One of "both" (both sides), "B" (black only), "W" (white only).
        max_hints: Number of candidate moves shown as hints (0..5).
        max_moves: Maximum number of moves to play through (0 = entire mainline).
        auto_export_weaknesses: Phase 249-γ. If True, finished-session
            ``WRONG_GUESS`` results are appended to a JSON file under
            :attr:`KIFUNARABE_AUTO_EXPORT_DIR_DEFAULT` (or the
            directory the GUI configured). Default is False because
            the export is opt-in — most users do not want every
            session to generate a side-effect file.
    """

    turn: str = SIDE_BOTH
    max_hints: int = 3
    max_moves: int = 0
    auto_export_weaknesses: bool = False

    def __post_init__(self) -> None:
        if self.turn not in VALID_TURNS:
            raise ValueError(f"Invalid turn: {self.turn!r}; expected one of {VALID_TURNS}")
        if self.max_hints not in VALID_HINT_COUNTS:
            raise ValueError(f"Invalid max_hints: {self.max_hints}; expected one of {VALID_HINT_COUNTS}")
        if self.max_moves not in VALID_MAX_MOVES:
            raise ValueError(f"Invalid max_moves: {self.max_moves}; expected one of {VALID_MAX_MOVES}")
        # ``auto_export_weaknesses`` is a plain bool — no extra
        # validation needed.


@dataclass
class KifunarabeGuessResult:
    """Record of one position in a kifunarabe session.

    Attributes:
        move_number: The position move number (1-indexed, equals tree depth).
        expected_gtp: GTP coordinate of the recorded (correct) move.
        guessed_gtp: GTP coordinate the user picked, or None if auto-advanced.
        outcome: GuessOutcome classification.
        hints_shown: Number of hint markers visible at this position.
        timestamp: When the result was recorded.
    """

    move_number: int
    expected_gtp: str | None
    guessed_gtp: str | None
    outcome: GuessOutcome
    hints_shown: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class KifunarabeSummary:
    """Aggregate statistics for a finished (or aborted) session.

    All counts are 0 when total_positions == 0.

    Phase 179-B2: the ``critical_3_*`` fields track performance on the
    Critical 3 review positions selected at session start. They stay at
    0 when no Critical 3 set was supplied.
    """

    total_positions: int
    correct_count: int
    wrong_count: int
    auto_advance_count: int
    skipped_count: int
    max_moves_reached: bool = False
    # Phase 179-B2: Critical 3 hit-rate breakdown.
    critical_3_total: int = 0
    critical_3_correct: int = 0
    critical_3_wrong: int = 0
    critical_3_skipped: int = 0

    @property
    def attempted_count(self) -> int:
        """Positions where the user actively made a guess (correct or wrong)."""
        return self.correct_count + self.wrong_count

    @property
    def guessed_count(self) -> int:
        """Alias for ``attempted_count`` for backward-compat display code."""
        return self.attempted_count

    @property
    def correct_rate(self) -> float:
        """Percentage of attempted guesses that were correct.

        Denominator is the number of positions where the user actually clicked
        (correct + wrong). Auto-advanced and SKIPPED positions are excluded.
        """
        attempted = self.attempted_count
        if attempted <= 0:
            return 0.0
        return self.correct_count / attempted * 100.0

    @property
    def wrong_rate(self) -> float:
        """Percentage of attempted guesses that were wrong."""
        attempted = self.attempted_count
        if attempted <= 0:
            return 0.0
        return self.wrong_count / attempted * 100.0

    @property
    def overall_rate(self) -> float:
        """Percentage including auto-advances as 'correct'."""
        if self.total_positions <= 0:
            return 0.0
        return (self.correct_count + self.auto_advance_count) / self.total_positions * 100.0

    @property
    def critical_3_hit_rate(self) -> float:
        """Phase 179-B2: percentage of Critical 3 positions guessed correctly.

        Returns 0.0 when no Critical 3 set was supplied (total == 0).
        """
        if self.critical_3_total <= 0:
            return 0.0
        return self.critical_3_correct / self.critical_3_total * 100.0


# =============================================================================
# Pure Helper Functions
# =============================================================================


def _expected_move_gtp(node: "GameNode") -> str | None:
    """Return the GTP coordinate of the mainline child of ``node`` (or None).

    The "expected" move in kifunarabe is the move recorded in the game tree -
    i.e. the actual move the player made at this position. We use
    ``ordered_children[0]`` because that is the mainline continuation.

    Phase 249-α: hardened to swallow the same edge cases the
    ``_expected_gtp_from_node`` helper on the controller side used to
    handle (``getattr`` lookups, non-str returns, raising ``gtp``).
    The two helpers are now consolidated: callers (e.g. the controller
    guess mixin) should import this function rather than re-implement
    the resolution locally.

    Phase 249-hotfix: the defensive ``getattr`` / ``try``-``except`` /
    ``isinstance`` guards were lost during the γ rebase. Restored so
    unit tests (and any non-conforming ``GameNode`` subclass) get a
    graceful ``None`` instead of a propagated ``AttributeError`` /
    ``TypeError``.
    """
    ordered = getattr(node, "ordered_children", None) or []
    if not ordered:
        return None
    child = ordered[0]
    if child is None:
        return None
    child_move = getattr(child, "move", None)
    if child_move is None:
        return None
    gtp = getattr(child_move, "gtp", None)
    if not callable(gtp):
        return None
    try:
        result = gtp()
    except Exception:  # noqa: BLE001
        return None
    return result if isinstance(result, str) else None


def _coords_equal_gtp(coords: tuple[int, int], expected_gtp: str, node: "GameNode") -> bool:
    """Return True if user ``coords`` match the expected GTP move on ``node``.

    Handles pass moves (``expected_gtp == "pass"``) by checking ``is_pass``.
    """
    from katrain.core.sgf_parser import Move

    expected_move = Move.from_gtp(expected_gtp, player=node.next_player)
    if expected_move.is_pass:
        return False
    guess_move = Move(coords, player=node.next_player)
    return guess_move.coords == expected_move.coords


def should_auto_advance(config: KifunarabeConfig, next_player: str) -> bool:
    """Return True if the engine should auto-play for ``next_player``.

    With ``turn="both"`` we never auto-advance.
    With ``turn="B"`` we auto-advance only when it is White's turn.
    With ``turn="W"`` we auto-advance only when it is Black's turn.
    """
    if config.turn == SIDE_BOTH:
        return False
    if config.turn == SIDE_BLACK:
        return next_player == SIDE_WHITE
    if config.turn == SIDE_WHITE:
        return next_player == SIDE_BLACK
    return False


def _coerce_candidate_pool(value: Any, *, default: str = KIFUNARABE_CANDIDATE_POOL_DEFAULT) -> str:
    """Normalise a candidate-pool config value into one of :data:`VALID_CANDIDATE_POOLS`.

    Accepts ``None`` (returns ``default``), and silently clamps any
    unrecognised string back to ``default``. The function exists so the
    GUI can pass raw ``ConfigParser`` values without us leaking
    ``ValueError``s into badukpan hint rendering.
    """
    if isinstance(value, str) and value in VALID_CANDIDATE_POOLS:
        return value
    return default


def _coerce_near_threshold(value: Any, *, default: float = KIFUNARABE_NEAR_THRESHOLD_DEFAULT) -> float:
    """Clamp a near-threshold config value into ``[0.0, 20.0]``.

    Strings that look numeric (e.g. ``"3.5"``) are accepted. Negative
    values are clamped to ``0.0``; absurdly large ones are clamped to
    ``20.0``. Anything non-numeric falls back to ``default`` so the GUI
    cannot crash the choice-set builder on a mistyped config entry.
    """
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(20.0, coerced))


def _candidate_points_lost(cand: dict[str, Any]) -> float:
    """Return the ``pointsLost`` of a candidate dict, treating missing as 0.

    ``pointsLost`` is clipped to ``>= 0`` by ``GameNode.candidate_moves``;
    this helper exists so the call sites stay readable and easy to mock.
    """
    raw = cand.get("pointsLost", 0)
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return 0.0


def _get_actual_points_lost(
    node: "GameNode",
    actual_gtp: str,
    parent_candidates: list[dict[str, Any]],
) -> float:
    """Determine the ``pointsLost`` centre for the ``near_actual`` pool mode.

    Resolution order:

    1. The actual move's entry inside ``parent_candidates`` (the parent's
       KataGo analysis already sees the move and labels it with its own
       ``pointsLost``). ``actual_gtp`` matching is case-insensitive.
    2. The actual move's child node analysis: ``pointsLost = root_score -
       child_score`` (signed by the side-to-move, clipped to ``>=0``).
       This handles games where the actual move was not in the parent's
       top-N candidate list.
    3. Fallback ``0.0`` — equivalent to assuming the actual move sits at
       KataGo's top. This is also what the legacy ``top_kata`` path used
       implicitly, so the puzzle never has zero options in degenerate
       cases.

    Args:
        node: The position whose options we're building (the *parent*
            of the move the user must guess).
        actual_gtp: GTP coordinate of the recorded (correct) move.
        parent_candidates: ``node.candidate_moves`` (may be empty).

    Returns:
        A non-negative ``pointsLost`` value, in the same units as
        ``GameNode.candidate_moves`` (i.e. signed points lost from the
        to-play player's perspective).
    """
    for cand in parent_candidates:
        gtp = cand.get("move")
        if gtp and isinstance(gtp, str) and gtp.upper() == actual_gtp.upper():
            return _candidate_points_lost(cand)

    ordered = getattr(node, "ordered_children", None) or []
    if ordered:
        child = ordered[0]
        if child is not None and getattr(child, "analysis_exists", False):
            root_analysis = getattr(node, "analysis", None) or {}
            root = root_analysis.get("root") or {}
            try:
                root_score = float(root.get("scoreLead", 0))
                child_score = float(child.analysis["root"]["scoreLead"])
            except (KeyError, TypeError, ValueError):
                root_score = child_score = None  # type: ignore[assignment]
            if root_score is not None and child_score is not None:
                sign = node.player_sign(getattr(node, "next_player", None)) if hasattr(node, "player_sign") else 1
                return max(0.0, sign * (root_score - child_score))

    return 0.0


def _select_near_actual_options(
    parent_candidates: list[dict[str, Any]],
    actual_gtp: str,
    actual_points_lost: float,
    threshold: float,
    slots_for_kata: int,
) -> list[str]:
    """Pick up to ``slots_for_kata`` candidates within ``threshold`` of actual.

    Candidates are sorted by ``|pointsLost - actual_points_lost|``
    ascending (closest first), then by KataGo ``order`` as a tiebreaker.
    When fewer than ``slots_for_kata`` neighbours are available the
    function back-fills with the next-best KataGo candidates so the user
    always sees the requested number of markers.
    """
    selected: list[str] = []
    seen: set[str] = {actual_gtp.upper()}

    neighbours = [
        c
        for c in parent_candidates
        if isinstance(c.get("move"), str)
        and c["move"].upper() not in seen
        and abs(_candidate_points_lost(c) - actual_points_lost) <= threshold
    ]
    neighbours.sort(
        key=lambda c: (
            abs(_candidate_points_lost(c) - actual_points_lost),
            c.get("order", 1 << 20),
        )
    )

    for cand in neighbours:
        if len(selected) >= slots_for_kata:
            break
        gtp = cand["move"]
        selected.append(gtp)
        seen.add(gtp.upper())

    if len(selected) < slots_for_kata:
        for cand in parent_candidates:
            if len(selected) >= slots_for_kata:
                break
            gtp = cand.get("move")
            if not isinstance(gtp, str) or gtp.upper() in seen:
                continue
            selected.append(gtp)
            seen.add(gtp.upper())

    return selected[:slots_for_kata]


def _select_top_kata_options(
    parent_candidates: list[dict[str, Any]],
    actual_gtp: str,
    slots_for_kata: int,
) -> list[str]:
    """Legacy KataGo top-N behaviour preserved verbatim (Phase 177)."""
    selected: list[str] = []
    seen: set[str] = {actual_gtp.upper()}
    for cand in parent_candidates:
        gtp = cand.get("move")
        if not isinstance(gtp, str) or gtp.upper() in seen:
            continue
        selected.append(gtp)
        seen.add(gtp.upper())
        if len(selected) >= slots_for_kata:
            break
    return selected


def get_hint_candidates(
    node: "GameNode",
    max_hints: int,
    min_visits: int = MIN_CANDIDATE_VISITS,
) -> list[str]:
    """Return up to ``max_hints`` candidate GTP coordinates for the current node.

    The list always contains the expected (mainline) move if it appears in the
    KataGo candidates; otherwise the engine's top picks are returned. When
    ``max_hints == 0`` an empty list is returned.

    Args:
        node: Current GameNode.
        max_hints: Number of hints to surface (0..5).
        min_visits: Minimum KataGo root visits to consider analysis reliable.

    Returns:
        List of GTP coordinate strings, length 0..max_hints.
    """
    if max_hints <= 0:
        return []
    if not node.analysis_exists:
        return []
    if node.root_visits < min_visits:
        return []
    candidates = node.candidate_moves
    if not candidates:
        return []
    top: list[str] = []
    seen: set[str] = set()
    for cand in candidates:
        gtp = cand.get("move")
        if not gtp or gtp in seen:
            continue
        seen.add(gtp)
        top.append(gtp)
        if len(top) >= max_hints:
            break
    return top


def build_kifunarabe_options(
    node: "GameNode",
    max_hints: int,
    min_visits: int = MIN_CANDIDATE_VISITS,
    *,
    candidate_pool: str = KIFUNARABE_CANDIDATE_POOL_DEFAULT,
    near_threshold_points: float = KIFUNARABE_NEAR_THRESHOLD_DEFAULT,
) -> list[str]:
    """Build the on-board choice set for a kifunarabe (棋譜並べ) position.

    The choice set always contains the recorded (actual) move first. The
    remaining ``max_hints - 1`` slots are filled according to
    ``candidate_pool``:

    - ``"top_kata"`` (legacy, Phase 177): KataGo candidates in ``order``
      ascending, best-to-decreasing, without shuffling. The user can read
      the engine ranking on the board.
    - ``"near_actual"`` (Phase 290): KataGo candidates whose ``pointsLost``
      is within ``near_threshold_points`` of the actual move's
      ``pointsLost``, sorted by closeness. Surfaces alternative hands of
      comparable evaluation rather than the obvious-best moves. Falls back
      to ``top_kata`` ordering when there aren't enough neighbours; this
      keeps the click count stable across positions.

    Edge cases:
    - ``max_hints <= 0``: returns ``[]`` (blind mode, no markers).
    - ``max_hints == 1``: returns ``[actual]`` only (effectively blind -
      there is exactly one clickable marker).
    - No recorded continuation (game ended): returns ``[]``.
    - KataGo analysis absent or low-visits: falls back to ``[actual]`` when
      ``max_hints >= 1`` (we still want the user to be able to click the
      correct move), otherwise ``[]``.
    - Unrecognised ``candidate_pool`` value: coerced to the default
      silently (see :func:`_coerce_candidate_pool`).

    Args:
        node: Current GameNode whose candidates are filtered.
        max_hints: 0..5 -- total options to surface (actual included).
        min_visits: Minimum KataGo root visits to trust candidates.
        candidate_pool: ``"top_kata"`` or ``"near_actual"`` (see above).
        near_threshold_points: Tolerance in points for the
            ``near_actual`` mode. Negative or unparseable values clamp to
            ``[0.0, 20.0]``.

    Returns:
        List of GTP coordinate strings, length 0..max_hints. The actual
        move is always at index ``0`` (so the GUI can mark it
        unambiguously as ``_kifunarabe_actual``); the remaining entries
        come from the selected pool mode.
    """
    if max_hints < 0:
        return []

    actual_gtp = _expected_move_gtp(node)
    if actual_gtp is None:
        return []

    if max_hints == 0:
        return []
    if max_hints == 1:
        return [actual_gtp]

    pool_mode = _coerce_candidate_pool(candidate_pool)
    threshold = _coerce_near_threshold(near_threshold_points)

    if not node.analysis_exists or node.root_visits < min_visits:
        return [actual_gtp]

    candidates = node.candidate_moves
    slots_for_kata = max_hints - 1

    if pool_mode == KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL:
        actual_points = _get_actual_points_lost(node, actual_gtp, candidates)
        kata_gtps = _select_near_actual_options(
            candidates,
            actual_gtp,
            actual_points,
            threshold,
            slots_for_kata,
        )
    else:
        kata_gtps = _select_top_kata_options(candidates, actual_gtp, slots_for_kata)

    return [actual_gtp, *kata_gtps[:slots_for_kata]]


# =============================================================================
# Session Class
# =============================================================================


class KifunarabeSession:
    """Session manager for kifunarabe (棋譜並べ).

    Records one ``KifunarabeGuessResult`` per position the user visits. The
    session is purely additive: callers decide what counts as a "guess" by
    invoking :meth:`record_guess` (correct) or :meth:`record_auto_advance`.
    """

    def __init__(
        self,
        config: KifunarabeConfig | None = None,
        critical_3_move_numbers: list[int] | None = None,
    ):
        """Initialize a session.

        Args:
            config: User-selected configuration. Defaults to a fresh
                ``KifunarabeConfig()``.
            critical_3_move_numbers: Phase 179-B1. Move numbers that are
                part of the Critical 3 set for this game. Used to track
                ``critical_3_correct/wrong/skipped`` counters so the
                summary popup and the history JSON can report hit rate.
                ``None`` or empty list = no Critical 3 tracking.
        """
        self.config: KifunarabeConfig = config or KifunarabeConfig()
        self.results: list[KifunarabeGuessResult] = []
        self.started_at: datetime = datetime.now()
        self.ended_at: datetime | None = None
        # Phase 179-B1/B2
        self.critical_3_set: set[int] = set(critical_3_move_numbers or [])
        self.critical_3_correct: int = 0
        self.critical_3_wrong: int = 0
        self.critical_3_skipped: int = 0

    # -- critical_3 helper ----------------------------------------------------

    def _is_critical_3(self, move_number: int) -> bool:
        """Phase 179-B2: True if ``move_number`` is part of the Critical 3 set."""
        return move_number in self.critical_3_set

    # -- state ----------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    def end(self, max_moves_reached: bool = False) -> None:
        """Mark the session as ended. Idempotent.

        Args:
            max_moves_reached: Set to True when the session ended because
                the configured ``max_moves`` cap was hit (so the summary
                popup can show "ended at the move limit"). ``False`` (the
                default) leaves the flag alone, meaning callers should not
                invoke ``end()`` themselves unless the session truly ended.
        """
        if self.is_active:
            self.ended_at = datetime.now()
        # The flag is sticky: once True it stays True, even after ``end()``
        # is called repeatedly. This lets callers upgrade an already-ended
        # session to a "stopped at the move limit" summary if they learn
        # later that the cap was hit.
        if max_moves_reached:
            self._max_moves_reached_flag = True

    @property
    def max_moves_reached(self) -> bool:
        """True iff the session ended because ``max_moves`` was hit."""
        return getattr(self, "_max_moves_reached_flag", False)

    # -- recording ------------------------------------------------------------

    def _max_moves_exceeded(self) -> bool:
        """Whether ``config.max_moves`` user-actionable visits have been reached.

        Phase 180-A: counts only ``CORRECT`` and ``AUTO_ADVANCE`` outcomes.
        The previous ``len(self.results) >= max_moves`` counted every
        click, which meant 50 wrong clicks on the same empty point could
        end the session without the user having visited 50 game
        positions. WRONG_GUESS is still recorded in ``self.results`` for
        accurate summary stats but does not contribute to the cap.

        Returns False when ``max_moves == 0`` (no limit) or when the
        session is not active.
        """
        if self.config is None:
            return False
        if self.config.max_moves <= 0:
            return False
        actionable = sum(1 for r in self.results if r.outcome in (GuessOutcome.CORRECT, GuessOutcome.AUTO_ADVANCE))
        return actionable >= self.config.max_moves

    def _finalize_at_limit(self) -> None:
        """End the session via ``end()`` only when the move cap was hit.

        Call sites do not need to check the limit themselves; the only
        side effect (calling ``end(max_moves_reached=True)``) happens
        here when ``_max_moves_exceeded()`` returns True.
        """
        if not self._max_moves_exceeded():
            return
        with contextlib.suppress(Exception):
            self.end(max_moves_reached=True)

    @staticmethod
    def _validate_move_number(move_number: Any, *, method: str) -> int:
        """Phase 249-α: validate ``move_number`` for ``record_*`` callers.

        The position number must be a non-negative integer. ``0`` is
        the root position (no children played yet); ``1+`` is a real
        move. Anything else (``None``, negative, non-int) is a
        programming error and must not silently corrupt the results
        list.

        Phase 249-hotfix: this validator and its 3 callers were lost
        during the γ rebase. Restored so ``record_guess`` /
        ``record_auto_advance`` / ``record_skipped_no_move`` reject
        bad inputs with the documented ``TypeError`` / ``ValueError``
        contract.

        Args:
            move_number: The candidate value to validate.
            method: The calling method name (for the error message).

        Returns:
            The validated integer.

        Raises:
            TypeError: ``move_number`` is not an int.
            ValueError: ``move_number`` is negative.
        """
        if not isinstance(move_number, int) or isinstance(move_number, bool):
            raise TypeError(
                f"KifunarabeSession.{method}: move_number must be int, "
                f"got {type(move_number).__name__}: {move_number!r}"
            )
        if move_number < 0:
            raise ValueError(f"KifunarabeSession.{method}: move_number must be >= 0, got {move_number}")
        return move_number

    def record_guess(
        self,
        move_number: int,
        expected_gtp: str | None,
        guessed_gtp: str | None,
        hints_shown: int = 0,
    ) -> KifunarabeGuessResult:
        """Record a guessed position.

        Whether the guess was correct is determined by comparing ``guessed_gtp``
        to ``expected_gtp`` (a string-compare of GTP coordinates is sufficient
        because both come from the same ``Move.gtp()`` path).

        Args:
            move_number: Tree depth (1-indexed) of the position.
            expected_gtp: GTP coordinate of the recorded move, or None.
            guessed_gtp: GTP coordinate the user chose.
            hints_shown: Number of hint markers visible.

        Returns:
            The recorded result.
        """
        move_number = self._validate_move_number(move_number, method="record_guess")
        correct = expected_gtp is not None and guessed_gtp is not None and expected_gtp.upper() == guessed_gtp.upper()
        # A guessed-but-wrong click is a "failure" distinct from "skip":
        # the user did participate. ``SKIPPED`` is reserved for positions
        # that were neither guessed nor auto-advanced (end of tree, etc.).
        if correct:
            outcome = GuessOutcome.CORRECT
        elif guessed_gtp is not None:
            outcome = GuessOutcome.WRONG_GUESS
        else:
            outcome = GuessOutcome.SKIPPED
        result = KifunarabeGuessResult(
            move_number=move_number,
            expected_gtp=expected_gtp,
            guessed_gtp=guessed_gtp,
            outcome=outcome,
            hints_shown=hints_shown,
        )
        self.results.append(result)
        _log.debug(
            "Kifunarabe record move %d: expected=%s guessed=%s hints=%d -> %s",
            move_number,
            expected_gtp,
            guessed_gtp,
            hints_shown,
            result.outcome.value,
        )
        # Phase 179-B2: aggregate Critical 3 counters when applicable.
        if self._is_critical_3(move_number):
            if outcome == GuessOutcome.CORRECT:
                self.critical_3_correct += 1
            elif outcome == GuessOutcome.WRONG_GUESS:
                self.critical_3_wrong += 1
            else:
                self.critical_3_skipped += 1
        self._finalize_at_limit()
        return result

    def record_auto_advance(self, move_number: int) -> KifunarabeGuessResult:
        """Record an auto-advanced (skipped) position.

        Args:
            move_number: Tree depth (1-indexed) of the skipped position.

        Returns:
            The recorded result.
        """
        move_number = self._validate_move_number(move_number, method="record_auto_advance")
        result = KifunarabeGuessResult(
            move_number=move_number,
            expected_gtp=None,
            guessed_gtp=None,
            outcome=GuessOutcome.AUTO_ADVANCE,
        )
        self.results.append(result)
        # Phase 179-B2: auto-advance counts as "skipped" against the
        # Critical 3 set because the user did not actively guess.
        if self._is_critical_3(move_number):
            self.critical_3_skipped += 1
        self._finalize_at_limit()
        return result

    def record_skipped_no_move(self, move_number: int) -> KifunarabeGuessResult:
        """Record a position with no expected continuation (end of game tree).

        Args:
            move_number: Tree depth (1-indexed) of the position.

        Returns:
            The recorded result.
        """
        move_number = self._validate_move_number(move_number, method="record_skipped_no_move")
        result = KifunarabeGuessResult(
            move_number=move_number,
            expected_gtp=None,
            guessed_gtp=None,
            outcome=GuessOutcome.SKIPPED,
        )
        self.results.append(result)
        # Phase 179-B2: end-of-tree skip counts as skipped against Critical 3.
        if self._is_critical_3(move_number):
            self.critical_3_skipped += 1
        return result

    # -- summary --------------------------------------------------------------

    def get_summary(self) -> KifunarabeSummary:
        """Aggregate the recorded results into a :class:`KifunarabeSummary`.

        Phase 179-B2: also forwards the Critical 3 counters so the summary
        popup and history JSON can report the Critical 3 hit rate.
        """
        total = len(self.results)
        correct = sum(1 for r in self.results if r.outcome == GuessOutcome.CORRECT)
        wrong = sum(1 for r in self.results if r.outcome == GuessOutcome.WRONG_GUESS)
        auto = sum(1 for r in self.results if r.outcome == GuessOutcome.AUTO_ADVANCE)
        skipped = sum(1 for r in self.results if r.outcome == GuessOutcome.SKIPPED)
        return KifunarabeSummary(
            total_positions=total,
            correct_count=correct,
            wrong_count=wrong,
            auto_advance_count=auto,
            skipped_count=skipped,
            max_moves_reached=self.max_moves_reached,
            critical_3_total=len(self.critical_3_set),
            critical_3_correct=self.critical_3_correct,
            critical_3_wrong=self.critical_3_wrong,
            critical_3_skipped=self.critical_3_skipped,
        )

    def clear(self) -> None:
        """Reset session state (keeps the current config)."""
        self.results.clear()
        self.started_at = datetime.now()
        self.ended_at = None
        self._max_moves_reached_flag = False
        # Phase 179-B2: counters reset along with results.
        self.critical_3_correct = 0
        self.critical_3_wrong = 0
        self.critical_3_skipped = 0


# =============================================================================
# Public judge helper
# =============================================================================


def evaluate_guess(coords: tuple[int, int], node: "GameNode") -> bool | None:
    """Decide whether ``coords`` match the recorded next move on ``node``.

    This is the small helper that the GUI click handler calls. It centralizes
    the rule "match the actual game move". For pass moves it always returns
    False because there is no board coordinate for the user to click.

    Args:
        coords: Board coordinates (col, row) from the user's click.
        node: Current GameNode.

    Returns:
        True if the guess matches the recorded next move; False if the user
        guessed something different; None if the node has no continuation
        (e.g. end of game).
    """
    expected = _expected_move_gtp(node)
    if expected is None:
        return None
    return _coords_equal_gtp(coords, expected, node)


# =============================================================================
# Phase 179-B1: Critical 3 helper
# =============================================================================


def get_critical_3_move_numbers(
    game: Any,
    level: str = "normal",
) -> list[int]:
    """Return the union of move numbers in the Critical 3 set for both players.

    Phase 179-B1: avoids building a full ``KarteContext`` by calling
    ``select_critical_moves`` directly with ``player_filter="B"`` and
    ``player_filter="W"`` and merging the two ``max_moves=3`` lists.

    Returns:
        Sorted list of unique move numbers (max 6 entries: 3 per player).
        Returns ``[]`` if the game lacks analysis or any exception occurs.
    """
    if game is None or getattr(game, "current_node", None) is None:
        return []
    try:
        from katrain.core.analysis.critical_moves import select_critical_moves
    except ImportError:
        return []
    moves: set[int] = set()
    for player in (SIDE_BLACK, SIDE_WHITE):
        try:
            critical = select_critical_moves(
                game,
                max_moves=CRITICAL_3_PER_PLAYER,
                lang="ja",
                level=level,
                player_filter=player,
            )
        except Exception:
            continue
        for cm in critical:
            n = getattr(cm, "move_number", None)
            if isinstance(n, int):
                moves.add(n)
    return sorted(moves)
