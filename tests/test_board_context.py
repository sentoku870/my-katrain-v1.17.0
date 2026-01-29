# tests/test_board_context.py
"""Phase 80: board_context単体テスト。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.analysis.board_context import (
    BoardArea,
    OwnershipContext,
    _normalize_board_size,
    _safe_get_ownership,
    classify_area,
    extract_ownership_context,
    get_area_name,
    get_score_stdev,
)


# =====================================================================
# classify_area
# =====================================================================


class TestClassifyArea:
    def test_corners_19x19(self):
        for coords in [(0, 0), (0, 18), (18, 0), (18, 18), (3, 3)]:
            assert classify_area(coords) == BoardArea.CORNER

    def test_edges_19x19(self):
        for coords in [(9, 0), (0, 9), (18, 9), (9, 18)]:
            assert classify_area(coords) == BoardArea.EDGE

    def test_center_19x19(self):
        for coords in [(9, 9), (6, 6), (12, 12)]:
            assert classify_area(coords) == BoardArea.CENTER

    def test_none_returns_none(self):
        assert classify_area(None) is None

    def test_negative_returns_none(self):
        assert classify_area((-1, 0)) is None
        assert classify_area((0, -1)) is None

    def test_out_of_bounds_returns_none(self):
        assert classify_area((19, 0)) is None
        assert classify_area((0, 19)) is None

    def test_9x9_with_adjusted_thresholds(self):
        assert classify_area((0, 0), (9, 9), 3, 3) == BoardArea.CORNER
        assert classify_area((4, 4), (9, 9), 3, 3) == BoardArea.CENTER


# =====================================================================
# get_area_name
# =====================================================================


class TestGetAreaName:
    def test_jp(self):
        assert get_area_name(BoardArea.CORNER, "jp") == "隅"
        assert get_area_name(BoardArea.EDGE, "jp") == "辺"
        assert get_area_name(BoardArea.CENTER, "jp") == "中央"

    def test_ja_alias(self):
        assert get_area_name(BoardArea.CORNER, "ja") == "隅"

    def test_en(self):
        assert get_area_name(BoardArea.CORNER, "en") == "Corner"

    def test_default_is_jp(self):
        assert get_area_name(BoardArea.CORNER) == "隅"

    def test_none_returns_empty(self):
        assert get_area_name(None) == ""


# =====================================================================
# _normalize_board_size
# =====================================================================


class TestNormalizeBoardSize:
    def test_tuple(self):
        assert _normalize_board_size((19, 19)) == (19, 19)
        assert _normalize_board_size((9, 9)) == (9, 9)

    def test_int(self):
        assert _normalize_board_size(19) == (19, 19)
        assert _normalize_board_size(9) == (9, 9)

    def test_none(self):
        assert _normalize_board_size(None) == (19, 19)

    def test_invalid(self):
        assert _normalize_board_size("19") == (19, 19)
        assert _normalize_board_size([19, 19]) == (19, 19)


# =====================================================================
# _safe_get_ownership
# =====================================================================


class TestSafeGetOwnership:
    def test_property_exists(self):
        node = MagicMock()
        node.ownership = [0.5, 0.3]
        assert _safe_get_ownership(node) == [0.5, 0.3]

    def test_property_none_fallback_to_analysis(self):
        node = MagicMock()
        node.ownership = None
        node.analysis = {"ownership": [0.1, 0.2]}
        assert _safe_get_ownership(node) == [0.1, 0.2]

    def test_property_raises_fallback_to_analysis(self):
        # Create a class where ownership property raises exception
        class NodeWithBrokenOwnership:
            @property
            def ownership(self):
                raise AttributeError("ownership not available")

            analysis = {"ownership": [0.9, 0.8]}

        node = NodeWithBrokenOwnership()
        assert _safe_get_ownership(node) == [0.9, 0.8]

    def test_no_ownership_anywhere(self):
        node = SimpleNamespace()
        assert _safe_get_ownership(node) is None

    def test_analysis_not_dict(self):
        node = SimpleNamespace(ownership=None, analysis="not a dict")
        assert _safe_get_ownership(node) is None


# =====================================================================
# OwnershipContext
# =====================================================================


class TestOwnershipContext:
    def test_get_ownership_at_valid(self):
        grid = [
            [0.5, 0.0, -0.5],  # row 0 (bottom)
            [0.8, 0.2, -0.8],  # row 1
            [1.0, -1.0, 0.0],  # row 2 (top)
        ]
        ctx = OwnershipContext(grid, 5.0, (3, 3))
        assert ctx.get_ownership_at((0, 0)) == 0.5
        assert ctx.get_ownership_at((0, 2)) == 1.0

    def test_none_coords(self):
        ctx = OwnershipContext([[0.5]], 1.0, (1, 1))
        assert ctx.get_ownership_at(None) is None

    def test_none_grid(self):
        ctx = OwnershipContext(None, None, (19, 19))
        assert ctx.get_ownership_at((9, 9)) is None

    def test_out_of_bounds(self):
        ctx = OwnershipContext([[0.5]], 1.0, (1, 1))
        assert ctx.get_ownership_at((5, 5)) is None
        assert ctx.get_ownership_at((-1, 0)) is None

    def test_vertical_orientation(self):
        """row 0 = bottom (y=0), row 2 = top (y=2)."""
        grid = [[1.0], [0.0], [-1.0]]  # bottom, mid, top
        ctx = OwnershipContext(grid, None, (1, 3))
        assert ctx.get_ownership_at((0, 0)) == 1.0  # bottom
        assert ctx.get_ownership_at((0, 2)) == -1.0  # top


# =====================================================================
# extract_ownership_context
# =====================================================================


class TestExtractOwnershipContext:
    """パッチ対象: katrain.core.analysis.critical_moves._get_score_stdev_from_node"""

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_no_ownership(self, mock_stdev):
        mock_stdev.return_value = None
        node = MagicMock()
        node.ownership = None
        node.analysis = {"ownership": None}
        node.board_size = (19, 19)

        ctx = extract_ownership_context(node)

        assert ctx.ownership_grid is None
        assert ctx.score_stdev is None
        assert ctx.board_size == (19, 19)

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_board_size_auto(self, mock_stdev):
        mock_stdev.return_value = None
        node = MagicMock()
        node.ownership = None
        node.analysis = {}
        node.board_size = (9, 9)

        ctx = extract_ownership_context(node)
        assert ctx.board_size == (9, 9)

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_board_size_fallback(self, mock_stdev):
        mock_stdev.return_value = None
        node = SimpleNamespace(ownership=None)

        ctx = extract_ownership_context(node)
        assert ctx.board_size == (19, 19)

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_board_size_int(self, mock_stdev):
        mock_stdev.return_value = None
        node = MagicMock()
        node.ownership = None
        node.analysis = {}
        node.board_size = 13

        ctx = extract_ownership_context(node)
        assert ctx.board_size == (13, 13)

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_explicit_board_size(self, mock_stdev):
        mock_stdev.return_value = None
        node = MagicMock()
        node.ownership = None
        node.analysis = {}
        node.board_size = (19, 19)

        ctx = extract_ownership_context(node, board_size=(13, 13))
        assert ctx.board_size == (13, 13)

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_score_stdev(self, mock_stdev):
        mock_stdev.return_value = 5.5
        node = MagicMock()
        node.ownership = None
        node.analysis = {}
        node.board_size = (19, 19)

        ctx = extract_ownership_context(node)
        assert ctx.score_stdev == 5.5
        mock_stdev.assert_called_once_with(node)

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_ownership_conversion(self, mock_stdev):
        """var_to_grid reverses: [top, bottom] -> [[bottom], [top]]."""
        mock_stdev.return_value = None
        node = MagicMock()
        node.ownership = [0.8, 0.2]  # KataGo: top, bottom
        node.board_size = (1, 2)

        ctx = extract_ownership_context(node)

        assert ctx.ownership_grid[0] == [0.2]  # row 0 = bottom
        assert ctx.ownership_grid[1] == [0.8]  # row 1 = top

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_ownership_fallback(self, mock_stdev):
        """node.ownership=None時にanalysis dictから取得。"""
        mock_stdev.return_value = None
        node = MagicMock()
        node.ownership = None
        node.analysis = {"ownership": [0.5, -0.5]}
        node.board_size = (1, 2)

        ctx = extract_ownership_context(node)

        assert ctx.ownership_grid[0] == [-0.5]
        assert ctx.ownership_grid[1] == [0.5]


# =====================================================================
# get_score_stdev
# =====================================================================


class TestGetScoreStdev:
    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_passthrough(self, mock_stdev):
        mock_stdev.return_value = 3.14
        node = MagicMock()
        assert get_score_stdev(node) == 3.14
        mock_stdev.assert_called_once_with(node)

    @patch("katrain.core.analysis.critical_moves._get_score_stdev_from_node")
    def test_none(self, mock_stdev):
        mock_stdev.return_value = None
        assert get_score_stdev(MagicMock()) is None


# =====================================================================
# Import smoke test
# =====================================================================


class TestImportSmoke:
    def test_analysis_module_import(self):
        import katrain.core.analysis

        assert hasattr(katrain.core.analysis, "BoardArea")
        assert hasattr(katrain.core.analysis, "classify_area")
        assert hasattr(katrain.core.analysis, "get_area_name")
        assert hasattr(katrain.core.analysis, "OwnershipContext")
        assert hasattr(katrain.core.analysis, "extract_ownership_context")
        assert hasattr(katrain.core.analysis, "get_score_stdev")
