# katrain/core/reports - レポート生成パッケージ
#
# game.pyから抽出されたレポート生成機能を配置します。
# このパッケージはkatrain.guiをインポートしません（core層のみ）。
#
# PR #115: パッケージ骨格作成
# PR #116: summary_report.py追加
# PR #117: quiz_report.py追加
# PR #119: karte_report.py追加
# PR #120: important_moves_report.py追加

from katrain.core.reports.important_moves_report import build_important_moves_report
from katrain.core.reports.karte_report import (
    KarteGenerationError,
    build_karte_report,
)
from katrain.core.reports.quiz_report import build_quiz_questions, get_quiz_items
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
    "get_quiz_items",
    "build_quiz_questions",
    "build_karte_report",
    "KarteGenerationError",
    "build_important_moves_report",
]
