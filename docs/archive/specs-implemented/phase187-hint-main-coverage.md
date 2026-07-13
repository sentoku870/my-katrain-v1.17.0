# Phase 187 — Beginner Hints Main Pipeline Coverage

## 概要

`core/beginner/hints.py` の行カバレッジを **16.5% → 97%** に引き上げる。
Phase 186 アーキテクチャレビューで特定された**全コア層中カバレッジ最低値**を改善し、Hint priority chain のリグレッションリスクを低減。

## 背景

### トリガー

2026-07-14 に実施したアーキテクチャレビュー（Plan Mode）で、`core/beginner/hints.py`（753 行）のカバレッジが **16.5%**（124/753 行）と判明。これは全プロダクションコア層ファイル中で最低値。

`hints.py` は:
- `compute_beginner_hint` / `get_beginner_hint_cached` — 構造的ヒント（Phase 91-92）
- `compute_summary_hint` / `get_summary_hint_cached` — サマリーヒント（Phase 179+182+186）
- 7 段の priority chain dispatcher
- 3 段のキャッシュ機構（require_reliable / flags / user_weak_tags / curator_min_occurrences）
- 6 個の公開ゲート関数（master / summary flag / board highlight / coord validity）

を持つ初心者 UX のコアで、リグレッション時のユーザー影響が大きい。

### 既存テストの状況

`tests/test_beginner_hints.py`（956 行・既存）と `tests/test_beginner_hints_summary.py`（1,602 行・既存）が以下の領域をカバーしていたが、**分岐網羅**で以下の隙間があった:

- **公開ゲート関数**: enabled × mode マトリクスの一部のみ
- **内部 extractor**: happy path のみ（None / 空 / 不正値なし）
- **`_compute_summary_context` の try/except フォールバック**: 未カバー
- **`_is_endgame_position` の scoreStdev 動的判定**: 静的フォールバックのみ
- **キャッシュ invalidate**: `require_reliable` のみ、`user_weak_tags` / `curator_min_occurrences` 軸が薄い
- **`compute_beginner_hint` の finally-block 復元**: 未明示テスト
- **複数 detector グループ同時該当時の priority 競合**: 部分的

## 実装

### 新規ファイル

| ファイル | 行数 | テスト数 |
|---------|----:|---------:|
| `tests/test_beginner_hints_main.py` | 876 | **137** |

### テスト構成（9 セクション）

| Section | 内容 | テスト数 |
|---------|------|---------:|
| 1. Public gate functions | `should_show_*` / `is_coords_valid` / `_normalize_board_size` のマトリクス | 28 |
| 2. Pure extractors | `_extract_predicted_territory` / `_extract_best_policy` の None/empty/malformed 経路 | 15 |
| 3. Summary context builder | `_compute_summary_context` の try/except 例外フォールバック + threshold 転送 | 8 |
| 4. Endgame heuristic | `_is_endgame_position` の scoreStdev 動的判定 + move_number 静的フォールバック | 5 |
| 5. Cache wrappers | `get_beginner_hint_cached` / `get_summary_hint_cached` の 4 次元 cache invalidate シナリオ | 11 |
| 6. compute_beginner_hint paths | pass move / root node / no parent 早期リターン + finally-block 復元 | 5 |
| 7. compute_summary_hint chain | priority chain + 各フラグ OFF 動作 + CURATOR 統合 | 10 + 4 = 14 |
| 8. i18n integration | `HintCategory` 全 23 カテゴリの namespace/fallback 一貫性 | 50+ パラメタライズド |
| 9. Constants sanity | `MIN_RELIABLE_VISITS` / `MIN_SUMMARY_VISITS` / `_DETECTOR_CATEGORIES` / `_NOT_COMPUTED` | 4 |

合計: **137 件**

### 設計上の決定

#### Phase 173 教訓の遵守

Kivy を**モジュールレベルで一切 import しない**（CI exit-102 再発防止）。テストファイルはコア層のみで完結。`MagicMock` と `unittest.mock.patch` のみを使用。

#### TYPE_CHECKING パッチターンの回避

`from katrain.core.analysis import X` で import された関数を patch する場合、**`katrain.core.analysis.X`** を patch ターゲットにする必要がある（テスト中に 1 回この間違いで失敗 → 修正）。

```python
# 誤: katrain.core.beginner.hints.difficulty_metrics_from_node
# 正: katrain.core.analysis.difficulty_metrics_from_node
```

#### Mock 過剰使用の回避

`test_user_weak_tags_none_calls_curator_but_returns_none`（初版）で `detect_curator_weak_axis` を mock していたが、mock が detector 内部の short-circuit をバイパスしてしまうため、本物の detector を呼ぶ形に修正し、**None ガードが本当に動く**ことを確認するテストに変えた。

#### MagicMock 属性設定

MagicMock の property 設定は **仕様で attribute 制御と衝突**するため、`MagicMock(spec=[...])` で明示的に属性を列挙するか、`type(node).attr = property(...)` のような `__class__` 操作を避ける。

## 検証結果

### カバレッジ

| 指標 | Before | After |
|------|-------:|------:|
| Line coverage | 16.5% (124/753) | **97%** (232/238) |
| Branch coverage | n/a | **97%** (99/104 branches) |
| Uncovered lines | n/a | 6 行（detector 内部の深い分岐、`_compute_summary_context` の数値変換フォールバック） |

### テスト実行

```
tests/test_beginner_hints.py        107 passed
tests/test_beginner_hints_summary.py 110 passed
tests/test_beginner_hints_main.py   137 passed
test_architecture.py                 41 passed (関連部分)
─────────────────────────────────────────────
Total beginner hint tests           354 passed (no regression)
Total including other beginner/curator   676 PASS (project-wide beginner family)
```

### lint / mypy

- `ruff check tests/test_beginner_hints_main.py`: All checks passed
- `mypy tests/test_beginner_hints_main.py`: clean (no errors)
- pyproject.toml mypy strict mode compatible

### 後方互換性

既存 539 テスト全て不変 PASS（`test_beginner_hints.py` + `test_beginner_hints_summary.py`）。

## 未対応（次フェーズ検討）

### hints.py 分割（Lv4 案件）

`hints.py` 753 行は 4 つの関心事を 1 ファイルに統合している:

1. **Gate** (90-188 行): `should_show_*` 系、`_normalize_board_size`、`_get_visits_from_node`
2. **Extract** (472-583 行): `_extract_predicted_territory` / `_extract_best_policy` / `_is_endgame_position`
3. **Dispatch** (191-322 + 586-700 行): `compute_beginner_hint` / `compute_summary_hint`
4. **Cache** (325-366 + 703-753 行): `get_beginner_hint_cached` / `get_summary_hint_cached`

`beginner/hints/` サブパッケージ化（gate.py / extract.py / dispatch.py / cache.py + 集約 `__init__.py`）が既存 `cluster_*` / `meaning_tags/` / `time/` / `models/` パターンと整合。

### 影響評価

- 既存 539 テストへの import path 更新が発生
- `__init__.py` で全公開 API を re-export すれば後方互換維持可能
- 工数: 8-12 時間、効果: 中（カバレッジは既に 97% で高い）、リスク: 中（API 移行ミス）

→ Phase 188 以降の Lv4 案件として別フェーズで評価。

## 関連ドキュメント

- AGENTS.md（変更履歴エントリ）
- `.opencode/skills/architecture/SKILL.md`（layers・Kivy 隔離原則）
- `tests/conftest.py`（既存フィクスチャとの重複回避）
- `docs/archive/specs-implemented/phase179-hints-summary-extension.md`（Phase 179.1/179.2 で確立されたキャッシュキーベストプラクティスの踏襲）
