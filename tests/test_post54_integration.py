# -*- coding: utf-8 -*-
"""Integration tests for Phase 55-64 features.

Part of Phase 65: Post-54 Integration.

Tests the interaction between:
- Style Archetype (Phase 56): determine_style()
- Pacing & Tilt (Phase 59): analyze_pacing()
- Risk Context (Phase 61): analyze_risk()
- Curator (Phase 63-64): generate_curator_outputs()

All tests use mock data to ensure CI stability.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Optional

import pytest

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.analysis.models import MoveEval
from katrain.core.analysis.risk import (
    RiskAnalysisResult,
    RiskBehavior,
    RiskJudgmentType,
    analyze_risk,
)
from katrain.core.analysis.skill_radar import RadarAxis, RadarMetrics, SkillTier
from katrain.core.analysis.style import (
    StyleArchetypeId,
    StyleResult,
    determine_style,
)
from katrain.core.analysis.time.models import GameTimeData, TimeMetrics
from katrain.core.analysis.time.pacing import (
    PacingAnalysisResult,
    PacingConfig,
    analyze_pacing,
)
from katrain.core.curator.batch import generate_curator_outputs


# =============================================================================
# JSON Normalization Helper (for determinism tests)
# =============================================================================


def normalize_json_for_comparison(data: dict) -> dict:
    """Normalize JSON dict for deterministic comparison.

    Approach: Allowlist of stable fields only.
    - Removes 'generated' (timestamp, environment-dependent)
    - Re-serializes with sort_keys for consistent key order

    Note: 'version' is a constant (not environment-dependent).
    """
    normalized = json.loads(json.dumps(data, sort_keys=True))
    if "generated" in normalized:
        del normalized["generated"]
    return normalized


# =============================================================================
# Test Helpers
# =============================================================================


def make_radar(
    opening: float = 3.0,
    fighting: float = 3.0,
    endgame: float = 3.0,
    stability: float = 3.0,
    awareness: float = 3.0,
) -> RadarMetrics:
    """Create RadarMetrics for testing.

    Scale: 1.0-5.0 (neutral=3.0, high=4.0+, low=2.0-)
    """
    return RadarMetrics(
        opening=opening,
        fighting=fighting,
        endgame=endgame,
        stability=stability,
        awareness=awareness,
        opening_tier=SkillTier.TIER_3,
        fighting_tier=SkillTier.TIER_3,
        endgame_tier=SkillTier.TIER_3,
        stability_tier=SkillTier.TIER_3,
        awareness_tier=SkillTier.TIER_3,
        overall_tier=SkillTier.TIER_3,
        valid_move_counts=MappingProxyType(
            {
                RadarAxis.OPENING: 10,
                RadarAxis.FIGHTING: 10,
                RadarAxis.ENDGAME: 10,
                RadarAxis.STABILITY: 10,
                RadarAxis.AWARENESS: 10,
            }
        ),
    )


def make_time_metrics(
    move_number: int, player: str, time_spent: float | None = None
) -> TimeMetrics:
    """Create a TimeMetrics instance for testing."""
    return TimeMetrics(
        move_number=move_number,
        player=player,
        time_left_sec=100.0 if time_spent is not None else None,
        time_spent_sec=time_spent,
    )


def make_time_data(
    move_numbers: list[int],
    players: list[str] | None = None,
    time_spents: list[float | None] | None = None,
) -> GameTimeData:
    """Create GameTimeData for testing."""
    if players is None:
        players = ["B" if i % 2 == 1 else "W" for i in move_numbers]
    if time_spents is None:
        time_spents = [10.0] * len(move_numbers)

    metrics = tuple(
        make_time_metrics(mn, p, ts)
        for mn, p, ts in zip(move_numbers, players, time_spents)
    )
    has_time = any(m.time_left_sec is not None for m in metrics)

    return GameTimeData(
        metrics=metrics,
        has_time_data=has_time,
        black_moves_with_time=sum(
            1 for m in metrics if m.player == "B" and m.time_left_sec is not None
        ),
        white_moves_with_time=sum(
            1 for m in metrics if m.player == "W" and m.time_left_sec is not None
        ),
    )


def make_move_eval(
    move_number: int,
    player: str = "B",
    score_loss: float | None = None,
    leela_loss_est: float | None = None,
    points_lost: float | None = None,
) -> MoveEval:
    """Create a MoveEval instance for testing."""
    return MoveEval(
        move_number=move_number,
        player=player,
        gtp="aa",
        score_before=None,
        score_after=None,
        delta_score=None,
        winrate_before=None,
        winrate_after=None,
        delta_winrate=None,
        points_lost=points_lost,
        realized_points_lost=None,
        root_visits=500,
        score_loss=score_loss,
        leela_loss_est=leela_loss_est,
    )


@dataclass
class MockMove:
    """Mock Move object for testing."""

    player: str
    coords: tuple | None = None

    @property
    def is_pass(self) -> bool:
        return self.coords is None


@dataclass
class MockNode:
    """Mock GameNode for testing."""

    analysis_exists: bool = False
    analysis: dict[str, Any] | None = None
    move: Optional["MockMove"] = None
    parent: Optional["MockNode"] = None
    children: list["MockNode"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


def make_node_with_analysis(
    winrate: float | None = None,
    score_lead: float | None = None,
    score_stdev: float | None = None,
    player: str = "B",
    parent: Optional["MockNode"] = None,
) -> MockNode:
    """Create a MockNode with specified analysis values."""
    root_info: dict[str, Any] = {}
    if winrate is not None:
        root_info["winrate"] = winrate
    if score_lead is not None:
        root_info["scoreLead"] = score_lead
    if score_stdev is not None:
        root_info["scoreStdev"] = score_stdev

    analysis = {"root": root_info} if root_info else None
    analysis_exists = analysis is not None

    return MockNode(
        analysis_exists=analysis_exists,
        analysis=analysis,
        move=MockMove(player=player),
        parent=parent,
        children=[],
    )


@dataclass
class MockGame:
    """Mock Game object for testing."""

    root: MockNode

    @property
    def current_node(self):
        return self.root


def make_mock_game_with_nodes(node_count: int = 5) -> MockGame:
    """Create a mock game with a chain of nodes."""
    root = MockNode(
        analysis_exists=False,
        analysis=None,
        move=None,
        parent=None,
        children=[],
    )
    current = root
    for i in range(1, node_count + 1):
        player = "B" if i % 2 == 1 else "W"
        node = make_node_with_analysis(
            winrate=0.5 + (0.01 * (i % 3 - 1)),  # Vary slightly
            score_lead=0.5 * (i % 3 - 1),
            score_stdev=5.0,
            player=player,
            parent=current,
        )
        current.children = [node]
        current = node

    return MockGame(root=root)


# =============================================================================
# TestStylePacingRiskContract
# =============================================================================


class TestStylePacingRiskContract:
    """Contract-level tests for Style, Pacing, Risk analyses."""

    def test_style_returns_valid_result(self):
        """determine_style returns StyleResult with valid archetype."""
        radar = make_radar()
        tag_counts: dict[MeaningTagId, int] = {}

        result = determine_style(radar, tag_counts)

        assert isinstance(result, StyleResult)
        assert result.archetype is not None
        assert result.archetype.id in StyleArchetypeId
        assert 0.0 <= result.confidence <= 1.0

    def test_pacing_returns_valid_result(self):
        """analyze_pacing returns PacingAnalysisResult with valid structure."""
        time_data = make_time_data([1, 2, 3, 4, 5])
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=0.5) for i in range(1, 6)]

        result = analyze_pacing(time_data, moves)

        assert isinstance(result, PacingAnalysisResult)
        assert isinstance(result.pacing_metrics, tuple)
        assert isinstance(result.tilt_episodes, tuple)
        assert result.game_stats is not None

    def test_risk_returns_valid_result(self):
        """analyze_risk returns RiskAnalysisResult with valid structure."""
        game = make_mock_game_with_nodes(5)

        result = analyze_risk(game)

        assert isinstance(result, RiskAnalysisResult)
        assert isinstance(result.contexts, tuple)
        assert isinstance(result.has_stdev_data, bool)
        assert isinstance(result.fallback_used, bool)

    def test_all_analyses_complete_without_error(self):
        """All three analyses complete without raising exceptions."""
        # Style
        radar = make_radar(fighting=4.5)  # High fighting
        tag_counts = {MeaningTagId.CAPTURE_RACE_LOSS: 3}
        style_result = determine_style(radar, tag_counts)
        assert style_result is not None

        # Pacing
        time_data = make_time_data([1, 2, 3])
        moves = [make_move_eval(i, score_loss=0.1) for i in range(1, 4)]
        pacing_result = analyze_pacing(time_data, moves)
        assert pacing_result is not None

        # Risk
        game = make_mock_game_with_nodes(3)
        risk_result = analyze_risk(game)
        assert risk_result is not None


# =============================================================================
# TestCuratorEndToEnd
# =============================================================================


class TestCuratorEndToEnd:
    """End-to-end tests for Curator output."""

    def test_curator_ranking_schema(self, tmp_path):
        """Curator ranking output has required schema fields."""
        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=str(tmp_path),
            batch_timestamp="20260126-120000",
        )

        assert result.ranking_path is not None
        with open(result.ranking_path, encoding="utf-8") as f:
            ranking = json.load(f)

        # Required fields
        assert "version" in ranking
        assert "generated" in ranking
        assert "total_games" in ranking
        assert "rankings" in ranking
        assert isinstance(ranking["rankings"], list)

    def test_curator_replay_guide_schema(self, tmp_path):
        """Curator replay guide output has required schema fields."""
        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=str(tmp_path),
            batch_timestamp="20260126-120000",
        )

        assert result.guide_path is not None
        with open(result.guide_path, encoding="utf-8") as f:
            guide = json.load(f)

        # Required fields
        assert "version" in guide
        assert "generated" in guide
        assert "total_games" in guide
        assert "games" in guide
        assert isinstance(guide["games"], list)

    def test_curator_output_deterministic(self, tmp_path):
        """Same input produces identical output (excluding timestamp)."""
        timestamp = "20260126-120000"

        # Run 1
        run1_dir = tmp_path / "run1"
        result1 = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=str(run1_dir),
            batch_timestamp=timestamp,
        )

        # Run 2
        run2_dir = tmp_path / "run2"
        result2 = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=str(run2_dir),
            batch_timestamp=timestamp,
        )

        # Ranking comparison
        with open(result1.ranking_path, encoding="utf-8") as f:
            ranking1 = normalize_json_for_comparison(json.load(f))
        with open(result2.ranking_path, encoding="utf-8") as f:
            ranking2 = normalize_json_for_comparison(json.load(f))
        assert ranking1 == ranking2, "Ranking output is not deterministic"

        # Guide comparison
        with open(result1.guide_path, encoding="utf-8") as f:
            guide1 = normalize_json_for_comparison(json.load(f))
        with open(result2.guide_path, encoding="utf-8") as f:
            guide2 = normalize_json_for_comparison(json.load(f))
        assert guide1 == guide2, "Guide output is not deterministic"


# =============================================================================
# TestBatchWithCurator
# =============================================================================


class TestBatchWithCurator:
    """Batch processing with Curator integration."""

    def test_batch_generates_curator_files(self, tmp_path):
        """generate_curator_outputs creates both ranking and guide files."""
        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=str(tmp_path),
            batch_timestamp="20260126-120000",
        )

        assert result.ranking_path is not None
        assert result.guide_path is not None
        assert Path(result.ranking_path).exists()
        assert Path(result.guide_path).exists()

    def test_batch_empty_input_produces_valid_empty_json(self, tmp_path):
        """Empty input produces valid JSON with empty lists."""
        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=str(tmp_path),
            batch_timestamp="20260126-120000",
        )

        assert result.ranking_path is not None
        assert result.guide_path is not None

        # Ranking validation
        with open(result.ranking_path, encoding="utf-8") as f:
            ranking = json.load(f)
        assert ranking["total_games"] == 0
        assert ranking["rankings"] == []

        # Guide validation
        with open(result.guide_path, encoding="utf-8") as f:
            guide = json.load(f)
        assert guide["total_games"] == 0
        assert guide["games"] == []


# =============================================================================
# TestBatchPerformance
# =============================================================================


@pytest.mark.slow
class TestBatchPerformance:
    """Performance tests (excluded from CI by default)."""

    def test_batch_processing_overhead(self):
        """Each feature's processing overhead is within acceptable limits.

        Goal: Detect order-of-magnitude regressions.
        Threshold: 100 calls < 5.0s (generous for slow machines).
        """
        # Style analysis
        radar = make_radar()
        tag_counts: dict[MeaningTagId, int] = {}

        start = time.perf_counter()
        for _ in range(100):
            determine_style(radar, tag_counts)
        style_elapsed = time.perf_counter() - start
        assert style_elapsed < 5.0, (
            f"Style analysis: {style_elapsed:.2f}s for 100 calls (limit: 5.0s)"
        )

        # Pacing analysis
        time_data = make_time_data([1, 2, 3, 4, 5])
        moves = [make_move_eval(i, score_loss=0.5) for i in range(1, 6)]

        start = time.perf_counter()
        for _ in range(100):
            analyze_pacing(time_data, moves)
        pacing_elapsed = time.perf_counter() - start
        assert pacing_elapsed < 5.0, (
            f"Pacing analysis: {pacing_elapsed:.2f}s for 100 calls (limit: 5.0s)"
        )

        # Risk analysis
        game = make_mock_game_with_nodes(5)

        start = time.perf_counter()
        for _ in range(100):
            analyze_risk(game)
        risk_elapsed = time.perf_counter() - start
        assert risk_elapsed < 5.0, (
            f"Risk analysis: {risk_elapsed:.2f}s for 100 calls (limit: 5.0s)"
        )
