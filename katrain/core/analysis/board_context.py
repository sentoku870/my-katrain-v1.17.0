# katrain/core/analysis/board_context.py
"""Phase 80: 盤面コンテキスト解析の共通基盤。

Area判定、ownership/scoreStdev抽出ヘルパを提供。
Karte/Summaryの出力仕様は変更せず、後続Phase 81-87の土台として使用。
"""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode

# =====================================================================
# Area Classification
# =====================================================================


class BoardArea(Enum):
    """盤面の区域分類。"""

    CORNER = "corner"
    EDGE = "edge"
    CENTER = "center"


_AREA_NAMES_JP: dict[BoardArea, str] = {
    BoardArea.CORNER: "隅",
    BoardArea.EDGE: "辺",
    BoardArea.CENTER: "中央",
}

_AREA_NAMES_EN: dict[BoardArea, str] = {
    BoardArea.CORNER: "Corner",
    BoardArea.EDGE: "Edge",
    BoardArea.CENTER: "Center",
}


def classify_area(
    coords: tuple[int, int] | None,
    board_size: tuple[int, int] = (19, 19),
    corner_threshold: int = 4,
    edge_threshold: int = 4,
) -> BoardArea | None:
    """座標からBoardAreaを判定。

    Args:
        coords: (col, row) 0-indexed。Noneまたは範囲外→None返却。
        board_size: (width, height)
        corner_threshold: 隅判定閾値（default: 4）
        edge_threshold: 辺判定閾値（default: 4）

    Returns:
        BoardArea or None
    """
    if coords is None:
        return None

    col, row = coords
    width, height = board_size

    if not (0 <= col < width and 0 <= row < height):
        return None

    min_col_dist = min(col, width - 1 - col)
    min_row_dist = min(row, height - 1 - row)

    if min_col_dist < corner_threshold and min_row_dist < corner_threshold:
        return BoardArea.CORNER
    if min_col_dist < edge_threshold or min_row_dist < edge_threshold:
        return BoardArea.EDGE
    return BoardArea.CENTER


def get_area_name(area: BoardArea | None, lang: str = "jp") -> str:
    """BoardAreaの表示名を取得。lang="ja"は"jp"として扱う。"""
    if area is None:
        return ""
    if lang == "ja":
        lang = "jp"
    if lang == "jp":
        return _AREA_NAMES_JP.get(area, area.value)
    return _AREA_NAMES_EN.get(area, area.value)


# =====================================================================
# Internal Helpers
# =====================================================================


def _normalize_board_size(raw: tuple[int, int] | int | None) -> tuple[int, int]:
    """board_sizeを(width, height)タプルに正規化。"""
    if isinstance(raw, tuple) and len(raw) == 2:
        return raw
    if isinstance(raw, int):
        return (raw, raw)
    return (19, 19)


def _safe_get_ownership(node: "GameNode") -> list[float] | None:
    """GameNodeからownership配列を安全に取得。

    1. node.ownership プロパティを試行（try/except で保護）
    2. フォールバック: node.analysis dict から取得
    3. どちらも失敗→None
    """
    # Try property access with exception guard
    try:
        ownership = getattr(node, "ownership", None)
        if ownership is not None:
            if isinstance(ownership, list):
                return list(ownership)
            return None
    except Exception:
        pass

    # Fallback to analysis dict
    try:
        analysis = getattr(node, "analysis", None)
        if isinstance(analysis, dict):
            result = analysis.get("ownership")
            if isinstance(result, list):
                return list(result)
            return None
    except Exception:
        pass

    return None


# =====================================================================
# OwnershipContext
# =====================================================================


@dataclass(frozen=True)
class OwnershipContext:
    """盤面ownershipとscoreStdevのコンテキスト。

    ownership_grid: grid[row][col] 形式。row 0 = 盤面下辺(y=0)。
    score_stdev: KataGoのscoreStdev（LeelaはNone）。
    board_size: (width, height)。
    """

    ownership_grid: list[list[float]] | None
    score_stdev: float | None
    board_size: tuple[int, int]

    def get_ownership_at(self, coords: tuple[int, int] | None) -> float | None:
        """指定座標のownership値を取得。範囲外/None→None。"""
        if coords is None or self.ownership_grid is None:
            return None

        col, row = coords
        width, height = self.board_size

        if not (0 <= col < width and 0 <= row < height):
            return None
        if row < len(self.ownership_grid) and col < len(self.ownership_grid[row]):
            return self.ownership_grid[row][col]
        return None


def extract_ownership_context(
    node: "GameNode",
    board_size: tuple[int, int] | None = None,
) -> OwnershipContext:
    """GameNodeからOwnershipContextを抽出。

    Args:
        node: GameNode
        board_size: 明示指定時はそれを使用。Noneならnode.board_sizeから自動取得。

    Note:
        - 内部インポート: critical_moves._get_score_stdev_from_node, utils.var_to_grid
        - パッチ対象: katrain.core.analysis.critical_moves._get_score_stdev_from_node
    """
    from katrain.core.analysis.critical_moves import _get_score_stdev_from_node
    from katrain.core.utils import var_to_grid

    # board_size: 引数 > node.board_size > (19,19)
    if board_size is not None:
        final_size = _normalize_board_size(board_size)
    else:
        raw = getattr(node, "board_size", None)
        final_size = _normalize_board_size(raw)

    # ownership: ヘルパー経由で安全に取得
    ownership = _safe_get_ownership(node)

    # scoreStdev: critical_moves経由
    score_stdev = _get_score_stdev_from_node(node)

    # var_to_grid: (width, height) タプルを期待
    ownership_grid = None
    if ownership is not None:
        ownership_grid = var_to_grid(list(ownership), final_size)

    return OwnershipContext(
        ownership_grid=ownership_grid,
        score_stdev=score_stdev,
        board_size=final_size,
    )


def get_score_stdev(node: "GameNode") -> float | None:
    """GameNodeからscoreStdevを取得（公開ヘルパ）。"""
    from katrain.core.analysis.critical_moves import _get_score_stdev_from_node

    return _get_score_stdev_from_node(node)


# =====================================================================
# Public API
# =====================================================================

__all__ = [
    "BoardArea",
    "classify_area",
    "get_area_name",
    "OwnershipContext",
    "extract_ownership_context",
    "get_score_stdev",
]
