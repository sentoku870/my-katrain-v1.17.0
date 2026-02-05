import copy
import logging
import math
import re
from collections import defaultdict
from typing import Any, Optional

import chardet


class ParseError(Exception):
    """Exception raised on a parse error"""

    pass


class Move:
    GTP_COORD = list("ABCDEFGHJKLMNOPQRSTUVWXYZ") + [
        xa + c for xa in "ABCDEFGH" for c in "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    ]  # board size 52+ support
    PLAYERS = "BW"
    SGF_COORD = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ".lower()) + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")  # sgf goes to 52

    @classmethod
    def from_gtp(cls, gtp_coords: str, player: str = "B") -> "Move":
        """Initialize a move from GTP coordinates and player.

        Args:
            gtp_coords: GTP format coordinate (e.g., "D4", "pass")
            player: Player color ("B" or "W")

        Returns:
            Move instance

        Raises:
            ValueError: If coordinate format is invalid
        """
        if "pass" in gtp_coords.lower():
            return cls(coords=None, player=player)

        match = re.match(r"([A-Z]+)(\d+)", gtp_coords.upper())
        if not match:
            raise ValueError(f"Invalid GTP coordinate format: {gtp_coords!r}")

        col_str, row_str = match.groups()
        try:
            col_idx = Move.GTP_COORD.index(col_str)
        except ValueError:
            raise ValueError(f"Invalid GTP column '{col_str}' in: {gtp_coords!r}")

        row_num = int(row_str) - 1
        if row_num < 0:
            raise ValueError(f"Invalid GTP row '{row_str}' in: {gtp_coords!r}")

        return cls(coords=(col_idx, row_num), player=player)

    @classmethod
    def from_sgf(cls, sgf_coords: str, board_size: tuple[int, int], player: str = "B") -> "Move":
        """Initialize a move from SGF coordinates and player"""
        if sgf_coords == "" or (
            sgf_coords == "tt" and board_size[0] <= 19 and board_size[1] <= 19
        ):  # [tt] can be used as "pass" for <= 19x19 board
            return cls(coords=None, player=player)
        return cls(
            coords=(Move.SGF_COORD.index(sgf_coords[0]), board_size[1] - Move.SGF_COORD.index(sgf_coords[1]) - 1),
            player=player,
        )

    def __init__(self, coords: tuple[int, int] | None = None, player: str = "B"):
        """Initialize a move from zero-based coordinates and player"""
        self.player = player
        self.coords = coords

    def __repr__(self) -> str:
        return f"Move({self.player or ''}{self.gtp()})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Move):
            return NotImplemented
        return self.coords == other.coords and self.player == other.player

    def __hash__(self) -> int:
        return hash((self.coords, self.player))

    def gtp(self) -> str:
        """Returns GTP coordinates of the move"""
        if self.is_pass:
            return "pass"
        assert self.coords is not None
        return Move.GTP_COORD[self.coords[0]] + str(self.coords[1] + 1)

    def sgf(self, board_size: tuple[int, int]) -> str:
        """Returns SGF coordinates of the move"""
        if self.is_pass:
            return ""
        assert self.coords is not None
        return f"{Move.SGF_COORD[self.coords[0]]}{Move.SGF_COORD[board_size[1] - self.coords[1] - 1]}"

    @property
    def is_pass(self) -> bool:
        """Returns True if the move is a pass"""
        return self.coords is None

    @staticmethod
    def opponent_player(player: str) -> str:
        """Returns the opposing player, i.e. W <-> B"""
        return "W" if player == "B" else "B"

    @property
    def opponent(self) -> str:
        """Returns the opposing player, i.e. W <-> B"""
        return self.opponent_player(self.player)


class SGFNode:
    children: list["SGFNode"]
    properties: dict[str, list[Any]]
    moves_cache: list[Move] | None
    _parent: Optional["SGFNode"]
    _root: Optional["SGFNode"]
    _depth: int | None

    def __init__(
        self,
        parent: Optional["SGFNode"] = None,
        properties: dict[str, Any] | None = None,
        move: Move | None = None,
    ) -> None:
        self.children = []
        self.properties = defaultdict(list)
        if properties:
            for k, v in properties.items():
                self.set_property(k, v)
        self.parent = parent
        if self.parent:
            self.parent.children.append(self)
        if parent and move:
            self.set_property(move.player, move.sgf(self.board_size))
        self._clear_cache()

    def _clear_cache(self) -> None:
        self.moves_cache = None

    def __repr__(self) -> str:
        return f"SGFNode({dict(self.properties)})"

    def sgf_properties(self, **xargs: Any) -> dict[str, list[Any]]:
        """For hooking into in a subclass and overriding/formatting any additional properties to be output."""
        return copy.deepcopy(self.properties)

    @staticmethod
    def order_children(children: list["SGFNode"]) -> list["SGFNode"]:
        """For hooking into in a subclass and overriding branch order."""
        return children

    @property
    def ordered_children(self) -> list["SGFNode"]:
        return self.order_children(self.children)

    @staticmethod
    def _escape_value(value: Any) -> Any:
        return re.sub(r"([\]\\])", r"\\\1", value) if isinstance(value, str) else value  # escape \ and ]

    @staticmethod
    def _unescape_value(value: Any) -> Any:
        return re.sub(r"\\([\]\\])", r"\1", value) if isinstance(value, str) else value  # unescape \ and ]

    def sgf(self, **xargs: Any) -> str:
        """Generates an SGF, calling sgf_properties on each node with the given xargs, so it can filter relevant properties if needed."""

        def node_sgf_str(node: "SGFNode") -> str:
            return ";" + "".join(
                [
                    prop + "".join(f"[{self._escape_value(v)}]" for v in values)
                    for prop, values in node.sgf_properties(**xargs).items()
                    if values
                ]
            )

        stack: list[str | SGFNode] = [")", self, "("]
        sgf_str = ""
        while stack:
            item = stack.pop()
            if isinstance(item, str):
                sgf_str += item
            else:
                sgf_str += node_sgf_str(item)
                if len(item.children) == 1:
                    stack.append(item.children[0])
                elif item.children:
                    for c in item.ordered_children[::-1]:
                        stack.extend([")", c, "("])
        return sgf_str

    def add_list_property(self, property: str, values: list[Any]) -> None:
        """Add some values to the property list."""
        # SiZe[19] ==> SZ[19] etc. for old SGF
        normalized_property = re.sub("[a-z]", "", property)
        self._clear_cache()
        self.properties[normalized_property] += values

    def get_list_property(self, property: str, default: Any = None) -> Any:
        """Get the list of values for a property."""
        return self.properties.get(property, default)

    def set_property(self, property: str, value: Any) -> None:
        """Add some values to the property. If not a list, it will be made into a single-value list."""
        if not isinstance(value, list):
            value = [value]
        self._clear_cache()
        self.properties[property] = value

    def get_property(self, property: str, default: Any = None) -> Any:
        """Get the first value of the property, typically when exactly one is expected."""
        return self.properties.get(property, [default])[0]

    def clear_property(self, property: str) -> list[Any] | None:
        """Removes property if it exists."""
        return self.properties.pop(property, None)

    @property
    def parent(self) -> Optional["SGFNode"]:
        """Returns the parent node"""
        return self._parent

    @parent.setter
    def parent(self, parent_node: Optional["SGFNode"]) -> None:
        self._parent = parent_node
        self._root = None
        self._depth = None

    @property
    def root(self) -> "SGFNode":
        """Returns the root of the tree, cached for speed"""
        if self._root is None:
            self._root = self.parent.root if self.parent else self
        return self._root

    @property
    def depth(self) -> int:
        """Returns the depth of this node, where root is 0, cached for speed"""
        if self._depth is None:
            moves = self.moves
            if self.is_root:
                self._depth = 0
            else:  # no increase on placements etc
                assert self.parent is not None
                self._depth = self.parent.depth + len(moves)
        return self._depth

    @property
    def board_size(self) -> tuple[int, int]:
        """Retrieves the root's SZ property, or 19 if missing. Parses it, and returns board size as a tuple x,y"""
        size = str(self.root.get_property("SZ", "19"))
        if ":" in size:
            x, y = map(int, size.split(":"))
        else:
            x = int(size)
            y = x
        return x, y

    @property
    def komi(self) -> float:
        """Retrieves the root's KM property, or 6.5 if missing"""
        try:
            km = float(self.root.get_property("KM", 6.5))
        except ValueError:
            km = 6.5

        return km

    @property
    def handicap(self) -> int:
        try:
            return int(self.root.get_property("HA", 0))
        except ValueError:
            return 0

    @property
    def ruleset(self) -> str:
        """Retrieves the root's RU property, or 'japanese' if missing"""
        return str(self.root.get_property("RU", "japanese"))

    @property
    def moves(self) -> list[Move]:
        """Returns all moves in the node - typically 'move' will be better."""
        if self.moves_cache is None:
            self.moves_cache = [
                Move.from_sgf(move, player=pl, board_size=self.board_size)
                for pl in Move.PLAYERS
                for move in self.get_list_property(pl, [])
            ]
        return self.moves_cache

    def _expanded_placements(self, player: str | None) -> list[Move]:
        sgf_pl = player if player is not None else "E"  # AE
        placements = self.get_list_property("A" + sgf_pl, [])
        if not placements:
            return []
        to_be_expanded = [p for p in placements if ":" in p]
        board_size = self.board_size
        if to_be_expanded:
            coords = {
                Move.from_sgf(sgf_coord, player=player or "B", board_size=board_size)
                for sgf_coord in placements
                if ":" not in sgf_coord
            }
            for p in to_be_expanded:
                from_coord, to_coord = [Move.from_sgf(c, board_size=board_size) for c in p.split(":")[:2]]
                assert from_coord.coords is not None and to_coord.coords is not None
                for x in range(from_coord.coords[0], to_coord.coords[0] + 1):
                    for y in range(to_coord.coords[1], from_coord.coords[1] + 1):  # sgf upside dn
                        if 0 <= x < board_size[0] and 0 <= y < board_size[1]:
                            coords.add(Move((x, y), player=player or "B"))
            return list(coords)
        else:
            return [Move.from_sgf(sgf_coord, player=player or "B", board_size=board_size) for sgf_coord in placements]

    @property
    def placements(self) -> list[Move]:
        """Returns all placements (AB/AW) in the node."""
        return [coord for pl in Move.PLAYERS for coord in self._expanded_placements(pl)]

    @property
    def clear_placements(self) -> list[Move]:
        """Returns all AE clear square commends in the node."""
        return self._expanded_placements(None)

    @property
    def move_with_placements(self) -> list[Move]:
        """Returns all moves (B/W) and placements (AB/AW) in the node."""
        return self.placements + self.moves

    @property
    def move(self) -> Move | None:
        """Returns the single move for the node if one exists, or None if no moves (or multiple ones) exist."""
        moves = self.moves
        if len(moves) == 1:
            return moves[0]
        return None

    @property
    def is_root(self) -> bool:
        """Returns true if node is a root"""
        return self.parent is None

    @property
    def is_pass(self) -> bool:
        """Returns true if associated move is pass"""
        move = self.move
        return not self.placements and move is not None and move.is_pass

    @property
    def empty(self) -> bool:
        """Returns true if node has no children or properties"""
        return not self.children and not self.properties

    @property
    def nodes_in_tree(self) -> list["SGFNode"]:
        """Returns all nodes in the tree rooted at this node"""
        stack: list[SGFNode] = [self]
        nodes: list[SGFNode] = []
        while stack:
            item = stack.pop(0)
            nodes.append(item)
            stack += item.children
        return nodes

    @property
    def nodes_from_root(self) -> list["SGFNode"]:
        """Returns all nodes from the root up to this node, i.e. the moves played in the current branch of the game"""
        nodes: list[SGFNode] = [self]
        n: SGFNode = self
        while not n.is_root:
            assert n.parent is not None
            n = n.parent
            nodes.append(n)
        return nodes[::-1]

    def play(self, move: Move) -> "SGFNode":
        """Either find an existing child or create a new one with the given move."""
        for c in self.children:
            if c.move and c.move == move:
                return c
        return self.__class__(parent=self, move=move)

    @property
    def initial_player(self) -> str:  # player for first node
        root = self.root
        if "PL" in root.properties:  # explicit
            return "B" if self.root.get_property("PL").upper().strip() == "B" else "W"
        elif root.children:  # child exist, use it if not placement
            for child in root.children:
                for color in "BW":
                    if color in child.properties:
                        return color
        # b move or setup with only black moves like handicap
        if "AB" in self.properties and "AW" not in self.properties:
            return "W"
        else:
            return "B"

    @property
    def next_player(self) -> str:
        """Returns player to move"""
        if self.is_root:
            return self.initial_player
        elif "B" in self.properties:
            return "W"
        elif "W" in self.properties:
            return "B"
        else:  # only placements, find a parent node with a real move. TODO: better placement support
            assert self.parent is not None
            return self.parent.next_player

    @property
    def player(self) -> str:
        """Returns player that moved last. nb root is considered white played if no handicap stones are placed"""
        if "B" in self.properties or ("AB" in self.properties and "W" not in self.properties):
            return "B"
        else:
            return "W"

    def place_handicap_stones(self, n_handicaps: int, tygem: bool = False) -> None:
        board_size_x, board_size_y = self.board_size
        if min(board_size_x, board_size_y) < 3:
            return  # No
        near_x = 3 if board_size_x >= 13 else min(2, board_size_x - 1)
        near_y = 3 if board_size_y >= 13 else min(2, board_size_y - 1)
        far_x = board_size_x - 1 - near_x
        far_y = board_size_y - 1 - near_y
        middle_x = board_size_x // 2  # what for even sizes?
        middle_y = board_size_y // 2
        if n_handicaps > 9 and board_size_x == board_size_y:
            stones_per_row = math.ceil(math.sqrt(n_handicaps))
            spacing = (far_x - near_x) / (stones_per_row - 1)
            if spacing < near_x:
                far_x += 1
                near_x -= 1
                spacing = (far_x - near_x) / (stones_per_row - 1)
            coords = list({math.floor(0.5 + near_x + i * spacing) for i in range(stones_per_row)})
            stones = sorted(
                [(x, y) for x in coords for y in coords],
                key=lambda xy: -((xy[0] - (board_size_x - 1) / 2) ** 2 + (xy[1] - (board_size_y - 1) / 2) ** 2),
            )
        else:  # max 9
            stones = [(far_x, far_y), (near_x, near_y), (far_x, near_y), (near_x, far_y)]
            if n_handicaps % 2 == 1:
                stones.append((middle_x, middle_y))
            stones += [(near_x, middle_y), (far_x, middle_y), (middle_x, near_y), (middle_x, far_y)]
        if tygem:
            stones[2], stones[3] = stones[3], stones[2]
        self.set_property(
            "AB", list({Move(stone).sgf(board_size=(board_size_x, board_size_y)) for stone in stones[:n_handicaps]})
        )


class SGF:
    DEFAULT_ENCODING = "UTF-8"

    _NODE_CLASS = SGFNode  # Class used for SGF Nodes, can change this to something that inherits from SGFNode
    # https://xkcd.com/1171/
    SGFPROP_PAT = re.compile(r"\s*(?:\(|\)|;|(\w+)((\s*\[([^\]\\]|\\.)*\])+))", flags=re.DOTALL)
    SGF_PAT = re.compile(r"\(;.*\)", flags=re.DOTALL)

    @classmethod
    def parse_sgf(cls, input_str: str) -> SGFNode:
        """Parse a string as SGF."""
        match = re.search(cls.SGF_PAT, input_str)
        clipped_str = match.group() if match else input_str
        root = cls(clipped_str).root
        # Fix weird FoxGo server KM values
        if "foxwq" in root.get_list_property("AP", []):
            if int(root.get_property("HA", 0)) >= 1:
                corrected_komi = 0.5
            elif root.get_property("RU").lower() in ["chinese", "cn"]:
                corrected_komi = 7.5
            else:
                corrected_komi = 6.5
            root.set_property("KM", corrected_komi)
        return root

    @classmethod
    def parse_file(cls, filename: str, encoding: str | None = None) -> SGFNode:
        """Parse a file as SGF, encoding will be detected if not given."""
        is_gib = filename.lower().endswith(".gib")
        is_ngf = filename.lower().endswith(".ngf")
        with open(filename, "rb") as f:
            bin_contents = f.read()
            if not encoding:
                if is_gib or is_ngf or b"AP[foxwq]" in bin_contents:
                    encoding = "utf8"
                else:  # sgf
                    match = re.search(rb"CA\[(.*?)\]", bin_contents)
                    if match:
                        encoding = match[1].decode("ascii", errors="ignore")
                    else:
                        detected = chardet.detect(bin_contents[:300])["encoding"]
                        # workaround for some compatibility issues for Windows-1252 and GB2312 encodings
                        if detected == "Windows-1252" or detected == "GB2312":
                            encoding = "GBK"
                        elif detected is not None:
                            encoding = detected
                        else:
                            encoding = cls.DEFAULT_ENCODING
            try:
                decoded = bin_contents.decode(encoding=encoding, errors="ignore")
            except LookupError:
                decoded = bin_contents.decode(encoding=cls.DEFAULT_ENCODING, errors="ignore")
            if is_ngf:
                return cls.parse_ngf(decoded)
            if is_gib:
                return cls.parse_gib(decoded)
            else:  # sgf
                return cls.parse_sgf(decoded)

    def __init__(self, contents: str) -> None:
        self.contents = contents
        try:
            self.ix = self.contents.index("(") + 1
        except ValueError:
            raise ParseError(f"Parse error: Expected '(' at start, found {self.contents[:50]}")
        self.root = self._NODE_CLASS()
        self._parse_branch(self.root)

    def _parse_branch(self, current_move: SGFNode) -> None:
        while self.ix < len(self.contents):
            match = re.match(self.SGFPROP_PAT, self.contents[self.ix :])
            if not match:
                break
            self.ix += len(match[0])
            matched_item = match[0].strip()
            if matched_item == ")":
                return
            if matched_item == "(":
                self._parse_branch(self._NODE_CLASS(parent=current_move))
            elif matched_item == ";":
                # ignore ;) for old SGF
                useless = self.ix < len(self.contents) and self.contents[self.ix :].strip() == ")"
                # ignore ; that generate empty nodes
                if not (current_move.empty or useless):
                    current_move = self._NODE_CLASS(parent=current_move)
            else:
                property, value = match[1], match[2].strip()[1:-1]
                values = re.split(r"\]\s*\[", value)
                current_move.add_list_property(property, [SGFNode._unescape_value(v) for v in values])
        if self.ix < len(self.contents):
            raise ParseError(f"Parse Error: unexpected character at {self.contents[self.ix : self.ix + 25]}")
        raise ParseError("Parse Error: expected ')' at end of input.")

    # NGF parser adapted from https://github.com/fohristiwhirl/gofish/
    @classmethod
    def parse_ngf(cls, ngf: str) -> SGFNode:
        ngf = ngf.strip()
        lines = ngf.split("\n")

        try:
            boardsize = int(lines[1])
            handicap = int(lines[5])
            pw = lines[2].split()[0]
            pb = lines[3].split()[0]
            rawdate = lines[8][0:8]
            komi = float(lines[7])

            if handicap == 0 and int(komi) == komi:
                komi += 0.5

        except (IndexError, ValueError):
            boardsize = 19
            handicap = 0
            pw = ""
            pb = ""
            rawdate = ""
            komi = 0

        re = ""
        try:
            if "hite win" in lines[10]:
                re = "W+"
            elif "lack win" in lines[10]:
                re = "B+"
        except IndexError:
            pass

        if handicap < 0 or handicap > 9:
            raise ParseError(f"Handicap {handicap} out of range")

        root = cls._NODE_CLASS()
        node = root

        # Set root values...

        root.set_property("SZ", boardsize)

        if handicap >= 2:
            root.set_property("HA", handicap)
            root.place_handicap_stones(handicap, tygem=True)  # While this isn't Tygem, it uses the same layout

        if komi:
            root.set_property("KM", komi)

        if len(rawdate) == 8:
            ok = True
            for n in range(8):
                if rawdate[n] not in "0123456789":
                    ok = False
            if ok:
                date = rawdate[0:4] + "-" + rawdate[4:6] + "-" + rawdate[6:8]
                root.set_property("DT", date)

        if pw:
            root.set_property("PW", pw)
        if pb:
            root.set_property("PB", pb)

        if re:
            root.set_property("RE", re)

        # Main parser...

        for line in lines:
            line = line.strip().upper()

            if len(line) >= 7 and line[0:2] == "PM" and line[4] in ["B", "W"]:
                # move format is similar to SGF, but uppercase and out-by-1

                key = line[4]
                raw_move = line[5:7].lower()
                if raw_move == "aa":
                    value = ""  # pass
                else:
                    value = chr(ord(raw_move[0]) - 1) + chr(ord(raw_move[1]) - 1)

                node = cls._NODE_CLASS(parent=node)
                node.set_property(key, value)

        if len(root.children) == 0:  # We'll assume we failed in this case
            raise ParseError("Found no moves")

        return root

    # GIB parser adapted from https://github.com/fohristiwhirl/gofish/
    @classmethod
    def parse_gib(cls, gib: str) -> SGFNode:
        def parse_player_name(raw: str) -> tuple[str, str]:
            name = raw
            rank = ""
            foo = raw.split("(")
            if len(foo) == 2 and foo[1][-1] == ")":
                name = foo[0].strip()
                rank = foo[1][0:-1]
            return name, rank

        def gib_make_result(grlt: int, zipsu: int) -> str:
            easycases = {3: "B+R", 4: "W+R", 7: "B+T", 8: "W+T"}

            if grlt in easycases:
                return easycases[grlt]

            if grlt in [0, 1]:
                return "{}+{}".format("B" if grlt == 0 else "W", zipsu / 10)

            return ""

        def gib_get_result(line: str, grlt_regex: str, zipsu_regex: str) -> str:
            try:
                grlt_match = re.search(grlt_regex, line)
                zipsu_match = re.search(zipsu_regex, line)
                if grlt_match is None or zipsu_match is None:
                    return ""
                grlt = int(grlt_match.group(1))
                zipsu = int(zipsu_match.group(1))
            except (ValueError, TypeError):
                # int() can raise ValueError (non-numeric) or TypeError (None)
                return ""
            return gib_make_result(grlt, zipsu)

        root = cls._NODE_CLASS()
        node = root

        lines = gib.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("\\[GAMEBLACKNAME=") and line.endswith("\\]"):
                s = line[16:-2]
                name, rank = parse_player_name(s)
                if name:
                    root.set_property("PB", name)
                if rank:
                    root.set_property("BR", rank)

            if line.startswith("\\[GAMEWHITENAME=") and line.endswith("\\]"):
                s = line[16:-2]
                name, rank = parse_player_name(s)
                if name:
                    root.set_property("PW", name)
                if rank:
                    root.set_property("WR", rank)

            if line.startswith("\\[GAMEINFOMAIN="):
                result = gib_get_result(line, r"GRLT:(\d+),", r"ZIPSU:(\d+),")
                if result:
                    root.set_property("RE", result)
                    try:
                        komi_match = re.search(r"GONGJE:(\d+),", line)
                        if komi_match is not None:
                            komi = int(komi_match.group(1)) / 10
                            if komi:
                                root.set_property("KM", komi)
                    except ValueError as e:
                        # Control-flow: komi extraction is optional metadata.
                        # ValueError: matched text wasn't a valid integer
                        # Unexpected exceptions propagate (operation is limited)
                        logging.debug(f"GIB komi extraction skipped (GAMEINFOMAIN): {e}")

            if line.startswith("\\[GAMETAG="):
                if "DT" not in root.properties:
                    date_match = re.search(r"C(\d\d\d\d):(\d\d):(\d\d)", line)
                    if date_match is not None:
                        date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                        root.set_property("DT", date)

                if "RE" not in root.properties:
                    result = gib_get_result(line, r",W(\d+),", r",Z(\d+),")
                    if result:
                        root.set_property("RE", result)

                if "KM" not in root.properties:
                    try:
                        komi_match = re.search(r",G(\d+),", line)
                        if komi_match is not None:
                            komi = int(komi_match.group(1)) / 10
                            if komi:
                                root.set_property("KM", komi)
                    except ValueError as e:
                        # Control-flow: komi extraction is optional metadata.
                        # ValueError: matched text wasn't a valid integer
                        # Unexpected exceptions propagate (operation is limited)
                        logging.debug(f"GIB komi extraction skipped (GAMETAG): {e}")

            if line[0:3] == "INI":
                if node is not root:
                    raise ParseError("Node is not root")
                setup = line.split()
                try:
                    handicap = int(setup[3])
                except ParseError:
                    continue

                if handicap < 0 or handicap > 9:
                    raise ParseError(f"Handicap {handicap} out of range")

                if handicap >= 2:
                    root.set_property("HA", handicap)
                    root.place_handicap_stones(handicap, tygem=True)

            if line[0:3] == "STO":
                move = line.split()
                key = "B" if move[3] == "1" else "W"
                try:
                    x = int(move[4])
                    y = 18 - int(move[5])
                    if not (0 <= x < 19 and 0 <= y < 19):
                        raise ParseError(f"Coordinates for move ({x},{y}) out of range on line {line}")
                    value = Move(coords=(x, y)).sgf(board_size=(19, 19))
                except IndexError:
                    continue

                node = cls._NODE_CLASS(parent=node)
                node.set_property(key, value)

        if len(root.children) == 0:  # We'll assume we failed in this case
            raise ParseError("No valid nodes found")

        return root
