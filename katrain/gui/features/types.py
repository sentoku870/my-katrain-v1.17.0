# katrain/gui/features/types.py
#
# 型定義モジュール
#
# gui/features パッケージで使用する TypedDict を定義します。
# Kivy ウィジェットの型は Protocol や Union を使わず、
# Widget 基底クラスで緩く型付けします。

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

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
#   - progress_label: Label - 進行状況ラベル
#   - log_text: TextInput - ログテキスト
#   - log_scroll: ScrollView - ログスクロール
#   - start_button: Button - 開始ボタン
#   - close_button: Button - 閉じるボタン
BatchWidgets = Dict[str, Any]  # More specific: Dict[str, "Widget"]


# BatchOptions: Persisted batch analysis options
# Keys:
#   - visits: Optional[int] - 探索回数
#   - timeout: Optional[float] - タイムアウト秒
#   - skip_analyzed: bool - 解析済みスキップ
#   - save_analyzed_sgf: bool - SGF保存
#   - generate_karte: bool - カルテ生成
#   - generate_summary: bool - サマリ生成
#   - karte_player_filter: Optional[str] - "B" or "W" or None
#   - min_games_per_player: int - 最小対局数
#   - jitter_pct: int - ジッター%
#   - variable_visits: bool - 可変visits
#   - deterministic: bool - 決定論的
#   - sound_on_finish: bool - 完了時サウンド
BatchOptions = Dict[str, Any]


# ---------------------------------------------------------------------------
# Summary Stats Types
# ---------------------------------------------------------------------------

# GameStats: Statistics extracted from a single SGF file
# Keys:
#   - game_name: str - ファイル名
#   - player_black: str - 黒プレイヤー名
#   - player_white: str - 白プレイヤー名
#   - rank_black: Optional[str] - 黒の段級位
#   - rank_white: Optional[str] - 白の段級位
#   - handicap: int - ハンディキャップ
#   - date: Optional[str] - 対局日
#   - board_size: Tuple[int, int] - 盤サイズ
#   - total_moves: int - 総手数
#   - total_points_lost: float - 総損失
#   - moves_by_player: Dict[str, int] - プレイヤー別手数
#   - loss_by_player: Dict[str, float] - プレイヤー別損失
#   - mistake_counts: Dict[MistakeCategory, int] - ミス分類別カウント
#   - mistake_total_loss: Dict[MistakeCategory, float] - ミス分類別損失
#   - freedom_counts: Dict[PositionDifficulty, int] - 難易度別カウント
#   - phase_moves: Dict[str, int] - フェーズ別手数
#   - phase_loss: Dict[str, float] - フェーズ別損失
#   - phase_mistake_counts: Dict[Tuple[str, MistakeCategory], int]
#   - phase_mistake_loss: Dict[Tuple[str, MistakeCategory], float]
#   - worst_moves: List[Tuple[...]] - 悪手リスト
#   - reason_tags_counts: Dict[str, int] - 理由タグカウント
GameStats = Dict[str, Any]


# ---------------------------------------------------------------------------
# Callback Types
# ---------------------------------------------------------------------------

# Log function signature: (message: str, level: int) -> None
LogFunction = Callable[[str, int], None]

# Progress callback: (current: int, total: int, message: str) -> None
ProgressCallback = Callable[[int, int, str], None]
