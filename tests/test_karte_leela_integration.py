"""Phase 35: Karte Leela integration tests.

CI-safe (no real engines), using mock/stub only.
Tests that Leela-analyzed data shows (推定) suffix in Export Karte output.
"""
import pytest
from typing import Optional, List
from unittest.mock import Mock

from katrain.core.analysis.models import (
    MoveEval, EvalSnapshot, EngineType, MistakeCategory,
    get_canonical_loss_from_move,
)
from katrain.core.reports.karte_report import (
    build_karte_report,
    format_loss_with_engine_suffix,
    has_loss_data,
    KARTE_ERROR_CODE_MIXED_ENGINE,
)
from tests.helpers_eval_metrics import make_move_eval


# ---------------------------------------------------------------------------
# Test helper: create mock Game for build_karte_report()
# ---------------------------------------------------------------------------

def create_mock_game(moves: List[MoveEval]) -> Mock:
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

    @pytest.mark.parametrize("score_loss,leela_loss_est,points_lost,expected", [
        (3.5, None, None, True),    # KataGo
        (None, 3.5, None, True),    # Leela
        (None, None, 3.5, True),    # Legacy
        (0.0, None, None, True),    # 真の 0.0 (KataGo)
        (None, 0.0, None, True),    # 真の 0.0 (Leela)
        (None, None, None, False),  # データなし
    ])
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

    @pytest.mark.parametrize("loss_val,engine_type,expected", [
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
    ])
    def test_format_loss(self, loss_val, engine_type, expected):
        result = format_loss_with_engine_suffix(loss_val, engine_type)
        assert result == expected


# ---------------------------------------------------------------------------
# Test 3: Leela worst move gets (推定) suffix
# ---------------------------------------------------------------------------
class TestKarteLeelaWorstMove:
    """Test worst move display for Leela data."""

    @pytest.fixture
    def leela_game(self):
        """Mock Game with Leela-analyzed moves."""
        moves = [
            make_move_eval(
                move_number=1, player="B", gtp="D4",
                points_lost=None,  # Leela: points_lost は None
                leela_loss_est=3.5,
                score_loss=None,
                importance_score=5.0,
                mistake_category=MistakeCategory.MISTAKE,
            ),
            make_move_eval(
                move_number=2, player="W", gtp="Q16",
                points_lost=None,
                leela_loss_est=6.0,  # worst move for W
                score_loss=None,
                importance_score=8.0,
                mistake_category=MistakeCategory.BLUNDER,
            ),
            make_move_eval(
                move_number=3, player="B", gtp="Q4",
                points_lost=None,
                leela_loss_est=1.0,
                score_loss=None,
                importance_score=2.0,
                mistake_category=MistakeCategory.INACCURACY,
            ),
        ]
        return create_mock_game(moves)

    def test_worst_move_selected_from_leela_data(self, leela_game):
        """Leela data (points_lost=None) still contributes to worst move selection."""
        output = build_karte_report(leela_game)

        # "- Worst move:" 行が存在し、"unknown" ではない
        assert "- Worst move:" in output
        worst_move_lines = [
            line for line in output.split("\n")
            if "- Worst move:" in line
        ]
        for line in worst_move_lines:
            # "unknown" のみの行ではない（損失データがある）
            assert "loss " in line

    def test_worst_move_shows_estimated_suffix(self, leela_game):
        """Worst move line contains (推定) for Leela data."""
        output = build_karte_report(leela_game)

        # worst move 行に (推定) が含まれる
        worst_move_lines = [
            line for line in output.split("\n")
            if "- Worst move:" in line and "loss" in line
        ]
        assert len(worst_move_lines) > 0, "No worst move lines found"
        for line in worst_move_lines:
            assert "(推定)" in line, f"Missing suffix in: {line}"


# ---------------------------------------------------------------------------
# Test 4: Important Moves table shows (推定) for Leela
# ---------------------------------------------------------------------------
class TestKarteLeelaImportantMoves:
    """Test Important Moves table for Leela data."""

    @pytest.fixture
    def leela_game_with_important_moves(self):
        """Mock Game with high-importance Leela moves."""
        moves = [
            make_move_eval(
                move_number=i,
                player="B" if i % 2 == 1 else "W",
                gtp=f"D{i}",
                points_lost=None,
                leela_loss_est=float(i),
                score_loss=None,
                importance_score=10.0,  # 高importance で確実にテーブルに含まれる
                mistake_category=MistakeCategory.MISTAKE,
            )
            for i in range(1, 6)
        ]
        return create_mock_game(moves)

    def test_table_loss_column_has_suffix(self, leela_game_with_important_moves):
        """Important Moves table Loss column shows (推定)."""
        output = build_karte_report(leela_game_with_important_moves)

        # テーブルデータ行を抽出（| で始まり、B/W を含む、ヘッダー/セパレータ除外）
        lines = output.split("\n")
        data_rows = [
            line for line in lines
            if line.startswith("|")
            and ("| B |" in line or "| W |" in line)
        ]

        # 少なくとも1行は (推定) を含む
        assert len(data_rows) > 0, "No table data rows found"
        assert any("(推定)" in row for row in data_rows), \
            f"No table row contains suffix. Found: {data_rows[:3]}"


# ---------------------------------------------------------------------------
# Test 5: KataGo data has no suffix (regression test)
# ---------------------------------------------------------------------------
class TestKarteKataGoUnchanged:
    """Verify KataGo output format remains unchanged."""

    @pytest.fixture
    def katago_game(self):
        """Mock Game with KataGo-analyzed moves."""
        moves = [
            make_move_eval(
                move_number=1, player="B", gtp="D4",
                points_lost=3.5,
                score_loss=3.5,  # KataGo: score_loss 設定
                leela_loss_est=None,
                importance_score=5.0,
                mistake_category=MistakeCategory.MISTAKE,
            ),
            make_move_eval(
                move_number=2, player="W", gtp="Q16",
                points_lost=6.0,
                score_loss=6.0,
                leela_loss_est=None,
                importance_score=8.0,
                mistake_category=MistakeCategory.BLUNDER,
            ),
        ]
        return create_mock_game(moves)

    def test_katago_no_suffix(self, katago_game):
        """KataGo data shows no (推定) suffix anywhere."""
        output = build_karte_report(katago_game)
        assert "(推定)" not in output

    def test_katago_loss_format_unchanged(self, katago_game):
        """KataGo loss uses legacy format (符号なし、単位なし)."""
        output = build_karte_report(katago_game)
        # "-6.0" や "6.0目" は含まれない
        assert "-6.0" not in output
        assert "目" not in output
        # "6.0" は含まれる（worst move または table）
        assert "6.0" in output


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
                move_number=1, player="B", gtp="D4",
                points_lost=2.0,
                score_loss=2.0,
                leela_loss_est=None,
                importance_score=5.0,
                mistake_category=MistakeCategory.INACCURACY,
            ),
            # Move 2: Leela
            make_move_eval(
                move_number=2, player="W", gtp="Q16",
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
