# katrain/common/typed_config/reader.py
#
# TypedConfigReader - 型付き設定リーダー。
# Phase 99で追加。

from typing import Any

from katrain.common.typed_config.models import (
    EngineConfig,
    LeelaConfig,
    TrainerConfig,
)


class TypedConfigReader:
    """型付き設定リーダー。

    毎回from_dict()を呼び出すため、常に最新の設定値を返す。
    セクションdictはコピーしてから解析（並行変更対策）。

    Note:
        - Phase 99ではキャッシュなし、invalidate APIなし
        - _config dictは初期化後に置換されない（in-place変更のみ）ため、
          参照が stale になるリスクなし
        - もし将来 reload/replace 機能が追加される場合は、
          TypedConfigReaderを再作成するか、各get_*()で毎回生成する

    Usage:
        reader = TypedConfigReader(config_dict)
        engine = reader.get_engine()  # EngineConfig
        trainer = reader.get_trainer()  # TrainerConfig
        leela = reader.get_leela()  # LeelaConfig
    """

    def __init__(self, config_dict: dict[str, Any]) -> None:
        """config辞書への参照を保持（コピーしない）。

        Args:
            config_dict: 設定辞書（通常はKaTrainBase._config）
        """
        self._config = config_dict

    def get_engine(self) -> EngineConfig:
        """エンジン設定を取得。

        Returns:
            EngineConfigインスタンス（frozen）
        """
        raw = self._config.get("engine")
        snapshot = dict(raw) if isinstance(raw, dict) else {}
        return EngineConfig.from_dict(snapshot)

    def get_trainer(self) -> TrainerConfig:
        """トレーナー設定を取得。

        Returns:
            TrainerConfigインスタンス（frozen）
        """
        raw = self._config.get("trainer")
        snapshot = dict(raw) if isinstance(raw, dict) else {}
        return TrainerConfig.from_dict(snapshot)

    def get_leela(self) -> LeelaConfig:
        """Leela設定を取得。

        Returns:
            LeelaConfigインスタンス（frozen）
        """
        raw = self._config.get("leela")
        snapshot = dict(raw) if isinstance(raw, dict) else {}
        return LeelaConfig.from_dict(snapshot)
