"""SGF file management.

PR #122: Phase B3 - SGFManager抽出

__main__.pyから抽出されたSGFファイル管理機能。
依存注入パターンで明示的な依存のみを受け取る。

このモジュールの設計原則:
- KaTrainGuiへの直接参照を持たない
- 必要な依存はコンストラクタで明示的に受け取る
- ファイル操作とUI操作を分離
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable

import urllib3
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp, sp
from kivy.uix.dropdown import DropDown

from katrain.core.constants import OUTPUT_DEBUG, OUTPUT_ERROR, OUTPUT_INFO, STATUS_ERROR, STATUS_INFO
from katrain.core.game import KaTrainSGF
from katrain.core.lang import i18n
from katrain.core.sgf_parser import ParseError
from katrain.gui.kivyutils import MenuItem
from katrain.gui.popups import I18NPopup, LoadSGFPopup, SaveSGFPopup
from katrain.gui.theme import Theme


class SGFManager:
    """SGFファイルの読み込み・保存を管理するクラス。

    KaTrainGuiから抽出されたSGF関連機能を担当。
    依存注入パターンにより、必要な機能のみをコールバックで受け取る。
    """

    def __init__(
        self,
        config_getter: Callable[[str, Any], Any],
        config_setter: Callable[[str, Any], None],
        save_config: Callable[[str], None],
        logger: Callable[[str, int], None],
        status_setter: Callable[[str, int], None],
        new_game_callback: Callable[[Any, bool, str | None], None],
        redo_callback: Callable[[int], None],
        get_game: Callable[[], Any],
        get_engine: Callable[[], Any],
        get_board_controls: Callable[[], Any],
        action_dispatcher: Callable[[str], None],
    ):
        """SGFManagerを初期化。

        Args:
            config_getter: 設定値を取得するコールバック config(key, default)
            config_setter: 設定を更新するコールバック set_config_section(section, values)
            save_config: 設定を保存するコールバック save_config(section)
            logger: ログ出力コールバック log(message, level)
            status_setter: ステータス表示コールバック set_status(message, level)
            new_game_callback: 新規ゲーム開始コールバック (move_tree, analyze_fast, sgf_filename)
            redo_callback: リドゥコールバック (moves)
            get_game: 現在のゲームを取得するコールバック
            get_engine: 現在のエンジンを取得するコールバック
            get_board_controls: ボードコントロールを取得するコールバック
            action_dispatcher: アクションをディスパッチするコールバック
        """
        self._config = config_getter
        self._set_config_section = config_setter
        self._save_config = save_config
        self._log = logger
        self._set_status = status_setter
        self._new_game = new_game_callback
        self._redo = redo_callback
        self._get_game = get_game
        self._get_engine = get_engine
        self._get_board_controls = get_board_controls
        self._dispatch = action_dispatcher

        # Popup state (managed externally to avoid memory leaks)
        self.fileselect_popup = None

    def load_sgf_file(self, file: str, fast: bool = False, rewind: bool = True) -> None:
        """SGFファイルを読み込む。

        Args:
            file: SGFファイルのパス
            fast: 高速解析モードを使用するか
            rewind: 最初の手に巻き戻すか
        """
        try:
            file = os.path.abspath(file)
            move_tree = KaTrainSGF.parse_file(file)
        except (ParseError, FileNotFoundError) as e:
            self._log(i18n._("Failed to load SGF").format(error=e), OUTPUT_ERROR)
            return
        self._new_game(move_tree, fast, file)
        if not rewind:
            game = self._get_game()
            if game:
                game.redo(999)

    def load_sgf_from_clipboard(self) -> None:
        """クリップボードからSGFを読み込む。"""
        clipboard = Clipboard.paste()
        if not clipboard:
            self._set_status("Ctrl-V pressed but clipboard is empty.", int(int(STATUS_INFO)))
            return

        url_match = re.match(r"(?P<url>https?://[^\s]+)", clipboard)
        if url_match:
            self._log("Recognized url: " + url_match.group(), OUTPUT_INFO)
            http = urllib3.PoolManager()
            response = http.request("GET", url_match.group())
            clipboard = response.data.decode("utf-8")

        try:
            move_tree = KaTrainSGF.parse_sgf(clipboard)
        except (ParseError, ValueError) as exc:
            # SGF parse failure: syntax error or invalid coordinates
            # Safe preview: avoid TypeError if clipboard is None or non-string
            preview = ""
            try:
                preview = (clipboard[:50] + "...") if clipboard and len(clipboard) > 50 else (clipboard or "")
            except (TypeError, AttributeError):
                preview = "<unreadable>"
            logging.info(f"Clipboard SGF parse failed: {exc}, preview: {preview}")
            # UI message: simple, no raw clipboard content (privacy)
            self._set_status(f"Failed to import from clipboard: {exc}", int(STATUS_INFO))
            return
        except Exception as exc:
            # Boundary fallback: unexpected error parsing clipboard SGF
            logging.warning(f"Unexpected clipboard SGF error: {exc}", exc_info=True)
            self._set_status(f"Failed to import from clipboard: {exc}", int(STATUS_INFO))
            return

        engine = self._get_engine()
        if engine:
            move_tree.nodes_in_tree[-1].analyze(engine, analyze_fast=False)  # type: ignore[attr-defined]

        self._new_game(move_tree, True, None)
        self._redo(9999)
        self._log("Imported game from clipboard.", OUTPUT_INFO)

    def save_game(self, filename: str | None = None) -> None:
        """ゲームを保存する。

        Args:
            filename: 保存先ファイル名（Noneの場合は既存ファイル名を使用）
        """
        game = self._get_game()
        if not game:
            return

        filename = filename or game.sgf_filename
        if not filename:
            self._dispatch("save-game-as-popup")
            return
        try:
            msg = game.write_sgf(filename)
            self._log(msg, OUTPUT_INFO)
            self._set_status(msg, int(STATUS_INFO))
        except OSError as e:
            # File write failure: permission denied, disk full, invalid path
            logging.warning(f"SGF save failed to {filename}: {e}", exc_info=True)
            self._log(f"Failed to save SGF to {filename}: {e}", OUTPUT_ERROR)
            self._set_status(f"Save failed: {e}", int(STATUS_ERROR))
        except Exception as e:
            # Boundary fallback: unexpected error during SGF save
            logging.error(f"Unexpected error saving SGF to {filename}: {e}", exc_info=True)
            self._log(f"Failed to save SGF to {filename}: {e}", OUTPUT_ERROR)
            self._set_status(f"Save failed: {e}", int(STATUS_ERROR))

    def open_recent_sgf(self) -> None:
        """最近のSGFファイルを開く（ドロップダウン表示）。"""
        try:
            sgf_dir = os.path.abspath(os.path.expanduser(self._config("general/sgf_load", ".")))
        except (OSError, KeyError, TypeError) as e:
            # Path expansion or config read failure
            logging.debug(f"Failed to determine sgf load directory: {e}")
            self._dispatch("analyze-sgf-popup")
            return
        except Exception as e:
            # Boundary fallback: unexpected error determining SGF directory
            logging.warning(f"Unexpected error getting SGF directory: {e}", exc_info=True)
            self._dispatch("analyze-sgf-popup")
            return

        if not sgf_dir or not os.path.isdir(sgf_dir):
            self._dispatch("analyze-sgf-popup")
            return

        try:
            sgf_files = [
                os.path.join(sgf_dir, f)
                for f in os.listdir(sgf_dir)
                if f.lower().endswith(".sgf") and os.path.isfile(os.path.join(sgf_dir, f))
            ]
            sgf_files.sort(key=os.path.getmtime, reverse=True)
        except OSError as e:
            # Directory listing or file stat failure
            logging.debug(f"Failed to list SGF files in {sgf_dir}: {e}")
            self._dispatch("analyze-sgf-popup")
            return
        except Exception as e:
            # Boundary fallback: unexpected error listing SGF files
            logging.warning(f"Unexpected error listing SGF files in {sgf_dir}: {e}", exc_info=True)
            self._dispatch("analyze-sgf-popup")
            return

        if not sgf_files:
            self._dispatch("analyze-sgf-popup")
            return

        sgf_files = sgf_files[:20]
        fast = bool(self._config("general/load_fast_analysis", False))
        rewind = bool(self._config("general/load_sgf_rewind", True))
        if len(sgf_files) == 1:
            self.load_sgf_file(sgf_files[0], fast=fast, rewind=rewind)
            return

        # Build and open dropdown on the main thread
        file_entries = [os.path.basename(path) for path in sgf_files]
        Clock.schedule_once(
            lambda *_dt: self._show_recent_sgf_dropdown(sgf_files, file_entries, fast, rewind)
        )

    def _show_recent_sgf_dropdown(
        self, sgf_files: list[str], labels: list[str], fast: bool, rewind: bool
    ) -> None:
        """最近のSGFファイルのドロップダウンを表示する。

        Args:
            sgf_files: SGFファイルパスのリスト
            labels: 表示ラベルのリスト
            fast: 高速解析モードを使用するか
            rewind: 最初の手に巻き戻すか
        """
        dropdown = DropDown(auto_width=False)
        max_width = 0
        menu_items = []
        base_width = dp(240)
        item_height = dp(34)
        font_size = sp(13)

        def truncate(text: str, max_len: int = 35) -> str:
            return text if len(text) <= max_len else text[: max_len - 3] + "..."

        def load_and_analyze(path: str, *_load_args: Any) -> None:
            dropdown.dismiss()
            self.load_sgf_file(path, fast=fast, rewind=rewind)

        for idx, (path, filename) in enumerate(zip(sgf_files, labels)):
            label = f"[NEW] {filename}" if idx < 3 else filename
            label = truncate(label)
            menu_item = MenuItem(text=label, content_width=max(base_width, len(label) * dp(7)))
            menu_item.height = item_height
            menu_item.font_size = font_size
            menu_item.background_color = Theme.LIGHTER_BACKGROUND_COLOR
            label_widget = menu_item.ids.get("label")
            if label_widget:
                label_widget.color = Theme.TEXT_COLOR
                label_widget.shorten = True
                label_widget.shorten_from = "right"
            menu_item.bind(on_action=lambda _item, p=path: load_and_analyze(p))
            dropdown.add_widget(menu_item)
            menu_items.append(menu_item)
            max_width = max(max_width, menu_item.content_width)

        if max_width:
            dropdown.width = max(max_width, base_width)
            for item in menu_items:
                label_widget = item.ids.get("label")
                if label_widget:
                    label_widget.text_size = (dropdown.width - dp(70), None)

        board_controls = self._get_board_controls()
        sgf_button = getattr(board_controls, "sgf_button", None) if board_controls else None
        try:
            if sgf_button:
                dropdown.open(sgf_button)
            else:
                raise AttributeError("SGF button not available")
        except (AttributeError, RuntimeError) as e:
            # Dropdown open failure: widget not available or in invalid state
            logging.debug(f"Failed to open recent SGF dropdown: {e}")
            self._dispatch("analyze-sgf-popup")
        except Exception as e:
            # Boundary fallback: unexpected Kivy widget error
            logging.warning(f"Unexpected error opening SGF dropdown: {e}", exc_info=True)
            self._dispatch("analyze-sgf-popup")

    def do_analyze_sgf_popup(self, katrain: Any) -> None:
        """SGF解析ポップアップを開く。

        Args:
            katrain: KaTrainGuiインスタンス（ポップアップのバインディング用）

        Note:
            この関数はKaTrainGuiインスタンスが必要なため、委譲メソッドとして残します。
        """
        if not self.fileselect_popup:
            popup_contents = LoadSGFPopup(katrain)
            # Set initial path with fallback if configured path doesn't exist
            sgf_load_path = os.path.abspath(os.path.expanduser(self._config("general/sgf_load", ".")))
            if os.path.isdir(sgf_load_path):
                popup_contents.filesel.path = sgf_load_path
            self.fileselect_popup = I18NPopup(
                title_key="load sgf title", size=[dp(1200), dp(800)], content=popup_contents
            ).__self__

            def readfile(*_args: Any) -> None:
                filename = popup_contents.filesel.filename
                if self.fileselect_popup:
                    self.fileselect_popup.dismiss()
                path, file = os.path.split(filename)
                if path != self._config("general/sgf_load", None):
                    self._log(f"Updating sgf load path default to {path}", OUTPUT_DEBUG)
                    general = dict(self._config("general", {}) or {})
                    general["sgf_load"] = path
                    self._set_config_section("general", general)
                    self._save_config("general")
                popup_contents.update_config(False)
                self._save_config("general")
                self.load_sgf_file(filename, popup_contents.fast.active, popup_contents.rewind.active)

            popup_contents.filesel.on_success = readfile
            popup_contents.filesel.on_submit = readfile
        if self.fileselect_popup:
            self.fileselect_popup.open()
            self.fileselect_popup.content.filesel.ids.list_view._trigger_update()

    def do_save_game_as_popup(self, katrain: Any) -> None:
        """名前を付けて保存ポップアップを開く。

        Args:
            katrain: KaTrainGuiインスタンス（設定保存用）

        Note:
            この関数はKaTrainGuiインスタンスが必要なため、委譲メソッドとして残します。
        """
        game = self._get_game()
        if not game:
            return

        popup_contents = SaveSGFPopup(suggested_filename=game.generate_filename())
        save_game_popup = I18NPopup(
            title_key="save sgf title", size=[dp(1200), dp(800)], content=popup_contents
        ).__self__

        def readfile(*_args: Any) -> None:
            filename = popup_contents.filesel.filename
            if not filename.lower().endswith(".sgf"):
                filename += ".sgf"
            save_game_popup.dismiss()
            path, file = os.path.split(filename.strip())
            if not path:
                path = popup_contents.filesel.path
            if path != self._config("general/sgf_save", None):
                self._log(f"Updating sgf save path default to {path}", OUTPUT_DEBUG)
                general = dict(self._config("general", {}) or {})
                general["sgf_save"] = path
                self._set_config_section("general", general)
                self._save_config("general")
            self.save_game(os.path.join(path, file))

        popup_contents.filesel.on_success = readfile
        popup_contents.filesel.on_submit = readfile
        save_game_popup.open()
