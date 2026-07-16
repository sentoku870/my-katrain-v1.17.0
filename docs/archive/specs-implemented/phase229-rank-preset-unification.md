# Phase 229 マスター仕様書 — 棋力プリセット / LLM コーチ 統合

> 起票日: 2026-07-15
> ステータス: ✅ 完了（全サブフェーズ 229-A〜E）
> ユーザー選択: Lv3 + C（設定画面で 1 つだけ選ぶ）/ `auto` 廃止

## 1. 背景とゴール

**背景**: myKatrain には独立した 2 つの棋力管理体系があった:

- **A. 解析設定 `skill_preset`** (5 段階 + auto): ミス判定閾値調整
- **B. LLM コーチ `CoachMode`** (5 段階): 解説トーン選択

両者は **同じ概念「棋力」を別々の語彙で表現**しており、`general/skill_preset` の値と Karte から取得した rank 文字列が「互いに知らない」二重管理状態だった。ユーザーが `skill_preset="beginner"` でも LLM Coach に `5d` を入力しても警告が出ず、UX 上混乱を生んでいた。

**問題**:
1. 設定と現実の乖離が検知できない
2. 同じ rank 文字列を 2 箇所（`default_user_rank` と LLM Coach 入力欄）で管理
3. 暗黙的対応表（relaxed↔BEGINNER、standard↔DAN、pro↔EXPERT）がコード化されていない

**ゴール**: 解析側・LLM 側の両システムが「同じ rank 文字列」を入力として共有する。設定 UI では rank を 1 つだけ入力し、両システムへ自動反映する。

## 2. サブフェーズ一覧

| Phase | 概要 | 主な変更 | tests |
|-------|------|---------|-------|
| 229-A | `core/common/rank.py` 新設（共有 Rank 型 + `rank_to_skill_preset`） | 4 ファイル + 94 tests | +94 |
| 229-B | `resolve_skill_preset()` 統合（GUI 6 callsite 置換） | 8 ファイル + 39 tests | +39 |
| 229-C | 設定 UI 刷新（rank 1 項目に集約、`auto` 廃止） | 6 ファイル + 4 tests | +4 |
| 229-D | LLM Coach 統合（fallback chain に `general/player_rank` 追加） | 2 ファイル + 17 tests | +17 |
| 229-E | ドキュメント + 移行ガイド（本ファイル） | docs-only | — |
| **合計** | | **+154** tests | **+154** |

## 3. アーキテクチャ

### Before（Phase 228 まで）

```
設定: general/skill_preset ─┐
                            ├─→ 解析（誤判定閾値）
LLM Coach 入力: "5d" ──────┘
                            └─→ LLM（解説トーン）
```

2 つの独立した経路が互いに存在を知らない。

### After（Phase 229）

```
設定: general/player_rank (5k / 4段 / 10級 / etc.)
            │
            ├─→ resolve_skill_preset(rank) → SKILL_PRESETS  → 解析
            └─→ resolve_rank_fallback_chain(info, rank, ...) → LLM Coach
```

1 つの rank 入力が両システムに自動反映される。

## 4. 主要 API

### 4.1 `katrain.common.rank` 共有モジュール

```python
from katrain.common.rank import (
    Rank,             # frozen dataclass with kyu_dan: int
    Rank.parse,       # "5k" / "4段" / "初段" / "４段" → Rank | None
    canonical_rank_key,  # raw string → "5k" | "" (canonical ASCII key)
    cmp_rank,         # Rank × Rank → int (Python cmp)
    format_rank,      # Rank, style="ascii"|"jp" → "5k" | "5級"
    RANK_ORDER,       # public alias for _RANK_ORDER (25 entries)
    RANK_ALIASES,     # public alias for _RANK_ALIASES (30 entries)
)
```

### 4.2 解析層への橋渡し (`katrain.core.analysis`)

```python
from katrain.core.analysis import (
    resolve_skill_preset,    # (override, rank) → preset name
    rank_to_skill_preset,    # Rank|str|None → preset name
    RANK_TO_PRESET_DEFAULT,  # dict[int, str] (25 entries)
)
```

### 4.3 LLM Coach への橋渡し (`katrain.gui.features.llm_coach`)

```python
from katrain.gui.features.llm_coach import (
    resolve_rank_fallback_chain,  # (info, perspective, rank_general, rank_user) → str | None
)
```

## 5. UX フロー（設定画面）

### Before（Phase 228）

```
[解析設定]
├─ 棋力プリセット:  ◯ 自動  ◯ 激甘  ◯ 甘口  ◯ 標準  ◯ 辛口  ◯ 激辛
```

### After（Phase 229）

```
[解析設定]
├─ 棋力: [____________________________]
│        例: 5k / 4d / 4段 / 5級 / 初段
│        現在: 標準（5k より自動推定）
```

ユーザーが入力した rank に応じて preset が自動決定される。`auto` 選択肢は廃止。

## 6. UX フロー（LLM Coach）

### Priority Chain (Phase 229-D)

```
1. Karte meta.player_info.{black,white}.rank   ← 最優先
2. SGF BR/WR (via detect_player_info)
3. general/player_rank                         ← NEW (Phase 229)
4. mykatrain_settings.default_user_rank        ← legacy (Phase 225.8)
5. (ユーザー手動入力欄が空のまま)
```

ユーザーが解析設定画面で `5d` を設定していれば、LLM Coach がそれを自動取得する。

## 7. マッピング表（Phase 229 design）

`rank_to_skill_preset` の対応:

| Rank (内部 kyu_dan) | 棋力文字列 | preset |
|---------------------|-----------|--------|
| 0..4 | 30k / 25k / 20k / 15k / 11k | `relaxed` |
| 5..10 | 10k / 9k / 8k / 7k / 6k / 5k | `beginner` |
| 11..15 | 4k / 3k / 2k / 1k / 1d | `standard` |
| 16..19 | 2d / 3d / 4d / 5d | `advanced` |
| 20..23, 99 | 6d / 7d / 8d / 9d / 99d | `pro` |

注: これは `CoachMode` の境界とは微妙に異なる（DAN 帯が `1d` まで含む、ADVANCED 帯が `2d` から）。ユーザーの historical 感覚に合わせた preset 命名を優先。

## 8. 後方互換性

### 8.1 既存ユーザーへの影響

| 既存 config | Phase 229 後の挙動 |
|-------------|-------------------|
| `skill_preset: "standard"` (デフォルト) | 変化なし（preset override として尊重） |
| `skill_preset: "auto"` | UI から消えるが、config 読み込みは継続。`resolve_skill_preset` が `None` と同等扱い |
| `skill_preset: "beginner"` | 変化なし（preset override として尊重） |
| `player_rank` 未設定 | 新規デフォルト挙動: rank 空 → preset は `standard` にフォールバック |

### 8.2 新規 config キー

```json
{
  "general": {
    "skill_preset": "standard",   // resolved preset (auto-managed)
    "player_rank": "5k",          // NEW (Phase 229): primary user input
    "pv_filter_level": "auto"
  }
}
```

旧設定（`skill_preset` のみ）でも全機能動作。新規ユーザーは `player_rank` を設定することで UX が向上。

### 8.3 `auto` の扱い

`auto` 文字列は引き続き config に書けるが、UI 選択肢から消える。`resolve_skill_preset("auto", ...)` は `None` と同等扱い（rank → preset 推定にフォールバック）。

## 9. アーキテクチャ境界（重要）

### `katrain.common.rank` の制約

- `katrain.common` レイヤーは Kivy 非依存（既存ルール）
- **`katrain.common` は `katrain.core` を import しない**（既存ルール: `test_architecture.py::test_common_has_no_lazy_core_or_gui_imports`）
- このため `rank_to_skill_preset` は **`katrain.core.analysis.logic_skill` に配置**

### 依存方向

```
katrain.common.rank           ← 純粋データ + parse logic
        ↑
        │ (import OK)
        │
katrain.core.analysis.logic_skill  ← rank_to_skill_preset 配置
katrain.core.coach.master_db      ← legacy shims (_canonical_rank_key, _normalise_rank_str)
katrain.gui.features.llm_coach    ← resolve_rank_fallback_chain 配置
```

## 10. i18n キー（Phase 229 追加分）

| キー | jp msgstr | en msgstr |
|------|-----------|-----------|
| `mykatrain:settings:player_rank` | "棋力:" | "Rank:" |
| `mykatrain:settings:player_rank_example` | "例: 5k / 4d / 4段 / 5級 / 初段" | "e.g. 5k / 4d / 4段 / 5級 / 初段" |
| `mykatrain:settings:player_rank_inferred` | "現在: {preset}（{rank} より自動推定）" | "Currently: {preset} (auto-derived from {rank})" |
| `mykatrain:settings:player_rank_default` | "現在: {preset}（棋力未設定のデフォルト）" | "Currently: {preset} (default; no rank set)" |

## 11. 移行ガイド（既存ユーザー向け）

### 既存ユーザー（preset を直接選んでいた人）

設定 → 解析タブを開くと、棋力欄に `5d` のような値が表示される（既存 `skill_preset` から逆算できない場合は空欄）。推奨アクション:

1. 自分の棋力を `5k` / `4d` / `4段` のように入力
2. 下の "現在: ○○（5d より自動推定）" ラベルで結果を確認
3. 保存

### 既存 LLM Coach ユーザー

LLM Coach を開いた時の挙動:
- これまで通り Karte / SGF から rank を自動取得
- それがない場合、新設 `general/player_rank` から取得（**未設定なら `default_user_rank` にフォールバック**）
- 引き続き手動入力欄は active

## 12. テスト数推移

| ベースライン | + Phase 229-A | + Phase 229-B | + Phase 229-C | + Phase 229-D | 合計 |
|-------------|--------------|--------------|--------------|--------------|------|
| 5,418       | 5,512 (+94)  | 5,551 (+39)  | 5,555 (+4)   | 5,572 (+17)  | 5,572 |

(参考: ローカル環境では Kivy 不在のため 61 件 skip。CI で Kivy 有効なら 5,633 件程度。)

## 13. 関連 Phase

- **Phase 207-213**: `core/coach/master_db.py` 構築（CoachMode / ToneVoice）
- **Phase 225.6**: SGF BR/WR からの rank 抽出 + LLM Coach 棋力自動取得
- **Phase 225.8**: `mykatrain_settings.default_user_rank` 追加（LLM Coach フォールバック）
- **Phase 226-C (C1)**: 漢字段級サポート（`"10段"` → `"9d"` 補正）
- **Phase 229（本Phase）**: 棋力プリセット統合 + `general/player_rank` 新設

## 14. 残作業（Phase 230+ 候補）

- **Phase 230**: `core/study/active_review.py` の `GRADE_THRESHOLDS` を `SKILL_PRESETS.grade_thresholds` に統合（重複定義解消）
- **Phase 231**: Karte JSON の meta に `coach_mode` フィールド併存（保存時のモード情報保持）
- **Phase 232**: 「あなたの棋力は?」設定ウィザード（初心者向け 5 問クイズ）
- **Phase 233**: ライブ棋力推定（プレイ中の loss シグナルから `player_rank` を動的更新）