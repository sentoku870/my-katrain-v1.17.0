# -*- coding: utf-8 -*-
"""Tests for pattern_miner module (Phase 84).

Uses FakeMoveEval (SimpleNamespace) to avoid MoveEval constructor drift.
All tests are deterministic and don't require KataGo.
"""

import pytest
from types import SimpleNamespace
from typing import List, Optional

from katrain.core.analysis.models import MistakeCategory
from katrain.core.analysis.meaning_tags import (
    THRESHOLD_ENDGAME_RATIO,
    THRESHOLD_MOVE_ENDGAME_ABSOLUTE,
)
from katrain.core.batch.stats.pattern_miner import (
    MistakeSignature,
    GameRef,
    PatternCluster,
    create_signature,
    mine_patterns,
    get_severity,
    normalize_primary_tag,
    determine_phase,
    get_area_from_gtp,
    get_opening_threshold,
    get_area_threshold,
    LOSS_THRESHOLD,
    OPENING_THRESHOLDS,
    AREA_THRESHOLDS,
    MAX_GAME_REFS_PER_CLUSTER,
)


# =============================================================================
# Test Helpers
# =============================================================================

def make_fake_move_eval(
    move_number: int,
    player: Optional[str],
    gtp: Optional[str],
    score_loss: Optional[float] = None,
    leela_loss_est: Optional[float] = None,
    points_lost: Optional[float] = None,
    mistake_category: MistakeCategory = MistakeCategory.MISTAKE,
    meaning_tag_id: Optional[str] = "overplay",
) -> SimpleNamespace:
    """Create a lightweight MoveEval substitute for testing.

    Uses SimpleNamespace to avoid MoveEval constructor drift.
    get_loss_value() uses duck typing so this works.
    """
    return SimpleNamespace(
        move_number=move_number,
        player=player,
        gtp=gtp,
        score_loss=score_loss,
        leela_loss_est=leela_loss_est,
        points_lost=points_lost,
        mistake_category=mistake_category,
        meaning_tag_id=meaning_tag_id,
    )


def make_fake_snapshot(moves: List[SimpleNamespace]) -> SimpleNamespace:
    """Create a lightweight EvalSnapshot substitute for testing."""
    return SimpleNamespace(moves=moves)


# =============================================================================
# Test: Data Model Basics
# =============================================================================

class TestMistakeSignature:
    """Tests for MistakeSignature dataclass."""

    def test_frozen(self):
        """MistakeSignature should be frozen (immutable)."""
        sig = MistakeSignature(
            phase="middle",
            area="corner",
            primary_tag="overplay",
            severity="mistake",
        )
        with pytest.raises(AttributeError):
            sig.phase = "endgame"

    def test_sort_key(self):
        """sort_key should return deterministic tuple."""
        sig = MistakeSignature(
            phase="middle",
            area="edge",
            primary_tag="life_death",
            severity="blunder",
        )
        assert sig.sort_key() == ("middle", "edge", "life_death", "blunder")

    def test_equality(self):
        """Two signatures with same values should be equal."""
        sig1 = MistakeSignature("opening", "corner", "overplay", "mistake")
        sig2 = MistakeSignature("opening", "corner", "overplay", "mistake")
        assert sig1 == sig2

    def test_hashable(self):
        """MistakeSignature should be hashable (usable as dict key)."""
        sig = MistakeSignature("middle", "center", "uncertain", "blunder")
        d = {sig: 1}
        assert d[sig] == 1


class TestGameRef:
    """Tests for GameRef dataclass."""

    def test_frozen(self):
        """GameRef should be frozen (immutable)."""
        ref = GameRef(game_name="game1.sgf", move_number=50, player="B")
        with pytest.raises(AttributeError):
            ref.player = "W"

    def test_equality(self):
        """Two refs with same values should be equal."""
        ref1 = GameRef("game.sgf", 100, "W")
        ref2 = GameRef("game.sgf", 100, "W")
        assert ref1 == ref2


class TestPatternCluster:
    """Tests for PatternCluster dataclass."""

    def test_impact_score(self):
        """impact_score formula: total_loss * (1.0 + 0.1 * count)."""
        sig = MistakeSignature("middle", "corner", "overplay", "mistake")
        cluster = PatternCluster(
            signature=sig,
            count=5,
            total_loss=20.0,
            game_refs=[],
        )
        # 20.0 * (1.0 + 0.1 * 5) = 20.0 * 1.5 = 30.0
        assert cluster.impact_score == pytest.approx(30.0)

    def test_impact_score_count_zero(self):
        """impact_score with count=0."""
        sig = MistakeSignature("endgame", "edge", "urgent", "blunder")
        cluster = PatternCluster(
            signature=sig,
            count=0,
            total_loss=10.0,
            game_refs=[],
        )
        # 10.0 * (1.0 + 0.0) = 10.0
        assert cluster.impact_score == pytest.approx(10.0)


# =============================================================================
# Test: get_severity
# =============================================================================

class TestGetSeverity:
    """Tests for get_severity function."""

    def test_mistake(self):
        """MISTAKE -> 'mistake'."""
        assert get_severity(MistakeCategory.MISTAKE) == "mistake"

    def test_blunder(self):
        """BLUNDER -> 'blunder'."""
        assert get_severity(MistakeCategory.BLUNDER) == "blunder"

    def test_good_skip(self):
        """GOOD -> None (skip)."""
        assert get_severity(MistakeCategory.GOOD) is None

    def test_inaccuracy_skip(self):
        """INACCURACY -> None (skip)."""
        assert get_severity(MistakeCategory.INACCURACY) is None


# =============================================================================
# Test: normalize_primary_tag
# =============================================================================

class TestNormalizePrimaryTag:
    """Tests for normalize_primary_tag function."""

    def test_none(self):
        """None -> 'uncertain'."""
        assert normalize_primary_tag(None) == "uncertain"

    def test_empty_string(self):
        """Empty string -> 'uncertain'."""
        assert normalize_primary_tag("") == "uncertain"

    def test_valid_tag(self):
        """Valid tag passes through."""
        assert normalize_primary_tag("overplay") == "overplay"
        assert normalize_primary_tag("life_death") == "life_death"


# =============================================================================
# Test: determine_phase
# =============================================================================

class TestDeterminePhase:
    """Tests for determine_phase function."""

    def test_opening_19x19(self):
        """19x19: move <= 40 -> opening."""
        assert determine_phase(1, total_moves=200, board_size=19) == "opening"
        assert determine_phase(40, total_moves=200, board_size=19) == "opening"

    def test_opening_9x9(self):
        """9x9: move <= 15 -> opening."""
        assert determine_phase(1, total_moves=50, board_size=9) == "opening"
        assert determine_phase(15, total_moves=50, board_size=9) == "opening"
        assert determine_phase(16, total_moves=50, board_size=9) == "middle"

    def test_middle(self):
        """Middle game detection."""
        assert determine_phase(50, total_moves=200, board_size=19) == "middle"
        assert determine_phase(100, total_moves=200, board_size=19) == "middle"

    def test_endgame_absolute(self):
        """Endgame by absolute threshold (total_moves=None)."""
        # Uses THRESHOLD_MOVE_ENDGAME_ABSOLUTE (150)
        threshold = THRESHOLD_MOVE_ENDGAME_ABSOLUTE
        assert determine_phase(threshold, total_moves=None, board_size=19) == "middle"
        assert determine_phase(threshold + 1, total_moves=None, board_size=19) == "endgame"

    def test_endgame_ratio(self):
        """Endgame by ratio threshold (with total_moves)."""
        # Uses THRESHOLD_ENDGAME_RATIO (0.7)
        total = 200
        threshold_move = int(total * THRESHOLD_ENDGAME_RATIO)  # 140
        assert determine_phase(threshold_move, total_moves=total, board_size=19) == "middle"
        assert determine_phase(threshold_move + 1, total_moves=total, board_size=19) == "endgame"


# =============================================================================
# Test: get_area_from_gtp (19x19)
# =============================================================================

class TestGetAreaFromGtp19x19:
    """Tests for get_area_from_gtp on 19x19 board."""

    def test_corner(self):
        """D4 on 19x19 -> corner (coords (3,3), both < 4)."""
        assert get_area_from_gtp("D4", board_size=19) == "corner"

    def test_edge(self):
        """D10 on 19x19 -> edge (col=3 < 4, row=9 >= 4)."""
        assert get_area_from_gtp("D10", board_size=19) == "edge"

    def test_center(self):
        """K10 on 19x19 -> center (coords (9,9), both >= 4)."""
        # Note: K=9 due to I-skip in GTP
        assert get_area_from_gtp("K10", board_size=19) == "center"


# =============================================================================
# Test: get_area_from_gtp (9x9)
# =============================================================================

class TestGetAreaFromGtp9x9:
    """Tests for get_area_from_gtp on 9x9 board."""

    def test_d4_center(self):
        """D4 on 9x9 -> center (coords (3,3), both >= 3)."""
        assert get_area_from_gtp("D4", board_size=9) == "center"

    def test_c3_corner(self):
        """C3 on 9x9 -> corner (coords (2,2), both < 3)."""
        assert get_area_from_gtp("C3", board_size=9) == "corner"

    def test_d3_edge(self):
        """D3 on 9x9 -> edge (col=3 >= 3, row=2 < 3)."""
        assert get_area_from_gtp("D3", board_size=9) == "edge"


# =============================================================================
# Test: GTP Normalization
# =============================================================================

class TestGtpNormalization:
    """Tests for GTP coordinate normalization."""

    def test_lowercase(self):
        """Lowercase GTP should work."""
        assert get_area_from_gtp("d4", board_size=19) == "corner"

    def test_whitespace(self):
        """Whitespace around GTP should be stripped."""
        assert get_area_from_gtp(" D4 ", board_size=19) == "corner"

    def test_invalid(self):
        """Invalid GTP should return None (no exception)."""
        assert get_area_from_gtp("ZZ", board_size=19) is None

    def test_pass(self):
        """pass should return None."""
        assert get_area_from_gtp("pass", board_size=19) is None
        assert get_area_from_gtp("PASS", board_size=19) is None

    def test_resign(self):
        """resign should return None."""
        assert get_area_from_gtp("resign", board_size=19) is None

    def test_none(self):
        """None input should return None."""
        assert get_area_from_gtp(None, board_size=19) is None

    def test_i_skip(self):
        """GTP skips 'I' column: J=8, K=9."""
        # J1 -> col=8
        assert get_area_from_gtp("J1", board_size=19) == "edge"
        # K1 -> col=9 (center on 19x19 if we only look at col, but row=0 so edge)
        assert get_area_from_gtp("K1", board_size=19) == "edge"
        # Verify by checking H vs J
        # H1 -> col=7, J1 -> col=8 (I is skipped)
        assert get_area_from_gtp("H1", board_size=19) == "edge"


# =============================================================================
# Test: create_signature
# =============================================================================

class TestCreateSignature:
    """Tests for create_signature function."""

    def test_basic(self):
        """Basic signature creation."""
        move = make_fake_move_eval(
            move_number=50,
            player="B",
            gtp="D4",
            score_loss=5.0,
            mistake_category=MistakeCategory.MISTAKE,
            meaning_tag_id="overplay",
        )
        sig = create_signature(move, total_moves=200, board_size=19)
        assert sig is not None
        assert sig.phase == "middle"
        assert sig.area == "corner"
        assert sig.primary_tag == "overplay"
        assert sig.severity == "mistake"

    def test_skip_small_loss(self):
        """Loss < LOSS_THRESHOLD should skip."""
        move = make_fake_move_eval(
            move_number=50,
            player="B",
            gtp="D4",
            score_loss=2.4,  # Below 2.5
            mistake_category=MistakeCategory.MISTAKE,
        )
        assert create_signature(move, total_moves=200, board_size=19) is None

    def test_skip_loss_none(self):
        """loss=None should skip."""
        move = make_fake_move_eval(
            move_number=50,
            player="B",
            gtp="D4",
            # No loss values set
            mistake_category=MistakeCategory.MISTAKE,
        )
        assert create_signature(move, total_moves=200, board_size=19) is None

    def test_skip_pass(self):
        """gtp='pass' should skip."""
        move = make_fake_move_eval(
            move_number=50,
            player="B",
            gtp="pass",
            score_loss=5.0,
            mistake_category=MistakeCategory.MISTAKE,
        )
        assert create_signature(move, total_moves=200, board_size=19) is None

    def test_skip_resign(self):
        """gtp='resign' should skip."""
        move = make_fake_move_eval(
            move_number=50,
            player="B",
            gtp="resign",
            score_loss=5.0,
            mistake_category=MistakeCategory.MISTAKE,
        )
        assert create_signature(move, total_moves=200, board_size=19) is None

    def test_skip_no_player(self):
        """player=None should skip."""
        move = make_fake_move_eval(
            move_number=50,
            player=None,
            gtp="D4",
            score_loss=5.0,
            mistake_category=MistakeCategory.MISTAKE,
        )
        assert create_signature(move, total_moves=200, board_size=19) is None

    def test_meaning_tag_none(self):
        """meaning_tag_id=None should use 'uncertain'."""
        move = make_fake_move_eval(
            move_number=50,
            player="B",
            gtp="D4",
            score_loss=5.0,
            mistake_category=MistakeCategory.MISTAKE,
            meaning_tag_id=None,
        )
        sig = create_signature(move, total_moves=200, board_size=19)
        assert sig is not None
        assert sig.primary_tag == "uncertain"

    def test_skip_good(self):
        """GOOD category should skip."""
        move = make_fake_move_eval(
            move_number=50,
            player="B",
            gtp="D4",
            score_loss=5.0,
            mistake_category=MistakeCategory.GOOD,
        )
        assert create_signature(move, total_moves=200, board_size=19) is None

    def test_blunder_severity(self):
        """BLUNDER should have severity='blunder'."""
        move = make_fake_move_eval(
            move_number=50,
            player="B",
            gtp="D4",
            score_loss=10.0,
            mistake_category=MistakeCategory.BLUNDER,
            meaning_tag_id="life_death",
        )
        sig = create_signature(move, total_moves=200, board_size=19)
        assert sig is not None
        assert sig.severity == "blunder"


# =============================================================================
# Test: mine_patterns
# =============================================================================

class TestMinePatterns:
    """Tests for mine_patterns function."""

    def test_count_filter(self):
        """min_count should filter out patterns below threshold."""
        # Create 2 games with same mistake pattern
        move1 = make_fake_move_eval(50, "B", "D4", score_loss=5.0)
        move2 = make_fake_move_eval(60, "B", "D4", score_loss=5.0)
        move3 = make_fake_move_eval(70, "B", "K10", score_loss=5.0)  # Different area

        games = [
            ("game1.sgf", make_fake_snapshot([move1])),
            ("game2.sgf", make_fake_snapshot([move2, move3])),
        ]

        # min_count=2: D4 pattern appears 2x, K10 only 1x
        result = mine_patterns(games, board_size=19, min_count=2)
        assert len(result) == 1
        assert result[0].signature.area == "corner"
        assert result[0].count == 2

    def test_ranking(self):
        """Patterns should be sorted by impact_score descending."""
        # Higher loss pattern
        move_high = make_fake_move_eval(50, "B", "D4", score_loss=10.0)
        # Lower loss pattern (same count)
        move_low = make_fake_move_eval(50, "W", "K10", score_loss=3.0)

        games = [
            ("game1.sgf", make_fake_snapshot([move_high, move_low])),
            ("game2.sgf", make_fake_snapshot([
                make_fake_move_eval(50, "B", "D4", score_loss=10.0),
                make_fake_move_eval(50, "W", "K10", score_loss=3.0),
            ])),
        ]

        result = mine_patterns(games, board_size=19, min_count=2)
        assert len(result) == 2
        # First should be D4 pattern (higher total loss)
        assert result[0].signature.area == "corner"
        assert result[0].total_loss > result[1].total_loss

    def test_stable_sort(self):
        """Same impact_score should sort by signature.sort_key()."""
        # Two patterns with same impact_score
        move1 = make_fake_move_eval(
            50, "B", "D4", score_loss=5.0,
            meaning_tag_id="aaa"  # Alphabetically first
        )
        move2 = make_fake_move_eval(
            50, "B", "D4", score_loss=5.0,
            meaning_tag_id="zzz"  # Alphabetically last
        )

        games = [
            ("game1.sgf", make_fake_snapshot([move1])),
            ("game2.sgf", make_fake_snapshot([move1])),
            ("game3.sgf", make_fake_snapshot([move2])),
            ("game4.sgf", make_fake_snapshot([move2])),
        ]

        result = mine_patterns(games, board_size=19, min_count=2)
        assert len(result) == 2
        # Both have same count/loss, so sort by primary_tag
        assert result[0].signature.primary_tag == "aaa"
        assert result[1].signature.primary_tag == "zzz"

    def test_top_n(self):
        """top_n should limit results."""
        moves = [
            make_fake_move_eval(i, "B", "D4", score_loss=float(i), meaning_tag_id=f"tag{i}")
            for i in range(1, 10)
        ]

        games = [
            ("game1.sgf", make_fake_snapshot(moves)),
            ("game2.sgf", make_fake_snapshot(moves)),
        ]

        result = mine_patterns(games, board_size=19, min_count=2, top_n=3)
        assert len(result) == 3

    def test_empty_input(self):
        """Empty games list should return empty list."""
        assert mine_patterns([], board_size=19) == []

    def test_top_n_zero(self):
        """top_n=0 should return empty list."""
        move = make_fake_move_eval(50, "B", "D4", score_loss=5.0)
        games = [("game1.sgf", make_fake_snapshot([move]))]
        assert mine_patterns(games, board_size=19, top_n=0) == []

    def test_game_refs_cap(self):
        """game_refs should not exceed MAX_GAME_REFS_PER_CLUSTER."""
        # Create many games with same pattern
        move = make_fake_move_eval(50, "B", "D4", score_loss=5.0)
        games = [
            (f"game{i}.sgf", make_fake_snapshot([move]))
            for i in range(20)
        ]

        result = mine_patterns(games, board_size=19, min_count=1, top_n=1)
        assert len(result) == 1
        assert result[0].count == 20  # All counted
        assert len(result[0].game_refs) == MAX_GAME_REFS_PER_CLUSTER

    def test_game_refs_encounter_order(self):
        """game_refs should preserve encounter order."""
        move = make_fake_move_eval(50, "B", "D4", score_loss=5.0)
        games = [
            (f"game{i}.sgf", make_fake_snapshot([move]))
            for i in range(5)
        ]

        result = mine_patterns(games, board_size=19, min_count=1, top_n=1)
        refs = result[0].game_refs
        assert refs[0].game_name == "game0.sgf"
        assert refs[1].game_name == "game1.sgf"
        assert refs[4].game_name == "game4.sgf"

    def test_total_moves_from_snapshot(self):
        """total_moves should be derived from len(snapshot.moves)."""
        # Short game - move 50 would be endgame if total is 60
        moves_short = [
            make_fake_move_eval(i, "B", "D4", score_loss=5.0)
            for i in range(1, 61)
        ]
        # Override move 50 to have meaningful loss
        moves_short[49] = make_fake_move_eval(50, "B", "D4", score_loss=5.0)

        games = [("short_game.sgf", make_fake_snapshot(moves_short))]
        result = mine_patterns(games, board_size=19, min_count=1, top_n=10)

        # Find the pattern from move 50
        # With total_moves=60, move 50 > 60*0.7=42, so phase=endgame
        endgame_patterns = [p for p in result if p.signature.phase == "endgame"]
        assert len(endgame_patterns) > 0

    def test_recurring_pattern_aggregation(self):
        """Same signature from multiple moves should aggregate correctly."""
        # Same pattern in multiple games
        move = make_fake_move_eval(
            50, "B", "D4",
            score_loss=5.0,
            mistake_category=MistakeCategory.MISTAKE,
            meaning_tag_id="overplay",
        )

        games = [
            ("game1.sgf", make_fake_snapshot([move])),
            ("game2.sgf", make_fake_snapshot([move])),
            ("game3.sgf", make_fake_snapshot([move])),
        ]

        result = mine_patterns(games, board_size=19, min_count=1, top_n=10)
        assert len(result) == 1
        cluster = result[0]
        assert cluster.count == 3
        assert cluster.total_loss == pytest.approx(15.0)  # 5.0 * 3
        assert len(cluster.game_refs) == 3


# =============================================================================
# Test: Constants
# =============================================================================

class TestConstants:
    """Tests for module constants."""

    def test_loss_threshold(self):
        """LOSS_THRESHOLD should be 2.5."""
        assert LOSS_THRESHOLD == 2.5

    def test_opening_thresholds(self):
        """Opening thresholds should match expected values."""
        assert OPENING_THRESHOLDS[9] == 15
        assert OPENING_THRESHOLDS[13] == 25
        assert OPENING_THRESHOLDS[19] == 40

    def test_area_thresholds(self):
        """Area thresholds should match expected values."""
        assert AREA_THRESHOLDS[9] == 3
        assert AREA_THRESHOLDS[13] == 4
        assert AREA_THRESHOLDS[19] == 4

    def test_max_game_refs(self):
        """MAX_GAME_REFS_PER_CLUSTER should be 10."""
        assert MAX_GAME_REFS_PER_CLUSTER == 10
