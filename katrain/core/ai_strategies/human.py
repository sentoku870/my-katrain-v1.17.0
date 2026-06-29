"""Human-style AI strategy.

Phase 158+: Extracted from ``katrain.core.ai`` for family-based organization.

Strategy:
- HumanStyleStrategy: imitates human play at various skill levels.
  Registered twice (AI_HUMAN, AI_PRO) - same class for both kyudan/amateur
  (controlled by ``human_kyu_rank``) and pro year (``pro_year``) profiles.
"""

from __future__ import annotations

import time
from typing import Any

from katrain.core.ai_strategies_base import AIStrategy, register_strategy
from katrain.core.constants import (
    AI_HUMAN,
    AI_PRO,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    PRIORITY_EXTRA_AI_QUERY,
)
from katrain.core.game import Game, Move
from katrain.core.utils import weighted_selection_without_replacement


@register_strategy(AI_HUMAN)
@register_strategy(AI_PRO)
class HumanStyleStrategy(AIStrategy):
    """Strategy that imitates human play at various skill levels"""

    def __init__(self, game: Game, ai_settings: dict[str, Any]):
        super().__init__(game, ai_settings)
        self.game.katrain.log("[HumanStyleStrategy] Initializing HumanStyleStrategy", OUTPUT_DEBUG)
        self.game.katrain.log(f"[HumanStyleStrategy] AI settings: {ai_settings}", OUTPUT_DEBUG)

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[HumanStyleStrategy] Starting move generation", OUTPUT_DEBUG)

        if "human_kyu_rank" in self.settings:
            human_kyu_rank = round(self.settings["human_kyu_rank"])
            human_style = "rank" if self.settings["modern_style"] else "preaz"

            rank_text = f"{1 - human_kyu_rank}d" if human_kyu_rank <= 0 else f"{human_kyu_rank}k"
            human_profile = f"{human_style}_{rank_text}"
        else:
            pro_year = round(self.settings["pro_year"])
            human_profile = f"proyear_{pro_year}"

        self.game.katrain.log(f"[HumanStyleStrategy] Human profile string: {human_profile}", OUTPUT_DEBUG)

        # Define override settings (separate from includePolicy)
        override_settings: dict[str, Any] = {
            "humanSLProfile": human_profile,
            "ignorePreRootHistory": False,
        }
        self.game.katrain.log(f"[HumanStyleStrategy] Override settings for engine: {override_settings}", OUTPUT_DEBUG)

        # Request analysis from engine - note includePolicy is a direct parameter
        analysis: dict[str, Any] | None = None
        error = False  # Define error BEFORE the nested function

        def set_analysis(a: dict[str, Any] | None, partial_result: bool) -> None:
            nonlocal analysis
            if not partial_result:
                self.game.katrain.log("[HumanStyleStrategy] Full analysis results received", OUTPUT_DEBUG)
                analysis = a
                # Log some analysis stats for debugging
                if a:
                    self.game.katrain.log(
                        f"[HumanStyleStrategy] Analysis contains humanPolicy: {'humanPolicy' in a}", OUTPUT_DEBUG
                    )
                    self.game.katrain.log(
                        f"[HumanStyleStrategy] Analysis contains moveInfos: {len(a.get('moveInfos', []))} moves",
                        OUTPUT_DEBUG,
                    )
                    if "humanPolicy" in a:
                        policy_sum = sum(a["humanPolicy"])
                        policy_max = max(a["humanPolicy"])
                        self.game.katrain.log(
                            f"[HumanStyleStrategy] Human policy sum: {policy_sum}, max: {policy_max}", OUTPUT_DEBUG
                        )
            else:
                self.game.katrain.log("[HumanStyleStrategy] Received partial analysis results - ignoring", OUTPUT_DEBUG)

        def set_error(a: Any) -> None:
            nonlocal error
            error = True
            self.game.katrain.log(f"[HumanStyleStrategy] Error in human analysis query: {a}", OUTPUT_ERROR)
            self.game.katrain.log("[HumanStyleStrategy] Will attempt to fall back to policy move", OUTPUT_DEBUG)

        self.game.katrain.log("[HumanStyleStrategy] Getting engine for player", OUTPUT_DEBUG)
        engine = self.game.engines[self.cn.player]
        self.game.katrain.log(f"[HumanStyleStrategy] Using engine for player {self.cn.player}", OUTPUT_DEBUG)

        self.game.katrain.log("[HumanStyleStrategy] Requesting analysis with human profile settings", OUTPUT_DEBUG)
        engine.request_analysis(
            self.cn,
            callback=set_analysis,
            error_callback=set_error,
            priority=PRIORITY_EXTRA_AI_QUERY,
            include_policy=True,
            extra_settings=override_settings,
        )
        self.game.katrain.log("[HumanStyleStrategy] Analysis request sent, waiting for results", OUTPUT_DEBUG)

        # Wait for analysis to complete
        wait_count = 0
        while not (error or analysis):
            time.sleep(0.01)
            wait_count += 1
            if wait_count % 100 == 0:  # Log every 1 second
                self.game.katrain.log(
                    f"[HumanStyleStrategy] Still waiting for analysis results ({wait_count / 100:.1f}s)", OUTPUT_DEBUG
                )
            engine.check_alive(exception_if_dead=True)

        self.game.katrain.log(
            f"[HumanStyleStrategy] Finished waiting for analysis, error={error}, analysis received={analysis is not None}",
            OUTPUT_DEBUG,
        )

        if error or not analysis:
            self.game.katrain.log("[HumanStyleStrategy] Analysis failed or returned empty", OUTPUT_DEBUG)
            # Fall back to policy
            policy_move = self.cn.policy_ranking[0][1] if self.cn.policy_ranking else None
            if policy_move:
                self.game.katrain.log(
                    f"[HumanStyleStrategy] Falling back to top policy move: {policy_move.gtp()}", OUTPUT_DEBUG
                )
                return policy_move, "Falling back to policy move due to error in human analysis."
            else:
                self.game.katrain.log(
                    "[HumanStyleStrategy] No policy moves available for fallback - will return pass", OUTPUT_DEBUG
                )
                return Move(None, player=self.cn.next_player), "No valid moves found."

        # Check if human policy is available
        self.game.katrain.log("[HumanStyleStrategy] Processing analysis results", OUTPUT_DEBUG)
        if "humanPolicy" not in analysis:
            error_msg = "humanPolicy not found in analysis—have you downloaded and configured your human model yet?"
            raise Exception(error_msg)

        self.game.katrain.log("[HumanStyleStrategy] Human policy found in analysis", OUTPUT_DEBUG)
        board_size = self.game.board_size
        self.game.katrain.log(f"[HumanStyleStrategy] Board size: {board_size}", OUTPUT_DEBUG)
        human_policy = analysis["humanPolicy"]
        self.game.katrain.log(f"[HumanStyleStrategy] Human policy length: {len(human_policy)}", OUTPUT_DEBUG)
        if len(human_policy) != 362:
            self.game.katrain.log(
                f"[HumanStyleStrategy] WARNING: Human policy length {len(human_policy)} != 362", OUTPUT_ERROR
            )

        # Create a list of moves with their human policy weights
        moves = []
        for x in range(board_size[0]):
            for y in range(board_size[1]):
                idx = (board_size[1] - y - 1) * board_size[0] + x
                if idx < len(human_policy) and human_policy[idx] > 0:
                    moves.append((Move((x, y), player=self.cn.next_player), human_policy[idx]))

        self.game.katrain.log(
            f"[HumanStyleStrategy] Generated {len(moves)} candidate moves from human policy", OUTPUT_DEBUG
        )

        # Add pass move if it has positive probability
        if len(human_policy) > board_size[0] * board_size[1] and human_policy[-1] > 0:
            self.game.katrain.log(
                f"[HumanStyleStrategy] Adding pass move with probability {human_policy[-1]}", OUTPUT_DEBUG
            )
            moves.append((Move(None, player=self.cn.next_player), human_policy[-1]))

        self.game.katrain.log(
            f"[HumanStyleStrategy] Performing weighted selection from {len(moves)} moves", OUTPUT_DEBUG
        )
        top_moves = sorted(moves, key=lambda x: -x[1])
        self.game.katrain.log("[HumanStyleStrategy] Top 5 moves by probability:", OUTPUT_DEBUG)

        # Create a formatted string of top 5 moves for ai_thoughts
        top_moves_str = "\n".join(
            [f"#{i + 1}: {move.gtp()} - {prob:.1%}" for i, (move, prob) in enumerate(top_moves[:5])]
        )

        self.game.katrain.log(f"[HumanStyleStrategy]\n{top_moves_str}", OUTPUT_DEBUG)

        selected = weighted_selection_without_replacement(moves, 1)[0]
        move = selected[0]
        prob = selected[1]

        # Find the rank of the selected move
        selected_rank = next(
            (i + 1 for i, (m, _) in enumerate(top_moves) if m.gtp() == move.gtp()), "ERROR: move not found in ranking"
        )

        self.game.katrain.log(
            f"[HumanStyleStrategy] Selected move {move.gtp()} with probability {prob:.4f}", OUTPUT_DEBUG
        )
        ai_thoughts = f"\n{top_moves_str}\n\nPlayed move {move.gtp()} ({prob:.1%}) as the #{selected_rank} top move."
        self.game.katrain.log(f"[HumanStyleStrategy] Final decision: {move.gtp()}", OUTPUT_DEBUG)
        return move, ai_thoughts
