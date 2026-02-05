"""
Tests for PV Filter (Phase 11)

候補手フィルタのユニットテスト。
- フィルタレベル別の動作確認
- PV長/pointsLost境界値テスト
- best_move別枠の確認
- AUTOマッピングの確認
"""

from katrain.core.analysis import (
    DEFAULT_PV_FILTER_LEVEL,
    PV_FILTER_CONFIGS,
    SKILL_TO_PV_FILTER,
    PVFilterConfig,
    PVFilterLevel,
    filter_candidates_by_pv_complexity,
    get_pv_filter_config,
)

# =============================================================================
# Fixtures
# =============================================================================


FIXTURE_CANDIDATES_NORMAL = [
    {"order": 0, "pointsLost": 0.0, "pv": ["D4", "D5"], "move": "D4"},
    {"order": 1, "pointsLost": 1.5, "pv": ["E5", "E6", "F6"], "move": "E5"},
    {"order": 2, "pointsLost": 3.0, "pv": ["C3", "C4", "D4", "E4", "F4"], "move": "C3"},
]


# STRONG: max_pv_length=6, MEDIUM: max_pv_length=10, WEAK: max_pv_length=15
FIXTURE_PV_BOUNDARY = [
    {"order": 0, "pointsLost": 0.0, "pv": ["A1"] * 5, "move": "A1"},  # pv=5: 全レベル通過
    {"order": 1, "pointsLost": 0.0, "pv": ["B2"] * 6, "move": "B2"},  # pv=6: STRONG境界
    {"order": 2, "pointsLost": 0.0, "pv": ["C3"] * 7, "move": "C3"},  # pv=7: STRONG除外
    {"order": 3, "pointsLost": 0.0, "pv": ["D4"] * 10, "move": "D4"},  # pv=10: MEDIUM境界
    {"order": 4, "pointsLost": 0.0, "pv": ["E5"] * 11, "move": "E5"},  # pv=11: MEDIUM除外
    {"order": 5, "pointsLost": 0.0, "pv": ["F6"] * 15, "move": "F6"},  # pv=15: WEAK境界
    {"order": 6, "pointsLost": 0.0, "pv": ["G7"] * 16, "move": "G7"},  # pv=16: WEAK除外
]


FIXTURE_NO_BEST_MOVE = [
    {"order": 999, "pointsLost": 0.5, "pv": ["D4", "D5"], "move": "D4"},
    {"order": 999, "pointsLost": 1.0, "pv": ["E5"], "move": "E5"},
]


# STRONG: max_points_lost=1.0 （<=比較なので1.0は通過、1.01は除外）
FIXTURE_POINTS_LOST_BOUNDARY = [
    {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},  # best_move（別枠）
    {"order": 1, "pointsLost": 0.99, "pv": ["B2"], "move": "B2"},  # 閾値未満: 通過
    {"order": 2, "pointsLost": 1.0, "pv": ["C3"], "move": "C3"},  # 閾値ちょうど: 通過
    {"order": 3, "pointsLost": 1.01, "pv": ["D4"], "move": "D4"},  # 閾値超過: 除外
    {"order": 4, "pointsLost": 2.0, "pv": ["E5"], "move": "E5"},  # 閾値超過: 除外
]


# =============================================================================
# Test: get_pv_filter_config
# =============================================================================


class TestGetPVFilterConfig:
    """get_pv_filter_config関数のテスト"""

    def test_off_returns_none(self):
        """OFF設定はNoneを返す"""
        assert get_pv_filter_config("off") is None
        assert get_pv_filter_config("OFF") is None

    def test_weak_config(self):
        """WEAK設定の値確認"""
        config = get_pv_filter_config("weak")
        assert config is not None
        assert config.max_candidates == 15
        assert config.max_points_lost == 4.0
        assert config.max_pv_length == 15

    def test_medium_config(self):
        """MEDIUM設定の値確認"""
        config = get_pv_filter_config("medium")
        assert config is not None
        assert config.max_candidates == 8
        assert config.max_points_lost == 2.0
        assert config.max_pv_length == 10

    def test_strong_config(self):
        """STRONG設定の値確認"""
        config = get_pv_filter_config("strong")
        assert config is not None
        assert config.max_candidates == 4
        assert config.max_points_lost == 1.0
        assert config.max_pv_length == 6

    def test_auto_with_relaxed(self):
        """AUTO + relaxed → WEAK"""
        config = get_pv_filter_config("auto", skill_preset="relaxed")
        weak_config = get_pv_filter_config("weak")
        assert config == weak_config

    def test_auto_with_beginner(self):
        """AUTO + beginner → WEAK"""
        config = get_pv_filter_config("auto", skill_preset="beginner")
        weak_config = get_pv_filter_config("weak")
        assert config == weak_config

    def test_auto_with_standard(self):
        """AUTO + standard → MEDIUM"""
        config = get_pv_filter_config("auto", skill_preset="standard")
        medium_config = get_pv_filter_config("medium")
        assert config == medium_config

    def test_auto_with_advanced(self):
        """AUTO + advanced → STRONG"""
        config = get_pv_filter_config("auto", skill_preset="advanced")
        strong_config = get_pv_filter_config("strong")
        assert config == strong_config

    def test_auto_with_pro(self):
        """AUTO + pro → STRONG"""
        config = get_pv_filter_config("auto", skill_preset="pro")
        strong_config = get_pv_filter_config("strong")
        assert config == strong_config

    def test_unknown_level_returns_none(self):
        """不明なレベルはNoneを返す"""
        assert get_pv_filter_config("unknown") is None


# =============================================================================
# Test: filter_candidates_by_pv_complexity
# =============================================================================


class TestFilterCandidatesByPVComplexity:
    """filter_candidates_by_pv_complexity関数のテスト"""

    def test_empty_candidates(self):
        """空リスト入力は空リストを返す"""
        config = PV_FILTER_CONFIGS["medium"]
        result = filter_candidates_by_pv_complexity([], config)
        assert result == []

    def test_filter_weak_all_pass(self):
        """WEAK設定: 正常データは全て残る"""
        config = PV_FILTER_CONFIGS["weak"]
        result = filter_candidates_by_pv_complexity(FIXTURE_CANDIDATES_NORMAL, config)
        assert len(result) == 3
        # best_moveが先頭
        assert result[0]["order"] == 0

    def test_filter_strong_filters_by_points_lost(self):
        """STRONG設定: pointsLostでフィルタされる"""
        config = PV_FILTER_CONFIGS["strong"]
        result = filter_candidates_by_pv_complexity(FIXTURE_CANDIDATES_NORMAL, config)
        # order=0 (pointsLost=0.0, pv=2) は通過
        # order=1 (pointsLost=1.5 > 1.0) は除外
        # order=2 (pointsLost=3.0 > 1.0) は除外
        assert len(result) == 1
        assert result[0]["order"] == 0

    def test_filter_medium(self):
        """MEDIUM設定: 閾値内の候補のみ残る"""
        config = PV_FILTER_CONFIGS["medium"]
        result = filter_candidates_by_pv_complexity(FIXTURE_CANDIDATES_NORMAL, config)
        # order=0 (pointsLost=0.0) 通過
        # order=1 (pointsLost=1.5 <= 2.0) 通過
        # order=2 (pointsLost=3.0 > 2.0) 除外
        assert len(result) == 2
        assert result[0]["order"] == 0
        assert result[1]["order"] == 1

    def test_pv_boundary_strong(self):
        """STRONG + PV境界データ: pv<=6の手のみ"""
        config = PV_FILTER_CONFIGS["strong"]
        result = filter_candidates_by_pv_complexity(FIXTURE_PV_BOUNDARY, config)
        # order=0 (pv=5, 別枠) 通過
        # order=1 (pv=6 <= 6) 通過
        # order=2 (pv=7 > 6) 除外
        # ...
        assert len(result) == 2
        orders = [c["order"] for c in result]
        assert 0 in orders  # best_move
        assert 1 in orders  # pv=6

    def test_pv_boundary_medium(self):
        """MEDIUM + PV境界データ: pv<=10の手のみ"""
        config = PV_FILTER_CONFIGS["medium"]
        result = filter_candidates_by_pv_complexity(FIXTURE_PV_BOUNDARY, config)
        # order=0 (pv=5, 別枠) 通過
        # order=1 (pv=6 <= 10) 通過
        # order=2 (pv=7 <= 10) 通過
        # order=3 (pv=10 <= 10) 通過
        # order=4 (pv=11 > 10) 除外
        # ...
        assert len(result) == 4
        orders = [c["order"] for c in result]
        assert set(orders) == {0, 1, 2, 3}

    def test_pv_boundary_weak(self):
        """WEAK + PV境界データ: pv<=15の手のみ"""
        config = PV_FILTER_CONFIGS["weak"]
        result = filter_candidates_by_pv_complexity(FIXTURE_PV_BOUNDARY, config)
        # order=0 (pv=5, 別枠) 通過
        # order=1-5 (pv<=15) 通過
        # order=6 (pv=16 > 15) 除外
        assert len(result) == 6
        orders = [c["order"] for c in result]
        assert 6 not in orders  # pv=16は除外

    def test_no_best_move(self):
        """order=0不在でもフィルタ条件を満たす手は返す"""
        config = PV_FILTER_CONFIGS["medium"]
        result = filter_candidates_by_pv_complexity(FIXTURE_NO_BEST_MOVE, config)
        # 両方 pointsLost <= 2.0, pv <= 10 なので通過
        assert len(result) == 2

    def test_best_move_separate_quota(self):
        """best_moveはmax_candidatesの上限外"""
        # max_candidates=2 でテスト
        config = PVFilterConfig(max_candidates=2, max_points_lost=10.0, max_pv_length=20)
        candidates = [
            {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
            {"order": 1, "pointsLost": 0.1, "pv": ["B2"], "move": "B2"},
            {"order": 2, "pointsLost": 0.2, "pv": ["C3"], "move": "C3"},
            {"order": 3, "pointsLost": 0.3, "pv": ["D4"], "move": "D4"},
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        # best_move(order=0) + 2件(order=1,2) = 計3件
        assert len(result) == 3
        assert result[0]["order"] == 0  # best_moveが先頭

    def test_fallback_best_only(self):
        """全候補がフィルタ条件外でもbest_moveは残る"""
        # 非常に厳しい設定
        config = PVFilterConfig(max_candidates=10, max_points_lost=0.0, max_pv_length=1)
        candidates = [
            {"order": 0, "pointsLost": 0.0, "pv": ["A1", "A2", "A3"], "move": "A1"},  # pv=3 > 1 だが別枠
            {"order": 1, "pointsLost": 1.0, "pv": ["B2"], "move": "B2"},  # pointsLost > 0
            {"order": 2, "pointsLost": 0.5, "pv": ["C3", "C4"], "move": "C3"},  # pv=2 > 1
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        # best_moveはフィルタ条件に関係なく含まれる
        assert len(result) == 1
        assert result[0]["order"] == 0

    def test_points_lost_boundary(self):
        """pointsLost境界値テスト（<=比較）"""
        config = PV_FILTER_CONFIGS["strong"]  # max_points_lost=1.0
        result = filter_candidates_by_pv_complexity(FIXTURE_POINTS_LOST_BOUNDARY, config)
        # order=0 (別枠) 通過
        # order=1 (0.99 <= 1.0) 通過
        # order=2 (1.0 <= 1.0) 通過
        # order=3 (1.01 > 1.0) 除外
        # order=4 (2.0 > 1.0) 除外
        assert len(result) == 3
        orders = [c["order"] for c in result]
        assert set(orders) == {0, 1, 2}


# =============================================================================
# Test: Constants
# =============================================================================


class TestConstants:
    """定数のテスト"""

    def test_default_pv_filter_level(self):
        """デフォルトレベルはauto"""
        assert DEFAULT_PV_FILTER_LEVEL == "auto"

    def test_skill_to_pv_filter_mapping(self):
        """skill_preset → pv_filterマッピングの確認"""
        assert SKILL_TO_PV_FILTER["relaxed"] == "weak"
        assert SKILL_TO_PV_FILTER["beginner"] == "weak"
        assert SKILL_TO_PV_FILTER["standard"] == "medium"
        assert SKILL_TO_PV_FILTER["advanced"] == "strong"
        assert SKILL_TO_PV_FILTER["pro"] == "strong"

    def test_pv_filter_configs_keys(self):
        """PV_FILTER_CONFIGSのキー確認"""
        assert set(PV_FILTER_CONFIGS.keys()) == {"weak", "medium", "strong"}

    def test_pv_filter_level_enum(self):
        """PVFilterLevel Enumの値確認"""
        assert PVFilterLevel.OFF.value == "off"
        assert PVFilterLevel.WEAK.value == "weak"
        assert PVFilterLevel.MEDIUM.value == "medium"
        assert PVFilterLevel.STRONG.value == "strong"
        assert PVFilterLevel.AUTO.value == "auto"
