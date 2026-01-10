# myKatrain（PC版）ロードマップ

> 最終更新: 2026-01-10
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
| 5 | 1局カルテを安定出力 | `karte.md` + アンカー規則 | ✅ **完了** |
| 6 | 複数局まとめで"悪癖"抽出 | `summary.md`（傾向） | ✅ **完了** |
| 6.5 | eval_metrics.py 品質向上 | production-ready 基盤 | ✅ **完了** |
| 7 | 単局カルテUI + カルテ品質向上 | デイリーコーチ完成 | ✅ **完了** |
| 9 | 検証テンプレで改善ループ | `03-llm-validation.md` | ✅ **完了** |
| 8 | 初心者向けヒント（任意） | 構造解析 + テンプレ | TBD |
| 10+ | クイズ/コーチUIの拡張 | [TBD] | TBD |
| 11 | 難解PVフィルタ | Top Moves表示改善 | 📋 **仕様確定** |
| 12 | MuZero 3分解難易度 | 難所抽出・解説出し分け | 📋 **仕様確定** |
| 13 | Smart Kifu Learning | 棋譜学習・プロファイル | 📋 **仕様確定** |
| 14 | Leelaモード推定損失 | Leela候補手の損失表示 | 📋 **仕様確定** |

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
- [x] `reports/karte_YYYYMMDD-HHMM.md`（単局版、Phase 5で実装済み）
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

### Phase 11: 難解PVフィルタ（Human Move Filter）
- **目的**: Top Moves候補手のうち、難解なPVを含む手を除外して見やすくする
- **設定**: OFF / WEAK / MEDIUM / STRONG / AUTO
- **仕様書**: `docs/specs/human-move-filter.md`

### Phase 12: MuZero 3分解難易度
- **目的**: 局面の「難しさ」をPolicy/Transition/Stateに分解し、難所抽出・解説出し分けに使用
- **用途**: 難所抽出（上位K局面）、Viewer Presetによる解説の出し分け
- **仕様書**: `docs/specs/muzero-difficulty.md`

### Phase 13: Smart Kifu Learning
- **目的**: 棋譜学習・プレイヤープロファイル・Viewer Level管理
- **主要機能**: Training Set、Context分離（human/vs_katago/generated）、学習条件提案
- **仕様書**: `docs/specs/smart-kifu-learning.md`

### Phase 14: Leelaモード推定損失
- **目的**: Leela解析に「推定損失」（KataGo風の損失目数）を表示
- **特徴**: KataGoモードとは完全分離、投了目安機能付き
- **仕様書**: `docs/specs/leela-estimated-loss.md`

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
- [ ] **複数局サマリー**: Batch Analyze → `reports/summary/` にファイル生成

---

## 10. "Done"の共通定義

- [ ] `00-purpose-and-scope.md` に矛盾しない
- [ ] 仕様の正本に反映されている
- [ ] 最小テスト手順があり、再現できる

---

## 11. 変更履歴

- 2026-01-10: Phase 3 SGFエラー統合（PR #98）
  - **目的**: SGF読み込みエラー処理をErrorHandler経由に統一
  - **errors.py**: InputValidationError追加
  - **__main__.py**:
    - `_handle_sgf_error` ヘルパー追加
    - `load_sgf_file()` 改修
    - `load_sgf_from_clipboard()` 改修（URL取得エラー対応含む）
  - **セキュリティ**: クリップボード内容をログ/contextに含めない
  - **成果**: 全510テストパス
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
