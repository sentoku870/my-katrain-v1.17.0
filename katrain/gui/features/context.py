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

from typing import TYPE_CHECKING, Any, Optional, Protocol

if TYPE_CHECKING:
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

    Methods:
        config: 設定値を取得
        save_config: 設定をファイルに保存
        log: ログメッセージを出力
    """

    game: Optional["Game"]
    controls: "ControlsPanel"

    def config(self, setting: str, default: Any = None) -> Any:
        """設定値を取得する。

        Args:
            setting: 設定キー（例: "trainer/export_format"）
            default: 設定が存在しない場合のデフォルト値

        Returns:
            設定値。存在しない場合は default。
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
