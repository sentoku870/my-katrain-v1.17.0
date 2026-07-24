# Phase PR2-P1: BadukPanWidget の分割判断

## 結論
**現状維持**。追加分割は実施しない。

## 理由

1. **既に thin wrapper 化が完了** (Phase 158+)
   - `badukpan.py` の 57 メソッドのうち 50+ は 4 行の delegate
   - 描画系は `badukpan_drawing.py` の module-level 関数
   - PV 系は `badukpan_pv.py` の module-level 関数
   - ヒント系は `badukpan_hints.py` の module-level 関数

2. **残った「大きい」メソッドは widget 属性との結合度が極めて高い**
   - `on_touch_up` (65 行) — katrain インスタンス・kifunarabe_mode・play logic に依存
   - `on_mouse_pos` (39 行) — Window.bind 経由、状態管理が複雑
   - `rotate_gridpos` (41 行) — gridpos 配列の直接操作
   - これらを抽出しても実質的に同じ行数が移動するだけで、メリット < リスク

3. **ユーザー承認時の選択肢**: 「推奨: 描画系を badukpan_drawing.py に集約 + 残りは thin wrapper 維持」
   - 描画系の集約は **既完了** (Phase 158+ で)
   - 残り (thin wrapper) は **現状維持が正解**

## 影響範囲
なし (BadukPanWidget の外部 API は完全に保持)

## 再評価トリガー
BadukPanWidget に新規で 10+ メソッドが追加される場合、再分割を検討。
現状は add 0 / yyyy-mm-dd を確認。
