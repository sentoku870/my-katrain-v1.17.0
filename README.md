# myKatrain v1.17.1 (KaTrain fork)

**myKatrain** は、Sander Land 氏によるオープンソース囲碁解析ソフト **KaTrain** をベースにした  
個人開発の拡張版です。KataGo 解析結果から「カルテ (Karte)」JSON を生成し、  
外部 LLM に手動で貼り付けて coaching コメントを得る用途に特化しています。

> **Unofficial personal fork.** This project is **not** an official release of the original KaTrain.  
> 公式 KaTrain とは別物であり、本家のサポート窓口への問い合わせはご遠慮ください。

---

## 1. このフォークで追加・変更している主な点

| 機能 | 概要 | 対応 Phase |
|------|------|------------|
| **KataGo 専用化** | 旧 Leela Zero 解析パスを完全削除（Phase 171） | 171 |
| **単局 Karte JSON 出力** | 1局の解析結果から重要局面・ミス分布・難易度を含む Karte (v3.3 JSON) を生成 | 171 / 231-237 |
| **複数局サマリ (Summary) JSON** | N局の弱点パターンを集約した Summary (v3.4 JSON) を生成 | 221 / 270 |
| **LLM Coach GUI 統合** | myKatrain メニュー「LLM コーチ（手動貼付）」から、Karte/Summary → プロンプト生成 → コピー → 応答貼付 → 検証の 1 サイクルを実行 | 225 / 226 / 227 / 228 |
| **複数局 LLM コーチ対応** | Summary JSON からの集約サマリプロンプト生成・バリデーション | 227 / 228 |
| **棋譜並べ (Kifunarabe)** | 重要局面反復・弱点自動 export・履歴永続化 | 177 / 249 |
| **Beginner Hints (初心者ヒント)** | ミス / 自由度 / 難易度 9 カテゴリ + 派生ヒント | 91-92 / 179 / 182 / 186 |
| **重要局面ナビゲーション** | 黒前/黒次/白前/白次の 4 ボタン（黒白別ジャンプ） | 250 |
| **候補手フィルター (PV Filter)** | AUTO / 5 プリセット + ライブプレビュー | 246 / 247 |
| **バッチ解析** | 複数 SGF を一括再解析（パスのみ指定） | 87 / 195 |
| **棋力プリセット自動推定** | `general/player_rank` を 1 箇所入力 → AI / LLM Coach へ自動反映 | 229 |
| **AI 戦略スリム化 (17→2)** | `ai:default` / `ai:handicap` の 2 戦略のみに整理 | 280 |
| **AYAKA ボイス削除 / TOMOKO 統一** | 全棋力を標準語キャラに統一 | 269 |
| **KivyMD 1.2.0 移行** | Material Design 3 対応 + フォント tofu fix | 277 / 281 |

LLM への自動 API 送信は行いません。**プロンプトをクリップボードへコピー → 任意の LLM に手動貼付 → 応答を popup に戻して検証** が正式ワークフローです (`docs/00-purpose-and-scope.md` §7 non-goals 参照)。

---

## 2. 動作環境

| 項目 | 要件 |
|------|------|
| Python | 3.11 以上（主開発環境: 3.13.9 / `.python-version` 参照） |
| OS | Windows（主利用）/ Linux（CI 検証対象） |
| KataGo | `analysis` エンジン（`katrain` 設定ダイアログから model / binary を取得） |
| パッケージ管理 | uv（`uv.lock` で再現可能、`poetry` 手順は廃止） |
| 表示 | Kivy 2.3.1 + KivyMD 1.2.0 |

> **macOS 検証は範囲外**です。本家 KaTrain の macOS パッケージをご利用ください。

---

## 3. クイックスタート (fork を clone した場合)

```bash
# 依存を再現性をもって同期
uv sync

# アプリを起動 (Kivy window が開く)
uv run python -m katrain
```

初回起動時に KataGo 実行ファイル・モデル・`analysis_config.cfg` の場所を入力するダイアログが表示されます。

> **`pipx install katrain` / `brew install katrain` は本家 KaTrain** を導入します。  
> 本フォークを動かしたい場合は clone + `uv sync` を利用してください。

---

## 4. 開発者向けコマンド

```bash
# 依存同期
uv sync

# 起動
uv run python -m katrain

# テスト（逐次）
uv run pytest tests

# テスト（並列・時間短縮）
uv run pytest tests -n auto

# テスト（時間上位表示）
uv run pytest tests --durations=20 --durations-min=0.1

# 静的解析
uv run mypy katrain
uv run ruff check katrain tests
uv run ruff format --check katrain tests

# コード整形
uv run ruff format katrain tests
```

CI（`.github/workflows/test_and_build.yaml`）では Python 3.11 / 3.12 / 3.13 のマトリクスを実行し、coverage 60% を gate としています。

> headless Kivy テストの詳細は [`docs/06-kivy-headless-testing.md`](docs/06-kivy-headless-testing.md) を参照。

---

## 5. AI 戦略

| config キー | 説明 |
|------------|------|
| `ai:default` | KataGo 通常対局（手加減なし）。プロ棋士レベル |
| `ai:handicap` | KataGo 置碁（置き石前提の設定） |

旧 KaTrain の「Calibrated Rank Bot」「Simple Style」「ScoreLoss」「Policy」「KataJigo」等のスタイル AI は **Phase 280 で削除済み** です。代わりにヒント生成・メニュー・LLM Coach 等で教育機能を強化しています。

詳細は [`docs/02-code-structure.md`](docs/02-code-structure.md) §5 を参照。

---

## 6. 主要な Karte / Summary ワークフロー

1. SGF をロードし KataGo 解析を実行
2. **マイ Katrain メニュー → 単局カルテ出力** で `reports/karte/karte_<game>.json` (v3.3) を生成
3. **マイ Katrain メニュー → LLM コーチ（手動貼付）** で Karte JSON のパスを指定
4. popup の「プロンプト生成」で Markdown 風プロンプトをクリップボードへコピー
5. 任意の LLM (ChatGPT / Claude / Gemini 等) に**手動で貼り付け**、応答をコピー
6. popup の「応答貼付 → 検証」で症状 ID / move number / pointsLost / トーン整合性を 6 ルールで自動チェック

複数局まとめワークフローは **マイ Katrain メニュー → 複数局サマリ作成** で生成した `summary.json` (v3.4) を使い、上の手順 2 以降を Summary に対して実行します（ポップアップが JSON の型を自動判別）。

Karte JSON のスキーマ正本は [`docs/archive/specs-implemented/karte-schema.md`](docs/archive/specs-implemented/karte-schema.md) です。

---

## 7. ドキュメント入口

| ファイル | 内容 |
|---------|------|
| [`docs/00-purpose-and-scope.md`](docs/00-purpose-and-scope.md) | 目的・スコープ・non-goals |
| [`docs/01-roadmap.md`](docs/01-roadmap.md) | 全体ロードマップ |
| [`docs/02-code-structure.md`](docs/02-code-structure.md) | コード構造・データフロー |
| [`docs/usage-guide.md`](docs/usage-guide.md) | 利用者ガイド |
| [`docs/03-llm-validation.md`](docs/03-llm-validation.md) | LLM 検証手順（手動 / 自動） |
| [`docs/06-kivy-headless-testing.md`](docs/06-kivy-headless-testing.md) | headless Kivy テスト |
| [`docs/archive/specs-implemented/`](docs/archive/specs-implemented/) | Phase 実装済みスペック一覧 |
| [`docs/archive/specs-planned/`](docs/archive/specs-planned/) | 計画中・延期中の仕様 |
| [`docs/ideas/`](docs/ideas/) | 構想段階のアイデアメモ |
| [`docs/future/`](docs/future/) | 将来実装予定の機能 |
| [`docs/resources/`](docs/resources/) | 外部リソース（囲碁用語 YAML 等） |
| [`AGENTS.md`](AGENTS.md) | opencode / 開発エージェント向け開発ガイド |

---

## 8. upstream との関係

| 項目 | 値 |
|------|-----|
| ベースプロジェクト | [sanderland/katrain](https://github.com/sanderland/katrain) |
| ライセンス | MIT（[`LICENSE`](LICENSE) を参照） |
| パッケージ名 | `KaTrain`（PyPI / Homebrew では本家版が入る） |
| Homepage | [`pyproject.toml`](pyproject.toml) の `[project.urls]` を参照 |

本家は KaTrain のマニュアル・インストール手順・サポート窓口を提供しています。本フォーク固有の質問・Issue は本リポジトリ（私的）の範囲で対応してください。

---

## 9. 現在のステータス

- パッケージバージョン: **v1.17.1**（`pyproject.toml` / `katrain/core/constants.py`）
- 設定互換最小バージョン: **v1.17.0**（旧 config JSON を読み込める下限）
- 用途: 個人利用・教育機能の試作・LLM コーチング実験
- 公開方針: 実験的リポジトリ。バグ報告は GitHub Issue へ（修正は任意）
- CI: Linux 3.11 / 3.12 / 3.13 で緑、`mypy 0 issues / ruff clean / pytest 6191 PASS + 3 SKIP`（Phase 284 時点）

詳細は [`AGENTS.md`](AGENTS.md) §1.3 直近のマイルストーンを参照。
