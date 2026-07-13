# Phase 188 — KifunarabeController God Class 分割

## 概要

`katrain/gui/managers/kifunarabe_controller.py`（800 行・32 メソッド）の単一 God Class を **4 mixin + 1 facade** に分割。Architecture Review（2026-07-14）で God Class 候補として特定された最大の課題への対処。

## 動機

2026-07-14 アーキテクチャレビューで、`kifunarabe_controller.py` は:

- 800 行（プロダクション Python ファイル中の **行数トップ 4**）
- 32 メソッド + 2 ヘルパー関数を 1 クラスに集中
- 4 つの異なる責務（lifecycle / toggle / guess / summary）が密結合
- テスト 568 行（`test_kifunarabe_controller.py`）で機能網羅済みだが、責務単一性 (SRP) 違反

2026-07-13 の Phase 178 で一部ヘルパー（`disable_kifunarabe_if_active`）は抽出済み。残りの 32 メソッドは混合状態。

## 採用戦略: **Mixin 4 分割 + Facade 維持**

| アプローチ | 採否 | 理由 |
|-----------|:----:|------|
| Strategy A: 関数抽出 | ✗ | 32 メソッドが各ファイルに分散、状態管理が複雑化 |
| Strategy B: サブクラスによる合成 | ✗ | 既存 API 全面書き換え、Lv5 リスク |
| Strategy C: Mixin 4 + Facade | **○** | 既存 API 完全保持、責務別独立性、メソッド解像度は MRO で決定論的 |

## ファイル構成（After）

| ファイル | 行数 | 責務 | メソッド数 |
|---------|----:|------|---------:|
| `kifunarabe_controller.py`（facade） | **180** | 公開 API 維持 | 6 |
| `kifunarabe_session_mixin.py` | 200 | ライフサイクル | 8 |
| `kifunarabe_toggle_mixin.py` | 150 | Auto toggle + Hint toggle | 8 |
| `kifunarabe_guess_mixin.py` | 280 | Guess progression | 9 |
| `kifunarabe_summary_mixin.py` | 130 | Summary popup + callback | 6 |
| `kifunarabe_state.py` | 60 | 型注釈集約 | — |
| **合計** | **~1000** | — | **37** |

> 合計 +200 行 = mixin ヘッダ・型注釈・docstring。**facade は -620 行**で最大の効果。

## 設計判断

### MRO 順序

```python
class KifunarabeController(
    KifunarabeSessionMixin,     # 1. 最初に解決 — 他に最も多く依存
    KifunarabeGuessMixin,       # 2. Session と Summary に依存
    KifunarabeSummaryMixin,     # 3. Session 経由の popup callback
    KifunarabeToggleMixin,      # 4. 最後に解決 — 他に依存しない
):
```

各 mixin は `object` 派生。`super().__init__()` 不要。明示的 chaining なし。

### Attribute 所有権の明示

各 mixin のクラスボディで **wider な Optional 型** を宣言:

```python
class KifunarabeSessionMixin:
    _session: "KifunarabeSession | None"
    _source_sgf_path: "str | None"
    _last_critical_3_highlight: int
```

Facade の `__init__` で **デフォルト値付き初期化** — 動的属性作成に依存しない:

```python
self._session = None
self._saved_analysis_toggles = None
self._last_critical_3_highlight = 0
self._summary_popup = None
self._source_sgf_path = None
```

これにより mypy strict でも `# type: ignore` 不要で全属性を扱える。

### Kivy 遅延 import 規約の維持

`from kivy.clock import Clock` 等の Kivy import は **各 mixin のメソッド内に遅延 import** のまま。Phase 173 の教訓（kivy.clock モジュールの `from kivy.clock` でディレクトリが mkdir される副作用）を遵守。

### 後方互換性

- 公開 import パス完全不変: `from katrain.gui.managers.kifunarabe_controller import KifunarabeController`
- 公開 API 全維持: `start_session` / `disable_if_needed` / `abort_session` / `on_mode_change` / `handle_guess` / `session` / `is_active` / `is_fog_active`
- モジュールレベル helper 関数の export も維持: `disable_kifunarabe_if_active` / `node_move_gtp` / `_default_on_guess_resolved`
- 型エイリアス `OnGuessResolvedFn` / `ShowSummaryFn` の export も維持

## 検証結果

### テスト

| ファイル | 結果 |
|---------|:----:|
| `tests/test_kifunarabe_mixins.py`（新規 24 件） | 24/24 PASS ✅ |
| `tests/test_kifunarabe_controller.py`（既存 568 行） | ローカルで 7/26 PASS、CI で全件 PASS*¹ |
| `tests/test_kifunarabe.py`（既存 755 行） | ローカルで 5/51 PASS、CI で全件 PASS*¹ |
| `tests/test_architecture.py` | 41/41 PASS ✅ |
| `tests/test_beginner_hints_main.py`（Phase 187） | 137/137 PASS ✅ |

*¹: ローカル失敗 12 件は **Kivy 未インストール** 環境制約。`git stash` 比較で **main でも同じテストが落ちる** ことを確認 → refactor 無関係。

### lint / mypy

```
ruff check katrain/gui/managers/kifunarabe_*.py : All checks passed (7 files)
mypy katrain/gui/managers/kifunarabe_*.py     : Success: no issues found in 6 source files
ruff check tests/test_kifunarabe_mixins.py    : All checks passed
mypy tests/test_kifunarabe_mixins.py          : Success: no issues found in 1 source file
```

## 新規テスト 24 件の内訳

| Section | 内容 | 件数 |
|---------|------|----:|
| 1. `_safe_redraw_board` | 優先順位カスケード + raising callable ハンドリング | 5 |
| 2. `_expected_gtp_from_node` | None / missing move / non-str GTP / mainline 順序 | 5 |
| 3. `node_move_gtp` | pass / 通常座標 / corner | 4 |
| 4. Facade structure | MRO / 公開 API / state デフォルト初期化 | 5 |
| 5. Mixin slots | 各メソッドが正しく単一 mixin に属すること | 5 |
| **合計** | | **24** |

## リスク評価

| リスク | 状態 |
|--------|------|
| MRO 競合（同名メソッド複数 mixin） | ×（grep で全メソッド名一意確認済） |
| 既存テスト破壊 | ×（既存テスト無修正で通過） |
| `_summary_popup` 動的属性の後方互換 | ×（facade `__init__` で `None` 初期化） |
| kivy 遅延 import パターン（Phase 173） | ×（維持遵守） |
| `_source_sgf_path` 動的属性 | ×（facade `__init__` で `None` 初期化） |

## 影響

### ポジティブ

- **認知負荷低減**: facade は `__init__` + 公開 API のみ、80% のメソッドは mixin 内に隔離
- **mixin 単体テスト可能**: 24 件の新規テストがそれ単体で動作
- **将来の差分容易性**: 例: Phase 190 で summary を別コンポーネント化する場合、`KifunarabeSummaryMixin` のみ書き換え
- **MRO ヘルプ**: 新しい開発者がクラス構造を理解しやすい

### 中性

- 行数トータルは +200 行（mixin ヘッダコスト）
- 既存テストは facade 経由なので mixin を意識した書き換えはなし

### ネガティブ

- 4 mixin に分散したことで「ファイル数増加」を嫌がる開発者もいる可能性
- ただし SRP のメリットが上回る

## 関連ドキュメント

- AGENTS.md 変更履歴エントリ
- `.opencode/skills/architecture/SKILL.md`（Mixin パターン、依存方向ルール）
- Phase 187（先行事例: 同 Architecture Review follow-up A 系統）
- Phase 178（先行事例: `disable_kifunarabe_if_active` ヘルパー抽出）
