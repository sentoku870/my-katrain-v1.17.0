# tests/test_ownership_cluster.py
"""Phase 81: Ownership差分クラスタ抽出のテスト。"""

from __future__ import annotations

import pytest

from katrain.core.analysis.board_context import BoardArea, OwnershipContext
from katrain.core.analysis.ownership_cluster import (
    ClusterType,
    ClusterExtractionConfig,
    ClusterExtractionResult,
    OwnershipCluster,
    OwnershipDelta,
    compute_ownership_delta,
    extract_clusters,
    extract_clusters_from_nodes,
    _AREA_PRIORITY,
    _AREA_PRIORITY_DEFAULT,
    _compute_primary_area,
)


# =============================================================================
# Test Helpers
# =============================================================================


def make_ctx(
    grid: list[list[float]] | None,
    board_size: tuple[int, int],
    score_stdev: float | None = None,
) -> OwnershipContext:
    """テスト用OwnershipContext生成ヘルパー。

    Args:
        grid: ownership_grid（grid[row][col]形式）
        board_size: (width, height)
        score_stdev: KataGoのscoreStdev（通常None）

    Note:
        OwnershipContextコンストラクタ引数順序:
        OwnershipContext(ownership_grid, score_stdev, board_size)
    """
    return OwnershipContext(
        ownership_grid=grid,
        score_stdev=score_stdev,
        board_size=board_size,
    )


def make_delta(
    parent_grid: list[list[float]],
    child_grid: list[list[float]],
    board_size: tuple[int, int],
) -> OwnershipDelta:
    """テスト用OwnershipDelta生成ヘルパー。"""
    parent_ctx = make_ctx(parent_grid, board_size)
    child_ctx = make_ctx(child_grid, board_size)
    delta = compute_ownership_delta(parent_ctx, child_ctx)
    assert delta is not None, "Delta should not be None for valid grids"
    return delta


# =============================================================================
# AC1: Coordinate System Tests
# =============================================================================


def test_coordinate_system_bottom_left_origin():
    """座標系: (0,0)=左下、row増加=上方向"""
    # 2x2グリッド: 左下(0,0)=0.1, 右下(1,0)=0.2, 左上(0,1)=0.3, 右上(1,1)=0.4
    # grid[row][col]形式: grid[0]=row0(下辺), grid[1]=row1(上辺)
    parent_grid = [[0.0, 0.0], [0.0, 0.0]]
    child_grid = [[0.1, 0.2], [0.3, 0.4]]

    delta = make_delta(parent_grid, child_grid, (2, 2))

    assert delta.get_delta_at(0, 0) == pytest.approx(0.1)  # 左下
    assert delta.get_delta_at(1, 0) == pytest.approx(0.2)  # 右下
    assert delta.get_delta_at(0, 1) == pytest.approx(0.3)  # 左上
    assert delta.get_delta_at(1, 1) == pytest.approx(0.4)  # 右上


def test_get_delta_at_out_of_bounds():
    """範囲外座標はNoneを返す"""
    parent_grid = [[0.0, 0.0], [0.0, 0.0]]
    child_grid = [[0.1, 0.2], [0.3, 0.4]]
    delta = make_delta(parent_grid, child_grid, (2, 2))

    assert delta.get_delta_at(-1, 0) is None
    assert delta.get_delta_at(0, -1) is None
    assert delta.get_delta_at(2, 0) is None
    assert delta.get_delta_at(0, 2) is None


# =============================================================================
# AC2: Delta Sign Convention Tests
# =============================================================================


def test_delta_sign_convention():
    """Delta符号規約のロックテスト"""
    # 2x2盤面、座標系: (col, row), 原点=左下
    # grid[row][col]形式
    # 親: 全て中立 (0.0)
    parent_grid = [[0.0, 0.0], [0.0, 0.0]]
    # 子: 左上(0,1)が黒に(+0.8)、右下(1,0)が白に(-0.6)
    # grid[0][1] = row0,col1 = (1,0) = 右下 → -0.6
    # grid[1][0] = row1,col0 = (0,1) = 左上 → +0.8
    child_grid = [[0.0, -0.6], [0.8, 0.0]]

    delta = make_delta(parent_grid, child_grid, (2, 2))

    # delta = child - parent
    assert delta.get_delta_at(0, 1) == pytest.approx(0.8)  # 左上: 黒に有利化
    assert delta.get_delta_at(1, 0) == pytest.approx(-0.6)  # 右下: 白に有利化

    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(delta_threshold=0.1, min_cluster_size=1),
    )

    black_clusters = [
        c for c in result.clusters if c.cluster_type == ClusterType.TO_BLACK
    ]
    white_clusters = [
        c for c in result.clusters if c.cluster_type == ClusterType.TO_WHITE
    ]

    assert len(black_clusters) == 1
    assert len(white_clusters) == 1
    assert (0, 1) in black_clusters[0].coords  # 左上
    assert (1, 0) in white_clusters[0].coords  # 右下


# =============================================================================
# AC3: Neutral Cluster Exclusion Tests
# =============================================================================


def test_neutral_cluster_excluded():
    """sum_delta≈0のクラスタは除外される"""
    # 隣接セル(0,0)と(1,0): +0.5と-0.5で相殺 → sum=0
    # grid[row][col]形式
    parent_grid = [[0.0, 0.0], [0.0, 0.0]]
    child_grid = [[0.5, -0.5], [0.0, 0.0]]  # row0: (0,0)=+0.5, (1,0)=-0.5

    delta = make_delta(parent_grid, child_grid, (2, 2))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=1, use_8_neighbors=False
        ),
    )
    # (0,0)と(1,0)は4方向で隣接 → 1クラスタだがsum=0で除外
    assert len(result.clusters) == 0


# =============================================================================
# AC4: max_abs_delta Tests
# =============================================================================


def test_max_abs_delta_uses_absolute_value():
    """max_abs_deltaは絶対値の最大を返す（負の値も正しく処理）"""
    # 隣接セル: (0,0)=+0.2, (1,0)=-0.9 → max_abs_delta = 0.9
    parent_grid = [[0.0, 0.0], [0.0, 0.0]]
    child_grid = [[0.2, -0.9], [0.0, 0.0]]  # row0: (0,0)=+0.2, (1,0)=-0.9

    delta = make_delta(parent_grid, child_grid, (2, 2))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=1, use_8_neighbors=False
        ),
    )

    # (0,0)と(1,0)は隣接するが、符号が異なるため別クラスタ
    # ここでは白クラスタ（-0.9）のmax_abs_deltaを検証
    white_clusters = [
        c for c in result.clusters if c.cluster_type == ClusterType.TO_WHITE
    ]
    assert len(white_clusters) == 1
    assert white_clusters[0].max_abs_delta == pytest.approx(0.9)


def test_max_abs_delta_mixed_signs_in_cluster():
    """クラスタ内に正負混在時もmax_abs_deltaは絶対値最大"""
    # 3セル隣接: (0,0)=+0.3, (1,0)=+0.5, (2,0)=-0.2
    # sum=+0.6 → TO_BLACK, max_abs_delta = 0.5
    parent_grid = [[0.0, 0.0, 0.0]]
    child_grid = [[0.3, 0.5, -0.2]]

    delta = make_delta(parent_grid, child_grid, (3, 1))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=1, use_8_neighbors=False
        ),
    )

    assert len(result.clusters) == 1
    cluster = result.clusters[0]
    assert cluster.cluster_type == ClusterType.TO_BLACK  # sum > 0
    assert cluster.max_abs_delta == pytest.approx(0.5)


# =============================================================================
# AC5-7: primary_area Tests
# =============================================================================


def test_primary_area_tiebreak_corner_wins():
    """同数ならCORNER > EDGE > CENTER"""
    # 1 CORNER + 1 EDGE（同数）
    coords = frozenset(
        [
            (0, 0),  # CORNER (左下隅)
            (0, 10),  # EDGE (左辺中央付近)
        ]
    )
    area = _compute_primary_area(coords, (19, 19))
    assert area == BoardArea.CORNER  # タイブレークでCORNER


def test_primary_area_tiebreak_edge_over_center():
    """同数ならEDGE > CENTER"""
    coords = frozenset(
        [
            (0, 10),  # EDGE
            (9, 9),  # CENTER
        ]
    )
    area = _compute_primary_area(coords, (19, 19))
    assert area == BoardArea.EDGE


def test_primary_area_no_keyerror_on_all_areas():
    """全BoardArea値でKeyErrorが発生しないことを確認"""
    # 全enum値に対して優先度取得がエラーにならないことを確認
    for area in BoardArea:
        priority = _AREA_PRIORITY.get(area, _AREA_PRIORITY_DEFAULT)
        assert isinstance(priority, int)


def test_primary_area_empty_coords():
    """空の座標セット→None"""
    coords: frozenset = frozenset()
    area = _compute_primary_area(coords, (19, 19))
    assert area is None


# =============================================================================
# AC8-9: Cluster Ordering Tests
# =============================================================================


def test_clusters_ordering_invariants():
    """クラスタ順序がソートキー規則に従うことを検証"""
    # 複数クラスタを生成するグリッド
    # 3x3: 左下(0,0)=+0.5(黒), 右上(2,2)=-0.8(白), 中央(1,1)=+0.3(黒)
    parent_grid = [[0.0] * 3 for _ in range(3)]
    child_grid = [
        [0.5, 0.0, 0.0],  # row0: (0,0)=+0.5
        [0.0, 0.3, 0.0],  # row1: (1,1)=+0.3
        [0.0, 0.0, -0.8],  # row2: (2,2)=-0.8
    ]

    delta = make_delta(parent_grid, child_grid, (3, 3))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(delta_threshold=0.1, min_cluster_size=1),
    )

    # ソートキーの不変条件を検証
    _TYPE_ORDER = {ClusterType.TO_BLACK: 0, ClusterType.TO_WHITE: 1}

    for i in range(len(result.clusters) - 1):
        curr = result.clusters[i]
        next_ = result.clusters[i + 1]

        curr_key = (
            _TYPE_ORDER[curr.cluster_type],
            -curr.max_abs_delta,
            min(curr.coords),
        )
        next_key = (
            _TYPE_ORDER[next_.cluster_type],
            -next_.max_abs_delta,
            min(next_.coords),
        )

        assert curr_key <= next_key, f"Ordering violation at index {i}"


def test_clusters_grouped_by_type():
    """TO_BLACKクラスタがTO_WHITEより先に来る"""
    parent_grid = [[0.0] * 3 for _ in range(3)]
    child_grid = [
        [0.5, 0.0, -0.3],  # (0,0)=+0.5(黒), (2,0)=-0.3(白)
        [0.0, 0.0, 0.0],
        [-0.4, 0.0, 0.6],  # (0,2)=-0.4(白), (2,2)=+0.6(黒)
    ]

    delta = make_delta(parent_grid, child_grid, (3, 3))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(delta_threshold=0.1, min_cluster_size=1),
    )

    saw_white = False
    for cluster in result.clusters:
        if cluster.cluster_type == ClusterType.TO_WHITE:
            saw_white = True
        elif cluster.cluster_type == ClusterType.TO_BLACK:
            assert not saw_white, "TO_BLACK found after TO_WHITE"


# =============================================================================
# AC10-13: Error Handling Tests
# =============================================================================


def test_board_size_mismatch_raises_valueerror():
    """board_size不一致でValueError"""
    grid_9x9 = [[0.0] * 9 for _ in range(9)]
    grid_19x19 = [[0.0] * 19 for _ in range(19)]
    parent = make_ctx(grid_9x9, (9, 9))
    child = make_ctx(grid_19x19, (19, 19))
    with pytest.raises(ValueError, match="Board size mismatch"):
        compute_ownership_delta(parent, child)


def test_grid_row_count_mismatch_raises_valueerror():
    """grid行数不整合でValueError"""
    # board_size=(2,2)だがgridは3行
    wrong_grid = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
    valid_grid = [[0.0, 0.0], [0.0, 0.0]]
    parent = make_ctx(wrong_grid, (2, 2))
    child = make_ctx(valid_grid, (2, 2))
    with pytest.raises(ValueError, match="row count mismatch"):
        compute_ownership_delta(parent, child)


def test_grid_column_count_mismatch_raises_valueerror():
    """grid列数不整合でValueError"""
    # 行ごとに列数が異なる
    wrong_grid = [[0.0, 0.0], [0.0]]  # row 1 has only 1 col
    valid_grid = [[0.0, 0.0], [0.0, 0.0]]
    parent = make_ctx(wrong_grid, (2, 2))
    child = make_ctx(valid_grid, (2, 2))
    with pytest.raises(ValueError, match="column count mismatch at row 1"):
        compute_ownership_delta(parent, child)


def test_none_ownership_returns_none():
    """ownership=NoneでNone返却"""
    valid_grid = [[0.0, 0.0], [0.0, 0.0]]
    parent = make_ctx(None, (2, 2))
    child = make_ctx(valid_grid, (2, 2))
    assert compute_ownership_delta(parent, child) is None


# =============================================================================
# AC14-15: Neighbor Connectivity Tests
# =============================================================================


def test_4_neighbors_no_diagonal():
    """4方向では斜め接続しない"""
    # (0,0)と(1,1)は斜め隣接のみ
    parent_grid = [[0.0, 0.0], [0.0, 0.0]]
    child_grid = [[0.5, 0.0], [0.0, 0.5]]  # (0,0)=+0.5, (1,1)=+0.5

    delta = make_delta(parent_grid, child_grid, (2, 2))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=1, use_8_neighbors=False
        ),
    )
    assert len(result.clusters) == 2  # 別々のクラスタ


def test_8_neighbors_with_diagonal():
    """8方向では斜め接続する"""
    # (0,0)と(1,1)は斜め隣接
    parent_grid = [[0.0, 0.0], [0.0, 0.0]]
    child_grid = [[0.5, 0.0], [0.0, 0.5]]  # (0,0)=+0.5, (1,1)=+0.5

    delta = make_delta(parent_grid, child_grid, (2, 2))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=1, use_8_neighbors=True
        ),
    )
    assert len(result.clusters) == 1  # 1つのクラスタ


# =============================================================================
# AC16: min_cluster_size Tests
# =============================================================================


def test_min_cluster_size_filters_small_clusters():
    """min_cluster_size未満のクラスタは除外される"""
    # 3x1グリッド: 2セル隣接クラスタ + 1セル単独
    # (0,0)=+0.5, (1,0)=+0.5 → 2セルクラスタ
    # (2,0) = 0.0 → 変動なし
    parent_grid = [[0.0, 0.0, 0.0]]
    child_grid = [[0.5, 0.5, 0.0]]

    delta = make_delta(parent_grid, child_grid, (3, 1))

    # min_cluster_size=3 → 2セルクラスタは除外
    result_3 = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=3, use_8_neighbors=False
        ),
    )
    assert len(result_3.clusters) == 0

    # min_cluster_size=2 → 2セルクラスタは含まれる
    result_2 = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=2, use_8_neighbors=False
        ),
    )
    assert len(result_2.clusters) == 1
    assert result_2.clusters[0].cell_count == 2


def test_min_cluster_size_boundary_exact():
    """ちょうどmin_cluster_sizeのクラスタは含まれる"""
    # 3セル隣接クラスタ
    parent_grid = [[0.0, 0.0, 0.0]]
    child_grid = [[0.5, 0.5, 0.5]]

    delta = make_delta(parent_grid, child_grid, (3, 1))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=3, use_8_neighbors=False
        ),
    )
    assert len(result.clusters) == 1
    assert result.clusters[0].cell_count == 3


# =============================================================================
# AC17: delta_threshold Boundary Tests
# =============================================================================


def test_delta_threshold_boundary_inclusive():
    """delta_thresholdちょうどの値は変動セルとして扱われる"""
    # threshold=0.15に対して、ちょうど0.15のdelta
    parent_grid = [[0.0, 0.0]]
    child_grid = [[0.15, 0.14]]  # (0,0)=0.15(境界上), (1,0)=0.14(未満)

    delta = make_delta(parent_grid, child_grid, (2, 1))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.15, min_cluster_size=1, use_8_neighbors=False
        ),
    )

    # (0,0)のみが変動セルとして扱われる
    assert len(result.clusters) == 1
    assert result.clusters[0].cell_count == 1
    assert (0, 0) in result.clusters[0].coords


def test_delta_threshold_boundary_negative():
    """負のdeltaも絶対値で判定される"""
    parent_grid = [[0.0, 0.0]]
    child_grid = [[-0.15, -0.14]]  # (0,0)=-0.15(境界上), (1,0)=-0.14(未満)

    delta = make_delta(parent_grid, child_grid, (2, 1))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.15, min_cluster_size=1, use_8_neighbors=False
        ),
    )

    assert len(result.clusters) == 1
    assert result.clusters[0].cell_count == 1
    assert (0, 0) in result.clusters[0].coords


# =============================================================================
# AC18-19: Import Tests
# =============================================================================


def test_import_from_module_directly():
    """モジュールから直接インポートできること"""
    # この単純なインポートが成功すれば循環importは発生していない
    from katrain.core.analysis.ownership_cluster import (
        ClusterType,
        OwnershipDelta,
        OwnershipCluster,
        ClusterExtractionConfig,
        ClusterExtractionResult,
        compute_ownership_delta,
        extract_clusters,
        extract_clusters_from_nodes,
    )

    # 基本的な動作確認
    assert ClusterType.TO_BLACK.value == "to_black"


def test_import_from_package():
    """パッケージ経由でインポートできること"""
    from katrain.core.analysis import (
        ClusterType,
        extract_clusters,
    )

    assert ClusterType.TO_BLACK.value == "to_black"


# =============================================================================
# Additional Tests
# =============================================================================


def test_cluster_to_dict():
    """OwnershipCluster.to_dict()が正しく動作する"""
    parent_grid = [[0.0, 0.0, 0.0]]
    child_grid = [[0.5, 0.5, 0.5]]

    delta = make_delta(parent_grid, child_grid, (3, 1))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(
            delta_threshold=0.1, min_cluster_size=1, use_8_neighbors=False
        ),
    )

    assert len(result.clusters) == 1
    cluster = result.clusters[0]
    d = cluster.to_dict()

    assert "coords" in d
    assert "cluster_type" in d
    assert d["cluster_type"] == "to_black"
    assert d["cell_count"] == 3


def test_result_statistics():
    """ClusterExtractionResultの統計が正しい"""
    parent_grid = [[0.0] * 3 for _ in range(3)]
    child_grid = [
        [0.5, 0.0, -0.3],  # (0,0)=+0.5(黒), (2,0)=-0.3(白)
        [0.0, 0.0, 0.0],
        [-0.4, 0.0, 0.6],  # (0,2)=-0.4(白), (2,2)=+0.6(黒)
    ]

    delta = make_delta(parent_grid, child_grid, (3, 3))
    result = extract_clusters(
        delta,
        config=ClusterExtractionConfig(delta_threshold=0.1, min_cluster_size=1),
    )

    # 4つの変動セル
    assert result.total_changed_cells == 4

    # 2つの黒クラスタ、2つの白クラスタ
    assert result.black_gain_clusters == 2
    assert result.white_gain_clusters == 2


def test_default_config():
    """デフォルト設定が正しく適用される"""
    parent_grid = [[0.0] * 5 for _ in range(5)]
    # 大きな変動を作る（min_cluster_size=3をパスするため）
    child_grid = [
        [0.5, 0.5, 0.5, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
    ]

    delta = make_delta(parent_grid, child_grid, (5, 5))
    result = extract_clusters(delta)  # configなし

    # デフォルトのmin_cluster_size=3
    assert result.config.min_cluster_size == 3
    assert result.config.delta_threshold == 0.15
    assert result.config.use_8_neighbors is False
    assert len(result.clusters) == 1  # 3セルクラスタが1つ
