# Phase 117: Top Moves カラー回帰修正（根本解決）

**日時**: 2026-02-03
**ステータス**: 計画フェーズ
**優先度**: 🔴 高（ユーザー報告による視覚的回帰）

---

## 0. 背景と問題

### 状況
- Phase 116 で 82 個の型エラーを修正し、mypy strict モード 100% 準拠を達成
- しかし、**Top Moves の色表示が紫色のままという回帰が発生**
- Phase 115 では正常に多色グラデーション表示されていた

### 根本原因（Phase 116 調査で判明）

**「ダブル反転」理論**:

1. **evaluation_class() のロジック**: 反転している
   ```python
   # 現在の実装
   while i < len(eval_thresholds) - 1:
       if points_lost < threshold:
           break  # 小さい損失 → index 0（紫、悪い）
       i += 1
   ```
   → 小さい損失（良い手）が index 0（紫） を返す（間違っている）

2. **KataGo の pointsLost 計算**: も反転している
   - 良い手（ゲイン）= 負の値（-2.0 など）
   - 悪い手（ロス）= 正の値（+5.0 など）

3. **Phase 115 での「偶然の成功」**:
   - 2 つの反転が相殺されて、結果的に正しく見えていた
   - evaluation_class() が反転 × KataGo が反転 = 相殺

4. **Phase 116 での破損**:
   - Phase 116 で evaluation_class() を修正したが、不完全
   - KataGo の反転は未修正のまま
   - 結果: 色が紫のままに

### 実装の証拠

**デバッグ結果**:
```
Loss     | Index  | Description
---------+--------+------------------------------
-5.0     | 0      | PURPLE   (Excellent move)
-2.0     | 0      | PURPLE   (Good move)
 0.5     | 0      | PURPLE   (Small loss)
 1.0     | 1      | RED      (At threshold)
 5.0     | 3      | YELLOW   (Large loss)
10.0     | 4      | LIGHT GREEN (Bad move)
```

→ 負の値（良い手）がすべて index 0（紫）
→ 正の値（悪い手）が高い index（緑）
→ **論理が完全に逆**

---

## 1. Phase 117 の目標

### 主要目標
✅ Top Moves カラーグラデーションを完全に修復
✅ evaluation_class() のロジックを正しく実装
✅ KataGo pointsLost の符号を検証・調整
✅ Phase 116 の型エラー修正は保持

### 成功基準
- ✅ Top Moves が多色グラデーションで表示（赤 → 黄 → 緑）
- ✅ 悪い手が赤/紫色（高い損失値）
- ✅ 良い手が黄/緑色（低い損失値）
- ✅ 全テスト 3776 PASS（回帰なし）
- ✅ mypy strict モード継続 100% 準拠

---

## 2. 詳細分析：evaluation_class() ロジック

### 現在の実装（utils.py:25-46）

```python
def evaluation_class(points_lost: float, eval_thresholds: Sequence[float | None]) -> int:
    i = 0
    while i < len(eval_thresholds) - 1:
        threshold = eval_thresholds[i]
        if threshold is None:
            i += 1
            continue
        if points_lost < threshold:
            break  # ← 問題: 小さい損失で break → index 0 返す
        i += 1
    return i
```

### 問題のシナリオ

**入力**:
- points_lost = -2.0 （KataGo: 良い手、ゲイン）
- eval_thresholds = [1.0, 2.0, 5.0, 10.0, 15.0]

**実行フロー**:
```
i = 0, threshold = 1.0
-2.0 < 1.0 ? YES → break
return i = 0 → PURPLE（悪い）
```

→ 良い手（-2.0）が紫（最悪）として表示される

**期待値**:
```
-2.0 は「ゲイン」＝「良い手」
→ 高い index（4 or 5）= 緑色 で表示されるべき
```

### 修正案

#### **修正案 A: evaluation_class() ロジック反転**（推奨度: 低）

```python
# 修正: >= に変更
if points_lost >= threshold:
    break  # 大きい損失で break
```

**問題**: これは KataGo の負の値に対応していない

#### **修正案 B: KataGo 損失値を絶対値に変換**（推奨度: 中）

```python
# eval_color() で呼び出し時に符号を反転
points_lost_abs = abs(points_lost)
i = evaluation_class(points_lost_abs, eval_thresholds)
```

**利点**: シンプル
**懸念**: 他の場所への影響

#### **修正案 C: evaluation_class() を完全に再設計**（推奨度: 高）⭐

```python
def evaluation_class(points_lost: float, eval_thresholds: Sequence[float | None]) -> int:
    """
    Map loss value to color class.

    Logic:
    - points_lost: 正 = 悪い手（ロス）
    - points_lost: 負 = 良い手（ゲイン）
    - 返値: 0=紫（悪い） ~ 5=緑（良い）

    Mapping:
    - points_lost >= 15.0 → index 0 (PURPLE, terrible)
    - 10.0 <= points_lost < 15.0 → index 1 (RED, bad)
    - 5.0 <= points_lost < 10.0 → index 2 (ORANGE, poor)
    - 2.0 <= points_lost < 5.0 → index 3 (YELLOW, okay)
    - 1.0 <= points_lost < 2.0 → index 4 (LIGHT_GREEN, good)
    - points_lost < 1.0 → index 5 (DARK_GREEN, excellent)
    """
    # 逆ソート: 大きい損失 → 悪い色
    for i in range(len(eval_thresholds) - 1, -1, -1):
        threshold = eval_thresholds[i]
        if threshold is None:
            continue
        if points_lost >= threshold:
            return i
    return len(eval_thresholds)  # 最悪のインデックス
```

**利点**:
- ✅ ロジックが明確（損失値が大きい = 悪い色）
- ✅ KataGo の負の値に対応可能
- ✅ ドキュメント充実

**懸念**: テスト修正が必要

---

## 3. 実装戦略（6 ステップ）

### Step 1: 調査と検証（30分）

**ファイル**: `core/game_node.py`, `core/game.py`

**確認項目**:
1. KataGo から `points_lost` がどのように計算されているか
2. 負の値が実際に送られてくるか
3. どこで符号が反転しているか

```bash
grep -n "points_lost" katrain/core/game_node.py
grep -n "pointsLost" katrain/core/game_node.py
```

**出力**: `Phase117_KataGo_Analysis.md`（調査結果）

### Step 2: 修正案の選定（15分）

**判断基準**:
- シンプルさ
- テスト影響範囲
- 長期的な保守性

**推奨**: 修正案 C（完全再設計）

### Step 3: evaluation_class() の修正（1時間）

**ファイル**: `katrain/core/utils.py:25-46`

**変更内容**:
1. 新しいロジック実装
2. ドキュメント充実
3. 符号処理の明確化

**テスト**: `tests/test_eval_color_regression.py` 更新

### Step 4: 呼び出し側の調整（30分）

**ファイル**: `katrain/gui/badukpan.py:372-380`

**変更内容**:
```python
def eval_color(self, points_lost: float, show_dots_for_class: list[bool] | None = None) -> list[float] | None:
    eval_thresholds = self.trainer_config.get("eval_thresholds", [1.0, 2.0, 5.0, 10.0, 15.0])
    theme = self.trainer_config.get("theme", "theme:normal")

    # evaluation_class() の新しいロジックに対応
    i = evaluation_class(points_lost, eval_thresholds)
    colors = Theme.EVAL_COLORS[theme]

    if show_dots_for_class is None or show_dots_for_class[i]:
        return colors[i]
    return None
```

### Step 5: テストと検証（1.5時間）

**テスト実行**:
```powershell
# 回帰テスト
uv run pytest tests/test_eval_color_regression.py -v

# 全テスト
uv run pytest tests -q

# mypy
uv run mypy katrain
```

**ユーザー検証**:
1. KaTrain を起動
2. tests/data/test_top_moves_color.sgf を読み込み
3. Top Moves が多色で表示されることを確認

### Step 6: ドキュメント更新（30分）

**ファイル**:
- `PHASE117_COMPLETION.md`
- `CLAUDE.md` Phase 情報更新
- `docs/archive/CHANGELOG.md` 更新

---

## 4. 修正詳細（修正案 C）

### utils.py での変更

```python
# BEFORE
def evaluation_class(points_lost: float, eval_thresholds: Sequence[float | None]) -> int:
    """Evaluate the class (bucket) for a given loss value."""
    i = 0
    while i < len(eval_thresholds) - 1:
        threshold = eval_thresholds[i]
        if threshold is None:
            i += 1
            continue
        if points_lost < threshold:
            break
        i += 1
    return i

# AFTER
def evaluation_class(points_lost: float, eval_thresholds: Sequence[float | None]) -> int:
    """
    Evaluate the class (color bucket) for a given loss value.

    Maps loss values to color indices from worst (0, purple) to best (5, green).

    Args:
        points_lost: Loss value (positive=bad move, negative=good move/gain)
        eval_thresholds: Thresholds for each class (ascending order)

    Returns:
        Color class index (0-based, 0=worst, 5=best)

    Logic:
        Larger positive loss → Lower index (worse color: purple)
        Smaller/negative loss → Higher index (better color: green)

    Examples:
        points_lost=15.0, thresholds=[1,2,5,10,15] → index 0 (PURPLE, terrible)
        points_lost=5.0, thresholds=[1,2,5,10,15] → index 2 (ORANGE, poor)
        points_lost=0.5, thresholds=[1,2,5,10,15] → index 4 (LIGHT_GREEN, good)
        points_lost=-2.0, thresholds=[1,2,5,10,15] → index 5 (DARK_GREEN, excellent)
    """
    # Reverse iteration: from worst threshold to best
    # Larger loss values get mapped to lower indices (worse colors)
    for i in range(len(eval_thresholds) - 1, -1, -1):
        threshold = eval_thresholds[i]
        if threshold is None:
            continue
        if points_lost >= threshold:
            return i

    # All values are below minimum threshold = best color
    return len(eval_thresholds) - 1
```

### テスト更新

```python
# tests/test_eval_color_regression.py に追加

def test_eval_color_with_negative_loss():
    """Test that negative loss (gains) map to higher indices (better colors)."""
    thresholds = [1.0, 2.0, 5.0, 10.0, 15.0]

    # Negative loss = gains (good moves) should map to high indices
    idx_gain = evaluation_class(-2.0, thresholds)
    assert idx_gain == 4 or idx_gain == 5, f"Gain should be high index, got {idx_gain}"

    # Positive loss = bad moves should map to low indices
    idx_loss = evaluation_class(10.0, thresholds)
    assert idx_loss <= 2, f"Bad move should be low index, got {idx_loss}"

def test_eval_color_gradient():
    """Test that loss values produce expected color gradient."""
    thresholds = [1.0, 2.0, 5.0, 10.0, 15.0]

    # Create ascending loss values
    losses = [-5.0, 0.5, 1.5, 5.5, 12.0, 20.0]
    indices = [evaluation_class(loss, thresholds) for loss in losses]

    # Indices should generally increase (better loss = higher index)
    # Note: Some ties are expected due to threshold boundaries
    for i in range(len(indices) - 1):
        assert indices[i] <= indices[i + 1], \
            f"Color should improve: {losses[i]}→index{indices[i]}, " \
            f"{losses[i+1]}→index{indices[i+1]}"
```

---

## 5. リスク管理

### リスク 1: テスト互換性
**リスク**: 既存テストが新しいロジックに対応していない
**緩和策**:
- 新ロジック実装後に全テスト実行
- テスト失敗時は段階的に修正

### リスク 2: ユーザー報告値との不整合
**リスク**: KataGo の実際の損失値が予想と異なる
**緩和策**:
- デバッグログを追加して実際の値を確認
- 必要に応じてロジック調整

### リスク 3: パフォーマンス
**リスク**: 新しいロジックが遅くなる可能性
**緩和策**: O(n) アルゴリズムなので影響なし

---

## 6. スケジュール

| ステップ | 内容 | 予想時間 | 責任 |
|---------|------|---------|------|
| 1 | 調査と検証 | 30分 | Claude Code |
| 2 | 修正案選定 | 15分 | ユーザー承認 |
| 3 | evaluation_class() 修正 | 1時間 | Claude Code |
| 4 | 呼び出し側調整 | 30分 | Claude Code |
| 5 | テスト・検証 | 1.5時間 | Claude Code + ユーザー |
| 6 | ドキュメント更新 | 30分 | Claude Code |
| **合計** | | **4時間** | |

---

## 7. 成功基準（チェックリスト）

- [ ] KataGo の点数計算ロジックを理解した
- [ ] evaluation_class() 新ロジック実装完了
- [ ] テスト 10/10 以上パス
- [ ] 全テスト 3776 PASS（回帰なし）
- [ ] mypy strict モード 100% 準拠
- [ ] Top Moves が多色グラデーション表示
- [ ] ドキュメント更新完了
- [ ] リモート（origin/main）に同期

---

## 8. 次のステップ

**ユーザーの決定事項**:

1. ✅ **Phase 117 を実施する** → すぐに Step 1 から開始
2. ❌ **Phase 116 をリバートしてから実施** → git revert 後に開始
3. ⏸️ **一度 Phase 115 に戻して確認** → 後から再検討

**推奨**: ✅ Phase 117 を実施する（最も効率的）

---

## 9. 参考資料

### 関連ドキュメント
- `PHASE116_REGRESSION_VERIFICATION.md` - Phase 116 分析
- `debug_top_moves_issue.py` - デバッグスクリプト
- `debug_katago_loss_values.py` - KataGo ロジック分析

### ファイル参照
- `katrain/core/utils.py` - evaluation_class()
- `katrain/gui/badukpan.py` - eval_color()
- `katrain/gui/theme.py` - EVAL_COLORS 定義
- `tests/test_eval_color_regression.py` - 回帰テスト

---

**Phase 117 計画完成日**: 2026-02-03
**ステータス**: ✅ 準備完了、ユーザー承認待ち
