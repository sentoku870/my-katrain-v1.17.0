# katrain/common/typed_config - 型付き設定アクセサ
#
# frozen dataclassで設定セクションを型付けし、
# get_<section>()メソッドで型安全なアクセスを提供。
#
# Phase 99で追加。既存のconfig()は維持（後方互換）。
# Phase 101で更新API追加。

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
from katrain.common.typed_config.reader import TypedConfigReader
from katrain.common.typed_config.writer import (
    TypedConfigWriter,
    UnknownFieldError,
    _to_json_safe,
)

__all__ = [
    # Dataclasses
    "EngineConfig",
    "LeelaConfig",
    "TrainerConfig",
    # Reader
    "TypedConfigReader",
    # Writer (Phase 101)
    "TypedConfigWriter",
    "UnknownFieldError",
    "_to_json_safe",
    # Helper functions
    "safe_int",
    "safe_float",
    "safe_bool",
    "safe_str",
    "normalize_path",
    "safe_float_tuple",
    "safe_bool_tuple",
]
