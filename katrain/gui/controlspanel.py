import time

from kivy.clock import Clock
from kivy.properties import ObjectProperty, OptionProperty
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.floatlayout import MDFloatLayout

from katrain.core.constants import (
    MODE_ANALYZE,
    MODE_PLAY,
    OUTPUT_DEBUG,
    PLAYER_HUMAN,
    STATUS_ANALYSIS,
    STATUS_ERROR,
    AI_DEFAULT,
    PLAYER_AI,
)
from katrain.core.lang import rank_label
from katrain.gui.kivyutils import AnalysisToggle, CollapsablePanel
from katrain.gui.theme import Theme
from katrain.gui.sound import play_sound, stop_sound
from katrain.core.eval_metrics import classify_mistake
from katrain.core.errors import UIStateError


class PlayAnalyzeSelect(MDFloatLayout):
    katrain = ObjectProperty(None)
    mode = OptionProperty(MODE_ANALYZE, options=[MODE_PLAY, MODE_ANALYZE])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初期化時に timer_or_movetree.mode を現在のモードに設定
        Clock.schedule_once(self._init_timer_mode, 0)
        Clock.schedule_once(self.load_ui_state, 1)

    def _init_timer_mode(self, _dt=None):
        """初期化時に timer_or_movetree のモードを設定"""
        if self.katrain and self.katrain.controls:
            self.katrain.controls.timer_or_movetree.mode = self.mode

    def save_ui_state(self):
        ui_state = dict(self.katrain.config("ui_state") or {})
        ui_state[self.mode] = {
            "analysis_controls": {
                id: toggle.active
                for id, toggle in self.katrain.analysis_controls.ids.items()
                if isinstance(toggle, AnalysisToggle)
            },
            "panels": {
                id: (panel.state, panel.option_state)
                for id, panel in self.katrain.controls.ids.items()
                if isinstance(panel, CollapsablePanel)
            },
        }
        # 前回終了時のモードを保存
        ui_state["last_mode"] = self.mode
        self.katrain.set_config_section("ui_state", ui_state)
        self.katrain.save_config("ui_state")

    def load_ui_state(self, _dt=None):
        try:
            state = self.katrain.config(f"ui_state/{self.mode}", {})
            analysis_ids = self.katrain.analysis_controls.ids
            for id, active in state.get("analysis_controls", {}).items():
                if id in analysis_ids:
                    cb = analysis_ids[id].checkbox
                    cb.active = bool(active)
                else:
                    self.katrain.log(f"load_ui_state: unknown id '{id}' in analysis_controls", OUTPUT_DEBUG)
            controls_ids = self.katrain.controls.ids
            for id, (panel_state, button_state) in state.get("panels", {}).items():
                if id in controls_ids:
                    controls_ids[id].set_option_state(button_state)
                    controls_ids[id].state = panel_state
                else:
                    self.katrain.log(f"load_ui_state: unknown id '{id}' in panels", OUTPUT_DEBUG)
        except Exception as e:
            # Startup time - no user notification, DEBUG log only
            if hasattr(self.katrain, "error_handler"):
                self.katrain.error_handler.handle(
                    UIStateError(
                        str(e),
                        user_message="UI state restore failed",
                        context={"mode": self.mode},
                    ),
                    notify_user=False,
                    log_level=OUTPUT_DEBUG,
                )

    def select_mode(self, new_mode):  # actual switch state handler
        if self.mode == new_mode:
            return
        self.save_ui_state()
        self.mode = new_mode
        self.katrain.controls.timer_or_movetree.mode = self.mode
        self.load_ui_state()
        self.katrain.update_state()  # for lock ai even if nothing changed

    def switch_ui_mode(self):  # on tab press, fake ui click and trigger everything top down
        if self.mode == MODE_PLAY:
            Clock.schedule_once(
                lambda _dt: self.analyze.trigger_action(duration=0)
            )  # normal trigger does not cross thread
        else:
            Clock.schedule_once(lambda _dt: self.play.trigger_action(duration=0))


class ControlsPanel(BoxLayout):
    katrain = ObjectProperty(None)
    button_controls = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(ControlsPanel, self).__init__(**kwargs)
        self.status_state = (None, -1e9, None)
        self.active_comment_node = None
        self.last_timer_update = (None, 0, False)
        self.beep_start = 5.2
        self.timer_interval = 0.07

        # Phase 22: タイマーイベントを追跡（cleanup用）
        self._timer_event = Clock.schedule_interval(self.update_timer, self.timer_interval)

    def cleanup(self) -> None:
        """アプリ終了時のクリーンアップ（Phase 22）

        KaTrainGui.cleanup() から呼び出される。
        """
        if self._timer_event:
            self._timer_event.cancel()
            self._timer_event = None

    def update_players(self, *_args):
        for bw, player_info in self.katrain.players_info.items():
            self.players[bw].player_type = player_info.player_type
            self.players[bw].player_subtype = player_info.player_subtype
            self.players[bw].name = player_info.name
            self.players[bw].rank = (
                player_info.sgf_rank
                if player_info.player_type == PLAYER_HUMAN
                else rank_label(player_info.calculated_rank)
            )

    def set_status(self, msg, status_type, at_node=None, check_level=True):
        at_node = at_node or self.katrain and self.katrain.game and self.katrain.game.current_node
        if (
            at_node != self.status_state[2]
            or not check_level
            or int(status_type) >= int(self.status_state[1])
            or msg == ""
        ):
            if self.status_state != (msg, status_type, at_node):  # prevent loop if error in update eval
                Clock.schedule_once(self.update_evaluation, 0)
            self.status_state = (msg, status_type, at_node)
            self.status.text = msg
            self.status.error = status_type == STATUS_ERROR

    # handles showing completed analysis and score graph
    def update_evaluation(self, *_args):
        katrain = self.katrain
        game = katrain and katrain.game
        if not game:
            return
        current_node, move = game.current_node, game.current_node.move
        if (
            game.current_node is not self.status_state[2]
            and not (self.status_state[1] == STATUS_ERROR and self.status_state[2] is None)
        ) or (
            self.katrain.engine.is_idle() and self.status_state[1] == STATUS_ANALYSIS
        ):  # clear status if node changes, except startup errors on root. also clear analysis message when no queries
            self.status.text = ""
            self.status_state = (None, -1e9, None)

        last_player_was_ai_playing_human = katrain.last_player_info.ai and katrain.next_player_info.human
        both_players_are_robots = katrain.last_player_info.ai and katrain.next_player_info.ai

        self.active_comment_node = current_node
        if katrain.play_analyze_mode == MODE_PLAY and last_player_was_ai_playing_human:
            if katrain.next_player_info.being_taught and current_node.children and current_node.children[-1].auto_undo:
                self.active_comment_node = current_node.children[-1]
            elif current_node.parent:
                self.active_comment_node = current_node.parent
        elif both_players_are_robots and not current_node.analysis_exists and current_node.parent:
            self.active_comment_node = current_node.parent

        lock_ai = katrain.config("trainer/lock_ai") and katrain.play_analyze_mode == MODE_PLAY
        details = self.info.detailed and not lock_ai
        info = ""

        if move or current_node.is_root:
            info += self.active_comment_node.comment(
                teach=katrain.players_info[self.active_comment_node.player].being_taught, details=details
            )

        if self.active_comment_node.analysis_exists:
            # 解析結果あり → stats を埋める
            self.stats.score = self.active_comment_node.format_score() or ""
            self.stats.winrate = self.active_comment_node.format_winrate() or ""
            self.stats.points_lost = self.active_comment_node.points_lost
            self.stats.player = self.active_comment_node.player
        else:
            # 解析結果なし → stats は空
            self.stats.score = ""
            self.stats.winrate = ""
            self.stats.points_lost = None
            self.stats.player = ""

        # ------------------------------------------------------------
        # ミス分類 + 局面難易度の簡易サマリを Details パネル（info）に追加
        # ------------------------------------------------------------
        detail_lines = []

        # 1) ミス分類（points_lost ベース）
        pts = getattr(self.active_comment_node, "points_lost", None)
        if pts is not None:
            score_loss = max(float(pts), 0.0)
            mc = classify_mistake(score_loss=score_loss, winrate_loss=None)

            label_map = {
                "GOOD": "良",
                "INACCURACY": "軽",
                "MISTAKE": "悪",
                "BLUNDER": "大悪",
            }
            mc_name = getattr(mc, "name", "")
            mc_label = label_map.get(mc_name, "-")

            if mc_label != "-" or score_loss > 0:
                if score_loss > 0:
                    detail_lines.append(f"ミス: {mc_label}（{score_loss:.1f}目損）")
                else:
                    detail_lines.append(f"ミス: {mc_label}")

        # 2) 局面難易度（親ノードの candidate_moves からざっくり評価）
        parent = getattr(self.active_comment_node, "parent", None)
        candidate_moves = getattr(parent, "candidate_moves", None) if parent is not None else None
        if candidate_moves:
            good_rel_threshold = 1.0
            near_rel_threshold = 2.0

            good_moves = []
            near_moves = []

            for mv in candidate_moves:
                rel = mv.get("relativePointsLost")
                if rel is None:
                    rel = mv.get("pointsLost")
                if rel is None:
                    continue

                rel_f = float(rel)
                if rel_f <= good_rel_threshold:
                    good_moves.append(rel_f)
                if rel_f <= near_rel_threshold:
                    near_moves.append(rel_f)

            difficulty_label = None
            difficulty_score = None

            if good_moves or near_moves:
                n_good = len(good_moves)
                n_near = len(near_moves)

                if n_good <= 1 and n_near <= 2:
                    difficulty_label = "一択"
                    difficulty_score = 1.0
                elif n_good <= 2:
                    difficulty_label = "狭い"
                    difficulty_score = 0.8
                elif n_good >= 4 or n_near >= 6:
                    difficulty_label = "広い"
                    difficulty_score = 0.2
                else:
                    difficulty_label = "普通"
                    difficulty_score = 0.5

            if difficulty_label:
                heading = "手の自由度"
                if difficulty_score is not None:
                    detail_lines.append(f"{heading}: {difficulty_label}（{difficulty_score:.2f}）")
                else:
                    detail_lines.append(f"{heading}: {difficulty_label}")

        # 3) 局面難易度（Phase 12.5）
        # active_comment_node 自体の難易度を表示（既存ミス分類と同じノード）
        if self.active_comment_node and self.active_comment_node.analysis_exists:
            from katrain.core.analysis import (
                difficulty_metrics_from_node,
                format_difficulty_metrics,
            )
            metrics = difficulty_metrics_from_node(self.active_comment_node)
            difficulty_lines = format_difficulty_metrics(metrics)
            detail_lines.extend(difficulty_lines)

        # 4) info テキストの末尾に追記
        if detail_lines:
            if info:
                info += "\n"
            info += "\n".join(detail_lines)

        # 既存の更新処理（必ず実行される位置に戻す）
        self.graph.update_value(current_node)
        self.note.text = current_node.note
        self.info.text = info

    def update_timer(self, _dt):
        game = self.katrain and self.katrain.game
        current_node = game and self.katrain.game.current_node
        if current_node:
            last_update_node, last_update_time, beeping = self.last_timer_update
            new_beeping = beeping
            now = time.time()
            main_time = self.katrain.config("timer/main_time", 0) * 60
            byo_len = max(1, self.katrain.config("timer/byo_length"))
            byo_num = max(1, self.katrain.config("timer/byo_periods"))
            sounds_on = self.katrain.config("timer/sound")
            player = self.katrain.next_player_info
            ai = player.ai
            used_period = False

            min_use = self.katrain.config("timer/minimal_use", 0)
            boing_at_remaining = byo_len - min_use
            main_time_remaining = main_time - game.main_time_used

            if not self.timer.paused and not ai and self.katrain.play_analyze_mode == MODE_PLAY:
                if last_update_node == current_node and not current_node.children:
                    if main_time_remaining > 0:
                        game.main_time_used += now - last_update_time
                    else:
                        current_node.time_used += now - last_update_time
                else:
                    current_node.time_used = 0
                    new_beeping = False
                time_remaining = byo_len - current_node.time_used
                while time_remaining < 0 and player.periods_used < byo_num:
                    current_node.time_used -= byo_len
                    time_remaining += byo_len
                    player.periods_used += 1
                    used_period = True

                if (
                    self.beep_start - 2 * self.timer_interval < time_remaining < self.beep_start
                    and player.periods_used < byo_num
                ):
                    new_beeping = True
                elif time_remaining > self.beep_start:
                    new_beeping = False

                if (
                    min_use
                    and not new_beeping
                    and boing_at_remaining - self.timer_interval
                    < time_remaining
                    < boing_at_remaining + self.timer_interval
                    and player.periods_used < byo_num
                ):
                    play_sound(Theme.MINIMUM_TIME_PASSED_SOUND, volume=0.1)

            else:
                new_beeping = False

            if player.periods_used == byo_num:
                time_remaining = 0
            else:
                time_remaining = byo_len - current_node.time_used
            periods_rem = byo_num - player.periods_used

            if sounds_on:
                if beeping and not new_beeping and not used_period:
                    stop_sound(Theme.COUNTDOWN_SOUND)
                elif not beeping and new_beeping:
                    play_sound(Theme.COUNTDOWN_SOUND, volume=0.5 if periods_rem > 1 else 1)

            self.last_timer_update = (current_node, now, new_beeping)

            if main_time_remaining > 0:
                self.timer.state = (main_time_remaining, None, ai)
            else:
                self.timer.state = (max(0, time_remaining), max(0, periods_rem), ai)
