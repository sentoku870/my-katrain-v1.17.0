"""Type definitions for report generation.

PR #115: Phase B2 - reports/パッケージ骨格

v5設計方針:
- Protocol は最小限から始める
- 各PRで必要なメソッドのみ追加
- runtime_checkableは使わない（属性テストで検証）
- ConfigReaderは既存のFeatureContext.configと同じシグネチャ
- 型は実際のGame/SGFNode実装に合わせる
"""

from typing import Any, Optional, Protocol, Tuple


class RootNodeProvider(Protocol):
    """ルートノードのプロパティアクセス用Protocol

    GameNode.get_property() に対応
    """

    def get_property(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """SGFプロパティを取得"""
        ...


class GameMetadataProvider(Protocol):
    """最小限のゲームメタデータ（PR #116 summary_report用）

    v5: 実際のGame/SGFNodeの型に合わせた定義
    - board_size: Tuple[int, int] (非正方形盤面対応)
    - root: GameNodeへのアクセス（get_property用）
    """

    @property
    def board_size(self) -> Tuple[int, int]:
        """盤面サイズ（x, y）。非正方形盤面対応のためタプル。"""
        ...

    @property
    def komi(self) -> float:
        ...

    @property
    def rules(self) -> str:
        ...

    @property
    def sgf_filename(self) -> Optional[str]:
        ...

    @property
    def root(self) -> RootNodeProvider:
        """ルートノードへのアクセス（SGFプロパティ取得用）"""
        ...


class ConfigReader(Protocol):
    """設定値を読み取るためのProtocol

    v5確認済み: 既存のFeatureContext.configおよびBaseKatrain.configと同じシグネチャ
    - FeatureContext.config(setting: str, default: Any = None) -> Any
    - BaseKatrain.config(setting, default=None)

    用途: karte_report等でconfig値を取得する際の型安全なインターフェース

    実装例:
    - KaTrainGui.config (実際の使用)
    - FeatureContext.config (既存Protocol)
    - テスト用のdictラッパー
    """

    def __call__(self, key: str, default: Any = None) -> Any:
        """設定値を取得

        Args:
            key: 設定キー（例: "karte/show_variation_pv"）
            default: キーが存在しない場合のデフォルト値

        Returns:
            設定値、またはdefault
        """
        ...


# PR #119 で追加予定
# class GameAnalysisProvider(GameMetadataProvider, Protocol):
#     """解析データを含むプロバイダ（karte_report用）"""
#     def build_eval_snapshot(self) -> "EvalSnapshot": ...
#     @property
#     def current_node(self) -> "GameNode": ...
#     @property
#     def root(self) -> "GameNode": ...


# Protocol が要求する属性リスト（テスト用）
GAME_METADATA_REQUIRED_ATTRS = [
    "board_size",
    "komi",
    "rules",
    "sgf_filename",
    "root",
]

ROOT_NODE_REQUIRED_ATTRS = [
    "get_property",
]

CONFIG_READER_REQUIRED_ATTRS = [
    "__call__",
]
