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
from unittest.mock import MagicMock

import pytest

from katrain.core.eval_metrics import (
    MoveEval,
    MistakeCategory,
    PositionDifficulty,
)
from katrain.core.game import Game, Move
from katrain.core.game_node import GameNode


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"


# ---------------------------------------------------------------------------
# CI Environment Detection
# ---------------------------------------------------------------------------

def is_ci_environment() -> bool:
    """
    Detect whether running in a CI environment.

    Checks multiple CI provider environment variables with proper value validation.
    Avoids false positives from CI=false or empty values.

    Returns:
        True if running in CI, False otherwise.
    """
    truthy_values = ("true", "1", "yes")

    # CI providers that set boolean-like values
    ci_env_vars = [
        "CI",             # Generic (GitHub Actions, GitLab CI, etc.)
        "GITHUB_ACTIONS", # GitHub Actions
        "GITLAB_CI",      # GitLab CI
        "CIRCLECI",       # CircleCI
        "TRAVIS",         # Travis CI
        "BUILDKITE",      # Buildkite
    ]

    for var in ci_env_vars:
        value = os.environ.get(var, "").lower()
        if value in truthy_values:
            return True

    # JENKINS_URL is set to the URL, so existence check is sufficient
    if os.environ.get("JENKINS_URL"):
        return True

    return False


# ---------------------------------------------------------------------------
# Normalization for Golden Tests
# ---------------------------------------------------------------------------

def normalize_output(text: str) -> str:
    """
    Normalize Karte/Summary output for golden test comparison.

    Normalizes:
    1. Line endings → LF only (handles CRLF and CR)
    2. Timestamps → [TIMESTAMP]
    3. Absolute paths → [PATH]
    4. Floating point numbers → 1 decimal place
    5. Trailing newlines → single trailing newline

    Does NOT normalize:
    - Order of sections (fixed by code)
    - Order of moves (deterministic tiebreaks in code)
    - Evidence order (deterministic tiebreaks in code)
    """
    # 1. Normalize line endings first (before other processing)
    # Order matters: \r\n first, then remaining \r
    result = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Normalize timestamps (various formats)
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
    # Time format: 12:34:56 (colon-separated)
    result = re.sub(
        r'\d{2}:\d{2}:\d{2}',
        '[TIME]',
        result
    )
    # Time format: 12 34 56 (space-separated, as in game_id from filename)
    result = re.sub(
        r'\d{2} \d{2} \d{2}',
        '[TIME]',
        result
    )

    # 3. Normalize absolute paths (Windows and Unix)
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

    # 4. Normalize floating point numbers to 1 decimal place
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

    # 5. Normalize trailing newlines (single trailing newline)
    result = result.rstrip("\n") + "\n"

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
# Radar Normalization for Golden Tests (Phase 52-B)
# ---------------------------------------------------------------------------

# Imports for Radar normalization (local to avoid polluting module namespace)
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import json
from typing import Any

# Top-level only schema fill. Nested values are data-dependent.
# This matches RadarMetrics.to_dict() output structure.
RADAR_SCHEMA_DEFAULTS = {
    "scores": {},
    "tiers": {},
    "overall_tier": None,
    "valid_move_counts": {},
}


def round_half_up(value: float, decimals: int = 2) -> float:
    """
    Round using ROUND_HALF_UP (not banker's rounding).

    For decimals=2:
    - round_half_up(2.545) = 2.55 (banker's would give 2.54)
    - round_half_up(3.145) = 3.15 (banker's would give 3.14)

    Args:
        value: The float value to round
        decimals: Number of decimal places (default 2)

    Returns:
        Rounded float, or None if input is None
    """
    if value is None:
        return None
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -decimals, rounding=ROUND_HALF_UP))


def _stabilize_float(v: float) -> float:
    """
    Re-parse via JSON to ensure stable repr (e.g., 2.55 not 2.5500...003).

    This handles floating point representation issues by round-tripping
    through JSON serialization with fixed decimal formatting.
    """
    return json.loads(f"{v:.2f}")


def normalize_radar_output(radar_dict: dict) -> str:
    """
    Normalize radar output for deterministic golden comparison.

    This function:
    1. Fills missing top-level keys with schema defaults
    2. Normalizes floats using ROUND_HALF_UP to 2 decimal places
    3. Stabilizes float representation via JSON round-trip
    4. Converts Enum values to their string representation
    5. Sorts dict keys alphabetically
    6. Preserves list order (semantically meaningful)

    Args:
        radar_dict: A dict from RadarMetrics.to_dict() or similar

    Returns:
        Deterministic JSON string with sorted keys and 2-space indent
    """
    # Top-level schema fill only
    filled = {**RADAR_SCHEMA_DEFAULTS, **radar_dict}

    def normalize(obj: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, Enum):  # Check Enum before str (for str, Enum classes)
            return obj.value
        if isinstance(obj, float):
            return _stabilize_float(round_half_up(obj, 2))
        if isinstance(obj, dict):
            return {k: normalize(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            # No sorting - list order is semantically meaningful
            return [normalize(x) for x in obj]
        return obj

    normalized = normalize(filled)
    return json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False)


def load_golden_json(name: str) -> dict:
    """Load golden JSON file and parse it."""
    golden_path = GOLDEN_DIR / name
    if not golden_path.exists():
        raise FileNotFoundError(f"Golden JSON file not found: {golden_path}")
    return json.loads(golden_path.read_text(encoding="utf-8"))


def save_golden_json(name: str, data: dict) -> None:
    """Save data to golden JSON file with consistent formatting."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_path = GOLDEN_DIR / name
    content = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    golden_path.write_text(content + "\n", encoding="utf-8")


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


# ---------------------------------------------------------------------------
# Phase 70: Game/Engine Test Infrastructure
# ---------------------------------------------------------------------------


class MockKaTrainStub:
    """Lightweight stub for KaTrain.

    Provides minimal interface needed by Game without KaTrainBase inheritance.

    MINIMAL REQUIRED INTERFACE (v6):
    --------------------------------
    Attributes:
        pondering: bool            - Used by STOP mode (set to False)
        controls: object           - Needs .set_status() method for status messages

    Methods:
        config(key, default=None)  - Used by Game for thresholds/rules lookup
        log(*args, **kwargs)       - Called for debug output (can be no-op)
    """
    def __init__(self):
        self.pondering = False
        self.controls = MagicMock()
        self._config = {
            "trainer/eval_thresholds": [0, 0.5, 1.0, 2.0, 5.0],
            "game/handicap": 0,
            "game/rules": "japanese",
        }

    def config(self, key, default=None):
        return self._config.get(key, default)

    def log(self, *args, **kwargs):
        pass


class MockEngine:
    """Mock engine with call tracking.

    MINIMAL REQUIRED INTERFACE (v7):
    --------------------------------
    Attributes:
        config: dict               - Needs "max_visits", "fast_visits" keys

    Methods:
        request_analysis(*args, **kwargs)  - Called by node.analyze()
        stop_pondering()                   - Called by STOP mode
        terminate_queries()                - Called by STOP mode
        has_query_capacity(headroom)       - Called by analyze_all_nodes() for throttling

    Tracking (test-only):
        stop_pondering_called: bool
        terminate_queries_called: bool
        request_analysis_calls: List[dict]
        reset_tracking()
    """
    def __init__(self, config=None):
        self.config = config or {"max_visits": 100, "fast_visits": 50}
        self.stop_pondering_called = False
        self.terminate_queries_called = False
        self.request_analysis_calls = []

    def request_analysis(self, *args, **kwargs):
        """Track analysis requests for assertion."""
        self.request_analysis_calls.append({"args": args, "kwargs": kwargs})

    def stop_pondering(self):
        self.stop_pondering_called = True

    def terminate_queries(self):
        self.terminate_queries_called = True

    def has_query_capacity(self, headroom: int = 10) -> bool:
        """Mock always has capacity (no throttling in tests)."""
        return True

    def reset_tracking(self):
        """Reset call tracking for fresh assertions."""
        self.stop_pondering_called = False
        self.terminate_queries_called = False
        self.request_analysis_calls = []


# ---------------------------------------------------------------------------
# Analysis State Factories (v6)
# ---------------------------------------------------------------------------

def make_analysis(
    *,
    root_present: bool = True,
    completed: bool = True,
    moves: dict = None,
    score: float = 0.0,
    visits: int = 500,
) -> dict:
    """Factory for creating analysis dict with explicit state control.

    Args:
        root_present: If True, include "root" dict; if False, set to None
        completed: Value for "completed" flag
        moves: Dict of move candidates (default: {"D4": {...}})
        score: scoreLead value (used if root_present=True)
        visits: visits value for root and moves

    Returns:
        Analysis dict matching GameNode.analysis structure

    Examples:
        # Complete analysis with moves
        make_analysis(score=5.0)

        # Incomplete analysis (analysis_complete=False)
        make_analysis(completed=False)

        # No root (analysis_exists=False when root is None)
        make_analysis(root_present=False)

        # Empty moves (triggers LOCAL mode bug)
        make_analysis(moves={})
    """
    if moves is None:
        moves = {"D4": {"visits": visits // 5, "scoreLead": score}}

    return {
        "root": {"scoreLead": score, "visits": visits} if root_present else None,
        "moves": moves,
        "completed": completed,
        "ownership": None,
        "policy": None,
    }


def setup_analyzed_node(node, score, parent_score=None, *, force_parent=False):
    """Setup analysis data on a node for testing.

    For points_lost to work correctly, both node and parent need analysis.

    BEHAVIOR (v6 - fixed):
    - Always sets node.analysis
    - Only sets parent.analysis if:
      a) parent_score is provided, AND
      b) parent exists, AND
      c) parent.analysis is not already set (or force_parent=True)

    Args:
        node: GameNode to setup
        score: scoreLead for this node
        parent_score: scoreLead for parent (optional)
        force_parent: If True, overwrite parent.analysis even if already set

    Example:
        # Simple: just set node analysis
        setup_analyzed_node(node, score=5.0)

        # With parent for points_lost calculation
        setup_analyzed_node(node, score=5.0, parent_score=0.0)

        # Chain setup (preserves earlier parent analysis)
        setup_analyzed_node(node1, score=0.0)
        setup_analyzed_node(node2, score=3.0, parent_score=0.0)  # Sets node2's parent
        setup_analyzed_node(node3, score=5.0)  # node2 already has analysis, not overwritten
    """
    node.analysis = make_analysis(score=score)

    if node.parent and parent_score is not None:
        # Only set parent analysis if not already set (or forced)
        parent_has_analysis = (
            node.parent.analysis.get("root") is not None
            if isinstance(node.parent.analysis, dict)
            else False
        )
        if force_parent or not parent_has_analysis:
            node.parent.analysis = make_analysis(score=parent_score, moves={})


# ---------------------------------------------------------------------------
# Game/Engine Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_katrain():
    """Lightweight KaTrain stub."""
    return MockKaTrainStub()


@pytest.fixture
def mock_engine():
    """Single mock engine."""
    return MockEngine()


@pytest.fixture
def mock_engines():
    """Separate engines for B and W (for STOP mode tests)."""
    return {"B": MockEngine(), "W": MockEngine()}


@pytest.fixture
def root_node():
    """Create a root GameNode (19x19)."""
    return GameNode(properties={"SZ": 19})


@pytest.fixture
def root_node_9x9():
    """Create a root GameNode (9x9)."""
    return GameNode(properties={"SZ": 9})


@pytest.fixture
def game(mock_katrain, mock_engine, root_node):
    """Create a Game instance for testing.

    Note: Game.__init__ converts single engine to {"B": engine, "W": engine}
    """
    # Reset tracking (Game.__init__ calls stop_pondering)
    mock_engine.reset_tracking()
    g = Game(mock_katrain, mock_engine, move_tree=root_node)
    mock_engine.reset_tracking()  # Reset again after init
    return g


@pytest.fixture
def game_with_separate_engines(mock_katrain, mock_engines, root_node):
    """Create a Game with separate B/W engines for STOP mode tests."""
    for e in mock_engines.values():
        e.reset_tracking()
    g = Game(mock_katrain, mock_engines, move_tree=root_node)
    for e in mock_engines.values():
        e.reset_tracking()
    return g


@pytest.fixture
def game_9x9(mock_katrain, mock_engine, root_node_9x9):
    """Create a 9x9 Game instance."""
    mock_engine.reset_tracking()
    g = Game(mock_katrain, mock_engine, move_tree=root_node_9x9)
    mock_engine.reset_tracking()
    return g
