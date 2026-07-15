# Phase 228 マスター仕様書 — summary プロンプトのスキーマ適応

> 起票日: 2026-07-15
> ステータス: ✅ 完了（全サブフェーズ 228-A〜D）
> ユーザー選択: A案（Phase 228 でスキーマ適応）

## 1. 背景とゴール

**背景**: Phase 227-A で実装した `extract_summary_weakness_patterns` と `extract_summary_mistake_buckets` は top-level の `weaknesses` / `phase_x_mistake` ブロックを期待していた。しかし実際の `summary_json_export.py` は `players.<name>.mistakes` と `players.<name>.phases` で出力する異なるスキーマを採用していた。

**問題**: 実 JSON を LLM Coach GUI に読み込ませると、prompt body に "Weakness Patterns (pre-computed, top 0)" と "Phase × Mistake Buckets" の空ブロックが生成され、LLM に「データなし」と嘘をついていた状態だった。

**ゴール**: prompt body が実際の summary JSON から直接データを抽出・表示できるようにする。LLM のハルシネーション余地を排除し、coach としての出力品質を向上させる。

## 2. サブフェーズ一覧

| Phase | 概要 | 主な変更 | tests |
|-------|------|---------|-------|
| 228-A | extractor 拡張（実シェーマ対応） | 4 ファイル + 30 tests | +30 |
| 228-B | prompt builder で新セクション描画 | 4 ファイル + 24 tests | +24 |
| 228-C | validator で標準カテゴリを valid reference 化 | 2 ファイル + 19 tests | +19 |
| 228-D | real_shape calibration fixtures + E2E 統合テスト | 2 ファイル + 26 tests | +26 |
| **合計** | | **+99** tests | **+99** |

## 3. シェーマの違い

### Shape A（Phase 227-A 想定、fixture-style）

```json
{
  "weaknesses": {
    "black": [
      {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
      ...
    ],
    "white": [...]
  },
  "phase_x_mistake": {
    "middle:blunder": 8,
    ...
  }
}
```

### Shape B（Phase 228-A 対応、summary_json_export.py 実際）

```json
{
  "meta": {"games_analyzed": 3, ...},
  "games": [...],
  "players": {
    "仙得": {
      "mistakes": {
        "good": {"count": 310, "pct": 79.9, "denominator": 388, "avg_loss": 0.28},
        "inaccuracy": {"count": 51, "pct": 13.1, "denominator": 388, "avg_loss": 3.11},
        "mistake": {"count": 22, "pct": 5.7, "denominator": 388, "avg_loss": 5.69},
        "blunder": {"count": 5, "pct": 1.3, "denominator": 388, "avg_loss": 19.04}
      },
      "phases": {
        "opening": {"moves": 75, "total_loss": 47.01, "avg_loss": 0.627},
        "middle": {"moves": 173, "total_loss": 370.78, "avg_loss": 2.143},
        "endgame": {"moves": 140, "total_loss": 48.6, "avg_loss": 0.347}
      },
      "top_mistakes": [...],
      ...
    }
  }
}
```

## 4. Phase 228-A: extractor 拡張

### 新規関数

```python
extract_summary_player_mistakes(data) -> dict[str, list[dict]]
    # Returns: {player_name: [{category, count, pct, avg_loss,
    #                         total_loss, denominator}, ...], ...}
    # Categories in severity order: blunder → mistake → inaccuracy → good

extract_summary_player_phase_losses(data) -> dict[str, dict[str, dict]]
    # Returns: {player_name: {phase: {moves, total_loss, avg_loss}, ...}, ...}
    # Phases in temporal order: opening → middle → endgame
```

### 既存関数拡張

```python
extract_summary_weakness_patterns(data, *, top_n=0) -> list[dict]
    # Phase 228-A: Shape B (players.<name>.mistakes) 対応
    # Shape A がある場合は Shape A を優先
    # Shape A がない場合のみ Shape B から (player, category) 単位のパターンを合成
    # total_loss が JSON に無い場合は avg_loss * count で再構成
    # frequency_ratio は Shape B では misleading (per-move) なので 0 にして
    # 代わりに pct フィールドを含める
```

## 5. Phase 228-B: prompt body の実シェーマ対応

### 新規セクション

```
### Player Mistake Distribution (sentoku870)
- **blunder**: 5/388 (1.3%) - avg_loss 19.04
- **mistake**: 22/388 (5.7%) - avg_loss 5.69
- **inaccuracy**: 51/388 (13.1%) - avg_loss 3.11
- **good**: 310/388 (79.9%) - avg_loss 0.28

### Player Phase Loss Distribution (sentoku870)
- **middle**: 173手 / 370.78損失 (avg 2.143)  ← worst phase first
- **endgame**: 140手 / 48.60損失 (avg 0.347)
- **opening**: 75手 / 47.01損失 (avg 0.627)
```

### Birdseye view (player_name=None)

```
### Player Mistake Distribution (全体俯瞰)
- **sentoku870**: top=blunder (5/388, 1.3%, avg_loss 19.04)
- **opponent1**: top=blunder (2/388, 0.5%, avg_loss 18.00)

### Player Phase Loss Distribution (全体俯瞰)
- **sentoku870** (worst phase): phase=`middle` / 173手 / 370.78損失
- **opponent1** (worst phase): phase=`middle` / 173手 / 150.00損失
```

### System instruction 更新

weakness pattern のソースを 3 つ明記:
1. `weakness_patterns` リスト (Phase 227-A format)
2. `weaknesses[<color>]` ブロック (Phase 227-A format)
3. `Player Mistake Distribution` ブロック (Phase 228-B format, categories: good / inaccuracy / mistake / blunder)

### `_format_patterns_block` 改良

Shape B パターンの `frequency_ratio` (per-move count / games) は misleading。
代わりに `pct` フィールドを「全体に占める割合=X.X%」として表示:

```
1. **inaccuracy** / phase=`all` / player=`sentoku870` / count=51 / 全体に占める割合=13.1% / 総損失=158.6
2. **mistake** / phase=`all` / player=`sentoku870` / count=22 / 全体に占める割合=5.7% / 総損失=125.2
```

Shape A は従来通り「頻度=X.X%」(per-game frequency) を維持。

### `_resolve_focused_player` 設計変更

`configured_player` がマッチしない場合、または `None` の場合、`None` を返す (全体俯瞰用)。auto-pick を削除 (LLM を誤解させるため)。

## 6. Phase 228-C: validator の valid reference 拡張

### 拡張された valid reference セット

```python
_STANDARD_MISTAKE_CATEGORIES = frozenset({
    "good", "inaccuracy", "mistake", "blunder",
})

_STANDARD_PHASE_LABELS = frozenset({
    "opening", "middle", "endgame",
})
```

### `_summary_available_categories` の挙動

| Shape | categories セット |
|-------|------------------|
| 無し | `set()` |
| Shape A only | Shape A の `weaknesses[*].category` のみ |
| Shape B only | 4 標準 + Shape B の `players.<name>.mistakes` のキー |
| 両方 | Shape A の category + 4 標準 |

### `_summary_available_phases` の挙動

| Shape | phases セット |
|-------|--------------|
| 無し | `set()` |
| Shape A only | Shape A の `weaknesses[*].phase` のみ |
| Shape B only | 3 標準 (opening/middle/endgame) + Shape B の `players.<name>.phases` のキー |
| 両方 | Shape A の phase + 3 標準 |

## 7. Phase 228-D: real_shape calibration fixtures

### 新規 fixture (3 個)

| name | 用途 |
|------|------|
| `real_summary_blunder_focused` | 1 プレイヤー・3 局・blunder 1.3% / middle 370 損失 |
| `real_summary_good_player` | 1 プレイヤー・5 局・good 95% (強者) |
| `real_summary_multi_player` | 2 プレイヤー (強者 + 弱者) ・4 局・birdseye |

合計: **15 fixtures** (8 karte + 4 Shape A summary + 3 Shape B summary)

### E2E 統合テスト

`test_real_shape_fixture_prompt_rendering` (5 tests) と
`test_real_shape_fixture_validator_e2e` (4 tests) で
実シェーマ全フロー (build → render → validate) を検証。

## 8. テスト結果

| フェーズ | テスト数 | 累計テスト合格 |
|---------|---------|--------------|
| Phase 227-E 終了時 | - | 5,319 件 |
| Phase 228-A 完了 | +30 | 5,349 件 |
| Phase 228-B 完了 | +24 | 5,373 件 |
| Phase 228-C 完了 | +19 | 5,392 件 |
| Phase 228-D 完了 | +26 | 5,418 件 |
| **合計** | **+99** | **5,418 件** |

## 9. CLI 動作例

```bash
# 実 JSON に対してプロンプト生成
$ python -m katrain.core.coach.cli build summary.json --summary-mode --rank 4d --player sentoku870

# 出力抜粋:
# summary-mode voice=4d → 智子 — 標準語・論理・構造重視; 4 patterns; 3 games; focus=sentoku870
# 
# ### Player Mistake Distribution (sentoku870)
# - **blunder**: 5/388 (1.3%) - avg_loss 19.04
# - **mistake**: 22/388 (5.7%) - avg_loss 5.69
# - **inaccuracy**: 51/388 (13.1%) - avg_loss 3.11
# - **good**: 310/388 (79.9%) - avg_loss 0.28
# 
# ### Player Phase Loss Distribution (sentoku870)
# - **middle**: 173手 / 370.78損失 (avg 2.143)
# - **endgame**: 140手 / 48.60損失 (avg 0.347)
# - **opening**: 75手 / 47.01損失 (avg 0.627)

# バリデータ実行
$ python -m katrain.core.coach.cli validate summary.json response.txt --rank 4d
# **Status**: ✅ 検証クリア — LLM 出力に問題なし
# **High**: 0 · **Medium**: 0 · **Low**: 0
# **Referenced patterns**: blunder, mistake, inaccuracy
# **Referenced phases**: middle, opening

# 全 fixture カリブレーション
$ python -m katrain.core.coach.cli calibrate
## Summary
- passed: 15
- failed: 0
- total:  15
```

## 10. スコープ外

- ❌ GUI popup の更新（Phase 228 は core 層のみ。GUI 反映は別途 Phase）
- ❌ rank auto-detect from `players.<name>.overall.rank`（実 JSON に rank 無し）
- ❌ `players.<name>.top_mistakes` の per-move 詳細を prompt に入れる（contract 違反）
- ❌ `win_loss_analysis` / `opponent_strength_loss_correlation` の prompt 描画（次のイテレーション）
- ❌ API 連携（手動貼付維持）

## 11. 関連ドキュメント

- `docs/archive/specs-implemented/phase227-llm-coach-multi-game.md` (Phase 227-A〜E)
- `docs/archive/specs-implemented/phase225-master.md` (Phase 225 マスター)
- `docs/archive/specs-planned/phase203-llm-translator.md` (元となった LLM 翻訳仕様)
- `katrain/core/reports/summary_json_export.py` (実 JSON 出力スキーマ)
- AGENTS.md §1.3「現在のフェーズ」と §10「変更履歴」に各 Phase のログ
