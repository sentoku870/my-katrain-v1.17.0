# tests/test_typed_config_models.py
#
# Unit tests for katrain.common.typed_config.models
# Phase 99

from dataclasses import FrozenInstanceError

import pytest

from katrain.common.typed_config.models import (
    EngineConfig,
    LeelaConfig,
    TrainerConfig,
    normalize_path,
    safe_bool,
    safe_bool_tuple,
    safe_float,
    safe_float_tuple,
    safe_int,
    safe_str,
)


# =============================================================================
# safe_int tests
# =============================================================================


class TestSafeInt:
    def test_none_returns_default(self):
        assert safe_int(None, 100) == 100

    def test_int_returns_as_is(self):
        assert safe_int(500, 100) == 500

    def test_zero_returns_zero(self):
        assert safe_int(0, 100) == 0

    def test_negative_int_returns_as_is(self):
        assert safe_int(-50, 100) == -50

    def test_string_int_converted(self):
        assert safe_int("500", 100) == 500

    def test_string_negative_int_converted(self):
        assert safe_int("-50", 100) == -50

    def test_invalid_string_returns_default(self):
        assert safe_int("abc", 100) == 100

    def test_empty_string_returns_default(self):
        assert safe_int("", 100) == 100

    def test_list_returns_default(self):
        assert safe_int([], 100) == 100

    def test_dict_returns_default(self):
        assert safe_int({}, 100) == 100

    def test_bool_true_returns_default(self):
        """boolはintに変換しない"""
        assert safe_int(True, 100) == 100

    def test_bool_false_returns_default(self):
        """boolはintに変換しない"""
        assert safe_int(False, 100) == 100

    def test_float_returns_default(self):
        """floatはintに変換しない（暗黙の切り捨てを防ぐ）"""
        assert safe_int(3.14, 100) == 100

    def test_float_string_returns_default(self):
        """float文字列はintに変換しない"""
        assert safe_int("3.14", 100) == 100


# =============================================================================
# safe_float tests
# =============================================================================


class TestSafeFloat:
    def test_none_returns_default(self):
        assert safe_float(None, 1.0) == 1.0

    def test_float_returns_as_is(self):
        assert safe_float(8.0, 1.0) == 8.0

    def test_zero_returns_zero(self):
        assert safe_float(0.0, 1.0) == 0.0

    def test_negative_float_returns_as_is(self):
        assert safe_float(-3.14, 1.0) == -3.14

    def test_string_float_converted(self):
        assert safe_float("8.0", 1.0) == 8.0

    def test_string_negative_float_converted(self):
        assert safe_float("-3.14", 1.0) == -3.14

    def test_int_converted_to_float(self):
        assert safe_float(8, 1.0) == 8.0

    def test_zero_int_converted_to_float(self):
        assert safe_float(0, 1.0) == 0.0

    def test_invalid_string_returns_default(self):
        assert safe_float("abc", 1.0) == 1.0

    def test_empty_string_returns_default(self):
        assert safe_float("", 1.0) == 1.0

    def test_list_returns_default(self):
        assert safe_float([], 1.0) == 1.0

    def test_bool_true_returns_default(self):
        """boolはfloatに変換しない"""
        assert safe_float(True, 1.0) == 1.0

    def test_bool_false_returns_default(self):
        """boolはfloatに変換しない"""
        assert safe_float(False, 1.0) == 1.0


# =============================================================================
# safe_bool tests
# =============================================================================


class TestSafeBool:
    def test_true_false(self):
        assert safe_bool(True) is True
        assert safe_bool(False) is False

    def test_int_1_0(self):
        assert safe_bool(1) is True
        assert safe_bool(0) is False

    def test_int_other_nonzero(self):
        assert safe_bool(42) is True
        assert safe_bool(-1) is True

    def test_string_true_false(self):
        assert safe_bool("true") is True
        assert safe_bool("false") is False
        assert safe_bool("TRUE") is True
        assert safe_bool("FALSE") is False
        assert safe_bool("True") is True
        assert safe_bool("False") is False

    def test_string_1_0(self):
        assert safe_bool("1") is True
        assert safe_bool("0") is False

    def test_string_yes_no(self):
        assert safe_bool("yes") is True
        assert safe_bool("no") is False
        assert safe_bool("YES") is True
        assert safe_bool("NO") is False

    def test_empty_string_returns_default(self):
        assert safe_bool("") is False  # default=False
        assert safe_bool("", default=True) is True

    def test_none_returns_default(self):
        assert safe_bool(None) is False
        assert safe_bool(None, default=True) is True

    def test_unknown_string_returns_default(self):
        """タイポ保護: 認識できない文字列はdefaultを返す"""
        assert safe_bool("abc") is False  # default
        assert safe_bool("abc", default=True) is True
        assert safe_bool("fasle") is False  # typo of "false"
        assert safe_bool("treu") is False  # typo of "true"
        assert safe_bool("maybe") is False

    def test_list_returns_default(self):
        assert safe_bool([]) is False
        assert safe_bool([1, 2]) is False


# =============================================================================
# safe_str tests
# =============================================================================


class TestSafeStr:
    def test_none_returns_default(self):
        assert safe_str(None, "default") == "default"

    def test_empty_string_returns_default(self):
        assert safe_str("", "default") == "default"

    def test_valid_string_preserved(self):
        assert safe_str("theme:normal", "default") == "theme:normal"

    def test_whitespace_only_preserved(self):
        """空白のみの文字列は有効な文字列として扱う"""
        assert safe_str("   ", "default") == "   "

    def test_non_string_returns_default(self):
        assert safe_str(123, "default") == "default"
        assert safe_str([], "default") == "default"
        assert safe_str({}, "default") == "default"
        assert safe_str(True, "default") == "default"


# =============================================================================
# normalize_path tests
# =============================================================================


class TestNormalizePath:
    def test_none(self):
        assert normalize_path(None) is None

    def test_empty_string(self):
        assert normalize_path("") is None

    def test_whitespace_only(self):
        assert normalize_path("   ") is None
        assert normalize_path("\t\n") is None

    def test_valid_path_preserved(self):
        assert normalize_path("C:\\katago.exe") == "C:\\katago.exe"
        assert normalize_path("/usr/bin/katago") == "/usr/bin/katago"

    def test_path_with_leading_trailing_spaces_preserved(self):
        # 有効なパスはstripしない（先頭/末尾スペースも保持）
        assert normalize_path("  /path/to/file  ") == "  /path/to/file  "

    def test_non_string_returns_none(self):
        assert normalize_path(123) is None
        assert normalize_path([]) is None
        assert normalize_path({}) is None


# =============================================================================
# safe_float_tuple tests
# =============================================================================


class TestSafeFloatTuple:
    def test_valid_list_converted(self):
        result = safe_float_tuple([12, 6, 3, 1.5, 0.5, 0], (0.0,) * 6)
        assert result == (12.0, 6.0, 3.0, 1.5, 0.5, 0.0)
        assert isinstance(result, tuple)

    def test_valid_tuple_converted(self):
        result = safe_float_tuple((12, 6, 3, 1.5, 0.5, 0), (0.0,) * 6)
        assert result == (12.0, 6.0, 3.0, 1.5, 0.5, 0.0)

    def test_length_mismatch_returns_default(self):
        default = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        assert safe_float_tuple([12, 6, 3], default) == default

    def test_longer_list_returns_default(self):
        default = (1.0, 2.0)
        assert safe_float_tuple([12, 6, 3, 4, 5], default) == default

    def test_empty_list_returns_default(self):
        default = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        assert safe_float_tuple([], default) == default

    def test_invalid_element_returns_default(self):
        default = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        assert safe_float_tuple(["a", "b", "c", "d", "e", "f"], default) == default

    def test_mixed_valid_invalid_returns_default(self):
        default = (1.0, 2.0, 3.0)
        assert safe_float_tuple([1, "invalid", 3], default) == default

    def test_none_returns_default(self):
        default = (1.0, 2.0)
        assert safe_float_tuple(None, default) == default

    def test_string_returns_default(self):
        default = (1.0, 2.0)
        assert safe_float_tuple("12", default) == default

    def test_empty_default(self):
        """空のdefaultに対しては空リストのみマッチ"""
        assert safe_float_tuple([], ()) == ()
        assert safe_float_tuple([1], ()) == ()


# =============================================================================
# safe_bool_tuple tests
# =============================================================================


class TestSafeBoolTuple:
    def test_valid_list_converted(self):
        result = safe_bool_tuple([True, False, True], (False, False, False))
        assert result == (True, False, True)
        assert isinstance(result, tuple)

    def test_int_values_converted(self):
        result = safe_bool_tuple([1, 0, 1], (False, False, False))
        assert result == (True, False, True)

    def test_length_mismatch_returns_default(self):
        default = (True, True, True)
        assert safe_bool_tuple([True, False], default) == default

    def test_empty_list_returns_default(self):
        default = (True, False, True)
        assert safe_bool_tuple([], default) == default

    def test_none_returns_default(self):
        default = (True, False)
        assert safe_bool_tuple(None, default) == default

    def test_unknown_string_in_list(self):
        """認識できない文字列はFalse（safe_boolのdefault）になる"""
        result = safe_bool_tuple(["true", "abc", "false"], (False, False, False))
        assert result == (True, False, False)


# =============================================================================
# EngineConfig tests
# =============================================================================


class TestEngineConfigFromDict:
    def test_all_fields_populated(self):
        cfg = EngineConfig.from_dict(
            {
                "analysis_engine": "leela",
                "max_visits": 1000,
                "max_time": 10.0,
            }
        )
        assert cfg.analysis_engine == "leela"
        assert cfg.max_visits == 1000
        assert cfg.max_time == 10.0

    def test_missing_fields_use_defaults(self):
        cfg = EngineConfig.from_dict({})
        assert cfg.analysis_engine == "katago"
        assert cfg.max_visits == 500
        assert cfg.fast_visits == 25
        assert cfg.max_time == 8.0
        assert cfg.wide_root_noise == 0.04
        assert cfg.enable_ownership is True

    def test_enable_ownership_underscore_key(self):
        """現行キー: _enable_ownership"""
        cfg = EngineConfig.from_dict({"_enable_ownership": False})
        assert cfg.enable_ownership is False

    def test_enable_ownership_no_underscore_key(self):
        """将来キー: enable_ownership（fallback）"""
        cfg = EngineConfig.from_dict({"enable_ownership": False})
        assert cfg.enable_ownership is False

    def test_enable_ownership_underscore_takes_precedence(self):
        """_enable_ownership が enable_ownership より優先"""
        cfg = EngineConfig.from_dict(
            {
                "_enable_ownership": True,
                "enable_ownership": False,
            }
        )
        assert cfg.enable_ownership is True

    def test_path_fields_normalized(self):
        cfg = EngineConfig.from_dict(
            {
                "katago": "C:\\katago.exe",
                "model": "",  # empty -> None
                "config": "   ",  # whitespace only -> None
            }
        )
        assert cfg.katago == "C:\\katago.exe"
        assert cfg.model is None
        assert cfg.config is None

    def test_type_conversion(self):
        """文字列の数値は変換される"""
        cfg = EngineConfig.from_dict(
            {
                "max_visits": "1000",
                "max_time": "10.5",
            }
        )
        assert cfg.max_visits == 1000
        assert cfg.max_time == 10.5

    def test_invalid_type_uses_default(self):
        """無効な型はデフォルト値を使用"""
        cfg = EngineConfig.from_dict(
            {
                "max_visits": "invalid",
                "max_time": [],
            }
        )
        assert cfg.max_visits == 500
        assert cfg.max_time == 8.0

    def test_frozen_immutability(self):
        cfg = EngineConfig.from_dict({})
        with pytest.raises(FrozenInstanceError):
            cfg.max_visits = 1000  # type: ignore


# =============================================================================
# TrainerConfig tests
# =============================================================================


class TestTrainerConfigFromDict:
    def test_list_to_tuple_with_correct_length(self):
        cfg = TrainerConfig.from_dict({"eval_thresholds": [12, 6, 3, 1.5, 0.5, 0]})
        assert cfg.eval_thresholds == (12.0, 6.0, 3.0, 1.5, 0.5, 0.0)
        assert isinstance(cfg.eval_thresholds, tuple)

    def test_wrong_length_list_uses_default(self):
        cfg = TrainerConfig.from_dict({"eval_thresholds": [12, 6, 3]})
        assert cfg.eval_thresholds == (12.0, 6.0, 3.0, 1.5, 0.5, 0.0)

    def test_empty_list_uses_default(self):
        cfg = TrainerConfig.from_dict({"eval_thresholds": []})
        assert cfg.eval_thresholds == (12.0, 6.0, 3.0, 1.5, 0.5, 0.0)

    def test_bool_tuple_conversion(self):
        cfg = TrainerConfig.from_dict(
            {"save_feedback": [True, False, True, False, True, False]}
        )
        assert cfg.save_feedback == (True, False, True, False, True, False)

    def test_missing_fields_use_defaults(self):
        cfg = TrainerConfig.from_dict({})
        assert cfg.theme == "theme:normal"
        assert cfg.low_visits == 25
        assert cfg.eval_on_show_last == 3
        assert cfg.extra_precision is False
        assert cfg.eval_show_ai is True

    def test_frozen_immutability(self):
        cfg = TrainerConfig.from_dict({})
        with pytest.raises(FrozenInstanceError):
            cfg.theme = "other"  # type: ignore


# =============================================================================
# LeelaConfig tests
# =============================================================================


class TestLeelaConfigFromDict:
    def test_enabled_false_by_default(self):
        cfg = LeelaConfig.from_dict({})
        assert cfg.enabled is False

    def test_enabled_true(self):
        cfg = LeelaConfig.from_dict({"enabled": True})
        assert cfg.enabled is True

    def test_exe_path_empty_becomes_none(self):
        cfg = LeelaConfig.from_dict({"exe_path": ""})
        assert cfg.exe_path is None

    def test_exe_path_valid(self):
        cfg = LeelaConfig.from_dict({"exe_path": "C:\\leela.exe"})
        assert cfg.exe_path == "C:\\leela.exe"

    def test_all_defaults(self):
        cfg = LeelaConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.exe_path is None
        assert cfg.max_visits == 1000
        assert cfg.fast_visits == 200
        assert cfg.play_visits == 500
        assert cfg.loss_scale_k == 0.5
        assert cfg.resign_hint_enabled is False
        assert cfg.resign_winrate_threshold == 5
        assert cfg.resign_consecutive_moves == 3

    def test_frozen_immutability(self):
        cfg = LeelaConfig.from_dict({})
        with pytest.raises(FrozenInstanceError):
            cfg.enabled = True  # type: ignore
