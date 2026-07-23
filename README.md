# myKatrain v1.17.1 (KaTrain fork)

**myKatrain** は、オープンソース囲碁解析ソフト KaTrain をベースにした個人開発の fork です。  
KataGo の解析結果から **Karte / Summary JSON** を生成し、外部 LLM に手動で貼り付けて  
coaching コメントを得る用途に使います。

> **Unofficial personal fork.** 本プロジェクトは個人開発の fork であり、  
> 公式 KaTrain とは別物です。本家のサポート窓口への問い合わせはご遠慮ください。

---

## 1. このフォークで追加した主な機能

| 機能 | 概要 |
|------|------|
| **Karte / Summary JSON 出力** | 単局 (v3.3) と複数局サマリ (v3.4) の JSON レポート。LLM に貼る前提の軽量形式 |
| **LLM Coach GUI（手動貼付）** | マイ Katrain メニュー「LLM コーチ（手動貼付）」から、プロンプト生成 → クリップボード → 応答貼付 → 検証の 1 サイクルを実行 |
| **複数局 LLM コーチ** | Summary JSON からの集約サマリプロンプト生成・バリデーション (Shape A/B) |
| **棋譜並べ (Kifunarabe)** | 重要局面反復学習モード。履歴永続化 + 弱点自動 export |
| **Beginner Hints** | 9 系統 23 カテゴリの構造的ヒント（self_atari / mistake / freedom / difficulty / KataGo 不確実 / ownership / policy / curator 統合） |
| **重要局面ナビゲーション** | サイドパネル「重要局面」タブで黒前/黒次/白前/白次の 4 ボタン（黒白別ジャンプ） |
| **候補手フィルター (PV Filter)** | AUTO / 4 段階プリセット + ライブプレビュー。盤サイズ連動補正 |
| **棋力プリセット自動推定** | `general/player_rank` 入力 1 箇所で AI 対局・LLM Coach・PV Filter・Beginner Hints すべてに自動連動 |

Karte JSON のスキーマ正本は [`docs/karte-schema.md`](docs/karte-schema.md)。

## 2. 動作環境

| 項目 | 要件 |
|------|------|
| Python | 3.11 以上（主開発環境: 3.13.9） |
| OS | Windows / Linux（macOS は本家のリリースを利用してください） |
| KataGo | `analysis` エンジン（`katrain` 設定ダイアログから取得） |
| パッケージ管理 | uv（`uv.lock` で再現可能） |
| GUI | Kivy 2.3.1 + KivyMD 1.2.0 |

## 3. クイックスタート

```bash
# 依存を再現可能に同期
uv sync

# アプリ起動 (Kivy window が開く)
uv run python -m katrain
```

初回起動時に KataGo 実行ファイル・モデル・`analysis_config.cfg` を指定するダイアログが表示されます。

> **`pipx install katrain` / `brew install katrain` は本家 KaTrain** をインストールします。  
> 本 fork を動かす場合は clone + `uv sync` を利用してください。  
> 
> **PyPI 公開について**: 本 fork は PyPI へ公開しません（`KaTrain` パッケージ名は本家のもの）。  
> 配布は clone + `uv sync` / `uv build` で生成した wheel/sdist を手動配布する想定です。  
> Windows 用バイナリは GitHub Actions の `Test, Build, and Release` ワークフロー（`workflow_dispatch` で `create_release=true`）で生成・ダウンロードできます。

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

# 整形
uv run ruff format katrain tests
```

CI では Python 3.11 / 3.12 / 3.13 のマトリクスを実行し、coverage 60% を gate としています。  
main ブランチは **lint / mypy / test (3.11/3.12/3.13) / coverage / build-windows** を全て成功させた `quality-gate` ジョブのみで保護しています。  
Windows バイナリは PR でも PyInstaller で生成されますが、artifact の保持は `workflow_dispatch` の `create_release=true` 実行時のみです。release 方法は「Release 方法」を参照。

## 5. AI 対局

| 設定 | 説明 |
|------|------|
| `ai:default` | KataGo 通常対局（手加減なし） |
| `ai:handicap` | KataGo 置碁 |

旧 KaTrain 風のスタイル AI（Calibrated Rank Bot / ScoreLoss / KataJigo 等）は廃止しています。  
KataGo の **raw analysis** をそのまま使い、ヒント生成・メニュー・LLM Coach で教育機能を強化する方針です。

## 5.5 Release 方法（Windows バイナリ配布）

GitHub Actions の **Run workflow** から手動実行します。

1. `Actions` タブ → `Test, Build, and Release` → `Run workflow`
2. `create_release` を **true** にする
3. 完了後、`KaTrainWindows-<version>` artifact がダウンロード可能（draft release にも添付）
4. リリース公開前に `<https://github.com/sentoku870/my-katrain-v1.17.0/releases>` で draft 状態のままレビュー → Publish

## 6. ドキュメント入口

| ファイル | 内容 |
|---------|------|
| [`docs/usage-guide.md`](docs/usage-guide.md) | 利用者ガイド（起動・Karte / Summary 出力・LLM Coach・棋譜並べ・Beginner Hints・PV Filter・重要局面・棋力・設定・FAQ） |
| [`docs/architecture.md`](docs/architecture.md) | 開発者向けアーキテクチャ（レイヤー依存・パッケージ責務・データフロー・変更時の注意点） |
| [`docs/karte-schema.md`](docs/karte-schema.md) | Karte / Summary JSON スキーマ正本（v3.3 / v3.4） |
| [`docs/i18n-workflow.md`](docs/i18n-workflow.md) | 翻訳ファイル更新手順 |
| [`docs/kivy-testing.md`](docs/kivy-testing.md) | headless Kivy テスト手順 |
| [`docs/resources/`](docs/resources/) | 囲碁用語 YAML（Lexicon 注入データ） |

## 7. upstream との関係

| 項目 | 値 |
|------|-----|
| ベースプロジェクト | [sanderland/katrain](https://github.com/sanderland/katrain) |
| ライセンス | MIT（[`LICENSE`](LICENSE) 参照） |
| パッケージ名 | `KaTrain`（PyPI / Homebrew では本家版が入る） |

## 8. バージョン

- パッケージバージョン: **v1.17.1**（`pyproject.toml` / `katrain/core/constants.py`）
- 設定互換最小バージョン: **v1.17.0**

## 9. 現在のステータス

- 用途: 個人利用・教育機能の試作・LLM コーチング実験
- 公開方針: 実験的リポジトリ。バグ報告は GitHub Issue へ（修正は任意）
