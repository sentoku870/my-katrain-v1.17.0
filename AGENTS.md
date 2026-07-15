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
- **完了**: Phase 1-225 + 225.1 + 225.2 + 225.3 + 225.4 + 225.5 + 225.6 + 225.7 + 225.8 + 226-A + 226-B + 226-C + 226-D + 226-E + 226-F (F-A) + 226-H + 226-I
- **直近のマイルストーン**:
  - Phase 171（2026-07-04）: Leela エンジン完全削除、KataGo 専用に整理
  - Phase 177（2026-07-12）: 棋譜並べ（kifunarabe）機能追加
  - Phase 179 + 179.1 + 179.2（2026-07-14）: Beginner Hints Summary Extension（ミス・自由度・難易度）+ 監査改善
  - Phase 182（2026-07-14）: Ownership / Policy 派生ヒント
  - Phase 186（2026-07-14）: Curator 集約統合（棋譜全体の弱点パターンを Hint 化）
  - Phase 187-192（2026-07-14〜16）: Architecture Review Follow-up（A1-A4 / B1-B2）
  - Phase 193（2026-07-16）: ドキュメントクリーンアップ
  - Phase 194-196（2026-07-17）: MagicMock 汚染除去 + 互換シム棚卸し + hints.py サブパッケージ化
  - Phase 197-202（2026-07-17）: 各種サブパッケージ化 + AppContext + リファクタリング
  - Phase 203（2026-07-17）: LLM「翻訳特化」導入 調査ドキュメント（D 案: ドキュメント整備のみ）
  - Phase 207-213（2026-07-17）: `core/coach/` パッケージ完全実装（master_db / lexicon / symptom_index / tones / prompt_builder / validator / e2e tests、合計 243 unit tests、全 4752 件テスト合格）
  - Phase 214-A（2026-07-17）: LLM coach CLI tool（`core/coach/cli.py`、17 unit tests）
  - Phase 215（2026-07-17）: Karte-aware symptom detection（`core/coach/karte_detector.py`、30 unit tests）
  - Phase 216（2026-07-17）: Streak-based symptom detection（`karte_detector.py` 拡張、17 unit tests）
  - Phase 217（2026-07-17）: Aggregate helpers + CLI `analyze` command（6 unit tests）
  - Phase 218（2026-07-17）: Calibration fixtures（39 unit tests、golden test cases）
  - Phase 219（2026-07-17）: Calibrate CLI command（5 unit tests）
  - Phase 220（2026-07-17）: Trace CLI command（6 unit tests）
  - Phase 221（2026-07-17）: Multi-game summary support（`json_type.py`、18 unit tests + 2 CLI tests）
  - Phase 225（2026-07-17）: **LLM Coach GUI 統合（手動貼付ワークフロー）**（Lv3、9 ファイル + 34 unit tests、全 4882 件テスト合格）
    - `katrain/gui/features/llm_coach.py`: `build_llm_prompt` / `validate_llm_response` / `find_latest_karte` の薄いラッパー
    - `katrain/gui/popups/llm_coach_popup.py` + `katrain/gui/kv/llm_coach_popup.kv`: MyKatrain メニュー「LLM コーチ（手動貼付）」から開く Popup
    - DISPATCH_TABLE に `llm_coach_popup` 追加、menu.kv にメニュー項目追加
    - i18n: `mykatrain:llm-coach:*` 28 個のキー（jp/en .po + .mo 更新済み）

  各 Phase の詳細は `docs/archive/specs-implemented/phase*.md` および `docs/archive/specs-planned/phase*.md` を参照。
- **次**: TBD（Phase 224 OpenAI 互換エンドポイント連携は将来再検討）

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

- 2026-07-15: **fix: settings_popup.py の `MagicMock` NameError を修正**
  - **問題**: ユーザーが設定ポップアップを保存すると `NameError: name 'MagicMock' is not defined` でクラッシュ
  - **原因**: `katrain/gui/features/settings_popup.py:235` で `MagicMock(text="")` がインポートなしに使われていた（テスト用ヘルパが本番コードに混入）
  - **修正**: `MagicMock` の代わりに `type("X", (), {"text": ""})()` の空っぽオブジェクトでフォールバック。`rank_input` が存在しない場合は空文字を返す
- 2026-07-15: **Phase 226-I — LLM コーチ prompt 品質改善（GUI 自動取得フィードバック）**（Lv2、3 ファイル + 4 unit tests）
  - **問題**: ユーザーが LLM Coach popup で「棋力が手動入力」「白黒自動判定が機能しない」と報告。`detect_player_color_for_user` が silent に失敗し、ユーザーに状況を伝える仕組みがない
  - **原因**: `_populate_rank_and_perspective` で `default_user_name` が空の場合、何の警告も出さずに silent 通過。視点も `color=None` で確定せず、perspective_hint にフォールバック表示のみ
  - **修正**: 
    - `default_user_name` が空の場合、status label に「視点自動判定不可: mykatrain 設定の『デフォルトユーザー名』が未設定です」と明示（`auto-detect-no-default-user` i18nキー追加）
    - 既存の `auto-detect-summary` 経路（`default_user_name` 有り）はそのまま動作
  - **今回スコープ外**: 
    - Lexicon YAML 拡張（AGENTS.md マーカーにより慎重に扱うべき、別タスク）
    - voice-summary / symptoms のレベル整合性強化（Phase 226-J として分離予定）
    - Symptom-Lexicon 関連の更なる充実（auto_detected=False の Symptom は現状関連付けのみ、注入経路には乗らない）
  - 4 件 unit tests 追加（default_user 空時警告、有り時サマリ、rank 自動取得ソース、default_user_rank フォールバック）
- 2026-07-15: **Phase 226-H — MeaningTagId を symptom_id ground truth に追加**（Lv2、2 ファイル + 10 unit tests）
  - **問題**: ユーザー報告で LLM 出力の HIGH 警告が誤検知。`life_death_error`, `reading_failure`, `connection_miss`, `overplay`, `endgame_slip` が SymptomId に存在しないという警告だが、これらは **MeaningTagId enum の値**で Karte JSON に正しく書かれている
  - **原因**: validator は SymptomId (30 種類) のみを ground truth としており、MeaningTagId (12 種類) を受け付けなかった。LLM は SymptomId と MeaningTagId を区別せず両方使うので誤検知が頻発
  - **修正**: `_karte_symptom_ids()` で MeaningTagId enum の全値を ground truth に追加。今後 LLM が MeaningTagId 値を書いても HIGH 警告は出ない
  - **注**: LOW 警告（Lexicon 言及）は Lexicon YAML に存在しない用語を書いた場合の挙動として妥当。Lexicon 拡充は別タスク（`docs/resources/go_lexicon_master_last.yaml` の更新）
  - 10 件テスト追加（8 値の parametrize + all-values + 真正 unknown 検証）
- 2026-07-15: **Phase 226-F (F-A) — SymptomContext に current_phase フィールド追加**（Lv3、2 ファイル + 11 unit tests）
  - **問題**: `build_symptom_context_from_karte` が `move_number=None` をハードコード → 5つの phase-gated 症状（FIRST_MOVE_CONFUSION / TOO_MANY_CHOICES / OVERCONCENTRATION / POST_JOSEKI_DIRECTION / ATTACK_WITH_PURPOSE）の `ctx_is_phase()` が常に False → karte 経由で**絶対発火しない**
  - **修正**: `SymptomContext` に `current_phase` フィールド（デフォルト `"unknown"`）を追加、`_infer_current_phase()` ヘルパーで karte の important_moves の move_number 分布から dominant phase を導出、`is_phase()` が `move_number=None` の場合に `current_phase` にフォールバック
  - **影響範囲**: 5症状の detector が karte 経由でも発火可能になる「前提条件」を整える。detector 個別の閾値調整は F-B（Phase 226-G として分離予定）
  - 11 件テスト追加（opening/middle/endgame 推定、board_size スケーリング、`is_phase()` フォールバック、move_number 優先順位）
- 2026-07-15: **Phase 226-E — 軽微な品質改善**（Lv2、6 ファイル + 0 unit tests、全 5116 件テスト合格）
  - **E1 クラス名タイポ修正**: `LLMCcoachPopupContent` → `LLMCoachPopupContent`（3 ファイル 7 箇所: popup.py / KV / test_llm_coach_popup.py）
  - **E2 デッドコード削除**: `_COPY_FEEDBACK_SECONDS` は Phase 226-B 内で既に削除済み（本 Phase で再確認・スキップ）
  - **E3 avg_points_lost 意図省略の明示**: GUI 入力欄は Phase 226 スコープ外（CLI の override ノブはある）。`on_generate_and_copy` の docstring に「Karte の summary.avg_points_lost に委譲」と明記
  - **E4 関西弁定義の同期契約**: 3 系統の AYAKA データ構造（`master_db._KANSAI_DICTIONARY` / `tones._KANSAI_NORMALISATION_PAIRS` / `tones._AYAKA_MARKERS`）間の同期契約を `tones.py` の docstring に明記
  - **E5 rank-auto msgstr 更新**: Phase 225.6 で「SGF から自動取得」だったのを Phase 225.8 で Karte/SGF/設定の 3 ソースに対応した msgstr に更新（jp/en .po + .mo）
  - **E6 仕様書整備**: `docs/archive/specs-implemented/phase225-master.md` 新規作成。Phase 225.1〜225.8 + 226-A〜E の索引として機能
- 2026-07-15: **Phase 226-D — テスト強化・CI 整備**（Lv2、3 ファイル + 6 unit tests、全 5116 件テスト合格）
  - **D1 CI skip 解消**: `test_llm_coach_popup.py` の `pytestmark` を CI 環境変数ベースから「Kivy import 可否」に変更。Kivy がある環境では popup ロジックテスト ~50 件が CI でも実行可能に
  - **D2 validator 境界値テスト追加**: `total_moves` 境界（200 OK / 201 NG）、`ceiling` 境界（7.55 OK / 7.6 NG）の境界値テストを追加
  - **D3 settings_export フィクスチャ更新**: `mock_package_defaults` に `default_user_rank: ""` を追加、`TestTabResetKeys` に `default_user_rank` が export タブに含まれることを検証するテストを追加
- 2026-07-15: **Phase 226-C — LLM コーチ データ・設定不整合の解消**（Lv3、4 ファイル + 6 unit tests、全 5110 件テスト合格）
  - **C1 `_RANK_ALIASES` デッドコード解消**: `_canonical_rank_key` が `_normalise_rank_str` 適用前に alias lookup するようルート変更。`"10段"` が `"10d"` → 存在しない → `None` だった経路を、`"10段"` → alias → `"9d"` → EXPERT で救済
  - **C2 `config.json` に `default_user_rank` 追加**: `mykatrain_settings` のデフォルト値に `default_user_rank: ""` を追加。新規インストール時の一貫性確保
  - **C3 `estimate_mode_from_loss` docstring 修正**: シグナル全不在でも `INTERMEDIATE` を返す実装と、docstring の "None if no signal available" の不一致を解消
  - **C4 `detect_json_type` の精緻化**: karte-shaped 判定（`weaknesses` + 非空 `important_moves`）を summary 判定より優先。`meta.game_count: 1` の single-game karte が誤って summary 判定される問題を修正
  - **C5 `json_type.py` docstring 更新**: C4 の新しい判定順序を反映、3段階ロジック（karte優先 → game_count/games_analyzed → players → phase_x_mistake フォールバック）を明記
  - 累計 6 件回帰テスト追加（rank aliases +2, json_type +4）、合計 5110 件テスト合格
- 2026-07-15: **Phase 226-B — LLM コーチ GUI 堅牢性・バグ修正**（Lv3、3 ファイル + 8 unit tests、全 5104 件テスト合格）
  - **B1 無限再試行ループの解消**: `_populate_rank_and_perspective` が karte_path 空時に `Clock.schedule_once` で無限再試行していた問題を修正。最大再試行回数（5回）を追加し、`on_dismiss` で保留中 Clock イベントをキャンセルする `cancel_pending_clocks` 機構を導入
  - **B2 ハードコード日本語の i18n 化**: `auto-detect-summary` メッセージ内の `"黒 (B)" / "白 (W)"` を i18n キー（`perspective-black` / `perspective-white`）に置き換え。en ロケールで日本語が混入する問題を解消
  - **B3 Spinner 安定内部値の導入**: Spinner の `text`（ローカライズ文字列）を表示専用とし、内部値（`"auto"/"B"/"W"`）を `perspective_value` で保持。`startswith("黒")` 判定を廃止し、`_spinner_text_to_internal` ヘルパーで逆マッピング
  - **B4 detect_player_info のキャッシュ化**: `detect_player_color_for_user` が `player_info` 引数を受け取り、同一 JSON の2回読み込みを解消
  - **B5 例外表示の統一**: `detect_player_color_for_user` の例外を黙殺せず、`auto-detect-failed` ステータスで表示するよう統一
  - デッドコード `_COPY_FEEDBACK_SECONDS` 削除
- 2026-07-15: **Phase 226-A — LLM コーチ機能 検証ロジック強化**（Lv3、2 ファイル + 26 unit tests、全 5096 件テスト合格）
  - **A1 Lexicon 検証の実働化**: `_extract_lexicon_mentions` が英 ID と日本語語句の不整合で常に空を返していた問題を修正。`lexicon.build_id_to_ja_term_map()` ヘルパーで id→ja_term 逆引きを構築し、注入 lexicon 外の「」語句を `lexicon_mention_not_injected` (LOW) で警告生成
  - **A2 症状 ID 抽出の 3 段階フォールバック**: 従来の行末 `参照した症状ID: [...]` (tier 1) に加え、インライン `症状: / Symptoms:` (tier 2) と全文 grep セーフティネット (tier 3) を追加。LLM が指示形式を無視しても捕捉可能
  - **A3 着手番号正規表現の厳格化**: prefix/suffix 両 optional で任意整数にマッチしていた問題を修正。`#50` / `move 50` / `50手目` のみ捕捉し、`5段` / `30級` / `2026年` / `7月` / `50%` を除外
  - **A4 pointsLost 正規表現の拡張**: `目` suffix 必須から、`損失` / `ロス` / `points lost` / `loss` にも対応
  - **A5 player_color 整合性検証（Phase 225.7 仕様）**: `config.player_color` 設定時、相手色の症状 ID 参照を HIGH → MEDIUM に降格（`symptom_id_belongs_to_opponent` kind）
  - **A6 tolerance パラメータ活用**: デッドパラメータだった `tolerance: float = 0.05` を `ceiling + tolerance` 比較に適用し、境界値での偽陽性を防止
  - `_injected_lexicon_ids` デッドコード削除、未使用 `SymptomId` import 削除
- 2026-07-17: **Phase 225.8 — 漢字段級サポート + mykatrain settings に default_user_rank 追加**
  - **挙動バグ**: SGF BR/WR から取得した「4段」漢字段級が `estimate_mode_from_rank` で None 扱い → LOSE フォールバックで BEGINNER モード。`_RANK_ALIASES` テーブルと `_normalise_rank_str` ヘルパーで全角数字・漢字 suffix (段/級) 対応
  - **新機能**: mykatrain settings に `default_user_rank` フィールド追加、デフォルトユーザー名の直下に配置。LLM Coach が Karte/SGF からランク取得できない時のフォールバック
  - 49 件回帰テスト追加（rank aliases 44 件 + default_user_rank 4 件 + settings savers 1 件）、累計 5070 件テスト合格
- 2026-07-17: **Phase 225.7 — Popup 幅拡大 + 自動判定タイミング修正 + LLM 応答はみ出し修正**
  - **UI バグ (Phase 225.6 対策不完全)**: `_populate_rank_and_perspective` が Clock.schedule_once(0) で karte_path 設定前に走っていた → 0.2s 遅延 + karte_path 空時のリトライ機構
  - **UI バグ**: ポップアップ幅が狭く LLM 応答がはみ出す / ボタンと重なる → 900x720 に拡大 + response_input を ScrollView で囲み、折り返しではなくスクロール
  - **UX 改善**: status_label に「デフォルトユーザー '{user}' / 黒:{black} 白:{white} → {color}」サマリ表示 → 自動判定がどちらの色にマッチしたか可視化
  - 4 件回帰テスト追加、累計 5021 件テスト合格
- 2026-07-17: **Phase 225.6 — LLM Coach 視点自動判定 + SGF 棋力自動取得**
  - **新機能**: SGF BR/WR を抽出する `sgf_player_info.py` 追加（17 テスト）
  - **新機能**: Karte JSON meta に `player_info.{black,white}.{name,rank}` 追加（schema 後方互換、golden 3 件更新）
  - **新機能**: `PromptConfig.player_color` 追加、`build_translation_prompt` が SystemInstruction に `PlayerColor: black/white/unknown` を出力（10 テスト）
  - **新機能**: LLM Coach GUI に視点スピナー（Auto/黒/白）+ 棋力自動表示（18 テスト）
  - **新機能**: `default_user_name` からプレイヤー色を自動判定する `detect_player_color_for_user` ヘルパー
  - i18n 7 キー追加 (jp/en): rank-auto、perspective-{label,auto,black,white,auto-detected,auto-fallback}
  - 累計 5017 passed (4968 baseline + 49 件新規)
- 2026-07-17: **Phase 225.5 — LLM Coach status/result stale ref 修正 + 検証サマリ件数表示 + 参照ダイアログ必ず閉じる**
  - **挙動バグ**: Phase 225.3 で `_read_text` を ids 経由に変更したが `_set_status` / `_set_result` は旧 `self.status_label` / `self.result_label` を直接参照 → Kivy ObjectProperty の stale reference で ScrollView 内の result_label.text が反映されず「検証結果コピー」ボタンが常に「コピーできる検証結果がありません」になる
  - **挙動バグ**: `_on_success` で chosen 空のとき `picker.dismiss()` を呼ばず早期 return → ユーザーがブラウザ選択なしで OK を押すとダイアログが閉じず「押しても反応しない」
  - **UX 改善**: 検証実行時に status_label に **件数サマリ**を表示（スクロール不要で高/中/低 件数を把握）
  - 修正: 全 setter を `self.ids` 経由に統一 / picker.dismiss() を全パスで呼ぶ
  - 7 件テスト追加（stale property での ids 上書き / dismiss 確実性 / 件数カウント）、累計 4968 件テスト合格
- 2026-07-17: **Phase 225.4 — LLM Coach ボタン幅完全固定 + 使い方ヒント表示**
  - **UI バグ (Phase 225.3 対策不完全)**: `AutoSizedRoundedRectangleButton` の `width: root.label.texture_size[0]` バインディングが size_hint_x を上書き → `SizedRoundedRectangleButton` (Auto なし) に変更で完全固定
  - **UX 改善**: 「検証実行」「検証結果をコピー」の使い方を説明する workflow-hint Label を Popup 上部に追加（jp/en）
  - 3 件回帰テスト追加（AutoSized 禁止契約 + 5 ボタン全部 Sized + hint 存在）、累計 4961 件テスト合格
- 2026-07-17: **Phase 225.3 — LLM Coach ボタン整列 + ids 経由テキスト読み出し**
  - **UI バグ**: `AutoSizedRoundedRectangleButton` がテキスト幅で自動サイズ調整されボタンが不揃い → KV レイアウト再設計（75/25, 50/50 比率、`size_hint_x: 0.5` 統一）+ 結果ラベルを `ScrollView` 化
  - **クリック無反応バグ**: `self.karte_path_input.text` が KivyMD の ObjectProperty バインド遅延で空文字を返す稀ケース → `_read_text(widget_id)` ヘルパーで `self.ids` 経由の堅牢な参照に変更
  - 16 件回帰テスト追加（KV 静的解析 + ids fallback）、累計 4958 件テスト合格
- 2026-07-17: **Phase 225.2 — `karte_export.copy_path` Clock NameError + LLM Coach 「参照」ボタン修正**
  - **既存バグ**: Phase 173 の `do_export_karte_ui` lazy-import から `Clock` が漏れていたため、エクスポート成功 popup の「コピー」ボタンクリックで `NameError: 'Clock' is not defined`
  - **Phase 225 自バグ**: LLM Coach の「参照」ボタンのハンドラが `I18NFileBrowser` の `on_submit`（ダブルクリックイベント）にしかバインドされておらず、OK ボタンを押しても反応しなかった
  - 修正: lazy-import に `Clock` 追加 / `on_success` と `on_submit` の両方にハンドラをバインド
  - 5 件回帰テスト追加（Clock 検証 + browse ボタン両イベント bind + OK 経由のパス反映）、累計 4942 件テスト合格
- 2026-07-17: **Phase 225.1 — `do_export_karte` Phase 172 引数抜け TypeError 修正**
- 2026-07-17: **Phase 225 — LLM Coach GUI 統合（手動貼付ワークフロー）**（Lv3、9 ファイル + 34 unit tests、累計 4882 件テスト合格）
- 2026-07-16: **Phase 193 — Documentation cleanup**
  - Leela 関連スペック 2 ファイル削除（`leela-estimated-loss.md` / `leela-output-format.md`、Phase 171 で実装削除済）
  - `AGENTS.md §3.4 / §3.5`（Phase 36/37 の Leela フォールバック / 混合エンジン検出）削除
  - `AGENTS.md §1.3` を Phase 1-192 主要マイルストーン簡潔化、`§10` を 3 ヶ月に圧縮
  - `docs/01-roadmap.md` に Phase 171-192 章追加、最終更新日を 2026-07-16 に修正
  - `docs/02-code-structure.md` 全面再構成（addendum マージ、Phase 171-192 の構造反映、Leela 系コード言及全削除）
  - `docs/archive/specs-implemented/README.md` を最新化（Phase 83-192 一覧追加）
- 2026-07-17: **Phase 221 — Multi-game summary support**（Lv2）
  - `katrain/core/coach/json_type.py`: `detect_json_type()` で karte/summary 自動判別
  - `normalize_summary_to_karte_shape()`: summary JSON を karte shape に投影
  - CLI コマンドが summary を自動検出して処理
  - 18 件単体テスト + 2 件 CLI 統合テスト、累計 4855 件テスト合格
- 2026-07-17: **Phase 220 — Trace CLI command**（Lv1）
  - CLI `trace <karte.json>` 新コマンド（検出器パイプラインをソース別に可視化）
  - per_move / weakness_category / streak / aggregate の 4 系列を表示
  - 各 SymptomId がどの source で発火したかを表示（debug 用）
  - 6 件 CLI テスト追加、累計 4837 件テスト合格
- 2026-07-17: **Phase 219 — Calibrate CLI command**（Lv1）
  - CLI `calibrate [--fixture <name>] [--out <path>]` 新コマンド
  - Phase 218 fixtures を実行して pass/fail レポート（CI 親和、exit code 0/1）
  - 5 件 CLI テスト追加、累計 4831 件テスト合格
- 2026-07-17: **Phase 218 — Calibration fixtures**（Lv2）
  - `katrain/core/coach/calibration_fixtures.py`: 8 個の GoldenFixture
  - 各 fixture は 1 症状のみ発火するよう独立化（テスト安定性）
  - 39 件新規テスト、検出器挙動を pin する regression suite
  - Phase 219+ での閾値チューニングの基礎
- 2026-07-17: **Phase 217 — Aggregate helpers + CLI analyze**（Lv2）
  - `extract_winrate_scorelead_correlation(karte)` — Pearson r ヘルパー
  - `extract_winrate_scorelead_pairs(karte)` — 生 (w, p) ペア抽出
  - CLI `analyze <karte.json>` 新コマンド追加（Meta / Metrics / Streak / Correlation / Symptoms を出力）
  - POSITION_EVALUATION 自動検出は相関閾値不安定のため placeholder（ゴールデン棋譜検証を要する）
  - 6 件 CLI テスト追加、累計 4822 件テスト合格
- 2026-07-17: **Phase 216 — Streak-based symptom detection**（Lv2）
  - `katrain/core/coach/karte_detector.py` 拡張: 5 個の streak aggregator helper
  - `detect_symptoms_from_karte` を 3 系統統合に拡張（per-move + weakness + streak）
  - 4 つの「新規」症状（OVERFIGHT / SMALL_MOVE_ADDICTION / TILT_CHAIN / TILT_DISCOURAGEMENT）を自動検出可能化
  - 17 件ユニットテスト追加、全 4816 件テスト合格
- 2026-07-17: **Phase 215 — Karte-aware symptom detection**（Lv2）
  - `katrain/core/coach/karte_detector.py`: Karte JSON → SymptomContext 自動構築
  - 11 個の aggregator helper（avg_points_lost, max_score_stdev, weakness_concentration 等）
  - `detect_symptoms_from_karte`: SymptomContext 検出 + weakness カテゴリ union
  - 30 件ユニットテスト合格、CLI プロンプト品質向上
- 2026-07-17: **Phase 214-A — LLM coach CLI tool**（Lv2）
  - `katrain/core/coach/cli.py`: 4 サブコマンド（build / validate / symptoms / lexicon）
  - 17 件ユニットテスト、Kivy 非依存（ターミナルから直接起動可能）
  - ワークフロー: GUI で Karte JSON 書き出し → CLI で LLM プロンプト生成 → LLM に貼付 → CLI で検証
- 2026-07-17: **Phase 213 — LLM「翻訳特化」導入 完全実装**
  - Phase 207 `master_db.py` + Phase 208 `lexicon.py` + Phase 209 `symptom_index.py` + Phase 210 `tones.py` + Phase 211 `prompt_builder.py` (Lv3) + Phase 212 `llm_validator.py` を `katrain/core/coach/` に完全実装
  - Phase 213 `test_coach_e2e.py`: 6 モジュールを end-to-end で結線する mock LLM テスト 9 件
  - 累計 243 件新規ユニットテスト、全 4752 件テスト合格（5 skip）
  - ハルシネーション抑制 3 層防御（構造化メタデータ / Lexicon 注入 / HTML コメント式 System Instruction）を実装
  - LLM 出力検証 5 種類（症状 ID 不在 / 着手番号範囲外 / pointsLost 外れ値 / トーン不一致）を警告表示で実装
- 2026-07-17: **Phase 203 — LLM「翻訳特化」導入 調査ドキュメント**
  - `docs/archive/specs-planned/` を新設（計画中スペック用ディレクトリ、初エントリ）
  - `docs/archive/specs-planned/phase203-llm-translator.md` 作成（約 600 行、D 案: ドキュメント整備のみ）
  - 30 症状（master doc §2-0）× KataGo 数値マッピング表、自動検出可能 22 / LLM 委ね 11 の分類を提示
  - ハルシネーション抑制 3 層防御設計、レベル判定（BR/WR + 負け基準補正）、LLM 出力検証（警告表示のみ）設計
- 2026-07-17: **Phase 207 — `core/coach/master_db.py`**（Lv2、Phase 208-213 と同時に main にマージ済み）
  - 統合マスター §0 + §1 を `katrain/core/coach/master_db.py` に構造化
  - `CoachMode` 5 モード + `ToneVoice` 3 ボイス、`estimate_mode_from_rank` / `estimate_mode_from_loss` 実装
  - 41 件ユニットテスト合格
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
