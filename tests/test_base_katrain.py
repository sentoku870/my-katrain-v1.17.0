"""Tests for katrain.core.base_katrain module.

Phase 69: Test coverage expansion.

Config I/O Isolation:
- force_package_config=True を使用してUSER_CONFIG_FILEの読み書きを回避
- CIで環境リークが発生した場合は tmp_path + monkeypatch を検討
"""
import pytest
from katrain.core.base_katrain import (
    KaTrainBase,
    Player,
    parse_version,
)
from katrain.core.constants import (
    PLAYER_HUMAN,
    PLAYER_AI,
    PLAYING_NORMAL,
    PLAYING_TEACHING,
    AI_DEFAULT,
    OUTPUT_INFO,
    OUTPUT_ERROR,
)


class TestParseVersion:
    """parse_version() tests（list戻り値確認済み）"""

    def test_standard_version(self):
        """X.Y.Z形式"""
        result = parse_version("1.17.0")
        assert result == [1, 17, 0]
        assert isinstance(result, list)

    def test_two_part_version(self):
        """X.Y形式（パディング）"""
        assert parse_version("1.5") == [1, 5, 0]

    def test_single_part_version(self):
        """X形式（パディング）"""
        assert parse_version("2") == [2, 0, 0]

    def test_version_comparison(self):
        """バージョン比較"""
        v1 = parse_version("1.16.0")
        v2 = parse_version("1.17.0")
        assert v1 < v2


class TestPlayerClass:
    def test_init_defaults(self):
        """デフォルト初期化"""
        p = Player("B")
        assert p.player == "B"
        assert p.human is True
        assert p.ai is False

    def test_ai_property(self):
        """aiプロパティ"""
        p = Player("W", player_type=PLAYER_AI)
        assert p.ai is True
        assert p.human is False

    def test_being_taught_true(self):
        """教学モード判定（True）"""
        p = Player("B", player_type=PLAYER_HUMAN, player_subtype=PLAYING_TEACHING)
        assert p.being_taught is True

    def test_being_taught_false(self):
        """通常モード判定（False）"""
        p = Player("B", player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL)
        assert p.being_taught is False

    def test_strategy_ai(self):
        """AI戦略取得"""
        p = Player("B", player_type=PLAYER_AI, player_subtype="jigo")
        assert p.strategy == "jigo"

    def test_strategy_human(self):
        """人間のデフォルト戦略"""
        p = Player("B", player_type=PLAYER_HUMAN)
        assert p.strategy == AI_DEFAULT

    def test_update(self):
        """updateメソッド"""
        p = Player("B")
        p.update(player_type=PLAYER_AI, player_subtype="strong")
        assert p.ai is True
        assert p.player_subtype == "strong"


class TestKaTrainBaseConfig:
    """KaTrainBase.config() tests.

    Isolation: force_package_config=True
    """

    def test_config_simple_key(self):
        """単純キー取得"""
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        assert katrain.config("general") is not None

    def test_config_hierarchical_key_with_default(self):
        """階層キー取得（cat/key）- デフォルト値付きで型を確認

        Note: デフォルト値を渡すことで、キーが存在しない場合でもテストが安定する
        """
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        result = katrain.config("general/debug_level", default=0)
        assert isinstance(result, int)

    def test_config_missing_key_returns_default(self):
        """不在キーのデフォルト値"""
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        result = katrain.config("nonexistent/key", default="fallback")
        assert result == "fallback"

    def test_config_missing_category_returns_default(self):
        """不在カテゴリのデフォルト値"""
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        result = katrain.config("nonexistent_category/key", default=42)
        assert result == 42


class TestKaTrainBaseLogging:
    """Logging tests.

    実装確認済み: log()は常に_log_buffer.append()を呼ぶ
    （base_katrain.py:131）
    debug_levelはコンソール出力のみに影響し、バッファ記録には影響しない
    """

    def test_log_info_recorded_in_buffer(self):
        """OUTPUT_INFOレベルのログがバッファに記録される"""
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        katrain.log("test info message", level=OUTPUT_INFO)
        logs = katrain.get_recent_logs()
        assert any("test info message" in line for line in logs)

    def test_log_error_recorded_in_buffer(self):
        """OUTPUT_ERRORレベルのログがバッファに記録される"""
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        katrain.log("error message", level=OUTPUT_ERROR)
        logs = katrain.get_recent_logs()
        assert any("error message" in line for line in logs)
