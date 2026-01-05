"""
katrain.core.analysis - 解析基盤パッケージ

このパッケージは eval_metrics.py の機能を整理したものです。
Phase B で models.py, logic.py, presentation.py に分離されました。

構成:
- models.py: Enum, Dataclass, 設定定数
- logic.py: 純粋計算関数
- presentation.py: 表示/フォーマット関数

後方互換性:
- 全てのシンボルはこの __init__.py から再エクスポートされます
- `from katrain.core.analysis import *` で全機能にアクセス可能

Note: シンボルの __module__ パスが変更されます。
      pickle/キャッシュでクラス参照を保存している場合、デシリアライズ失敗の可能性あり。
      （調査結果: リポジトリ内に pickle/cache 使用箇所なし）
"""

# Re-export everything from sub-modules
from katrain.core.analysis.models import *  # noqa: F401, F403
from katrain.core.analysis.logic import *  # noqa: F401, F403
from katrain.core.analysis.presentation import *  # noqa: F401, F403

# Import __all__ from sub-modules and combine
from katrain.core.analysis.models import __all__ as _models_all
from katrain.core.analysis.logic import __all__ as _logic_all
from katrain.core.analysis.presentation import __all__ as _presentation_all

__all__ = list(_models_all) + list(_logic_all) + list(_presentation_all)
