"""Leela AI strategy (Phase 159B).

Restored from the Phase 123 Leela Slimming, which dropped ``LeelaStrategy``
and ``AI_LEELA`` in favour of limiting Leela to analysis-only roles.
Phase 159B brings back a minimal ``AIStrategy`` so a human can play a
game against Leela via the LeelaEngine GTP wrapper.

Design notes
------------
* The strategy is deliberately thin: it leans on
  ``core.ai_strategies_base.AIStrategy`` for the constructor / logging
  interface, and on ``core.leela.engine.LeelaEngine`` for the actual
  GTP traffic. No board mirroring or scoring logic lives here; Leela
  plays the same moves KataGo would (and vice versa — that's exactly
  what the GTP ``play`` / ``genmove`` commands assume).

* The strategy reads Leela configuration from the typed config helper
  ``ctx.get_leela_config()``. Visit count, handicap compensation and
  the rest are user-tunable via the Leela settings tab.

* The strategy is registered via ``@register_strategy(AI_LEELA)`` so
  the engine selection dropdown can list it alongside the KataGo
  AI strategies. Phase 159A keeps Leela disabled in the Karte/Summary
  generators, but Karte reports are not consumed by LeelaStrategy
  anyway — only KataGo's Game + engine-comms pair matter here.
"""

from __future__ import annotations

from typing import Any

from katrain.core.ai_strategies_base import AIStrategy, register_strategy
from katrain.core.constants import (
    AI_LEELA,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_INFO,
)
from katrain.core.game import Move


@register_strategy(AI_LEELA)
class LeelaStrategy(AIStrategy):
    """Human-vs-Leela play strategy.

    Each call to ``generate_move()``:

    1. Resolves the Leela engine via ``game.katrain.leela_manager``.
    2. Re-plays the current main-branch moves onto Leela's board via
       ``set_position`` (with komi/board-size replay if changed).
    3. Asks Leela for its move via ``genmove`` (synchronous). The visit
       budget comes from ``ai_settings['play_visits']`` (default 500)
       and falls back to ``leela_config.max_visits``.

    No KataGo analysis is consulted on the Leela turn — the AI loop
    sequences KataGo / Leela analysis around the engine's own turn.
    """

    # Sentinel value used in ``ai_settings`` when the user hasn't
    # overridden the play-visit budget.
    _PLAY_VISITS_DEFAULT: int = 500

    def _resolve_leela_engine(self) -> Any:
        """Best-effort lookup of the Leela engine instance.

        We support two layouts the codebase has shipped over time:

        * ``self.game.katrain.leela_engine`` — direct reference (PR #121
          and later expose a property that proxies
          ``leela_manager.leela_engine``).
        * ``self.game.katrain.leela_manager.leela_engine`` — manager
          indirection (current ``gui/leela_manager.py``).

        Returns ``None`` if neither is available or Leela is not
        currently running — ``generate_move`` then falls back to a
        pass with a user-visible warning.
        """
        katrain = self.game.katrain
        engine = getattr(katrain, "leela_engine", None)
        if engine is not None:
            return engine
        manager = getattr(katrain, "leela_manager", None)
        if manager is not None:
            return getattr(manager, "leela_engine", None)
        return None

    def _current_leela_visits(self) -> int:
        """Read ``play_visits`` from ai_settings or Leela config."""
        play_visits = self.settings.get("play_visits") if isinstance(self.settings, dict) else None
        if isinstance(play_visits, (int, float)) and play_visits > 0:
            return int(play_visits)
        try:
            leela_cfg = self.game.katrain.get_leela_config()
            cfg_visits = getattr(leela_cfg, "play_visits", None)
            if isinstance(cfg_visits, (int, float)) and cfg_visits > 0:
                return int(cfg_visits)
            max_visits = getattr(leela_cfg, "max_visits", None)
            if isinstance(max_visits, (int, float)) and max_visits > 0:
                return int(max_visits)
        except Exception:  # noqa: BLE001 - best-effort config read
            pass
        return self._PLAY_VISITS_DEFAULT

    def _build_move_list(self) -> list[tuple[str, str]]:
        """Collect (player, coord) tuples for the main branch up to the current node."""
        nodes = self.cn.nodes_from_root or []
        moves: list[tuple[str, str]] = []
        for node in nodes:
            for m in node.moves:
                try:
                    moves.append((m.player, m.gtp()))
                except Exception:  # noqa: BLE001 - defensive
                    continue
        return moves

    def generate_move(self) -> tuple[Move, str]:
        """Generate Leela's move for the current position."""
        self.game.katrain.log("[LeelaStrategy] Starting move generation", OUTPUT_DEBUG)

        engine = self._resolve_leela_engine()
        if engine is None or not getattr(engine, "is_alive", lambda: False)():
            self.game.katrain.log(
                "[LeelaStrategy] Engine not running — falling back to pass. "
                "Start Leela from Settings > Leela.",
                OUTPUT_ERROR,
            )
            return (
                Move(None, player=self.cn.next_player),
                "Leela engine not running — passing. Open Settings > Leela to start it.",
            )

        # Board-size + komi derive from the Game root. We snapshot the
        # values we send to Leela so the next call can diff cheaply.
        try:
            board_size = self.game.root.board_size[0]
            komi = float(self.game.komi)
        except Exception:  # noqa: BLE001 - defensive
            board_size, komi = 19, 6.5

        moves = self._build_move_list()
        if not engine.set_position(moves, board_size=board_size, komi=komi):
            self.game.katrain.log(
                "[LeelaStrategy] Failed to sync position with Leela — passing.",
                OUTPUT_ERROR,
            )
            return (
                Move(None, player=self.cn.next_player),
                "Failed to sync Leela position. Passing turn.",
            )

        visits = self._current_leela_visits()
        color = self.cn.next_player

        # ``request_move`` runs synchronously; the callback is invoked
        # once. We collect the coord in a single-element list via a
        # closure to avoid a class attribute race.
        result: list[str] = [""]

        def _on_move(coord: str) -> None:
            result[0] = coord

        if not engine.request_move(color, _on_move, visits=visits):
            self.game.katrain.log(
                "[LeelaStrategy] request_move dispatch failed — passing.",
                OUTPUT_ERROR,
            )
            return (
                Move(None, player=self.cn.next_player),
                "Leela request_move failed. Passing turn.",
            )

        coord = result[0]
        if not coord:
            self.game.katrain.log(
                "[LeelaStrategy] No move returned from Leela. Passing.",
                OUTPUT_ERROR,
            )
            return (
                Move(None, player=self.cn.next_player),
                "Leela returned no move. Passing turn.",
            )
        if coord.lower() == "resign":
            self.game.katrain.log("[LeelaStrategy] Leela resigned.", OUTPUT_INFO)
            return (
                Move(None, player=color),
                "Leela resigned at the current position.",
            )

        chosen = Move.from_gtp(coord, player=color)
        ai_thoughts = (
            f"Leela ({visits} visits) selected {chosen.gtp()} as the next move."
        )
        self.game.katrain.log(
            f"[LeelaStrategy] Final decision: {chosen.gtp()} (visits={visits})",
            OUTPUT_DEBUG,
        )
        return chosen, ai_thoughts
