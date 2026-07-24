# AGENTS.md - myKatrain PC版 開発ガイド

> opencode がプロジェクト開始時に自動ロードする中核ドキュメント。  
> 細目ルールはスキル（`.opencode/skills/<name>/SKILL.md`）を on-demand で読み込む。  
> opencode の設定は `opencode.jsonc`、権限もそこで一元管理。

---

## 1. プロジェクト概要

### 1.1 基本情報

- **プロジェクト名**: myKatrain（KaTrain fork）
- **技術スタック**: Python 3.11+（主開発環境: 3.13）/ Kivy 2.3.1 + KivyMD 1.2.0（GUI）/ KataGo（解析エンジン）
- **リポジトリ**: `sentoku870/my-katrain-v1.17.0`
- **ローカルパス**: `D:\github\katrain-1.17.0`

### 1.2 目的（1文）

KataGo 解析を元に「カルテ（Karte）」を生成し、LLM 囲碁コーチングで的確な改善提案を引き出す。

### 1.3 配布方針（重要）

- 本 fork は **PyPI へ公開しない**。`KaTrain` というパッケージ名は本家の PyPI 登録と衝突するため。
- 配布手段: clone + `uv sync`、あるいは GitHub Actions の `Test, Build, and Release` ワークフロー（`create_release=true`）で生成した Windows バイナリ（draft release 添付）を手動ダウンロード。
- CI の `publish-pypi` ジョブは 2026-07-23 に削除済み（PR #466 想定）。`PYPI_TOKEN` Secret も不要なため削除してよい。

### 1.4 主要機能

| 機能 | 詳細 |
|------|------|
| Karte / Summary JSON 出力 | 単局 (v3.3) / 複数局サマリ (v3.4) |
| LLM Coach GUI 統合 | 手動貼付ワークフロー + 5 ルール検証 |
| 棋譜並べ (Kifunarabe) | 重要局面反復学習 + 履歴永続化 |
| Beginner Hints | 9 系統 23 カテゴリ |
| 重要局面ナビゲーション | サイドパネルタブ + 黒白別 4 ボタン |
| 候補手フィルター (PV Filter) | AUTO / 4 段階プリセット |
| 棋力プリセット自動推定 | `general/player_rank` 1 箇所入力 |

---

## 2. ユーザー（sentoku870）のスキルと期待

### 2.1 スキルレベル

| 領域 | レベル | 備考 |
|------|--------|------|
| PC操作 | 中〜上級 | 手順があれば複雑な操作も実行可能 |
| プログラミング | 初心者 | Progate Python 基礎程度、コードは読めるが書けない |
| Git/GitHub | 基本操作可 | 手順通りの操作は可能 |
| 囲碁 | 野狐 4-5 段 | ドメイン知識は十分 |

### 2.2 作業の快適さ優先順位

1. **最優先**: 自分だけで動作ロジック修正をしない
2. **可能**: LLM 指示ありの最小修正（タイポ、数値調整）
3. **許容**: ファイル全体のコピペ差し替え
4. **避けたい**: 複数ファイルの整合性判断

---

## 3. 開発ルール（要約）

タスクの種類に応じて以下スキルをロード:

| スキル | 用途 |
|--------|------|
| `correction-levels` | 修正規模（Lv0-5）の判定と回答フォーマット |
| `git-workflow` | ブランチ運用、コミット、PR 作成フロー |
| `debug-workflow` | バグ報告の整理、デバッグ 7 ステップ、KaTrain 固有ポイント |
| `go-domain` | 棋力 G0-G4、解説 A-D、KataGo 用語、カルテ概念 |
| `architecture` | レイヤー構造、core 層の Kivy 隔離、代替パターン |

### 3.1 基本コマンド

```bash
# 起動
uv sync
uv run python -m katrain

# テスト（全体・逐次）
uv run pytest tests

# テスト（並列）
uv run pytest tests -n auto

# テスト（時間上位表示）
uv run pytest tests --durations=20 --durations-min=0.1

# アーキテクチャテスト
uv run pytest tests/test_architecture.py -v

# UTF-8 強制（PowerShell）
$env:PYTHONUTF8 = "1"

# 静的解析
uv run mypy katrain
uv run ruff check katrain tests
uv run ruff format --check katrain tests

# 整形
uv run ruff format katrain tests
```

### 3.1.1 `uv --locked` / `--frozen` 運用ルール（PR-F 2026-07-23〜）

CI の `.github/actions/setup-python-uv/action.yml` は **`uv sync --locked`** で固定されています。`pyproject.toml` と `uv.lock` が乖離した状態で PR を開くと CI が即座に失敗する設計です。

| ケース | 対処 |
|---|---|
| 依存追加・更新を PR に含めたい | **ローカルで先に** `uv lock` を実行し、`uv.lock` をコミットしてから `uv sync --frozen` で適用 |
| CI が「`uv.lock` is out of date」とだけ失敗した | ブランチで `uv lock && git add uv.lock && git commit --amend --no-edit` で更新を反映 |
| 自分の環境だけ `.venv` が壊れた | `uv sync --frozen --reinstall` でロックに従い再構築 |
| ローカルで `uv sync` を素で叩きたくなった | 危険（lock を **暗黙に再生成** する）。代わりに `uv sync --frozen` |

`uv run --frozen ...` は wheel metadata の再検証を省略する素の wrapper。CI の matrix セルではこちらを使うので、cache hit が安定します。

### 3.2 トークン削減ルール

- **Grep → Read パターン**: まず検索で場所を特定、次に範囲読み込み
- **段階的アプローチ**: 広範囲→狭範囲の順
- **前後コンテキスト**: 関数定義は前後 30-40 行を含めて読む
- **小さなファイル**: 500 行未満は全体読み OK

---

## 4. コード構造（要約）

```
katrain/
├── __main__.py            ← アプリ起動、KaTrainGui
├── common/                ← 共有定数（Kivy 非依存）
│   └── rank.py            ← Rank dataclass
├── core/                  ← コアロジック（Kivy 非依存）
│   ├── game/              ← Game クラス
│   ├── analysis/          ← 解析基盤
│   ├── beginner/          ← Beginner Hints
│   ├── coach/             ← LLM Coach
│   ├── study/             ← 棋譜並べ
│   ├── reports/           ← Karte / Summary
│   └── batch/             ← バッチ処理
├── gui/                   ← Kivy GUI
│   ├── commands/          ← DISPATCH_TABLE（35 エントリ）
│   ├── popups/            ← ポップアップダイアログ
│   ├── managers/          ← 19 Manager クラス
│   └── features/          ← 機能モジュール
└── i18n/                  ← 翻訳ファイル（jp / en）
```

詳細: [`docs/architecture.md`](docs/architecture.md)

---

## 5. ドキュメント構成

```
README.md                            ← 入口・クイックスタート・fork 機能
docs/
├── usage-guide.md                   ← 操作方法（利用者向け）
├── architecture.md                  ← コード構造・データフロー（開発者向け）
├── karte-schema.md                  ← Karte / Summary JSON スキーマ正本
├── i18n-workflow.md                 ← 翻訳手順
├── kivy-testing.md                  ← headless Kivy テスト
└── resources/
    └── go_lexicon_master_last.yaml  ← 囲碁用語辞書
```

---

## 6. 出力時の注意

### 6.1 回答フォーマット（推奨）

```
1. 今回やること（1-2 文）
2. 修正レベル（Lv0-5）
3. 変更ファイル
4. 手順（コマンド付き）
5. 動作確認ポイント
```

### 6.2 記号の使い分け

- 囲碁解説レベル: `解説=A〜D`
- 技術選定 4 軸: `軸(対象範囲)=A〜C`
- 採用案: `案=A案/B案/C案`

### 6.3 スキル読み込みの判断

- 修正前に `correction-levels` スキルでレベル判定
- レベル 3 以上の作業では `architecture` スキルを参照
- 囲碁関連機能では `go-domain` スキルを参照
- バグ修正では `debug-workflow` スキルを参照
- コミット・PR 時は `git-workflow` スキルを参照

---

## 7. やらないこと（non-goals）

- 外部 API への自動送信（LLM 連携は手動貼付）
- フル機能 SGF エディタ化
- 大規模な棋譜管理 DB
- 対局支援（チート用途）
- 「最善手当てクイズ」を目的化した訓練
- PyPI 公開（`KaTrain` パッケージ名は本家のものを尊重するため、wheel/sdist は clone + uv sync で配布する想定）
- GitHub Actions artifact の大量保持（PR ごとに約 448MB の Windows バイナリを 90 日保管する運用は廃止し、`workflow_dispatch`（`create_release=true`）時のみ release 用 artifact をアップロードする）

---

## 7.5 CI と main ブランチ保護（2026-07-23〜）

- ワークフロー: `.github/workflows/test_and_build.yaml`
  - トリガー: `pull_request`、`push:main`、`workflow_dispatch`（`create_release`）
  - ジョブ: `prepare → {lint, typecheck, test×3, build-windows} → quality-gate → create-release`
  - Python 3.13のtest jobでcoverage gateと`coverage.xml` artifact保存を実行
- main ブランチ保護の必須チェックには **`quality-gate` 1件だけを登録**してください。
  - 個別ジョブ（`test (3.11)`、`test (3.12)`、ほか）を必須化すると、ジョブ追加のたびに保護設定を更新する必要があり、運用ミスが増える
- GitHub リポジトリの Settings → Branches → Branch protection rules → `main`:
  - ☑ Require status checks to pass before merging
    - 必須チェック: `quality-gate` (sources を `test_and_build` ワークフローから)
  - ☑ Require linear history（任意の PR squash / rebase）
  - ☑ Do not allow forcing pushes
- ローカルで CI 完全再現: `uv lock --check && uv sync --frozen && uv run --frozen ruff check katrain tests && uv run --frozen ruff format --check katrain tests && uv run --frozen mypy katrain && uv run --frozen pytest tests --cov=katrain --cov-report=term-missing --cov-fail-under=70`
  - なお CI では Linux matrix (3.11/3.12/3.13) 上で `xvfb-run` を使い Kivy 統合テストも実行する。ローカルで Xvfb がない環境では `kivy_headless` marker 以外を `-m "not kivy_headless"` で除外する近似となる。

## 8. シェル権限ルール（opencode.jsonc）

`opencode.jsonc` の bash 権限パターン。**設定変更後は opencode の再起動が必要**（起動時 1 回のみ読み込み）。

**運用方針**: 開発に必要なコマンドはほぼ無確認で通し、システム破壊系のみ明示ブロックする **B 案（中庸）**。確認ダイアログ（ask）は 0 件、危険コマンドは明示 deny、未指定コマンドは `*: allow` で通過。

### 自動許可（allow）

| 区分 | パターン例 |
|------|----------|
| Python 開発 | `uv *`, `python*`, `pytest*`, `ruff*`, `mypy*`, `coverage*` |
| バージョン管理 | `git *`, `gh *` |
| ビルド/コンテナ | `make*`, `docker*` |
| 読み取り/加工 | `cat*`, `head*`, `tail*`, `ls*`, `grep*`, `find*` |
| 診断 | `stat*`, `which*`, `pwd*`, `env*` |
| ファイル操作 | `mkdir*`, `touch*`, `cp*`, `mv*`, `chmod*`, `rm*` |

### 拒否（deny）— 危険コマンド

| カテゴリ | 拒否対象 |
|---------|---------|
| 権限昇格 | `sudo *`, `su *` |
| 電源操作 | `shutdown *`, `reboot *`, `halt *` |
| ディスク破壊 | `mkfs*`, `fdisk*`, `dd *` |
| サービス管理 | `systemctl*`, `service *` |
| 認証情報 | `passwd*` |
| ユーザー管理 | `useradd*`, `userdel*` |
| ファイアウォール | `iptables*`, `ufw *` |
| マウント | `mount*`, `umount*` |

**運用注意**:
- `rm*` を allow 化したため、削除操作は自己責任
- `chown*` を allow 化したため、オーナー書き換えは慎重に
- `curl*` / `wget*` を allow 化したため、外部送信は意図しないデータ流出に注意
- 緊急時は `OPENCODE_DISABLE_PROJECT_CONFIG=1` で設定無効化可能

詳細は [`opencode.jsonc`](opencode.jsonc) を参照。
