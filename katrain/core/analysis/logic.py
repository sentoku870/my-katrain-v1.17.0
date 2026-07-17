"""katrain.core.analysis.logic - 計算ロジック（再エクスポート用）

Phase 144-C: 1494 行の単一ファイル logic.py を 6 つの焦点化モジュールに分割:
- logic_skill.py: 棋力プリセット + auto-strictness + 棋力推定
- logic_reliability.py: 信頼性計算 + MoveEval 作成 + 信頼度レベル
- logic_phase.py: 局面分類 (opening/middle/yose)
- logic_difficulty.py: 局面難易度評価 + 3 因子分解メトリクス
- logic_snapshot.py: EvalSnapshot 生成 + ミス集計 + 連続ミス検出
- logic_pv.py: PV フィルタ + 候補手複雑度フィルタ

既存の補助モジュール (Phase B4 で抽出済み):
- logic_importance.py: 重要度計算
- logic_loss.py: 損失計算

Note: logic_quiz.py は Phase 138-D で Quiz 機能本体が削除された後、
Phase 176 (PR 2) で完全に削除されました。

Phase 195-A: logic_difficulty のシム (deprecated) への参照を解消し、
Phase 192 で確立された difficulty/ サブパッケージの新 canonical 名を
直接 re-export するように変更。

この __init__.py (logic.py) は後方互換性のため全シンボルを再エクスポートする。
"""

from __future__ import annotations

from katrain.core.analysis.difficulty._io import (
    determine_reliability,
    get_candidates_from_node,
    get_root_visits,
    normalize_candidates,
)
from katrain.core.analysis.difficulty._policy import (
    assess_difficulty_from_policy,
    compute_policy_difficulty,
)
from katrain.core.analysis.difficulty._state import compute_state_difficulty
from katrain.core.analysis.difficulty._transition import compute_transition_difficulty

# Position difficulty (canonical names from the Phase 192 subpackage)
from katrain.core.analysis.difficulty.api import (
    assess_position_difficulty_from_parent,
    compute_difficulty_metrics,
    difficulty_metrics_from_node,
    extract_difficult_positions,
)
from katrain.core.analysis.logic_importance import (
    compute_importance_for_moves,
    get_difficulty_modifier,
    get_reliability_scale,
    pick_important_moves,
)
from katrain.core.analysis.logic_loss import (
    classify_mistake,
    compute_canonical_loss,
    compute_loss_from_delta,
)
from katrain.core.analysis.logic_phase import (
    classify_game_phase,
    get_phase_thresholds,
)
from katrain.core.analysis.logic_phase_dynamic import (
    ENDGAME_DETECTION_WINDOW,
    ENDGAME_SCORE_STDEV_THRESHOLD,
    apply_dynamic_phases,
    classify_phases_dynamic,
    it_consistent_with_static,
)
from katrain.core.analysis.logic_pv import (
    PV_ANIMATION_MAX_STEPS,
    PVFilterDisplayInfo,
    clip_pv_for_animation,
    filter_candidates_by_pv_complexity,
    get_effective_pv_filter_info,
    get_pv_filter_config,
)
from katrain.core.analysis.logic_reliability import (
    compute_confidence_level,
    compute_effective_threshold,
    compute_reliability_stats,
    is_reliable_from_visits,
    move_eval_from_node,
)
from katrain.core.analysis.logic_skill import (
    _distance_from_range,
    estimate_skill_level_from_tags,
    get_skill_preset,
    get_urgent_miss_config,
    rank_to_skill_preset,
    recommend_auto_strictness,
    resolve_skill_preset,
    validate_reason_tag,
)
from katrain.core.analysis.logic_snapshot import (
    aggregate_phase_mistake_stats,
    detect_mistake_streaks,
    iter_main_branch_nodes,
    snapshot_from_game,
    snapshot_from_nodes,
)

__all__ = [
    # Skill preset helpers
    "get_skill_preset",
    "get_urgent_miss_config",
    # Phase 229: rank -> preset bridge
    "rank_to_skill_preset",
    "resolve_skill_preset",
    # Auto-strictness
    "_distance_from_range",
    "recommend_auto_strictness",
    # Reason tag validation
    "validate_reason_tag",
    # GameNode bridge
    "move_eval_from_node",
    # Reliability functions
    "get_difficulty_modifier",
    "get_reliability_scale",
    "is_reliable_from_visits",
    "compute_reliability_stats",
    "compute_effective_threshold",
    # Confidence level
    "compute_confidence_level",
    # Phase functions
    "get_phase_thresholds",
    "classify_game_phase",
    "classify_phases_dynamic",
    "apply_dynamic_phases",
    "it_consistent_with_static",
    "ENDGAME_SCORE_STDEV_THRESHOLD",
    "ENDGAME_DETECTION_WINDOW",
    # Position difficulty (Phase 192 canonical names)
    "assess_difficulty_from_policy",
    "assess_position_difficulty_from_parent",
    "compute_policy_difficulty",
    "compute_state_difficulty",
    "compute_transition_difficulty",
    "determine_reliability",
    "get_candidates_from_node",
    "get_root_visits",
    "normalize_candidates",
    # Loss calculation
    "compute_loss_from_delta",
    "compute_canonical_loss",
    "classify_mistake",
    # Snapshot
    "snapshot_from_nodes",
    "iter_main_branch_nodes",
    "snapshot_from_game",
    # Phase mistake stats
    "aggregate_phase_mistake_stats",
    # Mistake streaks
    "detect_mistake_streaks",
    # Importance
    "compute_importance_for_moves",
    "pick_important_moves",
    # Skill estimation
    "estimate_skill_level_from_tags",
    # PV Filter (Phase 11)
    "get_pv_filter_config",
    "filter_candidates_by_pv_complexity",
    # Phase 246-A: display-effective level for UI
    "get_effective_pv_filter_info",
    "PVFilterDisplayInfo",
    # Phase 246-C: PV clip for animation
    "clip_pv_for_animation",
    "PV_ANIMATION_MAX_STEPS",
    # Difficulty Metrics (Phase 12 / Phase 192 canonical names)
    "compute_difficulty_metrics",
    "difficulty_metrics_from_node",
    "extract_difficult_positions",
]  # noqa: E501
