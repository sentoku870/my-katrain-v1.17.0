# Phase 20: Guardrails + UI Polish & Cleanup 計画

> **作成日**: 2026-01-16
> **完了日**: 2026-01-16
> **ステータス**: ✅ 完了
> **修正レベル**: Lv3（複数ファイル、構造変更含む）
> **前提**: Phase 19完了（879テストパス）
> **成果**: PR #131-135マージ、許可リスト6→1エントリに削減

---

## サマリー

Phase 20は「Guardrails + UI Polish & Cleanup」をテーマに、Phase 19リファクタリングの成果を保護し、長期的なUI保守コストを削減する。主な目標は：(1) core→gui/Kivy依存の検出・防止テストの強化、(2) 発見されたcore内Kivy依存の解消、(3) KVファイルの整理とスタイル統一、(4) 開発ルールの文書化。新機能は追加せず、テスト基盤とコード品質の改善に集中する。

---

## 調査結果

### 1. 現在のアーキテクチャテスト状況

**tests/test_architecture.py** (566行):
- ✅ `test_no_core_imports_gui()`: core/がgui/をインポートしないことを検証
- ✅ `test_common_has_no_core_or_gui_imports()`: common/の独立性を検証
- ✅ `test_common_no_side_effects()`: common/に副作用がないことを検証
- ✅ TYPE_CHECKING, typing as t エイリアス対応済み
- ✅ 相対インポート解決対応済み
- ❌ **Kivyインポート検出テストなし** ← 重大な欠落

### 2. 発見されたcore内Kivy依存（4ファイル、5箇所）

| ファイル | 行 | インポート | 重大度 | 用途 |
|----------|-----|-----------|--------|------|
| `core/lang.py` | 5 | `from kivy._event import Observable` | HIGH | Lang classがObservable継承 |
| `core/lang.py` | 60 | `from katrain.gui.kivyutils import clear_texture_caches` | MED | 言語切替時のキャッシュクリア（遅延/guarded） |
| `core/base_katrain.py` | 5-6 | `from kivy import Config`<br>`from kivy.storage.jsonstore import JsonStore` | HIGH | 設定読み込み |
| `core/engine.py` | 13 | `from kivy.utils import platform as kivy_platform` | MED | OS判定 |
| `core/game.py` | 9 | `from kivy.clock import Clock` | HIGH | 通知スケジューリング |

**重要**: `test_no_core_imports_gui()`はgui依存は検出するが、**Kivy直接インポートを検出しない**

### 3. KVファイル現状

| ファイル | 行数 | 内容 |
|----------|------|------|
| `katrain/gui.kv` | 1,279 | メインUI（52ウィジェットルール） |
| `katrain/popups.kv` | 918 | ダイアログ（25ウィジェットルール） |
| widgets内インラインKV | ~470 | 5ファイルに分散 |
| **合計** | ~2,667 | |

**問題点**:
- ハードコード値（padding: 4, font_size: sp(16)など）が20箇所以上
- ボタンバリエーション爆発（8種類の類似クラス）
- 入力フィールドクラス重複（5種類の類似定義）
- ConfigPopupが200行超の巨大定義

### 4. ゴールデンテスト現状

**tests/conftest.py** に基盤あり:
- `normalize_output()`: タイムスタンプ、パス、float精度の正規化
- `--update-goldens` フラグ対応
- `tests/fixtures/golden/summary_output.txt` 存在

**欠落**:
- カルテ出力のゴールデンテストが不完全（SGFからの実際のテストなし）

### 5. CLAUDE.md 現状

- 依存方向図はあるが、**明示的なルールとして文書化されていない**
- `.claude/rules/` に `05-architecture.md` がない

---

## 調査時に解決した重要な質問

| 質問 | 結論 |
|------|------|
| coreがKivyをインポートする正当な理由はあるか？ | **NO** - 全て代替可能。Observable→callback、Clock→threading、platform→sys.platform |
| 既存テストがKivy依存を検出しているか？ | **NO** - gui依存のみ検出、Kivy直接インポートは見逃されている |
| common/パッケージの役割は適切か？ | **YES** - 循環依存解消用の共有定数置き場として正しく機能 |
| ゴールデンテストは機能しているか？ | **部分的** - 基盤はあるがカルテ出力の実SGFテストがない |
| KVファイルのコンポーネント化は進んでいるか？ | **MEDIUM** - Mixinパターンはあるが、モノリシックな定義が多い |

---

## 提案するワークアイテム（優先度順）

### A-1: Kivyインポート禁止テスト追加 [優先度: HIGH, 複雑度: S]

**目標**: coreからKivy/KivyMDへの直接依存を検出・防止

**アプローチ**:
- `tests/test_architecture.py` に `TestKivyIsolation` クラス追加
- 禁止モジュールリスト: kivy, kivymd, kivy.clock, kivy.storage等
- 暫定許可リスト（TEMPORARY_ALLOWED）で既存違反を一時許可
- A-2完了後に許可リストを空に

**対象ファイル**:
- `tests/test_architecture.py` (更新)

**受入条件**:
- テストが現在のKivy依存を検出
- 新規Kivy依存追加時にCIで失敗

---

### A-2: Core内Kivy依存の解消 [優先度: HIGH, 複雑度: L]

**目標**: 5箇所のKivy依存を標準ライブラリまたはcallbackパターンに置換

**サブタスク**:

| ID | ファイル | 変更内容 | 複雑度 |
|----|----------|----------|--------|
| A-2a | engine.py | `kivy.utils.platform` → `sys.platform`ベースの関数 | S |
| A-2b | game.py | `kivy.clock.Clock` → callback引数パターン | M |
| A-2c | base_katrain.py | `JsonStore` → JSON直接操作 | M |
| A-2d | lang.py | `Observable`継承 → callbackパターン | M |

**新規ファイル**:
- `katrain/common/platform.py` - OS判定ユーティリティ
- `katrain/common/config_store.py` - 設定ストア抽象化（オプション）

**受入条件**:
- 全879テストパス
- `python -m katrain` 起動成功
- TEMPORARY_ALLOWEDを空に

---

### A-3: ゴールデンテスト拡充 [優先度: MEDIUM, 複雑度: M]

**目標**: カルテ出力の回帰検出を強化

**アプローチ**:
- 2-5個の代表的SGFをテストフィクスチャに追加
- `test_golden_karte.py` 実装
- 正規化ルール: タイムスタンプ→[TIMESTAMP]、float→1桁
- `--update-goldens`フラグでの更新メカニズム

**フレーキネス対策**:
- 決定論的ソート（手番順）
- テスト用SGFにKataGo解析結果を事前埋め込み

**対象ファイル**:
- `tests/test_golden_karte.py` (新規)
- `tests/fixtures/sgf/` (テスト用SGF)
- `tests/fixtures/golden/karte_*.md` (期待出力)

**受入条件**:
- 3個以上のSGFでゴールデンテスト実行
- カルテ形式変更時にテスト失敗

---

### A-4: CLAUDE.md・アーキテクチャルール文書化 [優先度: MEDIUM, 複雑度: S]

**目標**: 開発者ガイドラインを明確化

**アプローチ**:
- `.claude/rules/05-architecture.md` 新規作成
- 依存ルール明文化: core→gui禁止、core→kivy禁止
- `CLAUDE.md` セクション4に依存ルール追加

**対象ファイル**:
- `.claude/rules/05-architecture.md` (新規)
- `CLAUDE.md` (更新)

**受入条件**:
- ルールが明文化されている
- Claude Codeがルールを認識

---

### B-1: ロジックファースト開発ルール [優先度: LOW, 複雑度: S]

**目標**: 新機能がUI前にロジック+テストを持つことを保証

**アプローチ**:
- PRテンプレートにチェックリスト追加
- CLAUDE.mdに開発フロー記載

**対象ファイル**:
- `.github/pull_request_template.md` (新規/更新)
- `CLAUDE.md` (更新)

---

### B-2: KVスタイル統一 [優先度: MEDIUM, 複雑度: M]

**目標**: KVファイルのハードコード値を定数化、重複削減

**アプローチ**:
- gui.kv先頭にスタイル定数定義（FONT_INPUT, PADDING_NORMAL等）
- 重複入力フィールドの統合（5→3クラス）
- ボタンバリエーション整理（8→4クラス）

**対象ファイル**:
- `katrain/gui.kv`
- `katrain/popups.kv`

**受入条件**:
- ハードコードpadding/font_sizeが定数参照に
- UI外観に変化なし

---

### B-3: 大規模Popup分割 [優先度: LOW, 複雑度: M]

**目標**: ConfigPopup（200行超）を管理可能な単位に分割

**対象ファイル**:
- `katrain/popups.kv`

---

## 実装計画（PRスライス）

| PR | 内容 | リスク | 依存 |
|:--:|------|:------:|:----:|
| #136 | A-1 Kivyインポート禁止テスト | LOW | - |
| #137 | A-2a/A-2b engine.py/game.py Kivy解消 | MEDIUM | #136 |
| #138 | A-2c/A-2d base_katrain/lang.py Kivy解消 | MED-HIGH | #137 |
| #139 | A-3 ゴールデンテスト拡充 | LOW | - |
| #140 | A-4 + B-1 ドキュメント更新 | NONE | - |
| #141 | B-2 KVスタイル統一 | LOW | - |

**並行実行可能**: #136, #139, #140, #141

---

## 受入条件（全体）

1. **テスト**: 全879+テストパス
2. **CI**: test_architecture.pyがKivy依存を検出
3. **起動**: `python -m katrain` 正常動作
4. **ドキュメント**: 依存ルールが明文化
5. **KV**: ハードコード値が50%以上削減（B-2完了時）

---

## リスクと緩和策

| リスク | 影響度 | 緩和策 |
|--------|--------|--------|
| lang.pyのObservable削除によるUIバインディング破損 | HIGH | 段階的移行、手動テスト重視 |
| Clock削除によるタイミング問題 | MEDIUM | callbackパターンで同等動作を保証 |
| ゴールデンテストのフレーキネス | MEDIUM | 厳格な正規化ルール、決定論的データ使用 |
| KVリファクタリングによるレイアウト崩れ | LOW | 視覚的リグレッションテスト（手動） |

---

## 変更履歴

| 日時 | 内容 |
|------|------|
| 2026-01-16 | 初版作成 - Phase 20調査・計画 |
