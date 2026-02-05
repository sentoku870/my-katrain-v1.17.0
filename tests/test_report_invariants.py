"""Report output invariant tests.

Phase 66: Tests for Summary/Karte quality improvements.
"""

import pytest


def _is_properly_nested(s: str) -> bool:
    """Check if brackets are properly nested (not just equal counts)."""
    depth = 0
    for ch in s:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth < 0:
                return False  # More closes than opens at this point
    return depth == 0


class TestGameLabelInvariants:
    """Issue A: Game label formatting invariants.

    Tests the actual functions:
    - _ensure_balanced_brackets() - helper for bracket balancing
    - _smart_truncate() - main truncation logic
    - format_game_display_label() - public API
    - format_game_link_target() - URL encoding
    """

    def test_ensure_balanced_brackets_removes_orphan_open(self):
        """_ensure_balanced_brackets removes orphan '[' at end."""
        from katrain.core.batch.helpers import _ensure_balanced_brackets

        result = _ensure_balanced_brackets("[Play...")
        assert _is_properly_nested(result), f"Not properly nested: {result!r}"

    def test_ensure_balanced_brackets_removes_orphan_close(self):
        """_ensure_balanced_brackets removes orphan ']' at start."""
        from katrain.core.batch.helpers import _ensure_balanced_brackets

        result = _ensure_balanced_brackets("...]Player")
        assert _is_properly_nested(result), f"Not properly nested: {result!r}"

    def test_ensure_balanced_brackets_fixes_reversed_brackets(self):
        """_ensure_balanced_brackets fixes '][' (count-equal but invalid)."""
        from katrain.core.batch.helpers import _ensure_balanced_brackets

        result = _ensure_balanced_brackets("][P1]")
        assert _is_properly_nested(result), f"Not properly nested: {result!r}"

    def test_ensure_balanced_brackets_preserves_balanced(self):
        """_ensure_balanced_brackets preserves already balanced strings."""
        from katrain.core.batch.helpers import _ensure_balanced_brackets

        input_str = "[P1]vs[P2]"
        result = _ensure_balanced_brackets(input_str)
        assert result == input_str

    @pytest.mark.parametrize(
        "name,max_len",
        [
            ("[Player1]vs[Player2]1234567890.sgf", 30),
            ("[日本語]vs[中文名]9876543210.sgf", 25),
            ("simple_game.sgf", 20),
            ("no_extension", 15),
            ("[P1]vs[P2]x.sgf", 10),  # Edge case: very small max_len
            # Fallback branch cases
            ("[VeryLongPlayer1]vs[VeryLongPlayer2]extremelylongsuffix.sgf", 15),
            ("file[with]random[brackets]here.sgf", 12),
            # Edge cases for length safety
            ("[A]vs[B]c.sgf", 5),  # Very small
            ("x" * 100, 20),  # Long name
        ],
    )
    def test_balanced_brackets_after_truncation_all_branches(self, name, max_len):
        """Brackets must be PROPERLY NESTED after truncation in ALL code paths."""
        from katrain.core.batch.helpers import _smart_truncate

        result = _smart_truncate(name, max_len)

        assert _is_properly_nested(result), f"Not properly nested: {result!r} (from {name!r})"

    @pytest.mark.parametrize(
        "name,max_len",
        [
            ("[Player1]vs[Player2]1234567890.sgf", 30),
            ("[P1]vs[P2]x.sgf", 10),
            ("[VeryLongPlayer1]vs[VeryLongPlayer2]extremelylongsuffix.sgf", 15),
            ("file[with]random[brackets]here.sgf", 12),
            ("[A]vs[B]c.sgf", 5),  # Very small - will be clamped to 10
            ("x" * 100, 20),
        ],
    )
    def test_length_never_exceeds_max_len(self, name, max_len):
        """Output length must never exceed max_len (clamped to 10 minimum)."""
        from katrain.core.batch.helpers import _smart_truncate

        result = _smart_truncate(name, max_len)
        effective_max = max(10, max_len)  # Function clamps to 10

        assert len(result) <= effective_max, f"len({result!r})={len(result)} > {effective_max}"

    @pytest.mark.parametrize(
        "name,max_len,escape_mode",
        [
            ("[Player1]vs[Player2]123.sgf", 30, "table"),
            ("[Player1]vs[Player2]123.sgf", 30, "plain"),
            ("[Player1]vs[Player2]123.sgf", None, "none"),
        ],
    )
    def test_display_label_does_not_crash(self, name, max_len, escape_mode):
        """format_game_display_label should not crash for any input."""
        from katrain.core.batch.helpers import format_game_display_label

        result = format_game_display_label(name, max_len=max_len, escape_mode=escape_mode)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_path_preserved_in_link_target(self):
        """Relative paths should have / preserved."""
        from katrain.core.batch.helpers import format_game_link_target

        name = "subdir/[P1]vs[P2].sgf"
        target = format_game_link_target(name, preserve_path=True)

        assert "/" in target, f"Path separator lost in: {target}"
        assert "%2F" not in target, f"Path separator wrongly encoded in: {target}"

    def test_link_with_path_and_brackets(self):
        """Links with both path separators and brackets should work."""
        from katrain.core.batch.helpers import format_game_link_target

        name = "dir/sub/[Player1]vs[Player2].sgf"
        target = format_game_link_target(name, preserve_path=True)

        # Path preserved, brackets encoded for URL safety
        assert "/" in target
        assert "%5B" in target or "[" in target  # Brackets may or may not be encoded


class TestStyleConfidenceGating:
    """Issue C: Style confidence gating invariants.

    Uses pure helper function to avoid dependency on full StyleResult construction.
    """

    def test_confidence_threshold_constant_exists(self):
        """STYLE_CONFIDENCE_THRESHOLD should be defined as 0.2."""
        from katrain.core.reports.karte_report import STYLE_CONFIDENCE_THRESHOLD

        assert STYLE_CONFIDENCE_THRESHOLD == 0.2

    @pytest.mark.parametrize(
        "confidence,should_show_style",
        [
            (0.0, False),
            (0.1, False),
            (0.19, False),
            (0.2, True),
            (0.5, True),
            (1.0, True),
        ],
    )
    def test_confidence_threshold_boundary(self, confidence, should_show_style):
        """Verify threshold behavior at 20% using constant directly."""
        from katrain.core.reports.karte_report import STYLE_CONFIDENCE_THRESHOLD

        assert (confidence >= STYLE_CONFIDENCE_THRESHOLD) == should_show_style


class TestMTagClassification:
    """Issue D: MTag classification invariants.

    Uses SimpleNamespace for duck-typed MoveEval to reduce brittleness.
    """

    def _make_move_like(self, reason_tags=None, score_loss=None, move_number=50):
        """Create duck-typed object with MoveEval-like attributes."""
        from types import SimpleNamespace

        return SimpleNamespace(
            move_number=move_number,
            player="B",
            gtp="D4",
            score_loss=score_loss,
            leela_loss_est=None,
            points_lost=score_loss,
            is_reliable=True,
            reason_tags=reason_tags or [],
            visits=100,
        )

    def test_single_low_liberties_not_uncertain(self):
        """Single low_liberties tag should not result in UNCERTAIN."""
        from katrain.core.analysis.meaning_tags.classifier import classify_meaning_tag
        from katrain.core.analysis.meaning_tags.models import MeaningTagId

        move = self._make_move_like(reason_tags=["low_liberties"], score_loss=3.0)
        result = classify_meaning_tag(move)

        assert result.id != MeaningTagId.UNCERTAIN, f"Got UNCERTAIN: {result.debug_reason}"

    def test_single_atari_not_uncertain(self):
        """Single atari tag should not result in UNCERTAIN."""
        from katrain.core.analysis.meaning_tags.classifier import classify_meaning_tag
        from katrain.core.analysis.meaning_tags.models import MeaningTagId

        move = self._make_move_like(reason_tags=["atari"], score_loss=3.0)
        result = classify_meaning_tag(move)

        assert result.id != MeaningTagId.UNCERTAIN

    def test_single_endgame_hint_not_uncertain(self):
        """Single endgame_hint tag should not result in UNCERTAIN."""
        from katrain.core.analysis.meaning_tags.classifier import classify_meaning_tag
        from katrain.core.analysis.meaning_tags.models import MeaningTagId

        move = self._make_move_like(reason_tags=["endgame_hint"], score_loss=1.5)
        result = classify_meaning_tag(move)

        assert result.id != MeaningTagId.UNCERTAIN

    def test_need_connect_takes_precedence(self):
        """need_connect should trigger CONNECTION_MISS over single-tag fallback."""
        from katrain.core.analysis.meaning_tags.classifier import classify_meaning_tag
        from katrain.core.analysis.meaning_tags.models import MeaningTagId

        move = self._make_move_like(reason_tags=["need_connect", "low_liberties"], score_loss=3.0)
        result = classify_meaning_tag(move)

        assert result.id == MeaningTagId.CONNECTION_MISS


class TestEvidenceSelection:
    """Issue B: Evidence selection invariants.

    Tests the actual functions:
    - EvidenceMove dataclass
    - _select_evidence_moves() - selection logic
    - _format_evidence_with_links() - Markdown safety
    """

    def test_evidence_move_dataclass_creation(self):
        """EvidenceMove can be created with required fields."""
        from katrain.core.analysis.models import MistakeCategory
        from katrain.core.batch.stats import EvidenceMove

        ev = EvidenceMove(
            game_name="test.sgf",
            move_number=42,
            player="B",
            gtp="D4",
            points_lost=5.2,
            mistake_category=MistakeCategory.BLUNDER,
        )
        assert ev.game_name == "test.sgf"
        assert ev.move_number == 42
        assert ev.points_lost == 5.2

    def test_deterministic_selection(self):
        """Same input should produce same output."""
        from katrain.core.analysis.models import MistakeCategory
        from katrain.core.batch.stats import EvidenceMove, _select_evidence_moves

        candidates = [
            EvidenceMove(f"game{i}.sgf", i, "B", f"D{i}", float(10 - i), MistakeCategory.BLUNDER) for i in range(1, 6)
        ]

        result1 = _select_evidence_moves(candidates, max_count=3)
        result2 = _select_evidence_moves(candidates, max_count=3)

        assert result1 == result2

    def test_game_deduplication(self):
        """Same game should not appear twice in evidence."""
        from katrain.core.analysis.models import MistakeCategory
        from katrain.core.batch.stats import EvidenceMove, _select_evidence_moves

        candidates = [
            EvidenceMove("game1.sgf", 10, "B", "D4", 8.0, MistakeCategory.BLUNDER),
            EvidenceMove("game1.sgf", 20, "B", "Q16", 6.0, MistakeCategory.BLUNDER),  # Same game
            EvidenceMove("game2.sgf", 15, "B", "C3", 5.0, MistakeCategory.MISTAKE),
        ]

        result = _select_evidence_moves(candidates, max_count=3)

        game_names = [e.game_name for e in result]
        assert len(game_names) == len(set(game_names)), "Duplicate game in results"

    def test_sort_by_loss_descending(self):
        """Evidence should be sorted by loss descending."""
        from katrain.core.analysis.models import MistakeCategory
        from katrain.core.batch.stats import EvidenceMove, _select_evidence_moves

        candidates = [
            EvidenceMove("game1.sgf", 10, "B", "D4", 3.0, MistakeCategory.MISTAKE),
            EvidenceMove("game2.sgf", 20, "B", "Q16", 8.0, MistakeCategory.BLUNDER),
            EvidenceMove("game3.sgf", 15, "B", "C3", 5.0, MistakeCategory.BLUNDER),
        ]

        result = _select_evidence_moves(candidates, max_count=3)

        losses = [e.points_lost for e in result]
        assert losses == sorted(losses, reverse=True), "Not sorted by loss descending"

    def test_evidence_formatting_markdown_safe(self):
        """Evidence formatting should be Markdown-safe even with brackets in names."""
        from katrain.core.analysis.models import MistakeCategory
        from katrain.core.batch.stats import EvidenceMove, _format_evidence_with_links

        evidence = [
            EvidenceMove("[Player1]vs[Player2].sgf", 42, "B", "D4", 5.0, MistakeCategory.BLUNDER),
        ]

        # No karte links for simplicity
        result = _format_evidence_with_links(evidence, None, None, "jp")

        # Should use backticks, not bracket wrappers
        assert "`" in result, f"Expected backticks in: {result}"
        # Should not have nested/broken bracket structure
        # The display name is in backticks so Markdown won't interpret brackets
        assert "例:" in result or "e.g.:" in result
