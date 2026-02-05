"""Phase 105: StateNotifier発火ポイント統合テスト

テスト戦略:
- notify_helpers.py のヘルパー関数を直接テスト（Kivy不要）
- save_config() はunbound method + スタブでテスト（ロジック複製なし）
- 統合テスト（KaTrainBase初期化）は @pytest.mark.integration でマーク
- 全テストはCI/ヘッドレス環境で実行可能
"""

from unittest.mock import MagicMock, patch

import pytest

from katrain.core.state import Event, EventType, StateNotifier

# =============================================================================
# Stub / Fixture
# =============================================================================


class ConfigSaveStub:
    """Minimal stub for testing save_config() via unbound method.

    Provides attributes required by KaTrainBase.save_config():
    - state_notifier: StateNotifier instance (via property)
    - _config: dict
    - _config_store: mock with put() method
    - log: callable

    Note: Does NOT duplicate save_config() logic. Tests call
    KaTrainBase.save_config(stub) to use the real implementation.
    """

    def __init__(self):
        self.__state_notifier = StateNotifier()
        self._config = {"general": {"version": "1.0"}}
        self._config_store = MagicMock()
        self.log = MagicMock()

    @property
    def state_notifier(self) -> StateNotifier:
        return self.__state_notifier


@pytest.fixture
def config_stub():
    """Provide a lightweight stub for CONFIG_UPDATED tests."""
    return ConfigSaveStub()


# =============================================================================
# CONFIG_UPDATED Tests (Unbound Method Pattern)
# =============================================================================


class TestConfigUpdatedNotification:
    """CONFIG_UPDATED発火テスト（unbound method + スタブ使用）"""

    def test_save_config_success_fires_config_updated(self, config_stub):
        """save_config()成功時にCONFIG_UPDATEDを発火する"""
        from katrain.core.base_katrain import KaTrainBase

        received: list[Event] = []
        config_stub.state_notifier.subscribe(EventType.CONFIG_UPDATED, received.append)

        with patch("katrain.core.base_katrain._save_config_with_errors", return_value=[]):
            # Unbound method call: use real save_config() implementation
            KaTrainBase.save_config(config_stub, key="general")

        assert len(received) == 1
        assert received[0].event_type == EventType.CONFIG_UPDATED
        assert received[0].payload["key"] == "general"

    def test_save_config_failure_does_not_fire(self, config_stub):
        """save_config()失敗時は通知しない"""
        from katrain.core.base_katrain import KaTrainBase

        received: list[Event] = []
        config_stub.state_notifier.subscribe(EventType.CONFIG_UPDATED, received.append)

        with patch(
            "katrain.core.base_katrain._save_config_with_errors",
            return_value=["general"],
        ):
            KaTrainBase.save_config(config_stub, key="general")

        assert len(received) == 0

    def test_save_config_key_none_in_payload(self, config_stub):
        """key=Noneの場合、payload["key"]はNone"""
        from katrain.core.base_katrain import KaTrainBase

        received: list[Event] = []
        config_stub.state_notifier.subscribe(EventType.CONFIG_UPDATED, received.append)

        with patch("katrain.core.base_katrain._save_config_with_errors", return_value=[]):
            KaTrainBase.save_config(config_stub, key=None)

        assert len(received) == 1
        assert received[0].payload["key"] is None


class TestConfigUpdatedIntegration:
    """KaTrainBase.save_config()の統合テスト（実インスタンス使用）

    Note: @pytest.mark.integration は情報マーカー。
    デフォルトCIに含まれる（Option B採用）。
    """

    @pytest.mark.integration
    def test_real_save_config_calls_notify(self):
        """KaTrainBase.save_config()が実際にnotify()を呼ぶことを検証

        Note: This test initializes KaTrainBase, which may be slow.
        Marker is informational; test runs in default CI.
        """
        from katrain.core.base_katrain import KaTrainBase

        base = KaTrainBase(force_package_config=True, debug_level=0)
        received: list[Event] = []
        base.state_notifier.subscribe(EventType.CONFIG_UPDATED, received.append)

        with patch("katrain.core.base_katrain._save_config_with_errors", return_value=[]):
            base.save_config(key="test")

        # このassertが失敗 = notify()呼び出しが欠けている
        assert len(received) == 1, "CONFIG_UPDATED notification missing in KaTrainBase.save_config()"


# =============================================================================
# ANALYSIS_COMPLETE Tests (Helper Function)
# =============================================================================


class TestAnalysisCompleteHelper:
    """maybe_notify_analysis_complete() ヘルパー関数テスト

    Note: All calls use keyword arguments (required by function signature).
    """

    def test_fires_on_complete_with_results(self):
        """完了 + 結果ありで発火"""
        from katrain.core.notify_helpers import maybe_notify_analysis_complete

        notifier = StateNotifier()
        received: list[Event] = []
        notifier.subscribe(EventType.ANALYSIS_COMPLETE, received.append)

        mock_katrain = MagicMock()
        mock_katrain.state_notifier = notifier

        result = maybe_notify_analysis_complete(
            mock_katrain,
            partial_result=False,
            results_exist=True,
            query_id="QUERY:42",
        )

        assert result is True
        assert len(received) == 1
        assert received[0].event_type == EventType.ANALYSIS_COMPLETE
        assert received[0].payload["query_id"] == "QUERY:42"

    def test_does_not_fire_on_partial(self):
        """partial_result=Trueでは発火しない"""
        from katrain.core.notify_helpers import maybe_notify_analysis_complete

        notifier = StateNotifier()
        received: list[Event] = []
        notifier.subscribe(EventType.ANALYSIS_COMPLETE, received.append)

        mock_katrain = MagicMock()
        mock_katrain.state_notifier = notifier

        result = maybe_notify_analysis_complete(
            mock_katrain,
            partial_result=True,
            results_exist=True,
            query_id="QUERY:42",
        )

        assert result is False
        assert len(received) == 0

    def test_does_not_fire_when_no_results(self):
        """results_exist=Falseでは発火しない"""
        from katrain.core.notify_helpers import maybe_notify_analysis_complete

        notifier = StateNotifier()
        received: list[Event] = []
        notifier.subscribe(EventType.ANALYSIS_COMPLETE, received.append)

        mock_katrain = MagicMock()
        mock_katrain.state_notifier = notifier

        result = maybe_notify_analysis_complete(
            mock_katrain,
            partial_result=False,
            results_exist=False,
            query_id="QUERY:42",
        )

        assert result is False
        assert len(received) == 0

    def test_does_not_fire_when_query_id_none(self):
        """query_id=Noneでは発火しない"""
        from katrain.core.notify_helpers import maybe_notify_analysis_complete

        notifier = StateNotifier()
        received: list[Event] = []
        notifier.subscribe(EventType.ANALYSIS_COMPLETE, received.append)

        mock_katrain = MagicMock()
        mock_katrain.state_notifier = notifier

        result = maybe_notify_analysis_complete(
            mock_katrain,
            partial_result=False,
            results_exist=True,
            query_id=None,
        )

        assert result is False
        assert len(received) == 0

    def test_handles_missing_notifier(self):
        """state_notifierがない場合もエラーなし"""
        from katrain.core.notify_helpers import maybe_notify_analysis_complete

        mock_katrain = MagicMock(spec=[])  # state_notifier属性なし

        result = maybe_notify_analysis_complete(
            mock_katrain,
            partial_result=False,
            results_exist=True,
            query_id="QUERY:42",
        )

        assert result is False

    def test_query_id_preserved_in_payload(self):
        """query_idがpayloadに正確に保存される"""
        from katrain.core.notify_helpers import maybe_notify_analysis_complete

        notifier = StateNotifier()
        received: list[Event] = []
        notifier.subscribe(EventType.ANALYSIS_COMPLETE, received.append)

        mock_katrain = MagicMock()
        mock_katrain.state_notifier = notifier

        maybe_notify_analysis_complete(
            mock_katrain,
            partial_result=False,
            results_exist=True,
            query_id="QUERY:special-123",
        )

        assert received[0].payload["query_id"] == "QUERY:special-123"


# =============================================================================
# GAME_CHANGED Tests (Helper Function)
# =============================================================================


class TestGameChangedHelper:
    """notify_game_changed() ヘルパー関数テスト（Kivy不要）

    Note: source is a keyword-only argument (required by function signature).
    """

    def test_fires_when_notifier_exists(self):
        """state_notifierが存在する場合、発火する"""
        from katrain.core.notify_helpers import notify_game_changed

        notifier = StateNotifier()
        received: list[Event] = []
        notifier.subscribe(EventType.GAME_CHANGED, received.append)

        mock_ctx = MagicMock()
        mock_ctx.state_notifier = notifier

        result = notify_game_changed(mock_ctx, source="new_game")

        assert result is True
        assert len(received) == 1
        assert received[0].event_type == EventType.GAME_CHANGED
        assert received[0].payload["source"] == "new_game"

    def test_handles_missing_notifier(self):
        """state_notifierがない場合もエラーなし"""
        from katrain.core.notify_helpers import notify_game_changed

        mock_ctx = MagicMock(spec=[])  # state_notifier属性なし

        result = notify_game_changed(mock_ctx, source="new_game")

        assert result is False

    def test_source_preserved_in_payload(self):
        """sourceがpayloadに正確に保存される"""
        from katrain.core.notify_helpers import notify_game_changed

        notifier = StateNotifier()
        received: list[Event] = []
        notifier.subscribe(EventType.GAME_CHANGED, received.append)

        mock_ctx = MagicMock()
        mock_ctx.state_notifier = notifier

        notify_game_changed(mock_ctx, source="load_sgf")

        assert received[0].payload["source"] == "load_sgf"


# =============================================================================
# Integration: Verify helpers are importable from expected modules
# =============================================================================


class TestHelperImports:
    """ヘルパー関数が正しいモジュールからインポート可能"""

    def test_notify_helpers_module_exists(self):
        """katrain.core.notify_helpers が存在する"""
        from katrain.core import notify_helpers

        assert hasattr(notify_helpers, "notify_game_changed")
        assert hasattr(notify_helpers, "maybe_notify_analysis_complete")

    def test_helpers_do_not_import_kivy(self):
        """notify_helpers.pyはKivyをインポートしない

        Note: Always runs subprocess (fresh Python environment).
        Parent process Kivy state is irrelevant.
        Timeout increased for slow CI/Windows environments.
        """
        import subprocess
        import sys

        code = (
            "import sys; "
            "from katrain.core.notify_helpers import notify_game_changed; "
            "kivy_mods = [m for m in sys.modules if m.startswith('kivy')]; "
            "sys.exit(1 if kivy_mods else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,  # Increased for slow CI/Windows
        )
        assert result.returncode == 0, (
            f"Kivy imported by notify_helpers:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
