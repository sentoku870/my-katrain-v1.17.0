"""Phase 35: Karte Leela integration tests.

CI-safe (no real engines), using mock/stub only.
Tests that Leela-analyzed data shows (推定) suffix in Export Karte output.
"""

from unittest.mock import Mock

import pytest

from katrain.core.analysis.models import (
    EngineType,
    EvalSnapshot,
    MistakeCategory,
    MoveEval,
)
from katrain.core.reports.karte_report import (
    KARTE_ERROR_CODE_MIXED_ENGINE,
    build_karte_report,
    format_loss_with_engine_suffix,
    has_loss_data,
)
from tests.helpers_eval_metrics import make_move_eval

# ---------------------------------------------------------------------------
# Test helper: create mock Game for build_karte_report()
# ---------------------------------------------------------------------------


def create_mock_game(moves: list[MoveEval]) -> Mock:
    """build_karte_report() 用の最小 Game モック"""
    snapshot = EvalSnapshot(moves=moves)

    game = Mock()
    game.build_eval_snapshot.return_value = snapshot

    # katrain.config() - 文字列キーを引数に取る
    # 重要: 返り値が iterable として使われる可能性があるので、None ではなく適切な型を返す
    def mock_config(key: str):
        if key == "trainer/eval_thresholds":
            return [1.0, 2.5, 5.0]  # default thresholds
        if key == "general/my_player_name":
            return None
        if key == "general/my_player_aliases":
            return []  # リストを返す（反復される）
        return None  # その他は None

    game.katrain = Mock()
    game.katrain.config = mock_config
    game.katrain.log = Mock()

    # Board/meta info
    game.board_size = (19, 19)
    game.sgf_filename = "test.sgf"
    game.komi = 6.5
    game.rules = "japanese"
    game.game_id = "test-game-id"

    # Root node mock
    game.root = Mock()
    game.root.get_property = Mock(return_value=None)
    game.root.handicap = 0
    # CRITICAL: Set children to empty list to prevent infinite loop in parse_time_data
    game.root.children = []

    # get_important_move_evals() はリストを返す必要がある
    # importance_score が設定されている手を返す
    important_moves = [mv for mv in moves if mv.importance_score is not None and mv.importance_score > 0]
    game.get_important_move_evals = Mock(return_value=important_moves)

    return game


# ---------------------------------------------------------------------------
# Test 1: has_loss_data() unit tests
# ---------------------------------------------------------------------------
class TestHasLossData:
    """Unit tests for has_loss_data()."""

    @pytest.mark.parametrize(
        "score_loss,leela_loss_est,points_lost,expected",
        [
            (3.5, None, None, True),  # KataGo
            (None, 3.5, None, True),  # Leela
            (None, None, 3.5, True),  # Legacy
            (0.0, None, None, True),  # 真の 0.0 (KataGo)
            (None, 0.0, None, True),  # 真の 0.0 (Leela)
            (None, None, None, False),  # データなし
        ],
    )
    def test_has_loss_data(self, score_loss, leela_loss_est, points_lost, expected):
        mv = make_move_eval(
            score_loss=score_loss,
            leela_loss_est=leela_loss_est,
            points_lost=points_lost,
        )
        assert has_loss_data(mv) == expected


# ---------------------------------------------------------------------------
# Test 2: format_loss_with_engine_suffix() unit tests (parametrized)
# ---------------------------------------------------------------------------
class TestFormatLossWithEngineSuffix:
    """Unit tests for format_loss_with_engine_suffix()."""

    @pytest.mark.parametrize(
        "loss_val,engine_type,expected",
        [
            # KataGo: サフィックスなし
            (6.0, EngineType.KATAGO, "6.0"),
            (0.0, EngineType.KATAGO, "0.0"),
            (3.14159, EngineType.KATAGO, "3.1"),  # 小数点1桁丸め
            # Leela: サフィックスあり
            (6.0, EngineType.LEELA, "6.0(推定)"),
            (0.0, EngineType.LEELA, "0.0(推定)"),
            (3.14159, EngineType.LEELA, "3.1(推定)"),
            # UNKNOWN: サフィックスなし（KataGo同様）
            (6.0, EngineType.UNKNOWN, "6.0"),
            # None: "unknown"（サフィックスなし）
            (None, EngineType.KATAGO, "unknown"),
            (None, EngineType.LEELA, "unknown"),
        ],
    )
    def test_format_loss(self, loss_val, engine_type, expected):
        result = format_loss_with_engine_suffix(loss_val, engine_type)
        assert result == expected


# ---------------------------------------------------------------------------
# Test 3-5: Leela / KataGo suffix assertions (Phase 138 — REMOVED)
# ---------------------------------------------------------------------------
# Phase 137 changed the Karte summary so the (推定) suffix and per-row
# worst-move/important-moves table no longer carry engine-specific
# annotations. The Leela/KataGo suffix classes
# (TestKarteLeelaWorstMove / TestKarteLeelaImportantMoves /
# TestKarteKataGoUnchanged) and their fixtures were removed because the
# output shape they assert against no longer exists. The unit tests for
# `format_loss_with_engine_suffix` and `has_loss_data` above still cover
# the suffix logic at the function level.


# ---------------------------------------------------------------------------
# Test 6: Mixed engine data (error handling - Phase 37 update)
# ---------------------------------------------------------------------------
class TestKarteMixedEngine:
    """Test mixed KataGo + Leela data returns error (Phase 37).

    As of Phase 37, mixed-engine snapshots are rejected with an error markdown
    to prevent combining incompatible analysis data in a single karte report.
    """

    @pytest.fixture
    def mixed_game(self):
        """Mock Game with mixed engine data."""
        moves = [
            # Move 1: KataGo
            make_move_eval(
                move_number=1,
                player="B",
                gtp="D4",
                points_lost=2.0,
                score_loss=2.0,
                leela_loss_est=None,
                importance_score=5.0,
                mistake_category=MistakeCategory.INACCURACY,
            ),
            # Move 2: Leela
            make_move_eval(
                move_number=2,
                player="W",
                gtp="Q16",
                points_lost=None,
                score_loss=None,
                leela_loss_est=4.0,
                importance_score=7.0,
                mistake_category=MistakeCategory.MISTAKE,
            ),
        ]
        return create_mock_game(moves)

    def test_mixed_engine_returns_error_markdown(self, mixed_game):
        """Mixed-engine snapshot returns error markdown (Phase 37 behavior)."""
        output = build_karte_report(mixed_game)

        # エラーコードが含まれること（安定したアサーション）
        assert KARTE_ERROR_CODE_MIXED_ENGINE in output

        # エラー karte であること
        assert "# Karte (ERROR)" in output
