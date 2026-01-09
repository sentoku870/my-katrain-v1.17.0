"""
GameAdapter - Qt wrapper around KaTrain's BaseGame.

Provides a clean interface for the Qt frontend to interact with
KaTrain core game logic (SGF loading, navigation, board state).

Coordinate System:
- KaTrain core uses (col, row) where:
  - col: 0..size-1 (left to right)
  - row: 0 at BOTTOM (GTP convention), size-1 at TOP
- Qt rendering uses row=0 at TOP
- This adapter converts: qt_row = board_size - 1 - core_row

Usage:
    from katrain_qt.core_adapter import GameAdapter
    adapter = GameAdapter()
    adapter.load_sgf_file("game.sgf")
"""

from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

# Import KaTrain core (shims must be installed before this)
from katrain.core.sgf_parser import SGF, Move
from katrain.core.game import BaseGame, KaTrainSGF, IllegalMoveException
from katrain.core.game_node import GameNode


class MockKaTrain:
    """
    Minimal mock for BaseGame instantiation.

    BaseGame requires:
      - katrain.log(msg, level)
      - katrain.config(key) for game/size, game/komi, game/rules
    """

    def __init__(self, board_size: int = 19, komi: float = 6.5, rules: str = "japanese"):
        self._config = {
            "game/size": board_size,
            "game/komi": komi,
            "game/rules": rules,
        }

    def log(self, msg, level=None):
        pass  # Discard logs

    def config(self, key, default=None):
        return self._config.get(key, default)


class GameAdapter(QObject):
    """
    Qt wrapper around KaTrain's BaseGame.

    Translates between KaTrain core and Qt signals.
    Handles coordinate conversion between core (row=0 at bottom)
    and Qt rendering (row=0 at top).

    Signals:
        position_changed: Emitted when board state changes (navigation, load)
        status_changed(str): Emitted with status messages
        error_occurred(str): Emitted on errors
    """

    position_changed = Signal()
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._game: Optional[BaseGame] = None
        self._mock_katrain = MockKaTrain()

    # -------------------------------------------------------------------------
    # Game Lifecycle
    # -------------------------------------------------------------------------

    def new_game(self, size: int = 19, komi: float = 6.5, rules: str = "japanese"):
        """Start a new empty game."""
        self._mock_katrain = MockKaTrain(board_size=size, komi=komi, rules=rules)
        self._game = BaseGame(self._mock_katrain)
        self.status_changed.emit(f"New {size}x{size} game")
        self.position_changed.emit()

    def load_sgf_file(self, path: str) -> bool:
        """
        Load SGF from file path.

        Returns True on success, False on error.
        """
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                self.error_occurred.emit(f"File not found: {path}")
                return False

            # Parse SGF using KaTrain's parser (KaTrainSGF uses GameNode, not SGFNode)
            root_node = KaTrainSGF.parse_file(str(path_obj))

            # Get board size from SGF
            size_x, size_y = root_node.board_size
            if size_x != size_y:
                self.error_occurred.emit(f"Non-square boards not supported: {size_x}x{size_y}")
                return False

            # Create game with the parsed tree
            self._mock_katrain = MockKaTrain(
                board_size=size_x,
                komi=root_node.komi,
                rules=root_node.get_property("RU", "japanese"),
            )
            self._game = BaseGame(
                self._mock_katrain,
                move_tree=root_node,
                sgf_filename=str(path_obj),
            )

            self.status_changed.emit(f"Loaded: {path_obj.name}")
            self.position_changed.emit()
            return True

        except Exception as e:
            self.error_occurred.emit(f"Error loading SGF: {e}")
            return False

    def load_sgf_string(self, content: str) -> bool:
        """
        Load SGF from string content.

        Returns True on success, False on error.
        """
        try:
            root_node = KaTrainSGF.parse_sgf(content)
            size_x, size_y = root_node.board_size
            if size_x != size_y:
                self.error_occurred.emit(f"Non-square boards not supported: {size_x}x{size_y}")
                return False

            self._mock_katrain = MockKaTrain(
                board_size=size_x,
                komi=root_node.komi,
                rules=root_node.get_property("RU", "japanese"),
            )
            self._game = BaseGame(
                self._mock_katrain,
                move_tree=root_node,
            )

            self.status_changed.emit("SGF loaded")
            self.position_changed.emit()
            return True

        except Exception as e:
            self.error_occurred.emit(f"Error parsing SGF: {e}")
            return False

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def nav_first(self) -> bool:
        """Go to initial position (root). Returns True if moved."""
        if not self._game:
            return False
        if self._game.current_node.is_root:
            return False
        self._game.set_current_node(self._game.root)
        self.position_changed.emit()
        return True

    def nav_prev(self) -> bool:
        """Go to previous move. Returns True if moved."""
        if not self._game:
            return False
        if self._game.current_node.is_root:
            return False
        self._game.undo(n_times=1)
        self.position_changed.emit()
        return True

    def nav_next(self) -> bool:
        """Go to next move (main line). Returns True if moved."""
        if not self._game:
            return False
        cn = self._game.current_node
        if not cn.children:
            return False
        # Move to first (main line) child
        self._game.redo(n_times=1)
        self.position_changed.emit()
        return True

    def nav_last(self) -> bool:
        """Go to last move (end of main line). Returns True if moved."""
        if not self._game:
            return False
        cn = self._game.current_node
        if not cn.children:
            return False
        # Navigate to end of main line
        self._game.redo(n_times=9999)
        self.position_changed.emit()
        return True

    def nav_to_move(self, move_number: int) -> bool:
        """Go to specific move number. Returns True if valid."""
        if not self._game:
            return False

        current = self.current_move_number
        if move_number == current:
            return False

        if move_number < current:
            # Go back
            self._game.undo(n_times=current - move_number)
        else:
            # Go forward
            self._game.redo(n_times=move_number - current)

        self.position_changed.emit()
        return True

    # -------------------------------------------------------------------------
    # Playing Moves
    # -------------------------------------------------------------------------

    def play_move_qt(self, qt_col: int, qt_row: int) -> Tuple[bool, str]:
        """
        Attempt to play a move at the given Qt coordinates.

        Args:
            qt_col: Column (0..size-1, left to right)
            qt_row: Row (0..size-1, 0 at TOP)

        Returns:
            (success, message) tuple.
            success: True if move was played, False if illegal.
            message: Description of result (e.g., "Black D16" or "Illegal: Ko")
        """
        if not self._game:
            return (False, "No game loaded")

        # Convert Qt coords (row=0 at top) to core coords (row=0 at bottom)
        board_size = self.board_size
        core_col = qt_col
        core_row = board_size - 1 - qt_row

        # Determine current player
        player = self.next_player

        # Create move
        move = Move(coords=(core_col, core_row), player=player)

        try:
            self._game.play(move)
            # Success - format message
            gtp_coord = move.gtp()
            player_name = "Black" if player == "B" else "White"
            self.position_changed.emit()
            return (True, f"{player_name} {gtp_coord}")
        except IllegalMoveException as e:
            reason = str(e)
            return (False, f"Illegal: {reason}")

    def play_pass(self) -> Tuple[bool, str]:
        """
        Play a pass move.

        Returns:
            (success, message) tuple.
        """
        if not self._game:
            return (False, "No game loaded")

        player = self.next_player
        move = Move(coords=None, player=player)  # coords=None means pass

        try:
            self._game.play(move)
            player_name = "Black" if player == "B" else "White"
            self.position_changed.emit()
            return (True, f"{player_name} passed")
        except IllegalMoveException as e:
            # Pass should never be illegal, but handle just in case
            return (False, f"Pass failed: {e}")

    def is_last_move_pass(self) -> bool:
        """Check if the last move was a pass."""
        if not self._game:
            return False
        cn = self._game.current_node
        if cn.is_root or not cn.move:
            return False
        return cn.move.is_pass

    # -------------------------------------------------------------------------
    # Board State Properties
    # -------------------------------------------------------------------------

    def get_stones(self) -> Dict[Tuple[int, int], str]:
        """
        Get current stone positions.

        Returns: {(col, row): "B" or "W"}

        Coordinates are in Qt convention:
          - col: 0..size-1 (left to right)
          - row: 0 at TOP, size-1 at BOTTOM
        """
        if not self._game:
            return {}

        stones = {}
        board_size = self.board_size

        # game.stones returns list of Move objects
        for move in self._game.stones:
            if move.coords:
                core_col, core_row = move.coords
                # Convert from KaTrain (row=0 at bottom) to Qt (row=0 at top)
                qt_row = board_size - 1 - core_row
                stones[(core_col, qt_row)] = move.player

        return stones

    def get_last_move(self) -> Optional[Tuple[int, int, str]]:
        """
        Get last move coordinates and player.

        Returns: (col, row, player) in Qt coordinates, or None if at root/pass.
        """
        if not self._game:
            return None

        cn = self._game.current_node
        if cn.is_root or not cn.move or cn.move.is_pass:
            return None

        core_col, core_row = cn.move.coords
        qt_row = self.board_size - 1 - core_row
        return (core_col, qt_row, cn.move.player)

    @property
    def board_size(self) -> int:
        """Board size (assumes square board)."""
        if not self._game:
            return 19
        size_x, size_y = self._game.board_size
        return size_x

    @property
    def next_player(self) -> str:
        """Next player to move: 'B' or 'W'."""
        if not self._game:
            return "B"
        cn = self._game.current_node
        if cn.move:
            return cn.move.opponent
        # At root, check if there are placements or use default
        return cn.next_player if hasattr(cn, 'next_player') else "B"

    @property
    def current_move_number(self) -> int:
        """Current move number (0 = initial position)."""
        if not self._game:
            return 0
        # nodes_from_root includes root, so length - 1 = move number
        return len(self._game.current_node.nodes_from_root) - 1

    @property
    def total_moves(self) -> int:
        """Total moves in main line."""
        if not self._game:
            return 0
        # Count nodes in main line from root
        count = 0
        node = self._game.root
        while node.children:
            count += 1
            node = node.children[0]  # Main line
        return count

    @property
    def komi(self) -> float:
        """Game komi."""
        if not self._game:
            return 6.5
        return self._game.komi

    @property
    def rules(self) -> str:
        """Game rules."""
        if not self._game:
            return "japanese"
        return self._game.root.get_property("RU", "japanese")

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------

    @property
    def black_player(self) -> str:
        """Black player name from SGF."""
        if not self._game:
            return ""
        return self._game.root.get_property("PB", "")

    @property
    def white_player(self) -> str:
        """White player name from SGF."""
        if not self._game:
            return ""
        return self._game.root.get_property("PW", "")

    @property
    def result(self) -> str:
        """Game result from SGF (e.g., 'B+R', 'W+3.5')."""
        if not self._game:
            return ""
        return self._game.root.get_property("RE", "")

    @property
    def date(self) -> str:
        """Game date from SGF."""
        if not self._game:
            return ""
        return self._game.root.get_property("DT", "")

    def is_loaded(self) -> bool:
        """Check if a game is loaded."""
        return self._game is not None

    # -------------------------------------------------------------------------
    # Analysis Integration
    # -------------------------------------------------------------------------

    def get_position_snapshot(self):
        """
        Get current position as PositionSnapshot for KataGo query.

        Returns: PositionSnapshot with stones in Qt coordinates, next_player, komi.
        Returns None if no game is loaded.
        """
        if not self._game:
            return None

        # Import here to avoid circular dependency
        from katrain_qt.analysis.models import PositionSnapshot

        return PositionSnapshot(
            stones=dict(self.get_stones()),  # Already in Qt coords
            next_player=self.next_player,
            board_size=self.board_size,
            komi=self.komi,
        )

    # -------------------------------------------------------------------------
    # SGF Save
    # -------------------------------------------------------------------------

    def save_sgf(self, path: str) -> bool:
        """
        Save current game to SGF file.

        Args:
            path: File path to save to (UTF-8 encoding)

        Returns:
            True on success, False on error.

        Note:
            Saves basic SGF without KaTrain-specific analysis feedback.
            Uses the core's root.sgf() method for serialization.
        """
        if not self._game:
            self.error_occurred.emit("No game to save")
            return False

        try:
            # Ensure parent directory exists
            path_obj = Path(path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Get SGF string from root node
            sgf_content = self._game.root.sgf()

            # Write with UTF-8 encoding
            with open(path_obj, "w", encoding="utf-8") as f:
                f.write(sgf_content)

            self.status_changed.emit(f"Saved: {path_obj.name}")
            return True

        except OSError as e:
            self.error_occurred.emit(f"Error saving SGF: {e}")
            return False
        except Exception as e:
            self.error_occurred.emit(f"Unexpected error saving SGF: {e}")
            return False

    @property
    def current_node_id(self) -> int:
        """
        Get unique identifier for current node.

        Returns Python object id of the current GameNode.
        Useful for caching analysis per-node (handles variations correctly).
        """
        if not self._game:
            return 0
        return id(self._game.current_node)

    # -------------------------------------------------------------------------
    # Variation Support (M5.1a)
    # -------------------------------------------------------------------------

    def has_variations(self) -> bool:
        """
        Check if current node has multiple children (variations).

        Returns: True if there are 2+ children at current node.
        """
        if not self._game:
            return False
        return len(self._game.current_node.children) > 1

    def get_child_variations(self):
        """
        Get list of child variations at current node.

        Returns: List of tuples (index, move_gtp, player)
            - index: Child index (0 = main line)
            - move_gtp: GTP coordinate string (e.g., "D4") or "pass"
            - player: "B" or "W"

        Returns empty list if no game loaded or no children.
        """
        if not self._game:
            return []

        children = self._game.current_node.ordered_children
        result = []

        for i, child in enumerate(children):
            if child.move:
                move_gtp = child.move.gtp() if child.move.coords else "pass"
                player = child.move.player
            else:
                # Setup node or root - no move
                move_gtp = ""
                player = ""
            result.append((i, move_gtp, player))

        return result

    def switch_to_child(self, child_index: int) -> bool:
        """
        Switch to a specific child variation.

        Args:
            child_index: Index of child to switch to (0 = main line)

        Returns: True if successfully switched, False otherwise.
        """
        if not self._game:
            return False

        children = self._game.current_node.ordered_children
        if child_index < 0 or child_index >= len(children):
            return False

        self._game.set_current_node(children[child_index])
        self.position_changed.emit()
        return True

    def get_current_variation_index(self) -> int:
        """
        Get index of current node among its siblings.

        Returns: Index of current node in parent's children list.
            Returns 0 if at root or no parent.
        """
        if not self._game:
            return 0

        cn = self._game.current_node
        if cn.is_root or not cn.parent:
            return 0

        siblings = cn.parent.ordered_children
        for i, sibling in enumerate(siblings):
            if sibling is cn:
                return i
        return 0

    def get_sibling_count(self) -> int:
        """
        Get number of sibling variations (including current node).

        Returns: Number of children at parent node.
            Returns 1 if at root.
        """
        if not self._game:
            return 1

        cn = self._game.current_node
        if cn.is_root or not cn.parent:
            return 1

        return len(cn.parent.children)

    def switch_to_sibling(self, sibling_index: int) -> bool:
        """
        Switch to a sibling variation (same parent, different child).

        Args:
            sibling_index: Index of sibling to switch to

        Returns: True if successfully switched, False otherwise.
        """
        if not self._game:
            return False

        cn = self._game.current_node
        if cn.is_root or not cn.parent:
            return False

        siblings = cn.parent.ordered_children
        if sibling_index < 0 or sibling_index >= len(siblings):
            return False

        target = siblings[sibling_index]
        if target is cn:
            return False  # Already at this sibling

        self._game.set_current_node(target)
        self.position_changed.emit()
        return True

    def nav_next_variation(self) -> bool:
        """
        Navigate to next sibling variation (cyclic).

        Returns: True if navigated, False otherwise.
        """
        if not self._game:
            return False

        cn = self._game.current_node
        if cn.is_root or not cn.parent:
            return False

        siblings = cn.parent.ordered_children
        if len(siblings) <= 1:
            return False

        current_idx = self.get_current_variation_index()
        next_idx = (current_idx + 1) % len(siblings)
        return self.switch_to_sibling(next_idx)

    def nav_prev_variation(self) -> bool:
        """
        Navigate to previous sibling variation (cyclic).

        Returns: True if navigated, False otherwise.
        """
        if not self._game:
            return False

        cn = self._game.current_node
        if cn.is_root or not cn.parent:
            return False

        siblings = cn.parent.ordered_children
        if len(siblings) <= 1:
            return False

        current_idx = self.get_current_variation_index()
        prev_idx = (current_idx - 1) % len(siblings)
        return self.switch_to_sibling(prev_idx)

    # -------------------------------------------------------------------------
    # Comment Support (M5.1b)
    # -------------------------------------------------------------------------

    def get_comment(self) -> str:
        """
        Get comment text for current node.

        KaTrain stores comments in the 'note' attribute, not the 'C' property.
        The 'C' property is processed during SGF loading and stored in 'note'.

        Returns: Comment string, or empty string if no comment.
        """
        if not self._game:
            return ""
        return self._game.current_node.note or ""

    def set_comment(self, text: str) -> bool:
        """
        Set comment text for current node.

        Updates the 'note' attribute which is serialized to 'C' property on save.

        Args:
            text: Comment text (empty string to clear)

        Returns: True if comment was changed, False otherwise.
        """
        if not self._game:
            return False

        cn = self._game.current_node
        current = cn.note or ""
        text = text or ""

        if text == current:
            return False  # No change

        cn.note = text
        return True

    def has_comment(self) -> bool:
        """
        Check if current node has a comment.

        Returns: True if comment exists and is non-empty.
        """
        if not self._game:
            return False
        note = self._game.current_node.note
        return bool(note and note.strip())
