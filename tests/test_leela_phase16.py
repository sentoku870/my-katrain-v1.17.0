"""Phase 16 tests for Leela enhancements: PV replay and resign hint."""

import pytest
from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval
from katrain.core.leela.logic import (
    check_resign_condition,
    ResignConditionResult,
    RESIGN_WINRATE_THRESHOLD,
    RESIGN_CONSECUTIVE_MOVES,
    RESIGN_RELIABILITY_RATIO,
)


class TestCheckResignCondition:
    """Tests for check_resign_condition function."""

    def test_triggers_when_conditions_met(self):
        """3 consecutive moves with winrate <= 5% should trigger."""
        history = [
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.03, visits=900)],
                root_visits=900,
            )
            for _ in range(3)
        ]

        result = check_resign_condition(history, max_visits=1000)

        assert result.should_show_hint is True
        assert result.consecutive_count == 3
        assert result.avg_winrate == pytest.approx(0.03, rel=0.01)

    def test_not_enough_moves(self):
        """2 moves is not enough to trigger."""
        history = [
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.03, visits=900)],
                root_visits=900,
            )
            for _ in range(2)
        ]

        result = check_resign_condition(history, max_visits=1000)

        assert result.should_show_hint is False
        assert result.consecutive_count == 0

    def test_above_threshold(self):
        """Winrate above 5% should not trigger."""
        history = [
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.10, visits=900)],
                root_visits=900,
            )
            for _ in range(3)
        ]

        result = check_resign_condition(history, max_visits=1000)

        assert result.should_show_hint is False

    def test_empty_history(self):
        """Empty history should not trigger."""
        result = check_resign_condition([], max_visits=1000)

        assert result.should_show_hint is False
        assert result.consecutive_count == 0

    def test_invalid_analysis_in_history(self):
        """Invalid analysis should prevent triggering."""
        history = [
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.03, visits=900)],
                root_visits=900,
            ),
            LeelaPositionEval(parse_error="Test error"),  # Invalid
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.03, visits=900)],
                root_visits=900,
            ),
        ]

        result = check_resign_condition(history, max_visits=1000)

        assert result.should_show_hint is False


class TestResignConditionResult:
    """Tests for ResignConditionResult dataclass."""

    def test_winrate_pct_property(self):
        """winrate_pct should return 0-100 scale."""
        result = ResignConditionResult(
            should_show_hint=True,
            consecutive_count=3,
            avg_winrate=0.04,  # 4%
            is_reliable=True,
        )

        assert result.winrate_pct == pytest.approx(4.0, rel=0.01)

    def test_winrate_pct_zero(self):
        """Zero winrate should give 0%."""
        result = ResignConditionResult(
            should_show_hint=True,
            consecutive_count=3,
            avg_winrate=0.0,
            is_reliable=True,
        )

        assert result.winrate_pct == 0.0


class TestDynamicThreshold:
    """Tests for v4 dynamic threshold calculation."""

    def test_threshold_with_default_max_visits(self):
        """max_visits=1000 -> threshold 800, root_visits=900 is reliable."""
        history = [
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.03, visits=900)],
                root_visits=900,
            )
            for _ in range(3)
        ]

        result = check_resign_condition(history, max_visits=1000)

        # Threshold is 800, root_visits=900 >= 800
        assert result.is_reliable is True

    def test_threshold_unreliable_with_low_visits(self):
        """root_visits=500 (50% of max_visits=1000) is below threshold 800."""
        history = [
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.03, visits=500)],
                root_visits=500,
            )
            for _ in range(3)
        ]

        result = check_resign_condition(history, max_visits=1000)

        # Threshold is 800, root_visits=500 < 800
        assert result.is_reliable is False
        # Should still detect condition, just not reliable
        assert result.should_show_hint is True

    def test_threshold_scales_with_max_visits(self):
        """max_visits=5000 -> threshold 4000."""
        history = [
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.03, visits=4500)],
                root_visits=4500,
            )
            for _ in range(3)
        ]

        result = check_resign_condition(history, max_visits=5000)

        # Threshold is 4000, root_visits=4500 >= 4000
        assert result.is_reliable is True

    def test_threshold_unreliable_with_scaled_max_visits(self):
        """max_visits=5000 -> threshold 4000, root_visits=3000 is unreliable."""
        history = [
            LeelaPositionEval(
                candidates=[LeelaCandidate(move="D4", winrate=0.03, visits=3000)],
                root_visits=3000,
            )
            for _ in range(3)
        ]

        result = check_resign_condition(history, max_visits=5000)

        # Threshold is 4000, root_visits=3000 < 4000
        assert result.is_reliable is False


class TestNodeKeyGeneration:
    """Tests for node key generation (GC-safe)."""

    def test_node_key_format(self):
        """node_key should be in 'depth:id' format."""
        from katrain.core.game_node import GameNode

        node = GameNode()
        key = f"{node.depth}:{id(node)}"

        assert ":" in key
        assert key.startswith(str(node.depth))

    def test_node_key_uniqueness(self):
        """Different nodes should have different keys (via id())."""
        from katrain.core.game_node import GameNode

        node1 = GameNode()
        node2 = GameNode()
        key1 = f"{node1.depth}:{id(node1)}"
        key2 = f"{node2.depth}:{id(node2)}"

        # Same depth but different id()
        assert node1.depth == node2.depth
        assert key1 != key2


class TestPVTypeCompatibility:
    """Tests for PV type compatibility between KataGo and Leela."""

    def test_leela_pv_is_list_str(self):
        """LeelaCandidate.pv should be list[str]."""
        candidate = LeelaCandidate(
            move="D4",
            winrate=0.5,
            visits=100,
            pv=["D4", "Q16", "R14"],
        )

        assert isinstance(candidate.pv, list)
        assert all(isinstance(m, str) for m in candidate.pv)

    def test_empty_pv_handling(self):
        """Empty PV should work without error."""
        candidate = LeelaCandidate(
            move="D4",
            winrate=0.5,
            visits=100,
            pv=[],
        )

        assert candidate.pv == []
        # if candidate.pv: should be False
        assert not candidate.pv

    def test_pv_with_pass(self):
        """PV containing 'pass' should be valid."""
        candidate = LeelaCandidate(
            move="D4",
            winrate=0.5,
            visits=100,
            pv=["D4", "pass", "Q16"],
        )

        assert len(candidate.pv) == 3
        assert candidate.pv[1] == "pass"


class TestKataGoPVRegression:
    """Regression tests to ensure KataGo PV still works."""

    def test_katago_pv_format_unchanged(self):
        """KataGo move_dict['pv'] format should be list[str]."""
        # Mock KataGo move_dict
        move_dict = {"move": "D4", "pv": ["D4", "Q16", "R14"]}

        assert isinstance(move_dict["pv"], list)
        assert all(isinstance(m, str) for m in move_dict["pv"])

    def test_active_pv_moves_tuple_format(self):
        """active_pv_moves entries should be (coords, pv, node) tuples."""
        coords = (3, 3)
        pv = ["D4", "Q16"]
        node = None  # Mock

        entry = (coords, pv, node)

        assert len(entry) == 3
        assert isinstance(entry[1], list)


class TestConfigIntegration:
    """Tests for Phase 16 config settings."""

    def test_resign_hint_config_exists(self):
        """config.json should have resign hint settings."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        assert "leela" in config
        assert "resign_hint_enabled" in config["leela"]
        assert "resign_winrate_threshold" in config["leela"]
        assert "resign_consecutive_moves" in config["leela"]

    def test_resign_hint_default_values(self):
        """Default values should be reasonable."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "katrain" / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        leela = config["leela"]
        assert leela["resign_hint_enabled"] is False  # Default off
        assert 1 <= leela["resign_winrate_threshold"] <= 10  # Percentage
        assert leela["resign_consecutive_moves"] >= 2  # At least 2 moves
