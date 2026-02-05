# katrain/core/analysis/ownership_cluster.py
"""Phase 81: Ownership差分クラスタ抽出MVP.

ownership差分から「変動の塊（クラスタ）」を抽出する。
Phase 80のboard_context.pyを基盤とし、BFSで隣接変動セルをグループ化する。
"""

from collections import Counter, deque
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

# 直接インポート（循環import防止）
from katrain.core.analysis.board_context import (
    BoardArea,
    OwnershipContext,
    classify_area,
    extract_ownership_context,
)

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode


# =====================================================================
# Constants
# =====================================================================

# 中立クラスタ除外のデフォルト閾値
DEFAULT_NEUTRAL_EPSILON = 1e-4


# =====================================================================
# Enums
# =====================================================================


class ClusterType(StrEnum):
    """クラスタの種類（黒有利/白有利）。"""

    TO_BLACK = "to_black"  # sum_delta > 0: 黒に有利化
    TO_WHITE = "to_white"  # sum_delta < 0: 白に有利化


# クラスタタイプの明示的ソート順序（文字列に依存しない）
# Note: ClusterType定義の後に配置（NameError防止）
_CLUSTER_TYPE_ORDER: dict[ClusterType, int] = {
    ClusterType.TO_BLACK: 0,
    ClusterType.TO_WHITE: 1,
}

# BoardArea優先度（タイブレーク用）
_AREA_PRIORITY: dict[BoardArea, int] = {
    BoardArea.CORNER: 0,  # 最優先
    BoardArea.EDGE: 1,
    BoardArea.CENTER: 2,
}
_AREA_PRIORITY_DEFAULT = 99  # 将来追加されるAreaのフォールバック


# =====================================================================
# Data Models
# =====================================================================


@dataclass(frozen=True)
class OwnershipDelta:
    """2ノード間のownership差分。"""

    delta_grid: tuple[tuple[float, ...], ...]  # immutable, grid[row][col]
    board_size: tuple[int, int]  # (width, height)
    parent_context: OwnershipContext
    child_context: OwnershipContext

    def get_delta_at(self, col: int, row: int) -> float | None:
        """指定座標(col, row)の差分値を取得。

        Args:
            col: 列番号（x座標）。0=左端。
            row: 行番号（y座標）。0=下辺。

        Returns:
            差分値。範囲外→None。
        """
        width, height = self.board_size
        if not (0 <= col < width and 0 <= row < height):
            return None
        return self.delta_grid[row][col]


@dataclass(frozen=True)
class OwnershipCluster:
    """ownership変動のクラスタ。"""

    coords: frozenset[tuple[int, int]]  # (col, row)のセット
    cluster_type: ClusterType
    sum_delta: float  # 符号付き合計
    avg_delta: float  # 符号付き平均
    max_abs_delta: float  # 絶対値の最大
    primary_area: BoardArea | None
    cell_count: int

    def to_dict(self) -> dict[str, Any]:
        """辞書形式に変換（シリアライズ用）。"""
        return {
            "coords": sorted(self.coords),
            "cluster_type": self.cluster_type.value,
            "sum_delta": self.sum_delta,
            "avg_delta": self.avg_delta,
            "max_abs_delta": self.max_abs_delta,
            "primary_area": self.primary_area.value if self.primary_area else None,
            "cell_count": self.cell_count,
        }


@dataclass(frozen=True)
class ClusterExtractionConfig:
    """クラスタ抽出の設定。

    Attributes:
        delta_threshold: 個別セルの変動閾値（default: 0.15）。
            abs(delta) >= delta_threshold のセルを変動セルとして扱う。
        min_cluster_size: 最小クラスタサイズ（default: 3）。
            1-2セルの変動は除外される。これらの単点変動は
            Phase 82の分類ロジックで別途評価される可能性がある。
        use_8_neighbors: 8方向隣接（default: False=4方向）。
            囲碁の石の連結は4方向なのでデフォルトは4方向。
        neutral_epsilon: 中立判定閾値（default: 1e-4）。
            abs(sum_delta) < neutral_epsilon のクラスタは除外。
    """

    delta_threshold: float = 0.15
    min_cluster_size: int = 3
    use_8_neighbors: bool = False
    neutral_epsilon: float = DEFAULT_NEUTRAL_EPSILON


@dataclass(frozen=True)
class ClusterExtractionResult:
    """クラスタ抽出結果。"""

    clusters: tuple[OwnershipCluster, ...]  # ソート済み
    total_changed_cells: int  # フィルタ前の変動セル数
    black_gain_clusters: int  # TO_BLACKクラスタ数
    white_gain_clusters: int  # TO_WHITEクラスタ数
    config: ClusterExtractionConfig


# =====================================================================
# Internal Helpers
# =====================================================================


def _validate_grid_shape(
    grid: list[list[float]],
    board_size: tuple[int, int],
    label: str,
) -> None:
    """グリッド形状を検証。不整合ならValueError。"""
    width, height = board_size
    if len(grid) != height:
        raise ValueError(f"{label} grid row count mismatch: expected {height}, got {len(grid)}")
    for row_idx, row in enumerate(grid):
        if len(row) != width:
            raise ValueError(f"{label} grid column count mismatch at row {row_idx}: expected {width}, got {len(row)}")


def _is_changed_cell(delta: float, threshold: float) -> bool:
    """セルが変動セルかを判定。閾値ちょうどは含む。"""
    return abs(delta) >= threshold


def _get_neighbors(
    col: int,
    row: int,
    width: int,
    height: int,
    use_8: bool,
) -> list[tuple[int, int]]:
    """隣接座標を取得。"""
    # 4方向
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    if use_8:
        # 8方向に拡張
        directions.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])

    neighbors = []
    for dc, dr in directions:
        nc, nr = col + dc, row + dr
        if 0 <= nc < width and 0 <= nr < height:
            neighbors.append((nc, nr))
    return neighbors


def _bfs_cluster(
    start_col: int,
    start_row: int,
    delta_grid: tuple[tuple[float, ...], ...],
    visited: set[tuple[int, int]],
    threshold: float,
    use_8: bool,
    width: int,
    height: int,
) -> frozenset[tuple[int, int]]:
    """BFSで連結成分を抽出。"""
    cluster_coords = set()
    queue = deque([(start_col, start_row)])
    visited.add((start_col, start_row))
    cluster_coords.add((start_col, start_row))

    while queue:
        col, row = queue.popleft()
        for nc, nr in _get_neighbors(col, row, width, height, use_8):
            if (nc, nr) not in visited:
                delta = delta_grid[nr][nc]
                if _is_changed_cell(delta, threshold):
                    visited.add((nc, nr))
                    cluster_coords.add((nc, nr))
                    queue.append((nc, nr))

    return frozenset(cluster_coords)


def _compute_cluster_stats(
    coords: frozenset[tuple[int, int]],
    delta_grid: tuple[tuple[float, ...], ...],
) -> tuple[float, float, float]:
    """sum_delta, avg_delta, max_abs_deltaを計算。"""
    deltas = [delta_grid[r][c] for c, r in coords]
    sum_delta = sum(deltas)
    avg_delta = sum_delta / len(deltas)
    max_abs_delta = max(abs(d) for d in deltas)
    return sum_delta, avg_delta, max_abs_delta


def _determine_cluster_type(sum_delta: float, epsilon: float) -> ClusterType | None:
    """クラスタタイプを判定。中立→None（除外対象）。

    Args:
        sum_delta: クラスタの合計delta値
        epsilon: 中立判定閾値（config.neutral_epsilonから渡す）
    """
    if abs(sum_delta) < epsilon:
        return None  # 除外
    return ClusterType.TO_BLACK if sum_delta > 0 else ClusterType.TO_WHITE


def _compute_primary_area(
    coords: frozenset[tuple[int, int]],
    board_size: tuple[int, int],
) -> BoardArea | None:
    """クラスタの主要Area（最頻値、タイブレーク=優先度順）を計算。

    Note:
        - 未知のBoardAreaは最低優先度で処理（KeyError回避）
    """
    if not coords:
        return None

    areas = [classify_area(coord, board_size) for coord in coords]
    # Noneを除外してカウント
    area_counts = Counter(a for a in areas if a is not None)

    if not area_counts:
        return None

    # (count, -priority) でソート → 最大を選択
    # .get()で未知のAreaもKeyError無しで処理
    return max(
        area_counts.keys(),
        key=lambda a: (area_counts[a], -_AREA_PRIORITY.get(a, _AREA_PRIORITY_DEFAULT)),
    )


def _cluster_sort_key(cluster: OwnershipCluster) -> tuple[int, float, tuple[int, int]]:
    """クラスタのソートキー。"""
    type_order = _CLUSTER_TYPE_ORDER[cluster.cluster_type]
    min_coord = min(cluster.coords)  # (col, row) の辞書順最小
    return (type_order, -cluster.max_abs_delta, min_coord)


# =====================================================================
# Public API
# =====================================================================


def compute_ownership_delta(
    parent_ctx: OwnershipContext,
    child_ctx: OwnershipContext,
) -> OwnershipDelta | None:
    """2つのOwnershipContextから差分を計算。

    Args:
        parent_ctx: 親ノードのコンテキスト
        child_ctx: 子ノードのコンテキスト

    Returns:
        OwnershipDelta。どちらかのgridがNoneならNone。

    Raises:
        ValueError: board_sizeが不一致、またはgrid形状が不正。
    """
    # board_sizeチェック
    if parent_ctx.board_size != child_ctx.board_size:
        raise ValueError(f"Board size mismatch: parent={parent_ctx.board_size}, child={child_ctx.board_size}")

    # どちらかのgridがNoneなら早期リターン（エラーではない）
    if parent_ctx.ownership_grid is None or child_ctx.ownership_grid is None:
        return None

    board_size = parent_ctx.board_size
    width, height = board_size

    # 形状検証
    _validate_grid_shape(parent_ctx.ownership_grid, board_size, "Parent")
    _validate_grid_shape(child_ctx.ownership_grid, board_size, "Child")

    # delta計算: child - parent
    delta_grid: list[list[float]] = []
    for row in range(height):
        delta_row: list[float] = []
        for col in range(width):
            parent_val = parent_ctx.ownership_grid[row][col]
            child_val = child_ctx.ownership_grid[row][col]
            delta_row.append(child_val - parent_val)
        delta_grid.append(delta_row)

    # immutableに変換
    immutable_grid = tuple(tuple(row) for row in delta_grid)

    return OwnershipDelta(
        delta_grid=immutable_grid,
        board_size=board_size,
        parent_context=parent_ctx,
        child_context=child_ctx,
    )


def extract_clusters(
    delta: OwnershipDelta,
    config: ClusterExtractionConfig | None = None,
) -> ClusterExtractionResult:
    """OwnershipDeltaからクラスタを抽出。

    Args:
        delta: ownership差分
        config: 抽出設定（Noneならデフォルト）

    Returns:
        ClusterExtractionResult
    """
    if config is None:
        config = ClusterExtractionConfig()

    width, height = delta.board_size
    threshold = config.delta_threshold
    use_8 = config.use_8_neighbors

    # 変動セルを特定
    changed_cells: list[tuple[int, int]] = []
    for row in range(height):
        for col in range(width):
            d = delta.delta_grid[row][col]
            if _is_changed_cell(d, threshold):
                changed_cells.append((col, row))

    total_changed_cells = len(changed_cells)

    # BFSでクラスタ抽出
    visited: set[tuple[int, int]] = set()
    raw_clusters: list[OwnershipCluster] = []

    for col, row in changed_cells:
        if (col, row) not in visited:
            coords = _bfs_cluster(
                col,
                row,
                delta.delta_grid,
                visited,
                threshold,
                use_8,
                width,
                height,
            )

            # min_cluster_sizeフィルタ
            if len(coords) < config.min_cluster_size:
                continue

            # 統計計算
            sum_delta, avg_delta, max_abs_delta = _compute_cluster_stats(coords, delta.delta_grid)

            # クラスタタイプ判定（中立は除外）
            cluster_type = _determine_cluster_type(sum_delta, config.neutral_epsilon)
            if cluster_type is None:
                continue

            # primary_area計算
            primary_area = _compute_primary_area(coords, delta.board_size)

            cluster = OwnershipCluster(
                coords=coords,
                cluster_type=cluster_type,
                sum_delta=sum_delta,
                avg_delta=avg_delta,
                max_abs_delta=max_abs_delta,
                primary_area=primary_area,
                cell_count=len(coords),
            )
            raw_clusters.append(cluster)

    # ソート
    sorted_clusters = sorted(raw_clusters, key=_cluster_sort_key)

    # 統計
    black_gain = sum(1 for c in sorted_clusters if c.cluster_type == ClusterType.TO_BLACK)
    white_gain = sum(1 for c in sorted_clusters if c.cluster_type == ClusterType.TO_WHITE)

    return ClusterExtractionResult(
        clusters=tuple(sorted_clusters),
        total_changed_cells=total_changed_cells,
        black_gain_clusters=black_gain,
        white_gain_clusters=white_gain,
        config=config,
    )


def extract_clusters_from_nodes(
    parent: "GameNode",
    child: "GameNode",
    config: ClusterExtractionConfig | None = None,
) -> ClusterExtractionResult | None:
    """GameNodeからクラスタを抽出（便利ラッパー）。

    Args:
        parent: 親ノード
        child: 子ノード
        config: 抽出設定（Noneならデフォルト）

    Returns:
        ClusterExtractionResult。ownershipがNoneならNone。
    """
    parent_ctx = extract_ownership_context(parent)
    child_ctx = extract_ownership_context(child)

    delta = compute_ownership_delta(parent_ctx, child_ctx)
    if delta is None:
        return None

    return extract_clusters(delta, config)


# =====================================================================
# Module Exports
# =====================================================================

__all__ = [
    # Constants
    "DEFAULT_NEUTRAL_EPSILON",
    # Enums
    "ClusterType",
    # Data Models
    "OwnershipDelta",
    "OwnershipCluster",
    "ClusterExtractionConfig",
    "ClusterExtractionResult",
    # Functions
    "compute_ownership_delta",
    "extract_clusters",
    "extract_clusters_from_nodes",
    # Internal (for testing)
    "_AREA_PRIORITY",
    "_AREA_PRIORITY_DEFAULT",
    "_compute_primary_area",
]
