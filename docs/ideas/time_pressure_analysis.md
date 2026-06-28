# 時間プレッシャー分析（Time Pressure Analysis）

> **ステータス**: idea（Phase 157-E）。実装は未定。
> 関連 SGF プロパティ: `TM`（基本持ち時間）, `TC`（秒読み回数）, `TT`（秒読み秒数）, `BL`（黒の着手時間）, `WL`（白の着手時間）

---

## 背景

Phase 157 のメモで、ユーザーが「**TM/TC/TT の情報が SGF にあるため、着手時間データ（BL/WL）と組み合わせれば「秒読みに入った後のミス増加」などを分析可能**」と指摘。

myKatrain は現状 KataGo の解析結果（`points_lost` / `score_loss`）のみを損失として扱っており、**着手に要した時間** を一切保持していない。`MoveEval` に `time_spent_seconds: float | None = None` のようなフィールドがあれば、秒読み前後で `points_lost` の分布を比較できる。

---

## 想定ユースケース

| ユースケース | 必要な SGF プロパティ | 出力セクション案 |
|--------------|---------------------|----------------|
| 秒読み突入後のミス率上昇 | `BL`/`WL`（着手時間）, `TM`/`TC`/`TT` | Summary: `time_pressure_loss_correlation` |
| 序盤 vs 終盤の平均思考時間比較 | `BL`/`WL` | Karte: `thinking_time_profile` |
| ティルト検知（連続短手 + 損失急増） | `BL`/`WL` + `points_lost` | Karte: `tilt_candidate_moves` |
| ハンデ戦での時間管理 | 上記すべて + `HA`/`KM` | Phase 157-C と組み合わせた `even.time_pressure` / `handicapped.time_pressure` |

---

## 実装コスト見積もり

| 作業 | 規模 | 備考 |
|------|------|------|
| SGF パース拡張（`BL`/`WL`/`TM`/`TC`/`TT` を読み取り） | Lv1 | `sgf_parser.py` の property 読み取りロジックに4行追加 |
| `MoveEval.time_spent_seconds` フィールド追加 | Lv1 | `katrain/core/analysis/models/move_eval.py` |
| `GameSummaryData` に `time_control_*` を伝播 | Lv1 | 既存 `handicap`/`komi` と同パターン |
| 秒読み境界検出ロジック | Lv2 | 残り時間 = `TM + TC * TT - sum(BL/WL up to here)` |
| サマリーセクション追加 | Lv2 | `SummaryReport.players[...].time_pressure` |
| ゴールデン + テスト追加 | Lv2 | 既存 fixtures（fox / alphago / panda）に time control はないので **新 fixture が必要** |

合計: **Lv3 相当**（複数ファイル + 新 fixture）。

---

## 技術的検討事項

### 1. 秒読み境界の計算
- ノード N の黒着手時点の残り時間 = `TM - sum(BL[1..N-1] for B) + sum(WL[1..N-1] for W)`
  - ※ 秒読み回は複雑なため、Phase 1 では **「秒読み突入フラグ」** のみを提供し、厳密な残り時間は将来課題とする。
- `TC > 0 AND 累計消費時間 > TM` → 秒読みモード突入

### 2. 欠損値の扱い
- 野狐・KGS 等では BL/WL が記録されないことが多い。
- Phase 1 では **「`time_spent_seconds` が `None` の着手は時間分析から除外」** とし、`status="insufficient_data"` を返す方針（Phase 155-D の opponent_strength と同パターン）。

### 3. テストデータ
- `tests/data/` に **time control 付き SGF** を最低 1 ファイル追加する必要がある。
- 候補: ユーザーが持っている野狐 SGF（`[富乐山下]vs[仙得]1761895784030052536.sgf`）。`TM[300] TC[3] TT[30]` を持つ。
  - ただし時間データが BL/WL として含まれているかは要確認。
- 代替: Python で合成 SGF を生成する helper を `tests/conftest.py` に追加。

### 4. 既存機能との統合
- Phase 157-C の `even` / `handicapped` 分岐と組み合わせれば、「互先での秒読み影響」と「ハンデ戦での秒読み影響」を分離できる。
- Phase 155-D の opponent_strength_loss_correlation と同様の構造で `time_pressure_loss_correlation` を追加可能。

---

## 想定スキーマ（案）

```jsonc
// KarteReport に追加 (Phase X)
"thinking_time_profile": {
  "black": {
    "avg_seconds": 25.3,
    "p10_seconds": 3.0,
    "p50_seconds": 18.0,
    "p90_seconds": 65.0,
    "total_seconds": 758.2,
    "byo_yomi_moves": 12,    // 秒読みに入った手数
    "status": "computed"
  },
  "white": {...}
},

// SummaryReport.players[...].time_pressure に追加
"time_pressure_loss_correlation": {
  "before_byo_yomi": {
    "moves": 142,
    "total_loss": 28.4,
    "avg_loss": 0.20,
    "mistake_count": 4
  },
  "in_byo_yomi": {
    "moves": 18,
    "total_loss": 12.5,
    "avg_loss": 0.69,        // ← 3.4倍に悪化
    "mistake_count": 3
  },
  "delta_avg_loss": 0.49,
  "status": "computed" | "insufficient_data" | "no_time_control"
}
```

---

## 段階リリース案

### Phase X-A: SGF 読み取り + フィールド追加（Lv1）
- `MoveEval.time_spent_seconds` 追加
- `GameSummaryData.time_control_*` 追加
- 既存テストへの影響なし

### Phase X-B: thinking_time_profile セクション（Karte）（Lv2）
- パーセンタイル集計ロジック追加
- ゴールデン更新

### Phase X-C: time_pressure_loss_correlation セクション（Summary）（Lv2）
- 秒読み境界検出
- 損失分布比較

---

## 関連ファイル（実装時に触る想定）

| ファイル | 変更 |
|---------|------|
| `katrain/core/sgf_parser.py` | `BL` / `WL` / `TM` / `TC` / `TT` 読み取り |
| `katrain/core/analysis/models/move_eval.py` | `time_spent_seconds` 追加 |
| `katrain/core/analysis/models/skill.py` | `GameSummaryData.time_control_*` 追加 |
| `katrain/core/batch/stats/extraction.py` | SGF ルートから `time_control_*` 抽出 |
| `katrain/core/reports/sections/time_pressure.py`（新規） | セクションビルダ |
| `katrain/core/reports/schema.py` | `time_pressure_loss_correlation` 追加 |
| `katrain/core/reports/karte/json_export.py` | Karte 側 emission |
| `katrain/core/reports/summary_json_export.py` | Summary 側 emission |
| `tests/data/time_control_*.sgf`（新規） | fixture |
| `tests/test_time_pressure.py`（新規） | ユニットテスト |

---

## 質問事項（実装着手前）

1. ユーザーは野狐 SGF をテスト fixture として提供可能か？
2. ハンデ戦での時間管理分析は Phase 157-C の分離出力と統合するか、別セクションとするか？
3. 秒読み 0 回（切れ負け）のケースは別途ハンドリングが必要か？

---

## 参考

- [SGF File Format FF[4] - GM/HA/KM/TM/TC/TT/BL/WL 仕様](https://www.red-bean.com/sgf/go.html)
- Phase 155-D `opponent_strength_loss_correlation` の `status` パターンを踏襲
- Phase 157-C の `even` / `handicapped` 分離を流用可能
