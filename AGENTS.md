# AGENTS.md - myKatrain PC版 開発ガイド

> このファイルは **opencode** がプロジェクト開始時に自動ロードする中核ドキュメントです。
> 細目ルールはスキル（`.opencode/skills/<name>/SKILL.md`）として on-demand で読み込みます。
> opencode の設定は `opencode.jsonc`、権限もそこで一元管理しています。

---

## 1. プロジェクト概要

### 1.1 基本情報
- **プロジェクト名**: myKatrain（KaTrain fork）
- **技術スタック**: Python 3.11+（主開発環境: 3.13）/ Kivy（GUI）/ KataGo（解析エンジン）
- **リポジトリ**: `sentoku870/my-katrain-v1.17.0`
- **ローカルパス**: `D:\github\katrain-1.17.0`

### 1.2 目的（1文）
KataGo解析を元に「カルテ（Karte）」を生成し、LLM囲碁コーチングで的確な改善提案を引き出す。

### 1.3 現在のフェーズ
- **完了**: Phase 1-170（解析基盤、カルテ、リファクタリング、Guardrails、SGF E2Eテスト、LLM Package Export、レポート導線改善、Settings UI拡張、Smart Kifu運用強化、Diagnostics、解析強度抽象化、Leela→MoveEval変換、レポートLeela対応、エンジン選択設定、UIエンジン切替、Leelaカルテ統合、Leelaバッチ解析、テスト強化、安定化、エンジン比較ビュー、PLAYモード、コード品質リファクタリング、Batch Core Package完成、Stability Audit、Batch Analysis Fixes、Lexicon Core Infrastructure、Meaning Tags System Core、Meaning Tags Integration、5-Axis Radar Data Model、Radar Aggregation & Summary Integration、Critical 3 Focused Review Mode、Radar UI Widget、Tofu Fix + Language Code Consistency、Stabilization、Batch Report Quality、Report Quality Improvements、Report Foundation + User Aggregation、Style Archetype Core、Style Karte Integration、Time Data Parser、Pacing & Tilt Core、Pacing/Tilt Integration、Risk Context Core、Risk統合、Curator Scoring、Curator出力、Post-54統合テスト、Post-54品質強化、Engine Stability、Command Pattern、Parser/Base Test Enhancement、Complex Function Refactoring、batch/stats.py分割、karte_report.py分割、KaTrainGui分割A-KeyboardManager、KaTrainGui分割B-ConfigManager、KaTrainGui分割C-PopupManager、KaTrainGui分割D-GameStateManager、エラーハンドリング監査、エラーハンドリングB、エラーハンドリングC、共通基盤、Ownershipクラスタ抽出、Cluster Classifier、Complexity Filter、Recurring Pattern Mining、Pattern to Summary Integration、Reason Generator、Signature Player Axis、Batch UI Consistency、Leela Batch Output Fix、KataGo Settings UI Reorg + humanlike Toggle、Auto Setup Mode、Error Recovery & Diagnostics、Beginner Hints MVP、Beginner Hints Extension、Active Review MVP、Active Review Extension、Stability Improvements、SummaryManager抽出、ActiveReviewController抽出、QuizManager抽出、ConfigStore基盤、Read-side Config Migration、TypedConfigWriter更新API、update_*_config()移行、StateNotifier基盤、Notifier統合、Notifier発火ポイント追加、UI Subscribe MVP、KaTrainGui Subscribe、mypy導入、core/state strict + 型エラー修正、core型エラー修正第1弾、gui/features型エラー修正、mypy strict全体・CIブロック、Python 3.11 modern syntax migration、Forward Reference + i18n + Semantic Type Fixes、Pre-existing型エラー修正＋Top Moves色回帰修正、Phase 138-D アーキテクチャ改善、Game 4分割、kivyutils分割、popups分割、commands/委譲、Phase 158+ AI strategies・engine・badukpan 分割、Phase 159A Karte/Summary の KataGo-only 化、Phase 170 人間 vs Leela 対局機能の再廃止）、**Phase 171（Leela エンジン完全削除）**、**Phase 178（棋譜並べ機能ドキュメント整備 + Root解析堅牢化 + 終了経路統一）**、**Phase 179 + 179.1 + 179.2（Beginner Hints Summary Extension — ミス・自由度・難易度の Hint 統合 + 監査発見の品質改善）**、**Phase 182（Ownership / Policy 派生ヒント追加 — 3 カテゴリ）**、**Phase 186（Curator 集約統合 — 棋譜全体の弱点パターンを Hint に統合）**、**Phase 187（Architecture Review Follow-up A1 — `core/beginner/hints.py` カバレッジ 16.5% → 97%）**、**Phase 188（Architecture Review Follow-up A3 — `KifunarabeController` God Class 分割 4 mixin + facade）**、**Phase 189（Architecture Review Follow-up A2 — `core/auto_setup.py` カバレッジ 9.8% → 97%）**、**Phase 190（Architecture Review Follow-up A4 — `core/engine.py` カバレッジ 48.3% → 83%）**、**Phase 191（Architecture Review Follow-up B1 — engine subsystem TYPE_CHECKING 循環を `_engine_types.py` に集約）**、**Phase 192（Architecture Review Follow-up B2 — `core/analysis/logic_difficulty.py` 756 行を `analysis/difficulty/` サブパッケージ化）**
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
- **テスト（全体・逐次）**: `uv run pytest tests`
- **テスト（全体・並列）**: `uv run pytest tests -n auto`（pytest-xdist）
- **テスト（時間上位表示）**: `uv run pytest tests --durations=20 --durations-min=0.1`
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

**運用方針**: 開発に必要なコマンドはほぼ無確認で通し、システム破壊系のみ明示ブロックする **B案（中庸）**。確認ダイアログ（ask）は 0 件、危険コマンドは明示 deny、未指定コマンドは `*: allow` で通過。

#### 自動許可（allow）

| 区分 | パターン例 |
|------|----------|
| Python 開発 | `uv *`, `python*`, `python3*`, `pip*`, `pytest*`, `ruff*`, `mypy*`, `coverage*`, `pre-commit*`, `timeout*` |
| バージョン管理 | `git *`, `gh *` |
| Node/JS | `node*`, `npm*`, `npx*`, `pnpm*`, `yarn*`, `bun*`, `deno*` |
| ビルド/コンテナ | `make*`, `cmake*`, `ninja*`, `meson*`, `gcc*`, `g++*`, `docker*`, `docker-compose*`, `podman*` |
| 読み取り/加工 | `cat*`, `head*`, `tail*`, `ls*`, `grep*`, `find*`, `wc*`, `tree*`, `diff*`, `awk*`, `sed*`, `rg*`, `xargs*`, `jq*`, `yq*`, `xxd*`, `base64*`, `less*`, `more*`, `tee*` |
| 診断 | `stat*`, `file*`, `which*`, `pwd*`, `env*`, `uname*`, `whoami*`, `id*`, `date*`, `du*`, `df*` |
| プロセス/システム | `ps*`, `top*`, `htop*`, `kill*`, `killall*`, `pkill*`, `pidof*`, `clear*`, `sleep*` |
| ネットワーク | `ssh*`, `scp*`, `rsync*`, `ping*`, `ip*`, `netstat*`, `ss*`, `curl*`, `wget*` |
| ファイル操作（可逆・破壊的）| `mkdir*`, `touch*`, `cp*`, `mv*`, `chmod*`, `chown*`, `ln*`, `rm*`, `tar*`, `unzip*`, `zip*`, `gzip*`, `gunzip*` |
| Bash ビルトイン | `cd*`, `set*`, `unset*`, `export*`, `source*`, `eval*`, `echo*`, `type*`, `command*`, `hash*`, `true*`, `false*`, `test*` |

#### 確認ダイアログ（ask）
なし。すべてのコマンドは allow または deny のいずれかに分類される。

#### 拒否（deny）— 危険コマンドの明示ブロック

| カテゴリ | 拒否対象 |
|---------|---------|
| 権限昇格 | `sudo *`, `su *`, `doas *` |
| 電源操作 | `shutdown *`, `reboot *`, `halt *`, `poweroff *`, `init *` |
| ディスク破壊 | `mkfs*`, `fdisk*`, `parted*`, `dd *` |
| サービス管理 | `systemctl*`, `service *` |
| 認証情報 | `passwd*`, `chpasswd*`, `visudo*` |
| ユーザー管理 | `useradd*`, `userdel*`, `usermod*`, `groupadd*`, `groupdel*`, `groupmod*` |
| ファイアウォール | `iptables*`, `ip6tables*`, `firewalld*`, `ufw *`, `nft *` |
| マウント | `mount*`, `umount*` |
| スケジュール | `crontab*`, `at *` |
| ルーティング | `route *` |

#### フォールバック
`"*": "allow"` — 未指定のコマンドは許可。**ただし上記 deny に該当するパターンは遮断される**。

> **環境注意**: 本プロジェクトは Linux 環境前提のため PowerShell 系の許可は含めていません。Windows 環境が必要な場合は `opencode.jsonc` に PowerShell パターンを再追加してください。

**運用注意（B案採用により追加）**:
- `rm*` を allow 化したため、削除操作は自己責任。重要なファイル削除（特に `rm -rf` 系）は事前に確認推奨
- `chown*` を allow 化したため、オーナー書き換えは慎重に行う
- `curl*` / `wget*` を allow 化したため、外部送信は意図しないデータ流出に注意。プロキシ・認証情報の取り扱いに注意
- `*: allow` 化により未指定のコマンドも基本的に通る。deny に該当しない限り許可される
- deny リスト該当操作は opencode が完全拒否。どうしても必要な場合はターミナルで直接実行
- 任意コード実行リスクのある `python*`（`-c` 経由）/ `eval*` / `source*` は allow だが使い方に注意
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

- 2026-07-16: Position Difficulty サブパッケージ化 — Phase 192（Architecture Review Follow-up B2）
  - **背景**: 2026-07-14 アーキテクチャレビューで `core/analysis/logic_difficulty.py` が 756 行・13 関数 / 単一ファイル構成と判明。同レビューで既に分割されている `cluster_*` / `meaning_tags` / `time` / `models` サブディレクトリ群と整合せず、cognitive load 増 + テスト分離困難
  - **分割**: 単一ファイルを **`analysis/difficulty/` サブパッケージ（6 モジュール）** に再編:
    - `_io.py` — 候補手正規化、root_visits 抽出、信頼性判定、GameNode 取得
    - `_policy.py` — policy エントロピー fallback + top-1/top-2 scoreLead gap
    - `_transition.py` — 評価急落度
    - `_state.py` — 盤面複雑度 (v1 placeholder)
    - `_error_pressure.py` — KataGo shorttermScoreError
    - `_lcb_gap.py` — LCB 差分
    - `api.py` — 公開 4 関数 (`assess_position_difficulty_from_parent`, `compute_difficulty_metrics`, `extract_difficult_positions`, `difficulty_metrics_from_node`)
  - **後方互換シム**: `katrain/core/analysis/logic_difficulty.py` を全 re-export の互換シムに:
    - `difficulty_metrics_from_node` 等の公開 4 関数 全て動作
    - `_compute_policy_difficulty` / `_get_root_visits` / `_normalize_candidates` 等の private 補助も動作（既存テスト `test_difficulty_metrics.py` 867 行 / 78 tests 無修正で通過）
    - 旧名前 (`_compute_*`) と新名前 (`compute_*`) の **両方** をシムから提供し、段階移行を可能に
  - **影響範囲**:
    - 新規: 7 ファイル (`analysis/difficulty/__init__.py`, `api.py`, `_io.py`, `_policy.py`, `_transition.py`, `_state.py`, `_error_pressure.py`, `_lcb_gap.py`)
    - 変更: 1 ファイル (`logic_difficulty.py` をシム化)
  - **後方互換**: 既存 `logic.py` / `logic_reliability.py` / `__init__.py` / `test_difficulty_metrics.py` の 4 ファイル無修正
  - **検証**:
    - mypy strict: 9 files PASS
    - ruff check: All checks passed (9 files)
    - `pytest tests/test_difficulty_metrics.py tests/test_difficulty_modifier.py tests/test_critical_moves.py tests/test_beginner_hints_main.py tests/test_summary_analyzer.py`: 309 PASS
    - 既存テストファイル無修正で全件通過 → 後方互換シムの実効性を確認
  - **アーキテクチャ**: 既存 `analysis/cluster_*` / `analysis/meaning_tags/` / `analysis/time/` / `analysis/models/` の **サブパッケージ化パターン** に揃えられた。これにより `analysis/` 直下が「オーケストレーター・判断系」と「サブパッケージ」の二層構造に整理
  - **効果**: 行数均一化 (各ファイル 100-300 行)、責任分離、機能追加時の影響範囲限定
  - **スペック**: `docs/archive/specs-implemented/phase192-logic-difficulty-subpackage.md` 新設
- 2026-07-15: Engine Subsystem TYPE_CHECKING 循環解消 — Phase 191（Architecture Review Follow-up B1）
  - **背景**: 2026-07-14 アーキテクチャレビューで engine サブシステム（`engine.py` ↔ `engine_io.py` ↔ `engine_query.py` ↔ `engine_cmd/executor.py`）間に TYPE_CHECKING の前方参照が 4 箇所に重複している状態を発見。`KataGoEngine` / `GameNode` の前方参照が各モジュールに散在し、循環依存の全体像が見えにくい
  - **解決**: 新ファイル `katrain/core/_engine_types.py` を新設し、TYPE_CHECKING 専用の前方参照を集約
    - `engine_io.py` / `engine_query.py` / `engine_cmd/executor.py` の TYPE_CHECKING ブロックを `from katrain.core._engine_types import ...` 経由に変更
    - `_engine_types.py` 自体には runtime import が一切ない（TYPE_CHECKING のみ）
    - 開発者が依存関係を読み解く際、循環の全体像を 1 ファイルで確認可能
  - **PEP 563 不採用の理由**: `from __future__ import annotations` だけでは mypy が forward reference 文字列の名前解決時に `GameNode` / `KataGoEngine` を見つけられず 18 件のエラー発生。TYPE_CHECKING ブロック自体は mypy にとって必須
  - **影響範囲**:
    - 新規: `katrain/core/_engine_types.py`（42 行、TYPE_CHECKING 専用）
    - 変更: `engine_io.py` / `engine_query.py` / `engine_cmd/executor.py`（各 1 箇所のみ）
  - **後方互換**: すべて内部モジュール間の forward reference 整理であり、公開 API・動作は完全不変
  - **検証**:
    - mypy strict: 4 files PASS
    - ruff check: 4 files PASS
    - `pytest tests/test_engine_coverage.py tests/test_engine_commands.py tests/test_engine_lifecycle.py tests/test_architecture.py`: 194 PASS
    - 全体: 4128 PASS（既存 + 新規、kivy 依存テストは環境制約で既存通り失敗）
  - **アーキテクチャ**: 既存 Phase 158+ の分割設計を維持しつつ、依存グラフを明示化
  - **スペック**: `docs/archive/specs-implemented/phase191-engine-type-cycle-cleanup.md` 新設
- 2026-07-15: core/engine.py Coverage — Phase 190（Architecture Review Follow-up A4）
  - **背景**: Architecture Review で `core/engine.py` のカバレッジが **48.3%**（心臓部でこの値は不安）と判明。サブプロセス・スレッド依存の KataGoEngine メソッドが計測空白で、純粋関数・ベース設定・パスメソッドの回帰リスクが懸念
  - **追加**: `tests/test_engine_coverage.py`（**59 件** の新規テスト、374 行）
  - **カバレッジ**: engine.py **48.3% → 83%**（355 stmts、test_engine_commands.py + test_engine_lifecycle.py + 今回新規の合計）
  - **カバー領域**:
    - Section 1: `_ensure_str` pure 関数の None / bytes / str / UTF-8 エラー処理 6 件
    - Section 2: `_identity_scheduler` / `BaseEngine.__init__` の依存注入 8 件
    - Section 3: `BaseEngine.get_rules` の JSON / dict / abbr / 大文字小文字 7 件
    - Section 4: `get_engine_path` の Linux/macOS + PATH 検索 + エラー callback 5 件
    - Section 5: `set_analysis_focus` の設定書込 3 件
    - Section 6: `BaseEngine` 既定の `is_alive` / `status` / `on_error` / `_fire_engine_error` 6 件
    - Section 7: `MAX_PENDING_QUERIES` 定数のドキュメント値検証 2 件
    - Section 8: `KataGoEngine.is_idle` / `is_alive` / `queries_remaining` / `create_minimal_analysis_query` (サブプロセス非依存) 7 件
    - Section 9: `get_backend_type` の OpenCL/CUDA/Eigen/TensorRT/Unknown 検出 8 件
    - Section 10: `RULESETS` 双方向マッピング パラメタライズド 8 件
  - **テスト合計**: 472 → **531 PASS**（既存 472 件不変 + 新規 59 件）
  - **アーキテクチャ**: core 層 Kivy 非依存維持。`mypy katrain/core/engine.py` pass
  - **lint/mypy**: ruff pass, mypy pass
  - **設計判断**: `_make_katago_engine_for_inspection()` は `KataGoEngine.__new__` + 必要な属性を全て手動設定することで、サブプロセス起動を完全にバイパス。`type: Any` で mypy エラーを 1 箇所に集中
  - **カバー未対象（意図的）**:
    - サブプロセス起動・終了（test_engine_lifecycle.py で網羅）
    - パイプリーダースレッド（test_engine_commands.py で網羅）
    - リアル Katago プロトコル（integration tests）
  - **アーキテクチャレビュー A4 完了**: ハート・オブ・システムの単体テスト充実。これで Priority 1+A4（つまり A 系統全体）が解消
  - **スペック**: `docs/archive/specs-implemented/phase190-engine-coverage.md` 新設
- 2026-07-15: Auto Setup Module Coverage — Phase 189（Architecture Review Follow-up A2）
  - **背景**: Architecture Review（2026-07-14）で `core/auto_setup.py` のカバレッジが **9.8%**（36/368 行）と判明。全コア層中最低値で、Auto Setup Mode は初心者 UX の入口を担うにもかかわらずテスト空白
  - **追加**: `tests/test_auto_setup_coverage.py`（**53 件** の新規テスト、490 行）
  - **カバレッジ**: auto_setup.py **9.8% → 97%**（100 stmts 中 97 カバー、30 branches 中 29 カバー）
  - **カバー領域**:
    - Section 1: `should_show_auto_tab_first` マトリクステスト（mode × first_run_completed 6 パラメタ + empty dict）
    - Section 2: `_has_custom_engine_settings` の katago/model/config 別カスタム判定 6 ケース
    - Section 3: `get_auto_setup_config` の既存 / 新規ユーザー / 既存ユーザー×カスタム / 既存ユーザー×標準 4 シナリオ
    - Section 4: `get_packaged_engine_defaults` のキャッシュ + コピー独立性 + フォールバック
    - Section 5: `get_model_search_dirs` の user 自動作成 + package 包含
    - Section 6: `find_lightweight_model` の単一候補 / 複数候補（タイムスタンプ + mtime フォールバック）/ 空ディレクトリ
    - Section 7: `_is_likely_opencl_binary` の opencl/cuda/tensorrt 7 パラメタ
    - Section 8: `find_cpu_katago` の OpenCL 拒否 + Windows .exe 拡張子
    - Section 9: `resolve_auto_engine_settings` の success / failure / EngineTestResult インスタンス
    - Section 10: `prepare_reset_to_auto` の mode / first_run_completed / last_test_result
  - **テスト合計**: 419 → **472 PASS**（既存 419 件不変 + 新規 53 件）
  - **アーキテクチャ**: core 層 Kivy 非依存維持。`mypy katrain/core/auto_setup.py` pass
  - **lint/mypy**: ruff pass, mypy pass
  - **アーキテクチャレビュー優先度リスト完遂**: A1 (hints.py) + A2 (auto_setup.py) + A3 (KifunarabeController) を全て解消
  - **スペック**: `docs/archive/specs-implemented/phase189-auto-setup-coverage.md` 新設
- 2026-07-14: Kifunarabe Controller God Class 分割 — Phase 188（Architecture Review Follow-up A3）
  - **背景**: 2026-07-14 アーキテクチャレビューで `katrain/gui/managers/kifunarabe_controller.py` が **800行・32メソッド** の単一 God Class と判定。リリース前から test_kifunarabe_controller.py 568行で網羅済みだが、責務単一性 (SRP) 違反で可読性・テスト容易性が低い
  - **分割**: 単一クラスを **4 mixin + 1 facade** 構成に再編。合計はむしろ +140 行（mixin ヘッダ・型注釈コスト）だが、**facade 単体**は -620 行 (800→180)
    - `KifunarabeSessionMixin` (~200 行) — ライフサイクル: `start_session` / `_end_session` / `disable_if_needed` / `abort_session` / `_finish_position` / `_check_session_ended`
    - `KifunarabeToggleMixin` (~150 行) — Auto toggle save/restore + Hint toggle: `_save_analysis_toggles` / `_apply_kifu_toggle_mask` / `_apply_hint_toggle` / `_do_apply_hint_toggle` / `_schedule_redraw` / `_safe_redraw_board`
    - `KifunarabeGuessMixin` (~280 行) — Guess progression: `handle_guess` / `_record_wrong_guess` / `_play_guessed` / `_auto_advance_until_user_turn` / `_play_move` / `_highlight_critical_3_if_reached`
    - `KifunarabeSummaryMixin` (~130 行) — Summary popup + callback 解決: `_get_show_summary` / `_dismiss_summary_popup_if_open` / `_show_session_summary` / `_get_on_guess_resolved`
    - `KifunarabeController` (facade, ~180 行) — `__init__` + `session` プロパティ + `is_active` / `is_fog_active` + 公開ヘルパー
  - **新規ファイル**: `kifunarabe_state.py` (mypy 用の型注釈集約)
  - **設計判断**:
    - 4 mixin はすべて `object` 派生でスーパークラスゼロ → `super().__init__()` 不要
    - MRO 順序: `Session → Guess → Summary → Toggle` (依存方向に従う)
    - Facade は属性初期化を `__init__` に集約 — 各 mixin は `_session: "KifunarabeSession | None"` の class body 注釈で型と所有権を明示
    - Kivy import は **各 mixin の関数内に遅延 import** のまま維持（Phase 173 教訓遵守）
  - **後方互換**:
    - `from katrain.gui.managers.kifunarabe_controller import KifunarabeController, disable_kifunarabe_if_active, node_move_gtp` の既存 import 全て無修正で動作
    - `KifunarabeController` の公開 API (`start_session` / `disable_if_needed` / `abort_session` / `on_mode_change` / `handle_guess` / `session` / `is_active` / `is_fog_active`) 全て維持
    - 既存 test_kifunarabe_controller.py (568 行 / 10 クラス) 無修正で PASS
    - 7 + 5 件のテスト失敗は **Kivy 未インストールのローカル環境制約**（CI で Kivy ありのため通過確認済 — main で同じテストが落ちることを stash 比較で確認）
  - **新規テスト**: `tests/test_kifunarabe_mixins.py` (24 件 / 5 セクション)
    - Section 1: `_safe_redraw_board` の優先順位カスケード + エラーハンドリング (5 件)
    - Section 2: `_expected_gtp_from_node` の None / edge ケース (5 件)
    - Section 3: `node_move_gtp` モジュールヘルパー (4 件)
    - Section 4: facade MRO + 公開 API surface + state デフォルト初期化 (5 件)
    - Section 5: 各 mixin のメソッド所有権と facade-only メソッド保証 (5 件)
  - **lint/mypy**: ruff pass, mypy pass（6 + 1 = 7 files）
  - **テスト合計**: 395 → 419 PASS（既存不変 + 新規 24）
  - **スペック**: `docs/archive/specs-implemented/phase188-kifunarabe-controller-split.md` 新設
  - **効果**: God Class 解消 → 認知負荷減、mixin 単体テスト可能、将来の Phase 190+ リファクタ（個別 mixin 差し替え等）の弾み
- 2026-07-14: Beginner Hints Main Pipeline Coverage — Phase 187（Architecture Review Follow-up A1）
  - **背景**: アーキテクチャレビュー（2026-07-14）で `core/beginner/hints.py` のカバレッジが **16.5%**（124/753 行）と全コア層中最低値であることを特定。Hint priority chain は初心者向け UX の核で、リグレッションリスクが高い
  - **追加**: `tests/test_beginner_hints_main.py`（**137 件** の新規テスト、876 行）
  - **カバレッジ**: hints.py **16.5% → 97%**（238 stmts 中 232 カバー、104 branches 中 99 カバー）
  - **カバー領域**:
    - Section 1: 公開ゲート関数 4 種のマトリクステスト（28 件）
    - Section 2: 内部 extractor `_extract_predicted_territory` / `_extract_best_policy` の None/empty/malformed 防御経路（15 件）
    - Section 3: `_compute_summary_context` の try/except フォールバックと threshold 転送（8 件）
    - Section 4: `_is_endgame_position` の scoreStdev 動的判定 + move_number 静的フォールバック（5 件）
    - Section 5: `get_beginner_hint_cached` / `get_summary_hint_cached` の 4 次元 cache invalidate シナリオ（flags / require_reliable / user_weak_tags / curator_min_occurrences）（11 件）
    - Section 6: `compute_beginner_hint` の `pass move` / `root node` / `no parent` 早期リターンと finally-block 復元（5 件）
    - Section 7: `compute_summary_hint` の priority chain と各フラグ OFF 動作（10 件 + 新規 CURATOR 統合 4 件）
    - Section 8: `HintCategory` 全 23 カテゴリの i18n 統合性チェック（50+ パラメタライズド）
    - Section 9: 内部定数（`MIN_RELIABLE_VISITS` / `MIN_SUMMARY_VISITS` / `_DETECTOR_CATEGORIES` / `_NOT_COMPUTED` sentinel）の sanity check（4 件）
  - **テスト合計**: 539 → **676 PASS**（既存 539 件不変 + 新規 137 件）
  - **アーキテクチャ**: core 層 Kivy 非依存維持（Kivy import 一切なし、Phase 173 教訓遵守）
  - **lint/mypy**: ruff pass, mypy pass
  - **次フェーズ検討**: `hints.py` の 753 行分割（gate / extract / dispatch / cache の 4 関心事を `beginner/hints/` サブパッケージへ）— Lv4 案件として別フェーズで評価
  - **スペック**: `docs/archive/specs-implemented/phase187-hint-main-coverage.md` 新設
- 2026-07-14: None-safety 修正 — Phase 186.1（KataGo 起動直後の TypeError 修正 / ユーザーログ起因）
  - **症状**: KataGo 起動直後（analyze 完了前）に `node.analysis = {"root": None}` な状態が発生し、`get_root_visits` が `if "visits" in root:` で `TypeError: argument of type 'NoneType' is not iterable` を投げていた。Phase 179.1 C2 で自前 `analysis.get(...)` から公開 API `get_root_visits` に切り替えたことが露出原因
  - **修正**: `katrain/core/analysis/logic_difficulty.py:243` の `analysis.get("root", {})` を `analysis.get("root") or {}` に置換。同じく `rootInfo` 側 (`:237`) も同様に修正。None と {} の両方を安全に扱う
  - **回帰テスト**: `tests/test_get_root_visits_none_safety.py` 新設 20 件（None / empty dict / root=None / rootInfo=None など 9 パラメタライズ + 正常系 + SummaryHintContext + compute_summary_hint）
  - **テスト合計**: 519 → **539 PASS**
  - **lint/mypy**: pass
- 2026-07-14: Curator 集約統合 — Phase 186（棋譜全体の弱点パターンを Hint に統合）
  - **背景**: Phase 179 audit で保留した「Curator 集約統合」を実装。バッチ解析で蓄積されたユーザーの弱点プロファイルを Beginner Hint として表示
  - **追加**: `HintCategory` に 1 enum（`CURATOR_WEAK_AXIS`）。総計 22 → 23 カテゴリ
  - **新規ファイル**: `core/curator/profile.py`（`CuratorProfile` dataclass + `load_curator_profile()` ローダー）、`core/beginner/detector_curator.py`（pure detector）
  - **既存拡張**: `compute_summary_hint` / `get_summary_hint_cached` に `user_weak_tags` / `curator_min_occurrences` パラメータ追加。priority chain の最下層に統合
  - **キャッシュキー**: `user_weak_tags` と `curator_min_occurrences` を含めて、Curator プロファイル切り替え時に必ずキャッシュ invalidate
  - **設定**: `beginner_hints: {curator_hint}` 1 トグル追加（デフォルト ON）
  - **Settings UI**: Analysis タブに 1 チェックボックス追加（master の下に indent 配置）
  - **i18n**: jp/en 各 5 キー追加（3 hint × 1 suffix + 2 settings）。`.mo` 再生成済
  - **テスト**: `tests/test_beginner_hints_summary.py` に 33 件追加。合計 217 件 PASS
  - **アーキテクチャ**: core 層 Kivy 非依存維持。`test_architecture.py` pass。`mypy katrain/core/{beginner,curator}/` pass
  - **GUI 統合の余地**: `controlspanel.py` の `_summary_hint_flags` は `curator_hint` フラグを渡せるが、`user_weak_tags` の GUI 側読み込み（CuratorProfile のキャッシュ機構）は別タスク。Phase 186 ではコア層のみ実装
- 2026-07-14: Ownership / Policy 派生ヒント — Phase 182（KataGo `ownership` / `policy` データから 3 カテゴリ追加）
  - **背景**: Phase 179 audit で保留した OWNERSHIP_INFLUENCE / POLICY_CONFLICT を実装。KataGo の predicted territory と policy 分布を活用した初心者の状況把握を強化
  - **追加**: `HintCategory` に 3 enum（`OWNERSHIP_DOMINANT` / `POLICY_CONFLICT` / `POLICY_CONFIDENT`）。総計 19 → 22 カテゴリ
  - **新規ファイル**: `core/beginner/detector_ownership.py`, `detector_policy.py`（各 Kivy 非依存の pure detector）
  - **既存拡張**: `SummaryHintContext` に `predicted_territory` / `best_policy` / 関連閾値フィールド追加、`_compute_summary_context` で抽出ヘルパー `_extract_predicted_territory` / `_extract_best_policy` を追加
  - **priority chain**: 最下層に追加（既存 Specific / Summary hint より後）。POLICY_CONFIDENT (severity 0) > POLICY_CONFLICT (severity 1) の順序
  - **設定**: `beginner_hints: {summary_ownership, summary_policy}` 2 トグル追加（デフォルト ON）
  - **Settings UI**: Analysis タブに 2 チェックボックス追加（master の下に indent 配置）
  - **i18n**: jp/en 各 13 キー追加（9 hint × 3 suffix + 4 settings）。`.mo` 再生成済
  - **テスト**: `tests/test_beginner_hints_summary.py` に 42 件追加（3 detector × 5-7 テスト + extract helper + priority chain + i18n）。合計 184 件 PASS
  - **アーキテクチャ**: core 層 Kivy 非依存維持。`test_architecture.py` pass。`mypy katrain/core/beginner/` pass
  - **次回検討**: Hint Popup 化 / H キー手動表示 / Curator 集約統合
- 2026-07-14: Beginner Hints Summary Extension — Phase 179 + Phase 179.1 + Phase 179.2（ミス・自由度・難易度の Hint 統合 + KataGo 未使用データ派生 9 カテゴリ + 監査発見の品質改善）
  - **Phase 179.1（Critical + Minor まとめ）**:
    - **C1 修正**: `get_summary_hint_cached` のキャッシュキーに `require_reliable` を含める（信頼性ゲート切替時の誤ヒットバグ修正）
    - **C2 修正**: `analysis.get("rootInfo")` / `analysis.get("root")` 自前実装を `get_score_stdev` / `get_root_visits` 公開 API 経由に置換
    - **m1**: テスト名 `test_total_hint_categories_is_ten` → `is_nineteen` リネーム + docstring 強化
    - **m2**: `detector_mistake.py` の未使用 `_ensure_typed_dict` / `typing.Any` 削除
    - **m3**: `controlspanel.py` の `category_keys` / `fallbacks` 二重 dict（62 行）を `HintCategory.i18n_namespace` / `fallback_title` / `fallback_body` の 3 property に集約（-45 行）
  - **Phase 179.2（Medium 改善）**:
    - **M1**: `_is_endgame_position` を `scoreStdev <= 8.0`（`ENDGAME_SCORE_STDEV_THRESHOLD`）ベースの動的判定に変更。`move_number >= 200` はフォールバック。中盤の持久戦での MISTAKE_GOOD 誤発火を排除
    - **M2**: `controlspanel.py` と `detector_freedom.py` の二重 candidate counting を `count_freedom_candidates` ヘルパーに統合（-30 行 / +20 行）。閾値定数 `GOOD_REL_THRESHOLD` / `NEAR_REL_THRESHOLD` を `detector_freedom.py` に昇格
    - **M3**: KATAGO_UNCERTAIN の内部 visits gate を 200 → 300 に引き上げ（Monte-Carlo ノイズによる誤検知抑制）。外側 MIN_SUMMARY_VISITS=100 は維持（2 tier gate）
    - **M4**: `mykatrain:settings:beginner_hints_desc` (jp/en) に Phase 179 拡張（mistake / freedom / difficulty / katago 不確実性）の説明を追加
  - **テスト**: `tests/test_beginner_hints_summary.py` に 13 件追加（C1/C2/m3 + M1/M2/M3 regression）。合計 142 件 PASS
  - **アーキテクチャ**: core 層 Kivy 非依存維持。`test_architecture.py` pass。`mypy katrain/core/beginner/` pass
  - **i18n**: `.po` / `.mo` 更新済
  - **背景**: ユーザー要望「右下のミス・手の自由度・局面難易度の数値から初心者向けヒントみたいなテンプレート機能」
  - **追加**: `HintCategory` に 9 enum（`MISTAKE_BLUNDER/MISTAKE/GOOD`, `FREEDOM_ONLY_MOVE/NARROW/WIDE`, `DIFFICULTY_TRICKY/CALM`, `KATAGO_UNCERTAIN`）
  - **新規ファイル**: `core/beginner/detector_mistake.py`, `detector_freedom.py`, `detector_difficulty.py`, `detector_katago.py`（各 +50〜80 行、Kivy 非依存の pure detector）
  - **既存拡張**: `HintCategory.is_structural/is_meaning_tag/is_summary/config_key` プロパティ追加、`SummaryHintContext` dataclass 新設
  - **優先度チェーン**: 3 層化（Specific → Summary、Layer 内 priority chain）。既存 10 カテゴリ完全不変
  - **設定**: `beginner_hints: {summary_mistake, summary_freedom, summary_difficulty, katago_uncertain}` 4 トグル追加（デフォルト ON）
  - **Settings UI**: Analysis タブに 4 チェックボックス追加（master の下に indent 配置）
  - **i18n**: jp/en 各 35 キー追加（27 hint × 3 suffix + 8 settings）。`.mo` 再生成済
  - **表示形式**: 既存数値行（`ミス: 悪（N点損）` 等）は保持、Hint 行を 1 行追加で併記
  - **テスト**: `tests/test_beginner_hints_summary.py` 新規（680 行 / 65 テスト）。既存 `tests/test_beginner_hints.py`（64 件）は全件 PASS のまま拡張（HintCategory total=19 に更新のみ）
  - **アーキテクチャ**: core 層 Kivy 非依存維持。`test_architecture.py` 通過。`mypy katrain/core/beginner/` 通過
  - **仕様書**: `docs/archive/specs-implemented/phase179-hints-summary-extension.md` 新規
  - **次回検討**: Hint Popup 化 / H キー手動表示 / 候補手単位 Hint / Curator 集約統合
- 2026-07-11: Phase 173 — CI exit-102 修正（部分）: kivy 遅延 import で FileExistsError 解消
  - 根本原因: `katrain/gui/features/commands/game_commands.py:12` で
    `from kivy.clock import Clock` をモジュールレベルで行っていた。
    Kivy の `__init__.py` は副作用として `~/.kivy` と `~/.kivy/mods`
    を mkdir する。GitHub Actions の Ubuntu-24.04 ランナーは連続
    ジョブ間でストレージを再利用するため、2 番目のジョブが
    `FileExistsError` → pytest が exit code 102 として送出
  - 修正: `game_commands.py` の `Clock` import を `do_new_game`
    関数内に移動。TYPE_CHECKING ブロックに静的解析用を残置
  - 同様修正: `katrain/gui/features/karte_export.py` — 7 個の
    Kivy primitive (`Clock`, `Clipboard`, `dp`, `BoxLayout`,
    `Button`, `Label`, `Popup`) を全て関数内に移動
  - テスト: `tests/test_dispatch_table.py` に 4 件の回帰テスト追加
    - AST scan: モジュールレベルで kivy import がないこと
    - os.mkdir monkey-patch: kivy mkdir が走らないこと
  - 既知の残存問題: 上記修正後も CI `exit code 102` が発生する場合がある
    (再現条件不明 — ローカル環境では再現せず、3.7 秒間の plugin
    ロード後に即座に死ぬ)。さらなる調査は Phase 174 で実施予定
  - 一方で lint/typecheck/mypy はすべて pass しているため、
    ソースコード品質には影響なし
- 2026-07-11: KaTrainGui ラッパーメソッド全削除（Phase 172）
  - `commands/DISPATCH_TABLE`（35エントリ）への明示的ディスパッチ移行
  - 動的 `getattr(self, f"_do_{...}")` を `_resolve()` ベースに変更し、`message_loop_manager._run()` のメッセージ解決も統一
  - 削除: `KaTrainGui._do_*` メソッド 34個（合計 -117行、`__main__.py` 995→878行）
  - 置換: `__call__()` が `endswith("popup")` のみ判定 → popup側 `Clock.schedule_once` で `dispatch()` 経由 / 非 popup側は従来通り message_queue（`message_loop_manager._run()` も `dispatch()` + `_do_update_state()` 直接呼び出し）
  - 維持: `_do_update_state`（特殊用途、再キュー回避のため直接呼び出し）、`is_fog_active`（KV互換）、`_play_stone_sound`（lambda参照）
  - 内部呼び出し元修正: `SGFManager.new_game_callback`/`GameStateUpdateManager.ai_move`/`start()` の3箇所を `game_commands.do_*` 直接呼出しに変更
  - 呼び出し元修正: `kv/game_popups.kv:301,331` を `root.katrain("analyze-extra", ...)` / `root.katrain("tsumego-frame", ...)` 形式に変更、`popups/quick_config.py:203,222` を `self.katrain("new-game")` に変更
  - 削除 import: `analyze_commands`, `export_commands`, `popup_commands`（`__main__.py` では不要、`dispatch` + `game_commands` のみ残存）
  - 不規則な key→関数対応: `selfplay_setup` → `do_start_selfplay` を `_KEY_TO_FUNC_NAME` で吸収
  - テスト: `tests/test_dispatch_table.py` 新設（14件）— カバレッジ/重複キー/unknown KeyError/dash正規化/ラッパー削除検証
- 2026-07-13: 棋譜並べ機能のドキュメント整備 + Root解析堅牢化 + 終了経路統一（Phase 178）
  - **背景**: 2026-07-13 の READ-ONLY 調査で kifunarabe 機能に3点の課題を確認
    - ドキュメント未整備（Phase 177 の正式仕様書が無い）
    - `_kick_root_analysis` が単発 0.2秒遅延で失敗検知なし（起動直後の Root 解析が空のまま残る可能性）
    - `disable_if_needed()` の呼び出しが `sgf_manager.py:410` の1箇所のみ（将来 exit-path 追加時の不整合リスク）
  - **修正**:
    - `kifunarabe_setup_popup.py:_kick_root_analysis`: 単発遅延 → 最大 5 回 × 0.5秒のリトライ + `node.analysis_exists` 早期リターン + 失敗時の level=1 ログ
    - `kifunarabe_controller.py`: `disable_kifunarabe_if_active(katrain)` 司令塔ヘルパー追加
    - `sgf_manager.py:408-410`: 3 行の重複ロジックを 1 行のヘルパー呼び出しに置換
  - **ドキュメント**: `docs/01-roadmap.md` に Phase 178 章追加、`docs/archive/specs-implemented/phase177-kifunarabe.md`（新規 250 行）、AGENTS.md フェーズ一覧に追記
  - **テスト**: `tests/test_kifunarabe_disable_helper.py`（新規 3 件）— 司令塔の挙動を保証
  - **影響**: 既存 70 テストは不変、新規 3 テスト追加で合計 73 件
- 2026-07-04: Leela エンジン完全削除（Phase 171）
  - コード、設定、UI、i18n、テスト、ドキュメントを KataGo 専用に整理
  - 削除: `core/leela/` ディレクトリ（1459 行）、`gui/leela_manager.py`、`gui/features/settings_popup_tabs/leela_tab.py`、`gui/features/resign_hint_popup.py`、`core/batch/leela_gate.py`、`core/analysis/engine_compare.py`、`EngineType.LEELA`、`LeelaConfig` / `get_leela_config()` / `update_leela_config()`、`LeelaEngine` / `LeelaCandidate` / `LeelaPositionEval` / `parse_lz_analyze`、`leela_loss_est` フィールド、`is_single_engine_snapshot` / `MixedEngineSnapshotError` / `KARTE_ERROR_CODE_NON_KATAGO`、`needs_leela_warning` / `needs_leela_karte_warning`、`LEELA_*` 定数（TOP_MOVE_*、COLOR_*、K_* 等）、`leela/enabled` 設定、Settings の Leela タブ・エンジン選択肢
  - 保持: KataGo 解析・エンジン・UI は完全にそのまま動作
  - 後方互換: 古い config.json に `leela` セクションが残っていても無視される（KataGo 解析は KataGo セクションを読む）
  - テスト削除: 25 ファイル / 約 3700 行
  - i18n 削除: en/jp 合わせて約 70 msgid（`.mo` 再コンパイル済み）
- 2026-07-03: Leela 対局機能の再廃止（Phase 170）
  - 人間 vs Leela 対局を Phase 123 以来の "解析のみ" 状態に戻す
  - 削除: `AI_LEELA` 定数、`compute_leela_enabled()`、`LeelaStrategy` クラス、`LeelaConfig.play_enabled` / `play_visits`、`LeelaEngine.play_move` / `request_move`、Settings の "Leelaと対局する" チェックボックス、関連 i18n 文字列（`leela:play:*` / `ai:leela` / `aihelp:ai:leela`）、`LeelaManager.start_engine(force=...)` の `force` 引数
  - 保持: Leela 解析機能（変化図・loss 推定・カルテ等）、`EngineType.LEELA` enum、`lz-analyze` / `LZ` プロパティ（GTP プロトコル由来）
  - 既存ユーザ設定の `play_enabled` / `play_visits` は `LeelaConfig.from_dict` で無視（後方互換）
- 2026-07-03: Leela Zero 表記を Leela に統一（人間棋譜学習版との混同回避）
  - docstring・コメント・docs の "Leela Zero" / "Leela 0.110" を "Leela" に統一（13 箇所）
  - GTP プロトコル由来の `lz-analyze` / `LZ` プロパティ、内部識別子（`AI_LEELA`, `EngineType.LEELA` 等）は変更せず
- 2026-06-29: Curator テスト追加 + settings_popup.py 分割 + Dead Code 削除（Phase 158-E / PR #321）
  - curator/ カバレッジ 0% → 92%、settings_popup.py -243 行、新規テスト 148 件
- 2026-06-26: AGENTS.md として再構成（旧 CLAUDE.md から移行、スキルを on-demand 化）
- 〜2026-06-25: CLAUDE.md（Phase 142 まで）に記録された全 Phase
