# AGENTS.md - myKatrain PC版 開発ガイド

> opencode 用の統合開発ガイドです。
> 詳細仕様は `docs/01-roadmap.md`、`docs/02-code-structure.md`、`docs/03-llm-validation.md` を参照してください。

---

## 1. プロジェクト概要

- **プロジェクト名**: myKatrain（KaTrain fork）
- **技術スタック**: Python 3.11+ / Kivy（GUI）/ KataGo・Leela Zero（解析エンジン）
- **リポジトリ**: `sentoku870/my-katrain-v1.17.0`
- **目的**: KataGo / Leela Zero 解析を元に「カルテ（Karte）」を生成し、LLM 囲碁コーチングで的確な改善提案を引き出す
- **最新完了**: Phase 137（2026-02-10、Skill Radar 削除・SGF 読込バグ修正）
- **進行中**: 計画中（Beginner Hint 拡張、Active Review 拡張）

詳細は `docs/01-roadmap.md` を参照。

---

## 2. ユーザー（sentoku870）のスキルと期待

### 2.1 スキルレベル

| 領域 | レベル | 備考 |
|------|--------|------|
| PC操作 | 中〜上級 | 手順があれば複雑な操作も実行可能 |
| プログラミング | 初心者 | Progate Python 基礎程度、コードは読めるが書けない |
| Git/GitHub | 基本操作可 | 手順通りの操作は可能 |
| 囲碁 | 野狐4-5段 | ドメイン知識は十分 |

### 2.2 期待する対応

- **コード変更**: 原則 opencode が実行（手動編集は最小限）
- **説明**: 専門用語は初出時に 1-2 文で定義
- **手順**: コピペで完結する具体的な bash コマンドを提示
- **確認**: 動作確認ポイントを明示

### 2.3 作業の快適さ優先順位

1. **最優先**: 自分だけで動作ロジック修正をしない
2. **可能**: AI 指示ありの最小修正（タイポ、数値調整）
3. **許容**: ファイル全体のコピペ差し替え
4. **避けたい**: 複数ファイルの整合性判断

---

## 3. 開発ルール

### 3.1 修正レベル（Lv0-5）

| Lv | 規模 | 対応方法 |
|:--:|------|----------|
| 0 | 超軽微（コメント/文言） | 直接修正 |
| 1 | 軽微（〜50行、1ファイル） | 直接修正 |
| 2 | 中程度（〜100行、1-2ファイル） | Plan Mode → 承認 → 実行 |
| 3 | 複数ファイル（2-3ファイル） | Plan Mode + 段階的実行 |
| 4 | 大規模（4ファイル超） | 分割案を先に提示 |
| 5 | 根本変更 | 設計相談のみ（実装保留） |

迷ったら上のレベルに寄せる（安全側）。

### 3.2 Git ワークフロー

```
code-change（コード修正を含む）:
  → ブランチ: feature/YYYY-MM-DD-<short-desc>
  → PR 経由で main にマージ

docs-only（ドキュメントのみ）:
  → main 直接コミット可
```

#### 基本手順

```bash
# 1) main を最新にする
git switch main
git pull origin main

# 2) 作業ブランチを作成
git switch -c feature/YYYY-MM-DD-<short-desc>

# 3) opencode で修正を実行

# 4) 動作確認
python -m katrain                 # 起動確認
PYTHONUTF8=1 uv run pytest tests  # テスト

# 5) コミット
git add -A
git commit -m "<type>: <short-desc>"

# 6) push / PR（ユーザー確認後に実行）
git push -u origin HEAD
gh pr create --base main --fill
```

#### コミットメッセージ規約

| type | 用途 | 例 |
|------|------|-----|
| `feat` | 新機能 | `feat: add karte export button` |
| `fix` | バグ修正 | `fix: quiz crash on empty analysis` |
| `refactor` | リファクタリング | `refactor: extract eval logic` |
| `docs` | ドキュメント | `docs: update roadmap` |
| `test` | テスト | `test: add quiz generation tests` |
| `chore` | その他 | `chore: update dependencies` |

### 3.3 動作確認コマンド

```bash
# 起動
python -m katrain

# 全テスト
PYTHONUTF8=1 uv run pytest tests

# 単一ファイル
uv run pytest tests/test_batch_analyzer.py -v

# 単一テスト関数
uv run pytest tests/test_batch_analyzer.py::test_function_name -v

# キーワードフィルタ
uv run pytest tests -k "radar" -v

# ゴールデン更新
uv run pytest tests/test_golden_summary.py --update-golden
uv run pytest tests/test_golden_karte.py --update-golden

# 失敗時に即停止
uv run pytest tests -x

# 直前の失敗テスト再実行
uv run pytest tests --lf

# mypy 型チェック
uv run mypy katrain
```

### 3.4 ファイル読み込みのトークン削減

#### 原則

- **ファイル全体の読み込みを避ける**: 必要な部分のみ読み取る
- **Grep → Read パターン**: まず検索で場所を特定、次に範囲読み込み
- **段階的アプローチ**: 広範囲 → 狭範囲の順で絞り込む

#### パターン別推奨範囲

| 目的 | 手順 | 推奨範囲 |
|------|------|----------|
| 関数定義の確認 | Grep → Read（前後 30-40 行） | 80-120 行 |
| クラス全体の把握 | Grep → Read（周辺含む） | 150-250 行 |
| 特定機能の調査 | Grep → Read（各箇所 ±40 行） | 60-100 行/箇所 |
| エラー原因の特定 | Grep → Read（スタック ±30 行） | 60-80 行 |
| 小さいファイル（< 500 行） | Grep せず直接 Read | 全体 |

**目標**: 厳格（96% 削減）ではなく **70-80% 削減** を目指す。

---

## 4. コード構造（要約）

```
katrain/
├── __main__.py                # アプリ起動、KaTrainGui
├── common/                    # 共有定数（Kivy 非依存）
│   ├── platform.py            # OS 判定
│   ├── config_store.py        # 設定永続化
│   ├── typed_config/          # 型付き設定（reader/writer/models）
│   └── lexicon/               # 囲碁用語辞書
├── core/                      # コアロジック（Kivy 非依存）
│   ├── game.py, game_node.py  # 対局状態
│   ├── engine.py              # KataGo エンジン
│   ├── leela/                 # Leela Zero 連携
│   ├── analysis/              # 解析基盤
│   │   ├── models.py, logic.py, presentation.py
│   │   └── meaning_tags/      # 意味タグ分類
│   ├── batch/                 # バッチ処理
│   ├── curator/               # 棋譜適合度スコアリング
│   ├── reports/               # Karte / Summary レポート
│   │   └── karte/             # Karte 生成サブパッケージ
│   ├── state/                 # StateNotifier
│   └── beginner/              # 初心者ヒント
├── gui/                       # GUI（Kivy 依存）
│   ├── controlspanel.py, badukpan.py
│   ├── features/              # 機能モジュール
│   ├── managers/              # マネージャー（Keyboard/Config/Popup/Quiz/Summary/...）
│   └── kv/                    # Kivy レイアウト分割
└── i18n/                      # 翻訳
```

### データフロー

```
KataGo(JSON) → KataGoEngine → GameNode.set_analysis()
            → KaTrainGui.update_state() → UI 更新
```

詳細は `docs/02-code-structure.md` を参照。

---

## 5. アーキテクチャ制約

- **レイヤー**: `gui/` → `core/` → `common/` の単方向依存
- **Kivy 隔離**: `core/` から `kivy` / `katrain.gui` への import 禁止
- **強制テスト**: `tests/test_architecture.py`（Kivy 隔離、許可リストの DELETE-ONLY 検証）
- **許可リスト**: `tests/fixtures/kivy_import_allowlist.json`（新規追加不可、削除のみ）
- **OS 判定**: `katrain.common.platform.get_platform()`（Kivy 非依存）
- **設定永続化**: `katrain.common.config_store.JsonFileConfigStore`
- **UI 通知**: `katrain.core.state.notifier.StateNotifier`

詳細は `.opencode/agent/plan.md` を参照。

---

## 6. 囲碁ドメイン（参照）

| 棋力 | 目安 | ユーザー |
|:----:|------|----------|
| G0 | 〜10級 | - |
| G1 | 5〜1級 | - |
| G2 | 初段〜二段 | - |
| G3 | 三〜四段 | - |
| G4 | 五段相当 | **本人** |

| 解説 | 内容 | 推奨度 |
|:----:|------|--------|
| A | 方向性ヒント | メイン |
| B | 役割・構図ヒント | 補助 |
| C | プロ構想レベル | 任意 |
| D | KataGo 詳細 | 非採用 |

デフォルト: **G3-G4 / 解説=A + 薄いB**

---

## 7. やらないこと（non-goals）

- 外部 API への自動送信（LLM 連携は手動添付）
- フル機能 SGF エディタ化
- 大規模な棋譜管理 DB
- 対局支援（チート用途）
- 「最善手当てクイズ」を目的化した訓練

---

## 8. 出力時の注意

### 8.1 回答フォーマット（推奨）

```
1. 今回やること（1-2 文）
2. 修正レベル（Lv0-5）
3. 変更ファイル
4. 手順（bash コマンド付き）
5. 動作確認ポイント
```

### 8.2 記号の使い分け

- 囲碁解説レベル: `解説=A〜D`
- 技術選定 4 軸: `軸(対象範囲)=A〜C`
- 採用案: `案=A案/B案/C案`

---

## 9. ドキュメント配置

```
docs/
├── 00-purpose-and-scope.md  # 目的とスコープ（固定）
├── 01-roadmap.md            # ロードマップ（更新可）
├── 02-code-structure.md     # コード構造
├── 03-llm-validation.md     # LLM 検証ガイド
├── usage-guide.md           # 使い方ガイド
├── i18n-workflow.md         # 翻訳ワークフロー
├── examples/                # ワークフロー例
├── resources/               # YAML リソース
├── ideas/                   # アイデア・構想メモ
├── future/                  # 延期された仕様書
└── archive/                 # 完了済みアーカイブ
    ├── CHANGELOG.md
    ├── plans/               # 完了した計画書
    ├── phase-guides/        # Phase 固有ガイド
    └── specs-implemented/   # 実装済み仕様書

.opencode/
└── agent/
    ├── build.md             # Build エージェント用プロンプト
    └── plan.md              # Plan エージェント用プロンプト
```

---

## 10. 関連スキル・エージェント

- **Build エージェント** (`.opencode/agent/build.md`): 実装・テスト・コミットまで担当
- **Plan エージェント** (`.opencode/agent/plan.md`): 計画・設計専用、ファイル変更は提案のみ
- **デフォルト動作**: Build で開始。Lv 3 以上は Plan に切替を推奨
