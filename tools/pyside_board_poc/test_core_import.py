"""
Phase 3.0 Preflight: Core Importability Tests

Run with: python test_core_import.py
Must pass WITHOUT Kivy installed (or with Kivy blocked).

Split into:
  - Test A: Import-only tests (no gameplay)
  - Test B: Minimal logic tests (captures, ko)
"""
import sys
from importlib.abc import MetaPathFinder

# =============================================================================
# Modern Kivy Blocker (Python 3.4+ compatible)
# =============================================================================


class KivyBlocker(MetaPathFinder):
    """
    Block real Kivy imports to verify shims work.
    Uses modern importlib.abc.MetaPathFinder with find_spec().
    """

    BLOCKED_PREFIXES = ("kivy",)

    def find_spec(self, fullname, path, target=None):
        for prefix in self.BLOCKED_PREFIXES:
            if fullname == prefix or fullname.startswith(prefix + "."):
                # Raise ImportError to block the import
                raise ImportError(
                    f"[KivyBlocker] Kivy blocked for testing: {fullname}"
                )
        return None  # Not our module, let other finders handle it


# Install blocker BEFORE any imports
_blocker = KivyBlocker()
sys.meta_path.insert(0, _blocker)

# Now install shims
from katrain_qt import install_shims

install_shims()

# =============================================================================
# Test A: Import-Only Tests (no gameplay)
# =============================================================================


def test_a1_sgf_parser_import():
    """Test A1: sgf_parser imports without Kivy."""
    from katrain.core.sgf_parser import Move, SGF

    print("[OK] A1: sgf_parser imports successfully")


def test_a2_move_gtp_coords():
    """Test A2: Move.gtp() returns correct GTP string (coord contract)."""
    from katrain.core.sgf_parser import Move

    # KaTrain coords: (col, row) where row is 0-indexed from bottom
    # Move(coords=(3, 3)) -> "D4" (col=3->D, row=3->4)
    m = Move(coords=(3, 3), player="B")
    gtp = m.gtp()
    assert gtp == "D4", f"Expected 'D4', got '{gtp}'"

    # Pass move
    m_pass = Move(coords=None, player="B")
    assert m_pass.gtp() == "pass"

    # Edge case: top-left (0, 18) on 19x19 -> "A19"
    m_corner = Move(coords=(0, 18), player="B")
    assert m_corner.gtp() == "A19", f"Expected 'A19', got '{m_corner.gtp()}'"

    print("[OK] A2: Move.gtp() coord contract verified")


def test_a3_game_import():
    """Test A3: game.py imports (Clock shim works)."""
    from katrain.core.game import BaseGame, IllegalMoveException

    print("[OK] A3: game.py imports successfully")


def test_a4_game_node_import():
    """Test A4: game_node.py imports (lang.py -> Theme chain shimmed)."""
    from katrain.core.game_node import GameNode

    print("[OK] A4: game_node.py imports successfully")


def test_a5_constants_import():
    """Test A5: constants.py imports (no Kivy deps)."""
    from katrain.core.constants import PROGRAM_NAME, VERSION

    assert PROGRAM_NAME == "KaTrain"
    print("[OK] A5: constants.py imports successfully")


# =============================================================================
# Test B: Minimal Logic Tests (captures, ko)
# =============================================================================


class MockKaTrain:
    """
    Minimal mock for BaseGame instantiation.
    BaseGame requires:
      - katrain.log(msg, level)
      - katrain.config(key) for game/size, game/komi, game/rules
    """

    def __init__(self, board_size=19, komi=6.5, rules="japanese"):
        self._config = {
            "game/size": board_size,
            "game/komi": komi,
            "game/rules": rules,
        }

    def log(self, msg, level=None):
        pass  # Discard logs

    def config(self, key, default=None):
        return self._config.get(key, default)


def test_b1_base_game_instantiation():
    """Test B1: BaseGame instantiates with MockKaTrain."""
    from katrain.core.game import BaseGame
    from katrain.core.sgf_parser import Move

    game = BaseGame(MockKaTrain(board_size=19))

    # Play a stone
    move = Move(coords=(3, 3), player="B")
    game.play(move)

    # Verify stone placed
    current = game.current_node
    assert current.move is not None
    assert current.move.coords == (3, 3)
    print("[OK] B1: BaseGame instantiation and play() work")


def test_b2_capture_single_stone():
    """Test B2: Capture a single stone (4-liberty surround)."""
    from katrain.core.game import BaseGame
    from katrain.core.sgf_parser import Move

    game = BaseGame(MockKaTrain(board_size=9))

    # Place W at (1,1), surround with B
    #   0 1 2
    # 0   B
    # 1 B W B
    # 2   B
    game.play(Move(coords=(1, 1), player="W"))
    game.play(Move(coords=(1, 0), player="B"))
    game.play(Move(coords=(0, 1), player="B"))
    game.play(Move(coords=(2, 1), player="B"))
    game.play(Move(coords=(1, 2), player="B"))  # Captures W

    # W stone should be captured
    # stones is a property on BaseGame, not GameNode
    # Returns list of Move objects representing all stones on board
    stones = game.stones
    stone_coords = [(m.coords[0], m.coords[1]) for m in stones if m.coords]
    assert (1, 1) not in stone_coords, f"W stone not captured: {stone_coords}"
    print("[OK] B2: Single stone capture works")


def test_b3_illegal_move_rejection():
    """Test B3: Illegal moves (occupied space) are rejected."""
    from katrain.core.game import BaseGame, IllegalMoveException
    from katrain.core.sgf_parser import Move

    game = BaseGame(MockKaTrain(board_size=9))

    # Place a stone
    game.play(Move(coords=(3, 3), player="B"))

    # Try to play on occupied space - should raise IllegalMoveException
    try:
        game.play(Move(coords=(3, 3), player="W"))
        assert False, "Playing on occupied space should have been rejected"
    except IllegalMoveException as e:
        assert "occupied" in str(e).lower() or "Space" in str(e)
        print("[OK] B3: Illegal move (occupied space) rejected")


def test_b4_sgf_parse():
    """Test B4: SGF parsing works."""
    from katrain.core.sgf_parser import SGF

    sgf_content = "(;GM[1]SZ[19]PB[Black]PW[White];B[pd];W[dp];B[pp])"
    root = SGF.parse_sgf(sgf_content)

    assert root is not None
    # Check metadata
    assert root.get_property("SZ") == "19"
    assert root.get_property("PB") == "Black"
    print("[OK] B4: SGF parsing works")


# =============================================================================
# Main Runner
# =============================================================================


def run_test_suite():
    """Run all tests with clear pass/fail reporting."""
    print("=" * 60)
    print("Phase 3.0 Preflight: Core Importability Tests")
    print("=" * 60)

    # Test A: Import-only
    print("\n--- Test A: Import-Only ---")
    test_a_passed = True
    try:
        test_a1_sgf_parser_import()
        test_a2_move_gtp_coords()
        test_a3_game_import()
        test_a4_game_node_import()
        test_a5_constants_import()
    except Exception as e:
        print(f"[FAIL] Test A FAILED: {e}")
        import traceback

        traceback.print_exc()
        test_a_passed = False

    if not test_a_passed:
        print("\n[X] Test A failed - fix shims/import chain before proceeding")
        print("    Stop/Go: STOP -> fix shims")
        return False

    print("\n[PASS] Test A passed - imports work")

    # Test B: Minimal logic
    print("\n--- Test B: Minimal Logic ---")
    test_b_passed = True
    try:
        test_b1_base_game_instantiation()
        test_b2_capture_single_stone()
        test_b3_illegal_move_rejection()
        test_b4_sgf_parse()
    except Exception as e:
        print(f"[FAIL] Test B FAILED: {e}")
        import traceback

        traceback.print_exc()
        test_b_passed = False

    if not test_b_passed:
        print("\n[X] Test B failed - MockKaTrain or core requirements issue")
        print("    Stop/Go: Fix MockKaTrain or identify missing requirements")
        return False

    print("\n[PASS] Test B passed - core logic works")
    print("\n" + "=" * 60)
    print("All tests passed! Ready for M3.1")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_test_suite()
    sys.exit(0 if success else 1)
