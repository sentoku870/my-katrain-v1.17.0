"""サマリエクスポート管理マネージャー（Phase 96）

SummaryManagerはKaTrainGuiのサマリエクスポート責務を担当する。

Kivy依存性:
- import/インスタンス化: Kivy不要（ローカルインポート使用）
- UI実行（do_export_summary等）: Kivy必要（summary_ui.py経由）

使用例:
    from katrain.gui.managers.summary_manager import SummaryManager

    manager = SummaryManager(
        get_ctx=lambda: self,
        get_engine=lambda: self.engine,
        get_config=self.config,
        config_manager=self._config_manager,
        logger=self.log,
    )

    manager.do_export_summary()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine
    from katrain.gui.features.context import FeatureContext
    from katrain.gui.managers.config_manager import ConfigManager


class SummaryManager:
    """サマリエクスポートの調整

    責務:
    - サマリエクスポートの開始・進行管理
    - 既存summary_*.pyモジュールの呼び出し調整
    - 設定読み書きの連携（ConfigManager経由）

    設計:
    - import/インスタンス化はKivy非依存（ユニットテスト可能）
    - UI実行時はKivy必要（summary_ui.py経由）
    - 依存注入パターン（テスト容易性）
    - ConfigManagerパターンに準拠
    """

    def __init__(
        self,
        get_ctx: Callable[[], "FeatureContext"],
        get_engine: Callable[[], "KataGoEngine" | None],
        get_config: Callable[[str, Any], Any],
        config_manager: "ConfigManager",
        logger: Callable[[str, int], None],
    ):
        """SummaryManagerを初期化する。

        Args:
            get_ctx: FeatureContext取得コールバック
            get_engine: KataGoEngine取得コールバック（None可）
            get_config: 設定値取得コールバック（config(key, default)形式）
            config_manager: ConfigManagerインスタンス
            logger: ロギングコールバック（logger(message, level)形式、KaTrainGui.log互換）
        """
        self._get_ctx = get_ctx
        self._get_engine = get_engine
        self._get_config = get_config
        self._config_manager = config_manager
        self._logger = logger

    # ========== 設定アクセス（ConfigManager経由・内部用） ==========

    def _load_export_settings(self) -> dict[str, Any]:
        """エクスポート設定をロード（内部用）"""
        return self._config_manager.load_export_settings()

    def _save_export_settings(
        self, sgf_directory: str | None = None, selected_players: list[str] | None = None
    ) -> None:
        """エクスポート設定を保存（内部用）"""
        self._config_manager.save_export_settings(sgf_directory, selected_players)

    # ========== Public API（KaTrainGui互換エントリポイント） ==========

    def do_export_summary(self, *args: Any, **kwargs: Any) -> None:
        """Schedule summary export on the main Kivy thread.

        Note: *args, **kwargs preserved for Kivy callback compatibility.
        Requires Kivy runtime.
        """
        # Local import to avoid circular dependency and defer Kivy import
        from katrain.gui.features.summary_ui import do_export_summary as _do_export_summary

        _do_export_summary(
            self._get_ctx(),
            self.scan_and_show_player_selection,
            self._load_export_settings,
            self._save_export_settings,
        )

    def do_export_summary_ui(self, *args: Any, **kwargs: Any) -> None:
        """Execute summary export UI flow.

        Note: *args, **kwargs preserved for Kivy callback compatibility.
        Requires Kivy runtime.
        """
        from katrain.gui.features.summary_ui import do_export_summary_ui as _do_export_summary_ui

        _do_export_summary_ui(
            self._get_ctx(),
            self.scan_and_show_player_selection,
            self._load_export_settings,
            self._save_export_settings,
        )

    # ========== Public API（Pure関数ラッパー・Kivy不要） ==========

    def extract_analysis_from_sgf_node(self, node: Any) -> dict[str, Any] | None:
        """SGFノードのKTプロパティから解析データを抽出。"""
        from katrain.gui.features.summary_stats import extract_analysis_from_sgf_node as _extract

        return _extract(node)

    def extract_sgf_statistics(self, path: str) -> dict[str, Any] | None:
        """SGFファイルから統計データを直接抽出。"""
        from katrain.gui.features.summary_stats import extract_sgf_statistics as _extract

        engine = self._get_engine()
        if not engine:
            return None
        return _extract(path, self._get_ctx(), engine, self._logger)

    def scan_player_names(self, sgf_files: list[str]) -> dict[str, Any]:
        """SGFファイル群からプレイヤー名をスキャン。"""
        from katrain.gui.features.summary_aggregator import scan_player_names as _scan

        return _scan(sgf_files, self._logger)

    def categorize_games_by_stats(
        self, game_stats_list: list[dict[str, Any]], focus_player: str | None
    ) -> dict[str, Any]:
        """ゲーム統計をカテゴリ分類。"""
        from katrain.gui.features.summary_aggregator import categorize_games_by_stats as _cat

        return _cat(game_stats_list, focus_player)

    def collect_rank_info(self, stats_list: list[dict[str, Any]], focus_player: str) -> str | None:
        """段級位情報を収集。"""
        from katrain.gui.features.summary_aggregator import collect_rank_info as _collect

        return _collect(stats_list, focus_player)

    def build_summary_from_stats(
        self, stats_list: list[dict[str, Any]], focus_player: str | None = None
    ) -> str:
        """統計からサマリテキストを構築。"""
        from katrain.gui.features.summary_formatter import build_summary_from_stats as _build

        # Adapt get_config(key, default) to config_fn(key) signature
        return _build(stats_list, focus_player, lambda key: self._get_config(key, None))

    # ========== Public API（UI連携・Kivy必要） ==========

    def scan_and_show_player_selection(self, sgf_files: list[str]) -> None:
        """プレイヤースキャン＋選択ダイアログ表示。Requires Kivy."""
        from katrain.gui.features.summary_ui import scan_and_show_player_selection as _scan_show

        _scan_show(
            sgf_files,
            self._get_ctx(),
            self.scan_player_names,
            self.process_summary_with_selected_players,
            self.show_player_selection_dialog,
        )

    def process_summary_with_selected_players(
        self, sgf_files: list[str], selected_players: list[str]
    ) -> None:
        """選択されたプレイヤーでサマリ処理。Requires Kivy."""
        from katrain.gui.features.summary_ui import process_summary_with_selected_players as _process

        _process(
            sgf_files,
            selected_players,
            self.process_and_export_summary,
        )

    def show_player_selection_dialog(
        self, sorted_players: list[tuple[str, int]], sgf_files: list[str]
    ) -> None:
        """プレイヤー選択ダイアログ表示。Requires Kivy."""
        from katrain.gui.features.summary_ui import show_player_selection_dialog as _show

        _show(
            sorted_players,
            sgf_files,
            self._load_export_settings,
            self._save_export_settings,
            self.process_and_export_summary,
        )

    def process_and_export_summary(
        self,
        sgf_paths: list[str],
        progress_popup: Any,
        selected_players: list[str] | None = None,
    ) -> None:
        """サマリ処理＋エクスポート実行。Requires Kivy."""
        from katrain.gui.features.summary_ui import process_and_export_summary as _process_export

        _process_export(
            sgf_paths,
            progress_popup,
            selected_players or [],  # Convert None to empty list
            self._get_ctx(),
            self.extract_sgf_statistics,  # type: ignore[arg-type]  # Returns Optional but callee handles None
            self.categorize_games_by_stats,
            self.save_summaries_per_player,
            self.save_categorized_summaries_from_stats,
        )

    def save_summaries_per_player(
        self,
        game_stats_list: list[dict[str, Any]],
        selected_players: list[str],
        progress_popup: Any,
    ) -> None:
        """プレイヤー別サマリ保存。Requires Kivy."""
        from katrain.gui.features.summary_io import save_summaries_per_player as _save

        _save(
            game_stats_list,
            selected_players,
            progress_popup,
            self._get_ctx(),
            self.categorize_games_by_stats,
            self.build_summary_from_stats,
        )

    def save_categorized_summaries_from_stats(
        self,
        categorized_games: dict[str, Any],
        player_name: str | None,
        progress_popup: Any,
    ) -> None:
        """カテゴリ別サマリ保存。Requires Kivy."""
        from katrain.gui.features.summary_io import save_categorized_summaries_from_stats as _save

        _save(
            categorized_games,
            player_name,
            progress_popup,
            self._get_ctx(),
            self.build_summary_from_stats,
        )

    def save_summary_file(
        self, summary_text: str, player_name: str, progress_popup: Any
    ) -> None:
        """サマリファイル保存。Requires Kivy."""
        from katrain.gui.features.summary_io import save_summary_file as _save

        _save(summary_text, player_name, progress_popup, self._get_ctx())
