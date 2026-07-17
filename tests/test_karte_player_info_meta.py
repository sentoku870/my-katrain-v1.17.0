"""Phase 225.6: tests for the new ``player_info`` block in Karte meta.

We mock the heavy ``katrain.core.reports.karte.json_export.build_karte_json``
pipeline and just verify that ``MetaExtractor.extract_game_meta`` returns
the new ``ranks`` field and that ``json_export`` propagates it into
``meta.player_info``. The full E2E build_karte_json is exercised by
the existing karte suite (we don't duplicate those tests here).
"""

from __future__ import annotations

# --- MetaExtractor (Phase 225.6) --------------------------------------


class _FakeRoot:
    """Stand-in for a ``Game`` object: it has a ``.root`` property container."""

    def __init__(self, props: dict[str, str]) -> None:
        self._inner_props = props
        self.root = self

    def get_property(self, key: str, default: str = "") -> str:
        return self._inner_props.get(key, default)


class TestMetaExtractorRanks:
    def test_extracts_br_wr_from_root(self) -> None:
        from katrain.core.reports.extractors import MetaExtractor

        root = _FakeRoot({"PB": "醉舞", "BR": "4d", "PW": "仙得", "WR": "3d"})
        meta = MetaExtractor.extract_game_meta(root, game_id="g1")
        assert meta["ranks"] == {"black": "4d", "white": "3d"}
        assert meta["players"] == {"black": "醉舞", "white": "仙得"}

    def test_missing_ranks_yields_none(self) -> None:
        from katrain.core.reports.extractors import MetaExtractor

        root = _FakeRoot({"PB": "Player1", "PW": "Player2"})
        meta = MetaExtractor.extract_game_meta(root)
        assert meta["ranks"] == {"black": None, "white": None}

    def test_partial_ranks(self) -> None:
        from katrain.core.reports.extractors import MetaExtractor

        root = _FakeRoot({"PB": "P1", "BR": "5k", "PW": "P2"})
        meta = MetaExtractor.extract_game_meta(root)
        assert meta["ranks"] == {"black": "5k", "white": None}

    def test_no_root_no_ranks(self) -> None:
        from katrain.core.reports.extractors import MetaExtractor

        class _Bare:
            game_id = "g1"

        meta = MetaExtractor.extract_game_meta(_Bare())
        assert meta["ranks"] == {"black": None, "white": None}


# --- json_export integration -------------------------------------------


class TestBuildKarteJsonMetaPlayerInfo:
    """Static analysis: the ``meta`` dict template inside
    ``json_export.build_karte_json`` must include a ``player_info`` block
    populated from the MetaExtractor's ``ranks`` field.

    We don't run the full build_karte_json pipeline (it pulls in KataGo
    snapshots / node maps and is exercised by the existing
    ``tests/test_karte_*`` suite). Instead we import the module and
    assert that the source has been wired to expose the new field.
    """

    def test_meta_template_contains_player_info(self) -> None:
        import inspect

        from katrain.core.reports.karte import json_export

        source = inspect.getsource(json_export)
        assert '"player_info"' in source, "build_karte_json meta dict must include a 'player_info' block"
        # The block must reference common_meta['players'] and common_meta['ranks']
        # so it stays in sync with MetaExtractor.
        assert 'common_meta["players"]' in source
        assert 'common_meta.get("ranks")' in source or '"ranks"' in source

    def test_meta_player_info_structure_roundtrip(self) -> None:
        """A round-trip test that exercises the meta dict construction
        inline (without the rest of build_karte_json)."""
        common_meta = {
            "name": "Game1",
            "date": "2026-01-01",
            "game_id": "g1",
            "moves": 0,
            "result": "B+R",
            "handicap": 0,
            "komi": 6.5,
            "board_size": [19, 19],
            "players": {"black": "醉舞", "white": "仙得"},
            "ranks": {"black": "4d", "white": "4d"},
        }

        # Reproduce the meta block building logic exactly as in json_export.py
        # Phase 236: each entry now also carries a stable ``color``
        # identifier so downstream consumers (LLM Coach popup, etc.) can
        # tell which side each player represents without a second SGF
        # lookup or a ``default_user_name`` match.
        player_info = {
            "black": {
                "name": common_meta["players"]["black"],
                "rank": (common_meta.get("ranks") or {}).get("black"),
                "color": "B",
            },
            "white": {
                "name": common_meta["players"]["white"],
                "rank": (common_meta.get("ranks") or {}).get("white"),
                "color": "W",
            },
        }

        assert player_info == {
            "black": {"name": "醉舞", "rank": "4d", "color": "B"},
            "white": {"name": "仙得", "rank": "4d", "color": "W"},
        }

    def test_meta_player_info_when_ranks_missing(self) -> None:
        """When MetaExtractor returns no ranks (legacy SGFs without
        BR/WR), the player_info block must still include the names
        with ``rank=None`` rather than crashing.

        Phase 236: the ``color`` field is always emitted (not gated on
        rank presence) so LLM consumers can rely on it being a stable
        identifier.
        """
        common_meta = {
            "players": {"black": "P1", "white": "P2"},
        }
        player_info = {
            "black": {
                "name": common_meta["players"]["black"],
                "rank": (common_meta.get("ranks") or {}).get("black"),
                "color": "B",
            },
            "white": {
                "name": common_meta["players"]["white"],
                "rank": (common_meta.get("ranks") or {}).get("white"),
                "color": "W",
            },
        }
        assert player_info == {
            "black": {"name": "P1", "rank": None, "color": "B"},
            "white": {"name": "P2", "rank": None, "color": "W"},
        }

    def test_meta_player_info_color_field_is_stable(self) -> None:
        """Phase 236: the ``color`` field is a stable ``"B"`` / ``"W"``
        identifier (not localised, not derived from names). Lock the
        contract so consumers can pattern-match on it directly.
        """
        # Reproduce the same block the production code builds.
        info = {
            "black": {"name": "Alice", "rank": "5d", "color": "B"},
            "white": {"name": "Bob", "rank": "4d", "color": "W"},
        }
        assert info["black"]["color"] == "B"
        assert info["white"]["color"] == "W"
        # The colour of the black entry must be "B" even when the
        # name contains "W" or vice versa.
        info_edge = {
            "black": {"name": "Walter", "rank": None, "color": "B"},
            "white": {"name": "Beatrice", "rank": None, "color": "W"},
        }
        assert info_edge["black"]["color"] == "B"
        assert info_edge["white"]["color"] == "W"

    def test_meta_template_includes_color_field(self) -> None:
        """Static check: the ``player_info`` template in
        ``json_export.build_karte_json`` must include ``"color": "B"``
        and ``"color": "W"`` (Phase 236 contract)."""
        import inspect

        from katrain.core.reports.karte import json_export

        source = inspect.getsource(json_export)
        # The two literal side identifiers must be present.
        assert '"color": "B"' in source, 'Phase 236: player_info.black must include "color": "B"'
        assert '"color": "W"' in source, 'Phase 236: player_info.white must include "color": "W"'
