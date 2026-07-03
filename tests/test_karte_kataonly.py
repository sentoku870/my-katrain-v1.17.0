"""Tests for the Phase 159A KataGo-only path.

The Karte and Summary generators now refuse to operate on snapshots that
contain Leela data (``leela_loss_est is not None``). This file verifies
that:

- Pure KataGo games produce normal reports (no behavioural change).
- Leela-only games are rejected with ``KARTE_ERROR_CODE_NON_KATAGO``.
- Mixed-engine (KataGo + Leela) games are also rejected — Phase 159A
  tightens the old mixed-engine check so both rules share the same
  rejection code, since downstream consumers cannot distinguish "mixed"
  from "pure Leela" loss semantics.
- ``Summary`` generation raises a ``ValueError`` with a descriptive
  message naming the offending games.
- The new ``KARTE_ERROR_CODE_NON_KATAGO`` constant is exported and used.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from katrain.core.eval_metrics import (
    EvalSnapshot,
    MoveEval,
    PositionDifficulty,
)
from katrain.core.reports.karte.helpers import is_single_engine_snapshot
from katrain.core.reports.karte.models import (
    KARTE_ERROR_CODE_GENERATION_FAILED,
    KARTE_ERROR_CODE_NON_KATAGO,
    MixedEngineSnapshotError,
)
from katrain.core.reports.karte_report import build_karte_json, build_karte_report
from katrain.core.reports.summary_report import build_summary_report

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_katago_move(move_number: int, *, score_loss: float | None = 0.5) -> MoveEval:
    """Build a MoveEval with KataGo-style data only (leela_loss_est=None)."""
    from katrain.core.eval_metrics import MistakeCategory

    return MoveEval(
        move_number=move_number,
        player="B" if move_number % 2 == 1 else "W",
        gtp=f"D{move_number % 19}",
        score_before=0.0,
        score_after=-score_loss if score_loss is not None else 0.0,
        delta_score=-score_loss if score_loss is not None else 0.0,
        winrate_before=0.5,
        winrate_after=0.5,
        delta_winrate=0.0,
        points_lost=score_loss,
        realized_points_lost=None,
        root_visits=500,
        score_loss=score_loss,
        winrate_loss=0.0,
        mistake_category=MistakeCategory.INACCURACY,
        position_difficulty=PositionDifficulty.NORMAL,
        reason_tags=[],
        importance_score=0.5,
        leela_loss_est=None,
    )


def _make_leela_move(move_number: int, *, leela_loss: float = 1.5) -> MoveEval:
    """Build a MoveEval with Leela-style data only (score_loss=None)."""
    from katrain.core.eval_metrics import MistakeCategory

    return MoveEval(
        move_number=move_number,
        player="B" if move_number % 2 == 1 else "W",
        gtp=f"D{move_number % 19}",
        score_before=0.0,
        score_after=0.0,
        delta_score=None,
        winrate_before=0.5,
        winrate_after=0.5 - leela_loss * 0.01,
        delta_winrate=-leela_loss * 0.01,
        points_lost=None,
        realized_points_lost=None,
        root_visits=200,
        score_loss=None,
        winrate_loss=0.0,
        mistake_category=MistakeCategory.INACCURACY,
        position_difficulty=PositionDifficulty.NORMAL,
        reason_tags=[],
        importance_score=0.3,
        leela_loss_est=leela_loss,
    )


def _make_unanalyzed_move(move_number: int) -> MoveEval:
    """Build a MoveEval with no loss data at all."""
    from katrain.core.eval_metrics import MistakeCategory

    return MoveEval(
        move_number=move_number,
        player="B" if move_number % 2 == 1 else "W",
        gtp=f"D{move_number % 19}",
        score_before=None,
        score_after=None,
        delta_score=None,
        winrate_before=None,
        winrate_after=None,
        delta_winrate=None,
        points_lost=None,
        realized_points_lost=None,
        root_visits=0,
        score_loss=None,
        winrate_loss=None,
        mistake_category=MistakeCategory.GOOD,
        position_difficulty=PositionDifficulty.UNKNOWN,
        reason_tags=[],
        importance_score=None,
        leela_loss_est=None,
    )


def _make_mock_game(snapshot: EvalSnapshot) -> Mock:
    """Build a minimal KaTrain-style Game mock for karte/json_export entry points.

    All non-snapshot attributes must be plain strings / numbers, not Mock
    objects, otherwise JSON serialisation fails when ``build_karte_json``
    dumps the resulting dict. ``extract_game_meta`` walks these via
    ``hasattr`` / ``getattr``, so any auto-generated Mock attribute
    surfaces a non-serialisable value downstream.
    """
    game = Mock(spec=[])  # spec=[] disables auto-attribute generation
    game.snapshot = snapshot
    game.build_eval_snapshot = Mock(return_value=snapshot)
    game.board_size = [19, 19]
    game.sgf_filename = "test.sgf"
    game.game_id = "test_kataonly"
    game.komi = 6.5
    game.rules = "Japanese"
    game.katrain = None
    game.date = "2026-07-01"
    game.result = "B+R"
    game.handicap = 0
    game.player_black = "BPlayer"
    game.player_white = "WPlayer"
    game.game_name = "test_game"

    root = Mock(spec=[])
    root.handicap = None
    root.board_size = [19, 19]

    def _prop(key, default=None):
        return {
            "PB": "BPlayer",
            "PW": "WPlayer",
            "DT": "2026-07-01",
            "RE": "B+R",
            "GN": "Test",
            "KM": "6.5",
            "HA": "0",
        }.get(key, default)

    root.get_property = Mock(side_effect=_prop)
    game.root = root

    # Only emit moves with real KataGo loss (>= 1.0 point) as "important".
    important = [m for m in snapshot.moves if m.score_loss is not None and m.score_loss >= 1.0]
    game.get_important_move_evals = Mock(return_value=important)
    return game


# ---------------------------------------------------------------------------
# is_single_engine_snapshot — the predicate that gates the new behaviour
# ---------------------------------------------------------------------------


class TestIsSingleEngineSnapshotKataGoOnly:
    """Phase 159A: predicate rejects any Leela data."""

    def test_pure_katago_snapshot_is_accepted(self):
        snapshot = EvalSnapshot(
            moves=[_make_katago_move(i) for i in range(1, 11)],
        )
        assert is_single_engine_snapshot(snapshot) is True

    def test_unanalyzed_snapshot_is_accepted(self):
        snapshot = EvalSnapshot(
            moves=[_make_unanalyzed_move(i) for i in range(1, 6)],
        )
        assert is_single_engine_snapshot(snapshot) is True

    def test_pure_leela_snapshot_is_rejected(self):
        snapshot = EvalSnapshot(
            moves=[_make_leela_move(i) for i in range(1, 6)],
        )
        assert is_single_engine_snapshot(snapshot) is False

    def test_mixed_engine_snapshot_is_rejected(self):
        moves = [_make_katago_move(i) for i in range(1, 6)] + [_make_leela_move(6), _make_katago_move(7)]
        snapshot = EvalSnapshot(moves=moves)
        assert is_single_engine_snapshot(snapshot) is False

    def test_single_leela_move_in_katago_game_rejected(self):
        # Even one Leela-tagged move in an otherwise KataGo game disqualifies
        # the whole snapshot for report generation.
        moves = [_make_katago_move(i) for i in range(1, 10)] + [_make_leela_move(10)]
        snapshot = EvalSnapshot(moves=moves)
        assert is_single_engine_snapshot(snapshot) is False


# ---------------------------------------------------------------------------
# build_karte_report — error-code constants
# ---------------------------------------------------------------------------


class TestKartaErrorCodeConstant:
    def test_non_katago_error_code_is_exported(self):
        assert KARTE_ERROR_CODE_NON_KATAGO == "KARTE_ERROR_CODE: NON_KATAGO_DATA"
        assert "NON_KATAGO_DATA" in KARTE_ERROR_CODE_NON_KATAGO

    def test_generation_failed_error_code_still_exists(self):
        # Backwards compatibility: existing tests rely on this constant.
        assert KARTE_ERROR_CODE_GENERATION_FAILED == "KARTE_ERROR_CODE: GENERATION_FAILED"


# ---------------------------------------------------------------------------
# build_karte_json — silent rejection with default raise_on_error=False
# ---------------------------------------------------------------------------


class TestBuildKarteJsonRejectsLeela:
    """build_karte_json returns an ERROR karte when Leela data is present."""

    def test_pure_katago_karte_generates_normally(self):
        snapshot = EvalSnapshot(moves=[_make_katago_move(i, score_loss=1.5) for i in range(1, 11)])
        game = _make_mock_game(snapshot)
        result = build_karte_json(game)
        # No error code in result — KataGo-only path stays clean.
        dumped = json.dumps(result)
        assert KARTE_ERROR_CODE_NON_KATAGO not in dumped
        assert "summary" in result

    def test_pure_leela_karte_emits_error_code(self):
        snapshot = EvalSnapshot(moves=[_make_leela_move(i) for i in range(1, 6)])
        game = _make_mock_game(snapshot)
        result = build_karte_json(game)
        dumped = json.dumps(result)
        assert KARTE_ERROR_CODE_NON_KATAGO in dumped

    def test_mixed_engine_karte_emits_error_code(self):
        # One Leela move among several KataGo moves still triggers the gate.
        snapshot = EvalSnapshot(
            moves=[_make_katago_move(i) for i in range(1, 6)] + [_make_leela_move(6)],
        )
        game = _make_mock_game(snapshot)
        result = build_karte_json(game)
        dumped = json.dumps(result)
        assert KARTE_ERROR_CODE_NON_KATAGO in dumped

    def test_leela_karte_does_not_emit_old_mixed_engine_code(self):
        # Phase 159A unifies Leela and mixed-engine rejection under a single
        # code (NON_KATAGO_DATA). The old MIXED_ENGINE code is no longer
        # used; the predicate collapses both cases to a single False return.
        snapshot = EvalSnapshot(moves=[_make_leela_move(i) for i in range(1, 6)])
        game = _make_mock_game(snapshot)
        result = build_karte_json(game)
        dumped = json.dumps(result)
        assert "MIXED_ENGINE" not in dumped


# ---------------------------------------------------------------------------
# build_karte_report — exception-raising variant
# ---------------------------------------------------------------------------


class TestBuildKarteReportRaisesOnLeela:
    def test_pure_katago_no_raise(self):
        snapshot = EvalSnapshot(moves=[_make_katago_move(i, score_loss=1.5) for i in range(1, 11)])
        game = _make_mock_game(snapshot)
        # Should NOT raise — pure KataGo stays on the happy path.
        markdown = build_karte_report(game, raise_on_error=True)
        assert KARTE_ERROR_CODE_NON_KATAGO not in markdown

    def test_pure_leela_raises_mixed_engine_error(self):
        # Phase 159A: keeps the exception type as MixedEngineSnapshotError
        # for backwards compatibility with callers that catch it. Only the
        # error code string inside the message changed to NON_KATAGO_DATA.
        snapshot = EvalSnapshot(moves=[_make_leela_move(i) for i in range(1, 6)])
        game = _make_mock_game(snapshot)
        with pytest.raises(MixedEngineSnapshotError) as exc_info:
            build_karte_report(game, raise_on_error=True)
        assert KARTE_ERROR_CODE_NON_KATAGO in str(exc_info.value)

    def test_mixed_engine_raises_mixed_engine_error(self):
        snapshot = EvalSnapshot(
            moves=[_make_katago_move(i) for i in range(1, 6)] + [_make_leela_move(6)],
        )
        game = _make_mock_game(snapshot)
        with pytest.raises(MixedEngineSnapshotError):
            build_karte_report(game, raise_on_error=True)


# ---------------------------------------------------------------------------
# build_summary_report — ValueError gate
# ---------------------------------------------------------------------------


class TestBuildSummaryReportRejectsLeela:
    """Summary raises ValueError when any input game carries Leela data."""

    def _make_summary_data(self, moves: list[MoveEval], name: str = "g1.sgf"):
        from katrain.core.analysis.models import GameSummaryData

        snapshot = EvalSnapshot(moves=moves)
        return GameSummaryData(
            game_name=name,
            player_black="BPlayer",
            player_white="WPlayer",
            snapshot=snapshot,
            board_size=(19, 19),
            result="B+R",
            skill_preset="standard",
        )

    def test_pure_katago_summary_passes_gate(self):
        gs = self._make_summary_data(
            [_make_katago_move(i, score_loss=1.5) for i in range(1, 11)],
        )
        # Should NOT raise — pure KataGo stays on the happy path.
        markdown = build_summary_report([gs])
        data = json.loads(markdown)
        assert data["schema_version"]
        assert "players" in data

    def test_pure_leela_summary_raises_value_error(self):
        gs = self._make_summary_data(
            [_make_leela_move(i) for i in range(1, 6)],
            name="leela_only.sgf",
        )
        with pytest.raises(ValueError) as exc_info:
            build_summary_report([gs])
        assert "KataGo-only" in str(exc_info.value)
        assert "leela_only.sgf" in str(exc_info.value)

    def test_mixed_summary_with_at_least_one_leela_raises(self):
        gs_katago = self._make_summary_data(
            [_make_katago_move(i, score_loss=1.5) for i in range(1, 6)],
            name="katago.sgf",
        )
        gs_leela = self._make_summary_data(
            [_make_leela_move(i) for i in range(1, 6)],
            name="leela.sgf",
        )
        # At least one bad game -> entire run rejected.
        with pytest.raises(ValueError) as exc_info:
            build_summary_report([gs_katago, gs_leela])
        # Both names mentioned (or at least the bad one).
        assert "leela.sgf" in str(exc_info.value)

    def test_empty_summary_returns_empty_marker(self):
        # No games -> no gate needed (returns the {"games_analyzed":0} marker).
        result = build_summary_report([])
        assert "games_analyzed" in result
