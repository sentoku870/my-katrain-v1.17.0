# katrain/core/reports - レポート生成パッケージ
#
# game.pyから抽出されたレポート生成機能を配置します。
# このパッケージはkatrain.guiをインポートしません（core層のみ）。
#
# PR #115: パッケージ骨格作成

from katrain.core.reports.types import (
    CONFIG_READER_REQUIRED_ATTRS,
    GAME_METADATA_REQUIRED_ATTRS,
    ROOT_NODE_REQUIRED_ATTRS,
    ConfigReader,
    GameMetadataProvider,
    RootNodeProvider,
)

__all__ = [
    "GameMetadataProvider",
    "RootNodeProvider",
    "ConfigReader",
    "GAME_METADATA_REQUIRED_ATTRS",
    "ROOT_NODE_REQUIRED_ATTRS",
    "CONFIG_READER_REQUIRED_ATTRS",
]
