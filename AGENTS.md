# AGENTS.md - myKatrain PC版 開発ガイド

> このファイルは **opencode** がプロジェクト開始時に自動ロードする中核ドキュメントです。
> 細目ルールはスキル（`.opencode/skills/<name>/SKILL.md`）として on-demand で読み込みます。
> opencode の設定は `opencode.jsonc`、権限もそこで一元管理しています。

---

## 1. プロジェクト概要

### 1.1 基本情報
- **プロジェクト名**: myKatrain（KaTrain fork）
- **技術スタック**: Python 3.13+ / Kivy（GUI）/ KataGo（解析エンジン）
- **リポジトリ**: `sentoku870/my-katrain-v1.17.0`
- **ローカルパス**: `D:\github\katrain-1.17.0`

### 1.2 目的（1文）
KataGo解析を元に「カルテ（Karte）」を生成し、LLM囲碁コーチングで的確な改善提案を引き出す。

### 1.3 現在のフェーズ
- **完了**: Phase 1-142（解析基盤、カルテ、リファクタリング、Guardrails、SGF E2Eテスト、LLM Package Export、レポート導線改善、Settings UI拡張、Smart Kifu運用強化、Diagnostics、解析強度抽象化、Leela→MoveEval変換、レポートLeela対応、エンジン選択設定、UIエンジン切替、Leelaカルテ統合、Leelaバッチ解析、テスト強化、安定化、エンジン比較ビュー、PLAYモード、コード品質リファクタリング、Batch Core Package完成、Stability Audit、Batch Analysis Fixes、Lexicon Core Infrastructure、Meaning Tags System Core、Meaning Tags Integration、5-Axis Radar Data Model、Radar Aggregation & Summary Integration、Critical 3 Focused Review Mode、Radar UI Widget、Tofu Fix + Language Code Consistency、Stabilization、Batch Report Quality、Report Quality Improvements、Report Foundation + User Aggregation、Style Archetype Core、Style Karte Integration、Time Data Parser、Pacing & Tilt Core、Pacing/Tilt Integration、Risk Context Core、Risk統合、Curator Scoring、Curator出力、Post-54統合テスト、Post-54品質強化、Engine Stability、Command Pattern、Parser/Base Test Enhancement、Complex Function Refactoring、batch/stats.py分割、karte_report.py分割、KaTrainGui分割A-KeyboardManager、KaTrainGui分割B-ConfigManager、KaTrainGui分割C-PopupManager、KaTrainGui分割D-GameStateManager、エラーハンドリング監査、エラーハンドリングB、エラーハンドリングC、共通基盤、Ownershipクラスタ抽出、Cluster Classifier、Complexity Filter、Recurring Pattern Mining、Pattern to Summary Integration、Reason Generator、Signature Player Axis、Batch UI Consistency、Leela Batch Output Fix、KataGo Settings UI Reorg + humanlike Toggle、Auto Setup Mode、Error Recovery & Diagnostics、Beginner Hints MVP、Beginner Hints Extension、Active Review MVP、Active Review Extension、Stability Improvements、SummaryManager抽出、ActiveReviewController抽出、QuizManager抽出、ConfigStore基盤、Read-side Config Migration、TypedConfigWriter更新API、update_*_config()移行、StateNotifier基盤、Notifier統合、Notifier発火ポイント追加、UI Subscribe MVP、KaTrainGui Subscribe、mypy導入、core/state strict + 型エラー修正、core型エラー修正第1弾、gui/features型エラー修正、mypy strict全体・CIブロック、Python 3.11 modern syntax migration、Forward Reference + i18n + Semantic Type Fixes、Pre-existing型エラー修正＋Top Moves色回帰修正、Phase 138-D アーキテクチャ改善、Game 4分割、kivyutils分割、popups分割、commands/委譲）
- **次**: TBD（計画中）

詳細は `docs/01-roadmap.md` を参照。

---

## 2. ユーザー（sentoku870）のスキルと期待

### 2.1 スキルレベル
| 領域 | レベル | 備考 |
|------|--------|------|
| PC操作 | 中〜上級 | 手順があれば複雑な操作も実行可能 |
| プログラミング | 初心者 | Progate Python基礎程度、コードは読めるが書けない |
| Git/GitHub | 基本操作可 | 手順通りの操作は可能 |
| 囲碁 | 野狐4-5段 | ドメイン知識は十分 |

### 2.2 期待する対応
- **コード変更**: 原則 opencode で実行（手動編集は最小限）
- **説明**: 専門用語は初出時に1-2文で定義
- **手順**: コピペで完結する具体的なコマンドを提示
- **確認**: 動作確認ポイントを明示

### 2.3 作業の快適さ優先順位
1. **最優先**: 自分だけで動作ロジック修正をしない
2. **可能**: LLM指示ありの最小修正（タイポ、数値調整）
3. **許容**: ファイル全体のコピペ差し替え
4. **避けたい**: 複数ファイルの整合性判断

---

## 3. 開発ルール（要約）

詳細ルールはスキルとして提供。タスクの種類に応じて以下をロードしてください：

| スキル名 | 用途 | ファイル |
|---------|------|---------|
| `correction-levels` | 修正規模（Lv0-5）の判定と回答フォーマット | `.opencode/skills/correction-levels/SKILL.md` |
| `git-workflow` | ブランチ運用、コミット、PR作成フロー | `.opencode/skills/git-workflow/SKILL.md` |
| `debug-workflow` | バグ報告の整理、デバッグ7ステップ、KaTrain固有ポイント | `.opencode/skills/debug-workflow/SKILL.md` |
| `go-domain` | 棋力G0-G4、解説A-D、KataGo用語、カルテ概念 | `.opencode/skills/go-domain/SKILL.md` |
| `architecture` | レイヤー構造、core層のKivy隔離、代替パターン | `.opencode/skills/architecture/SKILL.md` |

### 3.1 基本動作確認
- **起動確認**: `python -m katrain`
- **テスト（全体）**: `uv run pytest tests`
- **アーキテクチャテスト**: `uv run pytest tests/test_architecture.py -v`
- **UTF-8強制**（PowerShell）: `$env:PYTHONUTF8 = "1"`

### 3.2 トークン削減ルール
- **Grep → Read パターン**: まず検索で場所を特定、次に範囲読み込み
- **段階的アプローチ**: 広範囲→狭範囲の順
- **目標**: 厳格（96%削減）ではなく、**緩め（70-80%削減）**
- **前後コンテキスト**: 関数定義は前後30-40行を含めて読む
- **小さなファイル**: 500行未満は全体読みOK

### 3.3 ロック設計ガイドライン（engine.py）
| ルール | 説明 |
|--------|------|
| `*_unlocked()` サフィックス | 呼び出し元がロックを保持している前提 |
| ロック内でコールバック/停止操作を呼ばない | 例: `stop_pondering()` はロック外で呼ぶ |
| 長時間操作はロック外 | I/O, sleep, 外部呼び出しをロック内で行わない |

### 3.4 フォールバックポリシー（Phase 36）
| 文脈 | Leela選択時の動作 |
|------|------------------|
| Settings UI保存 | 警告表示＋保存続行 |
| Batch開始 | 即座にエラー＋中断 |
| Export Karte | 呼び出し元でチェック |
| Config読み込み | KataGoにフォールバック＋警告ログ |

### 3.5 混合エンジン検出（Phase 37）
1手でも KataGo と Leela が混在する場合 `MixedEngineSnapshotError`。エンフォースは `build_karte_report()` 冒頭のみ。

### 3.6 シェル権限ルール（opencode.jsonc）
`opencode.jsonc` の bash 権限パターン。**設定変更後は opencode の再起動が必要**（起動時 1 回のみ読み込み）。

| 区分 | 自動許可（例） | 確認ダイアログ（ask） |
|------|--------------|---------------------|
| 開発 | `git *`, `gh *`, `uv *`, `python*`, `pip*`, `timeout*` | — |
| 読み取り | `cat*`, `head*`, `tail*`, `ls*`, `grep*`, `find*`, `findstr*`, `wc*`, `tree*`, `sort*`, `cut*`, `tr*`, `diff*`, `awk*`, `sed*`, `rg*`, `ag*`, `ack*`, `xargs*` | — |
| 診断 | `stat*`, `file*`, `which*`, `where*`, `date*`, `pwd*`, `env*`, `printenv*`, `du*`, `df*`, `uname*`, `whoami*`, `id*` | — |
| ファイル操作（可逆） | `mkdir*`, `touch*`, `cp*`, `mv*`, `chmod*`, `ln*`, `tar*`, `unzip*`, `zip*`, `gzip*`, `gunzip*` | `rm*`, `chown*` |
| Bash ビルトイン | `cd*`, `set*`, `unset*`, `export*`, `source*`, `eval*`, `type*`, `command*`, `hash*`, `true*`, `false*`, `test*`, `echo*` | — |
| ネットワーク | — | `curl*`, `wget*` |
| PowerShell | `Get-*`, `Select-*`, `Sort-Object*`, `Group-Object*`, `Measure-Object*`, `ForEach-Object*`, `Out-String*`, `Test-Path*`, `Where-Object*`, `Format-Table*`, `Format-List*`, `ConvertTo-Json*`, `ConvertFrom-Json*`, `Set-Location*`, `Push-Location*`, `Pop-Location*`, `Resolve-Path*`, `Write-Host*`, `Clear-Host*` | `Invoke-*`, `Start-Process*`, `Stop-Process*`, `Remove-Item*`, `Restart-Computer*` |

**運用注意**:
- 自動許可は開発効率のため。**破壊的操作（`rm`）/ 外部送信（`curl`/`wget`）/ 任意コード実行（`Invoke-*`）は確認を維持**
- 新しいパターンを追加する場合は `opencode.jsonc` 編集 → opencode 再起動
- 緊急時は `OPENCODE_DISABLE_PROJECT_CONFIG=1` で設定無効化可能

---

## 4. コード構造（概要）

```
katrain/
├── __main__.py            ← アプリ起動、KaTrainGui
├── common/                ← 共有定数（Kivy非依存）
│   ├── platform.py        ← get_platform()
│   ├── config_store.py    ← JsonFileConfigStore
│   └── lexicon/           ← 囲碁用語辞書
├── core/                  ← コアロジック（Kivy非依存）
│   ├── game.py, game_node.py, engine.py
│   ├── lang.py
│   ├── analysis/          ← 解析基盤（models/logic/presentation/meaning_tags/）
│   ├── batch/             ← バッチ処理
│   ├── curator/           ← 棋譜適合度スコアリング
│   └── state/             ← StateNotifier（イベント基盤）
├── gui/                   ← Kivy GUI
│   ├── controlspanel.py, badukpan.py, lang_bridge.py
│   ├── managers/          ← 各種Manager（active_review, summary, quiz, ...）
│   ├── widgets/
│   └── features/          ← 機能モジュール
├── gui.kv                 ← Kivy レイアウト
└── i18n/                  ← 翻訳ファイル
```

### データフロー
```
KataGo(JSON) → KataGoEngine → GameNode.set_analysis()
           → KaTrainGui.update_state() → UI更新
```

詳細は `docs/02-code-structure.md` を参照。

---

## 5. 囲碁ドメイン（要約）

- **棋力レベル**: G0（〜10級）〜 G4（五段相当、ユーザー本人）
- **解説レベル**: A（方向性）〜 D（KataGo並み、非現実的）
- **デフォルト**: G1-G2 / 解説=A + 薄いB
- **カルテ**: 重要局面・弱点仮説・アンカーで構成

詳細: `.opencode/skills/go-domain/SKILL.md`

---

## 6. 技術選定の判断基準（4軸）

| 軸 | A | B | C |
|----|---|---|---|
| 対象範囲 | 局所機能 | 画面単位 | アプリ全体 |
| 継続性 | 実験/一時的 | 中期（数ヶ月） | 長期（標準機能） |
| 精度要求 | ざっくり | ある程度信頼 | かなり正確 |
| 自動化 | 手動中心 | 半自動 | ほぼ全自動 |

迷ったら **B案（標準構成）** を採用。

---

## 7. やらないこと（non-goals）

- 外部APIへの自動送信（LLM連携は手動添付）
- フル機能SGFエディタ化
- 大規模な棋譜管理DB
- 対局支援（チート用途）
- 「最善手当てクイズ」を目的化した訓練

---

## 8. 出力時の注意

### 8.1 回答フォーマット（推奨）
```
1. 今回やること（1-2文）
2. 修正レベル（Lv0-5）
3. 変更ファイル
4. 手順（コマンド付き）
5. 動作確認ポイント
```

### 8.2 記号の使い分け
- 囲碁解説レベル: `解説=A〜D`
- 技術選定4軸: `軸(対象範囲)=A〜C`
- 採用案: `案=A案/B案/C案`

### 8.3 スキル読み込みの判断
- 修正前に `correction-levels` スキルでレベル判定
- レベル3以上の作業では `architecture` スキルを参照
- 囲碁関連機能では `go-domain` スキルを参照
- バグ修正では `debug-workflow` スキルを参照
- コミット・PR時は `git-workflow` スキルを参照

---

## 9. ドキュメント配置

```
docs/
├── 00-purpose-and-scope.md
├── 01-roadmap.md
├── 02-code-structure.md
├── 03-llm-validation.md
├── usage-guide.md
├── i18n-workflow.md
├── examples/
├── resources/
├── ideas/
├── future/
└── archive/                ← 完了済みアーカイブ

.opencode/
├── skills/                 ← on-demand 細目ルール
│   ├── correction-levels/SKILL.md
│   ├── git-workflow/SKILL.md
│   ├── debug-workflow/SKILL.md
│   ├── go-domain/SKILL.md
│   └── architecture/SKILL.md
└── (agents/, commands/)    ← 必要に応じて追加
```

---

## 10. 変更履歴

- 2026-06-26: AGENTS.md として再構成（旧 CLAUDE.md から移行、スキルを on-demand 化）
- 〜2026-06-25: CLAUDE.md（Phase 142 まで）に記録された全 Phase
