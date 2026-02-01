# katrain/gui/features/types.py
#
# 型定義モジュール
#
# gui/features パッケージで使用する TypedDict を定義します。
# Kivy ウィジェットの型は Protocol や Union を使わず、
# Widget 基底クラスで緩く型付けします。

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Union

# Kivy imports for type hints only
if TYPE_CHECKING:
    from kivy.uix.button import Button
    from kivy.uix.checkbox import CheckBox
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.textinput import TextInput
    from kivy.uix.togglebutton import ToggleButton
    from kivy.uix.widget import Widget

# Use string literals for forward references
# This avoids Kivy import at runtime


# ---------------------------------------------------------------------------
# Batch UI Types
# ---------------------------------------------------------------------------

# TypedDict requires Python 3.8+ with typing_extensions or 3.9+ native
# Using Dict with documented keys for broader compatibility

# BatchWidgets: Dict returned by build_batch_popup_widgets()
# Keys:
#   - input_input: TextInput - 入力ディレクトリ
#   - output_input: TextInput - 出力ディレクトリ
#   - input_browse: Button - 入力ブラウズボタン
#   - output_browse: Button - 出力ブラウズボタン
#   - visits_input: TextInput - visits数入力
#   - timeout_input: TextInput - タイムアウト入力
#   - skip_checkbox: CheckBox - 解析済みスキップ
#   - save_sgf_checkbox: CheckBox - SGF保存
#   - karte_checkbox: CheckBox - カルテ生成
#   - summary_checkbox: CheckBox - サマリ生成
#   - filter_both: ToggleButton - 両プレイヤー
#   - filter_black: ToggleButton - 黒のみ
#   - filter_white: ToggleButton - 白のみ
#   - min_games_input: TextInput - 最小対局数
#   - jitter_input: TextInput - ジッター%
#   - variable_visits_checkbox: CheckBox - 可変visits
#   - deterministic_checkbox: CheckBox - 決定論的
#   - sound_checkbox: CheckBox - 完了時サウンド
#   - engine_katago: ToggleButton - KataGoエンジン選択 (Phase 36)
#   - engine_leela: ToggleButton - Leelaエンジン選択 (Phase 36)
#   - leela_warning_label: Label - Leela未有効警告 (Phase 36)
#   - progress_label: Label - 進行状況ラベル
#   - log_text: TextInput - ログテキスト
#   - log_scroll: ScrollView - ログスクロール
#   - start_button: Button - 開始ボタン
#   - close_button: Button - 閉じるボタン
BatchWidgets = dict[str, Any]  # More specific: dict[str, "Widget"]


# BatchOptions: Persisted batch analysis options
# Keys:
#   - visits: int | None - 探索回数
#   - timeout: float | None - タイムアウト秒
#   - skip_analyzed: bool - 解析済みスキップ
#   - save_analyzed_sgf: bool - SGF保存
#   - generate_karte: bool - カルテ生成
#   - generate_summary: bool - サマリ生成
#   - karte_player_filter: str | None - "B" or "W" or None
#   - min_games_per_player: int - 最小対局数
#   - jitter_pct: int - ジッター%
#   - variable_visits: bool - 可変visits
#   - deterministic: bool - 決定論的
#   - sound_on_finish: bool - 完了時サウンド
#   - analysis_engine: str - 解析エンジン "katago" or "leela" (Phase 36)
BatchOptions = dict[str, Any]


# ---------------------------------------------------------------------------
# Summary Stats Types
# ---------------------------------------------------------------------------

# GameStats: Statistics extracted from a single SGF file
# Keys:
#   - game_name: str - ファイル名
#   - player_black: str - 黒プレイヤー名
#   - player_white: str - 白プレイヤー名
#   - rank_black: str | None - 黒の段級位
#   - rank_white: str | None - 白の段級位
#   - handicap: int - ハンディキャップ
#   - date: str | None - 対局日
#   - board_size: tuple[int, int] - 盤サイズ
#   - total_moves: int - 総手数
#   - total_points_lost: float - 総損失
#   - moves_by_player: dict[str, int] - プレイヤー別手数
#   - loss_by_player: dict[str, float] - プレイヤー別損失
#   - mistake_counts: dict[MistakeCategory, int] - ミス分類別カウント
#   - mistake_total_loss: dict[MistakeCategory, float] - ミス分類別損失
#   - freedom_counts: dict[PositionDifficulty, int] - 難易度別カウント
#   - phase_moves: dict[str, int] - フェーズ別手数
#   - phase_loss: dict[str, float] - フェーズ別損失
#   - phase_mistake_counts: dict[tuple[str, MistakeCategory], int]
#   - phase_mistake_loss: dict[tuple[str, MistakeCategory], float]
#   - worst_moves: list[tuple[...]] - 悪手リスト
#   - reason_tags_counts: dict[str, int] - 理由タグカウント
GameStats = dict[str, Any]


# ---------------------------------------------------------------------------
# Callback Types
# ---------------------------------------------------------------------------

# Log function signature: (message: str, level: int) -> None
LogFunction = Callable[[str, int], None]

# Progress callback: (current: int, total: int, message: str) -> None
ProgressCallback = Callable[[int, int, str], None]
