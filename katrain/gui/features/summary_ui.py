# katrain/gui/features/summary_ui.py
#
# サマリUI配線モジュール
#
# Phase 230-A.2: ``do_export_summary`` / ``do_export_summary_ui`` /
# ``process_summary_with_selected_players`` /
# ``scan_and_show_player_selection`` / ``show_player_selection_dialog`` /
# ``process_and_export_summary`` の 6 関数を完全削除。
# メニュー export_summary からのみ呼ばれており、CLI / batch 等は
# ``summary_manager`` の pure 関数 API を直接利用する。
#
# このファイルは現在プレースホルダ（すべての実装関数が削除された）。
# モジュールが ``summary_manager.py`` から import される可能性があるため
# ファイル自体は温存（空のモジュール）。

from __future__ import annotations
