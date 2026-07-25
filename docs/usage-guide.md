# myKatrain 使い方ガイド

最終更新: 2026-07-21

myKatrain は KaTrain fork で、KataGo 解析結果を **Karte / Summary JSON** に出力し、外部 LLM に手動で貼り付けてコーチングコメントを得る用途に使います。本ガイドは現在利用可能な機能だけの操作方法を説明します。

## 1. 起動・基本操作

### 1.1 起動

```bash
uv sync
uv run python -m katrain
```

初回起動時に KataGo 実行ファイル・モデル・`analysis_config.cfg` を指定するダイアログが出ます。これらは設定ダイアログ（歯車アイコン）から後で変更可能です。

### 1.2 基本ワークフロー

1. SGF を読み込み（ドラッグ&ドロップ、またはメニュー → File → Open）
2. KataGo で解析（自動的に開始、または F2 で deeper analysis）
3. 以下のいずれかの機能で弱点を確認

## 2. Karte / Summary JSON の出力

### 2.1 単局カルテ（Karte）

| 操作 | 効果 |
|------|------|
| マイ Katrain メニュー → **カルテ出力** | 現在の局の Karte を `karte_output_directory` 直下の `karte_<base>_<YYYYMMDD-HHMM>.json`（schema v3.5）に書き出し |

JSON スキーマの正本は [`docs/karte-schema.md`](./karte-schema.md) を参照。

### 2.2 複数局サマリ（Summary）

複数局サマリの作成は **バッチ解析** メニューからのみ可能です
（Phase 230-A.2 で「複数局サマリ作成」メニューは廃止されました）。

| 操作 | 効果 |
|------|------|
| マイ Katrain メニュー → **バッチ解析** | フォルダ指定で SGF 一括解析＋Karte / Summary 生成（出力先: `<input_dir>/reports/karte/`, `reports/summary/`、schema v3.5） |

LLM Coach popup は両 JSON を型自動判別してプロンプト生成します。

## 3. LLM Coach（手動貼付ワークフロー）

### 3.1 基本フロー

```text
1. マイ Katrain メニュー → 「LLM コーチ（手動貼付）」
2. popup 上の path 入力欄で Karte / Summary JSON を指定（参照ボタン → OK）
3. 棋力プリセット（player_rank）が自動表示 → 必要なら手動修正
4. 「プロンプト生成」ボタン → Markdown 風プロンプトをクリップボードへコピー
5. ChatGPT / Claude / Gemini 等に手動で貼り付け
6. LLM の応答をコピー → popup の「応答貼付」欄にペースト
7. 「検証実行」で 5 ルールの自動チェック（HIGH / MEDIUM / LOW）
8. 「検証結果をコピー」で警告込み結果をコピー
```

### 3.2 検証 5 ルール

LLM 出力に対して以下を自動検出します。

| Severity | 項目 | 例 |
|----------|------|-----|
| HIGH | 症状 ID が無効 | 未知の SymptomId |
| HIGH | 着手番号が範囲外 | total_moves を超える #50 |
| MEDIUM | 相手側症状の混入 | `PlayerColor` 指定時に逆側の `weaknesses` を引用 |
| MEDIUM | pointsLost が天井超過 | `ceiling + tolerance` を超える値 |
| LOW | Lexicon 外語句の引用 | 注入していない用語を「」付きで言及 |

検証エラーが出ても abort しません。警告込みで結果を返すので、LLM の出力を再プロンプトの参考にしてください。

### 3.3 注意点

- **LLM に自動送信しません**。手動でコピー＆貼付する運用です。
- 応答は 100k 文字を超えると truncate されます。
- 視点（黒 / 白）は Karte / Summary の SGF 棋力から自動推定。手動切替可。

## 4. 棋譜並べ（Kifunarabe）

### 4.1 起動

| 操作 | 効果 |
|------|------|
| メニュー → 「棋譜並べ」(Ctrl-R) | 棋譜並べモード開始 |
| SGF 選択 → モード（先手 / 後手 / 両方）+ ヒント数（0〜5）+ 手数（50/100/150/全部） | セッション設定 |

### 4.2 ルール

- ユーザーが **実戦手と同じマスをクリック** → 正解
- 別のマーカーをクリック or マーカー外 → 不正解（`WRONG_GUESS` 記録）
- 自分の手番でない側は **自動進行**
- `max_moves` 到達または本譜終了で summary popup 表示

### 4.3 設定項目

設定ダイアログ → 「棋譜並べ」タブで以下を調整可能:

| キー | デフォルト | 効果 |
|------|:---------:|------|
| `kifunarabe/show_digits` | False | 候補マーカーに数字（勝率 / スコア / visits）表示 |
| `kifunarabe/show_actual_border` | False | 実戦手に枠線 |
| `kifunarabe/uniform_color` | True | 全マーカー同色（ランキング非表示） |
| `kifunarabe/auto_toggle_markers` | True | 「次の一手」「ドット」を自動 OFF |

履歴は `~/.katrain/kifunarabe_history/` に JSON 保存。summary popup の「履歴」ボタンで直近 50 件表示。

## 5. Beginner Hints

コントロールパネル / 盤面ハイライトで現在局面の構造的ヒントを表示。

| 系統 | 役割 |
|------|------|
| 構造 | self_atari / ignore_atari / missed_capture / cut_risk |
| Meaning tag | low_liberties / self_capture_like / bad_shape / heavy_group / missed_defense / urgent_vs_big |
| ミス | mistake_blunder / mistake_mistake / mistake_good（好手称賛） |
| 自由度 | only_move / narrow / wide |
| 難易度 | tricky / calm |
| KataGo 不確実 | katago_uncertain |
| 所有 | ownership_dominant |
| Policy | policy_confident / policy_conflict |
| Curator（弱点統合） | curator_weak_axis |

設定ダイアログ → 「解析」タブ → **Beginner Hints** ラジオボタンで 4 段階の優先順位を切替。

## 6. 候補手フィルター（PV Filter）

KataGo 解析の候補手を盤面表示前に「ノイズ」間引き。初期値は **AUTO** で `player_rank` により自動切替。

### 6.1 4 段階の強度

| レベル | max_candidates | max_points_lost | max_pv_length | 用途 |
|--------|---------------|----------------|---------------|------|
| 緩め (weak) | 15 | 4.0 | 15 | 激甘・初心者 |
| 標準 (medium) | 8 | 2.0 | 10 | 標準 |
| 厳選 (strong) | 4 | 1.0 | 6 | 辛口 |
| 最厳 (expert) | 3 | 0.5 | 4 | プロ用 |

`max_candidates` は **最善手以外** の上限。最善手は常駐表示です。

### 6.2 棋譜並べ中は完全 OFF

棋譜並べモード中は正解と AI 候補が必ず全件表示されます（フィルター無効）。

### 6.3 設定

設定ダイアログ → 「解析」タブ → **候補手フィルター** で AUTO / 4 段階を切替。AUTO の場合、下部に **N 件 → M 件** のライブプレビューが表示。

## 7. 重要局面ナビゲーション

| 操作 | 効果 |
|------|------|
| サイドパネル「重要局面」タブの **黒前 / 黒次** ボタン | 黒番の重要局面を黒白問わず前後ジャンプ |
| サイドパネル「重要局面」タブの **白前 / 白次** ボタン | 白番の重要局面を黒白問わず前後ジャンプ |
| 解析タブ → **Critical 3 件数** スピナー（1〜10） | Karte `critical_3` セクションの件数設定 |
| 解析タブ → **重要度レベル** ラジオ（緩め / 標準 / 厳しめ） | 抽出感度を棋力別に切替 |

### 重要度レベル

| レベル | 閾値 | 最大件数 | 向いている棋力 |
|--------|------|---------|----------------|
| easy | 1.0 | 10 | 30級〜11級 |
| normal | 0.5 | 20 | 10級〜5段（デフォルト） |
| strict | 0.3 | 40 | 6段以上 |

## 8. 棋力プリセット

`general.player_rank`（解析設定タブ）で `10k` / `5d` 等の棋力を入力すると、AI 対局・LLM Coach・Beginner Hints・PV Filter のすべてが自動連動します（Phase 230-E で `mykatrain_settings.default_user_rank` から移行済み）。

```
例: player_rank = "5d" の場合
  - AI 対局: KataGo 通常
  - PV Filter: AUTO → 厳選 (4 候補)
  - Beginner Hints: 既知の問題含めて全表示
  - LLM Coach: 5d 用の解説強度でプロンプト生成
```

## 9. 設定ダイアログの主要タブ

| タブ | 内容 |
|------|------|
| **KataGo** | 実行ファイル・モデル・分析 config・並列度 |
| **GUI** | 言語 (jp / en)、テーマ、表示詳細度 |
| **解析** | Beginner Hints、PV Filter、Critical 3、重要度レベル、棋力 |
| **AI** | AI プレイヤー設定（`ai:default` / `ai:handicap`） |
| **棋譜並べ** | 設定項目（§4.3）、棋力連動 |
| **診断** | 起動情報・KataGo 接続情報・クラッシュ時のヒント |

設定は `katrain/config.json` に保存されます。

## 10. トラブルシューティング

### KataGo が起動しない

| 症状 | 対処 |
|------|------|
| 「katago binary not found」 | 設定ダイアログ → KataGo → 実行ファイル指定 |
| 「analysis config not found」 | 「Download analysis config」で自動取得 |
| 起動直後クラッシュ | 設定ダイアログ → 診断タブでバージョン整合性確認 |

### 日本語が豆腐（□）になる

KivyMD 1.2.0 対応のフォント tofu fix が Phase 281 で組み込まれています。OS 環境に日本語フォントが存在しない場合は `python -c "from kivy.core.text import Label; Label(font_name='NotoSansCJK')"` で取得を試みてください。PyInstaller frozen binary で豆腐が出る場合は `uv pip install --force-reinstall kivy` を実行。

### 候補手が出ない

| 原因 | 対処 |
|------|------|
| PV Filter が強すぎる | 一時的に `off` にして候補手自体があるか確認 |
| 9路で STRONG | `max_pv_length` が 3 まで縮小。`off` で確認 |

### 起動時のクラッシュ

settings / config.json が破損している可能性。`~/.katrain/katrain_config.json` をバックアップして削除→起動で初期化されます。

## 11. 関連ドキュメント

- [`docs/karte-schema.md`](./karte-schema.md) — Karte / Summary JSON スキーマ正本
- [`docs/architecture.md`](./architecture.md) — コード構造と依存方向
- [`docs/i18n-workflow.md`](./i18n-workflow.md) — 翻訳ファイル更新手順
- [`docs/kivy-testing.md`](./kivy-testing.md) — headless Kivy テスト手順
