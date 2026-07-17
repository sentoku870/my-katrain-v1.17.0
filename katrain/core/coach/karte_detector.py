"""Phase 215: Karte-aware symptom detection.

Builds a SymptomContext from a real Karte JSON so that
``detect_auto_symptoms`` can be run end-to-end against actual data.

This module bridges the gap between:
- The aggregate Karte JSON produced by ``json_export.build_karte_json``
  (top-level weaknesses / mistake_streaks / critical_3 / reason_tags)
- The per-move SymptomContext the symptom_index detectors expect

Functions:
- ``build_symptom_context_from_karte(karte)`` → SymptomContext
- ``detect_symptoms_from_karte(karte)`` → tuple[SymptomId, ...]
- ``extract_avg_points_lost(karte)`` → float | None
- ``extract_weakness_concentration(karte)`` → float | None

All functions are pure / Kivy-free.

Note: Phase 215 deliberately avoids modifying the Karte JSON schema. It
reads only existing fields. New fields (e.g. time data) would require
Phase 211.5 (schema bump).
"""

from __future__ import annotations

from typing import Any

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.beginner.models import HintCategory
from katrain.core.coach.symptom_index import (
    SymptomContext,
    SymptomId,
    detect_auto_symptoms,
)

# --- Aggregators ---


def extract_avg_points_lost(karte: dict[str, Any]) -> float | None:
    """Compute the average pointsLost across all important moves.

    Returns None when no important moves have a numeric points_lost.
    """
    moves = karte.get("important_moves", []) or []
    losses: list[float] = []
    for m in moves:
        v = m.get("points_lost")
        if isinstance(v, (int, float)):
            losses.append(float(v))
    return sum(losses) / len(losses) if losses else None


def extract_avg_winrate_lost(karte: dict[str, Any]) -> float | None:
    """Compute the average winrate_lost across all important moves.

    Returns None when no moves have a numeric winrate_lost.
    """
    moves = karte.get("important_moves", []) or []
    losses: list[float] = []
    for m in moves:
        v = m.get("winrate_lost")
        if isinstance(v, (int, float)):
            losses.append(float(v))
    return sum(losses) / len(losses) if losses else None


def extract_max_winrate_drop(karte: dict[str, Any]) -> float | None:
    """Return the maximum winrate drop observed (0-1 scale).

    Returns None when no winrate_lost values are available.
    """
    moves = karte.get("important_moves", []) or []
    drops: list[float] = []
    for m in moves:
        v = m.get("winrate_lost")
        if isinstance(v, (int, float)):
            drops.append(float(v))
    return max(drops) if drops else None


def extract_max_score_stdev(karte: dict[str, Any]) -> float | None:
    """Return the maximum scoreStdev across important moves."""
    moves = karte.get("important_moves", []) or []
    values: list[float] = []
    for m in moves:
        v = m.get("score_stdev")
        if isinstance(v, (int, float)):
            values.append(float(v))
    return max(values) if values else None


def extract_max_overall_difficulty(karte: dict[str, Any]) -> float | None:
    """Return the maximum overall difficulty across important moves."""
    moves = karte.get("important_moves", []) or []
    values: list[float] = []
    for m in moves:
        v = m.get("overall_difficulty")
        if isinstance(v, (int, float)):
            values.append(float(v))
    return max(values) if values else None


def extract_good_move_count(karte: dict[str, Any]) -> int:
    """Return the maximum good_move_count across important moves.

    Used by Freedom-detector family (Phase 179).
    """
    moves = karte.get("important_moves", []) or []
    counts: list[int] = []
    for m in moves:
        v = m.get("good_move_count")
        if isinstance(v, int):
            counts.append(v)
    return max(counts) if counts else 0


# --- Phase 216: streak / loss-run aggregators ---


def _all_streaks(karte: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten mistake_streaks into a single list (both colours)."""
    out: list[dict[str, Any]] = []
    streaks = karte.get("mistake_streaks", {}) or {}
    for color in ("black", "white"):
        for s in streaks.get(color, []) or []:
            if isinstance(s, dict):
                out.append(s)
    return out


def extract_longest_streak(karte: dict[str, Any]) -> int:
    """Return the longest consecutive-mistake streak (in moves) across all colours.

    A streak is a sequence of consecutive mistakes for the same player.
    Used by OVERFIGHT detection (Phase 209 §4.1 row 18, 34).

    Returns 0 when no streaks present.
    """
    counts: list[int] = []
    for s in _all_streaks(karte):
        v = s.get("move_count")
        if isinstance(v, int):
            counts.append(v)
    return max(counts) if counts else 0


def extract_total_streak_loss(karte: dict[str, Any]) -> float:
    """Sum of total_loss across all mistake streaks.

    Used by TILT_CHAIN detection — large accumulated streak loss indicates
    increasing mistakes within a losing pattern.
    """
    total = 0.0
    for s in _all_streaks(karte):
        v = s.get("total_loss")
        if isinstance(v, (int, float)):
            total += float(v)
    return total


def extract_streak_count(karte: dict[str, Any]) -> int:
    """Return the total number of mistake streaks detected.

    Used by SMALL_MOVE_ADDICTION (Phase 209 §4.1 row 11) — many small streaks
    suggest a player is leaking points throughout the midgame.
    """
    return len(_all_streaks(karte))


def extract_consecutive_loss_run(karte: dict[str, Any]) -> int:
    """Return the longest run of consecutive-loss buckets from loss_progression.

    Phase 149 introduced ``loss_progression`` with bucket_size=10. We treat
    a bucket as "consecutive loss" if ``mistake_count > 0``. The longest
    such run is a coarse proxy for "連敗" (losing streak).

    Returns 0 when no loss_progression data is present.
    """
    progression = karte.get("loss_progression", []) or []
    if not progression:
        return 0
    longest = 0
    current = 0
    for bucket in progression:
        mc = bucket.get("mistake_count")
        if isinstance(mc, int) and mc > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def extract_avg_streak_loss(karte: dict[str, Any]) -> float:
    """Average total_loss across all streaks.

    Returns 0.0 when no streaks present.
    """
    losses: list[float] = []
    for s in _all_streaks(karte):
        raw_loss = s.get("total_loss")
        if isinstance(raw_loss, bool):
            # Guard against ``bool`` (subclass of int) being treated as a
            # numeric loss. We never expect this in practice but the
            # mypy strict mode rejects ``float(True|False)`` otherwise.
            continue
        if isinstance(raw_loss, (int, float)):
            losses.append(float(raw_loss))
    return sum(losses) / len(losses) if losses else 0.0


# --- Phase 217: aggregate pattern detection ---


def _safe_pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation between two equal-length sequences. Returns None on degenerate input."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    corr: float = cov / (var_x * var_y) ** 0.5
    return corr


def extract_winrate_scorelead_correlation(
    karte: dict[str, Any],
) -> float | None:
    """Pearson correlation between per-move winrate_lost and points_lost.

    For well-calibrated KataGo analysis these should track each other
    closely (correlation near -1.0: high winrate drop = high point loss).

    A weak correlation (|r| < 0.5) suggests the player's mental model
    of the game has a systematic disconnect between "this looks bad"
    (winrate signal) and "this loses points" (scoreLead signal) — the
    textbook POSITION_EVALUATION issue.

    Returns None when fewer than 2 numeric pairs are available.
    """
    moves = karte.get("important_moves", []) or []
    xs: list[float] = []
    ys: list[float] = []
    for m in moves:
        w = m.get("winrate_lost")
        p = m.get("points_lost")
        if isinstance(w, (int, float)) and isinstance(p, (int, float)):
            xs.append(float(w))
            ys.append(float(p))
    return _safe_pearson(xs, ys)


def extract_winrate_scorelead_pairs(karte: dict[str, Any]) -> list[tuple[float, float]]:
    """Return all numeric (winrate_lost, points_lost) pairs in move order.

    Useful for plotting or debugging. Empty when no numeric pairs.
    """
    moves = karte.get("important_moves", []) or []
    out: list[tuple[float, float]] = []
    for m in moves:
        w = m.get("winrate_lost")
        p = m.get("points_lost")
        if isinstance(w, (int, float)) and isinstance(p, (int, float)):
            out.append((float(w), float(p)))
    return out


def extract_critical_move_count(karte: dict[str, Any]) -> int:
    """Count critical / blunder moves in the karte.

    Phase 149-C-3 defines critical_3 section per player; we union those
    with any mistake_count from reason_tags_distribution.
    """
    critical_3 = karte.get("critical_3", {}) or {}
    reason_tags = karte.get("reason_tags_distribution", {}) or {}
    total = 0
    for color in ("black", "white"):
        c3 = critical_3.get(color, {}) or {}
        moves = c3.get("moves", []) if isinstance(c3, dict) else []
        total += len(moves) if isinstance(moves, list) else 0
        rt = reason_tags.get(color, {}) or {}
        if isinstance(rt, dict):
            total += int(rt.get("total_count", 0) or 0)
    return total


def extract_weakness_concentration(karte: dict[str, Any]) -> float | None:
    """Return the top weakness's share of total loss (Phase 149-C-3).

    Returns the ratio (top weakness loss / total player loss) for the
    most-affected player. None if data unavailable.
    """
    weaknesses = karte.get("weaknesses", {}) or {}
    meta = karte.get("weaknesses_meta", {}) or {}

    best_ratio: float | None = None
    for color in ("black", "white"):
        items = weaknesses.get(color, []) or []
        m = meta.get(color, {}) or {}
        total_loss = m.get("total_loss")
        if not total_loss:
            continue
        # Use top weakness's loss / total loss
        if items and isinstance(items[0], dict):
            top_loss = items[0].get("total_loss") or 0
            if total_loss > 0:
                ratio = top_loss / total_loss
                if best_ratio is None or ratio > best_ratio:
                    best_ratio = ratio
    return best_ratio


def extract_game_count(karte: dict[str, Any]) -> int | None:
    """Heuristic: number of games this karte summarises.

    For a single-game karte, returns 1. For a multi-game summary,
    inspects the meta. Returns None when unknown.
    """
    meta = karte.get("meta", {}) or {}
    if "game_count" in meta and isinstance(meta["game_count"], int):
        return int(meta["game_count"])
    # Single-game karte — game_count = 1
    if karte.get("schema_version"):
        return 1
    return None


# --- Context builder ---


def _collect_meaning_tags(karte: dict[str, Any]) -> tuple[MeaningTagId, ...]:
    """Collect all MeaningTagId values present in important_moves."""
    tags: list[MeaningTagId] = []
    seen: set[MeaningTagId] = set()
    for move in karte.get("important_moves", []) or []:
        tag_str = move.get("meaning_tag_id")
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
        cat = m.get("mistake_category") or m.get("category")
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
        "capture_race_loss": HintCategory.LOW_LIBERTIES,
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
    """
    board_size = _board_size(karte)
    return SymptomContext(
        points_lost=extract_avg_points_lost(karte),
        winrate_lost=extract_avg_winrate_lost(karte),
        # Per-move fields default to None (Phase 215 uses aggregates).
        move_number=None,
        good_move_count=extract_good_move_count(karte),
        near_move_count=0,
        overall_difficulty=extract_max_overall_difficulty(karte),
        score_stdev=extract_max_score_stdev(karte),
        is_endgame=_is_endgame_karte(karte),
        meaning_tag_ids=_collect_meaning_tags(karte),
        hint_categories=_collect_hint_categories(karte),
        avg_points_lost=extract_avg_points_lost(karte),
        game_count=extract_game_count(karte),
        weakness_concentration=extract_weakness_concentration(karte),
        board_size=board_size,
        current_phase=_infer_current_phase(karte, board_size=board_size),
    )


def _symptom_ids_from_weakness_categories(
    karte: dict[str, Any],
) -> tuple[SymptomId, ...]:
    """Map weakness[*].category strings to SymptomId values.

    The weakness aggregation in json_export writes SymptomId.value
    strings (e.g. "atari_blindness", "big_point_blindness") into the
    category field. We reverse-map them to the SymptomId enum.
    """
    out: list[SymptomId] = []
    seen: set[SymptomId] = set()
    for color in ("black", "white"):
        for w in karte.get("weaknesses", {}).get(color, []) or []:
            cat = str(w.get("category", "")).lower()
            if not cat:
                continue
            for sid in SymptomId:
                if sid.value == cat and sid not in seen:
                    out.append(sid)
                    seen.add(sid)
    return tuple(out)


def _symptom_ids_from_streaks(karte: dict[str, Any]) -> tuple[SymptomId, ...]:
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
    longest = extract_longest_streak(karte)
    total_loss = extract_total_streak_loss(karte)
    streak_count = extract_streak_count(karte)
    loss_run = extract_consecutive_loss_run(karte)
    avg_streak = extract_avg_streak_loss(karte)

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


def detect_symptoms_from_karte(
    karte: dict[str, Any],
) -> tuple[SymptomId, ...]:
    """Run auto-detection against the karte's derived SymptomContext.

    Returns the union of:
    (a) Symptoms fired by SymptomContext-based detectors (per-move heuristics)
    (b) Symptoms directly extracted from weakness[*].category
    (c) Streak-based symptoms from mistake_streaks + loss_progression (Phase 216)
    (d) Aggregate-pattern symptoms (Phase 217: POSITION_EVALUATION via
        winrate/scoreLead correlation)

    Order is the symptom-table order, which is stable across calls.
    """
    ctx = build_symptom_context_from_karte(karte)
    per_move = set(detect_auto_symptoms(ctx))
    from_categories = set(_symptom_ids_from_weakness_categories(karte))
    from_streaks = set(_symptom_ids_from_streaks(karte))
    from_aggregate = set(_symptom_ids_from_aggregate_patterns(karte))
    combined = per_move | from_categories | from_streaks | from_aggregate
    # Stable ordering by table order
    table_order = list(SymptomId)
    combined_sorted = tuple(sid for sid in table_order if sid in combined)
    return combined_sorted


__all__ = [
    "extract_avg_points_lost",
    "extract_avg_winrate_lost",
    "extract_max_winrate_drop",
    "extract_max_score_stdev",
    "extract_max_overall_difficulty",
    "extract_good_move_count",
    "extract_critical_move_count",
    "extract_weakness_concentration",
    "extract_game_count",
    "build_symptom_context_from_karte",
    "detect_symptoms_from_karte",
]
