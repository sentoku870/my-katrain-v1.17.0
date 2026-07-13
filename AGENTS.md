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
- **完了**: Phase 1-192
- **直近のマイルストーン**:
  - Phase 171（2026-07-04）: Leela エンジン完全削除、KataGo 専用に整理
  - Phase 177（2026-07-12）: 棋譜並べ（kifunarabe）機能追加
  - Phase 179 + 179.1 + 179.2（2026-07-14）: Beginner Hints Summary Extension（ミス・自由度・難易度）+ 監査改善
  - Phase 182（2026-07-14）: Ownership / Policy 派生ヒント
  - Phase 186（2026-07-14）: Curator 集約統合（棋譜全体の弱点パターンを Hint 化）
  - Phase 187-192（2026-07-14〜16）: Architecture Review Follow-up（A1-A4 / B1-B2）

  各 Phase の詳細は `docs/archive/specs-implemented/phase*.md` を参照。
- **次**: TBD（計画中）

全体ロードマップは `docs/01-roadmap.md` を参照。

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

### 3.4 シェル権限ルール（opencode.jsonc）
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

> 直近 3 ヶ月の主要 Phase のみ記載。Phase 1-169 の詳細は `docs/archive/CHANGELOG.md` および `docs/archive/ROADMAP_HISTORY.md` を参照。各 Phase の詳細スペックは `docs/archive/specs-implemented/phase*.md` に格納。

- 2026-07-16: **Phase 193 — Documentation cleanup**
  - Leela 関連スペック 2 ファイル削除（`leela-estimated-loss.md` / `leela-output-format.md`、Phase 171 で実装削除済）
  - `AGENTS.md §3.4 / §3.5`（Phase 36/37 の Leela フォールバック / 混合エンジン検出）削除
  - `AGENTS.md §1.3` を Phase 1-192 主要マイルストーン簡潔化、`§10` を 3 ヶ月に圧縮
  - `docs/01-roadmap.md` に Phase 171-192 章追加、最終更新日を 2026-07-16 に修正
  - `docs/02-code-structure.md` 全面再構成（addendum マージ、Phase 171-192 の構造反映、Leela 系コード言及全削除）
  - `docs/archive/specs-implemented/README.md` を最新化（Phase 83-192 一覧追加）
- 2026-07-16: Phase 192 — Position Difficulty サブパッケージ化（`core/analysis/difficulty/` 6 モジュール化、後方互換シム維持）
- 2026-07-15: Phase 191 — Engine Subsystem TYPE_CHECKING 循環解消（`core/_engine_types.py` に集約）
- 2026-07-15: Phase 190 — `core/engine.py` カバレッジ 48.3% → 83%（59 件追加）
- 2026-07-15: Phase 189 — `core/auto_setup.py` カバレッジ 9.8% → 97%（53 件追加）
- 2026-07-14: Phase 188 — Kifunarabe Controller God Class 分割（4 mixin + facade、800→180 行、24 テスト追加）
- 2026-07-14: Phase 187 — Beginner Hints Main Pipeline カバレッジ 16.5% → 97%（137 件追加）
- 2026-07-14: Phase 186.1 — KataGo 起動直後の TypeError 修正（`get_root_visits` の None-safety、20 件追加）
- 2026-07-14: Phase 186 — Curator 集約統合（棋譜全体の弱点パターンを Hint に統合、`HintCategory` 23 カテゴリ）
- 2026-07-14: Phase 182 — Ownership / Policy 派生ヒント 3 カテゴリ追加
- 2026-07-14: Phase 179 + 179.1 + 179.2 — Beginner Hints Summary Extension（ミス・自由度・難易度、9 カテゴリ + 監査改善）
- 2026-07-13: Phase 178 — kifunarabe ドキュメント整備 + Root 解析堅牢化 + 終了経路統一
- 2026-07-11: Phase 173 — CI exit-102 修正（部分）: kivy 遅延 import で FileExistsError 解消
- 2026-07-11: Phase 172 — KaTrainGui ラッパーメソッド全削除（DISPATCH_TABLE への明示的ディスパッチ）
- 2026-07-04: Phase 171 — **Leela エンジン完全削除**（`core/leela/` 1459 行削除、KataGo 専用化、i18n 70 msgid・テスト 25 ファイル削除）
- 2026-06-26: AGENTS.md として再構成（旧 CLAUDE.md から移行、スキルを on-demand 化）
