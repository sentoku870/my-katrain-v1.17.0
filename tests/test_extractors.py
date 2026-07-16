"""Direct unit tests for MoveExtractor and MetaExtractor.

Phase 194: These extractors previously imported ``unittest.mock.MagicMock``
to defend against stub game_data instances injected by tests. The MagicMock
defence was redundant with the surrounding ``try/except TypeError`` and
contaminated production code with a test-only dependency. This suite:

1. Verifies the post-fix behaviour for the Game path (snapshot.moves),
   the GameSummaryData path (``moves`` list), and the fallback path.
2. Locks in the regression that ``MagicMock`` (or any other object whose
   ``__len__`` raises ``TypeError``) is tolerated via the existing
   ``try/except`` rather than a magical ``isinstance`` guard.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from katrain.core.analysis.models import MoveEval
from katrain.core.analysis.models.enums import MistakeCategory
from katrain.core.analysis.models.move_eval import EvalSnapshot
from katrain.core.analysis.models.skill import GameSummaryData
from katrain.core.reports.extractors import MetaExtractor, MoveExtractor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_move(
    *,
    move_number: int = 1,
    player: str = "B",
    gtp: str = "D4",
    points_lost: float | None = 0.5,
    score_loss: float | None = 0.5,
    importance_score: float | None = 0.1,
    root_visits: int = 500,
    reason_tags: list[str] | None = None,
    mistake_category: MistakeCategory = MistakeCategory.GOOD,
    meaning_tag_id: str | None = None,
) -> MoveEval:
    return MoveEval(
        move_number=move_number,
        player=player,
        gtp=gtp,
        score_before=0.0,
        score_after=-points_lost if points_lost is not None and player == "B" else points_lost,
        delta_score=-points_lost if points_lost is not None and player == "B" else points_lost,
        winrate_before=0.5,
        winrate_after=0.5,
        delta_winrate=0.0,
        points_lost=points_lost,
        realized_points_lost=None,
        root_visits=root_visits,
        importance_score=importance_score,
        score_loss=score_loss,
        mistake_category=mistake_category,
        reason_tags=list(reason_tags or []),
        meaning_tag_id=meaning_tag_id,
    )


# ---------------------------------------------------------------------------
# MoveExtractor
# ---------------------------------------------------------------------------


class TestMoveExtractorBasic:
    def test_black_player_normalized(self):
        move = _make_move(player="B", gtp="D4", points_lost=1.25)
        result = MoveExtractor.extract(move, game_id="g1", game_name="Test")
        assert result["player"] == "black"
        assert result["move_number"] == 1
        assert result["coords"] == "D4"
        assert result["game_id"] == "g1"
        assert result["game_name"] == "Test"

    def test_white_player_normalized(self):
        move = _make_move(player="W", gtp="Q16", points_lost=2.0)
        result = MoveExtractor.extract(move)
        assert result["player"] == "white"
        assert result["coords"] == "Q16"

    def test_unknown_player_falls_back_to_unknown(self):
        move = _make_move(player=None, gtp="D4")
        result = MoveExtractor.extract(move)
        assert result["player"] == "unknown"

    def test_loss_clamped_non_negative(self):
        """When points_lost is set, it takes priority over score_loss (canonical)."""
        move = _make_move(points_lost=None, score_loss=10.0)
        result = MoveExtractor.extract(move)
        assert result["loss_clamped"] == 10.0
        assert result["loss_raw"] == 10.0

    def test_negative_points_lost_is_clamped_to_zero(self):
        """If points_lost is negative (shouldn't normally happen), clamp to 0."""
        move = _make_move(points_lost=-3.0, score_loss=None)
        result = MoveExtractor.extract(move)
        assert result["loss_clamped"] == 0.0
        assert result["loss_raw"] == -3.0

    def test_loss_zero_when_none(self):
        move = _make_move(points_lost=None, score_loss=None)
        result = MoveExtractor.extract(move)
        assert result["loss_clamped"] == 0.0
        assert result["loss_raw"] is None

    def test_no_gtp_uses_dash(self):
        move = _make_move(gtp=None)
        result = MoveExtractor.extract(move)
        assert result["coords"] == "-"

    def test_primary_tag_propagated(self):
        move = _make_move(meaning_tag_id="overplay")
        result = MoveExtractor.extract(move)
        assert result["primary_tag"] == "overplay"

    def test_mistake_type_lowercased(self):
        move = _make_move(mistake_category=MistakeCategory.BLUNDER)
        result = MoveExtractor.extract(move)
        assert result["mistake_type"] == "blunder"

    def test_reason_codes_sorted_and_deduplicated(self):
        move = _make_move(reason_tags=["shape", "atari", "shape", "low_liberties"])
        result = MoveExtractor.extract(move)
        assert result["reason_codes"] == ["atari", "liberties", "shape"]


class TestMoveExtractorPhase:
    def test_phase_normalized_via_alias(self):
        move = _make_move(move_number=201)
        result = MoveExtractor.extract(move, board_size=19)
        assert result["phase"] == "endgame"

    def test_phase_opening_for_early_move(self):
        move = _make_move(move_number=10)
        result = MoveExtractor.extract(move, board_size=19)
        assert result["phase"] == "opening"

    def test_phase_middle_in_between(self):
        move = _make_move(move_number=100)
        result = MoveExtractor.extract(move, board_size=19)
        assert result["phase"] == "middle"

    def test_phase_unknown_on_exception(self, monkeypatch):
        """If classify_game_phase raises, phase must default to ``unknown``."""
        from katrain.core.reports import extractors

        def boom(*_args, **_kwargs):
            raise RuntimeError("phase failure")

        monkeypatch.setattr(extractors, "classify_game_phase", boom)
        move = _make_move(move_number=1)
        result = MoveExtractor.extract(move)
        assert result["phase"] == "unknown"


# ---------------------------------------------------------------------------
# MetaExtractor — happy paths
# ---------------------------------------------------------------------------


def _game_summary_data(*, move_count: int = 5) -> GameSummaryData:
    snapshot = EvalSnapshot(moves=[_make_move(move_number=i + 1) for i in range(move_count)])
    return GameSummaryData(
        game_name="Round 1",
        player_black="Alice",
        player_white="Bob",
        snapshot=snapshot,
        board_size=(19, 19),
        date="2026-01-01",
        game_id="gid-1",
        result="B+R",
        handicap=0,
        komi=6.5,
    )


class TestMetaExtractorGameSummaryData:
    def test_basic_fields(self):
        gsd = _game_summary_data()
        meta = MetaExtractor.extract_game_meta(gsd)
        assert meta["name"] == "Round 1"
        assert meta["date"] == "2026-01-01"
        assert meta["game_id"] == "gid-1"
        assert meta["result"] == "B+R"
        assert meta["handicap"] == 0
        assert meta["komi"] == 6.5
        # GameSummaryData.board_size is tuple[int, int]; only ``int`` is
        # auto-normalised to [size, size]. Tuples pass through unchanged.
        assert meta["board_size"] == (19, 19)
        assert meta["players"] == {"black": "Alice", "white": "Bob"}

    def test_moves_count_via_snapshot(self):
        gsd = _game_summary_data(move_count=42)
        meta = MetaExtractor.extract_game_meta(gsd)
        assert meta["moves"] == 42

    def test_explicit_game_id_overrides_attr(self):
        gsd = _game_summary_data()
        meta = MetaExtractor.extract_game_meta(gsd, game_id="override")
        assert meta["game_id"] == "override"


class TestMetaExtractorFallback:
    def test_int_board_size_normalized(self):
        obj = SimpleNamespace(
            snapshot=type("S", (), {"moves": []})(),
            board_size=13,
            result="B+R",
            komi=6.5,
            handicap=0,
            player_black="A",
            player_white="B",
            date="2026-01-01",
            game_name="X",
            game_id="gid",
        )
        meta = MetaExtractor.extract_game_meta(obj)
        assert meta["board_size"] == [13, 13]

    def test_no_snapshot_no_moves_via_moves_list(self):
        """When ``snapshot`` is absent but a list-like ``moves`` exists, use it."""
        obj = SimpleNamespace(
            moves=[1, 2, 3, 4, 5],
            board_size=[9, 9],
            result="W+R",
            komi=7.5,
            handicap=2,
            player_black="X",
            player_white="Y",
            date="",
            game_name="",
            game_id=None,
        )
        meta = MetaExtractor.extract_game_meta(obj)
        assert meta["moves"] == 5
        assert meta["board_size"] == [9, 9]

    def test_komi_fallback_when_no_attr_and_no_root(self):
        obj = SimpleNamespace(
            snapshot=type("S", (), {"moves": []})(),
            board_size=(19, 19),
            result=None,
            komi=6.5,
            handicap=0,
            player_black="P1",
            player_white="P2",
            date="",
            game_name="g",
        )
        meta = MetaExtractor.extract_game_meta(obj)
        assert meta["komi"] == 6.5

    def test_minimal_object_uses_defaults(self):
        """Minimal SimpleNamespace with only ``root=None`` falls back cleanly."""

        class Bare:
            pass

        bare = Bare()
        # Deliberately do not set anything; ``getattr`` returns "" / 0 / None.
        meta = MetaExtractor.extract_game_meta(bare, game_id="explicit")
        assert meta["game_id"] == "explicit"
        assert meta["name"] == "Game explicit"
        assert meta["moves"] == 0
        assert meta["result"] is None
        assert meta["komi"] == 0.0
        assert meta["handicap"] == 0
        assert meta["players"] == {"black": "Black", "white": "White"}


# ---------------------------------------------------------------------------
# Regression: TypeError tolerance (Phase 194)
# ---------------------------------------------------------------------------


class TestMetaExtractorLenTypeErrorTolerance:
    """Phase 194: MagicMock was previously filtered by ``isinstance`` check.

    The check was removed; the surrounding ``try/except TypeError`` alone
    must keep the function safe for any non-sized ``moves`` attribute.
    """

    def test_magicmock_moves_handled_without_exception(self):
        obj = SimpleNamespace(
            snapshot=type("S", (), {"moves": []})(),
            board_size=(19, 19),
            result="B+R",
            komi=6.5,
            handicap=0,
            player_black="A",
            player_white="B",
            date="",
            game_name="g",
            game_id="gid",
            moves=MagicMock(),  # ``len(MagicMock())`` raises TypeError
        )
        meta = MetaExtractor.extract_game_meta(obj)
        assert meta["moves"] == 0

    def test_magicmock_snapshot_moves_handled_without_exception(self):
        snap = SimpleNamespace(moves=MagicMock())
        obj = SimpleNamespace(
            snapshot=snap,
            board_size=(19, 19),
            result="B+R",
            komi=6.5,
            handicap=0,
            player_black="A",
            player_white="B",
            date="",
            game_name="g",
            game_id="gid",
        )
        meta = MetaExtractor.extract_game_meta(obj)
        assert meta["moves"] == 0

    def test_no_moves_no_snapshot_no_root_keeps_zero(self):
        """When none of snapshot/moves/root are usable, moves stays 0."""
        obj = SimpleNamespace(
            board_size=(19, 19),
            result=None,
            komi=6.5,
            handicap=0,
            player_black="A",
            player_white="B",
            date="",
            game_name="g",
            game_id="gid",
        )
        meta = MetaExtractor.extract_game_meta(obj)
        assert meta["moves"] == 0


# ---------------------------------------------------------------------------
# Production hygiene: extractors.py must not import unittest.mock
# ---------------------------------------------------------------------------


class TestExtractorsModuleHygiene:
    def test_extractors_module_does_not_import_magicmock(self):
        """Phase 194 fix: production code must not depend on unittest.mock."""
        import katrain.core.reports.extractors as ext

        # ``sys.modules`` reflects the actually-loaded module.
        assert not hasattr(ext, "MagicMock"), "extractors.py must not define or re-export MagicMock"

    def test_extractors_module_source_has_no_magicmock(self):
        """Source-level check guards against future regressions."""
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "katrain" / "core" / "reports" / "extractors.py").read_text(
            encoding="utf-8"
        )
        assert "MagicMock" not in src
        assert "unittest.mock" not in src
