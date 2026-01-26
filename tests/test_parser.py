import os
from unittest.mock import MagicMock

import pytest

from katrain.core.base_katrain import KaTrainBase
from katrain.core.game import Game, KaTrainSGF
from katrain.core.sgf_parser import SGF, SGFNode, Move, ParseError


def test_simple():
    input_sgf = "(;GM[1]FF[4]SZ[19]DT[2020-04-12]AB[dd][dj];B[dp];W[pp];B[pj])"
    root = SGF.parse_sgf(input_sgf)
    assert "4" == root.get_property("FF")
    assert root.get_property("XYZ") is None
    assert "dp" == root.children[0].get_property("B")
    assert input_sgf == root.sgf()


def test_branch():
    input_sgf = "(;GM[1]FF[4]CA[UTF-8]AP[Sabaki:0.43.3]KM[6.5]SZ[19]DT[2020-04-12]AB[dd][dj](;B[dp];W[pp](;B[pj])(;PL[B]AW[jp]C[sdfdsfdsf]))(;B[pd]))"
    root = SGF.parse_sgf(input_sgf)
    assert input_sgf == root.sgf()


def test_dragon_weirdness():  # dragon go server has weird line breaks
    input_sgf = "\n(\n\n;\nGM[1]\nFF[4]\nCA[UTF-8]AP[Sabaki:0.43.3]KM[6.5]SZ[19]DT[2020-04-12]AB[dd]\n[dj]\n(\n;\nB[dp]\n;\nW[pp]\n(\n;\nB[pj]\n)\n(\n;\nPL[B]\nAW[jp]\nC[sdfdsfdsf]\n)\n)\n(\n;\nB[pd]\n)\n)\n"
    root = SGF.parse_sgf(input_sgf)
    assert input_sgf.replace("\n", "") == root.sgf()


def test_weird_escape():
    input_sgf = """(;GM[1]FF[4]CA[UTF-8]AP[Sabaki:0.43.3]KM[6.5]SZ[19]DT[2020-04-12]C[how does it escape
[
or \\]
])"""
    root = SGF.parse_sgf(input_sgf)
    assert input_sgf == root.sgf()


def test_backslash_escape():
    nasty_string = "[]]\\"
    nasty_strings = ["[\\]\\]\\\\", "[", "]", "\\", "\\[", "\\]", "\\\\[", "\\\\]", "]]]\\]]\\]]["]
    assert "[\\]\\]\\\\" == SGFNode._escape_value(nasty_string)
    for x in nasty_strings:
        assert x == SGFNode._unescape_value(SGFNode._escape_value(x))

    c2 = ["]", "\\"]
    node = SGFNode(properties={"C1": nasty_string})
    node.set_property("C2", c2)
    assert "(;C1[[\\]\\]\\\\]C2[\\]][\\\\])" == node.sgf()
    assert {"C1": [nasty_string], "C2": c2} == SGF.parse_sgf(node.sgf()).properties


def test_alphago():
    file = os.path.join(os.path.dirname(__file__), "data/LS vs AG - G4 - English.sgf")
    SGF.parse_file(file)


def test_pandanet():
    file = os.path.join(os.path.dirname(__file__), "data/panda1.sgf")
    root = SGF.parse_file(file)
    root_props = {
        "GM",
        "EV",
        "US",
        "CP",
        "GN",
        "RE",
        "PW",
        "WR",
        "NW",
        "PB",
        "BR",
        "NB",
        "PC",
        "DT",
        "SZ",
        "TM",
        "KM",
        "LT",
        "RR",
        "HA",
        "AB",
        "C",
    }
    assert root_props == root.properties.keys()

    move = root
    while move.children:
        move = move.children[0]
    assert 94 == len(move.get_list_property("TW"))
    assert "Trilan" == move.get_property("OS")
    while move.parent:
        move = move.parent
    assert move is root


def test_old_long_properties():
    file = os.path.join(os.path.dirname(__file__), "data/xmgt97.sgf")
    SGF.parse_file(file)


def test_old_server_style():
    input_sgf = "... 01:23:45 +0900 (JST) ... (;SZ[19];B[aa];W[ba];)"
    SGF.parse_sgf(input_sgf)


def test_old_server_style_again():
    input_sgf = """(;
SZ[19]TM[600]KM[0.500000]LT[]

;B[fp]BL[500];

)"""
    tree = SGF.parse_sgf(input_sgf)
    assert 2 == len(tree.nodes_in_tree)


def test_ogs():
    file = os.path.join(os.path.dirname(__file__), "data/ogs.sgf")
    SGF.parse_file(file)


def test_gibo():
    file = os.path.join(os.path.dirname(__file__), "data/test.gib")
    root = SGF.parse_file(file)
    assert {
        "PW": ["wildsim1"],
        "WR": ["2D"],
        "PB": ["kim"],
        "BR": ["2D"],
        "RE": ["W+T"],
        "KM": [6.5],
        "DT": ["2020-06-14"],
    } == root.properties
    assert "pd" == root.children[0].get_property("B")


def test_ngf():
    file = os.path.join(os.path.dirname(__file__), "data/handicap2.ngf")
    root = SGF.parse_file(file)
    root.properties["AB"].sort()
    assert {
        "AB": ["dp", "pd"],
        "DT": ["2017-03-16"],
        "HA": [2],
        "PB": ["p81587"],
        "PW": ["ace550"],
        "RE": ["W+"],
        "SZ": [19],
    } == root.properties
    assert "pq" == root.children[0].get_property("W")


def test_foxwq():
    for sgf in ["data/fox sgf error.sgf", "data/fox sgf works.sgf"]:
        file = os.path.join(os.path.dirname(__file__), sgf)
        move_tree = KaTrainSGF.parse_file(file)
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        game = Game(katrain, MagicMock(), move_tree)

        assert [] == move_tree.placements
        assert [] == game.root.placements
        while game.current_node.children:
            assert 1 == len(game.current_node.children)
            game.redo(1)


def test_next_player():
    input_sgf = "(;GM[1]FF[4]AB[aa]AW[bb])"
    assert "B" == SGF.parse_sgf(input_sgf).next_player
    assert "B" == SGF.parse_sgf(input_sgf).initial_player
    input_sgf = "(;GM[1]FF[4]AB[aa]AW[bb]PL[B])"
    assert "B" == SGF.parse_sgf(input_sgf).next_player
    assert "B" == SGF.parse_sgf(input_sgf).initial_player
    input_sgf = "(;GM[1]FF[4]AB[aa]AW[bb]PL[W])"
    assert "W" == SGF.parse_sgf(input_sgf).next_player
    assert "W" == SGF.parse_sgf(input_sgf).initial_player
    input_sgf = "(;GM[1]FF[4]AB[aa])"
    assert "W" == SGF.parse_sgf(input_sgf).next_player
    assert "W" == SGF.parse_sgf(input_sgf).initial_player
    input_sgf = "(;GM[1]FF[4]AB[aa]PL[B])"
    assert "B" == SGF.parse_sgf(input_sgf).next_player
    assert "B" == SGF.parse_sgf(input_sgf).initial_player
    input_sgf = "(;GM[1]FF[4]AB[aa];B[dd])"  # branch exists
    assert "B" == SGF.parse_sgf(input_sgf).next_player
    assert "B" == SGF.parse_sgf(input_sgf).initial_player
    input_sgf = "(;GM[1]FF[4]AB[aa];W[dd])"  # branch exists
    assert "W" == SGF.parse_sgf(input_sgf).next_player
    assert "W" == SGF.parse_sgf(input_sgf).initial_player


def test_placements():
    input_sgf = "(;GM[1]FF[4]SZ[19]DT[2020-04-12]AB[dd][aa:ee]AW[ff:zz]AE[aa][bb][cc:dd])"
    root = SGF.parse_sgf(input_sgf)
    print(root.properties)
    assert 6 == len(root.clear_placements)
    assert 25 + 14 * 14 == len(root.placements)


# =============================================================================
# Phase 69: Test Enhancement - Move, ParseError, EdgeCases, RoundTrip
# =============================================================================


class TestMoveClass:
    """Move class tests.

    実装確認済み:
    - __hash__() 実装あり（sgf_parser.py:78-79）→ ハッシュ可能
    """

    def test_from_gtp_roundtrip_d4(self):
        """D4のラウンドトリップ"""
        m = Move.from_gtp("D4", player="B")
        assert m.gtp() == "D4"
        assert m.player == "B"

    def test_from_gtp_roundtrip_q16(self):
        """Q16のラウンドトリップ"""
        m = Move.from_gtp("Q16", player="W")
        assert m.gtp() == "Q16"

    def test_from_gtp_pass(self):
        """パス手"""
        m = Move.from_gtp("pass", player="W")
        assert m.is_pass
        assert m.gtp() == "pass"

    def test_from_gtp_pass_case_insensitive(self):
        """PASS, Pass も受け入れる"""
        for variant in ["pass", "PASS", "Pass"]:
            m = Move.from_gtp(variant, player="B")
            assert m.is_pass

    def test_from_gtp_j1_roundtrip(self):
        """J1がラウンドトリップできる（I列スキップ後）"""
        m = Move.from_gtp("J1", player="B")
        assert m.gtp() == "J1"
        assert isinstance(m.coords, tuple)
        assert len(m.coords) == 2

    def test_from_gtp_i_column_rejected(self):
        """I列は無効（GTP_COORDに含まれない）"""
        with pytest.raises(ValueError):
            Move.from_gtp("I1", player="B")

    def test_from_gtp_invalid_format_raises(self):
        """無効フォーマットでValueError"""
        with pytest.raises(ValueError):
            Move.from_gtp("XYZ", player="B")

    def test_equality_and_hash(self):
        """等価性とハッシュ（__hash__実装確認済み）"""
        m1 = Move.from_gtp("D4", player="B")
        m2 = Move.from_gtp("D4", player="B")
        m3 = Move.from_gtp("D4", player="W")
        assert m1 == m2
        assert m1 != m3
        # ハッシュ可能（__hash__実装済み）
        s = {m1}
        assert m2 in s

    def test_opponent_property(self):
        """opponentプロパティ"""
        assert Move.from_gtp("D4", player="B").opponent == "W"
        assert Move.from_gtp("D4", player="W").opponent == "B"


class TestParseError:
    """ParseError tests（実装確認済み）"""

    def test_missing_opening_paren(self):
        """開き括弧なし → ParseError"""
        with pytest.raises(ParseError):
            SGF.parse_sgf("GM[1]FF[4]SZ[19]")

    def test_unclosed_property_value(self):
        """閉じ括弧なし → ParseError"""
        with pytest.raises(ParseError):
            SGF.parse_sgf("(;GM[1]FF[4]SZ[19")

    def test_empty_string(self):
        """空文字列 → ParseError"""
        with pytest.raises(ParseError):
            SGF.parse_sgf("")


class TestPropertyEdgeCases:
    """Property edge case tests（board_size: タプル返却確認済み）"""

    def test_komi_invalid_returns_numeric(self):
        """無効なKMでも数値が返る"""
        root = SGF.parse_sgf("(;GM[1]KM[invalid])")
        assert isinstance(root.komi, (int, float))

    def test_handicap_invalid_returns_int(self):
        """無効なHAでも整数が返る"""
        root = SGF.parse_sgf("(;GM[1]HA[invalid])")
        assert isinstance(root.handicap, int)

    def test_board_size_9x9(self):
        """SZ[9] - 標準9x9ボード"""
        root = SGF.parse_sgf("(;GM[1]SZ[9])")
        assert root.board_size == (9, 9)

    def test_board_size_13x13(self):
        """SZ[13] - 標準13x13ボード"""
        root = SGF.parse_sgf("(;GM[1]SZ[13])")
        assert root.board_size == (13, 13)

    def test_board_size_19x19(self):
        """SZ[19] - 標準19x19ボード"""
        root = SGF.parse_sgf("(;GM[1]SZ[19])")
        assert root.board_size == (19, 19)


class TestRoundTrip:
    """Roundtrip tests.

    get_property()は単一値を返す（sgf_parser.py:196）
    """

    def test_special_chars_semantic_equivalence(self):
        """特殊文字を含むコメントのセマンティック等価性"""
        input_sgf = r"(;GM[1]C[Test\]with\\brackets])"
        root = SGF.parse_sgf(input_sgf)
        output = root.sgf()
        reparsed = SGF.parse_sgf(output)
        # get_property()は単一値を返す（型は同一）
        original_comment = root.get_property("C")
        reparsed_comment = reparsed.get_property("C")
        assert original_comment == reparsed_comment

    def test_variation_tree_semantic_equivalence(self):
        """変化ツリーのセマンティック等価性"""
        input_sgf = "(;GM[1]SZ[9](;B[dd](;W[ff])(;W[gg]))(;B[ee]))"
        root = SGF.parse_sgf(input_sgf)
        assert len(root.children) == 2
        assert len(root.children[0].children) == 2

        output = root.sgf()
        reparsed = SGF.parse_sgf(output)

        # 構造の等価性
        assert len(reparsed.children) == len(root.children)
        assert len(reparsed.children[0].children) == len(root.children[0].children)

        # プロパティ保存の確認（脆弱性が低い追加チェック）
        assert root.children[0].get_property("B") == "dd"
        assert reparsed.children[0].get_property("B") == "dd"
        assert root.children[1].get_property("B") == "ee"
        assert reparsed.children[1].get_property("B") == "ee"
