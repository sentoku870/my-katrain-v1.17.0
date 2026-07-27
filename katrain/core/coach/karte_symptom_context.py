"""Phase 215 / 216 / 217 / 245: Symptom context and detection helpers.

Builds a ``SymptomContext`` from a Karte JSON and maps weakness /
streak / aggregate fields to ``SymptomId`` values. Extracted from
``katrain.coach.karte_detector`` so that ``karte_detector`` can focus
on the top-level :func:`detect_symptoms_from_karte` orchestrator.

Modules in this package:

- :mod:`katrain.coach.karte_extractors` — pure statistics (this file
  reads from it via the public ``extract_*`` API)
- :mod:`katrain.coach.karte_symptom_context` (this file) — builds a
  ``SymptomContext`` and per-symptom-id mappings
- :mod:`katrain.coach.karte_detector` — runs the full detection chain

The functions in this module are still pure / Kivy-free and only
import from :mod:`katrain.core.coach.symptom_index`,
:mod:`katrain.core.analysis.meaning_tags`, and
:mod:`katrain.core.beginner.models`.
"""

from __future__ import annotations

from typing import Any

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.beginner.models import HintCategory
from katrain.core.coach.karte_extractors import (
    extract_avg_points_lost,
    extract_avg_streak_loss,
    extract_consecutive_loss_run,
    extract_game_count,
    extract_good_move_count,
    extract_longest_streak,
    extract_max_overall_difficulty,
    extract_max_score_stdev,
    extract_streak_count,
    extract_total_streak_loss,
    extract_weakness_concentration,
    extract_winrate_scorelead_correlation,
    extract_winrate_scorelead_pairs,
)
from katrain.core.coach.symptom_index import SymptomContext, SymptomId

# --- Context builder ---


def _collect_meaning_tags(karte: dict[str, Any]) -> tuple[MeaningTagId, ...]:
    """Collect all MeaningTagId values present in important_moves.

    Dual-read (2026-07 fix): the real Karte stores the tag under
    ``primary_tag`` (legacy fallback: ``meaning_tag_id``).
    """
    tags: list[MeaningTagId] = []
    seen: set[MeaningTagId] = set()
    for move in karte.get("important_moves", []) or []:
        tag_str = move.get("primary_tag") or move.get("meaning_tag_id")
        if not tag_str:
            continue
        # Match by enum value (string)
        for tag in MeaningTagId:
            if tag.value == tag_str and tag not in seen:
                tags.append(tag)
                seen.add(tag)
    return tuple(tags)


def _collect_hint_categories(karte: dict[str, Any]) -> tuple[HintCategory, ...]:
    """Infer HintCategory values from karte content.

    Currently uses heuristic on mistake_categories + tags. Phase 215 keeps
    this lightweight — a full hint detector would need a GameNode.
    """
    cats: list[HintCategory] = []
    seen: set[HintCategory] = set()

    moves = karte.get("important_moves", []) or []
    for m in moves:
        # Dual-read (2026-07 fix): real Karte uses ``mistake_type``
        # (legacy fallback: ``mistake_category`` / ``category``).
        cat = m.get("mistake_type") or m.get("mistake_category") or m.get("category")
        if not cat:
            continue
        cat_str = str(cat).lower()
        # Map mistake category string → HintCategory
        if "blunder" in cat_str:
            for h in (HintCategory.MISTAKE_BLUNDER,):
                if h not in seen:
                    cats.append(h)
                    seen.add(h)
        elif "mistake" in cat_str:
            for h in (HintCategory.MISTAKE_MISTAKE,):
                if h not in seen:
                    cats.append(h)
                    seen.add(h)

    # also: heavy / cut / low_liberties tag → HintCategory
    tags = _collect_meaning_tags(karte)
    tag_to_hint: dict[str, HintCategory] = {
        # 2026-07: capture_race_loss used to map to LOW_LIBERTIES, which
        # had no consumer detector — it was a silent orphan. The
        # CAPTURE_OVERSIGHT detector requires MISSED_CAPTURE, so we now
        # remap this tag directly to the correct hint category. No other
        # symptom_index entry references LOW_LIBERTIES, so this is safe.
        "capture_race_loss": HintCategory.MISSED_CAPTURE,
        "life_death_error": HintCategory.SELF_CAPTURE_LIKE,
        "shape_mistake": HintCategory.BAD_SHAPE,
        "overplay": HintCategory.HEAVY_GROUP,
        "connection_miss": HintCategory.MISSED_DEFENSE,
        "endgame_slip": HintCategory.URGENT_VS_BIG,
    }
    for tag in tags:
        hint: HintCategory | None = tag_to_hint.get(tag.value)
        if hint is not None and hint not in seen:
            cats.append(hint)
            seen.add(hint)

    return tuple(cats)


def _is_endgame_karte(karte: dict[str, Any]) -> bool:
    """Heuristic: True if any important move is past 200 (19x19 endgame)."""
    moves = karte.get("important_moves", []) or []
    for m in moves:
        n = m.get("move_number")
        if isinstance(n, int) and n > 200:
            return True
    return False


def _move_number_range(karte: dict[str, Any]) -> tuple[int | None, int | None]:
    """Return ``(min, max)`` move numbers across important_moves.

    Used by :func:`_infer_current_phase` to pick a dominant phase even
    when the per-move ``move_number`` of the aggregate context is
    unknown.
    """
    moves = karte.get("important_moves", []) or []
    nums: list[int] = []
    for m in moves:
        n = m.get("move_number")
        if isinstance(n, int) and n > 0:
            nums.append(n)
    if not nums:
        return (None, None)
    return (min(nums), max(nums))


def _infer_current_phase(karte: dict[str, Any], board_size: int = 19) -> str:
    """Phase 226-F (F-A): infer the dominant phase from important_moves.

    Karte contexts don't have a single ``move_number`` to feed into
    :meth:`SymptomContext.is_phase`. Instead we use the *range* of
    move numbers seen in the karte's important_moves:

    - **opening-dominant**: any move_number ≤ 50, and at least 30 % of
      the mistakes are in the opening range.
    - **middle-dominant**: dominant range is 50 < n ≤ 200 (or roughly
      midgame for smaller boards).
    - **endgame-dominant**: at least one move > 200, and at least
      30 % of mistakes are past the middle/end boundary.
    - **unknown**: no move numbers available.

    The thresholds scale linearly with ``board_size`` for non-19 boards
    so the phase boundary stays at roughly the same fraction of the
    total game length.
    """
    lo, hi = _move_number_range(karte)
    if lo is None or hi is None:
        return "unknown"

    scale = board_size / 19 if board_size else 1.0
    opening_max = max(15, int(50 * scale))
    middle_max = max(60, int(200 * scale))

    moves = karte.get("important_moves", []) or []
    nums = [m.get("move_number") for m in moves]
    nums = [n for n in nums if isinstance(n, int) and n > 0]
    if not nums:
        return "unknown"

    opening_n = sum(1 for n in nums if n <= opening_max)
    endgame_n = sum(1 for n in nums if n > middle_max)
    total = len(nums)

    opening_share = opening_n / total
    endgame_share = endgame_n / total

    # Prefer the *most concentrated* phase to avoid the all-opening
    # case where a single early mistake dominates.
    if endgame_share >= 0.3:
        return "endgame"
    if opening_share >= 0.3 and hi <= opening_max:
        return "opening"
    if opening_share >= 0.5:
        return "opening"
    if lo > middle_max:
        return "endgame"
    # Default: if the mistakes span the middle, that's a middle-dominant
    # karte.
    return "middle"


def _board_size(karte: dict[str, Any]) -> int:
    """Return board size from karte meta (default 19)."""
    meta = karte.get("meta", {}) or {}
    bs = meta.get("board_size")
    if isinstance(bs, int) and bs > 0:
        return bs
    if isinstance(bs, (list, tuple)) and bs:
        try:
            return int(bs[0])
        except (TypeError, ValueError):
            pass
    return 19


# --- Public API ---


def build_symptom_context_from_karte(
    karte: dict[str, Any],
    *,
    player_color: str | None = None,
) -> SymptomContext:
    """Build a SymptomContext snapshot from a Karte JSON.

    Most fields are populated from aggregate karte data; per-move
    detail is intentionally approximated since one SymptomContext is
    shared across all moves for prompt-generation purposes.

    Phase 226-F (F-A): ``current_phase`` is derived from the move
    number range of ``important_moves`` so the phase-gated detectors
    (FIRST_MOVE_CONFUSION, TOO_MANY_CHOICES, OVERCONCENTRATION,
    POST_JOSEKI_DIRECTION, ATTACK_WITH_PURPOSE) can fire against
    karte contexts.

    PR-04a (H5): ``player_color`` (``"black"`` / ``"white"`` /
    ``None``) scopes streak-derived fields (longest_streak /
    total_streak_loss / streak_count / avg_streak_loss) to one
    colour. ``None`` keeps the legacy "both colours" behaviour.
    """
    board_size = _board_size(karte)
    avg_points = extract_avg_points_lost(karte)
    return SymptomContext(
        # PR-04b (H6): ``points_lost`` / ``winrate_lost`` are documented
        # as "current move's pointsLost / winrate drop" (SymptomContext
        # docstring). For the Karte-derived context there is no
        # current move, so set them to ``None``. The game-level average
        # belongs in ``avg_points_lost`` (already populated below) and
        # was being injected into the per-move field by mistake, which
        # made the ATARI_BLINDNESS / EVALUATION_ERRORS thresholds
        # effectively dead (they expect a per-move number).
        points_lost=None,
        winrate_lost=None,
        # Per-move fields default to None (Phase 215 uses aggregates).
        move_number=None,
        good_move_count=extract_good_move_count(karte),
        near_move_count=0,
        overall_difficulty=extract_max_overall_difficulty(karte),
        score_stdev=extract_max_score_stdev(karte),
        is_endgame=_is_endgame_karte(karte),
        meaning_tag_ids=_collect_meaning_tags(karte),
        hint_categories=_collect_hint_categories(karte),
        avg_points_lost=avg_points,
        game_count=extract_game_count(karte),
        weakness_concentration=extract_weakness_concentration(karte),
        board_size=board_size,
        current_phase=_infer_current_phase(karte, board_size=board_size),
        # PR-04a: streak-derived fields scoped per colour.
        longest_streak=extract_longest_streak(karte, player_color=player_color),
        total_streak_loss=extract_total_streak_loss(karte, player_color=player_color),
        streak_count=extract_streak_count(karte, player_color=player_color),
        avg_streak_loss=extract_avg_streak_loss(karte, player_color=player_color),
        player_color=player_color,
    )


def _symptom_ids_from_weakness_categories(
    karte: dict[str, Any],
    *,
    player_color: str | None = None,
) -> tuple[SymptomId, ...]:
    """Map weakness[*].category strings to SymptomId values.

    Note (2026-07): the real Karte export writes MistakeCategory values
    ("BLUNDER" / "MISTAKE" / "INACCURACY") into ``category``, which do
    not correspond to any SymptomId — so this mapping yields nothing on
    real kartes. Category-level detection instead flows through the
    meaning-tag path (:func:`_collect_meaning_tags`). This function is
    kept for legacy fixtures that stored SymptomId.value strings in the
    category field.

    PR-04a (H5): ``player_color`` scopes the iteration to one colour.
    """
    out: list[SymptomId] = []
    seen: set[SymptomId] = set()
    colors = (player_color,) if player_color in ("black", "white") else ("black", "white")
    for color in colors:
        for w in karte.get("weaknesses", {}).get(color, []) or []:
            cat = str(w.get("category", "")).lower()
            if not cat:
                continue
            for sid in SymptomId:
                if sid.value == cat and sid not in seen:
                    out.append(sid)
                    seen.add(sid)
    return tuple(out)


def _symptom_ids_from_streaks(
    karte: dict[str, Any],
    *,
    player_color: str | None = None,
) -> tuple[SymptomId, ...]:
    """Phase 216: detect streak-based symptoms from karte.mistake_streaks
    and loss_progression.

    Targets the four "新規" symptoms from Phase 209 §4.1 that need
    consecutive-pattern detection:

    - SMALL_MOVE_ADDICTION: many small streaks → midgame leakage
    - OVERFIGHT: longest streak >= 3 → 連続攻撃でミスを重ねる
    - TILT_DISCOURAGEMENT: long consecutive-loss bucket run + streak loss
    - TILT_CHAIN: large total_streak_loss within a short window

    Each detection is heuristic — actual thresholds are tentative and
    should be calibrated against golden games (Phase 217 future work).
    """
    longest = extract_longest_streak(karte, player_color=player_color)
    total_loss = extract_total_streak_loss(karte, player_color=player_color)
    streak_count = extract_streak_count(karte, player_color=player_color)
    loss_run = extract_consecutive_loss_run(karte)
    avg_streak = extract_avg_streak_loss(karte, player_color=player_color)

    fired: list[SymptomId] = []

    # OVERFIGHT: 3手以上連続の MISTAKE / BLUNDER (Phase 209 §4.1 row 18)
    if longest >= 3:
        fired.append(SymptomId.OVERFIGHT)

    # SMALL_MOVE_ADDICTION: midgame で streak が 5 個以上 (Phase 209 §4.1 row 11)
    if streak_count >= 5:
        fired.append(SymptomId.SMALL_MOVE_ADDICTION)

    # TILT_CHAIN: total_streak_loss が 15 目以上 + loss_run が 4 bucket 以上
    if total_loss >= 15.0 and loss_run >= 4:
        fired.append(SymptomId.TILT_CHAIN)

    # TILT_DISCOURAGEMENT: loss_run 5 bucket (50手相当) 連続 + 平均 streak_loss 高い
    if loss_run >= 5 and avg_streak >= 3.0:
        fired.append(SymptomId.TILT_DISCOURAGEMENT)

    return tuple(fired)


def detect_position_evaluation(
    karte: dict[str, Any],
    *,
    abs_correlation_threshold: float = 0.5,
    min_pairs: int = 8,
) -> bool:
    """Phase 245: detect POSITION_EVALUATION via winrate/scoreLead correlation.

    局面評価が正確なら winrate と scoreLead は強い正相関（r > 0.5）。
    局面評価の歪み = 大きなビハインドなのに winrate が高い、またはその逆 →
    |r| < 0.5。強歪み = r < 0 まで反転。

    Args:
        karte: The Karte JSON dict.
        abs_correlation_threshold: |r| below this triggers detection.
            Default 0.5 is conservative — the symptom fires only when
            the user's mental model is clearly decoupled from the
            numeric reality. Phase 246 will tune this against a
            golden-game dataset.
        min_pairs: Minimum number of (winrate, scoreLead) pairs
            required to compute a stable correlation. Below this the
            sample is too small and we return False to avoid noisy
            detections.

    Returns:
        True when the symptom should fire.
    """
    pairs = extract_winrate_scorelead_pairs(karte)
    if len(pairs) < min_pairs:
        return False
    corr = extract_winrate_scorelead_correlation(karte)
    if corr is None:
        return False
    return abs(corr) < abs_correlation_threshold


def _symptom_ids_from_aggregate_patterns(karte: dict[str, Any]) -> tuple[SymptomId, ...]:
    """Phase 217 + Phase 245: aggregate-pattern detection across the game.

    Returns symptoms whose detector requires whole-game analysis rather
    than per-move heuristics. Currently:

    - POSITION_EVALUATION (Phase 245): winrate/scoreLead correlation
      below threshold. Previously a placeholder (Phase 217); now wired
      to :func:`detect_position_evaluation`. Symptom is flipped to
      ``auto_detected=True`` in symptom_index.py.
    """
    fired: list[SymptomId] = []
    if detect_position_evaluation(karte):
        fired.append(SymptomId.POSITION_EVALUATION)
    return tuple(fired)


__all__ = [
    "build_symptom_context_from_karte",
    "detect_position_evaluation",
]
