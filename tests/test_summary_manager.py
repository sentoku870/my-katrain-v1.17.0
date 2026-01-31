"""SummaryManagerのユニットテスト（Phase 96）

テストスコープ:
- インポート・インスタンス化: Kivy不要
- ConfigManager連携: Kivy不要
- Pure関数ラッパー（scan_player_names, categorize_games_by_stats等）: Kivy不要
- UI実行メソッド（do_export_summary等）: Kivy必要のためスキップ

Note: これはUI統合テストではなく、配線の正確性を検証するWiring test

重要: loggerコールバックのアリティ
- downstream関数は log_fn(message, level) で常に2引数呼び出し
- テストでは lambda msg, lvl: None または lambda msg, lvl=0: None のどちらも使用可能
"""

import pytest
from unittest.mock import MagicMock, patch


# ========== テスト用ヘルパー ==========

def make_test_logger():
    """テスト用のloggerを作成（呼び出し記録付き）

    downstream関数は log_fn(message, level) で常に2引数呼び出しのため、
    2引数を受け取れるloggerが必要。デフォルト値(lvl=0)は任意。
    """
    calls = []
    def logger(msg: str, lvl: int = 0) -> None:
        calls.append((msg, lvl))
    logger.calls = calls
    return logger


class TestSummaryManagerImport:
    """インポート・インスタンス化テスト（Kivy不要）"""

    def test_import_does_not_require_kivy(self):
        """SummaryManagerのインポートがKivyを必要としない"""
        # This import should not trigger Kivy imports
        from katrain.gui.managers.summary_manager import SummaryManager

        assert SummaryManager is not None

    def test_instantiation_without_kivy(self):
        """SummaryManagerのインスタンス化がKivyを必要としない"""
        from katrain.gui.managers.summary_manager import SummaryManager

        ctx = MagicMock()
        config_manager = MagicMock()
        config_manager.load_export_settings.return_value = {}

        manager = SummaryManager(
            get_ctx=lambda: ctx,
            get_engine=lambda: None,
            get_config=lambda k, d=None: d,
            config_manager=config_manager,
            logger=make_test_logger(),  # 2引数対応logger
        )

        assert manager is not None
        assert manager._get_ctx() is ctx

    def test_managers_package_lazy_import(self):
        """SummaryManagerがmanagersパッケージから遅延インポート可能"""
        from katrain.gui.managers import SummaryManager

        assert SummaryManager is not None


class TestSummaryManagerConfigAccess:
    """ConfigManager連携テスト（Kivy不要）"""

    def test_load_export_settings_delegates_to_config_manager(self):
        """_load_export_settings()がConfigManagerへ委譲"""
        from katrain.gui.managers.summary_manager import SummaryManager

        config_manager = MagicMock()
        config_manager.load_export_settings.return_value = {"last_sgf_directory": "/path"}

        manager = SummaryManager(
            get_ctx=lambda: MagicMock(),
            get_engine=lambda: None,
            get_config=lambda k, d=None: d,
            config_manager=config_manager,
            logger=make_test_logger(),
        )

        result = manager._load_export_settings()

        config_manager.load_export_settings.assert_called_once()
        assert result == {"last_sgf_directory": "/path"}

    def test_save_export_settings_delegates_to_config_manager(self):
        """_save_export_settings()がConfigManagerへ委譲"""
        from katrain.gui.managers.summary_manager import SummaryManager

        config_manager = MagicMock()

        manager = SummaryManager(
            get_ctx=lambda: MagicMock(),
            get_engine=lambda: None,
            get_config=lambda k, d=None: d,
            config_manager=config_manager,
            logger=make_test_logger(),
        )

        manager._save_export_settings(sgf_directory="/new/path", selected_players=["Player1"])

        config_manager.save_export_settings.assert_called_once_with("/new/path", ["Player1"])


class TestSummaryManagerPureFunctionWrappers:
    """Pure関数ラッパーのWiring test（Kivy不要）

    これらのメソッドはsummary_stats/aggregator/formatterのPure関数を呼び出すのみで、
    Kivyを必要としない。パッチ対象はsummary_*.py内の関数。

    確認済み: summary_stats.py, summary_aggregator.py, summary_formatter.py は
    Kivyを直接インポートしていない（検証ポイント1参照）。
    """

    def test_scan_player_names_delegates_to_aggregator(self):
        """scan_player_names()がsummary_aggregator関数へ委譲"""
        from katrain.gui.managers.summary_manager import SummaryManager

        logger = make_test_logger()

        manager = SummaryManager(
            get_ctx=lambda: MagicMock(),
            get_engine=lambda: None,
            get_config=lambda k, d=None: d,
            config_manager=MagicMock(),
            logger=logger,
        )

        with patch(
            "katrain.gui.features.summary_aggregator.scan_player_names"
        ) as mock_scan:
            mock_scan.return_value = {"Player1": 5, "Player2": 3}

            result = manager.scan_player_names(["game1.sgf", "game2.sgf"])

            mock_scan.assert_called_once_with(["game1.sgf", "game2.sgf"], logger)
            assert result == {"Player1": 5, "Player2": 3}

    def test_categorize_games_by_stats_delegates_to_aggregator(self):
        """categorize_games_by_stats()がsummary_aggregator関数へ委譲"""
        from katrain.gui.managers.summary_manager import SummaryManager

        manager = SummaryManager(
            get_ctx=lambda: MagicMock(),
            get_engine=lambda: None,
            get_config=lambda k, d=None: d,
            config_manager=MagicMock(),
            logger=make_test_logger(),
        )

        with patch(
            "katrain.gui.features.summary_aggregator.categorize_games_by_stats"
        ) as mock_cat:
            mock_cat.return_value = {"even": [], "handi_weak": [], "handi_strong": []}

            result = manager.categorize_games_by_stats([{"player": "P1"}], "P1")

            mock_cat.assert_called_once_with([{"player": "P1"}], "P1")
            assert "even" in result

    def test_collect_rank_info_delegates_to_aggregator(self):
        """collect_rank_info()がsummary_aggregator関数へ委譲"""
        from katrain.gui.managers.summary_manager import SummaryManager

        manager = SummaryManager(
            get_ctx=lambda: MagicMock(),
            get_engine=lambda: None,
            get_config=lambda k, d=None: d,
            config_manager=MagicMock(),
            logger=make_test_logger(),
        )

        with patch(
            "katrain.gui.features.summary_aggregator.collect_rank_info"
        ) as mock_collect:
            mock_collect.return_value = "4d"

            result = manager.collect_rank_info([{"rank": "4d"}], "Player1")

            mock_collect.assert_called_once_with([{"rank": "4d"}], "Player1")
            assert result == "4d"

    def test_build_summary_from_stats_delegates_to_formatter(self):
        """build_summary_from_stats()がsummary_formatter関数へ委譲"""
        from katrain.gui.managers.summary_manager import SummaryManager

        get_config = MagicMock()

        manager = SummaryManager(
            get_ctx=lambda: MagicMock(),
            get_engine=lambda: None,
            get_config=get_config,
            config_manager=MagicMock(),
            logger=make_test_logger(),
        )

        with patch(
            "katrain.gui.features.summary_formatter.build_summary_from_stats"
        ) as mock_build:
            mock_build.return_value = "Summary text"

            result = manager.build_summary_from_stats([{}], "Player1")

            mock_build.assert_called_once_with([{}], "Player1", get_config)
            assert result == "Summary text"

    def test_extract_analysis_from_sgf_node_delegates_to_stats(self):
        """extract_analysis_from_sgf_node()がsummary_stats関数へ委譲"""
        from katrain.gui.managers.summary_manager import SummaryManager

        manager = SummaryManager(
            get_ctx=lambda: MagicMock(),
            get_engine=lambda: None,
            get_config=lambda k, d=None: d,
            config_manager=MagicMock(),
            logger=make_test_logger(),
        )

        with patch(
            "katrain.gui.features.summary_stats.extract_analysis_from_sgf_node"
        ) as mock_extract:
            mock_extract.return_value = {"score_loss": 1.5}
            mock_node = MagicMock()

            result = manager.extract_analysis_from_sgf_node(mock_node)

            mock_extract.assert_called_once_with(mock_node)
            assert result == {"score_loss": 1.5}


class TestSummaryManagerUIMethodsSkipped:
    """UI実行メソッドのテスト（Kivy必要のためスキップ）

    これらのメソッドはsummary_ui.pyを呼び出し、Kivyが必要。
    統合テストまたは手動テストで確認する。
    """

    @pytest.mark.skip(reason="Requires Kivy runtime - do_export_summary calls summary_ui")
    def test_do_export_summary_requires_kivy(self):
        """do_export_summary()はKivyランタイムが必要"""
        pass

    @pytest.mark.skip(reason="Requires Kivy runtime - do_export_summary_ui calls summary_ui")
    def test_do_export_summary_ui_requires_kivy(self):
        """do_export_summary_ui()はKivyランタイムが必要"""
        pass

    @pytest.mark.skip(reason="Requires Kivy runtime - scan_and_show_player_selection calls summary_ui")
    def test_scan_and_show_player_selection_requires_kivy(self):
        """scan_and_show_player_selection()はKivyランタイムが必要"""
        pass
