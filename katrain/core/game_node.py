import base64
import binascii
import copy
import gzip
import json
import random
from typing import Any

from katrain.core.constants import (
    ANALYSIS_FORMAT_VERSION,
    PROGRAM_NAME,
    REPORT_DT,
    SGF_INTERNAL_COMMENTS_MARKER,
    SGF_SEPARATOR_MARKER,
    VERSION,
    PRIORITY_DEFAULT,
    ADDITIONAL_MOVE_ORDER,
)
from katrain.common import INFO_PV_COLOR
from katrain.core.lang import i18n
from katrain.core.sgf_parser import Move, SGFNode
from katrain.core.utils import evaluation_class, pack_floats, unpack_floats, var_to_grid


def analysis_dumps(analysis: dict[str, Any]) -> list[str]:
    analysis = copy.deepcopy(analysis)
    for movedict in analysis["moves"].values():
        if "ownership" in movedict:  # per-move ownership rarely used
            del movedict["ownership"]
    ownership_data = pack_floats(analysis.pop("ownership"))
    policy_data = pack_floats(analysis.pop("policy"))
    main_data = json.dumps(analysis).encode("utf-8")
    return [
        base64.standard_b64encode(gzip.compress(data)).decode("utf-8")
        for data in [ownership_data, policy_data, main_data]
    ]


class GameNode(SGFNode):
    """Represents a single game node, with one or more moves and placements."""

    # Class-level type annotations for instance variables
    auto_undo: bool | None
    played_mistake_sound: bool | None
    ai_thoughts: str
    note: str
    move_number: int
    time_used: float
    undo_threshold: float
    end_state: Any
    shortcuts_to: list[tuple["GameNode", "GameNode"]]
    shortcut_from: "GameNode | None"
    analysis_from_sgf: list[str | None]
    analysis: dict[str, Any]
    analysis_visits_requested: int
    _leela_analysis: Any

    def __init__(
        self,
        parent: "GameNode | None" = None,
        properties: dict[str, list[Any | None]] = None,
        move: Move | None = None,
    ) -> None:
        super().__init__(parent=parent, properties=properties, move=move)
        self.auto_undo = None  # None = not analyzed. False: not undone (good move). True: undone (bad move)
        self.played_mistake_sound = None
        self.ai_thoughts = ""
        self.note = ""
        self.move_number = 0
        self.time_used = 0
        self.undo_threshold = random.random()  # for fractional undos
        self.end_state = None
        self.shortcuts_to = []
        self.shortcut_from = None
        self.analysis_from_sgf = None
        self.clear_analysis()

    def add_shortcut(self, to_node: "GameNode") -> None:  # collapses the branch between them
        nodes: list[GameNode] = [to_node]
        while nodes[-1].parent and nodes[-1] != self:  # ensure on path
            parent = nodes[-1].parent
            assert isinstance(parent, GameNode)
            nodes.append(parent)
        if nodes[-1] == self and len(nodes) > 2:
            via = nodes[-2]
            self.shortcuts_to.append((to_node, via))  # and first child
            to_node.shortcut_from = self

    def remove_shortcut(self) -> None:
        from_node = self.shortcut_from
        if from_node:
            from_node.shortcuts_to = [(m, v) for m, v in from_node.shortcuts_to if m != self]
            self.shortcut_from = None

    def load_analysis(self) -> bool:
        if not self.analysis_from_sgf:
            return False
        try:
            szx, szy = self.root.board_size
            board_squares = szx * szy
            version = self.root.get_property("KTV", ANALYSIS_FORMAT_VERSION)
            if version > ANALYSIS_FORMAT_VERSION:
                raise ValueError(f"Can not decode analysis data with version {version}, please update {PROGRAM_NAME}")
            ownership_data, policy_data, main_data, *_ = [
                gzip.decompress(base64.standard_b64decode(data)) for data in self.analysis_from_sgf
            ]
            self.analysis = {
                **json.loads(main_data),
                "policy": unpack_floats(policy_data, board_squares + 1),
                "ownership": unpack_floats(ownership_data, board_squares),
            }
            return True
        except (gzip.BadGzipFile, binascii.Error, json.JSONDecodeError, KeyError, ValueError) as e:
            # Specific exceptions for SGF analysis deserialization failures
            print(f"Error in loading analysis: {e}")
            return False

    def add_list_property(self, property: str, values: list[Any]) -> None:
        if property == "KT":
            self.analysis_from_sgf = values
        elif property == "C":
            comments = [  # strip out all previously auto generated comments
                c
                for v in values
                for c in v.split(SGF_SEPARATOR_MARKER)
                if c.strip() and SGF_INTERNAL_COMMENTS_MARKER not in c
            ]
            self.note = "".join(comments).strip()  # no super call intended, just save as note to be editable
        else:
            return super().add_list_property(property, values)

    def clear_analysis(self) -> None:
        self.analysis_visits_requested = 0
        self.analysis = {"moves": {}, "root": None, "ownership": None, "policy": None, "completed": False}
        # Leela analysis (separate from KataGo)
        self._leela_analysis = None

    # Leela analysis support (Phase 14)
    @property
    def leela_analysis(self) -> Any:
        """Leela analysis result (separate from KataGo's analysis).

        Returns:
            LeelaPositionEval or None if not analyzed.
        """
        return getattr(self, "_leela_analysis", None)

    def set_leela_analysis(self, eval_result: Any) -> None:
        """Set Leela analysis result.

        Args:
            eval_result: LeelaPositionEval from Leela engine.

        Note: Call from UI thread.
        """
        self._leela_analysis = eval_result

    def clear_leela_analysis(self) -> None:
        """Clear Leela analysis result."""
        self._leela_analysis = None

    def sgf_properties(  # type: ignore[override]
        self,
        save_comments_player: dict[str, bool | None] = None,
        save_comments_class: list[bool | None] = None,
        eval_thresholds: list[float | None] = None,
        save_analysis: bool = False,
        save_marks: bool = False,
    ) -> dict[str, list[Any]]:
        properties = copy.copy(super().sgf_properties())
        note = self.note.strip()
        if save_analysis and self.analysis_complete:
            try:
                properties["KT"] = analysis_dumps(self.analysis)
            except (gzip.BadGzipFile, binascii.Error, json.JSONDecodeError, KeyError, ValueError) as e:
                # Specific exceptions for SGF analysis serialization failures
                print(f"Error in saving analysis: {e}")
        if self.points_lost and save_comments_class is not None and eval_thresholds is not None:
            show_class = save_comments_class[evaluation_class(self.points_lost, eval_thresholds)]
        else:
            show_class = False
        comments = properties.get("C", [])
        parent = self.parent
        if (
            parent
            and isinstance(parent, GameNode)
            and parent.analysis_exists
            and self.analysis_exists
            and (note or ((save_comments_player or {}).get(self.player, False) and show_class))
        ):
            if save_marks:
                candidate_moves = parent.candidate_moves
                if candidate_moves:
                    top_x = Move.from_gtp(candidate_moves[0]["move"]).sgf(self.board_size)
                    best_sq = [
                        Move.from_gtp(d["move"]).sgf(self.board_size)
                        for d in candidate_moves
                        if d["pointsLost"] <= 0.5 and d["move"] != "pass" and d["order"] != 0
                    ]
                    if best_sq and "SQ" not in properties:
                        properties["SQ"] = best_sq
                    if top_x and "MA" not in properties:
                        properties["MA"] = [top_x]
            comments.append("\n" + self.comment(sgf=True, interactive=False) + SGF_INTERNAL_COMMENTS_MARKER)
        if self.is_root:
            if save_marks:
                comments = [i18n._("SGF start message") + SGF_INTERNAL_COMMENTS_MARKER + "\n"]
            else:
                comments = []
            comments += [
                *comments,
                f"\nSGF generated by {PROGRAM_NAME} {VERSION}{SGF_INTERNAL_COMMENTS_MARKER}\n",
            ]
            properties["CA"] = ["UTF-8"]
            properties["AP"] = [f"{PROGRAM_NAME}:{VERSION}"]
            properties["KTV"] = [ANALYSIS_FORMAT_VERSION]
        if self.shortcut_from:
            properties["KTSF"] = [id(self.shortcut_from)]
        elif "KTSF" in properties:
            del properties["KTSF"]
        if self.shortcuts_to:
            properties["KTSID"] = [id(self)]
        elif "KTSID" in properties:
            del properties["KTSID"]
        if note:
            comments.insert(0, f"{self.note}\n")  # user notes at top!
        if comments:
            properties["C"] = [SGF_SEPARATOR_MARKER.join(comments).strip("\n")]
        elif "C" in properties:
            del properties["C"]
        return properties

    @staticmethod
    def order_children(children: list["GameNode"]) -> list["GameNode"]:  # type: ignore[override]
        return sorted(
            children, key=lambda c: 0.5 if c.auto_undo is None else int(c.auto_undo)
        )  # analyzed/not undone main, non-teach second, undone last

    # various analysis functions
    def analyze(
        self,
        engine: Any,
        priority: int = PRIORITY_DEFAULT,
        visits: int | None = None,
        ponder: bool = False,
        time_limit: bool = True,
        refine_move: Move | None = None,
        analyze_fast: bool = False,
        find_alternatives: bool = False,
        region_of_interest: Any = None,
        report_every: float = REPORT_DT,
    ) -> None:
        engine.request_analysis(
            self,
            callback=lambda result, partial_result: self.set_analysis(
                result, refine_move, find_alternatives, region_of_interest, partial_result
            ),
            priority=priority,
            visits=visits,
            ponder=ponder,
            analyze_fast=analyze_fast,
            time_limit=time_limit,
            next_move=refine_move,
            find_alternatives=find_alternatives,
            region_of_interest=region_of_interest,
            report_every=report_every,
        )

    def update_move_analysis(self, move_analysis: dict[str, Any], move_gtp: str) -> None:
        cur = self.analysis["moves"].get(move_gtp)
        if cur is None:
            self.analysis["moves"][move_gtp] = {
                "move": move_gtp,
                "order": ADDITIONAL_MOVE_ORDER,
                **move_analysis,
            }  # some default values for keys missing in rootInfo
        else:
            cur["order"] = min(
                cur["order"], move_analysis.get("order", ADDITIONAL_MOVE_ORDER)
            )  # parent arriving after child
            if cur["visits"] < move_analysis["visits"]:
                cur.update(move_analysis)
            else:  # prior etc only
                cur.update({k: v for k, v in move_analysis.items() if k not in cur})

    def set_analysis(
        self,
        analysis_json: dict[str, Any],
        refine_move: Move | None = None,
        additional_moves: bool = False,
        region_of_interest: Any = None,
        partial_result: bool = False,
    ) -> None:
        if refine_move:
            pvtail = analysis_json["moveInfos"][0]["pv"] if analysis_json["moveInfos"] else []
            self.update_move_analysis(
                {"pv": [refine_move.gtp()] + pvtail, **analysis_json["rootInfo"]}, refine_move.gtp()
            )
        else:
            if additional_moves:  # additional moves: old order matters, ignore new order
                for m in analysis_json["moveInfos"]:
                    del m["order"]
            elif refine_move is None:  # normal update: old moves to end, new order matters. also for region?
                for move_dict in self.analysis["moves"].values():
                    move_dict["order"] = ADDITIONAL_MOVE_ORDER  # old moves to end
            for move_analysis in analysis_json["moveInfos"]:
                self.update_move_analysis(move_analysis, move_analysis["move"])
            self.analysis["ownership"] = analysis_json.get("ownership")
            self.analysis["policy"] = analysis_json.get("policy")
            if not additional_moves and not region_of_interest:
                self.analysis["root"] = analysis_json["rootInfo"]
                parent = self.parent
                if parent and isinstance(parent, GameNode) and self.move:
                    analysis_json["rootInfo"]["pv"] = [self.move.gtp()] + (
                        analysis_json["moveInfos"][0]["pv"] if analysis_json["moveInfos"] else []
                    )
                    parent.update_move_analysis(
                        analysis_json["rootInfo"], self.move.gtp()
                    )  # update analysis in parent for consistency
            is_normal_query = refine_move is None and not additional_moves
            self.analysis["completed"] = self.analysis["completed"] or (is_normal_query and not partial_result)

    @property
    def ownership(self) -> list[float | None]:
        return self.analysis.get("ownership")

    @property
    def policy(self) -> list[float | None]:
        return self.analysis.get("policy")

    @property
    def analysis_exists(self) -> bool:
        return self.analysis["root"] is not None

    @property
    def analysis_complete(self) -> bool:
        return self.analysis["completed"] and self.analysis["root"] is not None

    @property
    def root_visits(self) -> int:
        return int(((self.analysis or {}).get("root") or {}).get("visits", 0))

    @property
    def score(self) -> float | None:
        if self.analysis_exists:
            root = self.analysis["root"]
            if root is not None:
                return float(root.get("scoreLead", 0))
        return None

    def format_score(self, score: float | None = None) -> str | None:
        score = score or self.score
        if score is not None:
            leading_player = 'B' if score >= 0 else 'W'
            leading_player_color = i18n._(f"short color {leading_player}")
            return f"{leading_player_color}+{abs(score):.1f}"
        return None

    @property
    def winrate(self) -> float | None:
        if self.analysis_exists:
            root = self.analysis["root"]
            if root is not None:
                return float(root.get("winrate", 0.5))
        return None

    def format_winrate(self, win_rate: float | None = None) -> str | None:
        win_rate = win_rate or self.winrate
        if win_rate is not None:
            leading_player = 'B' if win_rate > 0.5 else 'W'
            leading_player_color = i18n._(f"short color {leading_player}")
            return f"{leading_player_color} {max(win_rate,1-win_rate):.1%}"
        return None

    def move_policy_stats(self) -> tuple[int | None, float, list[tuple[float, Move]]]:
        single_move = self.move
        parent = self.parent
        if single_move and parent and isinstance(parent, GameNode):
            policy_ranking = parent.policy_ranking
            if policy_ranking:
                for ix, (p, m) in enumerate(policy_ranking):
                    if m == single_move:
                        return ix + 1, p, policy_ranking
        return None, 0.0, []

    def make_pv(self, player: str, pv: list[str], interactive: bool) -> str:
        pvtext = f"{player}{' '.join(pv)}"
        if interactive:
            pvtext = f"[u][ref={pvtext}][color={INFO_PV_COLOR}]{pvtext}[/color][/ref][/u]"
        return pvtext

    def comment(self, sgf: bool = False, teach: bool = False, details: bool = False, interactive: bool = True) -> str:
        single_move = self.move
        if not self.parent or not single_move:  # root
            if self.root:
                rules = self.get_property("RU", "Japanese")
                if isinstance(rules, str):  # else katago dict
                    rules = i18n._(rules.lower())
                return f"{i18n._('komi')}: {self.komi:.1f}\n{i18n._('ruleset')}: {rules}\n"
            return ""

        text = i18n._("move").format(number=self.depth) + f": {single_move.player} {single_move.gtp()}\n"
        if self.analysis_exists:
            score = self.score
            if sgf:
                text += i18n._("Info:score").format(score=self.format_score(score)) + "\n"
                text += i18n._("Info:winrate").format(winrate=self.format_winrate()) + "\n"
            if details:
                text += f"Visits: {self.root_visits}\n"
            parent = self.parent
            if parent and isinstance(parent, GameNode) and parent.analysis_exists:
                parent_candidates = parent.candidate_moves
                previous_top_move = parent_candidates[0] if parent_candidates else None
                if previous_top_move and (sgf or details):
                    if previous_top_move["move"] != single_move.gtp():
                        points_lost = self.points_lost
                        if sgf and points_lost is not None and points_lost > 0.5:
                            text += i18n._("Info:point loss").format(points_lost=points_lost) + "\n"
                        top_move = previous_top_move["move"]
                        formatted_score = self.format_score(previous_top_move["scoreLead"])
                        text += (
                            i18n._("Info:top move").format(
                                top_move=top_move,
                                score=formatted_score,
                            )
                            + "\n"
                        )
                    else:
                        text += i18n._("Info:best move") + "\n"
                    if previous_top_move.get("pv") and (sgf or details):
                        pv = self.make_pv(single_move.player, previous_top_move["pv"], interactive)
                        text += i18n._("Info:PV").format(pv=pv) + "\n"
                if sgf or details or teach:
                    currmove_pol_rank, currmove_pol_prob, policy_ranking = self.move_policy_stats()
                    if currmove_pol_rank is not None:
                        policy_rank_msg = i18n._("Info:policy rank")
                        text += policy_rank_msg.format(rank=currmove_pol_rank, probability=currmove_pol_prob) + "\n"
                    if currmove_pol_rank != 1 and policy_ranking and (sgf or details):
                        policy_best_msg = i18n._("Info:policy best")
                        pol_move, pol_prob = policy_ranking[0][1].gtp(), policy_ranking[0][0]
                        text += policy_best_msg.format(move=pol_move, probability=pol_prob) + "\n"
            if self.auto_undo and sgf:
                text += i18n._("Info:teaching undo") + "\n"
                candidates = self.candidate_moves
                top_pv = self.analysis_exists and candidates and candidates[0].get("pv")
                if top_pv:
                    text += i18n._("Info:undo predicted PV").format(pv=f"{self.next_player}{' '.join(top_pv)}") + "\n"
        else:
            text = i18n._("No analysis available") if sgf else i18n._("Analyzing move...")

        if self.ai_thoughts and (sgf or details):
            text += "\n" + i18n._("Info:AI thoughts").format(thoughts=self.ai_thoughts)

        if "C" in self.properties:
            text += "\n[u]SGF Comments:[/u]\n" + "\n".join(self.properties["C"])

        return text

    @property
    def points_lost(self) -> float | None:
        single_move = self.move
        parent = self.parent
        if single_move and parent and isinstance(parent, GameNode) and self.analysis_exists and parent.analysis_exists:
            parent_score = parent.score
            score = self.score
            if parent_score is not None and score is not None:
                return float(self.player_sign(single_move.player) * (parent_score - score))
        return None

    @property
    def parent_realized_points_lost(self) -> float | None:
        single_move = self.move
        parent = self.parent
        if (
            single_move
            and parent
            and isinstance(parent, GameNode)
            and parent.parent
            and isinstance(parent.parent, GameNode)
            and self.analysis_exists
            and parent.parent.analysis_exists
        ):
            parent_parent_score = parent.parent.score
            score = self.score
            if parent_parent_score is not None and score is not None:
                return float(self.player_sign(single_move.player) * (score - parent_parent_score))
        return None

    @staticmethod
    def player_sign(player: str | None) -> int:
        return {"B": 1, "W": -1, None: 0}[player]

    @property
    def candidate_moves(self) -> list[dict[str, Any]]:
        if not self.analysis_exists:
            return []
        if not self.analysis["moves"]:
            polmoves = self.policy_ranking
            top_polmove = polmoves[0][1] if polmoves else Move(None)  # if no info at all, pass
            return [
                {
                    **self.analysis["root"],
                    "pointsLost": 0,
                    "winrateLost": 0,
                    "order": 0,
                    "move": top_polmove.gtp(),
                    "pv": [top_polmove.gtp()],
                }
            ]  # single visit -> go by policy/root

        root_score = self.analysis["root"]["scoreLead"]
        root_winrate = self.analysis["root"]["winrate"]
        move_dicts = list(self.analysis["moves"].values())  # prevent incoming analysis from causing crash
        top_move = [d for d in move_dicts if d["order"] == 0]
        top_score_lead = top_move[0]["scoreLead"] if top_move else root_score
        return sorted(
            [
                {
                    "pointsLost": self.player_sign(self.next_player) * (root_score - d["scoreLead"]),
                    "relativePointsLost": self.player_sign(self.next_player) * (top_score_lead - d["scoreLead"]),
                    "winrateLost": self.player_sign(self.next_player) * (root_winrate - d["winrate"]),
                    **d,
                }
                for d in move_dicts
            ],
            key=lambda d: (d["order"], d["pointsLost"]),
        )

    @property
    def policy_ranking(self) -> list[tuple[float, Move | None]]:  # return moves from highest policy value to lowest
        if self.policy:
            szx, szy = self.board_size
            policy_grid = var_to_grid(self.policy, size=(szx, szy))
            moves = [(policy_grid[y][x], Move((x, y), player=self.next_player)) for x in range(szx) for y in range(szy)]
            moves.append((self.policy[-1], Move(None, player=self.next_player)))
            return sorted(moves, key=lambda mp: -mp[0])
        return None
