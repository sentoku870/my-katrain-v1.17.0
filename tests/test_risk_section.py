"""Tests for Risk Management section.

Phase 62: Risk Integration

Design notes:
- Uses duck-typed stubs (StubContext, StubStats, StubResult) to decouple from Phase 61
- Tests for classify/extract/format functions use stubs only
- TestCanonicalImports verifies real dataclass imports work (smoke test)
- i18n-independent: tests do not assert exact translated strings

Duck-typing note:
  Stub enums (JudgmentStub, BehaviorStub) inherit from (str, Enum) with the same
  string values as real enums. This allows extract_risk_display_data comparisons
  like `ctx.judgment_type == RiskJudgmentType.WINNING` to work because str
  comparison takes precedence. If Phase 61 changes enum string values, tests
  will fail - but that's intentional (it's an API contract change).
"""

from dataclasses import dataclass
from enum import StrEnum

from katrain.core.reports.sections.risk_section import (
    RiskDisplayData,
    _classify_losing_behavior,
    _classify_winning_behavior,
    extract_risk_display_data,
    format_risk_stats,
)

# ============================================================
# Duck-typed stubs (decoupled from Phase 61 dataclasses)
# ============================================================


class JudgmentStub(StrEnum):
    """Stub for RiskJudgmentType (only WINNING/LOSING needed for Phase 62)."""

    WINNING = "winning"
    LOSING = "losing"


class BehaviorStub(StrEnum):
    """Stub for RiskBehavior."""

    SOLID = "solid"
    COMPLICATING = "complicating"


@dataclass
class StubStats:
    """Minimal stub for PlayerRiskStats."""

    mismatch_count: int = 0


@dataclass
class StubContext:
    """Minimal stub for RiskContext (only fields used by extract_risk_display_data)."""

    player: str
    judgment_type: JudgmentStub
    risk_behavior: BehaviorStub


@dataclass
class StubResult:
    """Minimal stub for RiskAnalysisResult."""

    contexts: tuple
    black_stats: StubStats
    white_stats: StubStats
    fallback_used: bool = False


def make_stub_context(
    player: str,
    judgment: JudgmentStub,
    behavior: BehaviorStub,
) -> StubContext:
    """Create a stub context for testing."""
    return StubContext(player=player, judgment_type=judgment, risk_behavior=behavior)


def make_stub_result(
    contexts: tuple,
    black_mismatch: int = 0,
    white_mismatch: int = 0,
    fallback_used: bool = False,
) -> StubResult:
    """Create a stub result for testing."""
    return StubResult(
        contexts=contexts,
        black_stats=StubStats(mismatch_count=black_mismatch),
        white_stats=StubStats(mismatch_count=white_mismatch),
        fallback_used=fallback_used,
    )


class TestClassifyWinningBehavior:
    """Tests for _classify_winning_behavior function."""

    def test_solid_high(self):
        """75% SOLID when winning -> solid."""
        assert _classify_winning_behavior(75) == "risk:solid"

    def test_solid_boundary_61(self):
        """61% SOLID when winning -> solid (boundary)."""
        assert _classify_winning_behavior(61) == "risk:solid"

    def test_mixed_boundary_60(self):
        """60% SOLID when winning -> mixed (boundary)."""
        assert _classify_winning_behavior(60) == "risk:mixed"

    def test_mixed_boundary_40(self):
        """40% SOLID when winning -> mixed (boundary)."""
        assert _classify_winning_behavior(40) == "risk:mixed"

    def test_risk_taker_boundary_39(self):
        """39% SOLID when winning -> risk_taker (boundary)."""
        assert _classify_winning_behavior(39) == "risk:risk_taker"

    def test_risk_taker_low(self):
        """20% SOLID when winning -> risk_taker."""
        assert _classify_winning_behavior(20) == "risk:risk_taker"


class TestClassifyLosingBehavior:
    """Tests for _classify_losing_behavior function."""

    def test_fighter_high(self):
        """75% COMPLICATING when losing -> fighter."""
        assert _classify_losing_behavior(75) == "risk:fighter"

    def test_fighter_boundary_61(self):
        """61% COMPLICATING when losing -> fighter (boundary)."""
        assert _classify_losing_behavior(61) == "risk:fighter"

    def test_mixed_boundary_60(self):
        """60% COMPLICATING when losing -> mixed (boundary)."""
        assert _classify_losing_behavior(60) == "risk:mixed"

    def test_mixed_boundary_40(self):
        """40% COMPLICATING when losing -> mixed (boundary)."""
        assert _classify_losing_behavior(40) == "risk:mixed"

    def test_resigned_boundary_39(self):
        """39% COMPLICATING when losing -> resigned (boundary)."""
        assert _classify_losing_behavior(39) == "risk:resigned"

    def test_resigned_low(self):
        """20% COMPLICATING when losing -> resigned."""
        assert _classify_losing_behavior(20) == "risk:resigned"


class TestExtractRiskDisplayData:
    """Tests for extract_risk_display_data function.

    Uses duck-typed stubs to decouple from Phase 61 dataclasses.
    Key: denominators are computed from contexts, not stats.
    """

    def test_no_contexts_no_data(self):
        """Empty contexts -> no winning/losing data."""
        result = make_stub_result(())
        data = extract_risk_display_data(result, "B")
        assert data.winning_solid_pct is None
        assert data.losing_complicating_pct is None
        assert data.has_winning_data is False
        assert data.has_losing_data is False

    def test_winning_solid_75_percent(self):
        """3/4 SOLID when winning -> 75%."""
        contexts = (
            make_stub_context("B", JudgmentStub.WINNING, BehaviorStub.SOLID),
            make_stub_context("B", JudgmentStub.WINNING, BehaviorStub.SOLID),
            make_stub_context("B", JudgmentStub.WINNING, BehaviorStub.SOLID),
            make_stub_context("B", JudgmentStub.WINNING, BehaviorStub.COMPLICATING),
        )
        result = make_stub_result(contexts)
        data = extract_risk_display_data(result, "B")
        assert data.winning_solid_pct == 75.0
        assert data.has_winning_data is True

    def test_losing_complicating_40_percent(self):
        """2/5 COMPLICATING when losing -> 40%."""
        contexts = (
            make_stub_context("B", JudgmentStub.LOSING, BehaviorStub.COMPLICATING),
            make_stub_context("B", JudgmentStub.LOSING, BehaviorStub.COMPLICATING),
            make_stub_context("B", JudgmentStub.LOSING, BehaviorStub.SOLID),
            make_stub_context("B", JudgmentStub.LOSING, BehaviorStub.SOLID),
            make_stub_context("B", JudgmentStub.LOSING, BehaviorStub.SOLID),
        )
        result = make_stub_result(contexts)
        data = extract_risk_display_data(result, "B")
        assert data.losing_complicating_pct == 40.0
        assert data.has_losing_data is True

    def test_only_winning_no_losing(self):
        """Only WINNING contexts -> no losing data."""
        contexts = (make_stub_context("B", JudgmentStub.WINNING, BehaviorStub.SOLID),)
        result = make_stub_result(contexts)
        data = extract_risk_display_data(result, "B")
        assert data.winning_solid_pct == 100.0
        assert data.losing_complicating_pct is None
        assert data.has_losing_data is False

    def test_only_losing_no_winning(self):
        """Only LOSING contexts -> no winning data."""
        contexts = (make_stub_context("B", JudgmentStub.LOSING, BehaviorStub.COMPLICATING),)
        result = make_stub_result(contexts)
        data = extract_risk_display_data(result, "B")
        assert data.winning_solid_pct is None
        assert data.losing_complicating_pct == 100.0
        assert data.has_winning_data is False

    def test_player_filtering_black(self):
        """Only counts contexts for Black player."""
        contexts = (
            make_stub_context("B", JudgmentStub.WINNING, BehaviorStub.SOLID),
            make_stub_context("W", JudgmentStub.WINNING, BehaviorStub.COMPLICATING),
        )
        result = make_stub_result(contexts)
        black_data = extract_risk_display_data(result, "B")
        assert black_data.winning_solid_pct == 100.0

    def test_player_filtering_white(self):
        """Only counts contexts for White player."""
        contexts = (
            make_stub_context("B", JudgmentStub.WINNING, BehaviorStub.SOLID),
            make_stub_context("W", JudgmentStub.WINNING, BehaviorStub.COMPLICATING),
        )
        result = make_stub_result(contexts)
        white_data = extract_risk_display_data(result, "W")
        assert white_data.winning_solid_pct == 0.0

    def test_mismatch_count_from_stats(self):
        """Mismatch count is extracted from stats."""
        contexts = (
            make_stub_context("B", JudgmentStub.WINNING, BehaviorStub.COMPLICATING),
            make_stub_context("B", JudgmentStub.LOSING, BehaviorStub.SOLID),
            make_stub_context("W", JudgmentStub.WINNING, BehaviorStub.COMPLICATING),
        )
        # Mismatch counts are provided directly to stub (not auto-derived)
        result = make_stub_result(contexts, black_mismatch=2, white_mismatch=1)
        assert extract_risk_display_data(result, "B").mismatch_count == 2
        assert extract_risk_display_data(result, "W").mismatch_count == 1


class TestFormatRiskStats:
    """Tests for format_risk_stats function."""

    def test_no_data_returns_empty(self):
        """No winning or losing data -> empty list."""
        data = RiskDisplayData(
            player="B",
            winning_solid_pct=None,
            losing_complicating_pct=None,
            mismatch_count=0,
            has_winning_data=False,
            has_losing_data=False,
        )
        lines = format_risk_stats(data, fallback_used=False)
        assert lines == []

    def test_fallback_suffix_added(self):
        """Fallback used -> suffix appended (i18n-independent check)."""
        data = RiskDisplayData(
            player="B",
            winning_solid_pct=75.0,
            losing_complicating_pct=None,
            mismatch_count=0,
            has_winning_data=True,
            has_losing_data=False,
        )
        lines_with_fallback = format_risk_stats(data, fallback_used=True)
        lines_without_fallback = format_risk_stats(data, fallback_used=False)
        assert len(lines_with_fallback) == 1
        assert len(lines_without_fallback) == 1
        # Fallback line should be longer (has suffix appended)
        assert len(lines_with_fallback[0]) > len(lines_without_fallback[0])

    def test_no_fallback_no_suffix(self):
        """No fallback -> no suffix (i18n-independent check)."""
        data = RiskDisplayData(
            player="B",
            winning_solid_pct=75.0,
            losing_complicating_pct=None,
            mismatch_count=0,
            has_winning_data=True,
            has_losing_data=False,
        )
        lines = format_risk_stats(data, fallback_used=False)
        assert len(lines) == 1
        # Line should end with percentage (no trailing suffix)
        assert lines[0].rstrip().endswith("%)")

    def test_mismatch_zero_not_shown(self):
        """Mismatch line NOT shown when count = 0."""
        data = RiskDisplayData(
            player="B",
            winning_solid_pct=75.0,
            losing_complicating_pct=None,
            mismatch_count=0,
            has_winning_data=True,
            has_losing_data=False,
        )
        lines = format_risk_stats(data, fallback_used=False)
        assert len(lines) == 1

    def test_mismatch_nonzero_shown(self):
        """Mismatch line shown when count > 0."""
        data = RiskDisplayData(
            player="B",
            winning_solid_pct=75.0,
            losing_complicating_pct=None,
            mismatch_count=3,
            has_winning_data=True,
            has_losing_data=False,
        )
        lines = format_risk_stats(data, fallback_used=False)
        assert len(lines) == 2
        assert "3" in lines[1]

    def test_percentage_rounded_to_integer(self):
        """Percentage is formatted as integer (rounded)."""
        data = RiskDisplayData(
            player="B",
            winning_solid_pct=66.666,
            losing_complicating_pct=None,
            mismatch_count=0,
            has_winning_data=True,
            has_losing_data=False,
        )
        lines = format_risk_stats(data, fallback_used=False)
        assert "(67%)" in lines[0]


class TestCanonicalImports:
    """Verify canonical import path works (smoke test)."""

    def test_required_symbols_importable(self):
        """Required symbols can be imported from katrain.core.analysis."""
        from katrain.core.analysis import (
            RiskBehavior,
            RiskJudgmentType,
        )

        # Minimal checks - just verify imports succeeded
        assert RiskJudgmentType.WINNING is not None
        assert RiskJudgmentType.LOSING is not None
        assert RiskBehavior.SOLID is not None
        assert RiskBehavior.COMPLICATING is not None
