"""Leela analysis manager.

PR #121: Phase B3 - LeelaManager抽出

__main__.pyから抽出されたLeela解析管理機能。
依存注入パターンで明示的な依存のみを受け取る。

このモジュールの設計原則:
- KaTrainGuiへの直接参照を持たない
- 必要な依存はコンストラクタで明示的に受け取る
- 状態変更はコールバック経由で通知
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Callable
from typing import Any

from kivy.clock import Clock

from katrain.core.constants import OUTPUT_ERROR, OUTPUT_INFO
from katrain.core.leela.engine import LeelaEngine
from katrain.core.leela.logic import (
    LEELA_K_DEFAULT,
    check_resign_condition,
    compute_estimated_loss,
)
from katrain.core.leela.models import LeelaPositionEval


class LeelaManager:
    """Leela解析を管理するクラス。

    KaTrainGuiから抽出されたLeela関連機能を担当。
    依存注入パターンにより、必要な機能のみをコールバックで受け取る。

    Attributes:
        leela_engine: LeelaEngineインスタンス（またはNone）
    """

    def __init__(
        self,
        config_getter: Callable[[str, Any], Any],
        logger: Callable[[str, int], None],
        update_state_callback: Callable[[], None],
        schedule_resign_popup: Callable[[Any], None],
    ):
        """LeelaManagerを初期化。

        Args:
            config_getter: 設定値を取得するコールバック config(key, default)
            logger: ログ出力コールバック log(message, level)
            update_state_callback: UI状態更新コールバック
            schedule_resign_popup: 投了ヒントポップアップ表示コールバック
        """
        self._config = config_getter
        self._log = logger
        self._update_state = update_state_callback
        self._schedule_resign_popup = schedule_resign_popup

        # Leela engine state
        self.leela_engine: LeelaEngine | None = None
        self._pending_node = None
        self._request_id: int = 0
        self._last_request_time: float = 0.0

        # Resign hint tracking (use node_key: str to avoid GC issues)
        self._resign_hint_shown_keys: set[str] = set()

    def start_engine(self, katrain_for_engine: Any) -> bool:
        """Start Leela engine (no-op if already running).

        Args:
            katrain_for_engine: KaTrainインスタンス（LeelaEngine初期化用）
                Note: LeelaEngineはログ出力のためにkatrainを必要とする

        Returns:
            True if engine started successfully
        """
        if self.leela_engine and self.leela_engine.is_alive():
            return True
        if not self._config("leela/enabled", False):
            return False

        exe_path = self._config("leela/exe_path", "")
        if not exe_path or not os.path.isfile(exe_path):
            from katrain.core.lang import i18n

            self._log(i18n._("leela:error:exe_not_found").format(exe_path or "(empty)"), OUTPUT_ERROR)
            return False

        self.shutdown_engine()
        try:
            leela_config = self._config("leela", {}) or {}
            self.leela_engine = LeelaEngine(katrain_for_engine, leela_config)
            if self.leela_engine.start():
                from katrain.core.lang import i18n

                self._log(i18n._("leela:status:started"), OUTPUT_INFO)
                return True
            self.leela_engine = None
            return False
        except Exception as e:
            self._log(f"Leela error: {e}", OUTPUT_ERROR)
            self.leela_engine = None
            return False

    def shutdown_engine(self) -> None:
        """Shutdown Leela engine."""
        if self.leela_engine:
            with contextlib.suppress(Exception):
                self.leela_engine.shutdown()
            self.leela_engine = None
        self._pending_node = None

    def request_analysis(
        self,
        current_node: Any,
        katrain_for_engine: Any,
        force: bool = False,
    ) -> None:
        """Request Leela analysis for current node (with debounce and duplicate prevention).

        Args:
            current_node: 解析対象のGameNode
            katrain_for_engine: KaTrainインスタンス（エンジン起動用）
            force: 強制的に再解析をリクエストするかどうか（例: スペースキー押下時）
        """
        if not current_node:
            return
        if not self._config("leela/enabled", False):
            return

        # Debounce: prevent rapid consecutive calls
        now = time.time()
        if not force and now - self._last_request_time < 0.3:  # 300ms debounce
            return
        self._last_request_time = now

        # Start engine if needed
        if not self.leela_engine or not self.leela_engine.is_alive():
            if not self.start_engine(katrain_for_engine):
                return

        # Skip if already analyzed or pending
        max_visits = self._config("leela/max_visits", 1000)
        already_analyzed = (
            current_node.leela_analysis
            and current_node.leela_analysis.is_valid
            and current_node.leela_analysis.root_visits >= max_visits
        )
        if not force and already_analyzed:
            return
        if not force and current_node == self._pending_node:
            return
        
        # Note: When force=True, we don't clear existing analysis
        # This keeps candidates visible while waiting for new results

        # Cancel old request
        if self.leela_engine:
            self.leela_engine.cancel_analysis()

        # New request
        self._pending_node = current_node
        self._request_id += 1
        my_request_id = self._request_id

        # Build moves list from current node path (same as KataGoEngine)
        nodes = current_node.nodes_from_root
        moves: list[tuple[str, str]] = []
        for node in nodes:
            for m in node.moves:
                # m is a Move object with .player ("B"/"W") and .gtp() method
                player = m.player
                coord = m.gtp()
                moves.append((player, coord))

        def on_leela_result(result: LeelaPositionEval) -> None:
            # Discard stale results
            if my_request_id != self._request_id:
                return
            k = self._config("leela/loss_scale_k", LEELA_K_DEFAULT)
            with_loss = compute_estimated_loss(result, k=k)

            # Apply candidate limit (Phase 3)
            # -1 = auto/unlimited (no limit)
            max_candidates = self._config("leela/max_candidates", 5)
            if max_candidates > 0 and len(with_loss.candidates) > max_candidates:
                with_loss.candidates = with_loss.candidates[:max_candidates]

            Clock.schedule_once(lambda dt: self._set_analysis(current_node, with_loss))

        if self.leela_engine:
            self.leela_engine.request_analysis(
                moves=moves,
                callback=on_leela_result,
                visits=self._config("leela/max_visits", 1000),
            )

    def _set_analysis(self, node: Any, analysis: LeelaPositionEval) -> None:
        """Set Leela analysis result on UI thread.

        Args:
            node: 解析結果を設定するGameNode
            analysis: Leela解析結果
        """
        if node == self._pending_node:
            self._pending_node = None
        if node:
            node.set_leela_analysis(analysis)
            self._update_state()

        # Check resign hint condition
        self._check_and_show_resign_hint(node)

    @staticmethod
    def _make_node_key(node: Any) -> str:
        """Generate a unique key for a node (GC-safe).

        Uses node.depth + id(node) to distinguish nodes at the same depth
        in variations.

        Args:
            node: GameNode instance

        Returns:
            String key like "45:123456789"
        """
        return f"{node.depth}:{id(node)}"

    def _check_and_show_resign_hint(self, node: Any) -> None:
        """Check resign condition and show popup if met.

        Args:
            node: GameNode that just received analysis
        """
        if node is None:
            return

        # 1. Settings check
        if not self._config("leela/resign_hint_enabled", False):
            return

        # 2. Prevent re-display (use node_key)
        node_key = self._make_node_key(node)
        if node_key in self._resign_hint_shown_keys:
            return

        # 3. Collect recent Leela analysis history
        history = []
        current = node
        consecutive_moves = self._config("leela/resign_consecutive_moves", 3)
        for _ in range(consecutive_moves):
            if not current or not current.leela_analysis:
                break
            history.append(current.leela_analysis)
            current = current.parent

        # 4. Check condition (v4: use max_visits for dynamic threshold)
        result = check_resign_condition(
            history,
            winrate_threshold=self._config("leela/resign_winrate_threshold", 5) / 100,
            consecutive_moves=consecutive_moves,
            max_visits=self._config("leela/max_visits", 1000),
        )

        # 5. Show popup (defensive: always via schedule for UI thread safety)
        if result.should_show_hint and result.is_reliable:
            self._resign_hint_shown_keys.add(node_key)
            self._schedule_resign_popup(result)

    def clear_resign_hint_tracking(self) -> None:
        """Clear resign hint tracking (call on new game)."""
        self._resign_hint_shown_keys.clear()

    def is_node_current(self, node: Any, game_current_node: Any) -> bool:
        """Check if node is the current game node.

        Args:
            node: Node to check
            game_current_node: Current node from game

        Returns:
            True if node is the current node
        """
        return bool(node == game_current_node)
