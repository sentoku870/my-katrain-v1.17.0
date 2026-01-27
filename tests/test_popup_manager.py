"""PopupManagerのユニットテスト（Phase 75）

Kivy完全非依存:
- PopupManagerのみをインスタンス化
- 全依存はモック/スタブで注入
- 内部状態（_popups等）へのアクセスを避け、ブラックボックステストを実現
"""
import pytest

from katrain.core.constants import OUTPUT_DEBUG
from katrain.gui.managers.popup_manager import PopupManager


class MockPopup:
    """ポップアップのモック"""

    def __init__(self):
        self.open_call_count = 0
        self.content = MockContent()

    def open(self):
        self.open_call_count += 1


class MockContent:
    """ポップアップコンテンツのモック"""

    pass


def create_manager(
    factory_call_counts=None,
    created_popups=None,  # ファクトリが作成したポップアップを外部キャプチャ
    get_popup_open=None,
    is_engine_recovery_fn=None,
    pause_timer_calls=None,
    on_new_game_calls=None,
    log_calls=None,
):
    """テスト用PopupManagerファクトリ

    Args:
        factory_call_counts: ファクトリ呼び出し回数を記録
        created_popups: 作成されたポップアップを外部リストにキャプチャ
        get_popup_open: ポップアップ取得関数（None時はlambda: Noneを使用）
        is_engine_recovery_fn: EngineRecoveryPopup判定関数（None時はlambda p: Falseを使用）
        pause_timer_calls: pause_timer呼び出しを記録
        on_new_game_calls: on_new_game_opened呼び出しを記録
        log_calls: ログ呼び出しを記録
    """
    if factory_call_counts is None:
        factory_call_counts = {
            "new_game": 0,
            "timer": 0,
            "teacher": 0,
            "ai": 0,
            "engine": 0,
        }
    if created_popups is None:
        created_popups = {
            "new_game": [],
            "timer": [],
            "teacher": [],
            "ai": [],
            "engine": [],
        }
    if pause_timer_calls is None:
        pause_timer_calls = []
    if on_new_game_calls is None:
        on_new_game_calls = []
    if log_calls is None:
        log_calls = []
    if get_popup_open is None:
        get_popup_open = lambda: None
    if is_engine_recovery_fn is None:
        is_engine_recovery_fn = lambda p: False

    def make_factory(key):
        def factory(*args):
            factory_call_counts[key] += 1
            popup = MockPopup()
            created_popups[key].append(popup)
            return popup

        return factory

    return (
        PopupManager(
            create_new_game_popup=make_factory("new_game"),
            create_timer_popup=make_factory("timer"),
            create_teacher_popup=make_factory("teacher"),
            create_ai_popup=make_factory("ai"),
            create_engine_recovery_popup=make_factory("engine"),
            get_popup_open=get_popup_open,
            is_engine_recovery_popup=is_engine_recovery_fn,
            pause_timer=lambda: pause_timer_calls.append(True),
            on_new_game_opened=lambda p: on_new_game_calls.append(p),
            logger=lambda msg, level: log_calls.append((msg, level)),
            log_level_debug=OUTPUT_DEBUG,
        ),
        factory_call_counts,
        created_popups,
        pause_timer_calls,
        on_new_game_calls,
        log_calls,
    )


class TestCacheManagement:
    """キャッシュ管理テスト"""

    def test_first_open_creates_popup_via_factory(self):
        """初回openでファクトリが1回呼ばれる"""
        # Arrange
        manager, counts, _, _, _, _ = create_manager()

        # Act
        manager.open_new_game_popup()

        # Assert
        assert counts["new_game"] == 1

    def test_second_open_reuses_cache_no_factory_call(self):
        """2回目openではファクトリは呼ばれない（キャッシュ再利用）"""
        # Arrange
        manager, counts, _, _, _, _ = create_manager()

        # Act
        manager.open_new_game_popup()
        manager.open_new_game_popup()

        # Assert
        assert counts["new_game"] == 1  # ファクトリは1回のみ

    def test_popup_open_called_on_every_request(self):
        """open()は毎回呼ばれる（ブラックボックステスト）"""
        # Arrange
        created_popups = {
            "new_game": [],
            "timer": [],
            "teacher": [],
            "ai": [],
            "engine": [],
        }
        manager, _, created_popups, _, _, _ = create_manager(created_popups=created_popups)

        # Act
        manager.open_new_game_popup()  # 1回目: ファクトリ呼び出し + open()
        manager.open_new_game_popup()  # 2回目: キャッシュ再利用 + open()

        # Assert: キャプチャしたポップアップでopen回数を確認
        assert len(created_popups["new_game"]) == 1  # ファクトリは1回のみ
        captured_popup = created_popups["new_game"][0]
        assert captured_popup.open_call_count == 2  # open()は2回呼ばれる

    def test_each_popup_type_has_separate_cache(self):
        """各ポップアップタイプは独立したキャッシュを持つ"""
        # Arrange
        manager, counts, _, _, _, _ = create_manager()

        # Act
        manager.open_new_game_popup()
        manager.open_timer_popup()
        manager.open_teacher_popup()
        manager.open_ai_popup()

        # Assert
        assert counts["new_game"] == 1
        assert counts["timer"] == 1
        assert counts["teacher"] == 1
        assert counts["ai"] == 1


class TestTimerPause:
    """タイマー一時停止テスト"""

    def test_open_new_game_pauses_timer(self):
        """open_new_game_popup()はタイマーを一時停止する"""
        # Arrange
        manager, _, _, pause_calls, _, _ = create_manager()

        # Act
        manager.open_new_game_popup()

        # Assert
        assert len(pause_calls) == 1

    def test_open_timer_pauses_timer(self):
        """open_timer_popup()はタイマーを一時停止する"""
        # Arrange
        manager, _, _, pause_calls, _, _ = create_manager()

        # Act
        manager.open_timer_popup()

        # Assert
        assert len(pause_calls) == 1

    def test_open_teacher_pauses_timer(self):
        """open_teacher_popup()はタイマーを一時停止する"""
        # Arrange
        manager, _, _, pause_calls, _, _ = create_manager()

        # Act
        manager.open_teacher_popup()

        # Assert
        assert len(pause_calls) == 1

    def test_open_ai_pauses_timer(self):
        """open_ai_popup()はタイマーを一時停止する"""
        # Arrange
        manager, _, _, pause_calls, _, _ = create_manager()

        # Act
        manager.open_ai_popup()

        # Assert
        assert len(pause_calls) == 1

    def test_engine_recovery_does_not_pause_timer(self):
        """open_engine_recovery_popup()はタイマーを一時停止しない（意図的）"""
        # Arrange
        manager, _, _, pause_calls, _, _ = create_manager()

        # Act
        manager.open_engine_recovery_popup("error", "E001")

        # Assert: pause_timerは呼ばれない
        assert len(pause_calls) == 0

    def test_pause_timer_called_on_every_open(self):
        """毎回のopen呼び出しでpause_timerが呼ばれる"""
        # Arrange
        manager, _, _, pause_calls, _, _ = create_manager()

        # Act
        manager.open_new_game_popup()
        manager.open_new_game_popup()

        # Assert
        assert len(pause_calls) == 2


class TestTeacherAndAiPopups:
    """Teacher/AIポップアップの追加テスト"""

    def test_teacher_factory_called_once_cache_reused(self):
        """teacherポップアップ: ファクトリは1回、キャッシュ再利用"""
        # Arrange
        created_popups = {
            "new_game": [],
            "timer": [],
            "teacher": [],
            "ai": [],
            "engine": [],
        }
        manager, counts, created_popups, _, _, _ = create_manager(
            created_popups=created_popups
        )

        # Act
        manager.open_teacher_popup()
        manager.open_teacher_popup()

        # Assert
        assert counts["teacher"] == 1  # ファクトリは1回のみ
        assert len(created_popups["teacher"]) == 1
        assert created_popups["teacher"][0].open_call_count == 2  # openは2回

    def test_ai_factory_called_once_cache_reused(self):
        """AIポップアップ: ファクトリは1回、キャッシュ再利用"""
        # Arrange
        created_popups = {
            "new_game": [],
            "timer": [],
            "teacher": [],
            "ai": [],
            "engine": [],
        }
        manager, counts, created_popups, _, _, _ = create_manager(
            created_popups=created_popups
        )

        # Act
        manager.open_ai_popup()
        manager.open_ai_popup()

        # Assert
        assert counts["ai"] == 1  # ファクトリは1回のみ
        assert len(created_popups["ai"]) == 1
        assert created_popups["ai"][0].open_call_count == 2  # openは2回

    def test_timer_factory_called_once_cache_reused(self):
        """timerポップアップ: ファクトリは1回、キャッシュ再利用"""
        # Arrange
        created_popups = {
            "new_game": [],
            "timer": [],
            "teacher": [],
            "ai": [],
            "engine": [],
        }
        manager, counts, created_popups, _, _, _ = create_manager(
            created_popups=created_popups
        )

        # Act
        manager.open_timer_popup()
        manager.open_timer_popup()

        # Assert
        assert counts["timer"] == 1  # ファクトリは1回のみ
        assert len(created_popups["timer"]) == 1
        assert created_popups["timer"][0].open_call_count == 2  # openは2回


class TestNewGamePostOpenHook:
    """新規対局ポップアップの後処理フックテスト"""

    def test_on_new_game_opened_called_with_popup(self):
        """open後にon_new_game_openedがポップアップ引数で呼ばれる（ブラックボックス）"""
        # Arrange
        created_popups = {
            "new_game": [],
            "timer": [],
            "teacher": [],
            "ai": [],
            "engine": [],
        }
        manager, _, created_popups, _, on_new_game_calls, _ = create_manager(
            created_popups=created_popups
        )

        # Act
        manager.open_new_game_popup()

        # Assert
        assert len(on_new_game_calls) == 1
        # キャプチャしたポップアップと同一であることを確認
        assert on_new_game_calls[0] is created_popups["new_game"][0]


class TestEngineRecoveryDuplicatePrevention:
    """エンジン復旧ポップアップ重複防止テスト"""

    def test_opens_when_no_popup_open(self):
        """ポップアップが開いていない場合は開く"""
        # Arrange
        manager, counts, _, _, _, _ = create_manager(get_popup_open=lambda: None)

        # Act
        manager.open_engine_recovery_popup("error", "E001")

        # Assert
        assert counts["engine"] == 1

    def test_opens_when_different_popup_open(self):
        """異なるポップアップが開いている場合は開く"""
        # Arrange
        other_popup = MockPopup()
        manager, counts, _, _, _, _ = create_manager(
            get_popup_open=lambda: other_popup,
            is_engine_recovery_fn=lambda p: False,  # EngineRecoveryPopupではない
        )

        # Act
        manager.open_engine_recovery_popup("error", "E001")

        # Assert
        assert counts["engine"] == 1

    def test_prevents_duplicate_when_engine_recovery_already_open(self):
        """EngineRecoveryPopupが既に開いている場合は開かない"""
        # Arrange
        existing_popup = MockPopup()
        created_popups = {
            "new_game": [],
            "timer": [],
            "teacher": [],
            "ai": [],
            "engine": [],
        }
        manager, counts, created_popups, _, _, log_calls = create_manager(
            created_popups=created_popups,
            get_popup_open=lambda: existing_popup,
            is_engine_recovery_fn=lambda p: True,  # 既にEngineRecoveryPopup
        )

        # Act
        manager.open_engine_recovery_popup("new error", "E002")

        # Assert
        assert counts["engine"] == 0  # ファクトリは呼ばれない
        assert len(created_popups["engine"]) == 0  # ポップアップは作成されていない

    def test_logs_when_duplicate_prevented(self):
        """重複防止時にログが出力される（注入したレベルが転送される）"""
        # Arrange
        existing_popup = MockPopup()
        manager, _, _, _, _, log_calls = create_manager(
            get_popup_open=lambda: existing_popup, is_engine_recovery_fn=lambda p: True
        )

        # Act
        manager.open_engine_recovery_popup("new error message", "E002")

        # Assert
        assert len(log_calls) == 1
        log_msg = log_calls[0][0]
        assert "already open" in log_msg
        assert "code=E002" in log_msg  # エラーコードが含まれる
        assert log_calls[0][1] == OUTPUT_DEBUG  # 注入した定数と一致


class TestEngineRecoveryAfterClose:
    """エンジン復旧ポップアップ: クローズ後の再オープンテスト"""

    def test_creates_new_popup_after_previous_closed(self):
        """前回のポップアップがクローズされた後は新しいポップアップを作成"""
        # Arrange
        # 状態を追跡: 最初はエンジン復旧ポップアップが開いている → 閉じる → 再度開く
        popup_state = {"current": None, "is_engine_recovery": False}

        def get_popup_open():
            return popup_state["current"]

        def is_engine_recovery_fn(p):
            return popup_state["is_engine_recovery"]

        manager, counts, _, _, _, _ = create_manager(
            get_popup_open=get_popup_open, is_engine_recovery_fn=is_engine_recovery_fn
        )

        # Act 1: 最初のエンジン復旧ポップアップを開く
        manager.open_engine_recovery_popup("error1", "E001")
        assert counts["engine"] == 1

        # シミュレート: ポップアップが開いている状態
        popup_state["current"] = MockPopup()
        popup_state["is_engine_recovery"] = True

        # Act 2: 既に開いているので2回目は開かない
        manager.open_engine_recovery_popup("error2", "E002")
        assert counts["engine"] == 1  # 変わらず

        # シミュレート: ユーザーがポップアップを閉じた
        popup_state["current"] = None
        popup_state["is_engine_recovery"] = False

        # Act 3: 閉じた後は新しいポップアップを作成
        manager.open_engine_recovery_popup("error3", "E003")

        # Assert
        assert counts["engine"] == 2  # クローズ後に新規作成


class TestLogTruncation:
    """ログメッセージ短縮テスト"""

    def test_long_error_message_is_truncated_in_log(self):
        """長いエラーメッセージはログで短縮される"""
        # Arrange
        existing_popup = MockPopup()
        log_calls = []
        manager, _, _, _, _, log_calls = create_manager(
            get_popup_open=lambda: existing_popup,
            is_engine_recovery_fn=lambda p: True,
            log_calls=log_calls,
        )

        # Act - 300文字のエラーメッセージ
        long_message = "x" * 300
        manager.open_engine_recovery_popup(long_message, "E001")

        # Assert
        log_msg = log_calls[0][0]
        # メッセージ部分が200文字以下に短縮されている
        assert len(log_msg) < 300  # 全体が短くなっている

    def test_newlines_removed_from_log(self):
        """ログメッセージから改行が除去される"""
        # Arrange
        existing_popup = MockPopup()
        log_calls = []
        manager, _, _, _, _, log_calls = create_manager(
            get_popup_open=lambda: existing_popup,
            is_engine_recovery_fn=lambda p: True,
            log_calls=log_calls,
        )

        # Act
        manager.open_engine_recovery_popup("line1\nline2\nline3", "E001")

        # Assert
        log_msg = log_calls[0][0]
        assert "\n" not in log_msg
