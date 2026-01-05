"""
katrain.core.analysis - 解析基盤パッケージ

このパッケージは eval_metrics.py の機能を整理したものです。
Phase A では単一の core.py モジュールに全機能を配置し、
後方互換性のため eval_metrics.py から全シンボルを再エクスポートします。

Phase B 以降で段階的に以下のモジュールに分離予定:
- models.py: Enum, Dataclass, 設定定数
- logic.py: 純粋計算関数
- presentation.py: 表示/フォーマット関数

Note: シンボルの __module__ パスが変更されます。
      pickle/キャッシュでクラス参照を保存している場合、デシリアライズ失敗の可能性あり。
      （調査結果: リポジトリ内に pickle/cache 使用箇所なし）
"""

# Re-export everything from core module
from katrain.core.analysis.core import *  # noqa: F401, F403

# Import __all__ from core module
from katrain.core.analysis.core import __all__  # noqa: F401
