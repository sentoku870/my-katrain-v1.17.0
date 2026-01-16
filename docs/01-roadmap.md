# myKatrain（PC版）ロードマップ

> 最終更新: 2026-01-17
> 固定ルールは `00-purpose-and-scope.md` を参照。

---

## 0. 用語（短縮表記）

| 用語 | 説明 |
|------|------|
| カルテ（Karte） | 対局の要点・弱点・根拠をまとめた「診断用まとめ」 |
| アンカー | 根拠を追跡できる最小情報（手数/座標/損失/候補手） |
| LLMパッケージ | LLMに渡す一式（karte.md + sgf + coach.md） |

---

## 1. フェーズ詳細（Phase 1〜）

### Phase 1: 解析基盤の整備（2025-12-08 完了）
- `eval_metrics.py` 追加
- 手番視点の正規化、評価差・重要度スコア算出

### Phase 2: 解析ビュー第1段階（2025-12-09 完了）
- 重要局面ハイライト（グラフ上の縦線表示）
- YoseAnalyzer v1（簡易版）
- ナビゲーションボタン追加

### Phase 3: ミス分類＋局面難易度（完了）
- ミス分類（良/軽/悪/大悪）
- 手の自由度（広い/普通/狭い/一択）
- グラフ上に大悪手のオレンジライン表示

### Phase 4: 学習モード＋棋力別フィードバック（Phase 4-1 完了）
- Phase 4-1: クイズ候補抽出（2025-12-11 完了）
- Phase 4-2〜4-4: クイズモードUI → Phase 10+ に延期
- UI: メニューに "(beta)" 表示で利用可能

### Phase 4.5: 評価指標の安定化 + バッチ改善（2025-12-29 完了、2026-01-05 拡張）
- `MoveEval.is_reliable`（visitsベースの信頼性フラグ）導入
- 棋力別プリセット5段階化（relaxed/beginner/standard/advanced/pro）
  - 日本語ラベル: 激甘/甘口/標準/辛口/激辛
- 重要手Top3の安定化
- i18n/CIの修正

**2026-01 拡張（PR #40-47）:**
- Variable Visits + Deterministic オプション
- 完了音通知（Sound on finish）
- タイムアウト解析の堅牢化（None/空文字対応）
- FileChooser パスガード（存在しないパスでクラッシュ防止）
- プレイヤーフィルタUI + per-player サマリー
- バッチオプション永続化

### Phase 5: 1局カルテを安定出力（2025-12-31 完了）
- カルテ出力機能（`build_karte_report()`）
- 重要局面（手数・座標・損失・ミス分類・Freedom）
- Export Karte ボタン（UI統合）
- LLM連携テスト成功（Claude + コーチファイル）

### Phase 6: 複数局まとめカルテ（2025-12-31 完了）
- 複数SGFファイル一括処理
- プレイヤーフィルタ（チェックボックスUI）
- ハンディ別カテゴリ分け（互先/置碁下手/置碁上手）
- ミス分類・フェーズ別統計
- 重要局面TopN + importance スコア
- `summary.md` 出力

### Phase 6.5: eval_metrics.py 品質向上（2025-12-31 完了）
- PositionDifficulty 自動計算（Game経由）
- importance 自動計算（snapshot作成時）
- score_loss/winrate_loss 一貫性修正
- SummaryStats クロス集計（Phase × Mistake）
- ドキュメント・コメント充実
- Freedom 制限事項の文書化

### Phase 7: 単局カルテUI + カルテ品質向上（2025-12-31 完了）
- Phase × Mistake クロス集計テーブル（複数局サマリー）
- 弱点仮説自動生成（単局カルテ + 複数局サマリー）
- Practice Priorities の精度向上（クロス集計活用）
- 統合テスト完了

### Phase 9: 検証テンプレで改善ループ（2025-12-31 完了）
- LLM検証テンプレート（`docs/03-llm-validation.md`）
- ワークフロー例（ウィークリーコーチ、デイリーコーチ）
- 5ステップ検証サイクルの確立
- 測定可能な改善指標の定義

---

## 2. フェーズ一覧（現在/次）

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|------|
| 4 | クイズモードUI | 学習機能 | 🔄 **進行中** |
| 4.5 | 評価指標安定化 + バッチ改善 | 5段階プリセット、Variable Visits | ✅ **完了** |
| 5 | 1局カルテを安定出力 | `reports/karte/karte_*.md` + アンカー規則 | ✅ **完了** |
| 6 | 複数局まとめで"悪癖"抽出 | `summary.md`（傾向） | ✅ **完了** |
| 6.5 | eval_metrics.py 品質向上 | production-ready 基盤 | ✅ **完了** |
| 7 | 単局カルテUI + カルテ品質向上 | デイリーコーチ完成 | ✅ **完了** |
| 9 | 検証テンプレで改善ループ | `03-llm-validation.md` | ✅ **完了** |
| 8 | 初心者向けヒント（任意） | 構造解析 + テンプレ | TBD |
| 10+ | クイズ/コーチUIの拡張 | [TBD] | TBD |
| 11 | 難解PVフィルタ | Top Moves表示改善 | ✅ **完了** |
| 12 | MuZero 3分解難易度 | 難所抽出・UI表示 | ✅ **完了** |
| 13 | Smart Kifu Learning | 棋譜学習・プロファイル | ✅ **完了** |
| 14 | Leelaモード推定損失 | Leela候補手の損失表示 | ✅ **完了** |
| 15 | Leela UI統合 | 設定UI + エンジン管理 | ✅ **完了** |
| 16 | Leela機能拡張 | PV再生 + 投了目安 | ✅ **完了** |
| 17 | Leela Stats on Top Moves | 候補手表示の選択機能 | ✅ **完了** |
| 18 | 安定性向上 | キャッシュLRU + バグ修正 | ✅ **完了** |
| 19 | 大規模リファクタリング | reports/パッケージ、analysis分割、GUI Manager抽出 | ✅ **完了** |
| 20 | Guardrails + UI Polish | Kivy依存削除、アーキテクチャテスト、config抽象化 | ✅ **完了** |
| 21 | Settings Popup タブ化 | 13設定を3タブに再編成 | ✅ **完了** |
| 22 | 安定性向上 | クラッシュ、フリーズ、リソースリーク防止 | ✅ **完了** |
| 23 | カルテ・サマリー品質向上 | ONLY_MOVE緩和、JSON出力、型ヒント | ✅ **完了** |
| 24 | Regression Tests (SGF E2E) | 既存golden testに実SGFケース追加 | ✅ **完了** |
| 25 | LLM Package Export | zip + manifest + PB/PW匿名化 | ✅ **完了** |
| 26 | レポート導線改善 | 最新レポートを開く、フォルダを開く | TBD |
| 27 | Settings UI拡張 | 検索、Export/Import、タブ別リセット | TBD |
| 28 | Smart Kifu運用強化 | バッチ連携、解析率表示 | TBD |
| 29 | Diagnostics | 診断画面、Bug Report zip（サニタイズ付き） | TBD |
| 30 | 検証テンプレ導線 | ショートカット、テンプレコピー | TBD |

---

## 3. Phase 5: 1局カルテ（最小）を安定出力 ✅ **完了**

### 3.1 目的
「1局 = 1枚のカルテ」を **安定して再現** できる状態にする。

### 3.2 スコープ
**In:**
- ✅ 重要局面の抽出（最小）
- ⚠️ 弱点仮説（最小）- Phase 6 で複数局統合時に実装
- ✅ 根拠アンカー（必須）
- ✅ 出力フォーマットの固定

**Out:**
- 自動送信（外部APIへの自動投稿）
- "人間らしさ調整"の深掘り
- クイズUIの作り込み

### 3.3 成果物
- [x] カルテ出力機能（`build_karte_report()`）
- [x] 重要局面（手数・座標・損失・ミス分類・Freedom）
- [x] LLM連携テスト（コーチファイル + カルテで診断成功）

### 3.4 実装内容（2025-12-21 〜 2025-12-31）
- [x] カルテ出力のコアロジック（`d796ad2`）
- [x] Freedom（手の自由度）を出力に追加
- [x] Export Karte ボタン（UI統合済み）
- [x] LLM診断の動作確認（Claude + コーチファイル）

### 3.5 受け入れ条件
- [x] カルテにアンカー情報（手数・座標・損失）が含まれる
- [x] Freedom（手の自由度）が出力される
- [x] LLMに渡して診断が成功する

### 3.6 Phase 6 への引継ぎ事項
- 複数局の統合カルテ設計
- 共通傾向の抽出方法
- ~~Freedom buckets（分布）~~ → 2025-12-31 削除
  - 1局カルテ: 常にUNKNOWNのため削除
  - 複数局サマリー: UNKNOWN以外があれば条件付き表示

---

## 4. Phase 6: 複数局まとめカルテ ✅ **完了**

### 4.1 目的
複数局のSGFから、共通の負け筋/悪癖を **短い言葉** で抽出。

### 4.2 スコープ
**In:**
- ✅ 傾向の集計（Phase別・ミス分類別）
- ✅ 次の練習優先順位（1-3個）
- ✅ プレイヤーフィルタ（AI自己対局除外）

**Out:**
- 個人最適化の高度な学習（Phase 9 以降）

### 4.3 成果物
- [x] `reports/summary_互先_YYYYMMDD-HHMM.md`
- [x] ハンディ別カテゴリ分け（互先/置碁下手/置碁上手）
- [x] importance スコア出力

### 4.4 受け入れ条件
- [x] 複数局の入力で統計が集計される
- [x] Practice Priorities が1-3個に絞られている
- [x] LLMに貼り付けて相談可能

---

## 5. Phase 7: 単局カルテUI + カルテ品質向上 ✅ **完了**

### 5.1 目的
デイリーコーチ（単局カルテ）を完成させ、カルテの品質を向上させる。

### 5.2 スコープ
**In:**
- ✅ 単局カルテUI実装（Phase 5で完了済み：Export Karte ボタン）
- ✅ Phase × Mistake クロス集計を summary.md に追加
- ✅ 弱点仮説の自動生成（簡易版）
- ✅ Freedom 統計の活用（Game オブジェクト経由、Phase 5で実装済み）

**Out:**
- 囲碁用語辞書との連携（Phase 7.5 で検討）
- 初心者向けヒント（Phase 8 に移動）
- 構造解析（Phase 8 に移動）

### 5.3 成果物
- [x] 単局カルテUI（Export Karte ボタン、Phase 5で実装済み）
- [x] `reports/karte/karte_YYYYMMDD-HHMM.md`（単局版、Phase 5で実装済み）
- [x] Phase × Mistake クロス集計テーブル（複数局サマリー）
- [x] 弱点仮説セクション（単局カルテ + 複数局サマリー）

### 5.4 受け入れ条件
- [x] 対局終了後、1クリックでカルテ生成（Export Karte ボタン）
- [x] Phase × Mistake クロス集計が表示される（複数局サマリー）
- [x] LLMに貼り付けて「デイリー診断」が機能する
- [x] 複数局サマリー（ウィークリー）と組み合わせて使える

### 5.5 設計方針
- **デイリーコーチ（単局カルテ）**: Game オブジェクト → Freedom 利用可
- **ウィークリーコーチ（複数局サマリー）**: SGF パース → Phase × Mistake クロス集計
- カルテ形式: Markdown（軽量・LLM連携に最適）

### 5.6 実装内容（2025-12-31 完了）
- Phase × Mistake クロス集計（`__main__.py`）
- 弱点仮説自動生成（複数局：`__main__.py`、単局：`game.py`）
- 統合テスト完了（分類ロジック、クロス集計、弱点抽出）

---

## 6. Phase 8: 初心者向けヒント（任意）

### 6.1 目的
構造解析（グループ・呼吸点・連絡点・切断点）と初心者向けテンプレの実装。

### 6.2 スコープ
**In:**
- [ ] 構造解析（グループ抽出・呼吸点・連絡点・切断点）
- [ ] 初心者向けテンプレ10個（症状 → 処方箋）
- [ ] 理由タグ（atari / low_liberties / cut_risk 等）

**Out:**
- 囲碁用語辞書との自動連携（Phase 7.5 で検討）

### 6.3 設計ドキュメント
- `docs/design/phase7-structure-hints.md`（既存）
- `docs/resources/go_lexicon_master_last.yaml`（既存）

---

## 7. Phase 9: 検証テンプレで改善ループ ✅ **完了**

### 7.1 目的
検証手順を固定し、同条件で比較できるようにする。

### 7.2 スコープ
**In:**
- ✅ 5ステップ検証サイクル（カルテ→診断→行動ルール→実践→再カルテ）
- ✅ プロンプトテンプレート（ウィークリー、デイリー）
- ✅ 測定可能な成功条件の定義
- ✅ ワークフロー例（実例ベース）

**Out:**
- 自動化されたカルテ比較ツール（手動比較で十分）
- 行動ルールの自動生成（LLMに任せる）

### 7.3 成果物
- [x] `docs/03-llm-validation.md`（LLM検証テンプレート）
- [x] `docs/examples/workflow-example-01.md`（ウィークリーコーチの例）
- [x] `docs/examples/workflow-example-02.md`（デイリーコーチの例）

### 7.4 実装内容（2025-12-31 完了）
- 5ステップ検証サイクルの確立
- プロンプトテンプレート（初回診断、継続診断、デイリー振り返り）
- 行動ルール記録フォーマット（バージョン管理）
- 改善判定基準（改善/変化なし/悪化）
- 実例ベースのワークフロー（10局→5局実践→改善測定）

### 7.5 受け入れ条件
- [x] カルテ→LLM→行動ルール→実践→再カルテのサイクルが回る
- [x] 成功条件が測定可能（客観的な数値で判定）
- [x] 主テーマ1つ + 行動ルール最大3つに絞る設計
- [x] ウィークリーコーチとデイリーコーチの使い分けが明確

### 7.6 検証サイクルの詳細

```
[1] カルテ生成（ウィークリー or デイリー）
      ↓
[2] LLM診断（弱点特定）
      ↓
[3] 行動ルール策定（最大3つ）
      ↓
[4] 実践（次の5局）
      ↓
[5] 再カルテ（改善を測定）
      ↓
   （サイクル継続）
```

### 7.7 実例（想定効果）

**初回カルテ**:
- Middle gameの大悪手: 8回、損失52.1目

**行動ルール v01**:
1. 戦いの前に「自分の石は安全か？」を確認
2. 相手の弱点（呼吸点2以下）を見つけてから動く
3. 読みが不安なら、まず連絡・補強を優先

**5局後のカルテ**:
- Middle gameの大悪手: 3回、損失18.5目

**判定**: 改善（損失64%減）

**次のアクション**: 行動ルールを継続、Openingの悪手に焦点を追加

---

## 8. Phase 10+（任意）: 拡張候補

- [ ] クイズUIの改善（表示の被り、操作性）
- [ ] コーチ画面（ルールカード、復習TODO）
- [ ] ヨセ/定石/攻め合い等の特化モジュール
- [ ] 囲碁用語辞書との自動連携
- [ ] 棋力判定システム（Tier1-5）

---

## 8.5 将来フェーズ（仕様確定済み）

詳細な設計書は `docs/specs/` を参照。

### Phase 11: 難解PVフィルタ（Human Move Filter） ✅ **完了**
- **目的**: Top Moves候補手のうち、難解なPVを含む手を除外して見やすくする
- **設定**: OFF / WEAK / MEDIUM / STRONG / AUTO
- **仕様書**: `docs/specs/human-move-filter.md`
- **実装**: PR #100（2026-01-11）
  - `PVFilterConfig` dataclass、`PVFilterLevel` enum
  - `get_pv_filter_config()`, `filter_candidates_by_pv_complexity()` 関数
  - Skill Preset連動（AUTO設定時）
  - 30件のテスト追加（`tests/test_pv_filter.py`）

### Phase 12: MuZero 3分解難易度 ✅ **完了**
- **目的**: 局面の「難しさ」をPolicy/Transition/Stateに分解し、難所抽出・解説出し分けに使用
- **用途**: 難所抽出（上位K局面）、UI表示
- **仕様書**: `docs/specs/muzero-difficulty.md`
- **実装**: PR #103（計算ロジック）、PR #104（UI表示）
  - `DifficultyMetrics` dataclass（policy/transition/state/overall）
  - `compute_difficulty_metrics()`, `extract_difficult_positions()` 関数
  - `difficulty_metrics_from_node()` public API
  - `format_difficulty_metrics()` フォーマット関数
  - 詳細パネルに「局面難易度: 易/中/難」を表示
  - 61件のテスト追加（`tests/test_difficulty_metrics.py`）

### Phase 13: Smart Kifu Learning ✅ **完了**
- **目的**: 棋譜学習・プレイヤープロファイル・Viewer Level管理
- **主要機能**: Training Set、Context分離（human/vs_katago/generated）、学習条件提案
- **仕様書**: `docs/specs/smart-kifu-learning.md`
- **実装**: PR #105（2026-01-15）
  - **Phase 13.1**: データ基盤（`katrain/core/smart_kifu/` パッケージ）
    - `models.py`: Context, ViewerPreset, Confidence enum、GameEntry, TrainingSetManifest, PlayerProfile dataclass
    - `logic.py`: compute_bucket_key(), compute_engine_profile_id(), compute_game_id(), suggest_handicap_adjustment()
    - `io.py`: manifest/profile JSON I/O, import_sgf_folder()
  - **Phase 13.2**: Training Set Manager UI（`gui/features/smart_kifu_training_set.py`）
    - Training Set一覧、新規作成、SGFフォルダ一括インポート
    - 重複判定（game_id）、インポート結果サマリー表示
  - **Phase 13.3**: Player Profile UI（`gui/features/smart_kifu_profile.py`）
    - Context切替、Bucket別カード表示、更新ワークフロー
    - Confidence表示、Viewer Level推定
  - **Phase 13.4**: 練習レポート（`gui/features/smart_kifu_practice.py`）
    - vs KataGo直近N局の勝率計算
    - 置石調整提案（勝率>70%→-1、<30%→+1、40-60%→維持）
  - 52件のテスト追加（`tests/test_smart_kifu.py`）

### Phase 14: Leelaモード推定損失 ✅ **完了**
- **目的**: Leela解析に「推定損失」（KataGo風の損失目数）を表示
- **特徴**: KataGoモードとは完全分離、winrate差からの推定損失計算
- **仕様書**: `docs/specs/leela-estimated-loss.md`
- **実装**: 2026-01-15
  - **Phase 14.0**: lz-analyze出力サンプル収集（`tests/fixtures/leela_samples/`）
  - **Phase 14.1**: データ基盤（`katrain/core/leela/models.py`, `parser.py`）
    - `LeelaCandidate`, `LeelaPositionEval` dataclass
    - `parse_lz_analyze()`, `normalize_winrate_from_raw()` 関数
  - **Phase 14.2**: 計算ロジック（`katrain/core/leela/logic.py`）
    - `compute_estimated_loss()`: winrate差からloss_est計算（K値スケーリング）
    - loss_est上限50.0、K値クランプ（0.1-2.0）
  - **Phase 14.3**: LeelaEngine（`katrain/core/leela/engine.py`）
    - GTPベースのエンジンラッパー（start/shutdown/request_analysis/cancel_analysis）
    - スレッド安全、リクエストID管理
  - **Phase 14.4**: GameNode拡張（`_leela_analysis`フィールド追加）
    - `leela_analysis` property、`set_leela_analysis()`、`clear_leela_analysis()`
  - **Phase 14.5**: 設定項目（`config.json` leela section、`constants.py` Leela定数）
  - **Phase 14.6**: UI表示（`badukpan.py` Leela候補手マーカー描画）
    - `loss_to_color()`: 損失に応じた色（緑→黄→橙→赤）
    - `draw_leela_candidates()`: Leela候補手専用描画関数
  - 114件のテスト追加（`tests/test_leela_*.py`, `tests/test_game_node_leela.py`）

### Phase 15: Leela UI統合 ✅ **完了**
- **目的**: Leela機能をUIから設定・操作可能にする
- **特徴**: 設定UI + エンジンライフサイクル管理 + 解析トリガー
- **実装**: PR #106-107（2026-01-15）
  - **Step 15.1**: 翻訳キー追加（7件）
  - **Step 15.2**: 設定UI追加（`settings_popup.py`）
    - Leela Zero有効化チェックボックス
    - 実行ファイルパス入力 + 参照ボタン
    - K値スライダー（0.1-2.0）
    - 最大訪問数入力
  - **Step 15.3**: LeelaEngine管理（`__main__.py`）
    - `start_leela_engine()`, `shutdown_leela_engine()` メソッド
    - 終了時クリーンアップ（`_cleanup_and_close()`）
  - **Step 15.4**: 解析トリガー接続
    - `request_leela_analysis()`: debounce + 多重防止
    - `_do_update_state()`: ヒントON時に自動解析
  - **Step 15.5**: 統合テスト（15件追加）
  - **バグ修正（PR #107）**:
    - UI freeze修正: `_wait_for_ready()`をバックグラウンドスレッドで実行
    - AttributeError修正: `nodes_from_root`パターンでmovesリスト構築

### Phase 16: Leela機能拡張（PV再生 + 投了目安） ✅ **完了**
- **目的**: Leela候補手のPV表示 + 投了タイミングの目安表示
- **特徴**: KataGoと同じPVパターン、動的閾値計算
- **実装**: PR #108（2026-01-15）
  - **Step 16.0**: PV再生機能（`badukpan.py`）
    - Leela候補手マーカーにホバーで読み筋（PV）表示
    - `active_pv_moves` に登録（KataGoと同じパターン）
  - **Step 16.1**: 投了目安ロジック（`logic.py`）
    - `ResignConditionResult` dataclass（`winrate_pct` property含む）
    - `check_resign_condition()`: 動的閾値計算（`max_visits * 0.8`）
    - v4修正: 固定閾値15000→動的閾値で「発火しない」バグ解消
  - **Step 16.2**: 設定項目追加（`config.json`）
    - `resign_hint_enabled`, `resign_winrate_threshold`, `resign_consecutive_moves`
  - **Step 16.3**: 投了目安ポップアップUI（`resign_hint_popup.py`新規）
    - `show_resign_hint_popup()`: UIスレッドでポップアップ表示
    - `schedule_resign_hint_popup()`: 非UIスレッドから安全に呼び出し
  - **Step 16.4**: 統合（`__main__.py`）
    - `_make_node_key()`: GC安全なキー生成（`depth:id(node)`）
    - `_check_and_show_resign_hint()`: 条件判定 + ポップアップ表示
    - `_resign_hint_shown_keys`: 同一ノードで1回のみ表示
  - **Step 16.5**: 翻訳キー追加（3件: ja/en）
  - **Step 16.6**: テスト追加（20件）
  - **成果**: 全794テストパス

### Phase 17: Leela Stats on Top Moves選択機能 ✅ **完了**
- **目的**: Leela候補手マーカーに表示する統計情報を選択可能にする
- **特徴**: KataGoと同様の選択UI、マージ方式で既存設定保持
- **実装**: PR #109（2026-01-15）
  - **Step 17.1**: 定数追加（`constants.py`）
    - `LEELA_TOP_MOVE_LOSS/WINRATE/VISITS/NOTHING`
    - `LEELA_TOP_MOVE_OPTIONS`, `LEELA_TOP_MOVE_OPTIONS_SECONDARY`
  - **Step 17.2**: 設定項目追加（`config.json`）
    - `top_moves_show`, `top_moves_show_secondary`
  - **Step 17.3**: 設定UI追加（`settings_popup.py`）
    - 2つのI18NSpinnerドロップダウン（1行目/2行目）
    - マージ方式で既存設定（resign_hint_*）を保持
  - **Step 17.4**: 描画ロジック追加（`badukpan.py`）
    - `_format_leela_stat()`: 動的なstat表示
    - ループ外でconfigキャッシュ（パフォーマンス最適化）
  - **Step 17.5**: 翻訳キー追加（5件: ja/en）
  - **Step 17.6**: テスト追加（10件）
  - **成果**: 全804テストパス（+10件）

### Phase 18: 安定性向上 ✅ **完了**
- **目的**: メモリリーク防止、UIバグ修正による安定性向上
- **特徴**: Critical修正を優先、3PR分割でリスク分離
- **実装**: PR #110-112（2026-01-15）
  - **PR #110: Critical Fixes (P1 + P2)**
    - **P1: テクスチャキャッシュLRU制限**
      - `@lru_cache` デコレータ（maxsize=500/100）で無制限成長を防止
      - `_make_hashable()`: kwargs値をhashableに変換（dict/list/set/tuple対応）
      - `_get_fallback_texture()`: 1x1透明フォールバックテクスチャ（シングルトン）
      - `_missing_resources`: ログスパム防止（同じパスは1回のみ警告）
      - `clear_texture_caches()`: 言語変更時にキャッシュクリア
    - **P2: Popup Clockバインディング修正**
      - バグ: `bind(on_dismiss=Clock.schedule_once(...))` が戻り値をbind
      - 修正: `bind(on_dismiss=self._schedule_update_state)` でメソッド参照をbind
      - `_get_app_gui()`: MDApp/App両対応のnull-safeヘルパー
      - sizeのtuple→list変換対応
    - **テスト追加（23件）**
  - **PR #111: Defensive Programming (P3 + P4)**
    - **P3: Move.from_gtp() 入力検証**
      - 不正フォーマット、不正列、負の行でValueError送出
      - 小文字入力を自動正規化（.upper()）
      - エラーメッセージに入力値を含める
    - **P4: 配列アクセスガード（既存確認）**
      - 空のmoveInfos/polmoves/top_moveのフォールバック確認
    - **テスト追加（13件）**
  - **PR #112: Optimization (P5)**
    - **P5: animate_pv インターバル遅延初期化**
      - 常時実行の100msタイマーを削除
      - `_start_pv_animation()`, `_stop_pv_animation()`: オンデマンド開始/停止
      - `_update_pv_animation_state()`: active_pv_movesに基づく自動管理
    - **テスト追加（3件）**
  - **成果**: 全843テストパス（+39件）

### Phase 19: 大規模リファクタリング ✅ **完了**
- **目的**: コードベースの保守性向上、責務分離、循環依存解消
- **特徴**: 中程度リファクタリング（Option B）を選択、段階的に実施
- **実装**: PR #113-135（2026-01-16）
  - **Phase B1: 循環依存解消**
    - `common/theme_constants.py` に `DEFAULT_FONT` 移動
    - `lang.py` から `katrain.gui.theme` への依存を解消
    - アーキテクチャ検証テスト追加
  - **Phase B2: game.py → reports/パッケージ抽出**
    - `katrain/core/reports/` パッケージ新設（5モジュール）
    - `summary_report.py`: サマリー生成ロジック
    - `quiz_report.py`: クイズ生成ロジック
    - `karte_report.py`: カルテ生成ロジック
    - `important_moves_report.py`: 重要局面レポート
    - `formatters.py`: 共通フォーマッタ
  - **Phase B3: KaTrainGui分割（部分完了）**
    - `gui/leela_manager.py`: Leela解析管理を依存注入パターンで抽出
    - `gui/sgf_manager.py`: SGF読み書き管理を抽出
    - ※ dialog_coordinator, keyboard_controller はリスク高でスキップ
  - **Phase B4: analysis/logic.py分割**
    - `logic_loss.py`: 損失計算関数を抽出
    - `logic_importance.py`: 重要度計算関数を抽出
    - `logic_quiz.py`: クイズヘルパー関数を抽出
  - **Phase B5: ai.py分割（部分完了）**
    - `ai_strategies_base.py`: 基底クラス・ユーティリティを抽出（~300行）
    - ※ ai_strategies_advanced.py は効果薄でスキップ（既に十分分割済み）
  - **Phase B6: テスト・ドキュメント**
    - `test_architecture.py`: モジュール構造・依存方向テスト追加
    - `scripts/generate_metrics.py`: メトリクス自動生成スクリプト追加
    - `docs/02-code-structure.md`: コード構造ドキュメント更新
- **スキップ項目**（理由）:
  - `dialog_coordinator.py`: 規模大・リスク高・手動テスト必須
  - `keyboard_controller.py`: リスク高・全ショートカット手動テスト必須
  - `ai_strategies_advanced.py`: 効果薄（既にai_strategies_base.pyで十分分割済み）
- **成果**:
  - テスト数: 879パス（+36件）
  - ai.py: 1,459行 → 1,061行（-27%）
  - analysis/: logic.pyをサブモジュール化（再利用性向上）
  - reports/: game.pyからレポート生成ロジックを分離
  - gui/: leela_manager, sgf_managerを依存注入パターンで抽出

### Phase 20: Guardrails + UI Polish & Cleanup ✅ **完了**
- **目的**: Phase 19リファクタリングの成果を保護し、core層のKivy依存を削除
- **特徴**: アーキテクチャ強制テスト + Kivy/GUI依存の完全分離
- **実装**: PR #131-135（2026-01-16）
  - **PR #131: A-1 インポート禁止テスト**
    - `AllImportCollector`: AST解析で全インポートを収集（関数内遅延インポート含む）
    - TYPE_CHECKINGブロックの正確なスキップ
    - 禁止プレフィックス: `kivy`, `kivymd`, `kivy_garden`, `katrain.gui`
    - DELETE-ONLYポリシー: ハードコードセットで新規エントリ追加を阻止
    - staleエントリ検出: 削除済みインポートの許可リスト残骸を検出
    - 単体テスト: `_resolve_relative_import()`、`is_forbidden()`
  - **PR #132: A-2a platform互換関数**
    - `katrain/common/platform.py` 新規作成
    - `get_platform()`: `sys.platform`ベースのOS判定
    - `engine.py`から`kivy.utils.platform`依存を削除
  - **PR #133: A-2b 未使用Clock削除**
    - `game.py`から未使用の`kivy.clock.Clock`インポートを削除
  - **PR #134: A-2c JsonFileConfigStore**
    - `katrain/common/config_store.py` 新規作成
    - `collections.abc.Mapping`プロトコル完全実装
    - `dict(store)`変換が正常動作
    - `base_katrain.py`から`kivy.storage.jsonstore`依存を削除
    - 16件のテスト追加
  - **PR #135: A-2d lang/i18nブリッジ**
    - `core/lang.py`: Observable継承削除、コールバックベースに変更
    - `gui/lang_bridge.py` 新規作成: KivyLangBridge（fbind/funbind互換）
    - `gui.kv`、`popups.kv`: i18nインポート先を変更
    - 既存KVファイルの変更不要（レガシーAPI互換維持）
- **許可リスト削減**:
  - 6エントリ → 1エントリ（`core/base_katrain.py|kivy` のみ残存）
  - 残りは`PR #139`で削除予定（Kivy Config for logging）
- **成果**:
  - 全879テストパス
  - core層のKivy依存を大幅削減
  - 将来のヘッドレステスト・CLIツール対応の基盤確立

### Phase 21: Settings Popup タブ化 ✅ **完了**
- **目的**: 13設定項目を3タブに再編成し、視認性・操作性を向上
- **実装**: PR #136（2026-01-16）
  - **TabbedPanel導入**:
    - Tab 1: 解析設定（Skill Preset, PV Filter Level）
    - Tab 2: 出力設定（Default User Name, Karte Output Directory, Batch Export Input Directory, Karte Format, Opponent Info Mode）
    - Tab 3: Leela Zero（Enabled, Executable Path, K Value, Max Visits, Top Moves Display）
  - **ScrollView構造変更**: 外側ScrollView削除、各タブ内にScrollView（ネスト回避）
  - **i18n更新**: タブタイトル3件追加（EN/JP）
  - **WeakProxy修正**: `lang_bridge.py`の弱参照互換性問題を修正
- **成果**:
  - 全904テストパス
  - 設定ポップアップのUX改善

### Phase 22: 安定性向上 ✅ **完了**
- **目的**: アプリケーションの安定性向上（クラッシュ、フリーズ、リソースリークの防止）
- **実装**: PR #137-140（2026-01-16）
  - **PR #137: Quick Wins（Issue #3, #5）**
    - `popups.py`: dismiss遅延を1秒→0.1秒に短縮、前イベントキャンセル
    - `__main__.py`: Clock event追跡、cleanup()メソッド追加
    - `controlspanel.py`: timer event追跡、cleanup()メソッド追加
  - **PR #138: Thread Safety（Issue #2, #4）**
    - `terminate_query`: ロック追加
    - `wait_to_finish`: ロック追加、ローカルキャプチャパターン
    - 全スレッド関数: TOCTOUパターン統一、例外ハンドリング拡張
  - **PR #139: I/O Timeout（Issue #1）**
    - Queue方式I/O: `_stdout_queue`, `_stderr_queue`
    - `_pipe_reader_thread`: ブロッキングI/Oを分離
    - `_shutdown_event`: 再起動時に再作成（clear()ではない）
    - シャットダウンシーケンス改善（7ステップ）
    - `_handle_engine_timeout`: 回復ポップアップ対応
  - **PR #140: Stability Tests**
    - 10件の自動テスト追加（スレッド安全性、タイムアウト、TOCTOU）
- **成果**:
  - 全914テストパス（+10件）
  - KataGoハング時のフリーズ防止
  - アプリ終了時のリソースリーク防止
  - スレッド競合によるクラッシュ防止

---

### Phase 24: Regression Tests / Golden Fixtures（SGF E2E）✅ **完了**

#### 24.1 目的
SGF→karte/summary の E2E テストを既存 golden test に統合し、出力の回帰を防止する。

#### 24.2 スコープ
**In:**
- ✅ 実SGF入力のE2Eテストを `test_golden_karte.py`/`test_golden_summary.py` に追加
- ✅ `--update-goldens` フラグでの期待値更新
- ✅ 既存 `conftest.py` の `update_golden_if_requested()` を活用

**Out:**
- KataGo 解析の再実行（モック解析注入で代替）
- UI 操作のテスト

#### 24.3 成果物
- [x] `tests/helpers/` パッケージ新設
  - `mock_analysis.py`: `LOSS_AT_MOVE` パターン、`inject_mock_analysis()`
  - `stats_extraction.py`: `extract_stats_from_nodes()` for summary tests
- [x] `tests/conftest.py` 拡張
  - `is_ci_environment()`: CI環境検出
  - `normalize_output()`: 改行正規化（CRLF→LF）、スペース区切り時刻形式対応
- [x] `tests/test_golden_karte.py` への `TestKarteFromSGF` 追加
- [x] `tests/test_golden_summary.py` への `TestSummaryFromSGF` 追加
- [x] 7つの新規 Golden ファイル
  - `karte_sgf_fox.golden`, `karte_sgf_alphago.golden`, `karte_sgf_panda.golden`
  - `summary_sgf_fox.golden`, `summary_sgf_alphago.golden`, `summary_sgf_panda.golden`, `summary_sgf_multi.golden`

#### 24.4 受け入れ条件
- [x] 3 SGFファイル（fox, alphago, panda）で karte/summary 生成が安定
- [x] 決定性テストで出力の一貫性を確認
- [x] `uv run pytest tests/test_golden_karte.py tests/test_golden_summary.py -v` パス（全957テスト）

#### 24.5 実装（PR #142）
- **tests/helpers/**: モック解析注入ユーティリティ
  - `LOSS_AT_MOVE`: 決定的な損失パターン（手5=2.5目, 17=6.0目, 34=12.0目）
  - `inject_mock_analysis()`: Game オブジェクトにモック解析を直接注入
  - `extract_stats_from_nodes()`: モック解析から統計dict抽出
- **tests/conftest.py**: 正規化強化
  - CI環境検出（GitHub Actions, GitLab CI等対応）
  - 改行コード正規化（CRLF→LF）
  - スペース区切り時刻形式の正規化（`HH MM SS` → `[TIME]`）
- **テストカバレッジ**: 3 SGF × (karte + summary) + 決定性テスト

---

### Phase 25: LLM Package Export ✅ **完了**

#### 25.1 目的
karte + SGF + coach.md を zip パッケージでエクスポートし、LLM への添付を容易にする。

#### 25.2 スコープ
**In:**
- ✅ zip ファイル生成（karte.md + SGF + coach.md + manifest.json）
- ✅ manifest.json（ファイル一覧、生成日時、バージョン）
- ✅ PB/PW 匿名化オプション（文字列ベース、SGFツリー非変更）
- ✅ **プライバシー保護**: manifest に絶対パス・ユーザー名を含めない

**Out:**
- LLM への自動送信（non-goal）
- SGF の加工（分岐削除等）

#### 25.3 成果物
- [x] `katrain/core/reports/package_export.py` - ZIP生成ロジック（Kivy非依存）
- [x] `katrain/gui/features/package_export_ui.py` - Export Package UI
- [x] `tests/test_package_export.py` - 40ユニットテスト

#### 25.4 受け入れ条件
- [x] Export Package ボタンで zip がダウンロードフォルダに保存
- [x] manifest.json にファイル一覧と生成条件が記録（相対パスのみ）
- [x] 匿名化 ON で PB/PW が "Black"/"White" に置換（文字列ベース）

#### 25.5 実装（PR #143）
- **Core層（package_export.py）**: ZIP生成、manifest構築、匿名化ヘルパー、出力先解決
- **GUI層（package_export_ui.py）**: UI実装、匿名化処理の前処理
- **責務分離**: GUI層で匿名化完了後、Core層は純粋にZIP生成のみ
- **テスト**: 40ユニットテスト（Kivy不要、CI対応）
- **i18n**: 英語・日本語翻訳キー追加

---

### Phase 26: レポート閲覧/導線の小改善 ✅

#### 26.1 目的
生成レポートへのアクセスを改善し、ユーザビリティを向上。

#### 26.2 スコープ
**In:**
- 「最新レポートを開く」メニュー項目 ✅
- 「出力フォルダを開く」メニュー項目（OS ファイルマネージャ起動）✅

**Out (Phase 27以降へ延期):**
- Context / Bucket / engine_profile_id の表示（Smart Kifu 連携）
- レポート履歴管理（DB 化）

#### 26.3 成果物
- `katrain/common/file_opener.py` - OS 別ファイル/フォルダオープナー（Kivy非依存）
- `katrain/gui/features/report_navigator.py` - 導線 UI
- `tests/test_file_opener.py` - 19テスト
- `tests/test_report_navigator.py` - 15テスト

#### 26.4 クロスプラットフォーム対応
| Platform | Open Folder | Open File | Open File in Folder |
|----------|-------------|-----------|---------------------|
| Windows | os.startfile() | os.startfile() | explorer /select, |
| macOS | open | open | open -R |
| Linux | xdg-open | xdg-open | xdg-open (parent) |

---

### Phase 27: Settings UIスケーラブル化（TBD）

#### 27.1 目的
設定検索・Export/Import・タブ別リセット機能を追加。

#### 27.2 スコープ
**In:**
- 設定検索（キーワードで項目をフィルタ/ハイライト）
- 設定 Export / Import（JSON 形式）
- タブ別リセット機能

**Out:**
- Advanced / Experimental タブ隔離（現状のタブ構成を維持）
- クラウド同期

#### 27.3 成果物
- `katrain/gui/features/settings_search.py` - 検索 UI コンポーネント
- `katrain/common/settings_export.py` - Export/Import ロジック

---

### Phase 28: Smart Kifu運用強化（TBD）

#### 28.1 目的
Smart Kifu とバッチ解析の連携強化、解析率の可視化。

#### 28.2 スコープ
**In:**
- バッチ解析からの Training Set 自動登録導線
- 解析率表示（解析済み/未解析の割合）
- Training Set の解析ステータスサマリー

**Out:**
- 自動解析スケジューリング
- クラウドストレージ連携

#### 28.3 成果物
- `katrain/gui/features/smart_kifu_batch_bridge.py` - バッチ連携 UI
- Training Set Manager への「解析率」列追加

---

### Phase 29: Diagnostics + Bug Report Bundle（TBD）

#### 29.1 目的
バグ報告用の診断情報収集を容易にする。

#### 29.2 スコープ
**In:**
- 診断画面（システム情報、KataGo バージョン、設定サマリー）
- zip 出力（ログ、設定スナップショット、システム情報）
- 「バグ報告用データを生成」ボタン
- **プライバシー保護（サニタイズ）**:
  - 絶対パスをマスキング（`C:\Users\xxx\...` → `<USER_HOME>/...`）
  - ユーザー名・マシン名を除去
  - ログ内の個人情報（SGFパス等）を正規化

**Out:**
- SGF / 棋譜の自動添付
- 自動送信

#### 29.3 成果物
- `katrain/gui/features/diagnostics_popup.py` - 診断画面 UI
- `katrain/core/diagnostics.py` - 情報収集ロジック

---

### Phase 30: 検証テンプレ運用の導線（TBD）

#### 30.1 目的
`03-llm-validation.md` の検証サイクルを UI から簡単に開始できるようにする。

#### 30.2 スコープ
**In:**
- 「検証サイクルを開始」ショートカット（テンプレをクリップボードにコピー）
- プロンプトテンプレートの選択 UI
- 行動ルール記録用テンプレート生成

**Out:**
- LLM への自動送信
- 行動ルールの DB 管理

#### 30.3 成果物
- `katrain/gui/features/validation_helper.py` - 検証支援 UI

---

## 9. スモークテスト チェックリスト

リリース前に2分以内で確認できる主要UXパスのチェックリスト。

### Batch Analyze Folder

- [ ] **Timeout入力**: `None` / 空文字 / 数値 / 無効文字列 → クラッシュしないこと
- [ ] **FileChooser**: 保存されたパスが存在しない → クラッシュせず、選択可能になること
- [ ] **Variable Visits**: Deterministic ON → 同じSGFに対して繰り返し実行で同じvisits選択
- [ ] **完了音**: Sound on finish ON → バッチ完了時に1回だけ再生

### 判定の厳しさ

- [ ] **5段階表示**: 激甘/甘口/標準/辛口/激辛 が選択可能
- [ ] **閾値反映**: プリセット変更 → カルテ/サマリーの Definitions セクションに反映

### カルテ出力

- [ ] **単局カルテ**: Export Karte → `reports/karte/` にファイル生成
- [ ] **複数局サマリー**: Batch Analyze → `reports/summary_互先_*.md` にファイル生成

---

## 10. "Done"の共通定義

- [ ] `00-purpose-and-scope.md` に矛盾しない
- [ ] 仕様の正本に反映されている
- [ ] 最小テスト手順があり、再現できる

---

## 11. 変更履歴

- 2026-01-17: Phase 26 レポート導線改善完了（PR #144）
  - **common/file_opener.py**: クロスプラットフォームファイル/フォルダオープナー
  - **gui/features/report_navigator.py**: レポート導線UI
  - **機能**: 「最新レポートを開く」「出力フォルダを開く」メニュー項目
  - **対応OS**: Windows (os.startfile/explorer)、macOS (open)、Linux (xdg-open)
  - **テスト**: 34新規テスト、全1031テストパス
- 2026-01-17: Phase 24 Regression Tests (SGF E2E) 完了（PR #142）
  - **tests/helpers/**: モック解析注入パッケージ新設
    - `mock_analysis.py`: `LOSS_AT_MOVE` パターン、`inject_mock_analysis()`
    - `stats_extraction.py`: `extract_stats_from_nodes()`
  - **tests/conftest.py**: 正規化強化
    - `is_ci_environment()`: CI環境検出
    - 改行正規化（CRLF→LF）、スペース区切り時刻形式対応
  - **TestKarteFromSGF**: 3 SGF（fox, alphago, panda）のE2Eテスト
  - **TestSummaryFromSGF**: 3 SGF + 複数SGF統合テスト
  - **成果**: 7つの新規Goldenファイル、全957テストパス
- 2026-01-17: Phase 25 LLM Package Export完了（PR #143）
  - **Core層（package_export.py）**: ZIP生成、manifest構築、匿名化ヘルパー
  - **GUI層（package_export_ui.py）**: UI実装、Kivy Clock統合
  - **責務分離**: GUI層で匿名化完了後、Core層は純粋にZIP生成のみ
  - **テスト**: 40ユニットテスト（Kivy不要、CI対応）
  - **i18n**: 英語・日本語翻訳キー追加
  - **成果**: 全997テストパス
- 2026-01-16: Phase 24〜30 ロードマップ追加
  - **Phase 24**: Regression Tests (SGF E2E) - 既存golden testに実SGFケース追加
  - **Phase 25**: LLM Package Export - zip + manifest + PB/PW匿名化
  - **Phase 26**: レポート導線改善 - 最新レポートを開く、フォルダを開く
  - **Phase 27**: Settings UI拡張 - 検索、Export/Import、タブ別リセット
  - **Phase 28**: Smart Kifu運用強化 - バッチ連携、解析率表示
  - **Phase 29**: Diagnostics - 診断画面、Bug Report zip（サニタイズ付き）
  - **Phase 30**: 検証テンプレ導線 - ショートカット、テンプレコピー
  - **優先度**: S = 24,25,27,29 / A = 26,28,30
- 2026-01-16: Phase 23 カルテ・サマリー品質向上完了（PR #141）
  - **PR #1**: ONLY_MOVE難易度修正緩和（-2.0 → -1.0、大損失時+0.5緩和）
    - `get_difficulty_modifier()` に `canonical_loss` パラメータ追加
    - 一択局面でも大損失は学習価値があるため重要度を保持
  - **PR #2**: LLM用JSON出力オプション追加
    - `build_karte_json()` 関数（schema v1.0）
    - meta, summary, important_moves セクション
    - `get_canonical_loss_from_move()` 使用で一貫性確保
  - **PR #3**: サマリー型ヒント追加
    - `summary_formatter.py` に型エイリアス・型ヒント追加
    - Snapshot Test による回帰防止
  - **テスト追加（32件）**:
    - `test_difficulty_modifier.py` (12件)
    - `test_karte_json.py` (16件)
    - `test_summary_snapshot.py` (4件)
  - **成果**: 全946テストパス
- 2026-01-16: Phase 22 安定性向上完了（PR #137-140）
  - デッドロック予防強化（PR #100-102でのフォローアップ）
  - エンジンシャットダウンにタイムアウトとログ追加
- 2026-01-16: Phase 21 Settings Popup タブ化完了（PR #136）
  - TabbedPanel導入、13設定を3タブに再編成
  - lang_bridge.py WeakProxy互換性修正
  - 全904テストパス
- 2026-01-16: Phase 20 Guardrails + UI Polish完了（PR #131-135）
  - **PR #131**: AllImportCollector + アーキテクチャ強制テスト
    - AST解析で全インポート収集（関数内遅延インポート含む）
    - TYPE_CHECKINGブロックの正確なスキップ
    - DELETE-ONLYポリシー: ハードコードセットで新規エントリ追加を阻止
    - 単体テスト: `_resolve_relative_import()`, `is_forbidden()`
  - **PR #132**: `common/platform.py` 新規作成、engine.pyからKivy依存削除
  - **PR #133**: `game.py`から未使用Clock削除
  - **PR #134**: `common/config_store.py` 新規作成、Mapping完全実装（16テスト）
  - **PR #135**: lang/i18nブリッジ、core/lang.pyからKivy依存削除
  - **成果**: 許可リスト6→1エントリに削減、全879テストパス
- 2026-01-16: Phase 19 大規模リファクタリング完了（PR #113-135）
  - **Phase B1**: 循環依存解消（common/theme_constants.py）
  - **Phase B2**: game.py → reports/パッケージ抽出（5モジュール）
  - **Phase B3**: KaTrainGui分割（leela_manager, sgf_manager）※部分完了
  - **Phase B4**: analysis/logic.py分割（loss, importance, quiz）
  - **Phase B5**: ai.py分割（ai_strategies_base.py）※部分完了
  - **Phase B6**: アーキテクチャテスト・ドキュメント
  - **スキップ**: dialog_coordinator, keyboard_controller, ai_strategies_advanced（リスク高/効果薄）
  - **成果**: 全879テストパス（+36件）、ai.py -27%削減
- 2026-01-15: Phase 18 安定性向上完了（PR #110-112）
  - **PR #110: Critical Fixes (P1 + P2)**
    - P1: テクスチャキャッシュLRU制限（`@lru_cache`, `_make_hashable()`, fallback texture）
    - P2: Popup Clockバインディング修正（`_get_app_gui()`, メソッド参照bind）
    - テスト追加: 23件
  - **PR #111: Defensive Programming (P3 + P4)**
    - P3: Move.from_gtp() 入力検証（ValueError送出、小文字正規化）
    - P4: 配列アクセスガード確認
    - テスト追加: 13件
  - **PR #112: Optimization (P5)**
    - P5: animate_pv インターバル遅延初期化（オンデマンド開始/停止）
    - テスト追加: 3件
  - **成果**: 全843テストパス（+39件）
- 2026-01-15: Phase 17 Leela Stats on Top Moves選択機能完了（PR #109）
  - **Step 17.1**: 定数追加（`LEELA_TOP_MOVE_*`）
  - **Step 17.2**: 設定項目追加（`top_moves_show`, `top_moves_show_secondary`）
  - **Step 17.3**: 設定UI追加（I18NSpinner×2 + マージ方式保存）
  - **Step 17.4**: 描画ロジック追加（`_format_leela_stat()` + configキャッシュ）
  - **Step 17.5**: 翻訳キー追加（5件: ja/en）
  - **Step 17.6**: テスト追加（10件）
  - **成果**: 全804テストパス（+10件）
- 2026-01-15: Phase 16 Leela機能拡張完了（PR #108）
  - **Step 16.0**: PV再生機能（`badukpan.py`）
    - Leela候補手マーカーにホバーで読み筋表示
    - KataGoと同じ `active_pv_moves` パターン使用
  - **Step 16.1**: 投了目安ロジック（`logic.py`）
    - `ResignConditionResult` dataclass
    - `check_resign_condition()`: 動的閾値計算（`max_visits * 0.8`）
  - **Step 16.2**: 設定項目追加（3項目: resign_hint_enabled等）
  - **Step 16.3**: 投了目安ポップアップUI（`resign_hint_popup.py`新規）
  - **Step 16.4**: 統合（`__main__.py`）
    - `_make_node_key()`: GC安全なキー生成
    - `_check_and_show_resign_hint()`: 条件判定 + 表示
  - **Step 16.5**: 翻訳キー追加（3件: ja/en）
  - **Step 16.6**: テスト追加（20件）
  - **成果**: 全794テストパス
- 2026-01-15: Phase 15 Leela UI統合完了（PR #106-107）
  - **Step 15.1**: 翻訳キー追加（7件: ja/en）
  - **Step 15.2**: 設定UI追加（`settings_popup.py`）
    - Leela有効化、パス選択、K値スライダー、最大訪問数
  - **Step 15.3**: LeelaEngine管理（`__main__.py`）
    - `start_leela_engine()`, `shutdown_leela_engine()`
    - 終了時クリーンアップ
  - **Step 15.4**: 解析トリガー接続
    - debounce + 多重防止、ヒントON時自動解析
  - **Step 15.5**: 統合テスト15件追加
  - **バグ修正（PR #107）**:
    - UI freeze: `_wait_for_ready()`をバックグラウンドスレッド化
    - AttributeError: `nodes_from_root`パターン使用
  - **成果**: 全774テストパス
- 2026-01-15: Phase 14 Leelaモード推定損失完了
  - **Phase 14.0**: lz-analyze出力サンプル収集（Leela 0.110のwinrate形式は0-10000と判明）
  - **Phase 14.1**: データ基盤（`katrain/core/leela/models.py`, `parser.py`）
    - `LeelaCandidate`, `LeelaPositionEval` dataclass
    - `parse_lz_analyze()`, `normalize_winrate_from_raw()` 関数（自動単位判定）
  - **Phase 14.2**: 計算ロジック（`katrain/core/leela/logic.py`）
    - `compute_estimated_loss()`: immutableパターン（新オブジェクト返却）
    - K値スケーリング、loss_est上限50.0、K値クランプ（0.1-2.0）
  - **Phase 14.3**: LeelaEngine（`katrain/core/leela/engine.py`）
    - GTPベースエンジンラッパー（スレッド安全、リクエストID管理）
  - **Phase 14.4**: GameNode拡張（KataGoとは完全分離の`_leela_analysis`フィールド）
  - **Phase 14.5**: 設定項目（`config.json` leela section、色定数追加）
  - **Phase 14.6**: UI表示（`badukpan.py` に`draw_leela_candidates()`追加）
  - **Phase 14.7**: 統合テスト + ドキュメント更新
  - **成果**: 114件のテスト追加、KataGo回帰なし
- 2026-01-15: Phase 13 Smart Kifu Learning完了（PR #105）
  - **Phase 13.1**: データ基盤（`katrain/core/smart_kifu/` パッケージ）
    - `models.py`: Enum（Context, ViewerPreset, Confidence）、Dataclass（GameEntry, TrainingSetManifest, PlayerProfile等）
    - `logic.py`: bucket_key計算、engine_profile_id計算、game_id（正規化ハッシュ）、置石調整提案
    - `io.py`: manifest/profile JSON I/O、SGFインポート（重複チェック含む）
  - **Phase 13.2**: Training Set Manager UI
    - Training Set一覧、新規作成ダイアログ、SGFフォルダ一括インポート
    - インポート結果サマリー（成功/重複/失敗）
  - **Phase 13.3**: Player Profile UI
    - Context切替タブ、Bucket別カード表示、更新ワークフロー（N局選択→プレビュー→採用）
  - **Phase 13.4**: 練習レポート
    - vs KataGo直近10局の勝率計算、置石調整提案
  - **メニュー統合**: myKatrainメニューに3項目追加
  - **成果**: 52件のテスト追加、全648テストパス
- 2026-01-14: Phase 12 MuZero 3分解難易度完了（PR #103-104）
  - **PR #103**: 難易度計算ロジック
    - `DifficultyMetrics` dataclass（policy/transition/state/overall）
    - `compute_difficulty_metrics()`, `extract_difficult_positions()` 関数
    - 信頼性ガード（visits/候補数）
    - 53件のテスト追加
  - **PR #104**: 難易度UI表示（Phase 12.5）
    - `difficulty_metrics_from_node()` public API
    - `get_difficulty_label()`, `format_difficulty_metrics()` フォーマット関数
    - 詳細パネルに「局面難易度: 易/中/難（0.XX）」表示
    - 信頼度低表示: ⚠ + [信頼度低]
    - 8件のフォーマットテスト追加
  - **成果**: 全596テストパス
- 2026-01-13: Phase 11 難解PVフィルタ完了 + デッドロック予防（PR #100-102）
  - **PR #100 (Phase 11)**: 難解PVフィルタ実装
    - `PVFilterConfig` dataclass、`PVFilterLevel` enum
    - `get_pv_filter_config()`, `filter_candidates_by_pv_complexity()` 関数
    - 5段階設定: OFF / WEAK / MEDIUM / STRONG / AUTO
    - Skill Preset連動（AUTO: relaxed/beginner→WEAK、standard→MEDIUM、advanced/pro→STRONG）
    - 30件のテスト追加（`tests/test_pv_filter.py`）
  - **PR #101**: ポンダリング停止時のデッドロック修正
    - `_write_stdin_thread()` 内の `stop_pondering()` 呼び出しをロック外に移動
    - `_stop_pondering_unlocked()` パターン導入
  - **PR #102**: デッドロック予防強化
    - `wait_to_finish()` に30秒タイムアウト追加（無限ループ防止）
    - `shutdown()` にデバッグログ追加（問題発生時の診断支援）
    - CLAUDE.md にロック設計ガイドライン追記
  - **成果**: 全535テストパス
- 2026-01-10: Phase 2 安定性向上（PR #97）
  - **目的**: 散在するエラー処理を集約し、Kivyイベントループの安定化
  - **エラー階層**: `katrain/core/errors.py` 新規作成
    - KaTrainError基底クラス（user_message + context）
    - サブクラス: EngineError, ConfigError, UIStateError, SGFError
  - **ErrorHandler**: `katrain/gui/error_handler.py` 新規作成
    - thread-safe（Clock.schedule_once使用）
    - never-throw保証（handle()自体が例外を投げない）
    - traceback logging（DEBUG level）
  - **統合箇所**: 3箇所のみ（最小スコープ）
    - _message_loop_thread: アクション実行エラー捕捉
    - engine.on_error: EngineErrorラップ + リッチコンテキスト
    - load_ui_state: 起動時エラー安全スキップ
  - **成果**: 全510テストパス、成功パスの動作変更なし
- 2026-01-07: コードベース簡素化（PR #90-92）
  - **目的**: Windows専用教育フォーク向けに不要機能を削除
  - **Phase 1（PR #90）**: Contribute Engine削除 + pygame依存削除
    - `contribute_engine.py` 削除（~300行）
    - `ContributePopup` UI削除（~180行）
    - pygame依存削除（macOS専用）
  - **Phase 2（PR #91）**: 多言語i18n削除（JP+EN以外）
    - 9言語のlocaleディレクトリ削除（cn,de,es,fr,ko,ru,tr,tw,ua）
    - ~12,200行削減
  - **残存参照クリーンアップ（PR #92）**:
    - `KEY_CONTRIBUTE_POPUP` 参照削除（緊急バグ修正）
    - `lang.py` FONTS から削除済み言語(tr,ua)を除去
    - `99-worklog.md` 参照を4ファイルから削除
  - **Phase 3**: AI戦略UIプリセット化（将来実装として延期）
  - **成果**: 合計~12,800行削減、全510テストパス
- 2026-01-06: Phase 4 安定化（PR #81-89）
  - **目的**: gui/features パッケージのテスト追加と品質向上
  - **テスト追加（PR #81-85）**: summary_stats, summary_aggregator, karte_export
    - 77件の新規テスト追加
  - **型ヒント改善（PR #86）**: TypedDict風Dict型エイリアス（BatchWidgets, GameStats等）
  - **エラーロギング改善（PR #87）**: silent exception → logger.debug
  - **設定管理Protocol統一（PR #88）**: _config直接アクセスを6箇所排除
    - controlspanel.py: save_ui_state()
    - popups.py: dist_models
    - __main__.py: sgf_load/save, language, window state
  - **UIヘルパー追加（PR #89）**: `katrain/gui/widgets/helpers.py` 新規作成
    - `bind_label_text_size()`, `create_styled_label()`, `create_text_input_row()`
    - settings_popup.py の重複コード削減（23行→5行）
  - **成果**: 全510テストパス、Protocol準拠の設定管理に完全統一
- 2026-01-06: __main__.py モジュール分割 Phase 3 完了（PR #62-80）
  - **目的**: 4,000行超の __main__.py を機能別モジュールに分割
  - **新規パッケージ**: `katrain/gui/features/`（13モジュール）
    - `context.py`: FeatureContext Protocol
    - `karte_export.py`: カルテエクスポート機能
    - `summary_*.py`: サマリ関連（stats/aggregator/formatter/ui/io）
    - `quiz_*.py`: クイズ機能（popup/session）
    - `batch_*.py`: バッチ解析（core/ui）
    - `settings_popup.py`: 設定ポップアップ
  - **共通基盤**: `katrain/common/theme_constants.py`（循環依存解消）
  - **成果**: ~3,290行を抽出、__main__.py は~1,200行に削減
  - **リグレッション**: ゼロ（全433テストパス）
- 2026-01-05: eval_metrics.py リファクタリング Phase B 完了（PR #54-57）
  - **PR #54 (Phase A)**: eval_metrics.py → analysis/core.py + facade
    - 約2500行を analysis パッケージに移動
    - eval_metrics.py は再エクスポート用ファサード（21行）に
  - **PR #55 (Phase B-3)**: core.py → models/logic/presentation 分離
    - models.py: Enum, Dataclass, 定数（~900行）
    - logic.py: 計算関数（~1300行）
    - presentation.py: 表示/フォーマット関数（~330行）
  - **PR #56 (Phase B-1)**: ラベル定数を presentation.py に移動
    - SKILL_PRESET_LABELS, CONFIDENCE_LABELS, REASON_TAG_LABELS
    - models.py に `__getattr__` で後方互換維持
  - **PR #57 (Phase B-2)**: star-import → 明示的インポート
    - __init__.py で全~80シンボルを明示的にインポート
    - IDE自動補完・静的解析対応改善
  - **成果**: 関心の分離達成、ゼロリグレッション（全384テストパス）
- 2026-01-05: Karte/Summary品質向上4連PR（PR #50-53）
  - **PR #50 Confidence Gating**: 解析信頼度に基づくセクション制御
    - `ConfidenceLevel` enum (HIGH/MEDIUM/LOW)
    - `compute_confidence_level()` 関数
    - `reliability_pct` 分母を `moves_with_visits` に変更
    - MIN_COVERAGE_MOVES (5) ガード
    - LOW confidence で警告表示・ヘッジ表現
  - **PR #51 Evidence Attachments**: 結論に具体例を添付
    - `select_representative_moves()` - score_loss 使用、None スキップ
    - `format_evidence_examples()` - i18n対応 (ja/en)
    - Weakness Hypothesis / Practice Priorities / Urgent Miss に例追加
    - 10件の新規テスト追加
  - **PR #52 Golden Tests**: スナップショットテスト基盤
    - `tests/conftest.py` - 共通ヘルパー、`normalize_output()`
    - `--update-goldens` pytest オプション
    - Confidence境界値テスト、決定論的ソートテスト
    - 18件の新規テスト追加
  - **PR #53 Important Move Ranking Redesign**: 学習価値ベースのランキング
    - 新公式: `canonical_loss + swing + difficulty_modifier + streak_start_bonus`
    - `get_difficulty_modifier()` - HARD +1.0, ONLY_MOVE -2.0
    - `get_reliability_scale()` - 段階的スケーリング (0.3-1.0)
    - 決定論的タイブレーク (move_number 昇順)
    - 17件の新規テスト追加
  - 合計: 55件の新規テスト、全384件パス
- 2026-01-05: Variable Visits と完了音（PR #47）
  - choose_visits_for_sgf() によるファイル別visits変動
  - Deterministic モード（MD5ハッシュで再現性確保）
  - Jitter上限25%
  - 完了音通知（Sound on finish）
  - 10件の新規テスト追加
- 2026-01-05: Auto strictness オプション（PR #46）
  - 「自動」オプション追加（6つ目のラジオボタン）
  - recommend_auto_strictness() によるプリセット推奨
  - 信頼性ゲート（reliability < 20% → standard）
- 2026-01-05: ロードマップ整理
  - フェーズ一覧テーブルにPhase 4/4.5を追加
  - セクション番号の重複修正（8→8,9,10,11）
  - スモークテストチェックリスト追加（セクション9）
  - Phase 4.5に2026-01拡張内容を追記
- 2026-01-05: 5レベル棋力プリセット実装（PR #45）
  - relaxed/beginner/standard/advanced/pro の5段階
  - 日本語ラベル: 激甘/甘口/標準/辛口/激辛
  - URGENT_MISS_CONFIGS も5段階対応
  - 11件の新規テスト追加
- 2026-01-05: バッチ解析タイムアウト修正（PR #44）
- 2026-01-04: バッチ解析UX改善（PR #42）
  - プレイヤーフィルタUI
  - per-player summary生成
  - バッチオプション永続化
- 2026-01-03: バッチ解析エラーハードニング（PR #41）
  - エラーカウントと表示改善
- 2026-01-03: 拡張バッチ解析機能（PR #40）
  - カルテ/サマリー自動生成
- 2025-12-31: カルテ出力最適化
  - LLM最適化カルテ出力実装
  - Freedom Distribution セクション削除（100% UNKNOWN、価値ゼロ）
  - Phase Breakdown セクション削除（Phase × Mistake で代替可能）
  - Meta の "Generated" タイムスタンプ削除（LLM不要）
  - 1局カルテの Freedom buckets/列削除（常にunknown）
  - トークン削減: 複数局約620トークン、1局約100トークン
  - 情報損失: 0%（重要セクションは全て保持）
- 2025-12-31: Phase 9完了を反映
  - LLM検証テンプレート作成（`docs/03-llm-validation.md`）
  - ワークフロー例作成（ウィークリーコーチ、デイリーコーチ）
  - 5ステップ検証サイクルの確立
  - 測定可能な改善指標の定義
  - 主テーマ1つ + 行動ルール最大3つの設計
- 2025-12-31: Phase 7完了を反映
  - Phase × Mistake クロス集計テーブルを複数局サマリーに追加
  - 弱点仮説自動生成（単局カルテ + 複数局サマリー）
  - Practice Priorities の精度向上（クロス集計から上位2-3個を抽出）
  - 統合テスト完了（分類ロジック、クロス集計、弱点抽出）
- 2025-12-31: Phase 6 + 6.5完了を反映、Phase 7を「単局カルテUI + カルテ品質向上」に再定義
  - Phase 6: 複数局まとめカルテ完了（summary.md、プレイヤーフィルタ、importance スコア）
  - Phase 6.5: eval_metrics.py 品質向上完了（PositionDifficulty、importance 自動計算、クロス集計）
  - Phase 7: デイリーコーチ（単局カルテ）+ カルテ品質向上に焦点
  - Phase 8: 初心者向けヒントは任意機能として後回し
- 2025-12-31: Phase 5完了を反映（カルテ出力 + Freedom追加 + LLM連携テスト成功）
- 2025-12-30: Claude Code移行対応で整理、Phase 4.5完了を反映
- 2025-12-26: v0.1作成
