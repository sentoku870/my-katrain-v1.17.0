# katrain/gui/features/context.py
#
# FeatureContext Protocol - 機能モジュールが必要とする最小限のインターフェース
#
# このProtocolは KaTrainGui のサブセットを定義し、機能モジュールが
# KaTrainGui に直接依存することなく動作できるようにします。
#
# 設計意図:
#   - 機能モジュールのテスト容易性向上（モック可能）
#   - 循環インポートの防止
#   - 依存関係の明示化
#
# Phase 90で拡張: エラー復旧に必要なメソッドを追加。
# Phase 99で拡張: 型付き設定アクセサを追加。
# Python 3.9互換: Optional/Dict/List構文を使用。

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol

if TYPE_CHECKING:
    from katrain.common.typed_config import EngineConfig, LeelaConfig, TrainerConfig
    from katrain.core.game import Game
    from katrain.gui.controlspanel import ControlsPanel


class FeatureContext(Protocol):
    """機能モジュールが必要とする最小限のインターフェース。

    KaTrainGui はこの Protocol を暗黙的に実装します（structural subtyping）。

    Attributes:
        game: 現在の対局。対局がない場合は None。
        controls: コントロールパネル。Kivy の id バインディングにより
                  アプリ起動時に自動的に設定されるため、機能モジュールが
                  呼ばれる時点では常に設定済み。
        engine: KataGoEngine インスタンス。None の場合あり。
        version: アプリケーションバージョン文字列。
        config_file: 設定ファイルのパス。

    Methods:
        config: 設定値を取得
        set_config_section: 設定セクションを書き込む
        save_config: 設定をファイルに保存
        log: ログメッセージを出力
        get_recent_logs: 最近のログを取得
        get_config_snapshot: 設定のスナップショットを取得
        restart_engine: エンジンを再起動
        get_engine_config: 型付きエンジン設定を取得（Phase 99）
        get_trainer_config: 型付きトレーナー設定を取得（Phase 99）
        get_leela_config: 型付きLeela設定を取得（Phase 99）

    Implementation Notes:
        KaTrainGui と BaseKaTrain がこの Protocol を満たす。
        各メソッドは既存実装を参照（Grep で "def <method>" で検索可能）。
    """

    game: Optional["Game"]
    controls: "ControlsPanel"
    engine: Any  # KataGoEngine or None - avoid circular import
    version: str
    config_file: str

    def config(self, setting: str, default: Any = None) -> Any:
        """設定値を取得する。

        Args:
            setting: 設定キー（例: "trainer/export_format"）
            default: 設定が存在しない場合のデフォルト値

        Returns:
            設定値。存在しない場合は default。
        """
        ...

    def set_config_section(self, section: str, value: Dict[str, Any]) -> None:
        """設定セクションを書き込む。

        Args:
            section: セクション名（例: "export_settings", "mykatrain_settings", "general"）
            value: セクション全体の値（辞書）

        Note:
            保存は別途 save_config(section) を呼ぶ必要がある。
        """
        ...

    def save_config(self, key: Optional[str] = None) -> None:
        """設定をファイルに保存する。

        Args:
            key: 保存する設定キー。None の場合は全設定を保存。
        """
        ...

    def log(self, message: str, level: int = 0) -> None:
        """ログメッセージを出力する。

        Args:
            message: ログメッセージ
            level: ログレベル（OUTPUT_INFO=0, OUTPUT_DEBUG=1, OUTPUT_ERROR=2）
        """
        ...

    def get_recent_logs(self) -> List[str]:
        """最近のログエントリを取得する。

        Returns:
            最近のログエントリのリスト。
        """
        ...

    def get_config_snapshot(self) -> Dict[str, Any]:
        """設定のスナップショットを取得する（Phase 90追加）。

        This is the public API for accessing config data.
        Avoids direct access to _config private attribute.

        Returns:
            Shallow copy of config dictionary.
        """
        ...

    def restart_engine(self) -> bool:
        """エンジンを再起動する。

        Returns:
            True if engine restarted successfully.
        """
        ...

    def get_engine_config(self) -> "EngineConfig":
        """型付きエンジン設定を取得する（Phase 99追加）。

        Returns:
            EngineConfigインスタンス（frozen）
        """
        ...

    def get_trainer_config(self) -> "TrainerConfig":
        """型付きトレーナー設定を取得する（Phase 99追加）。

        Returns:
            TrainerConfigインスタンス（frozen）
        """
        ...

    def get_leela_config(self) -> "LeelaConfig":
        """型付きLeela設定を取得する（Phase 99追加）。

        Returns:
            LeelaConfigインスタンス（frozen）
        """
        ...
