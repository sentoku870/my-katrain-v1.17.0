"""Pytest fixtures for KaTrain's test suite.

Not prefixed with ``test_`` so pytest does not try to collect this
module. Re-exported by ``tests/conftest.py`` via ``from tests._fixtures
import *``.

Exports:

- :func:`mock_katrain` — :class:`tests._factories.MockKaTrainStub` instance.
- :func:`mock_engine` / :func:`mock_engines` — engine stub(s).
- :func:`root_node` / :func:`root_node_9x9` — ``GameNode`` roots.
- :func:`game` / :func:`game_with_separate_engines` / :func:`game_9x9` —
  ``Game`` instances.
- :func:`make_moves` — factory producing lists of ``MoveEval`` objects.
- :func:`all_zero_visits_moves` / :func:`extreme_high_visits_moves` /
  :func:`partial_analysis_suffix_missing` / :func:`partial_analysis_scattered`
  — pre-built edge-case MoveEval lists for confidence gating tests.
- :func:`real_shape_summary` — canonical Shape-B Summary JSON.
"""

from __future__ import annotations

import pytest

from katrain.core.game import Game
from katrain.core.game_node import GameNode
from tests._factories import (
    MockEngine,
    MockKaTrainStub,
)
from tests._factories import (
    make_moves as _make_moves_impl,
)

# ---------------------------------------------------------------------------
# Game/Engine fixtures
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
    """Create a root ``GameNode`` (19x19)."""
    return GameNode(properties={"SZ": 19})


@pytest.fixture
def root_node_9x9():
    """Create a root ``GameNode`` (9x9)."""
    return GameNode(properties={"SZ": 9})


@pytest.fixture
def game(mock_katrain, mock_engine, root_node):
    """Create a ``Game`` instance for testing.

    Note: ``Game.__init__`` converts a single engine to
    ``{"B": engine, "W": engine}``.
    """
    # Reset tracking (Game.__init__ calls stop_pondering)
    mock_engine.reset_tracking()
    g = Game(mock_katrain, mock_engine, move_tree=root_node)
    mock_engine.reset_tracking()  # Reset again after init
    return g


@pytest.fixture
def game_with_separate_engines(mock_katrain, mock_engines, root_node):
    """Create a ``Game`` with separate B/W engines for STOP mode tests."""
    for e in mock_engines.values():
        e.reset_tracking()
    g = Game(mock_katrain, mock_engines, move_tree=root_node)
    for e in mock_engines.values():
        e.reset_tracking()
    return g


@pytest.fixture
def game_9x9(mock_katrain, mock_engine, root_node_9x9):
    """Create a 9x9 ``Game`` instance."""
    mock_engine.reset_tracking()
    g = Game(mock_katrain, mock_engine, move_tree=root_node_9x9)
    mock_engine.reset_tracking()
    return g


# ---------------------------------------------------------------------------
# MoveEval factory fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_moves():
    """Factory fixture: create a list of ``MoveEval`` objects.

    Delegates to ``tests._factories.make_moves``. We import the
    implementation under an alias (``_make_moves_impl``) to avoid a
    name collision: this fixture is named ``make_moves``, and the
    inner closure must NOT shadow the factory by binding to itself.
    """

    def _make_moves(
        count: int = 10,
        *,
        player: str = "B",
        visits: int = 500,
        loss_pattern: list[float] | None = None,
    ) -> list:
        return _make_moves_impl(
            count,
            player=player,
            visits=visits,
            loss_pattern=loss_pattern,
        )

    return _make_moves


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
# Karte / Summary shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_shape_summary() -> dict:
    """Canonical Shape-B Summary JSON used by the coach validator, prompt
    builder, and Shape-B extractor test suites.

    The data mirrors what ``katrain.core.reports.summary_json_export``
    actually emits: a ``players.<name>.{mistakes,phases}`` layout (no
    top-level ``weaknesses`` or ``phase_x_mistake`` arrays). Tests that
    want fewer mistakes or phases should deep-copy and mutate the dict
    rather than edit this fixture in place.

    Function-scoped so each test gets a fresh dict; mutation never leaks.
    """
    return {
        "schema_version": "3.4",
        "meta": {
            "games_analyzed": 3,
            "date_range": ["2025-10-31", "2025-11-06"],
            "games_by_type": {"even": 3, "handicapped": 0, "unknown": 0},
        },
        "games": [{"game_id": "g1"}, {"game_id": "g2"}, {"game_id": "g3"}],
        "players": {
            "sentoku870": {
                "mistakes": {
                    "good": {"count": 310, "pct": 79.9, "denominator": 388, "avg_loss": 0.28},
                    "inaccuracy": {"count": 51, "pct": 13.1, "denominator": 388, "avg_loss": 3.11},
                    "mistake": {"count": 22, "pct": 5.7, "denominator": 388, "avg_loss": 5.69},
                    "blunder": {"count": 5, "pct": 1.3, "denominator": 388, "avg_loss": 19.04},
                },
                "phases": {
                    "opening": {"moves": 75, "total_loss": 47.01, "avg_loss": 0.627},
                    "middle": {"moves": 173, "total_loss": 370.78, "avg_loss": 2.143},
                    "endgame": {"moves": 140, "total_loss": 48.6, "avg_loss": 0.347},
                },
            },
            "opponent1": {
                "mistakes": {
                    "good": {"count": 350, "pct": 90.2, "denominator": 388, "avg_loss": 0.22},
                    "inaccuracy": {"count": 28, "pct": 7.2, "denominator": 388, "avg_loss": 2.95},
                    "mistake": {"count": 8, "pct": 2.1, "denominator": 388, "avg_loss": 5.5},
                    "blunder": {"count": 2, "pct": 0.5, "denominator": 388, "avg_loss": 18.0},
                },
                "phases": {
                    "opening": {"moves": 75, "total_loss": 30.0, "avg_loss": 0.4},
                    "middle": {"moves": 173, "total_loss": 150.0, "avg_loss": 0.87},
                    "endgame": {"moves": 140, "total_loss": 25.0, "avg_loss": 0.18},
                },
            },
        },
        "loss_progression": {"all": [{"mistake_count": 5}] * 3},
    }
