# Phase 270 — 複数カルテ集約 + サマリプロンプト v3.5 拡張

> 実装日: 2026-07-18 / Lv2 / 1PR / 4 ファイル変更 / 1 ファイル新規 / +52 unit tests
> 動機: 単局カルテには `area` / `position_difficulty` / `meaning_tag_label` /
> `reason_tags_distribution` / `data_quality` が含まれているが、現行の
> サマリ経路 (`summary_json_export.py`) は `GameSummaryData` から直接構築
> するため、これらのフィールドが **集計サマリ JSON で欠落** していた。
> ユーザー報告「LLM に投げる前に集約サマリにもこれらの情報を乗せたい」。

## 1. ゴール

**「単局カルテ JSON を N 個渡すと、欠落していた 6 フィールドを埋めた
schema 3.5 のサマリプロンプトが生成できる」** 状態を作る。既存 3.4
経路は完全後方互換。

## 2. 背景と問題

### 2.1 現行アーキテクチャの欠落

```
[1局]  KataGo解析
        ↓ build_karte_json()
        単局カルテ JSON v3.4
        ├─ important_moves[].{area, position_difficulty, primary_tag,
        │                       meaning_tag_label}
        ├─ critical_3.<color>[].{area, position_difficulty, ...}
        ├─ reason_tags_distribution{black/white: {tag: count}}
        ├─ data_quality.{avg_visits, reliability_pct, coverage_pct}
        └─ loss_progression[].{start_move, end_move, avg_loss}

[複数局] build_summary_json()  ← GameSummaryData 由来
        集計サマリ JSON v3.4
        ├─ players.<name>.{mistakes, phases, top_mistakes}
        └─ loss_progression{all/even/handicapped: [...]}

[LLM]  build_summary_weakness_prompt()
        プロンプト Markdown
```

`build_summary_json` は `GameSummaryData`（生スナップショット由来）
を**直接**受け取るため、カルテ JSON が持つ拡張フィールド
（`area` / `position_difficulty` / `meaning_tag_label`）が入力段階で
欠落。`summary_prompt_builder` はこの欠落を**そのまま LLM に渡す**。

### 2.2 ユーザー要件（修正要件 1〜6）

1. `reason_tags_distribution` → `summary["reason_tags_by_color"]` に
   color 別・game 横断で合算
2. `area` + `position_difficulty` → `summary["area_difficulty_matrix"]`
   = `{"center": {"only": N, "normal": N}, "edge": {...}}`
3. `loss_progression` 10 手区切りから連続スパイク区間（avg_loss > 全体
   平均の 2 倍）を自動検出 → `summary["loss_spike_windows"]`
4. `top_mistakes` を `primary_tag` ごとにグループ化 → 代表例を
   `summary["representative_moves_by_tag"]` に
5. `data_quality.avg_visits` / `reliability_pct` を game 横断で平均
   → `summary["data_quality_aggregate"]`
6. `primary_tag` ↔ `meaning_tag_label` 日本語マッピングを引き継ぎ

スキーマバージョンを **3.5** にバンプ。**後方互換性のため既存
フィールドは変更しない**。

## 3. 設計判断

### 3.1 配置: 新規モジュール `karte_aggregator.py` を新設 (B 案)

**選択理由**:
- 既存の `karte_detector.py` (Phase 215) / `json_type.py` (Phase 221 /
  228) と同じ「core 層・Kivy 非依存・pure functions」パターン
- 将来 CLI 統合 (`Phase 270-D 想定`) で再利用しやすい
- `summary_prompt_builder` への組み込みは薄いラッパーに留めて
  prompt builder 本体の肥大化を防ぐ

### 3.2 prompt builder との結線: `SummaryPromptConfig.kartes`

`SummaryPromptConfig` に **optional** フィールド `kartes: tuple[dict, ...] | None`
を追加。渡された場合のみ 6 フィールドを計算 + body に
「Aggregated Karte View (Phase 270, schema 3.5)」セクションを追加
+ body header の `Schema:` 行を `3.5` にバンプ。**未指定時は従来
3.4 のまま** で、既存テスト・既存呼び出し元は完全無改変で動作。

### 3.3 サブフェーズ分割

| Phase | 概要 | 主な変更 | tests |
|-------|------|---------|-------|
| 270-α | karte_aggregator.py 実装 | 6 集約関数 + AggregatedKarteView | +52 |
| 270-β | summary_prompt_builder.py 拡張 | kartes 引数 + body テンプレ + Schema 3.5 | (270-α に含む) |
| 270-γ | __init__.py export 追加 | 8 シンボルを package から再公開 | (270-α に含む) |

## 4. 実装

### 4.1 新規ファイル: `katrain/core/coach/karte_aggregator.py`

6 つの独立した pure 関数 + 1 つのバンドル dataclass + 1 つの
エントリポイント関数。

```python
# 公開 API
def aggregate_reason_tags_by_color(kartes) -> dict[str, dict[str, int]]
def aggregate_area_difficulty(kartes) -> dict[str, dict[str, int]]
def detect_loss_spike_windows(kartes, *, multiplier=2.0) -> list[dict]
def group_representative_moves_by_tag(kartes, *, top_n=2) -> dict[str, list[dict]]
def aggregate_data_quality(kartes) -> dict[str, Any]
def build_meaning_tag_label_map(kartes) -> dict[str, str]

@dataclass(frozen=True)
class AggregatedKarteView:
    reason_tags_by_color: ...
    area_difficulty_matrix: ...
    loss_spike_windows: ...
    representative_moves_by_tag: ...
    data_quality_aggregate: ...
    meaning_tag_label_map: ...
    games_count: int
    schema_version: str = "3.5"

def aggregate_kartes(kartes, *, loss_spike_multiplier=2.0, representative_top_n=2) -> AggregatedKarteView
```

### 4.2 設計上の細部

#### `_iter_kartes` フィルタ

- `schema_version` キーを持つ dict のみ「karte」とみなして処理
- summary 形（`games_analyzed` のみ）も弾く
- 混在リスト (`kartes + summaries`) を渡されてもクラッシュしない

#### `aggregate_area_difficulty` のグリッド

- 常に **完全な 3x5 グリッド**を返す（zero-filled）
- `area` が未知値ならスキップ（"unknown area" バケットは作らない）
- `position_difficulty` が未知値なら `"unknown"` セルに正規化
- レンダラーが None チェックなしで `area_dict["only"]` できる

#### `detect_loss_spike_windows` の閾値

- デフォルト multiplier = **2.0**（ユーザー仕様 `avg_loss > 全体平均の2倍`）
- 厳密に `>` を使用（境界値 `== threshold` は非スパイク）
- **連続するスパイクは 1 つの run にマージ**（LLM には連続した区間として
  見せた方が自然）
- `start_move` / `end_move` / `total_loss` / `bucket_count` / `avg_loss` を
  出力
- `multiplier <= 0` は `ValueError`

#### `aggregate_data_quality` の同点処理

- `confidence_level` の集計で同点（例: "high" 1 票 vs "low" 1 票）になった
  場合は **常に "medium"** を採用
  - 理由: 「high」「low」どちらも信号過大。`"high"/"low"` の接頭で強い主張
    をするのは証拠不十分。LLM に「強い / 弱い棋力」と断定させたくない
  - 3 状態 (high/medium/low) のちょうど真ん中 = 「中庸 = medium」が安全

#### `group_representative_moves_by_tag` の入力ソース優先順位

1. `important_moves` (Phase 149 標準の per-move データ)
2. `critical_3.<color>` (Phase 248-B2 で拡張された重要局面)
3. `top_mistakes` (稀: 単局カルテにもこれが含まれるケース用)

`loss` フィールドは `loss_clamped` → `score_loss` → `points_lost` →
`0.0` のフォールバック順。

### 4.3 summary_prompt_builder.py の変更

- `SummaryPromptConfig.kartes: tuple[dict, ...] | None = None` 追加
- `SCHEMA_VERSION_WITH_KARTES: str = "3.5"` モジュール定数を新設
- `_format_aggregated_view_block(view: AggregatedKarteView) -> str` ヘルパー追加
- `_BODY_HEADER_TEMPLATE` に `{aggregated_view_block}` プレースホルダ追加
- `_SYSTEM_INSTRUCTION_TEMPLATE` の STRICT RULES 3 に
  `Aggregated Karte View ブロック (Phase 270, schema 3.5)` を valid
  source として追記
- `build_summary_weakness_prompt` 内で `kartes` 提供時のみ:
  - `aggregate_kartes(config.kartes)` 実行
  - `effective_schema_version = SCHEMA_VERSION_WITH_KARTES` (= 3.5)
  - `_format_aggregated_view_block(view)` を body に追加

### 4.4 出力例（kartes 提供時）

````markdown
> Schema: 3.5
> Games: 2
...

### Summary JSON
```json
{ ... }
```

### Aggregated Karte View (Phase 270, schema 3.5)

#### reason_tags_by_color
- **black**: endgame_hint=7, heavy_loss=2
- **white**: endgame_hint=1

#### area_difficulty_matrix
| area | only | hard | normal | easy | unknown |
|------|------|------|--------|------|---------|
| corner | 1 | 2 | 0 | 0 | 0 |
| edge | 0 | 1 | 3 | 0 | 0 |
| center | 0 | 1 | 1 | 0 | 0 |

#### loss_spike_windows
- **g1**: moves 31-60 (1 buckets, total_loss=50.00, avg=5.000)

#### representative_moves_by_tag
- **life_death_error** (死活ミス): Q16 #87 (loss=19.00, g1)
- **reading_failure** (読み抜け): D4 #62 (loss=8.50, g1)

#### data_quality_aggregate
- games_count: 2
- avg_visits: 250.0
- reliability_pct: 95.5
- coverage_pct: 100.0
- total_moves: 400
- confidence_level: high

#### meaning_tag_label_map
- life_death_error → 死活ミス, reading_failure → 読み抜け, ...
````

## 5. テスト戦略

### 5.1 新規: `tests/test_coach_karte_aggregator.py`（+52 tests）

7 つのテストクラス:

| クラス | 検証対象 | テスト数 |
|--------|---------|---------|
| `TestReasonTagsByColor` | aggregate_reason_tags_by_color の集計・欠落処理 | 8 |
| `TestAreaDifficulty` | aggregate_area_difficulty のグリッド・正規化 | 7 |
| `TestLossSpikeWindows` | detect_loss_spike_windows の検出・マージ・閾値変更 | 9 |
| `TestGroupRepresentativeMoves` | group_representative_moves_by_tag の top_n・severity 順・fallback | 8 |
| `TestAggregateDataQuality` | aggregate_data_quality の平均・同点処理 | 4 |
| `TestMeaningTagLabelMap` | build_meaning_tag_label_map の karte 優先・registry フォールバック | 4 |
| `TestAggregateKartes` | 統合エントリポイント + パラメータ | 4 |
| `TestSummaryPromptIntegration` | build_summary_weakness_prompt との結線 | 8 |

### 5.2 後方互換

- 既存 `test_coach_summary_prompt_builder.py` (59 tests) 無改変で
  全パス — `kartes` 未指定時の動作が完全に同一
- 既存 `test_phase269_summary_phase_all_and_voice_unify.py` (45 tests) 無改変で全パス

### 5.3 累計テスト

| Phase | 新規 | 累計 |
|-------|------|------|
| Phase 269 完了時点 | - | 5,615 件 |
| **Phase 270 完了** | **+52** | **5,667 件** |

## 6. 影響範囲

### 6.1 変更ファイル

| ファイル | 変更種別 | 概要 |
|---------|---------|------|
| `katrain/core/coach/karte_aggregator.py` | **新規** | 6 関数 + AggregatedKarteView + aggregate_kartes |
| `katrain/core/coach/summary_prompt_builder.py` | 修正 | kartes 引数 + _format_aggregated_view_block + Schema 3.5 + body テンプレ |
| `katrain/core/coach/__init__.py` | 修正 | 8 シンボルを export 追加 |
| `tests/test_coach_karte_aggregator.py` | **新規** | +52 unit tests |

### 6.2 非変更

- `katrain/core/reports/summary_json_export.py` (`build_summary_json`)
  は **触らない** — 既存 `summary_json_export` 経路はそのまま
- `katrain/core/reports/karte/json_export.py` (`build_karte_json`)
  も **触らない** — カルテ JSON v3.4 仕様は不変
- `REPORT_SCHEMA_VERSION` (`definitions.py`) は据え置き — 3.4 のまま
- GUI / Kivy 層 (`llm_coach_popup.py` 等) は未変更 — GUI 統合は将来
  Phase (270-D 想定) で着手

## 7. 後方互換性

- `SummaryPromptConfig()` 既存呼び出しは無改変で動作（`kartes=None`）
- `build_summary_weakness_prompt(summary, config)` 既存呼び出しは
  Schema 3.4 / 既存 body のまま
- テスト / golden file には一切影響なし
- LLM Coach popup も `SummaryPromptConfig` を直接構築しないので影響なし
  （popup 側で karte → カルテ → prompt のフローは引き続き単局のみ）

## 8. 既知の制約と将来タスク

### 8.1 Deferred（今回スコープ外）

- **GUI 統合**: LLM Coach popup の「複数カルテ選択」UI → 単局 /
  複数局サマリ / 複数カルテ集約の 3 モード切替（Phase 270-D 想定）
- **CLI 統合**: `core/coach/cli.py` に `aggregate <karte1.json> <karte2.json>`
  サブコマンド追加
- **humanize display**: `data_quality_aggregate` の avg_visits を
  人間可読文字列（"200 visits"）に整形

### 8.2 数値仕様

- `loss_spike_windows` の `multiplier` は固定 2.0 (Phase 270)。ユーザー
  テストで「1.5 が欲しい」という声が出たら `SummaryPromptConfig` に
  露出する想定
- `representative_top_n` も 2 固定。`top_n=0` で「全件」が選択可

### 8.3 数学的注記

- 2-bucket loss_progression 入力では 2.0× multiplier が物理的に
  発火しない（threshold = spike + other, strict > が成立しない）
- これはバグではなく「1 spike vs 1 normal では判定不能」という
  数学的現実。テストでは 3+ bucket 入力を使用

## 9. 関連 Phase

- Phase 215: `karte_detector.py` (per-karte symptom detection) — 同パターンの前置
- Phase 218-220: calibration fixtures / CLI calibrate / CLI trace — 同パターンの検証基盤
- Phase 227/228: multi-game summary support (Shape A/B) — 上位層の同居
- Phase 269: AYAKA 削除 + Shape B 整合性 — 直前 Phase の voice 統一
- Phase 229: 棋力プリセット統一 (`player_rank`) — 別途統合済み

## 10. チェックリスト

- [x] `karte_aggregator.py` 新規実装
- [x] 集約関数 6 個すべて + AggregatedKarteView + aggregate_kartes
- [x] `summary_prompt_builder.py` に kartes 引数追加
- [x] body テンプレに Aggregated Karte View セクション
- [x] Schema 3.5 へのバンプ条件付き
- [x] `__init__.py` に 8 シンボルを export
- [x] `tests/test_coach_karte_aggregator.py` 新規 52 tests
- [x] 既存テスト全パス (test_coach_summary_prompt_builder, phase269)
- [x] mypy パス (17 coach ファイル)
- [x] ruff lint + format パス
- [x] AGENTS.md / 01-roadmap.md 更新
