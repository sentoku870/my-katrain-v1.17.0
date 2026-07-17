# Phase 246: 候補手フィルター 包括改善 (Lv3)

**実装日:** 2026-07-17
**種別:** UX 可視化 + 盤面 UX + 堅牢性 + ロジック拡張 + ドキュメント統合

---

## 1. 概要

mykatrain の **候補手フィルター (PV filter)** は KataGo 解析結果から
盤面に表示する候補手を絞り込む仕組み (Phase 11 で実装)。本フェーズで
は、ヒト視点での UX 課題 (「今どのレベルで動いてるのか分からない」)、
実データ由来の堅牢性問題 (`pointsLost=None` で TypeError)、9路/13路
対応漏れ、pro プリセット差別化不足など、**20 件の課題**を一括で改修。

## 2. サブフェーズ索引

| Phase | 主旨 | 主要変更 | 規模 |
|-------|------|---------|------|
| **246-A** | 設定 UI 可視化 | AUTO レベル表示 / 横幅可変化 | Lv2 |
| **246-B** | 盤面 UX | 視点ラベル (次手 = B/W) / マーカー凡例 | Lv2 |
| **246-C** | 堅牢性 | 境界値テスト / best_move.pv クリップ / 二次ソート | Lv2 |
| **246-D** | ロジック拡張 | expert プリセット / board_size 連動 / loss_metric 切替 | Lv3 |
| **246-E** | ドキュメント | 仕様書 / usage-guide / config default | Lv1 |

## 3. 改善項目一覧 (20 件)

### 🔴 Priority High (H 系列) — 機能 / バグ

| ID | 項目 | Phase | 状態 |
|----|------|-------|------|
| H1 | pointsLost の「次手視点」を GUI で明示 (視点ウォーターマーク) | 246-B | ✅ |
| H2 | AUTO モード時 effective level + max_candidates を表示 | 246-A | ✅ |
| H3 | 現在のノードで N → M 候補のライブプレビュー | 246-E | 🟡 (deferred) |
| H4 | 棋譜並べモード中は filter 自動 OFF + 設定に説明追加 | 246-D | ✅ |
| H5 | 数値境界値テストの充実 (None / 欠損 / 重複 / NaN / 0件 / 1件) | 246-C | ✅ |

### 🟡 Priority Medium (M 系列) — UX / 設定妥当性

| ID | 項目 | Phase | 状態 |
|----|------|-------|------|
| M1 | `max_pv_length` の board_size 連動 (9路 → 0.47x, 13路 → 0.68x) | 246-D | ✅ |
| M2 | pro プリセット差別化 (`expert`: max_cand=3, max_loss=0.5, max_pv=4) | 246-D | ✅ |
| M3 | sort 重み (pointsLost + pv_length composite) | 246-D | 🟡 (TODO) |
| M4 | low_visits との統合凡例 (色 / サイズ / 枠線の意味) | 246-B | ✅ |
| M5 | best_move.pv 異常長クリップ (30 手上限、`draw_pv` のスキップコスト回避) | 246-C | ✅ |
| M6 | level 入力の `.lower().strip()` 正規化 | 246-A | ✅ |
| M7 | 二次ソートキー (order → pointsLost → -visits) で重複 order を決定論化 | 246-C | ✅ |
| M8 | 設定 UI の横幅可変化 (size_hint_x ベース) | 246-A | ✅ |

### 🟢 Priority Low (L 系列) — 将来検討

| ID | 項目 | Phase | 状態 |
|----|------|-------|------|
| L1 | `loss_metric`: `pointsLost` / `relativePointsLost` 切替 | 246-D | ✅ |
| L2 | 統合仕様書 (本ファイル) | 246-E | ✅ |
| L3 | `docs/usage-guide.md` に候補手フィルター節追加 | 246-E | ✅ |
| L4 | `config.json` の `general.pv_filter_level` デフォルト明記 | 246-E | ✅ |
| L5 | 毎フレームの `pv_filter_config` 解決キャッシュ | 246-E | 🟡 (deferred) |
| L6 | 候補手 N → M の position-aware live preview | 246-E | 🟡 (deferred) |
| L7 | `get_pv_filter_config` の API 統一 (`player_rank` 直渡し) | 246-E | 🟡 (deferred) |

凡例: ✅ 実装 / 🟡 deferred (将来課題 or 別フェーズで着手)

## 4. コア API 変更点

### 4.1 新規シンボル (`katrain.core.analysis`)

```python
@dataclass(frozen=True)
class PVFilterDisplayInfo:
    """UI-facing summary of the effective PV filter level (H2)."""
    effective_level: str  # "off" / "weak" / "medium" / "strong" / "expert"
    max_candidates: int   # 0 = unlimited (off)
    is_auto: bool         # True if user picked auto
    resolved_preset: str | None  # skill_preset that auto mapped to


def get_effective_pv_filter_info(
    pv_filter_level: str | None,
    player_rank: str | None = "",
) -> PVFilterDisplayInfo:
    """Resolve the display-effective level for the settings UI."""


PV_ANIMATION_MAX_STEPS: int = 30


def clip_pv_for_animation(pv: Any) -> list[str]:
    """Clip a PV sequence to PV_ANIMATION_MAX_STEPS (M5)."""
```

### 4.2 変更シグネチャ

```python
# Before
def get_pv_filter_config(level: str, skill_preset: str = ...) -> PVFilterConfig | None

# After (Phase 246-D M1)
def get_pv_filter_config(
    level: str,
    skill_preset: str = DEFAULT_SKILL_PRESET,
    board_size: int | None = None,  # ← 新規 (M1)
) -> PVFilterConfig | None
```

### 4.3 PVFilterConfig 拡張

```python
@dataclass(frozen=True)
class PVFilterConfig:
    max_candidates: int
    max_points_lost: float
    max_pv_length: int
    loss_metric: str = "pointsLost"  # ← Phase 246-D L1 で追加
```

## 5. PV フィルタープリセット (4 段階)

| レベル | max_candidates | max_points_lost | max_pv_length | 用途 |
|--------|----------------|------------------|----------------|------|
| `weak` | 15 | 4.0 | 15 | 激甘 / 甘口 (relaxed / beginner) |
| `medium` | 8 | 2.0 | 10 | 標準 (standard) |
| `strong` | 4 | 1.0 | 6 | 辛口 (advanced) |
| `expert` | 3 | 0.5 | 4 | 激辛 (pro) — Phase 246-D M2 で追加 |

AUTO マッピング (Phase 246-D M2 で `pro` が `expert` にリマップ):

```
relaxed/beginner → weak
standard         → medium
advanced         → strong
pro              → expert  ← 新規
```

`OFF` 設定時は `None` が返り、フィルタは適用されない (全候補手表示)。

## 6. 9路 / 13路 対応 (M1)

`max_pv_length` を board_size に比例して線形縮小:

| board_size | strong.max_pv_length | expert.max_pv_length |
|------------|------------------------|------------------------|
| 19路 | 6 | 4 |
| 13路 | 4 (6 * 13/19) | 3 (4 * 13/19) |
| 9路 | 3 (6 * 9/19) | 2 (4 * 9/19) |
| 5路 | 2 (6 * 5/19) | 1 (4 * 5/19) |

`max_candidates` と `max_points_lost` は盤サイズに依存しない (board-agnostic)。
最小 1 手でクリップ (0 にはしない)。

## 7. 堅牢性改善 (H5)

`filter_candidates_by_pv_complexity` の防御的コントラクト:

- `pointsLost` / `pv` が `None` の場合 `0.0` / `[]` として扱う
- `None <= float` の TypeError を回避
- 同一 `order` 値の候補は `pointsLost` 昇順 → `visits` 降順で決定論ソート (M7)
- 0 件候補は `[]` を即返却
- 1 件候補はそのまま返却
- 9e18 のような極大 `visits` でも `-visits` ソートキー化で安全

## 8. 棋譜並べ (kifunarabe) モードのバイパス (H4)

`prepare_hint_moves` 内の `if hint_moves and not in_kifu:` ガードで
棋譜並べモード中は filter を完全に skip。設定ポップアップに以下の
ノートを追加 (jp/en):

- jp: ※ 棋譜並べモード中は自動OFF（正解と AI 候補が必ず全件表示されます）
- en: Note: disabled in Kifunarabe (棋譜並べ) mode — all options are always shown.

AST ベースの静的テスト (`test_pv_filter_kifunarabe_skip.py`) で
リファクタ時の取りこぼしを検出。

## 9. テストカバレッジ

新規追加: **50+ 件** のテスト

| ファイル | 件数 | 主旨 |
|---------|------|------|
| `test_pv_filter.py` | 拡張 (50+ 件) | helper / 境界値 / 二次ソート / loss_metric / expert / board_size |
| `test_pv_filter_status_label.py` | 9 件 | 設定 UI の status label format 関数 |
| `test_pv_filter_perspective_watermark.py` | 6 件 | 視点ウォーターマーク / 凡例の i18n 検証 |
| `test_pv_animation_clip.py` | 9 件 | best_move.pv クリップヘルパー |
| `test_pv_filter_kifunarabe_skip.py` | 4 件 | AST ベースのコントラクトチェック |

**全 129 件 pass** (Phase 246 完了時点)。

## 10. ファイル変更サマリ

```
katrain/core/analysis/
  __init__.py              (export 追加)
  logic.py                 (re-export)
  logic_pv.py              (新ヘルパー + M1 + H5 + M7)
  models/difficulty.py     (M2: expert preset)

katrain/gui/
  badukpan_hints.py        (H1: 視点ウォーターマーク + M5: clip 呼び出し)
  features/settings_popup_tabs/analysis_tab.py  (H2 + M4 + M8 + H4 UI)

katrain/i18n/locales/{jp,en}/LC_MESSAGES/katrain.{po,mo}  (新規 5 キー)

katrain/config.json        (L4: pv_filter_level デフォルト)

tests/                     (新規 5 ファイル + 既存拡張)
docs/archive/specs-implemented/phase246-candidate-filter-improvements.md  (本ファイル)
docs/usage-guide.md        (L3: 候補手フィルター節追加)
```

## 11. 後方互換性

- 既存 `general/pv_filter_level` 設定値はそのまま動作
- `PVFilterConfig` の `loss_metric` フィールドはデフォルト `"pointsLost"`
  (Phase 11 からの挙動を保持)
- `get_pv_filter_config` の `board_size=None` は canonical 設定
  (backward compatible)
- `pro` → `expert` リマップは AUTO モードのみ。explicit `pv_filter_level="strong"`
  選択は変化なし

## 12. 既知の制約 / 将来課題

- **L5 キャッシュ**: 毎フレームの `pv_filter_config` 解決 (config 3 回 lookup)
  はホットパス。同一 analysis 内キャッシュは将来改善。
- **L6 live preview**: 候補手 N → M の position-aware 表示は
  controls panel 側の改修が必要 (Phase 246-E でスコープ外)。
- **L7 API 統一**: `get_pv_filter_config` に `player_rank` を直渡しする
  オプション引数追加は将来改善 (現在 `resolve_skill_preset` 経由で呼び出し元で解決)。
- **M3 composite sort**: 重み付き composite (pointsLost + α * pv_length)
  は TODO コメントで残置。
- **H3 live preview**: ノード変更検知の hook 必要、別フェーズで着手。
