"""Tests for EngineType detection and loss label formatting.

Phase 32: Report Leela support
"""
import pytest
from katrain.core.analysis import (
    EngineType,
    MoveEval,
    detect_engine_type,
    get_canonical_loss_from_move,
)
from katrain.core.analysis.presentation import (
    format_loss_label,
    format_evidence_examples,
)
from tests.helpers_eval_metrics import make_move_eval


class TestDetectEngineType:
    """Tests for detect_engine_type function"""

    @pytest.mark.parametrize("score_loss,leela_loss_est,expected", [
        (3.5, None, EngineType.KATAGO),      # KataGo: score_loss set
        (0.0, None, EngineType.KATAGO),      # KataGo: score_loss=0 is valid
        (None, 2.5, EngineType.LEELA),       # Leela: leela_loss_est set
        (None, 0.0, EngineType.LEELA),       # Leela: leela_loss_est=0 is valid
        (None, None, EngineType.UNKNOWN),    # Neither set
        (3.5, 2.5, EngineType.KATAGO),       # Both set: KataGo wins
    ])
    def test_engine_type_detection(self, score_loss, leela_loss_est, expected):
        m = make_move_eval(
            score_loss=score_loss,
            leela_loss_est=leela_loss_est,
        )
        assert detect_engine_type(m) == expected


class TestGetCanonicalLossLeela:
    """Tests for get_canonical_loss_from_move with Leela support"""

    @pytest.mark.parametrize("score_loss,leela_loss_est,points_lost,expected", [
        (3.5, None, None, 3.5),              # KataGo: use score_loss
        (None, 2.5, None, 2.5),              # Leela: use leela_loss_est
        (None, None, 1.5, 1.5),              # Fallback: use points_lost
        (None, None, -1.0, 0.0),             # Fallback: clamp negative
        (None, None, None, 0.0),             # Default: 0.0
        (3.5, 2.5, 1.5, 3.5),                # Priority: score_loss first
        (None, 2.5, 1.5, 2.5),               # Priority: leela_loss_est second
        # Clamp tests
        (-1.0, None, None, 0.0),             # Clamp negative score_loss
        (None, -0.5, None, 0.0),             # Clamp negative leela_loss_est
    ])
    def test_canonical_loss_priority(self, score_loss, leela_loss_est, points_lost, expected):
        m = make_move_eval(
            score_loss=score_loss,
            leela_loss_est=leela_loss_est,
            points_lost=points_lost,
        )
        assert get_canonical_loss_from_move(m) == expected


class TestFormatLossLabel:
    """Tests for format_loss_label function"""

    @pytest.mark.parametrize("loss,engine_type,lang,expected", [
        # KataGo Japanese - positive loss
        (3.5, EngineType.KATAGO, "ja", "-3.5目"),
        # KataGo Japanese - zero loss (no minus sign)
        (0.0, EngineType.KATAGO, "ja", "0.0目"),
        # KataGo English
        (3.5, EngineType.KATAGO, "en", "-3.5 pts"),
        (0.0, EngineType.KATAGO, "en", "0.0 pts"),
        # Leela Japanese
        (2.5, EngineType.LEELA, "ja", "-2.5目(推定)"),
        (0.0, EngineType.LEELA, "ja", "0.0目(推定)"),
        # Leela English
        (2.5, EngineType.LEELA, "en", "-2.5 pts(est.)"),
        (0.0, EngineType.LEELA, "en", "0.0 pts(est.)"),
        # Unknown (same as KataGo)
        (1.0, EngineType.UNKNOWN, "ja", "-1.0目"),
        (1.0, EngineType.UNKNOWN, "en", "-1.0 pts"),
        # Edge case: negative loss treated as zero
        (-1.0, EngineType.KATAGO, "ja", "0.0目"),
        (-0.5, EngineType.LEELA, "en", "0.0 pts(est.)"),
    ])
    def test_format_loss_label(self, loss, engine_type, lang, expected):
        assert format_loss_label(loss, engine_type, lang) == expected


class TestFormatEvidenceExamplesLeela:
    """Integration tests for format_evidence_examples with Leela data"""

    def test_leela_moves_show_estimated_suffix(self):
        """Leela moves should show (推定) suffix"""
        moves = [
            make_move_eval(move_number=10, gtp="D4", leela_loss_est=2.5),
            make_move_eval(move_number=20, player="W", gtp="Q16", leela_loss_est=1.5),
        ]
        result = format_evidence_examples(moves, lang="ja")
        assert "(推定)" in result

    def test_katago_moves_no_estimated_suffix(self):
        """KataGo moves should NOT show (推定) suffix"""
        moves = [
            make_move_eval(move_number=10, gtp="D4", score_loss=3.5),
        ]
        result = format_evidence_examples(moves, lang="ja")
        assert "(推定)" not in result

    def test_mixed_moves_format_correctly(self):
        """Mixed engine moves should each show correct format"""
        moves = [
            make_move_eval(move_number=10, gtp="D4", score_loss=3.5),
            make_move_eval(move_number=20, player="W", gtp="Q16", leela_loss_est=2.0),
        ]
        result = format_evidence_examples(moves, lang="ja")
        # D4 should NOT have (推定) before its position, Q16 should have (推定)
        assert "-3.5目" in result
        assert "(推定)" in result

    def test_empty_moves_returns_empty(self):
        """Empty moves list should return empty string"""
        result = format_evidence_examples([], lang="ja")
        assert result == ""

    def test_english_format(self):
        """English format should use 'pts' and '(est.)'"""
        moves = [
            make_move_eval(move_number=10, gtp="D4", leela_loss_est=2.5),
        ]
        result = format_evidence_examples(moves, lang="en")
        assert "pts" in result
        assert "(est.)" in result
        assert "e.g.:" in result

    def test_japanese_format_prefix(self):
        """Japanese format should use '例:' prefix"""
        moves = [
            make_move_eval(move_number=10, gtp="D4", score_loss=3.5),
        ]
        result = format_evidence_examples(moves, lang="ja")
        assert "例:" in result


class TestEngineTypeEnum:
    """Tests for EngineType enum properties"""

    def test_enum_values(self):
        """EngineType enum should have correct string values"""
        assert EngineType.KATAGO.value == "katago"
        assert EngineType.LEELA.value == "leela"
        assert EngineType.UNKNOWN.value == "unknown"

    def test_enum_members(self):
        """EngineType should have exactly three members"""
        members = list(EngineType)
        assert len(members) == 3
        assert EngineType.KATAGO in members
        assert EngineType.LEELA in members
        assert EngineType.UNKNOWN in members
