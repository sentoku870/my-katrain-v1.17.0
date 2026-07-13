"""Phase B2: Position difficulty computation — IO & candidate helpers.

This module centralises the small utilities used to normalise KataGo
candidate lists and to inspect the analysis payload (root visits,
reliability). Public API composition lives in :mod:`katrain.core.analysis.difficulty.api`.

History: extracted from ``katrain.core.analysis.logic_difficulty``
(756 lines, Phase 144-C) in Phase B2.
"""

from __future__ import annotations

import logging
from typing import Any

from katrain.core.analysis.models import (
    DIFFICULTY_MIN_CANDIDATES,
    DIFFICULTY_MIN_VISITS,
)

_difficulty_logger = logging.getLogger("katrain.core.analysis.difficulty")


# =============================================================================
# Candidate normalisation
# =============================================================================


def normalize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """候補手リストを正規化（ソート + バリデーション）。

    order 欠損時は UNKNOWN（手番依存のソートを回避）。

    Args:
        candidates: KataGo moveInfos（未ソートの可能性あり）

    Returns:
        order フィールドでソート済みのリスト。
        - order がある → order でソート
        - order がない → None（UNKNOWN扱い）

    Note:
        scoreLead は BLACK 視点なので、WHITE 手番では降順が「最悪手順」になる。
        手番情報なしでは正しくソートできないため、order 欠損時は UNKNOWN 扱い。
    """
    if not candidates:
        return []

    # order フィールドの存在チェック
    has_order = all("order" in c for c in candidates)

    if has_order:
        # order でソート（0=最善）
        return sorted(candidates, key=lambda c: c.get("order", 999))

    # order がない場合は UNKNOWN（手番依存のソートを回避）
    return None


# =============================================================================
# Analysis payload extraction
# =============================================================================


def get_root_visits(analysis: dict[str, Any] | None) -> int | None:
    """analysis から root_visits を取得（複数キーに対応）。

    KaTrain/KataGo の複数フォーマットに対応。

    Args:
        analysis: GameNode.analysis（辞書または None）

    Returns:
        root_visits 値。取得できない場合は None。

    Note:
        優先順位:
        1. rootInfo.visits（KataGo 標準）
        2. root.visits（KaTrain 内部フォーマット）
        3. visits（直接参照、一部のカスタムフォーマット）
    """
    if not analysis:
        return None

    # Phase 186 followup: defensive coercion. ``analysis.get("root", {})``
    # only returns the default when the key is absent; if the key is
    # present but its value is explicitly ``None`` (which happens during
    # the very first KataGo query before the analysis payload is
    # populated, or on a node that was created but never queried),
    # ``"visits" in root`` raises ``TypeError: argument of type
    # 'NoneType' is not iterable``. The ``or {}`` makes both "missing"
    # and "present-but-null" behave as an empty mapping. The error was
    # observed in the wild during initial KataGo startup before
    # ``analyze`` finished, surfacing through Beginner Hints's
    # ``_compute_summary_context``.

    # KataGo 標準: rootInfo.visits
    root_info = analysis.get("rootInfo") or {}
    if "visits" in root_info:
        visits_value = root_info.get("visits")
        return int(visits_value) if visits_value is not None else None

    # KaTrain 内部フォーマット: root.visits
    root = analysis.get("root") or {}
    if "visits" in root:
        visits_value = root.get("visits")
        return int(visits_value) if visits_value is not None else None

    # 直接参照（一部のカスタムフォーマット対応）
    if "visits" in analysis:
        visits_value = analysis.get("visits")
        return int(visits_value) if visits_value is not None else None

    return None


def determine_reliability(root_visits: int | None, candidate_count: int) -> tuple[bool, str]:
    """信頼性を判定。

    フォールバック係数なし、シンプルなルール。

    Args:
        root_visits: root_visits 値（None の場合は unreliable）
        candidate_count: 候補手の数

    Returns:
        (is_reliable, reason) タプル。
    """
    # root_visits が None の場合は unreliable
    if root_visits is None:
        return False, "root_visits_missing"

    # visits 不足
    if root_visits < DIFFICULTY_MIN_VISITS:
        return False, f"visits_insufficient ({root_visits} < {DIFFICULTY_MIN_VISITS})"

    # 候補不足
    if candidate_count < DIFFICULTY_MIN_CANDIDATES:
        return False, f"candidates_insufficient ({candidate_count} < {DIFFICULTY_MIN_CANDIDATES})"

    return True, "reliable"


def get_candidates_from_node(
    node: Any,
) -> tuple[list[dict[str, Any]], int | None, dict[str, Any] | None]:
    """GameNode から候補手リストと root_visits と rootInfo を取得。

    ``get_root_visits()`` を使用して複数キーに対応。

    Args:
        node: 解析済み GameNode

    Returns:
        (candidates, root_visits, root_info) タプル。
        解析データがない場合は ([], None, None)。
    """
    if not node.analysis_exists:
        return [], None, None

    # candidate_moves プロパティはソート済み・拡張済みを返す
    candidates = node.candidate_moves

    # get_root_visits() で複数キーに対応
    root_visits = get_root_visits(node.analysis)

    # Phase 154: rootInfo も渡す（error 系指標の計算用）
    analysis = getattr(node, "analysis", None) or {}
    root_info = analysis.get("rootInfo") if isinstance(analysis, dict) else None
    if root_info is not None and not isinstance(root_info, dict):
        root_info = None

    return candidates, root_visits, root_info


__all__ = [
    "normalize_candidates",
    "get_root_visits",
    "determine_reliability",
    "get_candidates_from_node",
    "_difficulty_logger",
]
