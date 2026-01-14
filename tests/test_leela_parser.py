"""Tests for Leela Zero lz-analyze parser."""

import pytest
from pathlib import Path

from katrain.core.leela.parser import (
    parse_lz_analyze,
    normalize_winrate_from_raw,
    parse_single_info_line,
)
from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval


class TestNormalizeWinrateFromRaw:
    """Tests for winrate normalization."""

    def test_leela_0110_format(self):
        """Test Leela 0.110 format: 0-10000."""
        assert normalize_winrate_from_raw(5000) == pytest.approx(0.5)
        assert normalize_winrate_from_raw(4912) == pytest.approx(0.4912)
        assert normalize_winrate_from_raw(10000) == pytest.approx(1.0)
        assert normalize_winrate_from_raw(0) == pytest.approx(0.0)
        assert normalize_winrate_from_raw(6828) == pytest.approx(0.6828)

    def test_percentage_format(self):
        """Test percentage format: 0-100."""
        assert normalize_winrate_from_raw(50.0) == pytest.approx(0.5)
        assert normalize_winrate_from_raw(49.12) == pytest.approx(0.4912)
        assert normalize_winrate_from_raw(100.0) == pytest.approx(1.0)
        # Note: 0-1 range is treated as already normalized

    def test_normalized_format(self):
        """Test already normalized format: 0-1."""
        assert normalize_winrate_from_raw(0.5) == pytest.approx(0.5)
        assert normalize_winrate_from_raw(0.4912) == pytest.approx(0.4912)
        assert normalize_winrate_from_raw(1.0) == pytest.approx(1.0)
        assert normalize_winrate_from_raw(0.0) == pytest.approx(0.0)

    def test_clamp_out_of_range(self):
        """Test clamping for out-of-range values."""
        # Values > 10000 should be clamped to 1.0
        assert normalize_winrate_from_raw(15000) == pytest.approx(1.0)
        # Negative values should be clamped to 0.0
        assert normalize_winrate_from_raw(-100) == pytest.approx(0.0)


class TestParseLzAnalyze:
    """Tests for lz-analyze output parsing."""

    def test_parse_opening_sample(self):
        """Test parsing opening position sample."""
        sample = (
            "info move C4 visits 7975 winrate 4912 order 0 pv C4 Q4 D17 "
            "info move C16 visits 9086 winrate 4902 order 1 pv C16 Q16 D3"
        )
        result = parse_lz_analyze(sample)

        assert result.is_valid
        assert len(result.candidates) == 2
        assert result.parse_error is None

        # Check first candidate (sorted by visits, so C16 first)
        c16 = result.candidates[0]
        assert c16.move == "C16"
        assert c16.visits == 9086
        assert c16.winrate == pytest.approx(0.4902)
        assert c16.eval_pct == pytest.approx(49.02)

        # Check second candidate
        c4 = result.candidates[1]
        assert c4.move == "C4"
        assert c4.visits == 7975
        assert c4.winrate == pytest.approx(0.4912)

    def test_parse_midgame_sample(self):
        """Test parsing midgame position sample."""
        sample = (
            "info move R14 visits 59871 winrate 4997 order 0 pv R14 R5 Q6 "
            "info move R13 visits 18346 winrate 4948 order 1 pv R13 R5"
        )
        result = parse_lz_analyze(sample)

        assert result.is_valid
        assert len(result.candidates) == 2

        # Best candidate
        best = result.best_candidate
        assert best.move == "R14"
        assert best.winrate == pytest.approx(0.4997)

    def test_parse_handicap_sample(self):
        """Test parsing handicap game sample (white perspective)."""
        sample = (
            "info move D16 visits 36661 winrate 3908 order 0 pv D16 C14 "
            "info move D17 visits 29801 winrate 3793 order 1 pv D17 D15"
        )
        result = parse_lz_analyze(sample)

        assert result.is_valid
        # In handicap, winrate is low for white
        assert result.best_winrate == pytest.approx(0.3908)

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_lz_analyze("")
        assert not result.is_valid
        assert result.parse_error == "Empty output"

        result = parse_lz_analyze("   ")
        assert not result.is_valid

    def test_parse_gtp_error(self):
        """Test parsing GTP error response."""
        result = parse_lz_analyze("? unknown command")
        assert not result.is_valid
        assert "GTP error" in result.parse_error

    def test_parse_no_info_lines(self):
        """Test parsing output without info lines."""
        result = parse_lz_analyze("some random output without candidates")
        assert not result.is_valid
        assert result.parse_error == "No analysis data"

    def test_skip_invalid_visits(self):
        """Test skipping candidates with invalid visits."""
        sample = (
            "info move C4 visits 0 winrate 5000 order 0 pv C4 "
            "info move D4 visits 100 winrate 5100 order 1 pv D4"
        )
        result = parse_lz_analyze(sample)

        assert result.is_valid
        assert len(result.candidates) == 1
        assert result.candidates[0].move == "D4"

    def test_skip_invalid_winrate(self):
        """Test skipping candidates with invalid winrate.

        Note: If winrate is non-numeric, the regex won't match at all,
        so this results in 'Parse failed' rather than 'No valid candidates'.
        """
        sample = "info move C4 visits 100 winrate abc order 0 pv C4"
        result = parse_lz_analyze(sample)

        assert not result.is_valid
        # Regex expects numeric winrate, so non-match leads to parse failure
        assert result.parse_error is not None

    def test_single_candidate(self):
        """Test parsing single candidate."""
        sample = "info move D4 visits 1000 winrate 5200 order 0 pv D4 D16 Q16"
        result = parse_lz_analyze(sample)

        assert result.is_valid
        assert len(result.candidates) == 1
        assert result.candidates[0].move == "D4"
        assert result.candidates[0].pv == ["D4", "D16", "Q16"]

    def test_root_visits_calculated(self):
        """Test that root_visits is calculated from candidates."""
        sample = (
            "info move C4 visits 100 winrate 5000 order 0 pv C4 "
            "info move D4 visits 200 winrate 5100 order 1 pv D4"
        )
        result = parse_lz_analyze(sample)

        assert result.root_visits == 300

    def test_candidates_sorted_by_visits(self):
        """Test that candidates are sorted by visits (descending)."""
        sample = (
            "info move C4 visits 100 winrate 5000 order 2 pv C4 "
            "info move D4 visits 300 winrate 5100 order 0 pv D4 "
            "info move E4 visits 200 winrate 5050 order 1 pv E4"
        )
        result = parse_lz_analyze(sample)

        assert result.candidates[0].visits == 300
        assert result.candidates[1].visits == 200
        assert result.candidates[2].visits == 100


class TestParseSingleInfoLine:
    """Tests for single info line parsing utility."""

    def test_valid_line(self):
        """Test parsing valid single info line."""
        line = "info move C4 visits 100 winrate 5000 order 0 pv C4 D4"
        candidate = parse_single_info_line(line)

        assert candidate is not None
        assert candidate.move == "C4"
        assert candidate.visits == 100
        assert candidate.winrate == pytest.approx(0.5)

    def test_invalid_line(self):
        """Test parsing invalid line returns None."""
        candidate = parse_single_info_line("invalid data")
        assert candidate is None


class TestLeelaCandidateModel:
    """Tests for LeelaCandidate model."""

    def test_eval_pct_property(self):
        """Test eval_pct property calculation."""
        candidate = LeelaCandidate(move="D4", winrate=0.5, visits=100)
        assert candidate.eval_pct == pytest.approx(50.0)

        candidate = LeelaCandidate(move="D4", winrate=0.4912, visits=100)
        assert candidate.eval_pct == pytest.approx(49.12)

    def test_winrate_clamping(self):
        """Test that winrate is clamped in __post_init__."""
        # Test high value clamping
        candidate = LeelaCandidate(move="D4", winrate=1.5, visits=100)
        assert candidate.winrate == 1.0

        # Test low value clamping
        candidate = LeelaCandidate(move="D4", winrate=-0.5, visits=100)
        assert candidate.winrate == 0.0


class TestLeelaPositionEvalModel:
    """Tests for LeelaPositionEval model."""

    def test_is_valid(self):
        """Test is_valid property."""
        # Valid with candidates
        eval_result = LeelaPositionEval(
            candidates=[LeelaCandidate(move="D4", winrate=0.5, visits=100)]
        )
        assert eval_result.is_valid

        # Invalid: no candidates
        eval_result = LeelaPositionEval(candidates=[])
        assert not eval_result.is_valid

        # Invalid: has parse error
        eval_result = LeelaPositionEval(
            candidates=[LeelaCandidate(move="D4", winrate=0.5, visits=100)],
            parse_error="Some error",
        )
        assert not eval_result.is_valid

    def test_best_candidate(self):
        """Test best_candidate property."""
        candidates = [
            LeelaCandidate(move="C4", winrate=0.48, visits=100),
            LeelaCandidate(move="D4", winrate=0.52, visits=200),
            LeelaCandidate(move="E4", winrate=0.50, visits=150),
        ]
        eval_result = LeelaPositionEval(candidates=candidates)

        best = eval_result.best_candidate
        assert best.move == "D4"
        assert best.winrate == pytest.approx(0.52)

    def test_best_candidate_empty(self):
        """Test best_candidate with no candidates."""
        eval_result = LeelaPositionEval(candidates=[])
        assert eval_result.best_candidate is None
        assert eval_result.best_winrate is None
        assert eval_result.best_eval_pct is None


class TestParseRealSamples:
    """Tests using real sample files."""

    @pytest.fixture
    def sample_dir(self):
        """Get sample directory path."""
        return Path(__file__).parent / "fixtures" / "leela_samples"

    def test_parse_even_game_opening(self, sample_dir):
        """Test parsing even game opening sample file."""
        sample_file = sample_dir / "even_game_opening.txt"
        if not sample_file.exists():
            pytest.skip("Sample file not found")

        content = sample_file.read_text()
        # Extract the info line (skip comments)
        info_line = ""
        for line in content.split("\n"):
            if line.startswith("info"):
                info_line = line
                break

        if info_line:
            result = parse_lz_analyze(info_line)
            assert result.is_valid
            assert len(result.candidates) > 10  # Opening should have many candidates

    def test_parse_handicap_sample(self, sample_dir):
        """Test parsing handicap sample file."""
        sample_file = sample_dir / "handicap_3.txt"
        if not sample_file.exists():
            pytest.skip("Sample file not found")

        content = sample_file.read_text()
        info_line = ""
        for line in content.split("\n"):
            if line.startswith("info"):
                info_line = line
                break

        if info_line:
            result = parse_lz_analyze(info_line)
            assert result.is_valid
            # White's winrate should be low in 3-stone handicap
            assert result.best_winrate < 0.5

    def test_parse_endgame_sample(self, sample_dir):
        """Test parsing endgame sample file."""
        sample_file = sample_dir / "endgame.txt"
        if not sample_file.exists():
            pytest.skip("Sample file not found")

        content = sample_file.read_text()
        info_line = ""
        for line in content.split("\n"):
            if line.startswith("info"):
                info_line = line
                break

        if info_line:
            result = parse_lz_analyze(info_line)
            assert result.is_valid
            # Endgame should still have multiple candidates
            assert len(result.candidates) >= 5
