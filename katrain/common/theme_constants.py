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

# DEFAULT_FONT: 既定本文フォント名
# 日本語対応フォント。core/lang.py と gui/theme.py の両方で使用。
# PR #113: 循環依存解消のため gui/theme.py から移動
DEFAULT_FONT = "NotoSansJP-Regular.otf"

# DEFAULT_FONT_BOLD: 見出し・主要ボタン用の太字フォント名
# Phase 287-G: 現在は Regular を流用（外部資産ダウンロード禁止のため）。
# NotoSansJP-Bold.otf を後追いでバンドルしたらここを差し替えるだけで全 UI
# に反映される。Kivy の ``bold: True`` は同じファイルでも太字を描画できる
# ため、フォールバックしても疑似 Bold が表示される。
DEFAULT_FONT_BOLD = "NotoSansJP-Regular.otf"

# DEFAULT_ICON_FONT: Material Design Icons の Kivy LabelBase 論理名.
# KivyMD 1.2.0 の ``kivymd.font_definitions`` が
# ``LabelBase.register(name="Icons", fn_regular=...materialdesignicons-webfont.ttf)``
# を行うため、ファイル名ではなく登録名で参照する必要がある。ファイル名
# (``materialdesignicons-webfont.ttf``) を渡すと Kivy の resource 解決に失敗して
# ``OSError: Label: File ... not found`` になる。起動時に
# ``kivymd.font_definitions`` を import すれば登録が確定する。
DEFAULT_ICON_FONT = "Icons"
