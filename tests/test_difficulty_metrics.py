"""
Phase 12: 難易度分解（Difficulty Metrics）のユニットテスト

テストカテゴリ:
- 正規化（_normalize_candidates）
- root_visits取得（_get_root_visits）
- 信頼性判定（_determine_reliability）
- Policy難易度（_compute_policy_difficulty）
- Transition難易度（_compute_transition_difficulty）
- State難易度（_compute_state_difficulty）
- 統合関数（compute_difficulty_metrics）
- UNKNOWN判定（is_unknownフラグ）
- 符号処理（負のscoreLead）
- 境界値
- 抽出（extract_difficult_positions）
- デバッグ情報
"""

import pytest

from katrain.core.analysis import (
    DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    DEFAULT_MIN_MOVE_NUMBER,
    DIFFICULTY_MIN_CANDIDATES,
    DIFFICULTY_MIN_VISITS,
    DIFFICULTY_UNKNOWN,
    POLICY_GAP_MAX,
    TRANSITION_DROP_MAX,
    DifficultyMetrics,
    _compute_policy_difficulty,
    _compute_state_difficulty,
    _compute_transition_difficulty,
    _determine_reliability,
    _get_root_visits,
    _normalize_candidates,
    compute_difficulty_metrics,
)

# =============================================================================
# Fixtures
# =============================================================================

FIXTURE_CANDIDATES_BALANCED = [
    {"order": 0, "scoreLead": 2.0, "move": "D4", "visits": 300},
    {"order": 1, "scoreLead": 1.8, "move": "E5", "visits": 200},  # gap=0.2
    {"order": 2, "scoreLead": 1.5, "move": "C3", "visits": 150},
]

FIXTURE_CANDIDATES_CLEAR_BEST = [
    {"order": 0, "scoreLead": 5.0, "move": "D4", "visits": 500},
    {"order": 1, "scoreLead": -3.0, "move": "E5", "visits": 100},  # gap=8.0
    {"order": 2, "scoreLead": -5.0, "move": "C3", "visits": 50},
]

FIXTURE_CANDIDATES_UNSORTED = [
    {"order": 2, "scoreLead": 0.0, "move": "C3", "visits": 100},
    {"order": 0, "scoreLead": 2.0, "move": "D4", "visits": 300},
    {"order": 1, "scoreLead": 1.0, "move": "E5", "visits": 200},
]

FIXTURE_CANDIDATES_NO_ORDER = [
    {"scoreLead": 0.0, "move": "C3", "visits": 100},
    {"scoreLead": 2.0, "move": "D4", "visits": 300},
    {"scoreLead": 1.0, "move": "E5", "visits": 200},
]

FIXTURE_CANDIDATES_WHITE_ADVANTAGE = [
    {"order": 0, "scoreLead": -10.0, "move": "D4", "visits": 500},
    {"order": 1, "scoreLead": -10.5, "move": "E5", "visits": 200},  # gap=0.5
    {"order": 2, "scoreLead": -12.0, "move": "C3", "visits": 100},
]


# =============================================================================
# 正規化テスト
# =============================================================================


class TestNormalizeCandidates:
    """_normalize_candidates のテスト"""

    def test_sorted_candidates(self):
        """既にソート済みの候補をそのまま返す"""
        result = _normalize_candidates(FIXTURE_CANDIDATES_BALANCED)
        assert result is not None
        assert len(result) == 3
        assert result[0]["order"] == 0
        assert result[1]["order"] == 1

    def test_unsorted_candidates(self):
        """未ソートの候補をソートする"""
        result = _normalize_candidates(FIXTURE_CANDIDATES_UNSORTED)
        assert result is not None
        assert result[0]["order"] == 0
        assert result[1]["order"] == 1
        assert result[2]["order"] == 2

    def test_no_order_returns_none(self):
        """order がない場合は None を返す"""
        result = _normalize_candidates(FIXTURE_CANDIDATES_NO_ORDER)
        assert result is None

    def test_empty_list(self):
        """空リストは空リストを返す"""
        result = _normalize_candidates([])
        assert result == []


# =============================================================================
# root_visits 取得テスト
# =============================================================================


class TestGetRootVisits:
    """_get_root_visits のテスト"""

    def test_from_rootInfo(self):
        """KataGo 標準フォーマット: rootInfo.visits"""
        analysis = {"rootInfo": {"visits": 1000}}
        assert _get_root_visits(analysis) == 1000

    def test_from_root(self):
        """KaTrain 内部フォーマット: root.visits"""
        analysis = {"root": {"visits": 800}}
        assert _get_root_visits(analysis) == 800

    def test_direct_visits(self):
        """直接参照: visits"""
        analysis = {"visits": 600}
        assert _get_root_visits(analysis) == 600

    def test_priority_order(self):
        """優先順位: rootInfo > root > visits"""
        analysis = {
            "rootInfo": {"visits": 1000},
            "root": {"visits": 800},
            "visits": 600,
        }
        assert _get_root_visits(analysis) == 1000

    def test_missing_returns_none(self):
        """どのキーもない場合は None"""
        analysis = {"moveInfos": []}
        assert _get_root_visits(analysis) is None

    def test_empty_analysis(self):
        """空の analysis は None"""
        assert _get_root_visits({}) is None
        assert _get_root_visits(None) is None


# =============================================================================
# 信頼性判定テスト
# =============================================================================


class TestDetermineReliability:
    """_determine_reliability のテスト"""

    def test_reliable(self):
        """十分な visits と候補数で reliable"""
        is_reliable, reason = _determine_reliability(1000, 5)
        assert is_reliable is True
        assert reason == "reliable"

    def test_root_visits_none(self):
        """root_visits=None は unreliable"""
        is_reliable, reason = _determine_reliability(None, 5)
        assert is_reliable is False
        assert "root_visits_missing" in reason

    def test_visits_insufficient(self):
        """visits 不足は unreliable"""
        is_reliable, reason = _determine_reliability(100, 5)
        assert is_reliable is False
        assert "visits_insufficient" in reason

    def test_candidates_insufficient(self):
        """候補不足は unreliable"""
        is_reliable, reason = _determine_reliability(1000, 1)
        assert is_reliable is False
        assert "candidates_insufficient" in reason

    def test_boundary_visits(self):
        """境界値: visits=500 は reliable"""
        is_reliable, _ = _determine_reliability(500, 5)
        assert is_reliable is True

        is_reliable, _ = _determine_reliability(499, 5)
        assert is_reliable is False

    def test_boundary_candidates(self):
        """境界値: 候補2件は reliable (MIN_CANDIDATES=2)"""
        is_reliable, _ = _determine_reliability(1000, 2)
        assert is_reliable is True

        is_reliable, _ = _determine_reliability(1000, 1)
        assert is_reliable is False


# =============================================================================
# Policy 難易度テスト
# =============================================================================


class TestComputePolicyDifficulty:
    """_compute_policy_difficulty のテスト"""

    def test_gap_zero_returns_one(self):
        """gap=0 は difficulty=1.0"""
        candidates = [
            {"order": 0, "scoreLead": 2.0},
            {"order": 1, "scoreLead": 2.0},
        ]
        difficulty, _ = _compute_policy_difficulty(candidates)
        assert difficulty == 1.0

    def test_gap_max_returns_zero(self):
        """gap>=MAX は difficulty=0.0"""
        candidates = [
            {"order": 0, "scoreLead": 10.0},
            {"order": 1, "scoreLead": 5.0},  # gap=5.0
        ]
        difficulty, _ = _compute_policy_difficulty(candidates)
        assert difficulty == 0.0

    def test_gap_intermediate(self):
        """中間値のテスト"""
        # gap=2.5 → difficulty = 1 - 2.5/5.0 = 0.5
        candidates = [
            {"order": 0, "scoreLead": 5.0},
            {"order": 1, "scoreLead": 2.5},
        ]
        difficulty, _ = _compute_policy_difficulty(candidates)
        assert difficulty == pytest.approx(0.5, abs=0.01)

    def test_insufficient_candidates(self):
        """候補1件は difficulty=0.0"""
        candidates = [{"order": 0, "scoreLead": 2.0}]
        difficulty, _ = _compute_policy_difficulty(candidates)
        assert difficulty == 0.0

    def test_missing_scorelead_returns_none(self):
        """scoreLead がない場合は None"""
        candidates = [
            {"order": 0, "move": "D4"},
            {"order": 1, "move": "E5"},
        ]
        difficulty, debug = _compute_policy_difficulty(candidates, include_debug=True)
        assert difficulty is None
        assert debug["reason"] == "missing_scoreLead"

    def test_debug_info(self):
        """デバッグ情報の確認"""
        candidates = FIXTURE_CANDIDATES_BALANCED
        difficulty, debug = _compute_policy_difficulty(candidates, include_debug=True)
        assert debug is not None
        assert "top1_score" in debug
        assert "top2_score" in debug
        assert "gap" in debug


# =============================================================================
# Transition 難易度テスト
# =============================================================================


class TestComputeTransitionDifficulty:
    """_compute_transition_difficulty のテスト"""

    def test_drop_zero_returns_zero(self):
        """drop=0 は difficulty=0.0"""
        candidates = [
            {"order": 0, "scoreLead": 2.0},
            {"order": 1, "scoreLead": 2.0},
        ]
        difficulty, _ = _compute_transition_difficulty(candidates)
        assert difficulty == 0.0

    def test_drop_max_returns_one(self):
        """drop>=MAX は difficulty=1.0"""
        candidates = [
            {"order": 0, "scoreLead": 10.0},
            {"order": 1, "scoreLead": 2.0},  # drop=8.0
        ]
        difficulty, _ = _compute_transition_difficulty(candidates)
        assert difficulty == 1.0

    def test_drop_intermediate(self):
        """中間値のテスト"""
        # drop=4.0 → difficulty = 4.0/8.0 = 0.5
        candidates = [
            {"order": 0, "scoreLead": 6.0},
            {"order": 1, "scoreLead": 2.0},
        ]
        difficulty, _ = _compute_transition_difficulty(candidates)
        assert difficulty == pytest.approx(0.5, abs=0.01)

    def test_insufficient_candidates(self):
        """候補1件は difficulty=0.0"""
        candidates = [{"order": 0, "scoreLead": 2.0}]
        difficulty, _ = _compute_transition_difficulty(candidates)
        assert difficulty == 0.0

    def test_missing_scorelead_returns_none(self):
        """scoreLead がない場合は None"""
        candidates = [
            {"order": 0, "move": "D4"},
            {"order": 1, "move": "E5"},
        ]
        difficulty, debug = _compute_transition_difficulty(candidates, include_debug=True)
        assert difficulty is None
        assert debug["reason"] == "missing_scoreLead"


# =============================================================================
# State 難易度テスト
# =============================================================================


class TestComputeStateDifficulty:
    """_compute_state_difficulty のテスト"""

    def test_always_zero(self):
        """v1 では常に 0.0"""
        candidates = FIXTURE_CANDIDATES_BALANCED
        difficulty, _ = _compute_state_difficulty(candidates)
        assert difficulty == 0.0

    def test_debug_info(self):
        """デバッグ情報の確認"""
        candidates = FIXTURE_CANDIDATES_BALANCED
        difficulty, debug = _compute_state_difficulty(candidates, include_debug=True)
        assert debug is not None
        assert "v1_note" in debug
        assert "candidate_count" in debug


# =============================================================================
# 統合関数テスト
# =============================================================================


class TestComputeDifficultyMetrics:
    """compute_difficulty_metrics のテスト"""

    def test_balanced_candidates(self):
        """候補が拮抗する場合"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_BALANCED, root_visits=1000)
        assert metrics.is_unknown is False
        assert metrics.is_reliable is True
        # gap=0.2 → policy = 1 - 0.2/5.0 = 0.96
        assert metrics.policy_difficulty == pytest.approx(0.96, abs=0.01)
        # drop=0.2 → transition = 0.2/8.0 = 0.025
        assert metrics.transition_difficulty == pytest.approx(0.025, abs=0.01)
        # overall = max(0.96, 0.025) = 0.96
        assert metrics.overall_difficulty == pytest.approx(0.96, abs=0.01)

    def test_clear_best(self):
        """最善が突出する場合"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_CLEAR_BEST, root_visits=1000)
        assert metrics.is_unknown is False
        # gap=8.0 → policy = 0.0
        assert metrics.policy_difficulty == 0.0
        # drop=8.0 → transition = 1.0
        assert metrics.transition_difficulty == 1.0
        # overall = max(0.0, 1.0) = 1.0
        assert metrics.overall_difficulty == 1.0

    def test_unreliable_overall_scaled(self):
        """unreliable の場合は overall が 0.7 倍"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_BALANCED, root_visits=100)
        assert metrics.is_reliable is False
        # policy = 0.96, overall = 0.96 * 0.7 = 0.672
        assert metrics.overall_difficulty == pytest.approx(0.96 * 0.7, abs=0.01)

    def test_empty_candidates_returns_unknown(self):
        """空リストは DIFFICULTY_UNKNOWN を返す"""
        metrics = compute_difficulty_metrics([])
        assert metrics is DIFFICULTY_UNKNOWN
        assert metrics.is_unknown is True

    def test_no_order_returns_unknown(self):
        """order 欠損は UNKNOWN"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_NO_ORDER, root_visits=1000)
        assert metrics.is_unknown is True

    def test_missing_scorelead_returns_unknown(self):
        """scoreLead 欠損は UNKNOWN"""
        candidates = [
            {"order": 0, "move": "D4"},
            {"order": 1, "move": "E5"},
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        assert metrics.is_unknown is True

    def test_debug_info(self):
        """デバッグ情報の確認"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_BALANCED, root_visits=1000, include_debug=True)
        assert metrics.debug_factors is not None
        assert "policy" in metrics.debug_factors
        assert "transition" in metrics.debug_factors
        assert "reliability" in metrics.debug_factors
        assert "overall_method" in metrics.debug_factors


# =============================================================================
# UNKNOWN 判定テスト
# =============================================================================


class TestDifficultyUnknown:
    """DIFFICULTY_UNKNOWN のテスト"""

    def test_unknown_has_is_unknown_flag(self):
        """DIFFICULTY_UNKNOWN は is_unknown=True を持つ"""
        assert DIFFICULTY_UNKNOWN.is_unknown is True
        assert DIFFICULTY_UNKNOWN.is_reliable is False
        assert DIFFICULTY_UNKNOWN.overall_difficulty == 0.0

    def test_normal_metrics_has_is_unknown_false(self):
        """正常計算時は is_unknown=False"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_BALANCED, root_visits=1000)
        assert metrics.is_unknown is False

    def test_is_unknown_flag_vs_is_comparison(self):
        """is_unknown フラグは別インスタンスでも動作"""
        # DIFFICULTY_UNKNOWN と等価な別インスタンスを作成
        fake_unknown = DifficultyMetrics(
            policy_difficulty=0.0,
            transition_difficulty=0.0,
            state_difficulty=0.0,
            overall_difficulty=0.0,
            is_reliable=False,
            is_unknown=True,
        )
        # is 比較は失敗するが、is_unknown フラグは動作
        assert fake_unknown is not DIFFICULTY_UNKNOWN
        assert fake_unknown.is_unknown is True


# =============================================================================
# 符号処理テスト
# =============================================================================


class TestSignHandling:
    """scoreLead の符号処理テスト"""

    def test_negative_scorelead(self):
        """白有利（負のscoreLead）でも正しく計算"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_WHITE_ADVANTAGE, root_visits=1000)
        # gap = |-10.0 - (-10.5)| = 0.5
        # policy = 1 - 0.5/5.0 = 0.9
        assert metrics.policy_difficulty == pytest.approx(0.9, abs=0.01)

    def test_mixed_sign_scorelead(self):
        """正負混在のscoreLeadでも差の絶対値で計算"""
        candidates = [
            {"order": 0, "scoreLead": 2.0},  # 黒2目有利
            {"order": 1, "scoreLead": -3.0},  # 白3目有利 → gap=5.0
            {"order": 2, "scoreLead": -5.0},
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        # gap = |2.0 - (-3.0)| = 5.0 → policy = 0.0
        assert metrics.policy_difficulty == 0.0
        # drop = |2.0 - (-3.0)| = 5.0 → transition = 5.0/8.0 = 0.625
        assert metrics.transition_difficulty == pytest.approx(0.625, abs=0.01)


# =============================================================================
# 境界値テスト
# =============================================================================


class TestBoundaryValues:
    """境界値のテスト"""

    def test_single_candidate(self):
        """候補1件の場合: policy=0, transition=0"""
        candidates = [{"order": 0, "scoreLead": 2.0}]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        assert metrics.policy_difficulty == 0.0
        assert metrics.transition_difficulty == 0.0
        # 候補1件は unreliable
        assert metrics.is_reliable is False

    def test_two_candidates_reliable(self):
        """候補2件は reliable (MIN_CANDIDATES=2)"""
        candidates = [
            {"order": 0, "scoreLead": 2.0},
            {"order": 1, "scoreLead": 1.0},
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        assert metrics.is_reliable is True
        assert metrics.is_unknown is False

    def test_reliability_boundary(self):
        """信頼性閾値の境界値テスト"""
        candidates = FIXTURE_CANDIDATES_BALANCED

        # visits=499 → unreliable
        metrics = compute_difficulty_metrics(candidates, root_visits=499)
        assert metrics.is_reliable is False

        # visits=500 → reliable
        metrics = compute_difficulty_metrics(candidates, root_visits=500)
        assert metrics.is_reliable is True

    def test_overall_uses_max(self):
        """overall は max(policy, transition) を使用"""
        # gap = 2.5 → policy = 0.5, transition = 2.5/8.0 = 0.3125
        candidates = [
            {"order": 0, "scoreLead": 5.0},
            {"order": 1, "scoreLead": 2.5},
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        # overall = max(0.5, 0.3125) = 0.5
        assert metrics.overall_difficulty == pytest.approx(0.5, abs=0.01)


# =============================================================================
# 定数確認テスト
# =============================================================================


class TestConstants:
    """定数の確認テスト"""

    def test_min_visits(self):
        """DIFFICULTY_MIN_VISITS の値"""
        assert DIFFICULTY_MIN_VISITS == 500

    def test_min_candidates(self):
        """DIFFICULTY_MIN_CANDIDATES の値"""
        assert DIFFICULTY_MIN_CANDIDATES == 2

    def test_policy_gap_max(self):
        """POLICY_GAP_MAX の値"""
        assert POLICY_GAP_MAX == 5.0

    def test_transition_drop_max(self):
        """TRANSITION_DROP_MAX の値"""
        assert TRANSITION_DROP_MAX == 8.0

    def test_default_limit(self):
        """DEFAULT_DIFFICULT_POSITIONS_LIMIT の値"""
        assert DEFAULT_DIFFICULT_POSITIONS_LIMIT == 10

    def test_default_min_move(self):
        """DEFAULT_MIN_MOVE_NUMBER の値"""
        assert DEFAULT_MIN_MOVE_NUMBER == 10


# =============================================================================
# Policy vs Transition の解釈テスト
# =============================================================================


class TestPolicyVsTransition:
    """Policy と Transition の逆解釈テスト"""

    def test_small_gap_high_policy_low_transition(self):
        """gap が小さい場合: Policy 高、Transition 低"""
        # gap=0.2
        candidates = FIXTURE_CANDIDATES_BALANCED
        normalized = _normalize_candidates(candidates)
        policy, _ = _compute_policy_difficulty(normalized)
        transition, _ = _compute_transition_difficulty(normalized)
        # 候補が拮抗 → 迷いやすいが崩れにくい
        assert policy > 0.9  # 高い
        assert transition < 0.1  # 低い

    def test_large_gap_low_policy_high_transition(self):
        """gap が大きい場合: Policy 低、Transition 高"""
        # gap=8.0
        candidates = FIXTURE_CANDIDATES_CLEAR_BEST
        normalized = _normalize_candidates(candidates)
        policy, _ = _compute_policy_difficulty(normalized)
        transition, _ = _compute_transition_difficulty(normalized)
        # 最善が突出 → 迷わないが崩れやすい
        assert policy == 0.0  # 低い
        assert transition == 1.0  # 高い


# =============================================================================
# Phase 12.5: Formatting Tests
# =============================================================================


class TestDifficultyFormatting:
    """Phase 12.5: フォーマット関数のテスト"""

    def test_get_difficulty_label_easy(self):
        """overall < 0.3 は '易'"""
        from katrain.core.analysis import get_difficulty_label

        assert get_difficulty_label(0.0) == "易"
        assert get_difficulty_label(0.29) == "易"

    def test_get_difficulty_label_medium_boundary(self):
        """overall = 0.3 は '中'（境界）"""
        from katrain.core.analysis import get_difficulty_label

        assert get_difficulty_label(0.30) == "中"

    def test_get_difficulty_label_medium(self):
        """0.3 <= overall < 0.6 は '中'"""
        from katrain.core.analysis import get_difficulty_label

        assert get_difficulty_label(0.5) == "中"
        assert get_difficulty_label(0.59) == "中"

    def test_get_difficulty_label_hard_boundary(self):
        """overall = 0.6 は '難'（境界）"""
        from katrain.core.analysis import get_difficulty_label

        assert get_difficulty_label(0.60) == "難"

    def test_get_difficulty_label_hard(self):
        """overall >= 0.6 は '難'"""
        from katrain.core.analysis import get_difficulty_label

        assert get_difficulty_label(0.8) == "難"
        assert get_difficulty_label(1.0) == "難"

    def test_format_unknown_returns_empty(self):
        """is_unknown=True の場合は空リスト"""
        from katrain.core.analysis import DIFFICULTY_UNKNOWN, format_difficulty_metrics

        lines = format_difficulty_metrics(DIFFICULTY_UNKNOWN)
        assert lines == []

    def test_format_reliable(self):
        """信頼性が高い場合のフォーマット"""
        from katrain.core.analysis import DifficultyMetrics, format_difficulty_metrics

        metrics = DifficultyMetrics(
            policy_difficulty=0.65,
            transition_difficulty=0.72,
            state_difficulty=0.0,
            overall_difficulty=0.72,
            is_reliable=True,
            is_unknown=False,
        )
        lines = format_difficulty_metrics(metrics)
        assert len(lines) == 2
        assert "難" in lines[0]
        assert "0.72" in lines[0]
        assert "⚠" not in lines[0]
        assert "迷い=0.65" in lines[1]
        assert "崩れ=0.72" in lines[1]
        assert "[信頼度低]" not in lines[1]

    def test_format_unreliable(self):
        """信頼性が低い場合のフォーマット"""
        from katrain.core.analysis import DifficultyMetrics, format_difficulty_metrics

        metrics = DifficultyMetrics(
            policy_difficulty=0.45,
            transition_difficulty=0.32,
            state_difficulty=0.0,
            overall_difficulty=0.45,
            is_reliable=False,
            is_unknown=False,
        )
        lines = format_difficulty_metrics(metrics)
        assert len(lines) == 2
        assert "⚠" in lines[0]
        assert "[信頼度低]" in lines[1]


# =============================================================================
# Phase 154: KataGo error / LCB 系のテスト
# =============================================================================


class TestPhase154ErrorPressure:
    """Phase 154: error_pressure（KataGo 短期 error 由来）のテスト"""

    def test_no_root_info_returns_none(self):
        """root_info=None のとき error_pressure は None"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_BALANCED, root_visits=1000)
        assert metrics.error_pressure is None

    def test_error_pressure_from_shortterm_score_error(self):
        """shorttermScoreError から error_pressure を計算"""
        root_info = {"shorttermScoreError": 2.5}  # /SHORTTERM_SCORE_ERROR_MAX(5.0) = 0.5
        metrics = compute_difficulty_metrics(
            FIXTURE_CANDIDATES_BALANCED, root_visits=1000, root_info=root_info
        )
        assert metrics.error_pressure == pytest.approx(0.5, abs=0.01)

    def test_error_pressure_clamped_to_one(self):
        """error_pressure は最大 1.0 にクランプ"""
        root_info = {"shorttermScoreError": 100.0}  # 大きすぎ
        metrics = compute_difficulty_metrics(
            FIXTURE_CANDIDATES_BALANCED, root_visits=1000, root_info=root_info
        )
        assert metrics.error_pressure == 1.0

    def test_error_pressure_missing_returns_none(self):
        """shorttermScoreError 欠損時は None"""
        root_info = {}  # shorttermScoreError なし
        metrics = compute_difficulty_metrics(
            FIXTURE_CANDIDATES_BALANCED, root_visits=1000, root_info=root_info
        )
        assert metrics.error_pressure is None


class TestPhase154LcbGap:
    """Phase 154: lcb_gap（LCB 差由来）のテスト"""

    def test_no_lcb_returns_none(self):
        """候補手に lcb がない場合は None"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_BALANCED, root_visits=1000)
        assert metrics.lcb_gap is None

    def test_lcb_gap_from_candidates(self):
        """lcb_gap が計算される"""
        candidates = [
            {"order": 0, "scoreLead": 2.0, "lcb": 1.5},
            {"order": 1, "scoreLead": 1.0, "lcb": 0.5},  # diff=1.0
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        # diff=1.0 / LCB_GAP_MAX(2.0) = 0.5
        assert metrics.lcb_gap == pytest.approx(0.5, abs=0.01)

    def test_lcb_gap_clamped_to_one(self):
        """lcb_gap は最大 1.0 にクランプ"""
        candidates = [
            {"order": 0, "scoreLead": 2.0, "lcb": 5.0},
            {"order": 1, "scoreLead": 1.0, "lcb": -10.0},  # diff=15.0
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        assert metrics.lcb_gap == 1.0

    def test_lcb_gap_only_top1_returns_none(self):
        """top2 に lcb がない場合は None"""
        candidates = [
            {"order": 0, "scoreLead": 2.0, "lcb": 1.0},
            {"order": 1, "scoreLead": 1.0},  # lcb なし
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        assert metrics.lcb_gap is None


class TestPhase154OverallAggregation:
    """Phase 154: overall への加成テスト"""

    def test_overall_with_only_error_pressure(self):
        """error_pressure のみで加成"""
        root_info = {"shorttermScoreError": 5.0}  # error_pressure=1.0
        metrics = compute_difficulty_metrics(
            FIXTURE_CANDIDATES_BALANCED, root_visits=1000, root_info=root_info
        )
        # 既存: overall = max(0.96, 0.025) = 0.96
        # 加成: 0.96 + 0.15 * 1.0 = 1.11 → クランプで 1.0
        assert metrics.overall_difficulty == pytest.approx(1.0, abs=0.01)

    def test_overall_with_only_lcb_gap(self):
        """lcb_gap のみで加成"""
        candidates = [
            {"order": 0, "scoreLead": 5.0, "lcb": 2.0},
            {"order": 1, "scoreLead": 5.0, "lcb": 0.0},  # diff=2.0 → lcb_gap=1.0
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000)
        # 既存: gap=0 → policy=1.0, transition=0.0 → overall=1.0
        # 加成: 1.0 + 0.15 * 1.0 = 1.15 → クランプで 1.0
        assert metrics.overall_difficulty == pytest.approx(1.0, abs=0.01)

    def test_overall_with_both_factors(self):
        """error_pressure と lcb_gap 両方で加成"""
        root_info = {"shorttermScoreError": 2.5}  # error_pressure=0.5
        candidates = [
            {"order": 0, "scoreLead": 2.0, "lcb": 1.0},
            {"order": 1, "scoreLead": 1.8, "lcb": 0.0},  # diff=1.0 → lcb_gap=0.5
        ]
        metrics = compute_difficulty_metrics(candidates, root_visits=1000, root_info=root_info)
        # gap=0.2 → policy=0.96, transition=0.025 → overall=0.96
        # 加成: 0.96 + 0.15*0.5 + 0.15*0.5 = 0.96 + 0.075 + 0.075 = 1.11 → 1.0
        assert metrics.overall_difficulty == pytest.approx(1.0, abs=0.01)

    def test_overall_backward_compatible_without_error_and_lcb(self):
        """error/lcb データなしの場合は従来と同じ結果"""
        metrics = compute_difficulty_metrics(FIXTURE_CANDIDATES_BALANCED, root_visits=1000)
        # 既存と完全に同じ: 0.96
        assert metrics.overall_difficulty == pytest.approx(0.96, abs=0.01)

    def test_overall_clamped_after_aggregation(self):
        """overall は集約後にクランプされる"""
        root_info = {"shorttermScoreError": 10.0}  # error_pressure=1.0
        metrics = compute_difficulty_metrics(
            FIXTURE_CANDIDATES_BALANCED, root_visits=1000, root_info=root_info
        )
        # error_pressure 加成で 1.0 を超えるがクランプ
        assert metrics.overall_difficulty <= 1.0


class TestPhase154Formatting:
    """Phase 154: フォーマット拡張のテスト"""

    def test_format_includes_error_pressure(self):
        """error_pressure がある場合、表示に含める"""
        from katrain.core.analysis import DifficultyMetrics, format_difficulty_metrics

        metrics = DifficultyMetrics(
            policy_difficulty=0.5,
            transition_difficulty=0.5,
            state_difficulty=0.0,
            overall_difficulty=0.5,
            error_pressure=0.3,
            lcb_gap=None,
            is_reliable=True,
            is_unknown=False,
        )
        lines = format_difficulty_metrics(metrics)
        # 3行: 局面難易度, 迷い/崩れ, error/LCB
        assert len(lines) == 3
        assert any("error=0.30" in line for line in lines)

    def test_format_includes_lcb_gap(self):
        """lcb_gap がある場合、表示に含める"""
        from katrain.core.analysis import DifficultyMetrics, format_difficulty_metrics

        metrics = DifficultyMetrics(
            policy_difficulty=0.5,
            transition_difficulty=0.5,
            state_difficulty=0.0,
            overall_difficulty=0.5,
            error_pressure=None,
            lcb_gap=0.4,
            is_reliable=True,
            is_unknown=False,
        )
        lines = format_difficulty_metrics(metrics)
        assert any("LCB差=0.40" in line for line in lines)

    def test_format_includes_both(self):
        """error_pressure と lcb_gap 両方ある場合"""
        from katrain.core.analysis import DifficultyMetrics, format_difficulty_metrics

        metrics = DifficultyMetrics(
            policy_difficulty=0.5,
            transition_difficulty=0.5,
            state_difficulty=0.0,
            overall_difficulty=0.5,
            error_pressure=0.3,
            lcb_gap=0.4,
            is_reliable=True,
            is_unknown=False,
        )
        lines = format_difficulty_metrics(metrics)
        last_line = lines[-1]
        assert "error=0.30" in last_line
        assert "LCB差=0.40" in last_line

    def test_format_no_extra_line_when_both_none(self):
        """error_pressure と lcb_gap 両方 None の場合は従来通り2行"""
        from katrain.core.analysis import DifficultyMetrics, format_difficulty_metrics

        metrics = DifficultyMetrics(
            policy_difficulty=0.5,
            transition_difficulty=0.5,
            state_difficulty=0.0,
            overall_difficulty=0.5,
            error_pressure=None,
            lcb_gap=None,
            is_reliable=True,
            is_unknown=False,
        )
        lines = format_difficulty_metrics(metrics)
        assert len(lines) == 2
