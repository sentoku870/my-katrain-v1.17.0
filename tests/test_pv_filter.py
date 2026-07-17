"""
Tests for PV Filter (Phase 11)

候補手フィルタのユニットテスト。
- フィルタレベル別の動作確認
- PV長/pointsLost境界値テスト
- best_move別枠の確認
- AUTOマッピングの確認
- (Phase 246-A) ``get_effective_pv_filter_info`` の表示用ヘルパー
"""

import pytest

from katrain.core.analysis import (
    DEFAULT_PV_FILTER_LEVEL,
    PV_FILTER_CONFIGS,
    SKILL_TO_PV_FILTER,
    PVFilterConfig,
    PVFilterDisplayInfo,
    PVFilterLevel,
    filter_candidates_by_pv_complexity,
    get_effective_pv_filter_info,
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
        """AUTO + pro → EXPERT (Phase 246-D M2 differentiation)."""
        config = get_pv_filter_config("auto", skill_preset="pro")
        expert_config = get_pv_filter_config("expert")
        assert config == expert_config

    def test_expert_preset(self):
        """Phase 246-D M2: 'expert' is a tighter tier than 'strong'."""
        config = get_pv_filter_config("expert")
        assert config is not None
        assert config.max_candidates == 3
        assert config.max_points_lost == 0.5
        assert config.max_pv_length == 4
        # And stricter than strong
        strong = get_pv_filter_config("strong")
        assert config.max_candidates <= strong.max_candidates
        assert config.max_points_lost <= strong.max_points_lost
        assert config.max_pv_length <= strong.max_pv_length

    def test_board_size_19_no_scaling(self):
        """Phase 246-D M1: 19路 board keeps the canonical config."""
        config_default = get_pv_filter_config("strong")
        config_19 = get_pv_filter_config("strong", board_size=19)
        assert config_19 == config_default

    def test_board_size_9_scales_pv_length_down(self):
        """9路 board scales max_pv_length linearly (9/19 ≈ 0.47x)."""
        config_19 = get_pv_filter_config("strong", board_size=19)
        config_9 = get_pv_filter_config("strong", board_size=9)
        # strong.max_pv_length=6 → 6 * 9/19 ≈ 2.84 → 3
        assert config_9.max_pv_length == 3
        # Other fields unchanged
        assert config_9.max_candidates == config_19.max_candidates
        assert config_9.max_points_lost == config_19.max_points_lost

    def test_board_size_13_scales_between_9_and_19(self):
        """13路 board scales between 9路 and 19路."""
        config_9 = get_pv_filter_config("strong", board_size=9)
        config_13 = get_pv_filter_config("strong", board_size=13)
        config_19 = get_pv_filter_config("strong", board_size=19)
        assert config_9.max_pv_length < config_13.max_pv_length < config_19.max_pv_length

    def test_board_size_none_uses_canonical(self):
        """No board_size → canonical config (backwards compatible)."""
        config = get_pv_filter_config("strong", board_size=None)
        config_default = get_pv_filter_config("strong")
        assert config == config_default

    def test_board_size_invalid_falls_back_to_canonical(self):
        """Invalid board_size (0, negative, too large) → canonical."""
        for bad_size in [0, -5, 4, 99]:
            config = get_pv_filter_config("strong", board_size=bad_size)
            config_default = get_pv_filter_config("strong")
            assert config == config_default

    def test_board_size_scaling_keeps_minimum_1(self):
        """Even on tiny boards, max_pv_length never collapses to 0."""
        config = get_pv_filter_config("expert", board_size=5)
        assert config.max_pv_length >= 1  # never zero

    def test_expert_appears_in_pv_filter_configs(self):
        """Phase 246-D M2: 'expert' is now a valid preset."""
        from katrain.core.analysis.models import PV_FILTER_CONFIGS

        assert "expert" in PV_FILTER_CONFIGS
        assert PV_FILTER_CONFIGS["expert"].max_candidates == 3

    def test_player_rank_overrides_skill_preset_in_auto(self):
        """Phase 246-E L7: when player_rank is passed and level='auto',
        the function derives the preset from rank itself, ignoring the
        skill_preset argument."""
        # 7d → pro → expert
        config = get_pv_filter_config("auto", skill_preset="beginner", player_rank="7d")
        expert = get_pv_filter_config("expert")
        assert config == expert

    def test_player_rank_empty_falls_back_to_skill_preset(self):
        """Phase 246-E L7: empty player_rank keeps the skill_preset."""
        config = get_pv_filter_config("auto", skill_preset="standard", player_rank="")
        medium = get_pv_filter_config("medium")
        assert config == medium

    def test_player_rank_kanji_works(self):
        """Phase 246-E L7: kanji ranks also resolve correctly."""
        # 6段 → pro → expert
        config = get_pv_filter_config("auto", skill_preset="beginner", player_rank="6段")
        expert = get_pv_filter_config("expert")
        assert config == expert

    def test_explicit_level_ignores_player_rank(self):
        """Phase 246-E L7: player_rank only affects AUTO mode."""
        # player_rank is irrelevant when level is explicit
        config = get_pv_filter_config("medium", skill_preset="pro", player_rank="7d")
        medium = get_pv_filter_config("medium")
        assert config == medium

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
        """skill_preset → pv_filterマッピングの確認 (Phase 246-D M2)"""
        assert SKILL_TO_PV_FILTER["relaxed"] == "weak"
        assert SKILL_TO_PV_FILTER["beginner"] == "weak"
        assert SKILL_TO_PV_FILTER["standard"] == "medium"
        assert SKILL_TO_PV_FILTER["advanced"] == "strong"
        # Phase 246-D M2: pro now maps to a tighter "expert" tier
        assert SKILL_TO_PV_FILTER["pro"] == "expert"

    def test_pv_filter_configs_keys(self):
        """PV_FILTER_CONFIGSのキー確認 (Phase 246-D M2)"""
        assert set(PV_FILTER_CONFIGS.keys()) == {"weak", "medium", "strong", "expert"}

    def test_pv_filter_level_enum(self):
        """PVFilterLevel Enumの値確認"""
        assert PVFilterLevel.OFF.value == "off"
        assert PVFilterLevel.WEAK.value == "weak"
        assert PVFilterLevel.MEDIUM.value == "medium"
        assert PVFilterLevel.STRONG.value == "strong"
        assert PVFilterLevel.AUTO.value == "auto"


# =============================================================================
# Phase 246-A: get_effective_pv_filter_info display helper
# =============================================================================


class TestGetEffectivePVFilterInfo:
    """``get_effective_pv_filter_info`` resolves the *display-effective*
    level and cap that the settings popup status label uses (H2)."""

    def test_off_returns_unlimited_cap(self):
        """OFF: max_candidates=0 sentinel = "unlimited"."""
        info = get_effective_pv_filter_info("off", "5d")
        assert info.effective_level == "off"
        assert info.max_candidates == 0
        assert info.is_auto is False
        assert info.resolved_preset is None

    def test_weak_returns_weak_config(self):
        info = get_effective_pv_filter_info("weak", "")
        assert info.effective_level == "weak"
        assert info.max_candidates == 15
        assert info.is_auto is False
        assert info.resolved_preset is None

    def test_medium_returns_medium_config(self):
        info = get_effective_pv_filter_info("medium", "")
        assert info.effective_level == "medium"
        assert info.max_candidates == 8
        assert info.is_auto is False

    def test_strong_returns_strong_config(self):
        info = get_effective_pv_filter_info("strong", "")
        assert info.effective_level == "strong"
        assert info.max_candidates == 4
        assert info.is_auto is False

    def test_auto_with_5d_resolves_advanced(self):
        """AUTO + 5d → advanced → strong (cap 4)."""
        info = get_effective_pv_filter_info("auto", "5d")
        assert info.effective_level == "strong"
        assert info.max_candidates == 4
        assert info.is_auto is True
        assert info.resolved_preset == "advanced"

    def test_auto_with_4kanji_resolves_advanced(self):
        """AUTO + '4段' (kanji) → advanced → strong."""
        info = get_effective_pv_filter_info("auto", "4段")
        assert info.effective_level == "strong"
        assert info.is_auto is True
        assert info.resolved_preset == "advanced"

    def test_auto_with_5k_resolves_beginner(self):
        """AUTO + 5k → beginner → weak (cap 15)."""
        info = get_effective_pv_filter_info("auto", "5k")
        assert info.effective_level == "weak"
        assert info.max_candidates == 15
        assert info.is_auto is True
        assert info.resolved_preset == "beginner"

    def test_auto_with_empty_rank_uses_default_preset(self):
        """AUTO + empty rank → DEFAULT_SKILL_PRESET ('standard') → medium."""
        info = get_effective_pv_filter_info("auto", "")
        assert info.effective_level == "medium"
        assert info.max_candidates == 8
        assert info.is_auto is True
        assert info.resolved_preset == "standard"

    def test_none_level_treated_as_auto(self):
        """None / empty level falls back to AUTO (matches runtime)."""
        assert get_effective_pv_filter_info(None, "5d").effective_level == "strong"
        assert get_effective_pv_filter_info("", "5d").effective_level == "strong"
        assert get_effective_pv_filter_info(None, "").effective_level == "medium"

    def test_level_normalised_to_lowercase(self):
        """Level matching is case-insensitive + strip-tolerant (M6 bonus)."""
        assert get_effective_pv_filter_info("STRONG", "5d").effective_level == "strong"
        assert get_effective_pv_filter_info(" Medium ", "5d").effective_level == "medium"
        assert get_effective_pv_filter_info("  off  ", "5d").effective_level == "off"

    def test_unknown_level_returns_zero_cap(self):
        """Unknown level keeps the name but reports cap=0 (no cap known)."""
        info = get_effective_pv_filter_info("unknown_level", "5d")
        assert info.effective_level == "unknown_level"
        assert info.max_candidates == 0
        assert info.is_auto is False

    def test_returns_dataclass_instance(self):
        """Return type is the frozen dataclass."""
        info = get_effective_pv_filter_info("medium", "")
        assert isinstance(info, PVFilterDisplayInfo)
        # Frozen: cannot mutate
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            info.effective_level = "off"  # type: ignore[misc]

    def test_auto_pro_maps_to_expert(self):
        """AUTO + 9d (pro tier) → expert (Phase 246-D M2 differentiation)."""
        info = get_effective_pv_filter_info("auto", "9d")
        # 9d is mapped to "pro" preset, which now → "expert"
        assert info.effective_level == "expert"
        assert info.max_candidates == 3
        assert info.is_auto is True


# =============================================================================
# Phase 246-C: boundary / robustness tests (H5, M5, M7)
# =============================================================================


FIXTURE_NEGATIVE_POINTS_LOST = [
    # Phase 246-C (H5): pointsLost can be negative in pathological cases
    # (e.g., a search finds a better move than the one used for "root").
    # The filter must not crash and must still respect the order cap.
    {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
    {"order": 1, "pointsLost": -0.5, "pv": ["B2"], "move": "B2"},
    {"order": 2, "pointsLost": -2.0, "pv": ["C3", "C4"], "move": "C3"},
]


FIXTURE_DUPLICATE_ORDER = [
    # Phase 246-C (M7): multiple candidates sharing the same ``order``
    # value (e.g., all set to ADDITIONAL_MOVE_ORDER=999 from a merge).
    # The secondary sort key (pointsLost asc, visits desc) must make
    # the truncation deterministic.
    {"order": 999, "pointsLost": 1.0, "visits": 500, "pv": ["A1"], "move": "A1"},
    {"order": 999, "pointsLost": 0.5, "visits": 100, "pv": ["B2"], "move": "B2"},
    {"order": 999, "pointsLost": 0.5, "visits": 800, "pv": ["C3"], "move": "C3"},
    {"order": 999, "pointsLost": 0.0, "visits": 50, "pv": ["D4"], "move": "D4"},
]


FIXTURE_NONE_POINTS_LOST = [
    # Phase 246-C (H5): defensive against ``pointsLost=None`` (shouldn't
    # happen in practice but the filter must not crash).
    {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
    {"order": 1, "pointsLost": None, "pv": ["B2"], "move": "B2"},
    {"order": 2, "pv": ["C3"], "move": "C3"},  # missing key entirely
]


class TestFilterBoundaryRobustness:
    """Phase 246-C (H5): boundary / robustness tests for the filter."""

    def test_negative_points_lost_does_not_crash(self):
        """Negative pointsLost values must be filtered normally."""
        config = PV_FILTER_CONFIGS["medium"]  # max_points_lost=2.0
        result = filter_candidates_by_pv_complexity(FIXTURE_NEGATIVE_POINTS_LOST, config)
        # best_move (order=0) is always included
        assert any(c["order"] == 0 for c in result)
        # negative pointsLost < 2.0 → all 3 candidates pass the loss cap
        assert len(result) == 3

    def test_duplicate_order_secondary_sort_is_deterministic(self):
        """M7: When multiple candidates share the same order, the
        secondary sort (pointsLost asc, visits desc) must produce a
        stable, intuitive ordering."""
        config = PVFilterConfig(max_candidates=2, max_points_lost=10.0, max_pv_length=20)
        result = filter_candidates_by_pv_complexity(FIXTURE_DUPLICATE_ORDER, config)
        # After filter: best_move is None, so the 2 with lowest
        # pointsLost go through. Among ties, the one with more visits
        # wins. Expected order: D4 (loss 0.0, 50v), C3 (loss 0.5, 800v)
        assert len(result) == 2
        orders = [c["order"] for c in result]
        assert orders == [999, 999]  # best_move is None here
        # Lower pointsLost first; within same loss, higher visits first
        assert result[0]["pointsLost"] == 0.0
        assert result[1]["pointsLost"] == 0.5
        assert result[1]["visits"] == 800  # higher than B2's 100

    def test_duplicate_order_no_secondary_sort_was_ambiguous(self):
        """Sanity check: with M7's secondary key, the same input dict
        iteration order always produces the same output."""
        config = PVFilterConfig(max_candidates=2, max_points_lost=10.0, max_pv_length=20)
        # Run twice with same data — output must be identical
        r1 = filter_candidates_by_pv_complexity(FIXTURE_DUPLICATE_ORDER, config)
        r2 = filter_candidates_by_pv_complexity(FIXTURE_DUPLICATE_ORDER, config)
        assert [c["move"] for c in r1] == [c["move"] for c in r2]

    def test_none_points_lost_falls_back_to_zero(self):
        """H5: ``pointsLost=None`` (or missing) must be treated as 0.0
        so the candidate is *not* incorrectly excluded by loss > 0."""
        config = PV_FILTER_CONFIGS["strong"]  # max_points_lost=1.0
        result = filter_candidates_by_pv_complexity(FIXTURE_NONE_POINTS_LOST, config)
        # best_move (order=0) always passes
        # order=1 (pointsLost=None, treated as 0 ≤ 1.0) → pass
        # order=2 (missing key, treated as 0) → pass
        assert len(result) == 3
        assert result[0]["order"] == 0

    def test_single_candidate_passes_through(self):
        """A single candidate (only best_move) is always returned."""
        config = PV_FILTER_CONFIGS["medium"]
        result = filter_candidates_by_pv_complexity(
            [{"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"}], config
        )
        assert len(result) == 1
        assert result[0]["order"] == 0

    def test_best_move_with_extreme_pv_is_preserved(self):
        """M5 sanity: best_move is always included even if its PV is
        the only thing the filter would otherwise drop (H5 contract)."""
        # Very strict filter: pv length must be 0, points_lost must be 0
        config = PVFilterConfig(max_candidates=10, max_points_lost=0.0, max_pv_length=1)
        # best_move has a 50-step PV — would be dropped by pv_length filter
        # but is preserved by the best_move special-quota contract.
        candidates = [
            {"order": 0, "pointsLost": 0.0, "pv": ["A1"] * 50, "move": "A1"},
            {"order": 1, "pointsLost": 5.0, "pv": ["B2"], "move": "B2"},
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        assert len(result) == 1
        assert result[0]["order"] == 0
        # The PV is NOT clipped here — clipping is the GUI's job
        # (M5: draw_pv / active_pv_moves). The filter just preserves
        # the dict as-is.
        assert len(result[0]["pv"]) == 50

    def test_very_large_visits_does_not_crash(self):
        """H5: a candidate with a billion visits must not break the
        secondary sort (we negate it for the sort key)."""
        config = PVFilterConfig(max_candidates=5, max_points_lost=10.0, max_pv_length=20)
        candidates = [
            {"order": 999, "pointsLost": 1.0, "visits": 10**9, "pv": ["A1"], "move": "A1"},
            {"order": 999, "pointsLost": 1.0, "visits": 1, "pv": ["B2"], "move": "B2"},
            {"order": 999, "pointsLost": 0.0, "visits": 100, "pv": ["C3"], "move": "C3"},
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        # D4 (loss 0.0) first, then the two loss-1.0 ones in visit desc
        assert [c["move"] for c in result] == ["C3", "A1", "B2"]

    def test_empty_pv_does_not_crash(self):
        """H5: an empty PV list must not cause errors (len(0) = 0)."""
        config = PV_FILTER_CONFIGS["strong"]  # max_pv_length=6
        result = filter_candidates_by_pv_complexity(
            [
                {"order": 0, "pointsLost": 0.0, "pv": [], "move": "A1"},
                {"order": 1, "pointsLost": 0.5, "pv": [], "move": "B2"},
            ],
            config,
        )
        # Both pass: best_move is always kept, and 0-length PV is <= 6
        assert len(result) == 2


# =============================================================================
# Phase 246-D (L1): loss_metric (pointsLost vs relativePointsLost)
# =============================================================================


FIXTURE_RELATIVE_LOSS = [
    # best_move is order=0, always kept.
    # Others carry both pointsLost (absolute, next-player view) and
    # relativePointsLost (gap to best move). The two diverge in
    # mid-game positions where the side-to-play already has a lead.
    {"order": 0, "pointsLost": 0.0, "relativePointsLost": 0.0, "pv": ["A1"], "move": "A1"},
    {"order": 1, "pointsLost": 0.5, "relativePointsLost": 0.5, "pv": ["B2"], "move": "B2"},
    {"order": 2, "pointsLost": 1.5, "relativePointsLost": 0.2, "pv": ["C3"], "move": "C3"},
    {"order": 3, "pointsLost": 0.8, "relativePointsLost": 2.0, "pv": ["D4"], "move": "D4"},
]


class TestFilterLossMetric:
    """Phase 246-D (L1): ``PVFilterConfig.loss_metric`` selects the field
    the loss threshold compares against."""

    def test_default_metric_is_points_lost(self):
        """Backwards compatibility: default loss_metric is 'pointsLost'."""
        config = PV_FILTER_CONFIGS["strong"]
        assert config.loss_metric == "pointsLost"

    def test_points_lost_metric_filters_by_absolute(self):
        config = PVFilterConfig(
            max_candidates=10, max_points_lost=1.0, max_pv_length=20, loss_metric="pointsLost"
        )
        result = filter_candidates_by_pv_complexity(FIXTURE_RELATIVE_LOSS, config)
        # best_move (order=0) always kept
        # order=1 (pointsLost=0.5 ≤ 1.0) kept
        # order=2 (pointsLost=1.5 > 1.0) DROPPED
        # order=3 (pointsLost=0.8 ≤ 1.0) kept
        assert len(result) == 3
        assert [c["order"] for c in result] == [0, 1, 3]

    def test_relative_points_lost_metric_filters_by_gap(self):
        config = PVFilterConfig(
            max_candidates=10, max_points_lost=1.0, max_pv_length=20, loss_metric="relativePointsLost"
        )
        result = filter_candidates_by_pv_complexity(FIXTURE_RELATIVE_LOSS, config)
        # best_move (order=0) always kept
        # order=1 (relative=0.5 ≤ 1.0) kept
        # order=2 (relative=0.2 ≤ 1.0) KEPT (this is the point of L1)
        # order=3 (relative=2.0 > 1.0) DROPPED
        assert len(result) == 3
        assert [c["order"] for c in result] == [0, 1, 2]

    def test_unknown_metric_falls_back_to_points_lost(self):
        """Defensive: an unrecognised metric name falls back to the
        default (pointsLost) rather than dropping all candidates."""
        config = PVFilterConfig(
            max_candidates=10, max_points_lost=1.0, max_pv_length=20, loss_metric="mystery_metric"
        )
        # The function uses getattr with default, so unknown key reads
        # ``None`` from each candidate, gets coerced to 0.0 — i.e. all
        # candidates pass the loss threshold. This is the same
        # "defensive" behavior the None-case test in 246-C established.
        result = filter_candidates_by_pv_complexity(FIXTURE_RELATIVE_LOSS, config)
        # All 4 pass (0 <= 1.0 for every candidate's missing key)
        assert len(result) == 4

    def test_relative_metric_keeps_best_move_zero(self):
        """Sanity: best_move (order=0) always passes regardless of metric."""
        config = PVFilterConfig(
            max_candidates=10, max_points_lost=0.0, max_pv_length=20, loss_metric="relativePointsLost"
        )
        result = filter_candidates_by_pv_complexity(FIXTURE_RELATIVE_LOSS, config)
        # Only best_move survives the very strict 0.0 threshold
        assert len(result) == 1
        assert result[0]["order"] == 0
