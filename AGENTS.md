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
- **完了**: Phase 1-170（解析基盤、カルテ、リファクタリング、Guardrails、SGF E2Eテスト、LLM Package Export、レポート導線改善、Settings UI拡張、Smart Kifu運用強化、Diagnostics、解析強度抽象化、Leela→MoveEval変換、レポートLeela対応、エンジン選択設定、UIエンジン切替、Leelaカルテ統合、Leelaバッチ解析、テスト強化、安定化、エンジン比較ビュー、PLAYモード、コード品質リファクタリング、Batch Core Package完成、Stability Audit、Batch Analysis Fixes、Lexicon Core Infrastructure、Meaning Tags System Core、Meaning Tags Integration、5-Axis Radar Data Model、Radar Aggregation & Summary Integration、Critical 3 Focused Review Mode、Radar UI Widget、Tofu Fix + Language Code Consistency、Stabilization、Batch Report Quality、Report Quality Improvements、Report Foundation + User Aggregation、Style Archetype Core、Style Karte Integration、Time Data Parser、Pacing & Tilt Core、Pacing/Tilt Integration、Risk Context Core、Risk統合、Curator Scoring、Curator出力、Post-54統合テスト、Post-54品質強化、Engine Stability、Command Pattern、Parser/Base Test Enhancement、Complex Function Refactoring、batch/stats.py分割、karte_report.py分割、KaTrainGui分割A-KeyboardManager、KaTrainGui分割B-ConfigManager、KaTrainGui分割C-PopupManager、KaTrainGui分割D-GameStateManager、エラーハンドリング監査、エラーハンドリングB、エラーハンドリングC、共通基盤、Ownershipクラスタ抽出、Cluster Classifier、Complexity Filter、Recurring Pattern Mining、Pattern to Summary Integration、Reason Generator、Signature Player Axis、Batch UI Consistency、Leela Batch Output Fix、KataGo Settings UI Reorg + humanlike Toggle、Auto Setup Mode、Error Recovery & Diagnostics、Beginner Hints MVP、Beginner Hints Extension、Active Review MVP、Active Review Extension、Stability Improvements、SummaryManager抽出、ActiveReviewController抽出、QuizManager抽出、ConfigStore基盤、Read-side Config Migration、TypedConfigWriter更新API、update_*_config()移行、StateNotifier基盤、Notifier統合、Notifier発火ポイント追加、UI Subscribe MVP、KaTrainGui Subscribe、mypy導入、core/state strict + 型エラー修正、core型エラー修正第1弾、gui/features型エラー修正、mypy strict全体・CIブロック、Python 3.11 modern syntax migration、Forward Reference + i18n + Semantic Type Fixes、Pre-existing型エラー修正＋Top Moves色回帰修正、Phase 138-D アーキテクチャ改善、Game 4分割、kivyutils分割、popups分割、commands/委譲、Phase 158+ AI strategies・engine・badukpan 分割、Phase 159A Karte/Summary の KataGo-only 化、Phase 170 人間 vs Leela 対局機能の再廃止）、**Phase 171（Leela エンジン完全削除）**、**Phase 178（棋譜並べ機能ドキュメント整備 + Root解析堅牢化 + 終了経路統一）**
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
