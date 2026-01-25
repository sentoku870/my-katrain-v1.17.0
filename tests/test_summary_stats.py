"""
Tests for katrain/gui/features/summary_stats.py

This module tests:
1. extract_analysis_from_sgf_node() - Pure function, no Kivy dependency
2. extract_sgf_statistics() - External dependencies mocked

Test philosophy:
- Align with current implementation behavior
- Use mocks for heavy dependencies (KaTrainSGF, Game, engine)
- No Kivy imports required
"""

import base64
import gzip
import json
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from katrain.gui.features.summary_stats import (
    extract_analysis_from_sgf_node,
    extract_sgf_statistics,
)
from katrain.core import eval_metrics


# ---------------------------------------------------------------------------
# Helper: Create valid KT payload
# ---------------------------------------------------------------------------

def create_kt_payload(
    analysis_dict: Optional[Dict[str, Any]] = None,
    include_ownership: bool = True,
    include_policy: bool = True,
) -> List[bytes]:
    """Create a valid KT payload list for testing.

    KaTrain SGF format: [ownership_data, policy_data, main_data]
    where main_data is base64-encoded gzip-compressed JSON.

    Args:
        analysis_dict: The analysis data to encode. Defaults to minimal valid data.
        include_ownership: Include ownership placeholder (index 0)
        include_policy: Include policy placeholder (index 1)

    Returns:
        List of bytes representing KT payload
    """
    if analysis_dict is None:
        analysis_dict = {"root": {"scoreLead": 0.5}, "moves": {}}

    # Encode main_data: JSON -> gzip -> base64
    json_bytes = json.dumps(analysis_dict).encode("utf-8")
    gzipped = gzip.compress(json_bytes)
    main_data = base64.standard_b64encode(gzipped)

    payload = []
    if include_ownership:
        payload.append(b"ownership_placeholder")
    if include_policy:
        payload.append(b"policy_placeholder")
    payload.append(main_data)

    return payload


def create_mock_node(
    analysis_from_sgf: Any = None,
    move_property: Optional[str] = None,
    player: str = "B",
) -> Mock:
    """Create a mock SGF node for testing.

    Args:
        analysis_from_sgf: Value for analysis_from_sgf attribute
        move_property: GTP coordinate (e.g., "D4") or None
        player: "B" or "W"

    Returns:
        Mock node object
    """
    node = Mock()
    node.analysis_from_sgf = analysis_from_sgf

    def get_property(prop):
        if prop == player and move_property:
            return move_property
        return None

    node.get_property = get_property
    return node


# ---------------------------------------------------------------------------
# Tests for extract_analysis_from_sgf_node()
# ---------------------------------------------------------------------------

class TestExtractAnalysisFromSgfNode:
    """Tests for extract_analysis_from_sgf_node() function."""

    # --- Normal cases ---

    def test_extract_valid_kt_data(self):
        """Valid KT payload should be decoded correctly."""
        analysis = {"root": {"scoreLead": 1.5}, "moves": {"D4": {"visits": 100}}}
        kt_payload = create_kt_payload(analysis)
        node = create_mock_node(analysis_from_sgf=kt_payload)

        result = extract_analysis_from_sgf_node(node)

        assert result == analysis
        assert result["root"]["scoreLead"] == 1.5
        assert "moves" in result

    def test_extract_with_root_and_moves(self):
        """Payload with both root and moves should decode correctly."""
        analysis = {
            "root": {
                "scoreLead": -2.3,
                "winrate": 0.45,
                "visits": 500,
            },
            "moves": {
                "Q16": {"prior": 0.15, "visits": 200},
                "D4": {"prior": 0.12, "visits": 150},
            },
        }
        kt_payload = create_kt_payload(analysis)
        node = create_mock_node(analysis_from_sgf=kt_payload)

        result = extract_analysis_from_sgf_node(node)

        assert result["root"]["scoreLead"] == -2.3
        assert result["root"]["winrate"] == 0.45
        assert len(result["moves"]) == 2
        assert result["moves"]["Q16"]["visits"] == 200

    # --- Boundary cases ---

    def test_extract_kt_data_exactly_3_items(self):
        """Payload with exactly 3 items (minimum valid) should work."""
        analysis = {"root": {"scoreLead": 0.0}}
        kt_payload = create_kt_payload(analysis)
        assert len(kt_payload) == 3  # ownership, policy, main_data

        node = create_mock_node(analysis_from_sgf=kt_payload)
        result = extract_analysis_from_sgf_node(node)

        assert result is not None
        assert result["root"]["scoreLead"] == 0.0

    def test_extract_kt_data_more_than_3_items(self):
        """Payload with more than 3 items should still work (uses index 2)."""
        analysis = {"root": {"scoreLead": 3.14}}
        kt_payload = create_kt_payload(analysis)
        kt_payload.append(b"extra_data")
        kt_payload.append(b"more_extra")
        assert len(kt_payload) == 5

        node = create_mock_node(analysis_from_sgf=kt_payload)
        result = extract_analysis_from_sgf_node(node)

        assert result is not None
        assert result["root"]["scoreLead"] == 3.14

    # --- None/Empty cases ---

    def test_extract_none_kt_data(self):
        """Node with analysis_from_sgf=None should return None."""
        node = create_mock_node(analysis_from_sgf=None)

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    def test_extract_empty_kt_data(self):
        """Node with empty list should return None."""
        node = create_mock_node(analysis_from_sgf=[])

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    def test_extract_kt_data_less_than_3(self):
        """Payload with fewer than 3 items should return None."""
        # Only 2 items
        node = create_mock_node(analysis_from_sgf=[b"item1", b"item2"])

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    def test_extract_kt_data_length_1(self):
        """Payload with only 1 item should return None."""
        node = create_mock_node(analysis_from_sgf=[b"single_item"])

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    # --- Error cases ---

    def test_extract_invalid_base64(self):
        """Invalid base64 in main_data should return None (not raise)."""
        kt_payload = [b"ownership", b"policy", b"not_valid_base64!!!"]
        node = create_mock_node(analysis_from_sgf=kt_payload)

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    def test_extract_invalid_gzip(self):
        """Valid base64 but invalid gzip should return None."""
        # Base64-encode some non-gzip data
        invalid_gzip = base64.standard_b64encode(b"this is not gzip data")
        kt_payload = [b"ownership", b"policy", invalid_gzip]
        node = create_mock_node(analysis_from_sgf=kt_payload)

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    def test_extract_invalid_json(self):
        """Valid gzip but invalid JSON should return None."""
        # Gzip-compress invalid JSON
        invalid_json = b"{ not valid json }"
        gzipped = gzip.compress(invalid_json)
        encoded = base64.standard_b64encode(gzipped)
        kt_payload = [b"ownership", b"policy", encoded]
        node = create_mock_node(analysis_from_sgf=kt_payload)

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    def test_extract_kt_data_not_list(self):
        """kt_data that is not a list should return None."""
        # String instead of list
        node = create_mock_node(analysis_from_sgf="not a list")

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    def test_extract_kt_data_dict(self):
        """kt_data that is a dict should return None."""
        node = create_mock_node(analysis_from_sgf={"key": "value"})

        result = extract_analysis_from_sgf_node(node)

        assert result is None

    # --- Attribute missing cases ---

    def test_extract_node_without_analysis_from_sgf(self):
        """Node without analysis_from_sgf attribute should return None."""
        node = Mock(spec=[])  # No attributes

        result = extract_analysis_from_sgf_node(node)

        assert result is None


# ---------------------------------------------------------------------------
# Tests for extract_sgf_statistics()
# ---------------------------------------------------------------------------

class TestExtractSgfStatistics:
    """Tests for extract_sgf_statistics() function."""

    @pytest.fixture
    def mock_ctx(self):
        """Create a mock FeatureContext."""
        ctx = MagicMock()
        ctx.config.return_value = "standard"  # skill_preset
        return ctx

    @pytest.fixture
    def mock_engine(self):
        """Create a mock KataGoEngine."""
        return MagicMock()

    @pytest.fixture
    def mock_log_fn(self):
        """Create a mock log function."""
        return MagicMock()

    def _create_mock_move_tree(
        self,
        properties: Dict[str, str],
        nodes: List[Mock],
    ) -> Mock:
        """Create a mock move tree.

        Args:
            properties: SGF properties (PB, PW, HA, DT, SZ, BR, WR)
            nodes: List of mock nodes
        """
        move_tree = MagicMock()
        move_tree.get_property = lambda prop, default=None: properties.get(prop, default)
        move_tree.nodes_in_tree = nodes
        # CRITICAL: Set children to empty list to prevent infinite loop in parse_time_data
        move_tree.children = []
        return move_tree

    # --- Normal cases ---

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_basic(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Basic statistics extraction should work."""
        # Create mock nodes with analysis
        analysis1 = {"root": {"scoreLead": 0.5}, "moves": {}}
        analysis2 = {"root": {"scoreLead": 0.3}, "moves": {}}  # Black lost 0.2 points

        node0 = create_mock_node(analysis_from_sgf=None)  # root node, no move
        node1 = create_mock_node(
            analysis_from_sgf=create_kt_payload(analysis1),
            move_property="D4",
            player="B",
        )
        node2 = create_mock_node(
            analysis_from_sgf=create_kt_payload(analysis2),
            move_property="Q16",
            player="W",
        )

        # Setup mock move tree
        move_tree = self._create_mock_move_tree(
            properties={
                "PB": "TestBlack",
                "PW": "TestWhite",
                "HA": "0",
                "DT": "2025-01-05",
                "SZ": "19",
            },
            nodes=[node0, node1, node2],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        # Mock Game to avoid reason_tags computation complexity
        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("test.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result is not None
        assert result["game_name"] == "test.sgf"
        assert result["player_black"] == "TestBlack"
        assert result["player_white"] == "TestWhite"
        assert result["handicap"] == 0
        assert result["date"] == "2025-01-05"
        assert result["board_size"] == (19, 19)

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_with_handicap(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Handicap game should be parsed correctly."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={
                "PB": "WeakPlayer",
                "PW": "StrongPlayer",
                "HA": "4",
                "SZ": "19",
            },
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("handicap.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result is not None
        assert result["handicap"] == 4
        assert result["player_black"] == "WeakPlayer"
        assert result["player_white"] == "StrongPlayer"

    # --- Boundary cases ---

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_empty_sgf(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """SGF with only root node (no moves) should return valid stats."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={"PB": "Black", "PW": "White", "SZ": "19"},
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("empty.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result is not None
        assert result["total_moves"] == 0
        assert result["total_points_lost"] == 0.0

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_no_analysis(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """SGF with moves but no KT analysis should return valid stats."""
        # Nodes without analysis_from_sgf
        node0 = create_mock_node(analysis_from_sgf=None)
        node1 = create_mock_node(analysis_from_sgf=None, move_property="D4", player="B")
        node2 = create_mock_node(analysis_from_sgf=None, move_property="Q16", player="W")

        move_tree = self._create_mock_move_tree(
            properties={"PB": "Black", "PW": "White"},
            nodes=[node0, node1, node2],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("no_analysis.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result is not None
        assert result["total_moves"] == 0  # No analyzed moves

    # --- Error cases ---

    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_nonexistent_file(self, mock_sgf_cls, mock_ctx, mock_engine, mock_log_fn):
        """Non-existent file should return None and log error."""
        mock_sgf_cls.parse_file.side_effect = FileNotFoundError("File not found")

        result = extract_sgf_statistics("nonexistent.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result is None
        mock_log_fn.assert_called()  # Error was logged

    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_invalid_sgf(self, mock_sgf_cls, mock_ctx, mock_engine, mock_log_fn):
        """Invalid SGF content should return None and log error."""
        mock_sgf_cls.parse_file.side_effect = Exception("Parse error")

        result = extract_sgf_statistics("invalid.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result is None
        mock_log_fn.assert_called()

    # --- Metadata extraction ---

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_player_names(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Player names (PB/PW) should be extracted correctly."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={
                "PB": "山田太郎",
                "PW": "田中花子",
            },
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("names.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result["player_black"] == "山田太郎"
        assert result["player_white"] == "田中花子"

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_player_names_default(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Missing player names should use defaults."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={},  # No PB/PW
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("no_names.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result["player_black"] == "Black"
        assert result["player_white"] == "White"

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_board_size(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Board size (SZ) should be extracted correctly."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={"SZ": "13"},
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("13x13.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result["board_size"] == (13, 13)

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_board_size_default(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Missing board size should default to 19x19."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={},  # No SZ
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("no_size.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result["board_size"] == (19, 19)

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_rank_info(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Rank info (BR/WR) should be extracted correctly."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={
                "PB": "Player1",
                "PW": "Player2",
                "BR": "5d",
                "WR": "4d",
            },
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("ranks.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result["rank_black"] == "5d"
        assert result["rank_white"] == "4d"

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_date(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Date (DT) should be extracted correctly."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={"DT": "2025-12-31"},
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("dated.sgf", mock_ctx, mock_engine, mock_log_fn)

        assert result["date"] == "2025-12-31"

    # --- Stats structure verification ---

    @patch("katrain.core.game.Game")
    @patch("katrain.gui.features.summary_stats.KaTrainSGF")
    def test_extract_stats_structure(self, mock_sgf_cls, mock_game_cls, mock_ctx, mock_engine, mock_log_fn):
        """Returned stats dict should have all required keys."""
        node0 = create_mock_node(analysis_from_sgf=None)

        move_tree = self._create_mock_move_tree(
            properties={},
            nodes=[node0],
        )
        mock_sgf_cls.parse_file.return_value = move_tree

        mock_game_instance = MagicMock()
        mock_game_instance.root.nodes_in_tree = []
        mock_game_instance.get_important_move_evals.return_value = []
        mock_game_cls.return_value = mock_game_instance

        result = extract_sgf_statistics("structure.sgf", mock_ctx, mock_engine, mock_log_fn)

        # Verify all required keys exist
        required_keys = [
            "game_name",
            "player_black",
            "player_white",
            "rank_black",
            "rank_white",
            "handicap",
            "date",
            "board_size",
            "total_moves",
            "total_points_lost",
            "moves_by_player",
            "loss_by_player",
            "mistake_counts",
            "mistake_total_loss",
            "freedom_counts",
            "phase_moves",
            "phase_loss",
            "phase_mistake_counts",
            "phase_mistake_loss",
            "worst_moves",
            "reason_tags_counts",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

        # Verify structure of nested dicts
        assert "B" in result["moves_by_player"]
        assert "W" in result["moves_by_player"]
        assert "B" in result["loss_by_player"]
        assert "W" in result["loss_by_player"]

        # Verify MistakeCategory keys
        for cat in eval_metrics.MistakeCategory:
            assert cat in result["mistake_counts"]
            assert cat in result["mistake_total_loss"]

        # Verify PositionDifficulty keys
        for diff in eval_metrics.PositionDifficulty:
            assert diff in result["freedom_counts"]

        # Verify phase keys
        for phase in ["opening", "middle", "yose", "unknown"]:
            assert phase in result["phase_moves"]
            assert phase in result["phase_loss"]
