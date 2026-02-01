# katrain/common/typed_config/writer.py
"""型付き設定更新API（Phase 101）。

MERGEパターンで既存値を保持しつつ、指定されたキーのみ更新。
フィールド名検証により、存在しないキーは UnknownFieldError。
"""

from __future__ import annotations

import logging
from dataclasses import fields, is_dataclass
from typing import Any, Callable, Dict, Type, cast

from katrain.common.typed_config.models import (
    EngineConfig,
    LeelaConfig,
    TrainerConfig,
)


class UnknownFieldError(AttributeError):
    """存在しないフィールドへのアクセス時に発生。"""

    pass


def _to_json_safe(value: Any) -> Any:
    """値をJSONシリアライズ可能な形式に変換。

    - tuple -> list
    - Path-like -> str
    - 再帰的に変換

    Args:
        value: 変換対象の値

    Returns:
        JSONシリアライズ可能な値
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, tuple):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    # Path-like objects
    if hasattr(value, "__fspath__"):
        return str(value)
    # Fallback: try str conversion
    return str(value)


class TypedConfigWriter:
    """型付き設定更新API。

    MERGEパターンで既存値を保持しつつ、指定されたキーのみ更新。
    フィールド名検証により、存在しないキーは UnknownFieldError。
    型変換は from_dict() に委譲（既存ロジック再利用）。
    自動保存（save_config(section)）。

    Persistence policy:
        - Updated fields are persisted with normalized, JSON-safe values
        - Unknown keys are preserved (forward/backward compatibility)
        - Unspecified known fields keep existing values

    Invalid value handling:
        - Invalid values are normalized to defaults
        - A WARNING is logged when unexpected normalization occurs
        - The normalized value (not the invalid input) is persisted

    Requirements:
        - config_cls must be a dataclass (enforced at runtime)

    Example:
        >>> writer = TypedConfigWriter(config_dict, save_func)
        >>> result = writer.update_engine(max_visits=1000)
        >>> assert result.max_visits == 1000
    """

    def __init__(
        self,
        config_dict: Dict[str, Any],
        save_func: Callable[[str], None],
    ) -> None:
        """Initialize the writer.

        Args:
            config_dict: Reference to the config dictionary (will be mutated)
            save_func: Function to call for saving a section (receives section name)
        """
        self._config = config_dict
        self._save = save_func

    def update_engine(self, **kwargs: Any) -> EngineConfig:
        """engineセクションを部分更新。

        Args:
            **kwargs: 更新するフィールドと値

        Returns:
            更新後のEngineConfig（frozen）

        Raises:
            UnknownFieldError: 存在しないフィールド名が指定された場合
            TypeError: config_clsがdataclassでない場合
        """
        return cast(EngineConfig, self._update_section("engine", EngineConfig, kwargs))

    def update_trainer(self, **kwargs: Any) -> TrainerConfig:
        """trainerセクションを部分更新。

        Args:
            **kwargs: 更新するフィールドと値

        Returns:
            更新後のTrainerConfig（frozen）

        Raises:
            UnknownFieldError: 存在しないフィールド名が指定された場合
            TypeError: config_clsがdataclassでない場合
        """
        return cast(TrainerConfig, self._update_section("trainer", TrainerConfig, kwargs))

    def update_leela(self, **kwargs: Any) -> LeelaConfig:
        """leelaセクションを部分更新。

        Args:
            **kwargs: 更新するフィールドと値

        Returns:
            更新後のLeelaConfig（frozen）

        Raises:
            UnknownFieldError: 存在しないフィールド名が指定された場合
            TypeError: config_clsがdataclassでない場合
        """
        return cast(LeelaConfig, self._update_section("leela", LeelaConfig, kwargs))

    def _update_section(
        self,
        section: str,
        config_cls: type[EngineConfig] | type[TrainerConfig] | type[LeelaConfig],
        updates: Dict[str, Any],
    ) -> EngineConfig | TrainerConfig | LeelaConfig:
        """セクションを部分更新（内部実装）。

        Args:
            section: セクション名（"engine", "trainer", "leela"）
            config_cls: dataclassモデル
            updates: 更新するフィールドと値

        Returns:
            更新後の設定インスタンス

        Raises:
            UnknownFieldError: 存在しないフィールド名が指定された場合
            TypeError: config_clsがdataclassでない場合
        """
        # 0. Dataclass要件チェック
        if not is_dataclass(config_cls):
            raise TypeError(
                f"{config_cls.__name__} is not a dataclass. "
                "TypedConfigWriter requires dataclass models."
            )

        # 1. フィールド名検証
        valid_fields = {f.name for f in fields(config_cls)}
        unknown = set(updates.keys()) - valid_fields
        if unknown:
            sorted_unknown = sorted(unknown)
            raise UnknownFieldError(
                f"{config_cls.__name__} has no field(s): {sorted_unknown}"
            )

        # 2. 既存dict取得 -> Shallow MERGE
        existing = self._config.get(section)
        merged = dict(existing) if isinstance(existing, dict) else {}
        merged.update(updates)

        # 3. parse_dict作成（既知フィールドのみ）
        parse_dict = {k: v for k, v in merged.items() if k in valid_fields}

        # 4. from_dict()で型変換
        validated = config_cls.from_dict(parse_dict)

        # 5. 永続化用dict構築（JSON-safe + 警告）
        persist = dict(merged)
        for key, input_val in updates.items():
            normalized_val = getattr(validated, key)
            json_safe_val = _to_json_safe(normalized_val)
            persist[key] = json_safe_val

            if self._should_warn(input_val, normalized_val):
                logging.getLogger("katrain").warning(
                    "TypedConfigWriter: %s.%s value %r was normalized to %r",
                    config_cls.__name__,
                    key,
                    input_val,
                    normalized_val,
                )

        # 6. _configに書き戻し
        self._config[section] = persist

        # 7. save_config(section)
        self._save(section)

        return validated

    def _should_warn(self, input_val: Any, output_val: Any) -> bool:
        """入力値と出力値の差異が警告すべきものかどうか。

        警告する: デフォルト値へのフォールバック（無効な入力）
        警告しない: 期待される型変換（str->int, list->tuple, ""->None）

        Args:
            input_val: 更新時に渡された値
            output_val: 正規化後の値

        Returns:
            True: 警告すべき（予期しない正規化）
            False: 警告不要（期待される変換）
        """
        # 同一値
        if input_val == output_val:
            return False

        # "" -> None (normalize_path)
        if input_val == "" and output_val is None:
            return False

        # list <-> tuple（等価なコンテナ）
        if isinstance(input_val, (list, tuple)) and isinstance(
            output_val, (list, tuple)
        ):
            return list(input_val) != list(output_val)

        # 文字列 -> 数値（有効な変換）
        if isinstance(input_val, str) and isinstance(output_val, (int, float)):
            try:
                if isinstance(output_val, int):
                    return int(input_val) != output_val
                return float(input_val) != output_val
            except ValueError:
                return True  # 変換失敗 = 警告

        # その他の差異は警告
        return True
