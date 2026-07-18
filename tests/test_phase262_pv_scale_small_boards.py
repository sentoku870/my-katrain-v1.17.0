"""Phase 262 (I-21): PV filter の board_size scaling 汎用化

``_scale_for_board`` の下限ガードを ``< 5`` から ``< 2`` に緩和し、
5路/7路の超小型盤でも同じ linear scaling を使えるようにする。

このテストは:
- 5路/7路で scaling が適用される (scaling されないパスに落ちない)
- 5路/7路で返される ``max_pv_length`` が min 1 保証される
- 既存の 9/13/19 路挙動は変わらない (回帰なし)
- 不正な board_size (1, 0, None, 26) は元の config を返す (回帰なし)
"""

from katrain.core.analysis.logic_pv import PV_FILTER_CONFIGS, _scale_for_board


def test_scale_5_lane() -> None:
    """5路: scale = 5/19 ≈ 0.263、max_pv_length は min 1 保証。"""
    config = PV_FILTER_CONFIGS["medium"]
    scaled = _scale_for_board(config, board_size=5)
    assert scaled is not None
    assert scaled is not config, "5路では元の config をそのまま返してはいけない"
    # max_pv_length が min 1 以上に丸められる
    assert scaled.max_pv_length >= 1
    # 19路の max_pv_length より小さい
    assert scaled.max_pv_length <= config.max_pv_length


def test_scale_7_lane() -> None:
    """7路: scale = 7/19 ≈ 0.368。"""
    config = PV_FILTER_CONFIGS["medium"]
    scaled = _scale_for_board(config, board_size=7)
    assert scaled is not None
    assert scaled is not config
    assert scaled.max_pv_length >= 1
    assert scaled.max_pv_length <= config.max_pv_length


def test_scale_5_vs_7_monotonic() -> None:
    """5路は 7路より小さいか等しい max_pv_length。"""
    config = PV_FILTER_CONFIGS["medium"]
    s5 = _scale_for_board(config, board_size=5)
    s7 = _scale_for_board(config, board_size=7)
    assert s5 is not None and s7 is not None
    assert s5.max_pv_length <= s7.max_pv_length


# -------------------------------------------------------------------
# 既存挙動の回帰テスト
# -------------------------------------------------------------------


def test_scale_9_lane_unchanged() -> None:
    """9路は Phase 246-D のまま。"""
    config = PV_FILTER_CONFIGS["medium"]
    scaled = _scale_for_board(config, board_size=9)
    assert scaled is not None
    # 9/19 ≈ 0.474 → round → max(1, ...) 保証
    assert 1 <= scaled.max_pv_length <= config.max_pv_length


def test_scale_13_lane_unchanged() -> None:
    """13路は Phase 246-D のまま。"""
    config = PV_FILTER_CONFIGS["medium"]
    scaled = _scale_for_board(config, board_size=13)
    assert scaled is not None
    assert 1 <= scaled.max_pv_length <= config.max_pv_length


def test_scale_19_lane_canonical() -> None:
    """19路は canonical なので元の config がそのまま返る。"""
    config = PV_FILTER_CONFIGS["medium"]
    scaled = _scale_for_board(config, board_size=19)
    assert scaled is config


# -------------------------------------------------------------------
# 不正な board_size の挙動
# -------------------------------------------------------------------


def test_scale_rejects_too_small() -> None:
    """1路以下は scaling しない (元の config パススルー)。"""
    config = PV_FILTER_CONFIGS["medium"]
    assert _scale_for_board(config, board_size=1) is config
    assert _scale_for_board(config, board_size=0) is config


def test_scale_rejects_too_large() -> None:
    """26路以上は scaling しない (元の config パススルー)。"""
    config = PV_FILTER_CONFIGS["medium"]
    assert _scale_for_board(config, board_size=26) is config
    assert _scale_for_board(config, board_size=99) is config


def test_scale_rejects_none_and_falsy() -> None:
    """None / 0 / False は元の config パススルー。"""
    config = PV_FILTER_CONFIGS["medium"]
    assert _scale_for_board(config, board_size=None) is config
    assert _scale_for_board(config, board_size=0) is config


# -------------------------------------------------------------------
# 不変条件: 5/7 路でも max_candidates / max_points_lost は不変
# -------------------------------------------------------------------


def test_scale_preserves_loss_and_cap_for_small_boards() -> None:
    """scaling は max_pv_length のみ。他フィールドは触らない。"""
    config = PV_FILTER_CONFIGS["medium"]
    s5 = _scale_for_board(config, board_size=5)
    s7 = _scale_for_board(config, board_size=7)
    assert s5 is not None and s7 is not None
    # cap と loss は不変
    assert s5.max_candidates == config.max_candidates
    assert s5.max_points_lost == config.max_points_lost
    assert s7.max_candidates == config.max_candidates
    assert s7.max_points_lost == config.max_points_lost


# -------------------------------------------------------------------
# 5路未満は依然スキップ (1路は物理的に碁盤として機能しない)
# -------------------------------------------------------------------


def test_scale_2_lane_in_range() -> None:
    """2路は下限 (>= 2) に入るので scaling される。"""
    config = PV_FILTER_CONFIGS["medium"]
    scaled = _scale_for_board(config, board_size=2)
    assert scaled is not config
    assert scaled.max_pv_length >= 1
