# katrain/common - 安定した共有定数パッケージ
#
# このパッケージには core/ と gui/ の両方から参照される
# 安定した定数を配置します。
#
# 注意: 実行時に変更される値（例: Theme.DEFAULT_FONT）は
# ここに配置しないでください。

from katrain.common.theme_constants import INFO_PV_COLOR

__all__ = ["INFO_PV_COLOR"]
