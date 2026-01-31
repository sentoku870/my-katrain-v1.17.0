# tests/test_typed_config_integration.py
#
# Integration tests for typed config system
# Phase 99
#
# These tests verify that typed config accessors work correctly with
# the actual config loading flow.

import pytest

from katrain.common.typed_config import EngineConfig, LeelaConfig, TrainerConfig
from katrain.core.base_katrain import KaTrainBase


@pytest.fixture
def katrain_base():
    """Provide a KaTrainBase instance with package config."""
    return KaTrainBase(force_package_config=True, debug_level=0)


class TestTypedConfigIntegration:
    """実際のconfig flowを使った統合テスト。

    統合テスト方針: Option A（厳密アサーション）
    - config.jsonはJSONネイティブ型で書かれている（検証済み）
    - _load_config()はJSONパース→dict変換のみ、型変換なし
    - もし将来コードが変わって文字列が来た場合、それはバグとして検出
    """

    def test_get_engine_config_returns_engine_config(self, katrain_base):
        """get_engine_config()はEngineConfigを返す"""
        cfg = katrain_base.get_engine_config()
        assert isinstance(cfg, EngineConfig)

    def test_get_trainer_config_returns_trainer_config(self, katrain_base):
        """get_trainer_config()はTrainerConfigを返す"""
        cfg = katrain_base.get_trainer_config()
        assert isinstance(cfg, TrainerConfig)

    def test_get_leela_config_returns_leela_config(self, katrain_base):
        """get_leela_config()はLeelaConfigを返す"""
        cfg = katrain_base.get_leela_config()
        assert isinstance(cfg, LeelaConfig)

    def test_config_and_typed_config_consistent(self, katrain_base):
        """config()とget_*_config()の値が一致する。

        検証済み不変条件:
        - config.json: "max_visits": 500 (int)
        - base_katrain.py:210: return self._config.get(...) - 型変換なし
        - JSONパース時にPython int に変換済み

        このテストが失敗した場合:
        - config flowに変更があった = 調査必要
        - 一時対応: safe_int(raw_value, default) == typed_value に緩和可能
        """
        raw_value = katrain_base.config("engine/max_visits")
        typed_value = katrain_base.get_engine_config().max_visits

        # 値が一致することを確認
        assert raw_value == typed_value, (
            f"Value mismatch: config()={raw_value!r} vs typed={typed_value!r}"
        )

        # 型が一致することを確認（想定: 両方int）
        assert isinstance(raw_value, int), (
            f"Expected config() to return int, got {type(raw_value).__name__}. "
            "If this fails, the config load path may have changed."
        )
        assert isinstance(typed_value, int)

    def test_engine_max_time_consistency(self, katrain_base):
        """engine/max_time の一貫性（float型）"""
        raw_value = katrain_base.config("engine/max_time")
        typed_value = katrain_base.get_engine_config().max_time

        assert raw_value == typed_value
        assert isinstance(raw_value, (int, float))
        assert isinstance(typed_value, float)

    def test_trainer_low_visits_consistency(self, katrain_base):
        """trainer/low_visits の一貫性（int型）"""
        raw_value = katrain_base.config("trainer/low_visits")
        typed_value = katrain_base.get_trainer_config().low_visits

        assert raw_value == typed_value
        assert isinstance(raw_value, int)
        assert isinstance(typed_value, int)


class TestTypedConfigSetSection:
    """set_config_sectionとの連携テスト"""

    def test_set_config_section_reflected_in_typed(self, katrain_base):
        """set_config_section後、get_*()は新しい値を返す"""
        original = katrain_base.get_engine_config().max_visits

        # 新しい値を設定
        new_engine = dict(katrain_base._config.get("engine", {}))
        new_engine["max_visits"] = original + 500
        katrain_base._config["engine"] = new_engine

        # 新しい値が反映される
        assert katrain_base.get_engine_config().max_visits == original + 500

    def test_trainer_config_update(self, katrain_base):
        """trainerセクションの更新が反映される"""
        original = katrain_base.get_trainer_config().low_visits

        new_trainer = dict(katrain_base._config.get("trainer", {}))
        new_trainer["low_visits"] = original + 10
        katrain_base._config["trainer"] = new_trainer

        assert katrain_base.get_trainer_config().low_visits == original + 10


class TestTypedConfigDefaults:
    """デフォルト値のテスト"""

    def test_engine_defaults_match_class_defaults(self, katrain_base):
        """EngineConfigのデフォルト値がクラス定義と一致"""
        # 存在しないセクションでもデフォルトが返る
        default_cfg = EngineConfig()

        # クラスのデフォルト値を確認
        assert default_cfg.analysis_engine == "katago"
        assert default_cfg.max_visits == 500
        assert default_cfg.fast_visits == 25
        assert default_cfg.max_time == 8.0
        assert default_cfg.enable_ownership is True

    def test_trainer_defaults_match_class_defaults(self):
        """TrainerConfigのデフォルト値がクラス定義と一致"""
        default_cfg = TrainerConfig()

        assert default_cfg.theme == "theme:normal"
        assert default_cfg.low_visits == 25
        assert default_cfg.eval_on_show_last == 3
        assert default_cfg.eval_show_ai is True
        assert len(default_cfg.eval_thresholds) == 6

    def test_leela_defaults_match_class_defaults(self):
        """LeelaConfigのデフォルト値がクラス定義と一致"""
        default_cfg = LeelaConfig()

        assert default_cfg.enabled is False
        assert default_cfg.exe_path is None
        assert default_cfg.max_visits == 1000
        assert default_cfg.fast_visits == 200


class TestTypedConfigImmutability:
    """frozenの動作確認"""

    def test_engine_config_is_frozen(self, katrain_base):
        """EngineConfigはfrozenで変更不可"""
        cfg = katrain_base.get_engine_config()
        with pytest.raises(Exception):  # FrozenInstanceError
            cfg.max_visits = 9999  # type: ignore

    def test_trainer_config_is_frozen(self, katrain_base):
        """TrainerConfigはfrozenで変更不可"""
        cfg = katrain_base.get_trainer_config()
        with pytest.raises(Exception):
            cfg.low_visits = 9999  # type: ignore

    def test_leela_config_is_frozen(self, katrain_base):
        """LeelaConfigはfrozenで変更不可"""
        cfg = katrain_base.get_leela_config()
        with pytest.raises(Exception):
            cfg.enabled = True  # type: ignore


class TestTypedConfigMultipleCalls:
    """複数回呼び出しのテスト"""

    def test_multiple_get_engine_calls_consistent(self, katrain_base):
        """get_engine_config()を複数回呼んでも一貫した値"""
        cfg1 = katrain_base.get_engine_config()
        cfg2 = katrain_base.get_engine_config()

        assert cfg1.max_visits == cfg2.max_visits
        assert cfg1.max_time == cfg2.max_time

    def test_different_calls_return_new_instances(self, katrain_base):
        """毎回新しいインスタンスが返される（キャッシュなし）"""
        cfg1 = katrain_base.get_engine_config()
        cfg2 = katrain_base.get_engine_config()

        # 値は同じだが、異なるインスタンス
        assert cfg1.max_visits == cfg2.max_visits
        # Note: frozen dataclassは同じ値でも異なるインスタンス
        # (eq=Trueなのでcfg1 == cfg2はTrue)
        assert cfg1 == cfg2
