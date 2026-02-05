"""ConfigManagerのユニットテスト（Phase 74）

Kivy完全非依存:
- ConfigManagerのみをインスタンス化
- config_dict: 通常のPython dict
- save_config: 呼び出し記録用のスタブ関数
"""

import pytest

from katrain.gui.managers.config_manager import ConfigManager


class TestConfigManagerGet:
    """読み取りテスト"""

    def test_get_section_returns_shallow_copy(self):
        """get_section()はshallow copyを返す（トップレベルキーのみ保護）"""
        config = {"general": {"lang": "ja"}}
        manager = ConfigManager(config, lambda k: None)

        result = manager.get_section("general")
        result["lang"] = "en"  # トップレベルキーの変更

        assert config["general"]["lang"] == "ja"  # 元は変更されない

    def test_get_section_shallow_copy_nested_dict_shares_reference(self):
        """get_section()のshallow copyはネストdictの参照を共有（documented behavior）"""
        config = {"settings": {"nested": {"key": "original"}}}
        manager = ConfigManager(config, lambda k: None)

        result = manager.get_section("settings")
        # ネストdictの変更は元に影響する（shallow copyの制限）
        result["nested"]["key"] = "modified"

        # これはshallow copyの既知の制限
        assert config["settings"]["nested"]["key"] == "modified"

    def test_get_returns_direct_reference_not_copy(self):
        """get()は直接参照を返す（パフォーマンス優先、変更禁止ポリシー）"""
        config = {"trainer": {"thresholds": [0.5, 2.0]}}
        manager = ConfigManager(config, lambda k: None)

        result = manager.get("trainer")

        # 同一オブジェクト（コピーではない）
        assert result is config["trainer"]

    def test_get_nested_key(self):
        """階層キーの取得"""
        config = {"trainer": {"eval_thresholds": [0.5, 2.0]}}
        manager = ConfigManager(config, lambda k: None)

        assert manager.get("trainer/eval_thresholds") == [0.5, 2.0]

    def test_get_missing_key_returns_default(self):
        """存在しないキーはデフォルト値を返す"""
        manager = ConfigManager({}, lambda k: None)

        assert manager.get("missing/key", "default") == "default"

    def test_get_nested_key_returns_default_for_non_dict_section(self):
        """非dictセクションの階層キー取得はdefaultを返す"""
        config = {
            "string_section": "not a dict",
            "list_section": [1, 2, 3],
            "none_section": None,
        }
        manager = ConfigManager(config, lambda k: None)

        assert manager.get("string_section/key", "fallback") == "fallback"
        assert manager.get("list_section/key", "fallback") == "fallback"
        assert manager.get("none_section/key", "fallback") == "fallback"

    def test_get_nested_key_works_for_valid_dict_section(self):
        """正常なdictセクションの階層キー取得"""
        config = {"valid": {"nested_key": "nested_value"}}
        manager = ConfigManager(config, lambda k: None)

        assert manager.get("valid/nested_key") == "nested_value"
        assert manager.get("valid/missing", "default") == "default"

    def test_get_section_name_only(self):
        """セクション名のみでセクション全体を取得"""
        config = {"general": {"lang": "ja", "theme": "dark"}}
        manager = ConfigManager(config, lambda k: None)

        result = manager.get("general")

        assert result == {"lang": "ja", "theme": "dark"}

    def test_get_missing_section_returns_default(self):
        """存在しないセクションはdefaultを返す"""
        manager = ConfigManager({}, lambda k: None)

        assert manager.get("missing") is None
        assert manager.get("missing", {}) == {}


class TestConfigManagerGetSection:
    """get_section()テスト"""

    def test_get_section_returns_empty_dict_for_non_dict_value(self):
        """非dict値のセクションは空辞書を返す"""
        config = {
            "string_section": "not a dict",
            "list_section": [1, 2, 3],
            "none_section": None,
            "int_section": 42,
        }
        manager = ConfigManager(config, lambda k: None)

        assert manager.get_section("string_section") == {}
        assert manager.get_section("list_section") == {}
        assert manager.get_section("none_section") == {}
        assert manager.get_section("int_section") == {}

    def test_get_section_works_for_valid_dict(self):
        """正常なdict値のセクションは正しく返す"""
        config = {"valid": {"key": "value"}}
        manager = ConfigManager(config, lambda k: None)

        assert manager.get_section("valid") == {"key": "value"}

    def test_get_section_returns_empty_dict_for_missing_section(self):
        """存在しないセクションは空辞書を返す"""
        manager = ConfigManager({}, lambda k: None)

        assert manager.get_section("missing") == {}


class TestConfigManagerSetSection:
    """set_section()テスト - REPLACEセマンティクス"""

    def test_set_section_replaces_entire_section(self):
        """セクション全体を置き換える（REPLACE）"""
        config = {"general": {"lang": "ja", "theme": "dark"}}
        manager = ConfigManager(config, lambda k: None)

        manager.set_section("general", {"lang": "en"})

        assert config["general"] == {"lang": "en"}  # themeは消える
        assert "theme" not in config["general"]

    def test_set_section_does_not_auto_save(self):
        """set_section()は自動保存しない"""
        save_calls = []
        manager = ConfigManager({}, lambda k: save_calls.append(k))

        manager.set_section("test", {"key": "value"})

        assert save_calls == []  # 保存は呼び出されない

    def test_set_section_creates_new_section(self):
        """新しいセクションを作成"""
        config = {}
        manager = ConfigManager(config, lambda k: None)

        manager.set_section("new_section", {"key": "value"})

        assert config["new_section"] == {"key": "value"}


class TestLoadExportSettings:
    """load_export_settings()テスト"""

    def test_load_export_settings_returns_section(self):
        """export_settingsセクションを返す"""
        config = {"export_settings": {"last_sgf_directory": "/path"}}
        manager = ConfigManager(config, lambda k: None)

        result = manager.load_export_settings()

        assert result == {"last_sgf_directory": "/path"}

    def test_load_export_settings_returns_empty_dict_for_missing(self):
        """export_settingsが存在しない場合は空辞書"""
        manager = ConfigManager({}, lambda k: None)

        result = manager.load_export_settings()

        assert result == {}


class TestSaveExportSettings:
    """save_export_settings()テスト - PARTIAL UPDATEセマンティクス"""

    def test_none_does_not_change_existing_value(self):
        """None引数は既存値を変更しない"""
        config = {"export_settings": {"last_sgf_directory": "/old/path"}}
        save_calls = []
        manager = ConfigManager(config, lambda k: save_calls.append(k))

        manager.save_export_settings(sgf_directory=None)

        assert config["export_settings"]["last_sgf_directory"] == "/old/path"

    def test_partial_update_preserves_other_keys(self):
        """部分更新で他のキーは保持される"""
        config = {
            "export_settings": {
                "last_sgf_directory": "/old",
                "last_selected_players": ["Alice"],
                "other_key": "preserved",
            }
        }
        manager = ConfigManager(config, lambda k: None)

        manager.save_export_settings(sgf_directory="/new")

        assert config["export_settings"]["last_sgf_directory"] == "/new"
        assert config["export_settings"]["last_selected_players"] == ["Alice"]
        assert config["export_settings"]["other_key"] == "preserved"

    def test_calls_save_config_with_section_key(self):
        """save_config("export_settings")が呼ばれる"""
        save_calls = []
        manager = ConfigManager({}, lambda k: save_calls.append(k))

        manager.save_export_settings(sgf_directory="/path")

        assert save_calls == ["export_settings"]

    def test_update_both_values(self):
        """両方の値を同時に更新"""
        config = {"export_settings": {}}
        manager = ConfigManager(config, lambda k: None)

        manager.save_export_settings(sgf_directory="/new/path", selected_players=["Alice", "Bob"])

        assert config["export_settings"]["last_sgf_directory"] == "/new/path"
        assert config["export_settings"]["last_selected_players"] == ["Alice", "Bob"]

    def test_creates_export_settings_if_missing(self):
        """export_settingsが存在しない場合は作成"""
        config = {}
        manager = ConfigManager(config, lambda k: None)

        manager.save_export_settings(sgf_directory="/path")

        assert config["export_settings"]["last_sgf_directory"] == "/path"


class TestSaveBatchOptions:
    """save_batch_options()テスト - PARTIAL UPDATEセマンティクス"""

    def test_merges_into_batch_options_subtree(self):
        """batch_optionsサブツリーのみMERGE"""
        config = {
            "mykatrain_settings": {
                "karte_output_directory": "/reports",
                "batch_options": {"visits": 100, "timeout": 30},
            }
        }
        manager = ConfigManager(config, lambda k: None)

        manager.save_batch_options({"visits": 200})

        # batch_options内はMERGE
        assert config["mykatrain_settings"]["batch_options"]["visits"] == 200
        assert config["mykatrain_settings"]["batch_options"]["timeout"] == 30
        # 他のmykatrain_settingsキーは保持
        assert config["mykatrain_settings"]["karte_output_directory"] == "/reports"

    def test_creates_batch_options_if_missing(self):
        """batch_optionsが存在しない場合は作成"""
        config = {"mykatrain_settings": {"karte_output_directory": "/reports"}}
        manager = ConfigManager(config, lambda k: None)

        manager.save_batch_options({"visits": 100})

        assert config["mykatrain_settings"]["batch_options"] == {"visits": 100}
        assert config["mykatrain_settings"]["karte_output_directory"] == "/reports"

    def test_handles_corrupted_batch_options_list(self):
        """破損データ: batch_optionsがlistの場合は{}として扱う"""
        log_calls = []
        config = {
            "mykatrain_settings": {
                "karte_output_directory": "/reports",
                "batch_options": ["corrupted", "data"],
            }
        }
        manager = ConfigManager(
            config,
            lambda k: None,
            logger=lambda msg, lvl: log_calls.append(msg),
            log_level_info=42,  # テスト用の任意の値
        )

        manager.save_batch_options({"visits": 100})

        assert config["mykatrain_settings"]["batch_options"] == {"visits": 100}
        assert config["mykatrain_settings"]["karte_output_directory"] == "/reports"
        assert any("list" in msg for msg in log_calls)  # ログ出力確認

    def test_save_batch_options_does_not_mutate_original_nested_dict(self):
        """save_batch_options()は元のネストdictを変更しない（shallow copy保護）"""
        original_batch = {"visits": 100, "timeout": 30}
        config = {"mykatrain_settings": {"batch_options": original_batch}}
        manager = ConfigManager(config, lambda k: None)

        # 別の参照を保持
        original_batch_ref = config["mykatrain_settings"]["batch_options"]

        manager.save_batch_options({"visits": 200})

        # 新しいdictが設定される（元の参照は変更されない）
        new_batch = config["mykatrain_settings"]["batch_options"]
        assert new_batch["visits"] == 200
        assert new_batch["timeout"] == 30
        # 元のオブジェクトは変更されていない
        assert original_batch_ref["visits"] == 100

    def test_handles_corrupted_batch_options_string(self):
        """破損データ: batch_optionsがstrの場合は{}として扱う"""
        config = {"mykatrain_settings": {"batch_options": "not a dict"}}
        manager = ConfigManager(config, lambda k: None)

        manager.save_batch_options({"visits": 100})

        assert config["mykatrain_settings"]["batch_options"] == {"visits": 100}

    def test_raises_type_error_for_non_dict_options_argument(self):
        """options引数が非dictの場合はTypeError"""
        manager = ConfigManager({}, lambda k: None)

        with pytest.raises(TypeError, match="options must be dict"):
            manager.save_batch_options("not a dict")

        with pytest.raises(TypeError, match="options must be dict"):
            manager.save_batch_options([1, 2, 3])

    def test_calls_save_config_with_section_key(self):
        """save_config("mykatrain_settings")が呼ばれる"""
        save_calls = []
        manager = ConfigManager({}, lambda k: save_calls.append(k))

        manager.save_batch_options({"visits": 100})

        assert save_calls == ["mykatrain_settings"]

    def test_creates_mykatrain_settings_if_missing(self):
        """mykatrain_settingsが存在しない場合は作成"""
        config = {}
        manager = ConfigManager(config, lambda k: None)

        manager.save_batch_options({"visits": 100})

        assert config["mykatrain_settings"]["batch_options"] == {"visits": 100}

    def test_handles_corrupted_batch_options_none(self):
        """破損データ: batch_optionsがNoneの場合は{}として扱う"""
        config = {"mykatrain_settings": {"batch_options": None}}
        manager = ConfigManager(config, lambda k: None)

        manager.save_batch_options({"visits": 100})

        assert config["mykatrain_settings"]["batch_options"] == {"visits": 100}


class TestErrorHandling:
    """エラーハンドリングテスト"""

    def test_get_from_empty_config(self):
        """空の設定からの読み取り"""
        manager = ConfigManager({}, lambda k: None)

        assert manager.get("missing") is None
        assert manager.get_section("missing") == {}

    def test_constructor_with_no_logger(self):
        """loggerなしでのインスタンス化"""
        config = {"mykatrain_settings": {"batch_options": ["corrupted"]}}
        manager = ConfigManager(config, lambda k: None)  # logger=None (default)

        # ログ出力なしでも動作する
        manager.save_batch_options({"visits": 100})

        assert config["mykatrain_settings"]["batch_options"] == {"visits": 100}

    def test_constructor_with_custom_log_level(self):
        """カスタムlog_level_infoでのインスタンス化"""
        log_levels = []
        config = {"mykatrain_settings": {"batch_options": "corrupted"}}
        manager = ConfigManager(
            config,
            lambda k: None,
            logger=lambda msg, lvl: log_levels.append(lvl),
            log_level_info=99,
        )

        manager.save_batch_options({"visits": 100})

        assert 99 in log_levels


class TestIntegration:
    """統合テスト"""

    def test_full_workflow_export_settings(self):
        """エクスポート設定の完全なワークフロー"""
        save_calls = []
        config = {}
        manager = ConfigManager(config, lambda k: save_calls.append(k))

        # 初回保存
        manager.save_export_settings(sgf_directory="/first/path")
        assert config["export_settings"]["last_sgf_directory"] == "/first/path"

        # 部分更新
        manager.save_export_settings(selected_players=["Alice"])
        assert config["export_settings"]["last_sgf_directory"] == "/first/path"
        assert config["export_settings"]["last_selected_players"] == ["Alice"]

        # 複数キー更新
        manager.save_export_settings(sgf_directory="/second/path", selected_players=["Bob"])
        assert config["export_settings"]["last_sgf_directory"] == "/second/path"
        assert config["export_settings"]["last_selected_players"] == ["Bob"]

        # 保存が毎回呼ばれている
        assert save_calls == ["export_settings"] * 3

    def test_full_workflow_batch_options(self):
        """バッチオプションの完全なワークフロー"""
        save_calls = []
        config = {}
        manager = ConfigManager(config, lambda k: save_calls.append(k))

        # 初回保存
        manager.save_batch_options({"visits": 100})
        assert config["mykatrain_settings"]["batch_options"]["visits"] == 100

        # 追加キー
        manager.save_batch_options({"timeout": 30})
        assert config["mykatrain_settings"]["batch_options"]["visits"] == 100
        assert config["mykatrain_settings"]["batch_options"]["timeout"] == 30

        # 既存キーの更新
        manager.save_batch_options({"visits": 200})
        assert config["mykatrain_settings"]["batch_options"]["visits"] == 200
        assert config["mykatrain_settings"]["batch_options"]["timeout"] == 30

        # 保存が毎回呼ばれている
        assert save_calls == ["mykatrain_settings"] * 3
