# katrain/common/theme_constants.py
#
# 安定した共有定数を配置するモジュール。
# core/ と gui/ の両方から参照される定数のみを含みます。
#
# 注意: 実行時に変更される値はここに配置しないでください。

# INFO_PV_COLOR: PVリンクの色（黄色）
# 元の値: to_hexcol(YELLOW) where YELLOW = [0.8, 0.8, 0.1, 1]
# 計算結果: "#cccc19"
INFO_PV_COLOR = "#cccc19"

# DEFAULT_FONT: デフォルトフォント名
# 日本語対応フォント。core/lang.py と gui/theme.py の両方で使用。
# PR #113: 循環依存解消のため gui/theme.py から移動
DEFAULT_FONT = "NotoSansJP-Regular.otf"
