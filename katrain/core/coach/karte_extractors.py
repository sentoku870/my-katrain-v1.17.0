"""Phase 215 / 216 / 217 / 245: Karte JSON statistics extractors.

Pure / Kivy-free functions that read fields from a Karte JSON dict
and return numeric summaries. Extracted from
``katrain.coach.karte_detector`` so that the detector module itself
focuses on symptom detection rather than statistics gathering.

Each ``extract_*`` function reads a specific slice of the Karte JSON
and returns a primitive (``float`` / ``int`` / ``list`` / ``tuple``).
Two private helpers (``_all_streaks``, ``_safe_pearson``) provide
shared aggregation primitives.

This module is intentionally import-light: only standard library
types and ``typing.Any``. Higher-level orchestration lives in
:mod:`katrain.coach.karte_symptom_context` and
:mod:`katrain.coach.karte_detector`.
"""

from __future__ import annotations

from typing import Any

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
    """Average winrateLost across all important moves (None when no data)."""
    moves = karte.get("important_moves", []) or []
    losses: list[float] = []
    for m in moves:
        v = m.get("winrate_lost")
        if isinstance(v, (int, float)):
            losses.append(float(v))
    return sum(losses) / len(losses) if losses else None


def extract_max_winrate_drop(karte: dict[str, Any]) -> float | None:
    """Largest single winrate drop across important moves (None when no data)."""
    moves = karte.get("important_moves", []) or []
    values: list[float] = []
    for m in moves:
        v = m.get("winrate_lost")
        if isinstance(v, (int, float)):
            values.append(float(v))
    return max(values) if values else None


def extract_max_score_stdev(karte: dict[str, Any]) -> float | None:
    """Largest KataGo scoreStdev seen on any important move (None when no data)."""
    moves = karte.get("important_moves", []) or []
    values: list[float] = []
    for m in moves:
        v = m.get("score_stdev")
        if isinstance(v, (int, float)):
            values.append(float(v))
    return max(values) if values else None


def extract_max_overall_difficulty(karte: dict[str, Any]) -> float | None:
    """Largest overall_difficulty reported on any important move (None when no data)."""
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
        if isinstance(v, bool):
            # Guard against ``bool`` (subclass of int) being treated as a
            # numeric loss. We never expect this in practice but the
            # mypy strict mode rejects ``float(True|False)`` otherwise.
            continue
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


__all__ = [
    "extract_avg_points_lost",
    "extract_avg_streak_loss",
    "extract_avg_winrate_lost",
    "extract_consecutive_loss_run",
    "extract_critical_move_count",
    "extract_game_count",
    "extract_good_move_count",
    "extract_longest_streak",
    "extract_max_overall_difficulty",
    "extract_max_score_stdev",
    "extract_max_winrate_drop",
    "extract_streak_count",
    "extract_total_streak_loss",
    "extract_weakness_concentration",
    "extract_winrate_scorelead_correlation",
    "extract_winrate_scorelead_pairs",
]
