"""Phase 35 / 159A: Karte Leela integration tests.

CI-safe (no real engines), using mock/stub only.

Phase 159A: Karte generation is now KataGo-only. Leela-only and
mixed-engine snapshots are rejected with ``KARTE_ERROR_CODE_NON_KATAGO``
at the entry point. The unit tests for ``has_loss_data`` and
``format_loss_with_engine_suffix`` remain useful as the formatting
helpers stay in the codebase (still used by other consumers such as
``summary_formatter`` / ``engine_compare``).
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
    KARTE_ERROR_CODE_MIXED_ENGINE,  # kept for backwards-compat assertion
    KARTE_ERROR_CODE_NON_KATAGO,  # Phase 159A: active rejection code
    build_karte_report,
    format_loss_with_engine_suffix,
    has_loss_data,
)
from tests.helpers_eval_metrics import make_move_eval

# ---------------------------------------------------------------------------
# Test helper: create mock Game for build_karte_report()
# ---------------------------------------------------------------------------


def create_mock_game(moves: list[MoveEval]) -> Mock:
    """build_karte_report() 用の最小 Game モック。

    Phase 159A: spec=[] を使い、MetaExtractor で取りうるフィールドを
    全て実値（文字列 / 数値）で返すようにした。Mock() のデフォルト動作は
    存在しない属性を自動生成するため、``extract_game_meta`` が
    ``game.result`` を読もうとすると ``mock_result`` が返って JSON
    シリアライズが失敗する（``TypeError: expected string or bytes-like
    object, got 'Mock'``）。spec=[] にして明示属性のみ許可する。
    """
    snapshot = EvalSnapshot(moves=moves)

    def mock_config(key: str):
        if key == "trainer/eval_thresholds":
            return [1.0, 2.5, 5.0]
        if key == "general/my_player_name":
            return None
        if key == "general/my_player_aliases":
            return []
        return None

    game = Mock(spec=[])
    game.snapshot = snapshot
    game.build_eval_snapshot = Mock(return_value=snapshot)
    game.board_size = [19, 19]
    game.sgf_filename = "test.sgf"
    game.game_id = "test-game-id"
    game.komi = 6.5
    game.rules = "japanese"
    game.handicap = 0
    game.game_name = "test_game"
    game.result = "W+R"
    game.date = "2024-01-15"
    game.player_black = "PB"
    game.player_white = "PW"

    game.katrain = Mock(spec=[])
    game.katrain.config = mock_config
    game.katrain.log = Mock()

    root = Mock(spec=[])
    root.handicap = 0
    root.board_size = [19, 19]
    root.children = []  # type: ignore[attr-defined]

    def _prop(key, default=None):
        return {
            "PB": "PB",
            "PW": "PW",
            "DT": "2024-01-15",
            "RE": "W+R",
            "GN": "Test",
            "KM": "6.5",
            "HA": "0",
        }.get(key, default)

    root.get_property = Mock(side_effect=_prop)
    game.root = root

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
# Test 6: Mixed / Leela-only engine data (Phase 159A: KataGo-only gate)
# ---------------------------------------------------------------------------
class TestKarteMixedEngine:
    """Mixed KataGo + Leela data, and Leela-only data, are rejected.

    Phase 37 originally introduced mixed-engine rejection with
    KARTE_ERROR_CODE_MIXED_ENGINE. Phase 159A unified the behaviour so
    any Leela data (mixed or pure Leela) is rejected with
    KARTE_ERROR_CODE_NON_KATAGO. The old code is no longer emitted.
    """

    @pytest.fixture
    def mixed_game(self):
        """Mock Game with mixed KataGo + Leela data."""
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

    @pytest.fixture
    def leela_only_game(self):
        """Mock Game with pure Leela data (no KataGo score_loss)."""
        moves = [
            make_move_eval(
                move_number=1,
                player="B",
                gtp="D4",
                points_lost=None,
                score_loss=None,
                leela_loss_est=2.0,
                importance_score=5.0,
                mistake_category=MistakeCategory.INACCURACY,
            ),
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

    @pytest.fixture
    def katago_only_game(self):
        """Mock Game with pure KataGo data — should NOT be rejected."""
        moves = [
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
            make_move_eval(
                move_number=2,
                player="W",
                gtp="Q16",
                points_lost=0.5,
                score_loss=0.5,
                leela_loss_est=None,
                importance_score=2.0,
                mistake_category=MistakeCategory.GOOD,
            ),
        ]
        return create_mock_game(moves)

    def test_mixed_engine_returns_error_markdown(self, mixed_game):
        """Mixed-engine snapshot returns error markdown (Phase 159A gate)."""
        output = build_karte_report(mixed_game)

        # Phase 159A: NON_KATAGO_DATA is the active rejection code.
        assert KARTE_ERROR_CODE_NON_KATAGO in output
        # The Phase 37 MIXED_ENGINE code is no longer emitted (unified
        # under NON_KATAGO_DATA in Phase 159A).
        assert KARTE_ERROR_CODE_MIXED_ENGINE not in output

        # エラー karte であること
        assert "# Karte (ERROR)" in output

    def test_pure_leela_engine_returns_error_markdown(self, leela_only_game):
        """Pure Leela snapshot returns error markdown (Phase 159A gate)."""
        output = build_karte_report(leela_only_game)
        assert KARTE_ERROR_CODE_NON_KATAGO in output
        assert "# Karte (ERROR)" in output

    def test_pure_katago_engine_generates_normal_karte(self, katago_only_game):
        """Pure KataGo snapshot passes the gate and emits a normal Karte."""
        output = build_karte_report(katago_only_game)
        # No error code (KataGo path is the happy path).
        assert KARTE_ERROR_CODE_NON_KATAGO not in output
        # The (ERROR) tag must NOT appear for happy-path outputs.
        assert "(ERROR)" not in output
        # Phase 149 A-8 + 158-G: build_karte_report returns the JSON dict as a
        # string. The happy path includes schema_version + meta + sections.
        assert "schema_version" in output
        assert '"meta"' in output
        # The rejection error code (NON_KATAGO_DATA) is structurally distinct
        # from the standard schema: a normal karte carries summary/important_moves,
        # the error karte carries "error".
        assert '"error"' not in output
