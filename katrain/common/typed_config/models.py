# katrain/common/typed_config/models.py
#
# Frozen dataclass定義と型変換ヘルパー関数。
# Phase 99で追加。

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 認識されるbool文字列
_TRUE_STRINGS = frozenset({"true", "1", "yes"})
_FALSE_STRINGS = frozenset({"false", "0", "no"})


# =============================================================================
# Helper Functions
# =============================================================================


def safe_int(value: Any, default: int) -> int:
    """int変換。None/bool/float/変換失敗時はdefault。

    Args:
        value: 変換対象の値
        default: 変換失敗時のデフォルト値

    Returns:
        変換後のint値、または変換失敗時はdefault

    Note:
        boolはintのサブクラスだが、意図的にdefaultを返す。
        これはTrue→1, False→0の暗黙変換を防ぐため。
        floatも意図的にdefaultを返す（暗黙の切り捨てを防ぐため）。
    """
    if value is None:
        return default
    # boolはintのサブクラスだが、意図的にdefaultを返す
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    # floatは暗黙の切り捨てを防ぐためdefaultを返す
    if isinstance(value, float):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float) -> float:
    """float変換。None/bool/変換失敗時はdefault。

    Args:
        value: 変換対象の値
        default: 変換失敗時のデフォルト値

    Returns:
        変換後のfloat値、または変換失敗時はdefault

    Note:
        boolはintのサブクラスだが、意図的にdefaultを返す。
    """
    if value is None:
        return default
    # boolはintのサブクラスだが、意図的にdefaultを返す
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """bool変換。認識できない文字列はdefault（タイポ保護）。

    Args:
        value: 変換対象の値
        default: 変換失敗時またはNone時のデフォルト値

    Returns:
        変換後のbool値

    Note:
        認識できない文字列（"abc", "fasle"等のタイポ）はdefaultを返す。
        これにより設定ファイルのタイポを安全に処理できる。
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        if not value:  # empty string
            return default
        lower = value.lower()
        if lower in _TRUE_STRINGS:
            return True
        if lower in _FALSE_STRINGS:
            return False
        # 認識できない文字列（"abc", "fasle"等）→ default
        return default
    return default


def safe_str(value: Any, default: str) -> str:
    """文字列変換。None/空文字/非strはdefault。

    Args:
        value: 変換対象の値
        default: 変換失敗時のデフォルト値

    Returns:
        文字列値、または変換失敗時はdefault

    Note:
        str(None)="None"を防ぐため、Noneは明示的にdefaultを返す。
    """
    if value is None:
        return default
    if not isinstance(value, str):
        return default
    if not value:  # empty string
        return default
    return value


def normalize_path(value: Any) -> str | None:
    """パス正規化。None/空文字/空白のみ/非strはNone。有効パスはそのまま。

    Args:
        value: パス文字列

    Returns:
        有効なパス文字列、または無効な場合はNone

    Note:
        空白のみ（"   "）は無効なパスとして扱う。
        有効パスの先頭/末尾スペースは保持する（ファイルシステム依存のため）。
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    if not value.strip():  # 空白のみも含めて空とみなす
        return None
    return value  # 有効パスはそのまま（stripしない）


def safe_float_tuple(
    value: Any, default: tuple[float, ...]
) -> tuple[float, ...]:
    """list/tuple → Tuple[float, ...] 変換。長さ不一致/失敗時はdefault。

    Args:
        value: リストまたはタプル
        default: 変換失敗時のデフォルト値（長さの基準にもなる）

    Returns:
        変換後のfloatタプル、または変換失敗時はdefault

    Note:
        長さがdefaultと一致しない場合はdefaultを返す。
        これにより設定ファイルの不正な配列長を安全に処理できる。
    """
    if not isinstance(value, (list, tuple)):
        return default
    if len(value) != len(default):
        return default
    try:
        return tuple(float(x) for x in value)
    except (TypeError, ValueError):
        return default


def safe_bool_tuple(
    value: Any, default: tuple[bool, ...]
) -> tuple[bool, ...]:
    """list/tuple → Tuple[bool, ...] 変換。長さ不一致時はdefault。

    Args:
        value: リストまたはタプル
        default: 変換失敗時のデフォルト値（長さの基準にもなる）

    Returns:
        変換後のboolタプル、または変換失敗時はdefault

    Note:
        各要素にsafe_boolを適用（default=Falseで統一）。
    """
    if not isinstance(value, (list, tuple)):
        return default
    if len(value) != len(default):
        return default
    # 各要素にsafe_boolを適用（default=Falseで統一）
    return tuple(safe_bool(x, default=False) for x in value)


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True)
class EngineConfig:
    """KataGoエンジン設定（engineセクション）。

    Thread-safety: Immutable (frozen=True)

    Attributes:
        analysis_engine: 使用する解析エンジン名
        katago: KataGo実行ファイルのパス
        altcommand: 代替コマンド
        model: モデルファイルのパス
        humanlike_model: 人間らしいモデルのパス
        humanlike_model_last: 直前に使用した人間らしいモデルのパス
        config: KataGo設定ファイルのパス
        max_visits: 最大訪問回数
        fast_visits: 高速解析時の訪問回数
        max_time: 最大解析時間（秒）
        wide_root_noise: ルートノードのワイドノイズ
        enable_ownership: オーナーシップ表示の有効化

    Note:
        - config keyは `_enable_ownership`（先頭アンダースコア）
        - 将来の互換性のため `enable_ownership` も fallback として読む
    """

    analysis_engine: str = "katago"
    katago: str | None = None
    altcommand: str | None = None
    model: str | None = None
    humanlike_model: str | None = None
    humanlike_model_last: str | None = None
    config: str | None = None
    max_visits: int = 500
    fast_visits: int = 25
    max_time: float = 8.0
    wide_root_noise: float = 0.04
    enable_ownership: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EngineConfig":
        """dictから生成。欠損キーはデフォルト、型不正は安全に変換。

        Args:
            d: 設定辞書（engineセクション）

        Returns:
            EngineConfigインスタンス
        """
        # enable_ownership: 優先順位
        # 1. _enable_ownership (現行キー)
        # 2. enable_ownership (将来の正規キー候補)
        # 3. デフォルト True
        if "_enable_ownership" in d:
            enable_ownership_val = d["_enable_ownership"]
        elif "enable_ownership" in d:
            enable_ownership_val = d["enable_ownership"]
        else:
            enable_ownership_val = True

        return cls(
            analysis_engine=safe_str(d.get("analysis_engine"), "katago"),
            katago=normalize_path(d.get("katago")),
            altcommand=normalize_path(d.get("altcommand")),
            model=normalize_path(d.get("model")),
            humanlike_model=normalize_path(d.get("humanlike_model")),
            humanlike_model_last=normalize_path(d.get("humanlike_model_last")),
            config=normalize_path(d.get("config")),
            max_visits=safe_int(d.get("max_visits"), 500),
            fast_visits=safe_int(d.get("fast_visits"), 25),
            max_time=safe_float(d.get("max_time"), 8.0),
            wide_root_noise=safe_float(d.get("wide_root_noise"), 0.04),
            enable_ownership=safe_bool(enable_ownership_val, default=True),
        )


@dataclass(frozen=True)
class TrainerConfig:
    """トレーナー設定（trainerセクション）。

    Attributes:
        theme: UIテーマ名
        num_undo_prompts: Undoプロンプト表示確率（6要素タプル）
        eval_thresholds: 評価閾値（6要素タプル）
        save_feedback: フィードバック保存フラグ（6要素タプル）
        show_dots: ドット表示フラグ（6要素タプル）
        extra_precision: 追加精度モード
        save_analysis: 解析結果保存
        save_marks: マーク保存
        low_visits: 低訪問閾値
        eval_on_show_last: 表示時の評価手数
        top_moves_show: トップ手表示モード
        top_moves_show_secondary: セカンダリトップ手表示モード
        eval_show_ai: AI評価表示
        lock_ai: AIロック

    Note:
        リスト型フィールドはTupleに変換（frozen互換のため）。
        長さはdefaultと一致する必要がある（6要素）。
    """

    theme: str = "theme:normal"
    num_undo_prompts: tuple[float, ...] = (1.0, 1.0, 1.0, 0.5, 0.0, 0.0)
    eval_thresholds: tuple[float, ...] = (12.0, 6.0, 3.0, 1.5, 0.5, 0.0)
    save_feedback: tuple[bool, ...] = (True, True, True, True, False, False)
    show_dots: tuple[bool, ...] = (True, True, True, True, True, True)
    extra_precision: bool = False
    save_analysis: bool = False
    save_marks: bool = False
    low_visits: int = 25
    eval_on_show_last: int = 3
    top_moves_show: str = "top_move_delta_score"
    top_moves_show_secondary: str = "top_move_visits"
    eval_show_ai: bool = True
    lock_ai: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TrainerConfig":
        """dictから生成。JSON list → Tuple 変換（長さ検証あり）。

        Args:
            d: 設定辞書（trainerセクション）

        Returns:
            TrainerConfigインスタンス
        """
        return cls(
            theme=safe_str(d.get("theme"), "theme:normal"),
            num_undo_prompts=safe_float_tuple(
                d.get("num_undo_prompts"),
                (1.0, 1.0, 1.0, 0.5, 0.0, 0.0),
            ),
            eval_thresholds=safe_float_tuple(
                d.get("eval_thresholds"),
                (12.0, 6.0, 3.0, 1.5, 0.5, 0.0),
            ),
            save_feedback=safe_bool_tuple(
                d.get("save_feedback"),
                (True, True, True, True, False, False),
            ),
            show_dots=safe_bool_tuple(
                d.get("show_dots"),
                (True, True, True, True, True, True),
            ),
            extra_precision=safe_bool(d.get("extra_precision"), default=False),
            save_analysis=safe_bool(d.get("save_analysis"), default=False),
            save_marks=safe_bool(d.get("save_marks"), default=False),
            low_visits=safe_int(d.get("low_visits"), 25),
            eval_on_show_last=safe_int(d.get("eval_on_show_last"), 3),
            top_moves_show=safe_str(
                d.get("top_moves_show"), "top_move_delta_score"
            ),
            top_moves_show_secondary=safe_str(
                d.get("top_moves_show_secondary"), "top_move_visits"
            ),
            eval_show_ai=safe_bool(d.get("eval_show_ai"), default=True),
            lock_ai=safe_bool(d.get("lock_ai"), default=False),
        )


@dataclass(frozen=True)
class LeelaConfig:
    """Leela Zero設定（leelaセクション）。

    Attributes:
        enabled: Leela Zero有効化
        exe_path: 実行ファイルパス
        max_visits: 最大訪問回数
        fast_visits: 高速解析時の訪問回数
        play_visits: プレイ時の訪問回数
        loss_scale_k: 損失スケール係数
        resign_hint_enabled: 投了ヒント有効化
        resign_winrate_threshold: 投了勝率閾値（パーセント）
        resign_consecutive_moves: 投了連続手数
        top_moves_show: トップ手表示モード
        top_moves_show_secondary: セカンダリトップ手表示モード
    """

    enabled: bool = False
    exe_path: str | None = None
    max_visits: int = 1000
    fast_visits: int = 200
    play_visits: int = 500
    loss_scale_k: float = 0.5
    resign_hint_enabled: bool = False
    resign_winrate_threshold: int = 5
    resign_consecutive_moves: int = 3
    top_moves_show: str = "leela_top_move_loss"
    top_moves_show_secondary: str = "leela_top_move_winrate"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LeelaConfig":
        """dictから生成。

        Args:
            d: 設定辞書（leelaセクション）

        Returns:
            LeelaConfigインスタンス
        """
        return cls(
            enabled=safe_bool(d.get("enabled"), default=False),
            exe_path=normalize_path(d.get("exe_path")),
            max_visits=safe_int(d.get("max_visits"), 1000),
            fast_visits=safe_int(d.get("fast_visits"), 200),
            play_visits=safe_int(d.get("play_visits"), 500),
            loss_scale_k=safe_float(d.get("loss_scale_k"), 0.5),
            resign_hint_enabled=safe_bool(
                d.get("resign_hint_enabled"), default=False
            ),
            resign_winrate_threshold=safe_int(
                d.get("resign_winrate_threshold"), 5
            ),
            resign_consecutive_moves=safe_int(
                d.get("resign_consecutive_moves"), 3
            ),
            top_moves_show=safe_str(
                d.get("top_moves_show"), "leela_top_move_loss"
            ),
            top_moves_show_secondary=safe_str(
                d.get("top_moves_show_secondary"), "leela_top_move_winrate"
            ),
        )
