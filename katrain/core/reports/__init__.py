# katrain/core/reports - レポート生成パッケージ
#
# game.pyから抽出されたレポート生成機能を配置します。
# このパッケージはkatrain.guiをインポートしません（core層のみ）。
#
# PR #115: パッケージ骨格作成
# PR #116: summary_report.py追加

from katrain.core.reports.summary_report import build_summary_report
from katrain.core.reports.types import (
    CONFIG_READER_REQUIRED_ATTRS,
    GAME_METADATA_REQUIRED_ATTRS,
    ROOT_NODE_REQUIRED_ATTRS,
    ConfigReader,
    GameMetadataProvider,
    RootNodeProvider,
)

__all__ = [
    # Protocol types
    "GameMetadataProvider",
    "RootNodeProvider",
    "ConfigReader",
    # Required attrs for testing
    "GAME_METADATA_REQUIRED_ATTRS",
    "ROOT_NODE_REQUIRED_ATTRS",
    "CONFIG_READER_REQUIRED_ATTRS",
    # Report functions
    "build_summary_report",
]
