"""設定管理マネージャー（Phase 74）

ConfigManagerはKaTrainGuiの設定管理責務を担当する。
Kivy非依存で、ユニットテスト可能な設計。

使用例:
    from katrain.gui.managers.config_manager import ConfigManager

    manager = ConfigManager(
        config_dict=self._config,
        save_config=super().save_config,
        logger=self.log,
        log_level_info=OUTPUT_INFO,
    )

    # 読み取り
    value = manager.get("trainer/eval_thresholds")
    section = manager.get_section("export_settings")

    # 書き込み
    manager.set_section("general", {"lang": "ja"})
    manager.save_export_settings(sgf_directory="/path")
    manager.save_batch_options({"visits": 200})
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ConfigManager:
    """設定管理（読み取り/書き込み/セクション管理）

    更新セマンティクス:
    - set_section(): REPLACE - セクション全体を置き換え
    - save_export_settings(): PARTIAL - None引数は「変更しない」
    - save_batch_options(): PARTIAL - batch_optionsサブツリーのみMERGE

    コピーセマンティクス:
    - get(): 直接参照を返す（パフォーマンス優先、呼び出し元は変更禁止）
    - get_section(): SHALLOW COPYを返す（トップレベルキーのみ保護）
    """

    def __init__(
        self,
        config_dict: dict[str, Any],
        save_config: Callable[[str | None], None],
        logger: Callable[[str, int], None] | None = None,
        log_level_info: int = 0,
    ):
        """ConfigManagerを初期化する。

        Args:
            config_dict: メモリ上の設定辞書（参照）
            save_config: 保存コールバック（save_config(section_key)）
            logger: ロギングコールバック（logger(message, level)）
            log_level_info: OUTPUT_INFO相当のログレベル（注入）
        """
        self._config = config_dict
        self._save_config = save_config
        self._logger = logger or (lambda msg, level: None)
        self._log_level_info = log_level_info

    # ========== 読み取り ==========

    def get(self, setting: str, default: Any = None) -> Any:
        """階層的な設定値取得（例: "trainer/eval_thresholds"）

        Args:
            setting: "section/key" または "section" 形式
            default: キーが存在しない場合のデフォルト値

        Returns:
            設定値、または存在しない場合はdefault

        非dict値への対応ポリシー:
        - セクションが非dict（None, str, list等） → defaultを返す

        重要: 返り値の変更禁止ポリシー
        - get()はパフォーマンスのため直接参照を返す（コピーなし）
        - 呼び出し元は返り値を変更してはならない
        - dict全体を取得して変更する場合はget_section()を使用すること
        """
        if "/" in setting:
            section, key = setting.split("/", 1)
            section_val = self._config.get(section)
            if isinstance(section_val, dict):
                return section_val.get(key, default)
            return default
        return self._config.get(setting, default)

    def get_section(self, section: str) -> dict[str, Any]:
        """セクション全体を取得（SHALLOW COPYを返す）

        Args:
            section: セクション名

        Returns:
            セクションのshallow copy、または空辞書

        非dict値への対応ポリシー:
        - セクションが存在しない → {}
        - セクションがNone → {}
        - セクションが非dict（str, list等） → {}（安全に空辞書を返す）

        コピーセマンティクス:
        - SHALLOW COPY: トップレベルキーはコピーされるが、ネストしたdictは参照共有
        - 呼び出し元がネストした値を変更すると元データに影響する
        - 変更パス（save_export_settings, save_batch_options等）は内部でコピーして保護
        """
        value = self._config.get(section)
        if not isinstance(value, dict):
            return {}
        return dict(value)

    # ========== 書き込み ==========

    def set_section(self, section: str, value: dict[str, Any]) -> None:
        """セクション全体を設定（REPLACE）

        Args:
            section: セクション名
            value: セクション全体の値（辞書）

        注意: save_config()は呼び出し元で明示的に行う
        """
        self._config[section] = value

    # ========== エクスポート設定（PARTIAL UPDATE） ==========

    def load_export_settings(self) -> dict[str, Any]:
        """エクスポート設定をロード

        Returns:
            export_settingsセクションのshallow copy
        """
        return self.get_section("export_settings")

    def save_export_settings(
        self,
        sgf_directory: str | None = None,
        selected_players: list[str] | None = None,
    ) -> None:
        """エクスポート設定を保存（PARTIAL UPDATE）

        Args:
            sgf_directory: None=変更しない、str=更新
            selected_players: None=変更しない、list=更新
        """
        current = self.load_export_settings()
        if sgf_directory is not None:
            current["last_sgf_directory"] = sgf_directory
        if selected_players is not None:
            current["last_selected_players"] = selected_players
        self.set_section("export_settings", current)
        self._save_config("export_settings")

    # ========== バッチオプション（PARTIAL UPDATE） ==========

    def save_batch_options(self, options: dict[str, Any]) -> None:
        """バッチオプションを保存（PARTIAL UPDATE - batch_optionsサブツリーのみ）

        mykatrain_settings.batch_optionsをMERGE更新。
        他のmykatrain_settingsキー（karte_output_directory等）は保持。

        Args:
            options: マージするオプション辞書

        Raises:
            TypeError: optionsがdictでない場合

        破損データへの対応ポリシー:
        - mykatrain_settings["batch_options"]が非dict → {}として扱う（ログ出力）
        - options引数が非dict → TypeError（明示的エラー）
        """
        if not isinstance(options, dict):
            raise TypeError(f"options must be dict, got {type(options).__name__}")

        mykatrain_settings = self.get_section("mykatrain_settings")
        existing_batch = mykatrain_settings.get("batch_options")

        # 破損データ対応: 非dictなら空dictとして扱う
        if not isinstance(existing_batch, dict):
            if existing_batch is not None:
                self._logger(
                    f"batch_options was {type(existing_batch).__name__}, resetting to dict",
                    self._log_level_info,
                )
            existing_batch = {}
        else:
            # shallow copy保護: 元のネストdictを変更しないようコピー
            existing_batch = dict(existing_batch)

        existing_batch.update(options)  # MERGE (on copy)
        mykatrain_settings["batch_options"] = existing_batch
        self.set_section("mykatrain_settings", mykatrain_settings)
        self._save_config("mykatrain_settings")
