"""
Tests for KataGo response parsing and query building.

These tests verify:
1. parse_response produces stable ranks 1..N with no gaps
2. pass candidates are filtered out BEFORE ranking
3. scoreLead and visits are correctly extracted
4. build_query produces valid JSON structure
"""

import json
from pathlib import Path

import pytest

from katrain_qt.analysis.katago_engine import (
    parse_response,
    build_query,
    MAX_CANDIDATES,
    DEFAULT_MAX_VISITS,
    DEFAULT_RULES,
    position_signature,
    extract_root_score_lead,
    extract_root_winrate,
    build_analysis_result,
)
from katrain_qt.analysis.models import PositionSnapshot, CandidateMove, AnalysisResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def katago_response():
    """Load the sample KataGo response from fixtures."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    response_path = fixtures_dir / "katago_response.json"
    with open(response_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def empty_position():
    """Empty board position snapshot."""
    return PositionSnapshot(
        stones={},
        next_player="B",
        board_size=19,
        komi=6.5,
    )


@pytest.fixture
def position_with_stones():
    """Position with some stones."""
    return PositionSnapshot(
        stones={
            (3, 15): "B",   # D4
            (15, 3): "W",   # Q16
            (3, 3): "B",    # D16
            (15, 15): "W",  # Q4
        },
        next_player="B",
        board_size=19,
        komi=6.5,
    )


# =============================================================================
# parse_response Tests
# =============================================================================

class TestParseResponse:
    """Tests for parse_response function."""

    def test_returns_candidate_list(self, katago_response):
        """parse_response should return a list of CandidateMove."""
        candidates = parse_response(katago_response)
        assert isinstance(candidates, list)
        assert all(isinstance(c, CandidateMove) for c in candidates)

    def test_stable_ranks_1_to_n(self, katago_response):
        """Ranks should be stable 1, 2, 3, ... N with no gaps."""
        candidates = parse_response(katago_response)
        ranks = [c.rank for c in candidates]
        expected_ranks = list(range(1, len(candidates) + 1))
        assert ranks == expected_ranks

    def test_pass_filtered_before_ranking(self, katago_response):
        """Pass moves should be filtered out and not affect ranking."""
        candidates = parse_response(katago_response)

        # Original response has "pass" at position 2 (0-indexed)
        # After filtering, D16 (originally order 3) should be rank 3 (not 4)
        gtp_moves = [c.to_gtp(19) for c in candidates]
        assert "pass" not in gtp_moves

        # Verify ranks are still contiguous
        ranks = [c.rank for c in candidates]
        assert ranks == list(range(1, len(candidates) + 1))

    def test_max_candidates_limit(self, katago_response):
        """Should return at most MAX_CANDIDATES candidates."""
        candidates = parse_response(katago_response, max_candidates=MAX_CANDIDATES)
        assert len(candidates) <= MAX_CANDIDATES

    def test_custom_max_candidates(self, katago_response):
        """Custom max_candidates should be respected."""
        candidates = parse_response(katago_response, max_candidates=3)
        assert len(candidates) == 3

    def test_score_lead_extracted(self, katago_response):
        """scoreLead should be correctly extracted."""
        candidates = parse_response(katago_response)
        # First candidate (D4) has scoreLead 1.5
        assert candidates[0].score_lead == 1.5

    def test_visits_extracted(self, katago_response):
        """visits should be correctly extracted."""
        candidates = parse_response(katago_response)
        # First candidate (D4) has 500 visits
        assert candidates[0].visits == 500

    def test_coordinates_converted(self, katago_response):
        """GTP coordinates should be converted to internal Qt coordinates."""
        candidates = parse_response(katago_response, board_size=19)
        # D4 -> (3, 15) in Qt coords
        d4_candidate = candidates[0]
        assert d4_candidate.col == 3
        assert d4_candidate.row == 15

    def test_score_lead_rounded(self, katago_response):
        """scoreLead should be rounded to 2 decimal places."""
        candidates = parse_response(katago_response)
        for c in candidates:
            # Check that score_lead has at most 2 decimal places
            assert c.score_lead == round(c.score_lead, 2)

    def test_empty_move_infos(self):
        """Empty moveInfos should return empty list."""
        response = {"id": "test", "moveInfos": []}
        candidates = parse_response(response)
        assert candidates == []

    def test_missing_move_infos(self):
        """Missing moveInfos key should return empty list."""
        response = {"id": "test"}
        candidates = parse_response(response)
        assert candidates == []

    def test_different_board_sizes(self, katago_response):
        """Coordinate conversion should work for different board sizes."""
        # D4 on 13x13 board
        response_13 = {
            "moveInfos": [
                {"move": "D4", "visits": 100, "scoreLead": 1.0}
            ]
        }
        candidates = parse_response(response_13, board_size=13)
        # D4 on 13x13: col=3, row=13-4=9
        assert candidates[0].col == 3
        assert candidates[0].row == 9


class TestParseResponseRankingOrder:
    """Test that ranking respects KataGo's moveInfos order."""

    def test_first_move_is_rank_1(self, katago_response):
        """First valid move in moveInfos should be rank 1."""
        candidates = parse_response(katago_response)
        # D4 is first in response (before pass)
        assert candidates[0].to_gtp(19) == "D4"
        assert candidates[0].rank == 1

    def test_ranking_after_pass_filter(self, katago_response):
        """After filtering pass, subsequent moves should have consecutive ranks."""
        candidates = parse_response(katago_response)
        # Original order: D4(0), Q16(1), pass(2), D16(3), Q4(4), K10(5), C3(6)
        # After filter:   D4(1), Q16(2), D16(3), Q4(4), K10(5)
        expected_moves = ["D4", "Q16", "D16", "Q4", "K10"]
        actual_moves = [c.to_gtp(19) for c in candidates]
        assert actual_moves == expected_moves


# =============================================================================
# build_query Tests
# =============================================================================

class TestBuildQuery:
    """Tests for build_query function."""

    def test_returns_dict(self, empty_position):
        """build_query should return a dictionary."""
        query = build_query(empty_position, "test-id")
        assert isinstance(query, dict)

    def test_has_required_fields(self, empty_position):
        """Query should have all required KataGo fields."""
        query = build_query(empty_position, "test-id")

        required_fields = [
            "id", "rules", "komi", "boardXSize", "boardYSize",
            "initialStones", "initialPlayer", "moves", "analyzeTurns", "maxVisits"
        ]
        for field in required_fields:
            assert field in query, f"Missing required field: {field}"

    def test_id_from_parameter(self, empty_position):
        """Query ID should come from parameter."""
        query = build_query(empty_position, "my-custom-id")
        assert query["id"] == "my-custom-id"

    def test_board_size_from_snapshot(self, empty_position):
        """Board size should come from snapshot."""
        query = build_query(empty_position, "test-id")
        assert query["boardXSize"] == 19
        assert query["boardYSize"] == 19

    def test_komi_from_snapshot(self, empty_position):
        """Komi should come from snapshot."""
        query = build_query(empty_position, "test-id")
        assert query["komi"] == 6.5

    def test_initial_player_from_snapshot(self, empty_position):
        """initialPlayer should come from snapshot."""
        query = build_query(empty_position, "test-id")
        assert query["initialPlayer"] == "B"

    def test_rules_default(self, empty_position):
        """Rules should default to DEFAULT_RULES."""
        query = build_query(empty_position, "test-id")
        assert query["rules"] == DEFAULT_RULES

    def test_rules_custom(self, empty_position):
        """Custom rules should be used."""
        query = build_query(empty_position, "test-id", rules="chinese")
        assert query["rules"] == "chinese"

    def test_max_visits_default(self, empty_position):
        """maxVisits should default to DEFAULT_MAX_VISITS."""
        query = build_query(empty_position, "test-id")
        assert query["maxVisits"] == DEFAULT_MAX_VISITS

    def test_max_visits_custom(self, empty_position):
        """Custom maxVisits should be used."""
        query = build_query(empty_position, "test-id", max_visits=500)
        assert query["maxVisits"] == 500

    def test_empty_moves_array(self, empty_position):
        """moves array should be empty (using initialStones approach)."""
        query = build_query(empty_position, "test-id")
        assert query["moves"] == []

    def test_analyze_turns_zero(self, empty_position):
        """analyzeTurns should be [0] for initialStones approach."""
        query = build_query(empty_position, "test-id")
        assert query["analyzeTurns"] == [0]

    def test_initial_stones_format(self, position_with_stones):
        """initialStones should be list of [color, gtp_coord] pairs."""
        query = build_query(position_with_stones, "test-id")
        initial_stones = query["initialStones"]

        assert isinstance(initial_stones, list)
        assert len(initial_stones) == 4

        # Each element should be [color, coord]
        for stone in initial_stones:
            assert isinstance(stone, list)
            assert len(stone) == 2
            assert stone[0] in ("B", "W")
            assert isinstance(stone[1], str)

    def test_initial_stones_gtp_format(self, position_with_stones):
        """initialStones coordinates should be valid GTP format."""
        query = build_query(position_with_stones, "test-id")
        initial_stones = query["initialStones"]

        # Extract coordinates
        coords = [stone[1] for stone in initial_stones]

        # All coords should be valid GTP (letter + number)
        for coord in coords:
            assert len(coord) >= 2
            assert coord[0].isalpha()
            assert coord[1:].isdigit()

    def test_serializable_to_json(self, position_with_stones):
        """Query should be serializable to JSON."""
        query = build_query(position_with_stones, "test-id")

        # Should not raise
        json_str = json.dumps(query)
        assert isinstance(json_str, str)

        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed == query


# =============================================================================
# position_signature Tests
# =============================================================================

class TestPositionSignature:
    """Tests for position_signature function."""

    def test_empty_position(self, empty_position):
        """Empty position should produce consistent signature."""
        sig = position_signature(empty_position)
        assert sig.startswith("B|0|")

    def test_includes_stone_count(self, position_with_stones):
        """Signature should include stone count."""
        sig = position_signature(position_with_stones)
        assert "|4|" in sig  # 4 stones

    def test_includes_next_player(self, position_with_stones):
        """Signature should start with next player."""
        sig = position_signature(position_with_stones)
        assert sig.startswith("B|")

    def test_deterministic(self, position_with_stones):
        """Same position should produce same signature."""
        sig1 = position_signature(position_with_stones)
        sig2 = position_signature(position_with_stones)
        assert sig1 == sig2

    def test_different_players_different_sig(self):
        """Different next_player should produce different signature."""
        pos_b = PositionSnapshot(stones={(0, 0): "B"}, next_player="B")
        pos_w = PositionSnapshot(stones={(0, 0): "B"}, next_player="W")

        sig_b = position_signature(pos_b)
        sig_w = position_signature(pos_w)

        assert sig_b != sig_w


# =============================================================================
# extract_root_score_lead Tests
# =============================================================================

class TestExtractRootScoreLead:
    """Tests for extract_root_score_lead function."""

    def test_extracts_from_root_info(self, katago_response):
        """Should extract scoreLead from rootInfo if present."""
        # katago_response fixture has rootInfo.scoreLead = 1.5
        score = extract_root_score_lead(katago_response)
        assert score == 1.5

    def test_rounds_to_two_decimals(self):
        """Score lead should be rounded to 2 decimal places."""
        response = {
            "rootInfo": {"scoreLead": 1.23456789}
        }
        score = extract_root_score_lead(response)
        assert score == 1.23

    def test_fallback_to_best_candidate(self):
        """Should fallback to best candidate's scoreLead if no rootInfo."""
        # Create a response without rootInfo but with moveInfos
        response = {
            "moveInfos": [
                {"move": "D4", "visits": 100, "scoreLead": 2.5}
            ]
        }
        # Pre-parsed candidates with rank 1 having score_lead 3.0
        candidates = [
            CandidateMove(col=3, row=15, rank=1, score_lead=3.0, visits=100)
        ]
        score = extract_root_score_lead(response, candidates)
        assert score == 3.0  # Uses candidate, not moveInfos

    def test_fallback_to_move_infos_without_candidates(self):
        """Should fallback to moveInfos[0] if no rootInfo and no candidates."""
        response = {
            "moveInfos": [
                {"move": "D4", "visits": 100, "scoreLead": 4.5}
            ]
        }
        score = extract_root_score_lead(response)
        assert score == 4.5

    def test_returns_none_for_empty_response(self):
        """Should return None if no score data available."""
        response = {}
        score = extract_root_score_lead(response)
        assert score is None

    def test_returns_none_for_empty_move_infos(self):
        """Should return None if moveInfos is empty."""
        response = {"moveInfos": []}
        score = extract_root_score_lead(response)
        assert score is None

    def test_returns_none_for_missing_score_lead(self):
        """Should return None if scoreLead field is missing."""
        response = {
            "rootInfo": {"visits": 1000},  # No scoreLead
            "moveInfos": [
                {"move": "D4", "visits": 100}  # No scoreLead
            ]
        }
        score = extract_root_score_lead(response)
        assert score is None

    def test_priority_root_info_over_candidates(self, katago_response):
        """rootInfo.scoreLead should take priority over candidates."""
        candidates = [
            CandidateMove(col=3, row=15, rank=1, score_lead=99.0, visits=100)
        ]
        score = extract_root_score_lead(katago_response, candidates)
        # rootInfo has 1.5, candidates have 99.0 - should use rootInfo
        assert score == 1.5

    def test_negative_score_lead(self):
        """Should handle negative score leads correctly."""
        response = {
            "rootInfo": {"scoreLead": -5.5}
        }
        score = extract_root_score_lead(response)
        assert score == -5.5


# =============================================================================
# extract_root_winrate Tests
# =============================================================================

class TestExtractRootWinrate:
    """Tests for extract_root_winrate function."""

    def test_extracts_from_root_info(self, katago_response):
        """Should extract winrate from rootInfo if present."""
        winrate = extract_root_winrate(katago_response)
        assert winrate == 0.52

    def test_rounds_to_four_decimals(self):
        """Winrate should be rounded to 4 decimal places."""
        response = {"rootInfo": {"winrate": 0.123456789}}
        winrate = extract_root_winrate(response)
        assert winrate == 0.1235

    def test_fallback_to_best_candidate(self):
        """Should fallback to best candidate's winrate if no rootInfo."""
        response = {}
        candidates = [
            CandidateMove(col=3, row=15, rank=1, score_lead=1.0, visits=100, winrate=0.65)
        ]
        winrate = extract_root_winrate(response, candidates)
        assert winrate == 0.65

    def test_returns_none_for_empty_response(self):
        """Should return None if no winrate data available."""
        response = {}
        winrate = extract_root_winrate(response)
        assert winrate is None


# =============================================================================
# CandidateMove PV Tests
# =============================================================================

class TestCandidateMovePV:
    """Tests for CandidateMove PV extraction and methods."""

    def test_pv_extracted(self, katago_response):
        """PV should be extracted from moveInfos."""
        candidates = parse_response(katago_response)
        # First candidate (D4) has PV
        assert candidates[0].pv == ["D4", "Q16", "D16", "Q4", "C6"]

    def test_pv_empty_list_handled(self, katago_response):
        """Empty PV list should be handled."""
        candidates = parse_response(katago_response)
        # K10 (rank 5) has empty pv list
        k10 = [c for c in candidates if c.to_gtp(19) == "K10"][0]
        assert k10.pv == []

    def test_pv_missing_handled(self, katago_response):
        """Missing PV field should result in empty list."""
        candidates = parse_response(katago_response)
        # C3 has no pv field
        # Note: In our fixture, C3 would be cut off by MAX_CANDIDATES=5
        # Let's test with a custom response
        response = {
            "moveInfos": [
                {"move": "D4", "visits": 100, "scoreLead": 1.0, "winrate": 0.5}
            ]
        }
        candidates = parse_response(response)
        assert candidates[0].pv == []

    def test_pv_string_method(self, katago_response):
        """pv_string should return space-separated PV."""
        candidates = parse_response(katago_response)
        pv_str = candidates[0].pv_string()
        assert pv_str == "D4 Q16 D16 Q4 C6"

    def test_pv_string_max_moves(self, katago_response):
        """pv_string should respect max_moves limit."""
        candidates = parse_response(katago_response)
        pv_str = candidates[0].pv_string(max_moves=3)
        assert pv_str == "D4 Q16 D16"

    def test_pv_string_empty(self):
        """pv_string should return empty string for empty PV."""
        cand = CandidateMove(col=0, row=0, rank=1, score_lead=0, visits=0, pv=[])
        assert cand.pv_string() == ""

    def test_winrate_extracted(self, katago_response):
        """Winrate should be extracted from moveInfos."""
        candidates = parse_response(katago_response)
        assert candidates[0].winrate == 0.52


# =============================================================================
# build_analysis_result Tests
# =============================================================================

class TestBuildAnalysisResult:
    """Tests for build_analysis_result function."""

    def test_returns_analysis_result(self, katago_response):
        """Should return AnalysisResult dataclass."""
        result = build_analysis_result("test-id", katago_response, "B")
        assert isinstance(result, AnalysisResult)

    def test_query_id_preserved(self, katago_response):
        """Query ID should be preserved."""
        result = build_analysis_result("my-query-123", katago_response, "B")
        assert result.query_id == "my-query-123"

    def test_candidates_parsed(self, katago_response):
        """Candidates should be parsed."""
        result = build_analysis_result("test", katago_response, "B")
        assert len(result.candidates) == 5  # MAX_CANDIDATES
        assert result.candidates[0].to_gtp(19) == "D4"

    def test_score_lead_black_when_black_to_play(self, katago_response):
        """Score lead should be positive when Black to play and Black ahead."""
        # Fixture has scoreLead=1.5 (Black ahead from Black's perspective)
        result = build_analysis_result("test", katago_response, "B")
        assert result.score_lead_black == 1.5

    def test_score_lead_black_when_white_to_play(self, katago_response):
        """Score lead should be flipped when White to play."""
        # When White to play, KataGo returns from White's perspective
        # If White is behind by 1.5, that means Black is ahead by 1.5
        # But our fixture has it as Black ahead (positive for Black to play)
        # So when White to play, we flip: -1.5
        result = build_analysis_result("test", katago_response, "W")
        assert result.score_lead_black == -1.5

    def test_winrate_black_when_black_to_play(self, katago_response):
        """Winrate should be Black's when Black to play."""
        result = build_analysis_result("test", katago_response, "B")
        assert result.winrate_black == 0.52

    def test_winrate_black_when_white_to_play(self, katago_response):
        """Winrate should be flipped when White to play."""
        result = build_analysis_result("test", katago_response, "W")
        # 1.0 - 0.52 = 0.48
        assert result.winrate_black == 0.48

    def test_root_visits_extracted(self, katago_response):
        """Root visits should be extracted."""
        result = build_analysis_result("test", katago_response, "B")
        assert result.root_visits == 1000

    def test_next_player_stored(self, katago_response):
        """Next player should be stored."""
        result = build_analysis_result("test", katago_response, "W")
        assert result.next_player == "W"

    def test_best_move_method(self, katago_response):
        """best_move should return first candidate."""
        result = build_analysis_result("test", katago_response, "B")
        best = result.best_move()
        assert best is not None
        assert best.rank == 1

    def test_score_lead_to_play(self, katago_response):
        """score_lead_to_play should return from to-play perspective."""
        # Black to play, Black ahead
        result_b = build_analysis_result("test", katago_response, "B")
        assert result_b.score_lead_to_play() == 1.5

        # White to play, score_lead_black = -1.5 (White ahead)
        result_w = build_analysis_result("test", katago_response, "W")
        # From White's perspective: -(-1.5) = 1.5 (White ahead from White's view)
        assert result_w.score_lead_to_play() == 1.5

    def test_winrate_to_play(self, katago_response):
        """winrate_to_play should return from to-play perspective."""
        result_b = build_analysis_result("test", katago_response, "B")
        assert result_b.winrate_to_play() == 0.52

        result_w = build_analysis_result("test", katago_response, "W")
        # 1.0 - 0.48 = 0.52 (White's winrate)
        assert result_w.winrate_to_play() == 0.52
