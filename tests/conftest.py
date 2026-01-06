"""
Pytest configuration and shared fixtures for KaTrain tests.

This module provides:
- Common fixtures for MoveEval creation
- Golden test utilities (normalize_output, load_golden, save_golden)
- Test configuration
"""

import re
import os
from pathlib import Path
from typing import List, Optional

import pytest

from katrain.core.eval_metrics import (
    MoveEval,
    MistakeCategory,
    PositionDifficulty,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"


# ---------------------------------------------------------------------------
# Normalization for Golden Tests
# ---------------------------------------------------------------------------

def normalize_output(text: str) -> str:
    """
    Normalize Karte/Summary output for golden test comparison.

    Normalizes:
    1. Timestamps → [TIMESTAMP]
    2. Absolute paths → [PATH]
    3. Floating point numbers → 1 decimal place

    Does NOT normalize:
    - Order of sections (fixed by code)
    - Order of moves (deterministic tiebreaks in code)
    - Evidence order (deterministic tiebreaks in code)
    """
    result = text

    # 1. Normalize timestamps (various formats)
    # ISO format: 2025-01-05T12:34:56
    result = re.sub(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        '[TIMESTAMP]',
        result
    )
    # Date format: 2025-01-05
    result = re.sub(
        r'\d{4}-\d{2}-\d{2}',
        '[DATE]',
        result
    )
    # Time format: 12:34:56
    result = re.sub(
        r'\d{2}:\d{2}:\d{2}',
        '[TIME]',
        result
    )

    # 2. Normalize absolute paths (Windows and Unix)
    # Windows: D:\github\... or C:\Users\...
    result = re.sub(
        r'[A-Z]:\\[^\s\]]+',
        '[PATH]',
        result
    )
    # Unix: /home/... or /tmp/...
    result = re.sub(
        r'/(?:home|tmp|var|usr)[^\s\]]*',
        '[PATH]',
        result
    )

    # 3. Normalize floating point numbers to 1 decimal place
    # Match numbers like 3.14159 or -12.345 (but not integers)
    def round_float(match):
        num = float(match.group(0))
        # Keep sign, round to 1 decimal
        return f"{num:.1f}"

    # Match floats that have decimal points with 2+ digits after
    result = re.sub(
        r'-?\d+\.\d{2,}',
        round_float,
        result
    )

    return result


def load_golden(name: str) -> str:
    """Load golden file content."""
    golden_path = GOLDEN_DIR / name
    if not golden_path.exists():
        raise FileNotFoundError(f"Golden file not found: {golden_path}")
    return golden_path.read_text(encoding="utf-8")


def save_golden(name: str, content: str) -> None:
    """Save content to golden file."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_path = GOLDEN_DIR / name
    golden_path.write_text(content, encoding="utf-8")


def update_golden_if_requested(name: str, content: str, request: pytest.FixtureRequest) -> None:
    """Update golden file if --update-goldens flag is passed."""
    if request.config.getoption("--update-goldens", default=False):
        save_golden(name, content)


# ---------------------------------------------------------------------------
# Pytest Configuration
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Update golden test files with current output",
    )


# ---------------------------------------------------------------------------
# Fixtures for creating test data
# ---------------------------------------------------------------------------

@pytest.fixture
def make_moves():
    """Factory fixture to create a list of MoveEval objects."""
    def _make_moves(
        count: int = 10,
        *,
        player: str = "B",
        visits: int = 500,
        loss_pattern: Optional[List[float]] = None,
    ) -> List[MoveEval]:
        """
        Create a list of MoveEval objects for testing.

        Args:
            count: Number of moves to create
            player: Player for all moves (or alternating if "BW")
            visits: Root visits for all moves
            loss_pattern: List of score_loss values (cycled if shorter than count)
        """
        moves = []
        if loss_pattern is None:
            loss_pattern = [0.5]  # Default: small loss

        for i in range(count):
            p = player if player in ("B", "W") else ("B" if i % 2 == 0 else "W")
            loss = loss_pattern[i % len(loss_pattern)]

            move = MoveEval(
                move_number=i + 1,
                player=p,
                gtp=f"D{i + 1}" if i < 19 else f"Q{i - 18}",
                score_before=0.0,
                score_after=-loss if p == "B" else loss,
                delta_score=-loss if p == "B" else loss,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=loss,
                realized_points_lost=None,
                root_visits=visits,
            )
            move.score_loss = max(0.0, loss)
            moves.append(move)

        return moves

    return _make_moves


@pytest.fixture
def high_confidence_moves(make_moves):
    """Fixture providing moves that result in HIGH confidence."""
    # 10 moves with high visits (500), all reliable
    return make_moves(count=10, visits=500, loss_pattern=[0.5, 1.0, 0.5, 0.5, 0.5])


@pytest.fixture
def medium_confidence_moves(make_moves):
    """Fixture providing moves that result in MEDIUM confidence."""
    # 10 moves with medium visits (180), 40% reliable
    moves = make_moves(count=10, visits=180, loss_pattern=[0.5])
    # Make some moves have lower visits
    for i in range(6, 10):
        moves[i].root_visits = 100
    return moves


@pytest.fixture
def low_confidence_moves(make_moves):
    """Fixture providing moves that result in LOW confidence."""
    # 10 moves with low visits (50), few reliable
    return make_moves(count=10, visits=50, loss_pattern=[1.0])


@pytest.fixture
def sparse_moves(make_moves):
    """Fixture providing moves with sparse analysis (< 5 moves with visits)."""
    moves = make_moves(count=20, visits=500, loss_pattern=[0.5])
    # Only 3 moves have visits > 0
    for i in range(3, 20):
        moves[i].root_visits = 0
    return moves


# ---------------------------------------------------------------------------
# Edge case fixtures for confidence gating tests
# ---------------------------------------------------------------------------

@pytest.fixture
def all_zero_visits_moves(make_moves):
    """Fixture: all moves have zero visits."""
    return make_moves(count=10, visits=0)


@pytest.fixture
def extreme_high_visits_moves(make_moves):
    """Fixture: all moves have very high visits (2000)."""
    return make_moves(count=10, visits=2000)


@pytest.fixture
def partial_analysis_suffix_missing(make_moves):
    """Fixture: first half analyzed, second half missing."""
    moves = make_moves(count=20, visits=500)
    for i in range(10, 20):
        moves[i].root_visits = 0
    return moves


@pytest.fixture
def partial_analysis_scattered(make_moves):
    """Fixture: only even-indexed moves have analysis."""
    moves = make_moves(count=20, visits=300)
    for i in range(20):
        if i % 2 == 1:
            moves[i].root_visits = 0
    return moves
