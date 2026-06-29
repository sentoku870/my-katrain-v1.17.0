"""Basic AI strategies.

Phase 158+: Extracted from ``katrain.core.ai`` for family-based organization.

Strategies:
- DefaultStrategy: plays the top engine move (fallback for many other strategies)
- HandicapStrategy: uses playoutDoublingAdvantage (PDA) analysis
- AntimirrorStrategy: uses antiMirror analysis
- JigoStrategy: aims for a specific score difference
"""

from __future__ import annotations

from katrain.core.ai_strategies_base import AIStrategy, register_strategy
from katrain.core.constants import (
    AI_ANTIMIRROR,
    AI_DEFAULT,
    AI_HANDICAP,
    AI_JIGO,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
)
from katrain.core.game import Move


@register_strategy(AI_DEFAULT)
class DefaultStrategy(AIStrategy):
    """Default strategy - simply plays the top move from the engine"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[DefaultStrategy] Starting move generation", OUTPUT_DEBUG)
        self.wait_for_analysis()

        candidate_moves = self.cn.candidate_moves
        self.game.katrain.log(f"[DefaultStrategy] Analysis found {len(candidate_moves)} candidate moves", OUTPUT_DEBUG)

        if not candidate_moves:
            self.game.katrain.log("[DefaultStrategy] No candidate moves found, will play pass", OUTPUT_DEBUG)
            top_cand = Move(None, player=self.cn.next_player)
        else:
            top_move_data = candidate_moves[0]
            top_cand = Move.from_gtp(top_move_data["move"], player=self.cn.next_player)
            self.game.katrain.log(
                f"[DefaultStrategy] Top move: {top_cand.gtp()} with stats: {top_move_data}", OUTPUT_DEBUG
            )

        ai_thoughts = f"Default strategy found {len(candidate_moves)} moves returned from the engine and chose {top_cand.gtp()} as top move"
        self.game.katrain.log(f"[DefaultStrategy] Final decision: {top_cand.gtp()}", OUTPUT_DEBUG)

        return top_cand, ai_thoughts


@register_strategy(AI_HANDICAP)
class HandicapStrategy(AIStrategy):
    """Handicap strategy - uses playoutDoublingAdvantage to analyze the position"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[HandicapStrategy] Starting move generation", OUTPUT_DEBUG)

        # Calculate PDA (Playout Doubling Advantage)
        pda = self.settings["pda"]
        self.game.katrain.log(f"[HandicapStrategy] Initial PDA from settings: {pda}", OUTPUT_DEBUG)

        if self.settings["automatic"]:
            n_handicaps = len(self.game.root.get_list_property("AB", []))
            MOVE_VALUE = 14  # could be rules dependent
            b_stones_advantage = max(n_handicaps - 1, 0) - (self.cn.komi - MOVE_VALUE / 2) / MOVE_VALUE
            pda = min(3, max(-3, -b_stones_advantage * (3 / 8)))  # max PDA at 8 stone adv, normal 9 stone game is 8.46

            self.game.katrain.log("[HandicapStrategy] Automatic PDA calculation:", OUTPUT_DEBUG)
            self.game.katrain.log(f"[HandicapStrategy] - Handicap stones: {n_handicaps}", OUTPUT_DEBUG)
            self.game.katrain.log(f"[HandicapStrategy] - Komi: {self.cn.komi}", OUTPUT_DEBUG)
            self.game.katrain.log(f"[HandicapStrategy] - Stone advantage: {b_stones_advantage}", OUTPUT_DEBUG)
            self.game.katrain.log(f"[HandicapStrategy] - Calculated PDA: {pda}", OUTPUT_DEBUG)

        # Request additional analysis with PDA
        self.game.katrain.log(f"[HandicapStrategy] Requesting analysis with PDA={pda}", OUTPUT_DEBUG)
        handicap_analysis = self.request_analysis(
            {"playoutDoublingAdvantage": pda, "playoutDoublingAdvantagePla": "BLACK"}
        )

        if not handicap_analysis:
            self.game.katrain.log(
                "[HandicapStrategy] Error getting handicap-based move, falling back to DefaultStrategy", OUTPUT_ERROR
            )
            return DefaultStrategy(self.game, self.settings).generate_move()

        self.wait_for_analysis()

        candidate_moves = handicap_analysis["moveInfos"]
        self.game.katrain.log(
            f"[HandicapStrategy] Analysis returned {len(candidate_moves)} candidate moves", OUTPUT_DEBUG
        )

        # Get top candidate move
        top_move_data = candidate_moves[0]
        top_cand = Move.from_gtp(top_move_data["move"], player=self.cn.next_player)

        # Log details about the top move
        self.game.katrain.log(f"[HandicapStrategy] Top move: {top_cand.gtp()}", OUTPUT_DEBUG)
        self.game.katrain.log(
            f"[HandicapStrategy] Score lead: {handicap_analysis['rootInfo']['scoreLead']}", OUTPUT_DEBUG
        )
        self.game.katrain.log(f"[HandicapStrategy] Win rate: {handicap_analysis['rootInfo']['winrate']}", OUTPUT_DEBUG)

        ai_thoughts = f"Handicap strategy found {len(candidate_moves)} moves returned from the engine and chose {top_cand.gtp()} as top move. PDA based score {self.cn.format_score(handicap_analysis['rootInfo']['scoreLead'])} and win rate {self.cn.format_winrate(handicap_analysis['rootInfo']['winrate'])}"

        self.game.katrain.log(f"[HandicapStrategy] Final decision: {top_cand.gtp()}", OUTPUT_DEBUG)
        return top_cand, ai_thoughts


@register_strategy(AI_ANTIMIRROR)
class AntimirrorStrategy(AIStrategy):
    """Antimirror strategy - uses antiMirror to analyze the position"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[AntimirrorStrategy] Starting move generation", OUTPUT_DEBUG)

        # Request analysis with antimirror option
        self.game.katrain.log("[AntimirrorStrategy] Requesting analysis with antiMirror=True", OUTPUT_DEBUG)
        antimirror_analysis = self.request_analysis({"antiMirror": True})

        if not antimirror_analysis:
            self.game.katrain.log(
                "[AntimirrorStrategy] Error getting antimirror move, falling back to DefaultStrategy", OUTPUT_ERROR
            )
            return DefaultStrategy(self.game, self.settings).generate_move()

        self.wait_for_analysis()

        candidate_moves = antimirror_analysis["moveInfos"]
        self.game.katrain.log(
            f"[AntimirrorStrategy] Analysis returned {len(candidate_moves)} candidate moves", OUTPUT_DEBUG
        )

        # Get top candidate move
        top_move_data = candidate_moves[0]
        top_cand = Move.from_gtp(top_move_data["move"], player=self.cn.next_player)

        # Log details about the top move
        self.game.katrain.log(f"[AntimirrorStrategy] Top move: {top_cand.gtp()}", OUTPUT_DEBUG)
        self.game.katrain.log(
            f"[AntimirrorStrategy] Score lead: {antimirror_analysis['rootInfo']['scoreLead']}", OUTPUT_DEBUG
        )
        self.game.katrain.log(
            f"[AntimirrorStrategy] Win rate: {antimirror_analysis['rootInfo']['winrate']}", OUTPUT_DEBUG
        )

        # Log the top 3 moves for comparison
        for i, move_data in enumerate(candidate_moves[:3]):
            move = Move.from_gtp(move_data["move"], player=self.cn.next_player)
            self.game.katrain.log(
                f"[AntimirrorStrategy] Move #{i + 1}: {move.gtp()} - visits: {move_data.get('visits', 'N/A')}, points lost: {move_data.get('pointsLost', 'N/A')}",
                OUTPUT_DEBUG,
            )

        ai_thoughts = f"AntiMirror strategy found {len(candidate_moves)} moves returned from the engine and chose {top_cand.gtp()} as top move. antiMirror based score {self.cn.format_score(antimirror_analysis['rootInfo']['scoreLead'])} and win rate {self.cn.format_winrate(antimirror_analysis['rootInfo']['winrate'])}"

        self.game.katrain.log(f"[AntimirrorStrategy] Final decision: {top_cand.gtp()}", OUTPUT_DEBUG)
        return top_cand, ai_thoughts


@register_strategy(AI_JIGO)
class JigoStrategy(AIStrategy):
    """Jigo strategy - aims for a specific score difference"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[JigoStrategy] Starting move generation", OUTPUT_DEBUG)
        self.wait_for_analysis()

        candidate_moves = self.cn.candidate_moves
        self.game.katrain.log(f"[JigoStrategy] Analysis found {len(candidate_moves)} candidate moves", OUTPUT_DEBUG)

        if not candidate_moves:
            self.game.katrain.log("[JigoStrategy] No candidate moves found, will play pass", OUTPUT_DEBUG)
            return Move(None, player=self.cn.next_player), "No candidate moves found, passing"

        # Get top engine move for reference
        top_cand = Move.from_gtp(candidate_moves[0]["move"], player=self.cn.next_player)
        self.game.katrain.log(f"[JigoStrategy] Top engine move would be: {top_cand.gtp()}", OUTPUT_DEBUG)

        # Calculate player sign (1 for black, -1 for white)
        sign = self.cn.player_sign(self.cn.next_player)
        self.game.katrain.log(f"[JigoStrategy] Player sign: {sign}", OUTPUT_DEBUG)

        # Get target score from settings
        target_score = self.settings["target_score"]
        self.game.katrain.log(f"[JigoStrategy] Target score: {target_score}", OUTPUT_DEBUG)

        # Log score leads before selecting jigo move
        self.game.katrain.log("[JigoStrategy] Candidate move score leads:", OUTPUT_DEBUG)
        for _i, move_data in enumerate(candidate_moves[:5]):
            move = Move.from_gtp(move_data["move"], player=self.cn.next_player)
            score_diff = abs(sign * move_data["scoreLead"] - target_score)
            self.game.katrain.log(
                f"[JigoStrategy] - {move.gtp()}: scoreLead={move_data['scoreLead']}, diff from target={score_diff}",
                OUTPUT_DEBUG,
            )

        # Find the move that gives a score closest to the target
        jigo_move = min(candidate_moves, key=lambda move: abs(sign * move["scoreLead"] - target_score))

        aimove = Move.from_gtp(jigo_move["move"], player=self.cn.next_player)
        jigo_score_diff = abs(sign * jigo_move["scoreLead"] - target_score)

        self.game.katrain.log(f"[JigoStrategy] Selected move: {aimove.gtp()}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[JigoStrategy] Selected move score lead: {jigo_move['scoreLead']}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[JigoStrategy] Distance from target: {jigo_score_diff}", OUTPUT_DEBUG)

        ai_thoughts = f"Jigo strategy found {len(candidate_moves)} candidate moves (best {top_cand.gtp()}) and chose {aimove.gtp()} as closest to 0.5 point win"

        self.game.katrain.log(f"[JigoStrategy] Final decision: {aimove.gtp()}", OUTPUT_DEBUG)
        return aimove, ai_thoughts
