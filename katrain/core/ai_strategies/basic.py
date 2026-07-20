"""Basic AI strategies.

Phase 158+: Extracted from ``katrain.core.ai`` for family-based organization.
Phase 280: Slimmed down to only the two survivor strategies
(`ai:default` DefaultStrategy and `ai:handicap` HandicapStrategy).

Strategies:
- DefaultStrategy: plays the top engine move (fallback for many other strategies)
- HandicapStrategy: uses playoutDoublingAdvantage (PDA) analysis
"""

from __future__ import annotations

from katrain.core.ai.constants import AI_DEFAULT, AI_HANDICAP
from katrain.core.ai_strategies_base import AIStrategy, register_strategy
from katrain.core.constants import OUTPUT_DEBUG, OUTPUT_ERROR
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

        top_move_data = candidate_moves[0]
        top_cand = Move.from_gtp(top_move_data["move"], player=self.cn.next_player)

        self.game.katrain.log(f"[HandicapStrategy] Top move: {top_cand.gtp()}", OUTPUT_DEBUG)
        self.game.katrain.log(
            f"[HandicapStrategy] Score lead: {handicap_analysis['rootInfo']['scoreLead']}", OUTPUT_DEBUG
        )
        self.game.katrain.log(f"[HandicapStrategy] Win rate: {handicap_analysis['rootInfo']['winrate']}", OUTPUT_DEBUG)

        ai_thoughts = f"Handicap strategy found {len(candidate_moves)} moves returned from the engine and chose {top_cand.gtp()} as top move. PDA based score {self.cn.format_score(handicap_analysis['rootInfo']['scoreLead'])} and win rate {self.cn.format_winrate(handicap_analysis['rootInfo']['winrate'])}"

        self.game.katrain.log(f"[HandicapStrategy] Final decision: {top_cand.gtp()}", OUTPUT_DEBUG)
        return top_cand, ai_thoughts
