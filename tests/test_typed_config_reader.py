# tests/test_typed_config_reader.py
#
# Unit tests for katrain.common.typed_config.reader
# Phase 99


from katrain.common.typed_config import TypedConfigReader
from katrain.common.typed_config.models import EngineConfig, LeelaConfig, TrainerConfig


class TestTypedConfigReader:
    def test_get_engine_returns_engine_config(self):
        reader = TypedConfigReader({"engine": {"max_visits": 1000}})
        cfg = reader.get_engine()
        assert isinstance(cfg, EngineConfig)
        assert cfg.max_visits == 1000

    def test_get_trainer_returns_trainer_config(self):
        reader = TypedConfigReader({"trainer": {"low_visits": 50}})
        cfg = reader.get_trainer()
        assert isinstance(cfg, TrainerConfig)
        assert cfg.low_visits == 50

    def test_get_leela_returns_leela_config(self):
        reader = TypedConfigReader({"leela": {"enabled": True}})
        cfg = reader.get_leela()
        assert isinstance(cfg, LeelaConfig)
        assert cfg.enabled is True

    def test_non_dict_section_returns_defaults(self):
        """セクションがdictでない場合はデフォルト値を返す"""
        reader = TypedConfigReader({"engine": "invalid"})
        cfg = reader.get_engine()
        assert cfg.max_visits == 500  # default

    def test_none_section_returns_defaults(self):
        """セクションがNoneの場合はデフォルト値を返す"""
        reader = TypedConfigReader({"engine": None})
        cfg = reader.get_engine()
        assert cfg.max_visits == 500

    def test_missing_section_returns_defaults(self):
        """セクションが存在しない場合はデフォルト値を返す"""
        reader = TypedConfigReader({})
        cfg = reader.get_engine()
        assert cfg.max_visits == 500

    def test_changes_reflected_immediately(self):
        """キャッシュなしのため、dict変更後は新しい値を返す"""
        config = {"engine": {"max_visits": 500}}
        reader = TypedConfigReader(config)
        assert reader.get_engine().max_visits == 500

        config["engine"]["max_visits"] = 1000
        assert reader.get_engine().max_visits == 1000

    def test_in_place_section_replacement(self):
        """ConfigManager.set_section相当のin-place置換"""
        config = {"engine": {"max_visits": 500}}
        reader = TypedConfigReader(config)
        assert reader.get_engine().max_visits == 500

        # in-place replacement (like set_config_section does)
        config["engine"] = {"max_visits": 2000}
        assert reader.get_engine().max_visits == 2000

    def test_multiple_sections(self):
        """複数セクションを同時に読める"""
        config = {
            "engine": {"max_visits": 1000},
            "trainer": {"low_visits": 50},
            "leela": {"enabled": True},
        }
        reader = TypedConfigReader(config)

        assert reader.get_engine().max_visits == 1000
        assert reader.get_trainer().low_visits == 50
        assert reader.get_leela().enabled is True


class TestTypedConfigReaderSnapshot:
    """スナップショット機能のテスト"""

    def test_concurrent_modification_safe(self):
        """読み取り中のdict変更に対して安全"""
        config = {"engine": {"max_visits": 500, "fast_visits": 25}}
        reader = TypedConfigReader(config)

        # 1回目の読み取り
        cfg1 = reader.get_engine()
        assert cfg1.max_visits == 500

        # 読み取り後にconfigを変更
        config["engine"]["max_visits"] = 1000

        # frozen objectなので変わらない（既に作成済みのオブジェクトは不変）
        assert cfg1.max_visits == 500

        # 2回目の読み取りは新しい値
        cfg2 = reader.get_engine()
        assert cfg2.max_visits == 1000

    def test_list_type_section_handled(self):
        """セクションがlistの場合もクラッシュしない"""
        config = {"engine": [1, 2, 3]}  # listは無効
        reader = TypedConfigReader(config)
        cfg = reader.get_engine()
        assert cfg.max_visits == 500  # default


class TestTypedConfigReaderEdgeCases:
    """エッジケースのテスト"""

    def test_empty_config(self):
        """空のconfig辞書"""
        reader = TypedConfigReader({})
        engine = reader.get_engine()
        trainer = reader.get_trainer()
        leela = reader.get_leela()

        # すべてデフォルト値
        assert engine.max_visits == 500
        assert trainer.low_visits == 25
        assert leela.enabled is False

    def test_partial_engine_config(self):
        """部分的なengineセクション"""
        reader = TypedConfigReader({"engine": {"max_visits": 1000}})
        cfg = reader.get_engine()

        assert cfg.max_visits == 1000
        assert cfg.fast_visits == 25  # default
        assert cfg.max_time == 8.0  # default

    def test_extra_keys_ignored(self):
        """未知のキーは無視される"""
        reader = TypedConfigReader({"engine": {"max_visits": 1000, "unknown_key": "value"}})
        cfg = reader.get_engine()
        assert cfg.max_visits == 1000
        # unknown_keyは無視される（エラーにならない）

    def test_nested_dict_in_section(self):
        """セクション内のネストしたdict"""
        reader = TypedConfigReader({"engine": {"max_visits": 1000, "nested": {"key": "value"}}})
        cfg = reader.get_engine()
        assert cfg.max_visits == 1000
        # nestedは無視される
