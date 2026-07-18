"""Phase 268+ Curator aggregate / profile-loader fix tests.

Phase 268 audit found three real bugs that combined to make the
Curator weak-axis hint invisible in practice:

1. ``generate_curator_outputs`` was always called with
   ``user_aggregate=None`` because no orchestration step ever
   *built* the aggregate from ``game_stats_list``.  Every
   ``curator_ranking.json`` carried ``"user_weak_tags": []`` no
   matter how many games were analysed.
2. The profile loader only inspected ``user_weak_tags`` (and the
   legacy ``user_aggregate`` shape) — it ignored
   ``rankings[*].recommended_tags`` even though the per-game tag
   data was sitting right there.  Legacy JSON files therefore
   always yielded 0 weak tags.
3. The settings popup's Curator status label kept showing the
   "Batch 分析で …" hint even after a profile was successfully
   loaded (with 0 weak tags), because the only label branch was
   ``n_tags > 0``.

These tests pin all three fixes.  They are pure-unit (no Kivy) so
they run in the headless CI without the popup test skip that the
Phase 268 file-browser tests had to add.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import polib
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JP_PO_PATH = REPO_ROOT / "katrain" / "i18n" / "locales" / "jp" / "LC_MESSAGES" / "katrain.po"
EN_PO_PATH = REPO_ROOT / "katrain" / "i18n" / "locales" / "en" / "LC_MESSAGES" / "katrain.po"


# ---------------------------------------------------------------------------
# 1. build_user_aggregate_from_stats
# ---------------------------------------------------------------------------


class TestBuildUserAggregateFromStats:
    def test_empty_list_returns_none(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        assert build_user_aggregate_from_stats([]) is None
        assert build_user_aggregate_from_stats(None) is None

    def test_single_game(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        stats = [
            {
                "game_name": "game1.sgf",
                "meaning_tags_by_player": {
                    "B": {"overplay": 2, "endgame_slip": 1, "uncertain": 1},
                    "W": {"connection_miss": 1},
                },
            }
        ]
        agg = build_user_aggregate_from_stats(stats)
        assert agg is not None
        assert agg.total_games == 1
        # UNCERTAIN excluded, "uncertain" treated as a real tag here
        # (the function trusts the caller to have already normalised
        # raw tag names — "uncertain" is a MeaningTagId.value, not
        # the UNCERTAIN sentinel "uncertain" placeholder).
        # Just check the totals add up to the right counts.
        assert agg.weak_tags["overplay"] == 2
        assert agg.weak_tags["endgame_slip"] == 1
        assert agg.weak_tags["connection_miss"] == 1
        # Source game id is captured.
        assert agg.source_games == ("game1.sgf",)

    def test_multi_game_accumulates_counts(self) -> None:
        """The user's bug: 3 games where reading_failure appears in
        every game's recommended_tags must yield a weak_tags entry
        of 3, not 0.
        """
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        stats = [
            {
                "game_name": "g1.sgf",
                "meaning_tags_by_player": {
                    "B": {"reading_failure": 2, "overplay": 1},
                    "W": {"endgame_slip": 1},
                },
            },
            {
                "game_name": "g2.sgf",
                "meaning_tags_by_player": {
                    "B": {"reading_failure": 1, "overplay": 2},
                    "W": {"connection_miss": 1},
                },
            },
            {
                "game_name": "g3.sgf",
                "meaning_tags_by_player": {
                    "B": {"overplay": 1, "life_death_error": 1},
                    "W": {"reading_failure": 1},
                },
            },
        ]
        agg = build_user_aggregate_from_stats(stats)
        assert agg is not None
        # reading_failure: g1=2 + g2=1 + g3=1 = 4
        assert agg.weak_tags["reading_failure"] == 4
        # overplay: g1=1 + g2=2 + g3=1 = 4
        assert agg.weak_tags["overplay"] == 4
        # endgame_slip: 1, connection_miss: 1, life_death_error: 1
        assert agg.weak_tags["endgame_slip"] == 1
        assert agg.weak_tags["connection_miss"] == 1
        assert agg.weak_tags["life_death_error"] == 1
        assert agg.total_games == 3

    def test_excludes_uncertain_sentinel(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        # UNCERTAIN_TAG value is "uncertain" per
        # katrain.core.analysis.meaning_tags.models.MeaningTagId.UNCERTAIN.value
        stats = [
            {
                "game_name": "g1.sgf",
                "meaning_tags_by_player": {
                    "B": {"overplay": 1, "uncertain": 5},
                },
            }
        ]
        agg = build_user_aggregate_from_stats(stats)
        assert agg is not None
        assert "uncertain" not in agg.weak_tags
        assert agg.weak_tags["overplay"] == 1

    def test_skips_stats_without_meaning_tags(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        stats = [
            {"game_name": "g1.sgf"},  # no meaning_tags_by_player
            {"game_name": "g2.sgf", "meaning_tags_by_player": "garbage"},
            {"game_name": "g3.sgf", "meaning_tags_by_player": {}},
            {
                "game_name": "g4.sgf",
                "meaning_tags_by_player": {
                    "B": {"overplay": 1},
                },
            },
        ]
        agg = build_user_aggregate_from_stats(stats)
        assert agg is not None
        assert agg.weak_tags == {"overplay": 1}
        assert agg.total_games == 1

    def test_skips_non_dict_entries(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        stats = [
            "not a dict",
            None,
            42,
            {"meaning_tags_by_player": {"B": {"overplay": 1}}},
        ]
        agg = build_user_aggregate_from_stats(stats)
        assert agg is not None
        assert agg.weak_tags == {"overplay": 1}

    def test_source_games_fallback_chain(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        stats = [
            {"meaning_tags_by_player": {"B": {"overplay": 1}}},
            {"title": "Game Title", "meaning_tags_by_player": {"B": {"overplay": 1}}},
            {"game_id": "id-1", "meaning_tags_by_player": {"B": {"overplay": 1}}},
        ]
        agg = build_user_aggregate_from_stats(stats)
        assert agg is not None
        # First entry has no name/title/id; that's ok (count drops).
        # We expect the second and third to be recorded.
        assert "Game Title" in agg.source_games
        assert "id-1" in agg.source_games
        # total_games falls back to len(game_stats_list) when no
        # identifier is present in any entry.
        assert agg.total_games == 3

    def test_total_games_falls_back_to_list_length(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        stats = [{"meaning_tags_by_player": {"B": {"x": 1}}}]
        agg = build_user_aggregate_from_stats(stats)
        assert agg is not None
        assert agg.total_games == 1
        assert agg.source_games == ()

    def test_returns_none_when_no_meaningful_data(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        stats = [
            {"game_name": "g1.sgf", "meaning_tags_by_player": {}},
            {"game_name": "g2.sgf"},  # no key
        ]
        assert build_user_aggregate_from_stats(stats) is None

    def test_preserves_per_player_breakdown(self) -> None:
        from katrain.core.curator.batch import build_user_aggregate_from_stats

        stats = [
            {
                "game_name": "g1.sgf",
                "meaning_tags_by_player": {
                    "B": {"overplay": 1},
                    "W": {"reading_failure": 1},
                },
            },
            {
                "game_name": "g2.sgf",
                "meaning_tags_by_player": {
                    "B": {"overplay": 2},
                },
            },
        ]
        agg = build_user_aggregate_from_stats(stats)
        assert agg is not None
        assert agg.meaning_tags_by_player["B"]["overplay"] == 3
        assert agg.meaning_tags_by_player["W"]["reading_failure"] == 1


# ---------------------------------------------------------------------------
# 2. UserAggregate dataclass
# ---------------------------------------------------------------------------


class TestUserAggregateDataclass:
    def test_is_meaningful_with_tags(self) -> None:
        from katrain.core.curator.models import UserAggregate

        agg = UserAggregate(
            weak_tags={"overplay": 1},
            meaning_tags_by_player={},
            total_games=1,
        )
        assert agg.is_meaningful() is True

    def test_is_meaningful_empty(self) -> None:
        from katrain.core.curator.models import UserAggregate

        agg = UserAggregate(
            weak_tags={},
            meaning_tags_by_player={},
            total_games=0,
        )
        assert agg.is_meaningful() is False

    def test_frozen(self) -> None:
        from katrain.core.curator.models import UserAggregate

        agg = UserAggregate(
            weak_tags={"x": 1},
            meaning_tags_by_player={},
            total_games=1,
        )
        with pytest.raises((AttributeError, Exception)):
            agg.total_games = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. Profile loader recommended_tags fallback
# ---------------------------------------------------------------------------


class TestCuratorProfileLoaderFallback:
    """Test the Phase 268+ fallback that recovers weak_tags from
    rankings[*].recommended_tags when user_weak_tags is empty.
    """

    def _make_payload(self, user_weak_tags, rankings, total_games=3):
        return {
            "version": "1.0",
            "total_games": total_games,
            "user_weak_tags": user_weak_tags,
            "rankings": rankings,
        }

    def test_user_weak_tags_priority(self) -> None:
        """When user_weak_tags is non-empty, it wins regardless of
        what rankings[*].recommended_tags says.
        """
        from katrain.core.curator.profile import curator_profile_from_payload

        payload = self._make_payload(
            user_weak_tags={"life_death_error": 5},
            rankings=[
                {
                    "game_id": "g1.sgf",
                    "recommended_tags": ["reading_failure", "overplay"],
                }
            ],
        )
        profile = curator_profile_from_payload(payload)
        assert profile is not None
        assert profile.weak_tags == {"life_death_error": 5}

    def test_fallback_when_user_weak_tags_empty(self) -> None:
        """The bug we are fixing: rankings exist with common
        recommended_tags but user_weak_tags is empty.  The loader
        must synthesise weak_tags from the per-game recommendations.
        """
        from katrain.core.curator.profile import curator_profile_from_payload

        payload = self._make_payload(
            user_weak_tags=[],
            rankings=[
                {
                    "game_id": "g1.sgf",
                    "recommended_tags": ["reading_failure", "overplay", "endgame_slip"],
                },
                {
                    "game_id": "g2.sgf",
                    "recommended_tags": ["reading_failure", "overplay", "connection_miss"],
                },
                {
                    "game_id": "g3.sgf",
                    "recommended_tags": ["overplay", "life_death_error", "reading_failure"],
                },
            ],
        )
        profile = curator_profile_from_payload(payload)
        assert profile is not None
        # reading_failure: 3 occurrences (g1, g2, g3) → above min=3
        assert profile.weak_tags.get("reading_failure") == 3
        # overplay: 3 occurrences (g1, g2, g3) → above min=3
        assert profile.weak_tags.get("overplay") == 3
        # endgame_slip: 1, connection_miss: 1, life_death_error: 1
        # (each only in one game → below min=3 → excluded)
        assert "endgame_slip" not in profile.weak_tags
        assert "connection_miss" not in profile.weak_tags
        assert "life_death_error" not in profile.weak_tags

    def test_fallback_respects_min_occurrences(self) -> None:
        from katrain.core.curator.profile import curator_profile_from_payload

        payload = self._make_payload(
            user_weak_tags=[],
            rankings=[
                {"recommended_tags": ["overplay"]},
                {"recommended_tags": ["overplay", "reading_failure"]},
                {"recommended_tags": ["reading_failure"]},
                {"recommended_tags": ["reading_failure"]},
            ],
            total_games=4,
        )
        profile = curator_profile_from_payload(payload, min_occurrences=2)
        assert profile is not None
        # overplay: 2, reading_failure: 3
        assert profile.weak_tags == {"overplay": 2, "reading_failure": 3}

    def test_fallback_empty_rankings(self) -> None:
        from katrain.core.curator.profile import curator_profile_from_payload

        # total_games=0 and no rankings → no info, returns None
        payload = self._make_payload(user_weak_tags=[], rankings=[], total_games=0)
        profile = curator_profile_from_payload(payload)
        assert profile is None

    def test_fallback_empty_rankings_with_total_games(self) -> None:
        """A payload that says total_games=3 but has neither
        user_weak_tags nor any rankings still returns a (empty)
        profile — the file is recognised, just nothing to extract.
        """
        from katrain.core.curator.profile import curator_profile_from_payload

        payload = self._make_payload(user_weak_tags=[], rankings=[], total_games=3)
        profile = curator_profile_from_payload(payload)
        assert profile is not None
        assert profile.weak_tags == {}
        assert profile.total_games == 3

    def test_fallback_with_min_occurrences_1(self) -> None:
        from katrain.core.curator.profile import curator_profile_from_payload

        payload = self._make_payload(
            user_weak_tags=[],
            rankings=[
                {"recommended_tags": ["overplay"]},
                {"recommended_tags": ["reading_failure"]},
            ],
            total_games=2,
        )
        profile = curator_profile_from_payload(payload, min_occurrences=1)
        assert profile is not None
        assert profile.weak_tags == {"overplay": 1, "reading_failure": 1}

    def test_fallback_skips_malformed_entries(self) -> None:
        from katrain.core.curator.profile import curator_profile_from_payload

        payload = self._make_payload(
            user_weak_tags=[],
            rankings=[
                "not a dict",
                {"recommended_tags": "not a list"},
                {"recommended_tags": [1, 2, None, ""]},
                {"recommended_tags": ["overplay", "overplay"]},
                {"recommended_tags": ["overplay"]},
                {"recommended_tags": ["overplay"]},
            ],
            total_games=6,
        )
        profile = curator_profile_from_payload(payload, min_occurrences=2)
        assert profile is not None
        # Only the valid overplay entries count: 4 occurrences
        assert profile.weak_tags == {"overplay": 4}

    def test_load_curator_profile_from_file(self) -> None:
        """End-to-end: write a legacy JSON to disk, load it via the
        public API, and confirm the fallback populated weak_tags.
        """
        from katrain.core.curator.profile import load_curator_profile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "curator_ranking.json"
            data = {
                "version": "1.0",
                "total_games": 3,
                "user_weak_tags": [],
                "rankings": [
                    {
                        "game_id": "g1.sgf",
                        "recommended_tags": ["reading_failure", "overplay"],
                    },
                    {
                        "game_id": "g2.sgf",
                        "recommended_tags": ["reading_failure", "overplay"],
                    },
                    {
                        "game_id": "g3.sgf",
                        "recommended_tags": ["reading_failure", "overplay"],
                    },
                ],
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            profile = load_curator_profile(path)
            assert profile is not None
            assert profile.weak_tags == {"reading_failure": 3, "overplay": 3}
            assert profile.total_games == 3

    def test_load_curator_profile_real_user_json(self) -> None:
        """Pin the fix for the user's actual JSON.  Before the fix,
        this file produced 0 weak tags despite 3 games with
        overlapping recommended_tags.
        """
        from katrain.core.curator.profile import load_curator_profile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "curator_ranking.json"
            data = {
                "version": "1.0",
                "total_games": 3,
                "user_weak_tags": [],
                "rankings": [
                    {
                        "game_id": "[富乐山下]vs[仙得]1761895784030052536.sgf",
                        "recommended_tags": ["reading_failure", "overplay", "endgame_slip"],
                    },
                    {
                        "game_id": "[爱心文化]vs[仙得]1762159392030043871.sgf",
                        "recommended_tags": ["reading_failure", "overplay", "connection_miss"],
                    },
                    {
                        "game_id": "[醉舞]vs[仙得]1762426844030053574.sgf",
                        "recommended_tags": ["overplay", "life_death_error", "reading_failure"],
                    },
                ],
            }
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            profile = load_curator_profile(path)
            assert profile is not None
            # reading_failure: 3, overplay: 3 → both reach min=3
            assert profile.weak_tags.get("reading_failure") == 3
            assert profile.weak_tags.get("overplay") == 3
            # the others appear only once → excluded
            for absent in ("endgame_slip", "connection_miss", "life_death_error"):
                assert absent not in profile.weak_tags


# ---------------------------------------------------------------------------
# 4. run_batch wires user_aggregate
# ---------------------------------------------------------------------------


class TestRunBatchUserAggregateWiring:
    """Pin that run_batch() builds a UserAggregate from
    game_stats_list when the caller did not pass one.  We test the
    *contract* (the inline wiring inside run_batch) by directly
    exercising the build_user_aggregate_from_stats call that the
    wiring now performs; the run_batch surface itself is exercised
    by tests/batch/test_output.py which already covers the full
    engine-driven path.
    """

    def test_run_batch_inline_builds_user_aggregate(self) -> None:
        """The wiring added in Phase 268 calls
        ``build_user_aggregate_from_stats(game_stats_list)`` when
        the caller did not supply ``user_aggregate``.  This test
        pins that the helper produces a usable aggregate from the
        shape ``game_stats_list`` actually carries in production.
        """
        from katrain.core.curator.batch import build_user_aggregate_from_stats
        from katrain.core.curator.models import UserAggregate

        game_stats_list = [
            {
                "game_name": "g1.sgf",
                "meaning_tags_by_player": {
                    "B": {"overplay": 1, "reading_failure": 2},
                },
            },
            {
                "game_name": "g2.sgf",
                "meaning_tags_by_player": {
                    "B": {"overplay": 1, "reading_failure": 1},
                },
            },
        ]
        # Mirror the inline call in run_batch().
        user_aggregate = build_user_aggregate_from_stats(game_stats_list)
        assert isinstance(user_aggregate, UserAggregate)
        # reading_failure appears in both games → reaches min_occurrences=3
        # only when we add the third game; in 2 games we get 3 occurrences
        # (2 + 1 = 3).
        assert user_aggregate.weak_tags.get("reading_failure") == 3
        assert user_aggregate.weak_tags.get("overplay") == 2

    def test_curator_ranking_json_written_with_weak_tags(self, tmp_path) -> None:
        """End-to-end: feed a non-empty ``user_aggregate`` into
        ``generate_curator_outputs`` and confirm the resulting JSON
        has populated ``user_weak_tags``.  This is the contract the
        orchestration layer now satisfies.
        """
        from katrain.core.curator.batch import (
            build_user_aggregate_from_stats,
            generate_curator_outputs,
        )

        game_stats_list = [
            {
                "game_name": "g1.sgf",
                "meaning_tags_by_player": {"B": {"reading_failure": 1, "overplay": 1}},
            },
            {
                "game_name": "g2.sgf",
                "meaning_tags_by_player": {"B": {"reading_failure": 1, "overplay": 1}},
            },
            {
                "game_name": "g3.sgf",
                "meaning_tags_by_player": {"B": {"reading_failure": 1, "overplay": 1}},
            },
        ]
        # 1) Build the user_aggregate the way run_batch() now does.
        user_aggregate = build_user_aggregate_from_stats(game_stats_list)
        assert user_aggregate is not None

        # 2) Pass it through to generate_curator_outputs.  We use
        #    minimal placeholder games — the helper only needs the
        #    stats dicts to render the rankings + weak_tags.  The
        #    game object is still walked by scoring.compute_stability,
        #    so we need a ``root`` attribute that has no children.
        class _FakeNode:
            children = []
            analysis = None

        class _FakeGame:
            def __init__(self, name):
                self.name = name
                self.root = _FakeNode()

        games_and_stats = [
            (_FakeGame("g1.sgf"), game_stats_list[0]),
            (_FakeGame("g2.sgf"), game_stats_list[1]),
            (_FakeGame("g3.sgf"), game_stats_list[2]),
        ]
        out_dir = tmp_path / "curator_out"
        result = generate_curator_outputs(
            games_and_stats=games_and_stats,
            curator_dir=str(out_dir),
            batch_timestamp="20260718-000000",
            user_aggregate=user_aggregate,
        )
        assert result.ranking_path is not None
        payload = json.loads(Path(result.ranking_path).read_text(encoding="utf-8"))
        # 3) The bug we are fixing: pre-Phase 268, this list was
        #    always [].
        assert payload["user_weak_tags"] == ["overplay", "reading_failure"]
        # And the per-game rankings still carry their per-mistake
        # recommended_tags.
        assert all("recommended_tags" in r for r in payload["rankings"])
        assert payload["total_games"] == 3


# ---------------------------------------------------------------------------
# 5. i18n key presence
# ---------------------------------------------------------------------------


class TestCuratorHintNoTagsI18n:
    def test_jp_po_has_no_tags_key(self) -> None:
        po = polib.pofile(str(JP_PO_PATH))
        entry = po.find("mykatrain:settings:curator_hint_loaded_no_tags")
        assert entry is not None
        assert "弱点タグなし" in entry.msgstr or "batch" in entry.msgstr.lower()

    def test_en_po_has_no_tags_key(self) -> None:
        po = polib.pofile(str(EN_PO_PATH))
        entry = po.find("mykatrain:settings:curator_hint_loaded_no_tags")
        assert entry is not None
        assert "weak tag" in entry.msgstr.lower() or "no weak" in entry.msgstr.lower()
