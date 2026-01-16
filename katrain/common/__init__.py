# katrain/common - 安定した共有定数パッケージ
#
# このパッケージには core/ と gui/ の両方から参照される
# 安定した定数を配置します。
#
# 注意: 実行時に変更される値はここに配置しないでください。

from katrain.common.theme_constants import DEFAULT_FONT, INFO_PV_COLOR
from katrain.common.platform import get_platform

__all__ = ["DEFAULT_FONT", "INFO_PV_COLOR", "get_platform"]
