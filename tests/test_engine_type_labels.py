"""Tests for EngineType detection and loss label formatting.

Phase 32: Add KataGo / UNKNOWN detection (Leela support removed Phase 171).
"""

import pytest

from katrain.core.analysis import (
    EngineType,
    detect_engine_type,
    get_canonical_loss_from_move,
)
from katrain.core.analysis.presentation import (
    format_evidence_examples,
    format_loss_label,
)
from tests.helpers_eval_metrics import make_move_eval


class TestDetectEngineType:
    """Tests for detect_engine_type function (Phase 171: KataGo-only)"""

    def test_katago_when_score_loss_set(self):
        m = make_move_eval(score_loss=3.5)
        assert detect_engine_type(m) == EngineType.KATAGO

    def test_zero_score_loss_counts_as_katago(self):
        m = make_move_eval(score_loss=0.0)
        assert detect_engine_type(m) == EngineType.KATAGO

    def test_unknown_when_no_loss(self):
        m = make_move_eval(score_loss=None)
        assert detect_engine_type(m) == EngineType.UNKNOWN

    def test_leela_only_returns_unknown(self):
        """Phase 171: Leela は廃止されたが、テスト互換のため
        ``score_loss=None
        （旧 LEELA 分岐に該当する入力だが、現状は単純化されて UNKNOWN 扱い）"""
        m = make_move_eval(score_loss=None)
        assert detect_engine_type(m) == EngineType.UNKNOWN


class TestGetCanonicalLoss:
    """Tests for get_canonical_loss_from_move (Phase 171: KataGo-only)"""

    def test_score_loss_used(self):
        m = make_move_eval(score_loss=3.5, points_lost=None)
        assert get_canonical_loss_from_move(m) == 3.5

    def test_points_lost_used_when_no_score_loss(self):
        m = make_move_eval(score_loss=None, points_lost=1.5)
        assert get_canonical_loss_from_move(m) == 1.5

    def test_points_lost_clamp_negative(self):
        m = make_move_eval(score_loss=None, points_lost=-1.0)
        assert get_canonical_loss_from_move(m) == 0.0

    def test_defaults_to_zero(self):
        m = make_move_eval(score_loss=None, points_lost=None)
        assert get_canonical_loss_from_move(m) == 0.0

    def test_score_loss_wins_over_leela_loss(self):
        # Phase 171 で leela_loss_est は渡しても無視（MoveEval 側が属性なし）.
        # 旧テストと互換にするため make_move_eval の leela_loss_est は渡さない。
        m = make_move_eval(score_loss=3.5, points_lost=1.5)
        assert get_canonical_loss_from_move(m) == 3.5


class TestFormatLossLabel:
    """Tests for format_loss_label function"""

    @pytest.mark.parametrize(
        "loss,engine_type,lang,expected",
        [
            # KataGo Japanese
            (3.5, EngineType.KATAGO, "ja", "-3.5目"),
            (0.0, EngineType.KATAGO, "ja", "0.0目"),
            # KataGo English
            (3.5, EngineType.KATAGO, "en", "-3.5 pts"),
            (0.0, EngineType.KATAGO, "en", "0.0 pts"),
        ],
    )
    def test_format_loss_label_kata(self, loss, engine_type, lang, expected):
        assert format_loss_label(loss, engine_type, lang) == expected

    def test_format_loss_label_unknown_uses_kata(self):
        """Phase 171: UNKNOWN は KataGo と同じフォーマット。"""
        assert format_loss_label(2.0, EngineType.UNKNOWN, "ja") == "-2.0目"


class TestFormatEvidenceExamples:
    """Tests for format_evidence_examples function (Phase 171: Leela suffix 削除)"""

    def test_empty_moves(self):
        assert format_evidence_examples([], lang="ja") == ""
        assert format_evidence_examples([], lang="en") == ""

    def test_japanese_format(self):
        moves = [make_move_eval(1, "B", score_loss=1.5)]
        result = format_evidence_examples(moves, lang="ja")
        assert "例:" in result
        assert "#1" in result or "# 1" in result or "1" in result

    def test_english_format(self):
        moves = [make_move_eval(1, "B", score_loss=1.5)]
        result = format_evidence_examples(moves, lang="en")
        assert "e.g.:" in result
