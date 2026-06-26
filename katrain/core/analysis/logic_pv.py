"""PV filter configuration and complexity-based candidate filtering.

Phase 144-C: Extracted from logic.py (1494 lines → 6 focused modules).

Contains:
- get_pv_filter_config: Get PV filter config by level (with auto-mapping)
- filter_candidates_by_pv_complexity: Filter candidates by PV length and loss
"""
from __future__ import annotations

from typing import Any

from katrain.core.analysis.models import (
    DEFAULT_SKILL_PRESET,
    PV_FILTER_CONFIGS,
    SKILL_TO_PV_FILTER,
    PVFilterConfig,
)


# =============================================================================
# PV Filter (Phase 11)
# =============================================================================


def get_pv_filter_config(
    pv_filter_level: str,
    skill_preset: str = DEFAULT_SKILL_PRESET,
) -> PVFilterConfig | None:
    """
    PVフィルタ設定を取得する。

    Args:
        pv_filter_level: "off", "weak", "medium", "strong", "auto"
        skill_preset: AUTOモード時に参照するskill_preset名

    Returns:
        PVFilterConfig または None（OFFの場合）
    """
    level = pv_filter_level.lower()

    if level == "off":
        return None

    if level == "auto":
        # skill_presetからpv_filter_levelを決定
        mapped_level = SKILL_TO_PV_FILTER.get(skill_preset, "medium")
        return PV_FILTER_CONFIGS.get(mapped_level)

    return PV_FILTER_CONFIGS.get(level)


def filter_candidates_by_pv_complexity(
    candidates: list[dict[str, Any]],
    config: PVFilterConfig,
) -> list[dict[str, Any]]:
    """
    候補手リストをPV複雑度でフィルタリングする（Phase 11）。

    データ仕様:
    - pv: 常にList[str]で存在（GTP座標の着手列）
    - pointsLost: 常に存在（game_node.pyで計算追加）
    - order: 常に存在（欠損時はADDITIONAL_MOVE_ORDER=999）

    上限ルール:
    - max_candidates はフィルタ通過手の上限（best_move は別枠）
    - best_move（order=0）は上限に含めず常に表示

    Args:
        candidates: candidate_moves から取得した候補手リスト
        config: PVFilterConfig（閾値設定）

    Returns:
        フィルタ済みの候補手リスト
    """
    if not candidates:
        return []

    # Step 1: order=0（最善手）を特定
    best_move = None
    for c in candidates:
        if c.get("order", 999) == 0:
            best_move = c
            break

    # Step 2: フィルタ条件でチェック（best_move以外）
    filtered = []
    for c in candidates:
        if c is best_move:
            continue  # best_moveは別枠で処理
        points_lost = c.get("pointsLost", 0.0)
        pv = c.get("pv", [])
        pv_length = len(pv) if pv else 0

        # 条件: 損失が閾値以下 AND PV長が閾値以下
        if points_lost <= config.max_points_lost and pv_length <= config.max_pv_length:
            filtered.append(c)

    # Step 3: max_candidates 制限（order順でカット、best_move除外済み）
    filtered = sorted(filtered, key=lambda c: c.get("order", 999))
    filtered = filtered[: config.max_candidates]

    # Step 4: best_moveを先頭に挿入（別枠、上限外）
    if best_move:
        filtered.insert(0, best_move)

    return filtered
