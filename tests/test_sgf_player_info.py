"""Tests for :mod:`katrain.core.coach.sgf_player_info`.

Phase 225.6: pure / Kivy-free helpers that extract black/white player
info from SGF files. These tests run headless-CI friendly without
Kivy / Katrain init.
"""

from __future__ import annotations

import re

import pytest

from katrain.core.coach.sgf_player_info import (
    PlayerInfo,
    SgfPlayerInfo,
    extract_player_info_for_user,
    extract_player_info_from_sgf,
    parse_sgf_player_info,
)


# --- parse_sgf_player_info --------------------------------------------


class TestParseSgfPlayerInfo:
    def test_basic_extraction(self) -> None:
        sgf = "(;GM[1]FF[4]PB[醉舞]BR[4d]PW[仙得]WR[4d]SZ[19];B[pd];W[dp])"
        info = parse_sgf_player_info(sgf)
        assert info.black.name == "醉舞"
        assert info.black.rank == "4d"
        assert info.white.name == "仙得"
        assert info.white.rank == "4d"

    def test_only_names_no_ranks(self) -> None:
        sgf = "(;GM[1]PB[sentoku]PW[opponent];B[pd])"
        info = parse_sgf_player_info(sgf)
        assert info.black.name == "sentoku"
        assert info.black.rank is None
        assert info.white.name == "opponent"
        assert info.white.rank is None

    def test_only_ranks_no_names(self) -> None:
        sgf = "(;GM[1]BR[5k]WR[6k];B[pd])"
        info = parse_sgf_player_info(sgf)
        assert info.black.name is None
        assert info.black.rank == "5k"
        assert info.white.name is None
        assert info.white.rank == "6k"

    def test_missing_root(self) -> None:
        info = parse_sgf_player_info("not sgf content at all")
        assert info.black == PlayerInfo()
        assert info.white == PlayerInfo()

    def test_only_first_root_properties_used(self) -> None:
        """SGF game trees can have child nodes with their own properties.
        We must only read the root (first '(;' block)."""
        sgf = (
            "(;GM[1]PB[RootBlack]BR[4d]PW[RootWhite]WR[3d];"
            "B[pd](;B[dd]PB[ChildBlack]BR[5k]))"
        )
        info = parse_sgf_player_info(sgf)
        assert info.black.name == "RootBlack"
        assert info.black.rank == "4d"
        assert info.white.name == "RootWhite"
        assert info.white.rank == "3d"

    def test_empty_string(self) -> None:
        info = parse_sgf_player_info("")
        assert info.black == PlayerInfo()
        assert info.white == PlayerInfo()

    def test_path_echo(self) -> None:
        info = parse_sgf_player_info("(;)", sgf_path="/tmp/x.sgf")
        assert info.sgf_path == "/tmp/x.sgf"

    def test_unbalanced_brackets_handled(self) -> None:
        """If we never find the closing ')', return whatever we scanned."""
        sgf = "(;GM[1]PB[onlyBlack]"  # never closes
        info = parse_sgf_player_info(sgf)
        assert info.black.name == "onlyBlack"


# --- extract_player_info_from_sgf -------------------------------------


class TestExtractPlayerInfoFromSgf:
    def test_reads_file(self, tmp_path) -> None:
        sgf = tmp_path / "game.sgf"
        sgf.write_text(
            "(;GM[1]FF[4]PB[醉舞]BR[4d]PW[仙得]WR[3d];B[pd])",
            encoding="utf-8",
        )
        info = extract_player_info_from_sgf(sgf)
        assert info.black.name == "醉舞"
        assert info.black.rank == "4d"
        assert info.white.name == "仙得"
        assert info.white.rank == "3d"
        assert info.sgf_path == str(sgf)

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_player_info_from_sgf(tmp_path / "missing.sgf")


# --- extract_player_info_for_user ------------------------------------


class TestExtractPlayerInfoForUser:
    def test_no_username_returns_none(self) -> None:
        info = SgfPlayerInfo(
            black=PlayerInfo(name="sentoku", rank="5k"),
            white=PlayerInfo(name="opponent", rank="6k"),
        )
        assert extract_player_info_for_user(info, None) == (None, None)
        assert extract_player_info_for_user(info, "") == (None, None)

    def test_black_match(self) -> None:
        info = SgfPlayerInfo(
            black=PlayerInfo(name="sentoku", rank="5k"),
            white=PlayerInfo(name="opponent", rank="6k"),
        )
        color, rank = extract_player_info_for_user(info, "sentoku")
        assert color == "B"
        assert rank == "5k"

    def test_white_match(self) -> None:
        info = SgfPlayerInfo(
            black=PlayerInfo(name="sentoku", rank="5k"),
            white=PlayerInfo(name="opponent", rank="6k"),
        )
        color, rank = extract_player_info_for_user(info, "opponent")
        assert color == "W"
        assert rank == "6k"

    def test_substring_match(self) -> None:
        info = SgfPlayerInfo(
            black=PlayerInfo(name="sentoku870", rank="5k"),
            white=PlayerInfo(name="someone", rank="6k"),
        )
        # "sentoku" is contained in "sentoku870"
        color, _ = extract_player_info_for_user(info, "sentoku")
        assert color == "B"

    def test_case_insensitive(self) -> None:
        info = SgfPlayerInfo(
            black=PlayerInfo(name="Sentoku", rank="5k"),
            white=PlayerInfo(name="opponent", rank="6k"),
        )
        color, _ = extract_player_info_for_user(info, "SENTOKU")
        assert color == "B"

    def test_no_match_returns_none(self) -> None:
        info = SgfPlayerInfo(
            black=PlayerInfo(name="sentoku", rank="5k"),
            white=PlayerInfo(name="opponent", rank="6k"),
        )
        color, rank = extract_player_info_for_user(info, "unknown")
        assert color is None
        assert rank is None

    def test_punctuation_ignored(self) -> None:
        info = SgfPlayerInfo(
            black=PlayerInfo(name="醉舞(野狐)", rank="4d"),
            white=PlayerInfo(name="仙得", rank="4d"),
        )
        # "醉舞(野狐)" normalises to "醉舞野狐" while the query
        # "醉舞" is a substring of that, so we still match.
        color, rank = extract_player_info_for_user(info, "醉舞")
        assert color == "B"
        assert rank == "4d"