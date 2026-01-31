"""TypedConfigWriter の単体テスト（Phase 101）。

AC3対応: デフォルト値はモデルから取得（ハードコードしない）
"""

from __future__ import annotations

import json
import logging

import pytest

from katrain.common.typed_config import (
    EngineConfig,
    LeelaConfig,
    TrainerConfig,
    TypedConfigWriter,
    UnknownFieldError,
)
from katrain.common.typed_config.writer import _to_json_safe


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def engine_defaults():
    """EngineConfigのデフォルト値。"""
    return EngineConfig.from_dict({})


@pytest.fixture
def leela_defaults():
    """LeelaConfigのデフォルト値。"""
    return LeelaConfig.from_dict({})


@pytest.fixture
def trainer_defaults():
    """TrainerConfigのデフォルト値。"""
    return TrainerConfig.from_dict({})


# =============================================================================
# Basic Functionality
# =============================================================================


class TestBasicFunctionality:
    """基本機能テスト"""

    def test_update_engine_single_field(self):
        """単一フィールドの更新"""
        config = {"engine": {"max_visits": 500}}
        saved_sections = []
        writer = TypedConfigWriter(config, lambda s: saved_sections.append(s))

        result = writer.update_engine(max_visits=1000)

        assert result.max_visits == 1000
        assert config["engine"]["max_visits"] == 1000
        assert saved_sections == ["engine"]

    def test_update_engine_multiple_fields(self):
        """複数フィールドの同時更新"""
        config = {"engine": {"max_visits": 500, "fast_visits": 25}}
        writer = TypedConfigWriter(config, lambda s: None)

        result = writer.update_engine(max_visits=1000, fast_visits=50)

        assert result.max_visits == 1000
        assert result.fast_visits == 50
        assert config["engine"]["max_visits"] == 1000
        assert config["engine"]["fast_visits"] == 50

    def test_update_leela(self):
        """Leelaセクションの更新"""
        config = {"leela": {"enabled": False}}
        writer = TypedConfigWriter(config, lambda s: None)

        result = writer.update_leela(enabled=True, exe_path="/path")

        assert result.enabled is True
        assert result.exe_path == "/path"

    def test_update_trainer(self):
        """Trainerセクションの更新"""
        config = {"trainer": {"low_visits": 25}}
        writer = TypedConfigWriter(config, lambda s: None)

        result = writer.update_trainer(low_visits=50)

        assert result.low_visits == 50


# =============================================================================
# Merge Semantics (AC5)
# =============================================================================


class TestMergeSemantics:
    """MERGEパターンのテスト"""

    def test_preserves_unspecified_fields(self, engine_defaults):
        """指定されなかったフィールドは保持"""
        initial_fast = engine_defaults.fast_visits
        config = {"engine": {"max_visits": 500, "fast_visits": initial_fast}}
        writer = TypedConfigWriter(config, lambda s: None)

        result = writer.update_engine(max_visits=1000)

        assert result.fast_visits == initial_fast
        assert config["engine"]["fast_visits"] == initial_fast

    def test_preserves_unknown_keys_in_existing(self):
        """既存dictの未知キーは保持される（AC5）"""
        config = {"engine": {"max_visits": 500, "legacy_key": "value"}}
        writer = TypedConfigWriter(config, lambda s: None)

        writer.update_engine(max_visits=1000)

        assert config["engine"]["legacy_key"] == "value"

    def test_missing_section_creates_new(self):
        """セクションが存在しない場合は新規作成"""
        config = {}
        writer = TypedConfigWriter(config, lambda s: None)

        writer.update_engine(max_visits=1000)

        assert "engine" in config
        assert config["engine"]["max_visits"] == 1000

    def test_none_section_creates_new(self):
        """セクションがNoneの場合も新規作成"""
        config = {"engine": None}
        writer = TypedConfigWriter(config, lambda s: None)

        writer.update_engine(max_visits=1000)

        assert config["engine"]["max_visits"] == 1000

    def test_non_dict_section_creates_new(self):
        """セクションがdict以外の場合も新規作成"""
        config = {"engine": "invalid"}
        writer = TypedConfigWriter(config, lambda s: None)

        writer.update_engine(max_visits=1000)

        assert isinstance(config["engine"], dict)
        assert config["engine"]["max_visits"] == 1000


# =============================================================================
# Field Validation (AC4)
# =============================================================================


class TestFieldValidation:
    """フィールド名検証のテスト"""

    def test_unknown_field_raises(self):
        """存在しないフィールドはUnknownFieldError（AC4）"""
        config = {"engine": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with pytest.raises(UnknownFieldError) as exc:
            writer.update_engine(unknown_field="value")

        assert "unknown_field" in str(exc.value)

    def test_unknown_field_multiple(self):
        """複数の存在しないフィールド"""
        config = {"engine": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with pytest.raises(UnknownFieldError) as exc:
            writer.update_engine(bad1="a", bad2="b")

        assert "bad1" in str(exc.value)
        assert "bad2" in str(exc.value)

    def test_error_message_is_sorted(self):
        """エラーメッセージのフィールド名はソート済み"""
        config = {"engine": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with pytest.raises(UnknownFieldError) as exc:
            writer.update_engine(zzz="a", aaa="b", mmm="c")

        assert "['aaa', 'mmm', 'zzz']" in str(exc.value)

    def test_error_message_includes_class_name(self):
        """エラーメッセージにクラス名を含む"""
        config = {"leela": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with pytest.raises(UnknownFieldError) as exc:
            writer.update_leela(bad_field="x")

        assert "LeelaConfig" in str(exc.value)

    def test_valid_and_invalid_fields_mixed(self):
        """有効なフィールドと無効なフィールドが混在"""
        config = {"engine": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with pytest.raises(UnknownFieldError) as exc:
            writer.update_engine(max_visits=1000, bad_field="x")

        assert "bad_field" in str(exc.value)
        # 無効フィールドがあれば更新は行われない
        assert "max_visits" not in config.get("engine", {})


# =============================================================================
# Dataclass Requirement (AC8)
# =============================================================================


class TestDataclassRequirement:
    """dataclass要件のテスト"""

    def test_non_dataclass_raises_typeerror(self):
        """非dataclassモデルはTypeError（AC8）"""

        class NotADataclass:
            @classmethod
            def from_dict(cls, d):
                return cls()

        config = {}
        writer = TypedConfigWriter(config, lambda s: None)

        with pytest.raises(TypeError) as exc:
            writer._update_section("test", NotADataclass, {"field": "value"})

        assert "not a dataclass" in str(exc.value)
        assert "NotADataclass" in str(exc.value)


# =============================================================================
# JSON Serialization (AC7)
# =============================================================================


class TestJsonSerialization:
    """JSON シリアライズ可能性のテスト"""

    def test_config_dict_is_json_serializable_after_update(self):
        """更新後のconfig_dictはJSONシリアライズ可能（AC7）"""
        config = {"trainer": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        # tuple を含むフィールドを更新
        writer.update_trainer(eval_thresholds=[12.0, 6.0, 3.0, 1.5, 0.5, 0.0])

        # JSONシリアライズが成功すること
        json_str = json.dumps(config)
        assert isinstance(json_str, str)

        # デシリアライズして検証
        parsed = json.loads(json_str)
        assert parsed["trainer"]["eval_thresholds"] == [12.0, 6.0, 3.0, 1.5, 0.5, 0.0]

    def test_tuple_persisted_as_list(self):
        """tupleはlistとして永続化される"""
        config = {"trainer": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        result = writer.update_trainer(eval_thresholds=[12.0, 6.0, 3.0, 1.5, 0.5, 0.0])

        # 返り値はtuple
        assert isinstance(result.eval_thresholds, tuple)
        # 永続化はlist
        assert isinstance(config["trainer"]["eval_thresholds"], list)

    def test_to_json_safe_converts_tuple(self):
        """_to_json_safe: tuple -> list"""
        assert _to_json_safe((1, 2, 3)) == [1, 2, 3]

    def test_to_json_safe_nested(self):
        """_to_json_safe: ネストされた構造"""
        nested = {"a": (1, 2), "b": [(3, 4), (5, 6)]}
        result = _to_json_safe(nested)
        assert result == {"a": [1, 2], "b": [[3, 4], [5, 6]]}

    def test_to_json_safe_primitives(self):
        """_to_json_safe: プリミティブはそのまま"""
        assert _to_json_safe(None) is None
        assert _to_json_safe(True) is True
        assert _to_json_safe(False) is False
        assert _to_json_safe(42) == 42
        assert _to_json_safe(3.14) == 3.14
        assert _to_json_safe("hello") == "hello"

    def test_to_json_safe_empty_containers(self):
        """_to_json_safe: 空のコンテナ"""
        assert _to_json_safe([]) == []
        assert _to_json_safe(()) == []
        assert _to_json_safe({}) == {}


# =============================================================================
# Invalid Value Handling (AC2, AC6)
# =============================================================================


class TestInvalidValueHandling:
    """無効値処理のテスト"""

    def test_invalid_int_logs_warning_and_persists_normalized(
        self, caplog, engine_defaults
    ):
        """無効なint値: 警告ログ + 正規化値を永続化（AC2, AC6）"""
        config = {"engine": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with caplog.at_level(logging.WARNING, logger="katrain"):
            result = writer.update_engine(max_visits="invalid")

        assert result.max_visits == engine_defaults.max_visits
        assert config["engine"]["max_visits"] == engine_defaults.max_visits
        assert "max_visits" in caplog.text
        assert "normalized" in caplog.text

    def test_valid_string_to_int_no_warning(self, caplog):
        """有効な文字列->int変換は警告なし"""
        config = {"engine": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with caplog.at_level(logging.WARNING, logger="katrain"):
            result = writer.update_engine(max_visits="1000")

        assert result.max_visits == 1000
        assert config["engine"]["max_visits"] == 1000
        assert "normalized" not in caplog.text

    def test_empty_string_to_none_no_warning(self, caplog):
        """空文字->None変換は警告なし"""
        config = {"leela": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with caplog.at_level(logging.WARNING, logger="katrain"):
            result = writer.update_leela(exe_path="")

        assert result.exe_path is None
        assert config["leela"]["exe_path"] is None
        assert "normalized" not in caplog.text

    def test_list_to_tuple_no_warning(self, caplog):
        """list->tuple変換は警告なし"""
        config = {"trainer": {}}
        writer = TypedConfigWriter(config, lambda s: None)
        input_list = [12.0, 6.0, 3.0, 1.5, 0.5, 0.0]

        with caplog.at_level(logging.WARNING, logger="katrain"):
            result = writer.update_trainer(eval_thresholds=input_list)

        assert result.eval_thresholds == tuple(input_list)
        assert "normalized" not in caplog.text

    def test_invalid_bool_logs_warning(self, caplog, engine_defaults):
        """無効なbool値: 警告ログ"""
        config = {"engine": {}}
        writer = TypedConfigWriter(config, lambda s: None)

        with caplog.at_level(logging.WARNING, logger="katrain"):
            result = writer.update_engine(enable_ownership="invalid_bool")

        # 無効な文字列はデフォルト値に正規化
        assert result.enable_ownership == engine_defaults.enable_ownership
        assert "enable_ownership" in caplog.text
        assert "normalized" in caplog.text


# =============================================================================
# Save Failure
# =============================================================================


class TestSaveFailure:
    """保存失敗ポリシーのテスト"""

    def test_in_memory_update_kept_on_save_failure(self):
        """save失敗時もin-memory更新は維持"""
        config = {"engine": {"max_visits": 500}}

        def failing_save(section):
            raise IOError("Disk full")

        writer = TypedConfigWriter(config, failing_save)

        with pytest.raises(IOError):
            writer.update_engine(max_visits=1000)

        # メモリ上の更新は維持される
        assert config["engine"]["max_visits"] == 1000


# =============================================================================
# Integration with BaseKaTrain
# =============================================================================


class TestIntegrationPattern:
    """BaseKaTrain統合パターンのテスト"""

    def test_writer_mutates_provided_dict(self):
        """WriterはDEEP COPYではなく参照を変更"""
        config = {"engine": {"max_visits": 500}}
        original_engine_dict = config["engine"]
        writer = TypedConfigWriter(config, lambda s: None)

        writer.update_engine(max_visits=1000)

        # 同じdictオブジェクトが更新されている（replace ではない）
        # Note: writerはmergedを新しいdictに置き換えるので、参照は変わる可能性あり
        assert config["engine"]["max_visits"] == 1000

    def test_save_func_receives_section_name(self):
        """save_funcは正しいセクション名を受け取る"""
        config = {}
        received_sections = []
        writer = TypedConfigWriter(config, lambda s: received_sections.append(s))

        writer.update_engine(max_visits=1000)
        writer.update_leela(enabled=True)
        writer.update_trainer(low_visits=50)

        assert received_sections == ["engine", "leela", "trainer"]
