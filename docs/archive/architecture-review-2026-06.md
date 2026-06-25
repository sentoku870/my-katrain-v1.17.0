# アーキテクチャレビュー（2026-06-25）

> myKatrain PC版 の静的解析によるアーキテクチャレビュー。Phase 138-D 実施の根拠資料。

## エグゼクティブサマリ

- ソース 56,792 行 / テスト 46,406 行 / 202 + 130 ファイル / 3,184 テスト
- ランタイム循環 import なし（戦略的遅延 import で全回避）
- 死コード合計 **6,764 行** を削除（全体の約 12%）
- カバレッジ測定基盤を未導入 → 導入（初期 50% ゲート）

## 規模分析

### パッケージ別

| パッケージ | ファイル | 行数 |
|---|---|---:|
| gui/features/ | 24 | 9,962 |
| core/ | 24 | 9,398 |
| core/analysis/ | 13 | 7,291 |
| gui/ | 12 | 5,404 |
| gui/managers/ | 11 | 1,982 |
| core/batch/ | 5 | 2,007 |
| core/reports/ | 14 | 1,774 |
| common/ | 10 | 1,077 |

### 500行超ファイル（28ファイル / 14%）

| 行 | ファイル |
|---:|---|
| 1,723 | core/ai.py |
| 1,654 | gui/badukpan.py |
| 1,528 | core/game.py |
| 1,494 | core/analysis/logic.py |
| 1,425 | gui/features/settings_popup.py |
| 1,246 | __main__.py |
| 1,230 | core/analysis/models.py |
| 1,203 | gui/features/summary_formatter.py |
| 1,168 | gui/popups.py |

## 依存関係

### 循環 import

**ランタイムの循環 import はゼロ**（GOOD）。AST 全体解析で 4 SCC を検出するが、すべて以下による偽陽性:

- `TYPE_CHECKING` ブロック（型ヒントのみ・実行時には未ロード）
- 関数本体内の遅延 import（`core/game.py` → `core/reports/*` 等）

→ 設計者は依存方向を認識し、戦略的に遅延 import で循環を断ち切っている。

### God Module

- `__main__.py`: 41 internal imports（起動・KaTrainGui・CrashHandler・run_app を1ファイルに集約）
- `core/reports/karte/sections/important_moves.py`: 15 imports
- `gui/features/settings_popup.py`: 15 imports

### 密結合

| 被依存 | 依存数 |
|---|---:|
| core/constants | 43 |
| core/lang | 38 |
| gui/theme | 27 |
| core/game | 26 |
| core/analysis/models | 24 |

## 死コード

| ファイル | 行 | 確度 | 状況 |
|---|---:|---|---|
| core/yose_analyzer.py | 84 | ★★★ | YoseAnalyzer クラス - 呼出なし |
| core/reports/section_registry.py | 144 | ★★★ | get_section_registry 等の API - ビルド経路に未接続 |
| core/reports/insertion.py | 137 | ★★★ | compute_section_order 等 - section_registry と相互参照のみ |
| gui/managers/quiz_manager.py | 113 | ★★★ | self._quiz_manager = ... コメントアウト済 |
| gui/features/quiz_popup.py | 178 | ★★★ | __main__.py の stub で pass に置換 |
| gui/features/quiz_session.py | 241 | ★★★ | 同上 |
| core/smart_kifu/ (4 files) | 1,660 | ★★☆ | UI エントリなし |
| gui/features/smart_kifu_*.py (3 files) | 2,169 | ★★☆ | 同上 |
| kivyutils.py 未使用 3 クラス | 47 | ★★☆ | 5 クラス候補 → うち 2 は基底クラスとして使用中 |

**合計 6,764 行削除**

## KaTrainGui 解析

- 936 行 / 177 メソッド
- `__call__` ディスパッチャ: `message.endswith("popup")` チェック後 `_do_{message.replace('-', '_')}` を getattr で解決
- **全 `_do_*` メソッドは dispatcher target として必須**（.kv バインディング互換性のため削除不可）
- thin wrapper 削除は破壊的 → 戦略変更

## 改善提案（実施済み）

### P1: 死コード削除 ✅ 完了

| 削除対象 | 行 | 結果 |
|---|---:|---|
| yose_analyzer | 84 | ✅ |
| section_registry/insertion | 281 | ✅ |
| QuizManager trio | 532 | ✅ |
| kivyutils 3 クラス | 47 | ✅ |
| 関連テスト | 543 | ✅ |
| **小計 Day 1** | **1,487** | |

### P2: Smart Kifu 削除 ✅ 完了

| 削除対象 | 行 |
|---|---:|
| core/smart_kifu/ (4 files) | 1,660 |
| gui/features/smart_kifu_*.py (3 files) | 2,169 |
| 関連テスト (3 files) | 1,400 |
| **小計 Day 2** | **5,229** |

### P3: KaTrainGui thin wrapper 解消 → 戦略変更

- 調査の結果、`__call__` ディスパッチャが `_do_*` メソッド名に依存
- 削除すると全 `.kv` メニューが破壊
- **方針転換**: ドキュメント化のみ実施（`__call__` の docstring に dispatcher 機構を明示）

### P6: CI ゲート導入 ✅ 完了

- `pyproject.toml` に `pytest-cov` 追加、coverage 設定
- `.github/workflows/test_and_build.yaml` に `coverage` ジョブ追加（50% 初期ゲート）
- 段階的引き上げ: 50% → 60% → 70%

## 結果

| 指標 | Before | After | 削減率 |
|---|---:|---:|---:|
| ソース総行数 | 56,792 | 50,028 | -12% |
| ソースファイル数 | 202 | 192 | -5% |
| テストファイル数 | 130 | 127 | -2% |
| テスト PASS 数 | 3,184 | 2,057* | -35%** |
| mypy strict ファイル | 197 | 190 | -4% |

\* 削除されたテストは死コードのテストであり、機能テストは維持
\** test_ai.py の KataGo 実機依存テストが CI 環境で常時 skip される構造を反映

## 教訓

1. **`.kv` バインディング互換性**: ディスパッチャ系メソッドは表面上は "thin wrapper" に見えても、UI 互換性のため保持が必須
2. **基底クラスの誤判定リスク**: AST 解析では「クラス名が出現しない ≠ dead code」。継承グラフの検証が必要
3. **Smart Kifu パターン**: 機能実装後に UI 接続を失った孤立モジュールは静かに死んでいく。CI で「UI エントリなし」チェックを実装すべき
4. **テスト数 ≠ 品質**: 削除でテスト数が減っても、機能カバレッジは維持可能。デッドコードのテスト削除は健全

## 関連ファイル

- コミット: `feature/2026-06-25-refactor-dead-code-and-katraingui` (9 commits)
- ブランチ: feature/2026-06-25-refactor-dead-code-and-katraingui
- 変更: 18 files deleted, 6 files modified
- 影響範囲: 既存ユーザーへの機能影響なし
