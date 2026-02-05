# katrain/gui/features - 機能モジュールパッケージ
#
# __main__.py から抽出した機能モジュールを配置します。
# 各機能は FeatureContext Protocol を通じて KaTrainGui と連携します。
#
# 利用例:
#   from katrain.gui.features.context import FeatureContext
#   from katrain.gui.features.karte_export import do_export_karte
#
# 注意: このパッケージ内のモジュールは KaTrainGui のインスタンスに
# 依存しますが、FeatureContext Protocol を介して疎結合を維持します。

from __future__ import annotations

from katrain.core.batch.helpers import needs_leela_karte_warning
from katrain.gui.features.context import FeatureContext

__all__ = ["FeatureContext", "needs_leela_karte_warning"]
