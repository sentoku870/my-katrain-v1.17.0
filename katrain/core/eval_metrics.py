"""
eval_metrics.py - 後方互換ファサード

全てのシンボルは katrain.core.analysis パッケージから再エクスポート。
既存のインポートパスを維持するため、このファイルは削除しない。

構成:
- katrain.core.analysis.core: 全機能（Phase A）

将来の構成（Phase B以降）:
- katrain.core.analysis.models: Enum, Dataclass, 設定定数
- katrain.core.analysis.logic: 純粋計算関数
- katrain.core.analysis.presentation: 表示/フォーマット関数

Note: シンボルの __module__ パスが変更されています。
      pickle/キャッシュでクラス参照を保存している場合、デシリアライズ失敗の可能性あり。
      （調査結果: リポジトリ内に pickle/cache 使用箇所なし）
"""

# Re-export everything from the analysis package
from katrain.core.analysis import *  # noqa: F401, F403

# Import __all__ from analysis package
from katrain.core.analysis import __all__  # noqa: F401
