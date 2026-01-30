# myKatrain（PC版）ロードマップ

> 最終更新: 2026-01-31（Phase 92完了）
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

## 2. フェーズ一覧

### 完了済み（Phase 1〜43）

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 1 | 解析基盤の整備 | eval_metrics.py | ✅ |
| 2 | 解析ビュー第1段階 | 重要局面ハイライト、ナビゲーション | ✅ |
| 3 | ミス分類＋局面難易度 | 良/軽/悪/大悪、手の自由度 | ✅ |
| 4 | クイズモード基盤 | クイズ候補抽出（Phase 4-1） | ✅ |
| 4.5 | 評価指標安定化 | 5段階プリセット、Variable Visits | ✅ |
| 5 | 1局カルテ出力 | `reports/karte/karte_*.md` | ✅ |
| 6 | 複数局まとめカルテ | `summary.md`（傾向抽出） | ✅ |
| 6.5 | eval_metrics.py 品質向上 | production-ready 基盤 | ✅ |
| 7 | カルテ品質向上 | Phase×Mistake クロス集計 | ✅ |
| 9 | 検証テンプレ | `03-llm-validation.md` | ✅ |
| 11 | 難解PVフィルタ | Top Moves表示改善 | ✅ |
| 12 | MuZero 3分解難易度 | 難所抽出・UI表示 | ✅ |
| 13 | Smart Kifu Learning | 棋譜学習・プロファイル | ✅ |
| 14 | Leelaモード推定損失 | Leela候補手の損失表示 | ✅ |
| 15 | Leela UI統合 | 設定UI + エンジン管理 | ✅ |
| 16 | Leela機能拡張 | PV再生 + 投了目安 | ✅ |
| 17 | Leela Stats on Top Moves | 候補手表示の選択機能 | ✅ |
| 18 | 安定性向上 | キャッシュLRU + バグ修正 | ✅ |
| 19 | 大規模リファクタリング | reports/、analysis/分割 | ✅ |
| 20 | Guardrails | Kivy依存削減、アーキテクチャテスト | ✅ |
| 21 | Settings Popup タブ化 | 3タブ再編成 | ✅ |
| 22 | 安定性向上 | クラッシュ・フリーズ防止 | ✅ |
| 23 | カルテ品質向上 | ONLY_MOVE緩和、JSON出力 | ✅ |
| 24 | Regression Tests | SGF E2E ゴールデンテスト | ✅ |
| 25 | LLM Package Export | zip + manifest + 匿名化 | ✅ |
| 26 | レポート導線改善 | 最新レポートを開く | ✅ |
| 27 | Settings UI拡張 | 検索、Export/Import、リセット | ✅ |
| 28 | Smart Kifu運用強化 | バッチ連携、解析率表示 | ✅ |
| 29 | Diagnostics | 診断画面、Bug Report zip | ✅ |
| 30 | 解析強度抽象化 | AnalysisStrength enum | ✅ |
| 31 | Leela→MoveEval変換 | conversion.py | ✅ |
| 32 | レポートLeela対応 | 推定損失ラベル表示 | ✅ |
| 33 | エンジン選択設定 | engine.analysis_engine | ✅ |
| 34 | UIエンジン切替 | Settings Popup拡張 | ✅ |
| 35 | Leelaカルテ統合 | Export Karte Leela対応 | ✅ |
| 36 | Leelaバッチ解析 | batch拡張（オプション） | ✅ |
| 37 | テスト強化 | E2E, --update-goldens | ✅ |
| 38 | 安定化 | エラーハンドリング強化 | ✅ |
| 39 | エンジン比較ビュー | KataGo/Leela比較表示 | ✅ |
| 40 | PLAYモード | Leela Zero対戦機能 | ✅ |
| 41 | コード品質 | Enum化、コマンド抽出、定数化 | ✅ |
| 42 | Batch Core移行 | core/batch/（Kivy非依存） | ✅ |
| 43 | Stability Audit | Atomic save、Shutdown改善 | ✅ |
| 44 | Batch Analysis Fixes | 信頼性閾値一貫性、完了チャイム | ✅ |

### Phase 45–52: Lexicon・MeaningTags・Radar・Critical 3 ✅ **完了**

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 45 | Lexicon Core | `common/lexicon/`（YAML読み込み） | ✅ |
| 46 | MeaningTags Core | `analysis/meaning_tags/`（分類ヒューリスティクス） | ✅ |
| 47 | MeaningTags統合 | Summary/Karte出力対応 | ✅ |
| 48 | Radar Data Model | `RadarMetrics`, `SkillTier`（5軸評価） | ✅ |
| 49 | Radar Summary統合 | Summary出力、Tier表示 | ✅ |
| 50 | Critical 3 | 重要3手抽出、LLMプロンプトテンプレート | ✅ |
| 51 | Radar UI Widget | Kivy radar chart widget | ✅ |
| 52 | Stabilization | 回帰テスト、ドキュメント | ✅ |

**詳細**: [Phase 45–52 詳細](#phase-4552-詳細lexiconmeaningtagsradarcritical-3)

### Phase 53–54: Batch Report Quality ✅ **完了**（2026-01-25）

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 53 | Batch Report基盤 | helpers.py（truncate, format_wr_gap, markdown link） | ✅ |
| 54 | Report Quality Improvements | ローカライズ、タグベースヒント、escape_markdown | ✅ |

**詳細**: [Phase 53–54 詳細](#phase-5354-詳細batch-report-quality)

### Phase 55–66: Post-54 拡張（Style / Pacing / Risk / Curator）✅ **完了**（2026-01-26）

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 55 | レポート基盤 + ユーザー集計 | `reports/section_registry.py`, `UserRadarAggregate` | ✅ |
| 56 | Style Archetype Core | `analysis/style/`（6アーキタイプ判定） | ✅ |
| 57 | Style統合 | Summary/Karteにスタイルセクション追加 | ✅ |
| 58 | 時間データパーサー | `analysis/time/parser.py`（SGF BL/WL読取） | ✅ |
| 59 | Pacing & Tilt Core | `analysis/time/pacing.py`（相対メトリクス） | ✅ |
| 60 | Pacing/Tilt統合 | Summary/Karteに時間分析セクション追加 | ✅ |
| 61 | Risk Context Core | `analysis/risk/`（形勢判断＋フォールバック） | ✅ |
| 62 | Risk統合 | Karteに「勝負術」セクション追加 | ✅ |
| 63 | Curator Scoring | `curator/scoring.py`（適合度スコア） | ✅ |
| 64 | Curator出力 | `curator_ranking.json`, `replay_guide.json` | ✅ |
| 65 | Post-54 Integration | 統合テスト、回帰テスト | ✅ |
| 66 | Post-54 品質強化 | Summary/Karte品質改善、不変条件テスト | ✅ |

**詳細**: [Phase 55–66 詳細](#phase-5566-詳細post-54-拡張)

### Phase 67: Engine Stability Improvements ✅ **完了**（2026-01-26）

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 67 | エンジン安定性向上 | shutdown改善、fakes.py、leak check | ✅ |

**詳細**: [Phase 67 詳細](#phase-67-engine-stability-improvements-完了)

### Phase 68: Command Pattern for KataGoEngine ✅ **完了**（2026-01-26）

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 68-A | Command Core | `engine_cmd/commands.py`, `executor.py`, `engine_query.py` | ✅ |
| 68-B | Engine統合 | `request_analysis` で `build_analysis_query()` 使用 | ✅ |
| 68-C | Pondering便利メソッド | `is_pondering`, `get_ponder_command()`, `stop_pondering()` | ✅ |

**詳細**: [Phase 68 詳細](#phase-68-command-pattern-for-katagoengine完了)

### Phase 69–79: Large Refactor & Maintainability ✅ **完了**（2026-01-28）

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 69 | テスト強化 | sgf_parser + base_katrain テスト | ✅ |
| 70 | 複雑関数リファクタ | analyze_extra分割 + 重複解消 | ✅ |
| 71 | batch/stats.py 分割 | `batch/stats/` パッケージ化 | ✅ |
| 72 | karte_report.py 分割 | `reports/karte/` パッケージ化 | ✅ |
| 73 | KaTrainGui分割 A | KeyboardManager | ✅ |
| 74 | KaTrainGui分割 B | ConfigManager | ✅ |
| 75 | KaTrainGui分割 C | PopupManager | ✅ |
| 76 | KaTrainGui分割 D | GameStateManager | ✅ |
| 77 | エラーハンドリング A | 監査・分類 | ✅ |
| 78 | エラーハンドリング B | ユーザー操作パス | ✅ |
| 79 | エラーハンドリング C | バックグラウンドパス | ✅ |

**詳細**: [Phase 69–79 詳細](#phase-6979-large-refactor--maintainability完了)

### Phase 80–87: Analysis Intelligence（Karte/Summaryの意味付け強化）📋 **Planned**

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 80 | 共通基盤（Area判定・抽出ヘルパ） | `get_area_name()` / Area分類、ownership・scoreStdev取得ヘルパ、最小テスト | ✅ Done |
| 81 | Ownership差分クラスタ抽出（MVP） | ownership diff + clustering（BFS）、27ユニットテスト | ✅ Done |
| 82 | Consequence判定 + Karteへ限定統合 | 3分類（Group Death/Territory Loss/Missed Kill）、Critical 3のContextが(none)時のみ注入 | ✅ Done |
| 83 | Complexityフィルタ（最小ルール） | `scoreStdev>20` Chaos判定、除外/減点、件数カウント、回帰テスト | ✅ Done |
| 84 | Recurring Pattern集計コア（MVP） | `pattern_miner`（signature集計・ランキング）、テストSGFセット | ✅ Done |
| 85 | PatternのSummary統合（レンダリング） | summary出力テンプレ（Markdown）、ゴールデン更新/スナップショット | ✅ Done |
| 86 | Reason Generator（限定実装） | 単発タグ＋上位N組み合わせのみ自然文、残りはタグ併記フォールバック、i18n最小 | 📋 Planned |
| 87 | バッファ（調整・拡張・磨き込み） | 閾値調整、追加指標、説明文改善、ドキュメント整理（拡張は原則ここへ集約） | 📋 Planned |

**Phase 80**: 後続の前提を固定するための共通基盤。Area判定（隅/辺/中央など）と、ownership・scoreStdev等の取得ヘルパを整備する。
このフェーズではKarte/Summaryの出力仕様は変えない（土台固めのみ）。

**Phase 81**: ownership差分から「変動の塊（クラスタ）」を抽出するMVP。再現性と安定性を優先し、分類やレポート統合は次へ送る。
外部依存は増やさず、BFS/Union-Find等の軽量実装を想定。

**Phase 82**: クラスタを3分類（Group Death / Territory Loss / Missed Kill）へ落とし込む。
Karteへの統合は「Critical 3のContextが(none)のときのみ」注入する限定運用で安全に入れる。

**Phase 83**: ✅ Complexity（Chaos）フィルタの最小導入。`scoreStdev > 20` で70%割引（除外ではなく減点）。
`ComplexityFilterStats`でログ出力、`complexity_discounted`フラグでKarte表示。（2026-01-30完了）

**Phase 84**: ✅ Recurring Patternの集計コア（MVP）。`pattern_miner.py`でMistakeSignature/GameRef/PatternClusterを実装。
`mine_patterns()`で複数ゲームから頻出パターンを抽出。盤サイズ対応、GTP Iスキップ対応、56テスト。（2026-01-30完了）

**Phase 85**: ✅ PatternをSummaryへ統合し、Recurring Patternsセクションを追加。
`extraction.py`に`pattern_data`/`source_index`追加、`summary_formatter.py`にパターンマイニング統合（+435行）。
TYPE_CHECKINGガード、GTP座標検証、決定論的ソート、22契約テスト追加。（2026-01-30完了）

**Phase 86**: ✅ Reason Generator（自然文）の限定実装。`reason_generator.py`で12単発タグ＋8組み合わせテンプレート（JP/EN）を提供。
Critical 3とRecurring PatternsにReason行を追加。ワイルドカードマッチング、lang=None→日本語デフォルト、20テスト追加。（2026-01-30完了）

**Phase 87**: ✅ MistakeSignatureにplayer軸追加（黒/白分離分析）、Reason Generatorテンプレート7個追加（8→15個）。
`normalize_player()`でB/W/?正規化、Summary出力に`[Black]/[White]`表示、i18nキー追加、ワイルドカード優先順位テスト追加。（2026-01-30完了）

**Phase 87.5**: ✅ Batch Analysis UIとSettings UIの一貫性・安全性改善。`is_leela_configured()`ヘルパー追加、
`analysis_engine`/`leela_engine`を`run_batch()`に渡す[CRITICAL]、3ステップLeela起動ロジック、Variable visits連動、
Leelaゲーティング（両UI）、"Setup Leela"ショートカットボタン、`extract_game_stats()`/`build_karte_report()`にsnapshot対応。（2026-01-30完了）

**Phase 87.6**: ✅ Leela Zeroバッチ解析の出力生成バグを修正。0手SGFを失敗扱いに変更（`fail_result()`）、
Success gateを強化（gameとsnapshot両方をチェック）、`karte_failed`を解析失敗時にインクリメント、
`_DummyEngine`クラス追加（`engine=None`クラッシュ防止）、解析品質ログ追加。（2026-01-30完了）

**Phase 88**: ✅ KataGo設定UI再構成とhuman-like排他制御。`model_labels.py`（クロスプラットフォームbasename対応）、
`humanlike_config.py`（Option A: パス空時強制OFF）、Switchトグル+ステータス表示、
モデル強度ラベル（軽量/標準/強力/その他）、`humanlike_model_last`永続化、i18n（EN/JP）追加。（2026-01-30完了）

### Phase 88–94: Beginner Experience & Study Modes 📋 **Planned**

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 88 | KataGo設定UI再構成 + human-like排他 | モード選択/サマリ/詳細折りたたみ、human-likeトグル排他 | ✅ Done |
| 89 | 自動(まず動かす)モード | 実行テスト、OpenCL→CPUフォールバック、軽量モデル運用の導線 | ✅ Done |
| 90 | エラー救済/診断 | LLM用コピー、diagnostics自動ダンプ、サニタイズ、復旧導線 | ✅ Done |
| 91 | Beginner Hint MVP | 1手1ヒント枠、コア4判定、Review/Analysis中心、ON/OFF | ✅ Done |
| 92 | Beginner Hint 拡張 | 翻訳テンプレ、信頼度フィルタ、盤上ハイライト、i18n整備 | ✅ Done |
| 93 | Active Review MVP | Fog of War、回答入力、即時採点（最小）、基本UI統合 | 📋 Planned |
| 94 | Active Review 拡張 | Retry/Hint、セッションサマリ、ゲーム化、（任意）80系連携 | 📋 Planned |

**Phase 88**: PC初心者の事故を根治するため、設定UIの再構成と「安全なデフォルト導線」を整備する。
human-likeは通常モデルと混在しない設計に寄せ、迷いポイントを減らす。

**Phase 89**: "まず動かす"自動モードを用意し、初回導入の失敗率を下げる。
実行テスト＋OpenCL→CPUフォールバックなど、起動/解析が通ることを最優先にする。

**Phase 90**: ✅ エラー救済機能の実装。`error_recovery.py`（スレッドセーフ重複排除、4096バイトUTF-8制限）、
`recovery_actions.py`（4つの復旧アクション）、EngineRecoveryPopupに復旧ボタン追加、
`collect_diagnostics_bundle()`/`format_llm_diagnostics_text()`パブリックAPI、`extra_files`でllm_prompt.txt注入。（2026-01-30完了）

**Phase 91**: ✅ 初心者向けヒント（Safety Net）MVP。`katrain/core/beginner/`パッケージ新規作成、
4カテゴリ検出（SELF_ATARI, IGNORE_ATARI, MISSED_CAPTURE, CUT_RISK）、モードゲーティング（PLAYモード無効）、
ノードキャッシュ、設定トグル、i18n対応。（2026-01-30完了）

**Phase 92**: ✅ 初心者ヒント拡張。テンプレ10個ID化（MeaningTagマッピング6カテゴリ追加）、信頼度フィルタ（MIN_VISITS=200）、
盤上ハイライト（オレンジ半透明円）、i18n完全化（30キー）、キャッシュ設定対応、CI修正（Kivy headless対応）。（2026-01-31完了）

**Phase 93**: Active Review Mode（次の一手予測）MVP。Fog of WarでAIヒントを隠し、ユーザー回答→即時採点の最小ループを作る。
UI統合と基本評価指標の提示までに絞る。

**Phase 94**: Active Review拡張。Retry/Hint/セッションサマリ等の学習導線を追加する。
必要に応じてPhase 80系（弱点パターン等）との接続も検討する。

### 未定（TBD / Post-52）

※「初心者向けヒント」「Active Review」「KataGoセットアップ救済」は Phase 88–94 に移動。

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| - | Ownership Volatility (Idea #3) | 盤面リスクオーバーレイ | 📋 Future |
| - | Style Matching Quiz (Idea #5) | スタイル判定クイズ | 📋 Future |
| - | Lexicon UI Browser | 用語ポップアップ | 📋 Future |

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

### Phase 27: Settings UIスケーラブル化 ✅ **完了**

#### 27.1 目的
設定検索・Export/Import・タブ別リセット機能を追加。

#### 27.2 スコープ
**In:**
- 設定検索（キーワードで項目をフィルタ/ハイライト）✅
- 設定 Export / Import（JSON 形式）✅
- タブ別リセット機能 ✅

**Out:**
- Advanced / Experimental タブ隔離（現状のタブ構成を維持）
- クラウド同期

#### 27.3 成果物
- `katrain/common/settings_export.py` - Export/Import/Reset ロジック（Kivy非依存）
- `tests/test_settings_export.py` - 22テスト
- `katrain/gui/features/settings_popup.py` - 検索バー、Export/Import/Resetボタン統合

#### 27.4 実装（4 PR）
- **PR #145**: Core層 settings_export.py + 22テスト
- **PR #146**: タブ別リセット機能 + i18n（3キー）
- **PR #147**: Export/Import UI + tkinter ファイルダイアログ + i18n（5キー）
- **PR #148**: 設定検索（opacity-based filtering）+ i18n（2キー）

#### 27.5 技術詳細
- **Atomic Save**: temp file + `os.replace()` パターンでImport時のファイル破損を防止
- **Store同期**: reload-then-sync パターン（`_load()` → `dict()` 変換）
- **検索フィルタ**: opacity 0.3/1.0 による視覚的フィルタリング
- **ファイルダイアログ**: tkinter の `filedialog` を使用（クロスプラットフォーム対応）

---

### Phase 28: Smart Kifu運用強化 ✅ **完了**

#### 28.1 目的
Smart Kifu とバッチ解析の連携強化、解析率の可視化。

#### 28.2 スコープ
**In:**
- ✅ バッチ解析からの Training Set 自動登録導線
- ✅ 解析率表示（解析済み/未解析の割合）
- ✅ Training Set の解析ステータスサマリー

**Out:**
- 自動解析スケジューリング
- クラウドストレージ連携

#### 28.3 成果物
- ✅ `ImportErrorCode` enum（文字列マッチング脆弱性を解消）
- ✅ `TrainingSetSummary` dataclass（オンデマンドサマリー計算）
- ✅ `import_analyzed_sgf_folder()` - バッチ出力フォルダのインポート
- ✅ `show_import_batch_output_dialog()` - バッチインポートダイアログ UI
- ✅ Training Set Manager への解析率表示（色分け付き）

#### 28.4 実装詳細（2026-01-17）

**PR #149: Core層 - 解析率計算**
- `ImportErrorCode` enum 追加（DUPLICATE, PARSE_FAILED, FILE_NOT_FOUND, COPY_FAILED, UNKNOWN）
- `TrainingSetSummary` dataclass 追加
- `has_analysis_data()` - 軽量な解析データ存在チェック
- `compute_analyzed_ratio_from_sgf_file()` - SGF解析率計算
- `compute_training_set_summary()` - Training Set サマリー計算
- `import_sgf_to_training_set()` に `compute_ratio` オプション追加
- `import_analyzed_sgf_folder()` - バッチ出力フォルダのインポート

**PR #152: UI - Training Set Manager解析率表示**
- `_format_analyzed_ratio()` - 解析率の色分け表示
- None vs 0.0 の正しい区別（`if ratio is None` を使用）
- 色分け: 緑(≥70%), 黄(40-69%), 赤(<40%), グレー(None)

**PR #151: UI - バッチインポートブリッジ**
- `show_import_batch_output_dialog()` - バッチインポートダイアログ
- フォルダ選択、Context選択（Human/vs_katago/AI生成）
- バックグラウンドスレッドでインポート実行
- 結果サマリー表示（success/skipped/failed + 平均解析率）

**テスト: 36件**
- `tests/test_smart_kifu_analyzed_ratio.py` - 25件
- `tests/test_smart_kifu_import.py` - 11件
- `tests/data/analyzed/` - 6つのテストフィクスチャSGF

#### 28.5 受け入れ条件
- [x] `has_analysis_data()` が `bool(getattr(..., None))` を使用
- [x] `compute_analyzed_ratio_from_sgf_file()` が None vs 0.0 を正しく区別
- [x] `ImportErrorCode` enum を追加
- [x] `import_sgf_to_training_set()` が `ImportErrorCode` を返す
- [x] `import_analyzed_sgf_folder()` がエラーコードで分類
- [x] 平均計算が None を除外
- [x] UI が `if ratio is None` を使用（`if not ratio` ではない）
- [x] None → "--"、0.0 → "0%" が正しく区別される

---

### Phase 29: Diagnostics + Bug Report Bundle ✅ **完了**

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
| ファイル | 行数 | 説明 |
|----------|------|------|
| `katrain/common/sanitize.py` | ~120 | パス/テキストサニタイズ（Kivy非依存） |
| `katrain/core/log_buffer.py` | ~80 | スレッドセーフな循環ログバッファ |
| `katrain/core/diagnostics.py` | ~280 | 情報収集、ZIP生成 |
| `katrain/gui/features/diagnostics_popup.py` | ~370 | 診断ポップアップUI |
| `tests/test_sanitize.py` | ~300 | サニタイズテスト（30件） |
| `tests/test_log_buffer.py` | ~150 | LogBufferテスト（13件） |
| `tests/test_diagnostics.py` | ~320 | 診断テスト（28件） |

#### 29.4 変更ファイル
| ファイル | 変更内容 |
|----------|----------|
| `katrain/core/base_katrain.py` | LogBuffer統合、`get_recent_logs()` |
| `katrain/__main__.py` | Diagnosticsメニュー項目追加 |
| `katrain/gui.kv` | メニューボタン追加 |
| `katrain/i18n/locales/*/katrain.po` | 翻訳キー追加 |
| `.gitignore` | `log_buffer.py` 例外追加 |

#### 29.5 アーキテクチャ
```
Common層: sanitize.py（純粋関数、Kivy非依存）
    ↑
Core層:  log_buffer.py（循環バッファ）
         diagnostics.py（情報収集、ZIP生成）
    ↑
GUI層:   diagnostics_popup.py（UI、スレッド管理）
```

#### 29.6 ZIP構造
```
diagnostics_YYYYMMDD-HHMMSS_XXXX.zip
├── manifest.json        # メタデータ（schema_version, privacy flags）
├── system_info.json     # OS、Python、メモリ（サニタイズ済み）
├── katago_info.json     # パス、状態（サニタイズ済み）
├── app_info.json        # バージョン、設定パス（サニタイズ済み）
├── settings.json        # 設定スナップショット（engineセクション除外）
└── logs.txt             # サニタイズ済みログ（最新500行）
```

#### 29.7 受入基準
- [x] MyKatrain メニュー → Diagnostics で画面表示
- [x] システム情報、KataGo情報、アプリ情報が正しく表示
- [x] 「Generate Bug Report」でZIP生成（UIフリーズなし）
- [x] ZIP内に個人情報がないこと（パス→`<USER_HOME>`等）
- [x] 「Open Folder」ボタンでフォルダを開ける
- [x] テスト71件全パス（sanitize:30, log_buffer:13, diagnostics:28）

---

### Phase 30-39: Leela Zero解析パイプライン拡張（Phase 30-36 完了）

Phase 30-39はLeela Zero解析をKataGoと同等のカルテ/サマリー生成パイプラインに統合するためのロードマップです。
詳細な計画は計画ファイルを参照してください。

#### 設計原則
1. **単一エンジンレポート**: KataGo/Leela混合禁止（初回実装）
2. **既存パイプライン再利用**: EvalSnapshot/MoveEvalを活用
3. **テストはCI対応**: 実エンジン不使用（mock/stub + golden）
4. **ハードコード禁止**: `leela.fast_visits`で設定可能
5. **損失セマンティクス明確化**: `score_loss`（目単位）vs `leela_loss_est`（推定損失）

#### フェーズ概要
| Phase | 名称 | 主な成果物 | 状態 |
|------:|------|-----------|------|
| 30 | 解析強度抽象化 | AnalysisStrength enum, leela.fast_visits | ✅ **完了** |
| 31 | Leela→MoveEval変換 | conversion.py, leela_loss_est | ✅ **完了** |
| 32 | レポートLeela対応 | EngineType, format_loss_label | ✅ **完了** |
| 33 | エンジン選択設定 | engine.analysis_engine キー | ✅ **完了** |
| 34 | UIエンジン切替 | Settings Popup, フォールバック診断 | ✅ **完了** |
| 35 | Leelaカルテ統合 | Export Karte Leela対応 | ✅ **完了** |
| 36 | Leelaバッチ解析 | 既存batch拡張（オプション） | ✅ **完了** |
| 37 | テスト強化 | Python-level E2E, golden | ✅ **完了** |
| 38 | 安定化 | エラーハンドリング強化 + テスト追加 | ✅ **完了** |
| 39 | エンジン比較ビュー | KataGo/Leela比較表示 | ✅ **完了** |
| 40 | PLAYモード | Leela Zero対戦機能 | ✅ **完了** |
| 41 | コード品質 | Enum化、コマンド抽出、例外改善、定数化 | ✅ **完了** |
| 42 | Batch Core移行 | core/batch/パッケージ（Kivy非依存） | ✅ **完了** |

#### Phase 42 詳細（Batch Core移行）
**目的**: batch-processing logicをcore層に移動し、Kivy非依存化

| PR | 内容 | 状態 |
|:--:|------|:----:|
| 42-A | models.py, helpers.py（dataclass + 純粋関数） | ✅ |
| 42-B | analysis.py, orchestration.py, stats.py | ✅ |
| 42-C | test_batch_core_imports.py（後方互換テスト） | ✅ |

**成果物**:
```
katrain/core/batch/
├── __init__.py        ← Eager: models/helpers; Lazy: run_batch/analyze_*
├── models.py          ← WriteError, BatchResult（~50行）
├── helpers.py         ← 純粋関数15種（~600行）
├── analysis.py        ← analyze_single_file, analyze_single_file_leela（~400行）
├── orchestration.py   ← run_batch() メインエントリ（~440行）
└── stats.py           ← 統計抽出、サマリー生成（~960行）
```

**効果**: `tools/batch_analyze_sgf.py` 1900行 → 240行（87%削減）

#### 依存関係
```
Phase 30 → 31 → 32 → 33 → 34 → 35 ──→ 37 → 38 → 39 → 40 → 41 → 42
                                   │
                                   └→ 36 [OPTIONAL]
```
- Phase 42完了。Leela Zero解析パイプライン拡張ロードマップ完了

---

## Phase 45–52 詳細（Lexicon・MeaningTags・Radar・Critical 3）

### 固定決定事項（Decisions Fixed）

| 決定事項 | 解決 |
|----------|------|
| **Lexiconデータソース** | `go_lexicon_master_last.yaml` が正本。別JSONデータセットは作成しない |
| **Lexicon言語** | EN/JP のみ（既存YAMLフィールド）。他言語はPost-52 |
| **Radar軸** | `opening`, `fighting`, `endgame`, `stability`, `awareness` (Idea #2仕様) |
| **Radarスコア** | 内部: 0.0–1.0、表示: 1.0–5.0（線形変換: `display = 1 + internal * 4`） |
| **Tier名** | Tier 1 (入門), Tier 2 (初級), Tier 3 (中級), Tier 4 (上級), Tier 5 (高段) |
| **Radar調整** | ガベージタイム除外（30点以上ビハインドの最後20手）、一択除外（ONLY_MOVE） |
| **MeaningTag↔Lexicon** | `lexicon_anchor_id: Optional[str]` でYAMLエントリを参照。アンカーなしも許容 |
| **Critical 3コンテキスト** | 構造化フィールドのみ。盤面シリアライズなし |

### Phase 45: Lexicon Core Infrastructure

**Goal**: Kivy非依存の`LexiconStore`を実装し、既存`go_lexicon_master_last.yaml`を読み込み・検証・検索可能にする

**Deliverables**:
- `katrain/common/lexicon/` パッケージ
- `LexiconEntry` dataclass（YAML構造をミラー）
- `LexiconStore` クラス: `load()`, `get()`, `get_by_title()`, `get_by_category()`, `get_by_level()`
- バリデーション: 必須フィールド、related_ids解決、重複ID検出
- ユニットテスト

**Non-goals**: GUI統合、動的編集UI、EN/JP以外、Karte/Summary出力連携

**Acceptance Criteria**:
- `LexiconStore.get("atari")` がja/en両フィールド付きエントリを返す
- `get_by_title("アタリ", "ja")` と `get_by_title("atari", "en")` が同じエントリを返す
- `get_by_level(1)` が初心者レベルサブセットを返す（フィルタビュー）
- 不正YAMLで明確なエラーメッセージ
- `common/lexicon/` にKivyインポートなし

**PR size**: 1–2 PRs

### Phase 46: Meaning Tags System Core（2026-01-23 完了）

**Goal**: MoveEvalに「意味タグ」を付与するヒューリスティック分類を実装、Lexiconアンカー参照オプション付き

**Deliverables**:
- `MeaningTag` dataclass: `id`, `lexicon_anchor_id: Optional[str]`
- `MEANING_TAG_REGISTRY`: 12–15タグ
- `MeaningTagClassifier`: 決定論的ルール
- 初期タグ: `missed_tesuji`, `overplay`, `slow_move`, `direction_error`, `shape_mistake`, `reading_failure`, `endgame_slip`, `connection_miss`, `capture_race_loss`, `life_death_error`, `territorial_loss`, `uncertain`

**Non-goals**: GUI表示、機械学習、Karte/Summary出力変更

**Acceptance Criteria**:
- `classify_meaning_tag(move_eval)` が決定論的結果を返す
- 10タグ以上に分類ルール実装
- `lexicon_anchor_id` 付きタグは有効な`LexiconEntry`に解決
- アンカーなしタグは `lexicon_anchor_id=None` で明示
- エッジケーステスト（解析なし、低visits、パス手）

**PR size**: 2–3 PRs

### Phase 47: Meaning Tags Integration（2026-01-23 完了）

**Goal**: MeaningTagをSummary集計とKarte出力に統合、RAG的定義表示

**Deliverables**:
- `MoveEval.meaning_tag: Optional[MeaningTag]`
- `SummaryStats.meaning_tag_counts: Dict[str, int]`
- Summary出力: 「頻出ミスタイプ」セクション
- Karte: 重要手に`meaning_tag` + oneliner定義
- i18nキー（EN/JP）
- `format_meaning_tag_with_definition()` ヘルパー

**Non-goals**: Radar表示、Tier絞り込み、Lexicon UIブラウザ、expanded説明文

**Acceptance Criteria**:
- Summary出力に上位3タグ＋カウント
- Karte重要手: `meaning_tag: overplay (無理手: 相手の強い場所への深入り)`
- ゴールデンファイルテスト更新
- 全タグ表示名にJP翻訳

**PR size**: 2–3 PRs

### Phase 48: 5-Axis Radar Data Model（2026-01-23 完了）

**Goal**: Idea #2仕様に基づく5軸スキル評価モデルとTier分類を実装

**Deliverables**:
- `RadarAxis` enum: `OPENING`, `FIGHTING`, `ENDGAME`, `STABILITY`, `AWARENESS`（str継承）
- `RadarMetrics` frozen dataclass: 表示スコア1.0–5.0、`MappingProxyType`でimmutability保証
- `SkillTier` enum: `TIER_1`–`TIER_5` + `TIER_UNKNOWN`（str継承、int mapping付き）
- `compute_radar_from_moves()`: MoveEvalリストから5軸計算、playerフィルタ対応
- Tier変換関数: APL/BlunderRate/MatchRate → Tier（半開区間閾値）
- `is_garbage_time()`: BLACK視点winrate >= 0.99 or <= 0.01
- `compute_overall_tier()`: 5軸median、math.ceil for even counts

**実装詳細**:
- 新規: `katrain/core/analysis/skill_radar.py`（~570行）
- 更新: `katrain/core/analysis/__init__.py`（再エクスポート追加）
- テスト: 95件追加（test_skill_radar.py）
- 制約: 19x19のみ（OPENING_END_MOVE=50, ENDGAME_START_MOVE=150）

**Non-goals**: GUI表示、複数局集約、ユーザー設定可能な重み、履歴追跡

**PR size**: 1 PR（#183）

### Phase 49: Radar Aggregation & Summary Integration（2026-01-23 完了）

**Goal**: 複数局のRadar集約とSummary出力統合

**Deliverables**:
- `AggregatedRadarResult` frozen dataclass: 複数局集約結果、`Optional[float]`スコア
- `aggregate_radar()`: 均等重み、per-axis UNKNOWNフィルタリング
- `radar_from_dict()`: roundtripシリアライゼーションヘルパー
- `round_score()`: Decimal ROUND_HALF_UPで決定論的丸め
- Summary「Skill Profile」セクション: 5軸スコア + Tier + 有効手数
- 弱軸（<2.5）を練習優先に（最大2件）
- エクスポート: Markdownテーブル + JSON（`to_dict()`経由）
- i18n: EN/JP radar tier/axis翻訳キー追加

**実装詳細**:
- 更新: `katrain/core/analysis/skill_radar.py`（+357行）
- 更新: `katrain/core/analysis/__init__.py`（再エクスポート追加）
- 更新: `katrain/core/batch/stats.py`（+196行）
- 更新: `katrain/i18n/locales/en/LC_MESSAGES/katrain.po`（+13キー）
- 更新: `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po`（+13キー）
- テスト: 60件追加（38 aggregation + 22 integration）
- 定数: `MIN_VALID_AXES_FOR_OVERALL=3`, `MIN_MOVES_FOR_RADAR=10`
- 制約: 19x19のみ（Phase 48から継承）、recency weightingは将来フェーズへ延期

**Non-goals**: Kivy radar chart、履歴追跡、対戦相手radar、フェーズ別radar、recency weighting

**PR size**: 1 PR（単一コミット）

### Phase 50: Critical 3 Focused Review Mode（2026-01-23 完了）

**Goal**: 重要度上位3手を抽出し、構造化コンテキスト付きでKarte出力・LLMプロンプト生成

**Deliverables**:
- `select_critical_moves()`: `List[CriticalMove]`
- `CriticalMove` dataclass: 構造化フィールド（move_number, gtp_coord, score_loss, winrate_delta, meaning_tag, position_difficulty, reason_tags, score_stdev, game_phase）
- スコアリング: `importance × meaning_tag_weight × diversity_bonus`
- Karte「Critical 3」セクション
- `CRITICAL_3_PROMPT_TEMPLATE`

**Non-goals**: インタラクティブUI、盤面シリアライズ、変化図、バッチ出力対応

**Acceptance Criteria**:
- 選択が決定論的（同じゲーム→同じ3手）
- diversity_bonusで同一タグ重複回避
- 全`CriticalMove`フィールドが値設定（盤面図なし）
- Karteに「Important Moves」+「Critical 3」両方
- LLMプロンプトテンプレートがself-contained markdown

**PR size**: 2 PRs

### Phase 51: Radar UI Widget（2026-01-23 完了）

**Goal**: 5軸スキルプロファイルのKivy radarチャートウィジェット実装

**Deliverables**:
- `katrain/gui/widgets/radar_geometry.py`（~150行）: 純粋幾何関数（Kivy非依存）
- `katrain/gui/widgets/radar_chart.py`（~160行）: RadarChartWidgetクラス
- `katrain/gui/features/skill_radar_popup.py`（~200行）: ポップアップUI
- 5軸ペンタゴン描画（Opening→Fighting→Endgame→Stability→Awareness、時計回り）
- グリッドリング（固定比率: 20%, 40%, 60%, 80%, 100%）
- Black/Whiteタブ切替、弱軸ハイライト
- 軸ラベルi18n（EN/JP）、Tier色分け（緑/黄/赤/灰）
- MyKatrainメニュー統合（`skill-radar-popup`）

**Non-goals**: アニメーション、軸ドリルダウン、複数radar重ね、画像エクスポート

**Acceptance Criteria**: ✅ 全て達成
- 全5 Tierで正しく描画
- 1280×720以上で軸ラベル可読
- 弱軸が視覚的に識別可能（赤ドット＋弱点セクション）
- radar dataがNoneでもプレースホルダ表示（灰色ドット＋N/A）
- Tier表示（数字＋日本語ラベル）

**Tests**: 45件追加（31 geometry + 14 popup）、総数2161件

**PR size**: 1 PR（#185）

### Phase 52: Stabilization & Documentation（2026-01-24 完了）

**Goal**: Phase 45–51の包括的テスト、回帰防止、ドキュメント整備

#### Phase 52-A: Tofu Fix + Language Code Consistency（2026-01-23 完了）

**問題**:
- Quiz popup、Settings popupで日本語が豆腐（□）表示
- jp/ja言語コードの不整合（内部は"jp"、ISO規格は"ja"）

**対応**:
- 新規: `katrain/common/locale_utils.py`
  - `normalize_lang_code()`: 内部正規コード（"en"/"jp"）への変換
  - `to_iso_lang_code()`: ISO 639-1コード（"en"/"ja"）への変換
  - 地域バリアント対応: "ja_JP", "ja-JP" → "jp"
- 豆腐修正: 以下のウィジェットに`font_name=Theme.DEFAULT_FONT`追加
  - `quiz_popup.py`: header_label, btn, start_button, close_button
  - `settings_popup.py`: search_input, search_clear_btn, タブヘッダー
  - `popups.kv`: LabelledTextInput, LabelledPathInput
- meaning_tags後方互換: `normalize_lang = to_iso_lang_code`エイリアス
- テスト25件追加

**PR size**: 1 PR

#### Phase 52-B: 残タスク（予定）

**Deliverables**:
- ゴールデンファイル回帰テスト
- 統合テスト: SGF→解析→Karte全フィールド、バッチ→Summary radar集約
- ドキュメント更新: `docs/02-code-structure.md`, ユーザーガイド
- パフォーマンスベンチマーク: 50局バッチで<5秒

**Non-goals**: 新機能、アーキテクチャ変更、EN/JP以外のi18n、Lexiconデータ追加

**Acceptance Criteria**:
- 既存テスト全パス（2186+ベースライン）
- Phase 45–51で40テスト以上追加 ✅（実績: 600+件）
- バッチ処理がPhase 44比10%以内
- ドキュメントが全新機能・設定をカバー
- `CLAUDE.md` にPhase 52完了エントリ

**PR size**: 1 PR

### 依存関係

```
Phase 45 (Lexicon) ──→ Phase 46 (MeaningTags Core) ──→ Phase 47 (MeaningTags Integration)
                                      │                              │
                                      ↓                              ↓
                              Phase 48 (Radar Model) ──→ Phase 49 (Radar Summary)
                                                                     │
                              Phase 47 ──────────────→ Phase 50 (Critical 3)
                                                                     │
                              Phase 49 ──────────────→ Phase 51 (Radar UI)
                                                                     │
                              Phases 45–51 ──────────→ Phase 52 (Stabilization)
```

### リスク

1. **MeaningTag曖昧性**: 保守的ルール + `uncertain`フォールバック + アンカーなしオプション
2. **Radar軸測定困難**: 寄与要因を文書化、v1制限を許容
3. **閾値チューニング**: 設定可能に、Phase 52でチューニング
4. **既存出力への回帰**: 新セクションは追加的、ゴールデンファイルテスト
5. **非UIフェーズへのUI混入**: Non-goals厳守、UIはPhase 51に集約
6. **Lexicon YAML安定性**: YAMLは安定入力扱い、変更時はテスト更新必須

---

## Phase 53–54 詳細（Batch Report Quality）

### Phase 53: Batch Report基盤（2026-01-24 完了）

**目的**: バッチレポートの品質向上のためのヘルパー関数と表示改善。

**In-scope:**
- `truncate_game_name()`: 長いゲーム名を適切に省略（tail保持）
- `format_wr_gap()`: WR Gap表示のクランプと精度向上
- `make_markdown_link_target()`: カルテリンク生成（相対パス、URL encode）
- カルテ列追加（Top 10 Worst Moves）
- "Best Gap" → "WR Gap" リネーム
- "Practice Priorities" → "練習の優先順位"

**成果物:**
- `katrain/core/batch/helpers.py`（truncate, format_wr_gap, make_markdown_link_target）
- `katrain/core/batch/orchestration.py`（karte_path_map追加）
- `katrain/core/batch/stats.py`（カルテ列、WR Gap表示）

**受け入れ条件:**
- [x] ゲーム名が35文字以内に省略される
- [x] WR Gapが0-100%にクランプ、1桁精度表示
- [x] Top 10 Worst Movesに「カルテ」列表示
- [x] リンククリックでカルテファイルを開ける

---

### Phase 54: Report Quality Improvements（2026-01-25 完了）

**目的**: レポートのローカライズとタグベースの具体的な練習ヒント追加。

**In-scope:**
- `escape_markdown_table_cell()`: テーブルセルの安全なエスケープ
- `lang`パラメータ追加（`run_batch()`, `build_player_summary()`）
- 12+ローカライズヘルパー関数（JP/EN両言語対応）
- タグベース練習ヒント（MeaningTag / ReasonTagに基づく）
- パーセンテージ注記（タグ出現割合の説明）
- 色偏り注記（全黒番/白番の注意書き）
- WR Gap説明改善（JP/EN両言語で明確な説明）

**成果物:**
- `katrain/core/batch/helpers.py`（escape_markdown_table_cell）
- `katrain/core/batch/stats.py`（ローカライズヘルパー、タグヒント）
- `katrain/core/reports/karte_report.py`（WR Gap説明改善）

**受け入れ条件:**
- [x] `lang="jp"`で日本語、`lang="en"`で英語出力
- [x] EN出力にJPマーカー（回、→、（）など）が含まれない
- [x] タグベースの具体的な練習ヒントが表示される
- [x] パーセンテージ注記と色偏り注記が表示される

---

## Phase 55–66 詳細（Post-54 拡張）

### Phase 55: レポート基盤 + ユーザー集計

**目的**: 新セクション追加を標準化する共通基盤と、ユーザー直近N局の集計機構を定義。

**In-scope:**
- `ReportSection` Protocol（section_id, title, render_markdown()）
- セクション登録レジストリ + 挿入位置指定（after_section_id）
- `UserRadarAggregate`: 直近N局（default 10）のRadarMetrics集計
- 集計データの一時保存（メモリ内、バッチ実行時に計算）

**Out-of-scope:**
- 永続的ユーザープロファイルDB
- 既存セクションのリファクタリング

**成果物:**
- `katrain/core/reports/section_registry.py`（~100行）
- `katrain/core/reports/insertion.py`（~50行）
- `katrain/core/analysis/user_aggregate.py`（~80行）
- `tests/test_section_registry.py`
- `tests/test_user_aggregate.py`

**受け入れ条件:**
- [x] ReportSection登録・取得・挿入位置指定が動作
- [x] 既存summary/karte生成が壊れていない（回帰テストパス）
- [x] UserRadarAggregateが直近N局のRadar平均を返す
- [x] normalize_lang()が"ja"/"ja_JP"/"JA" → "jp"変換
- [x] DuplicateSectionErrorで重複検出
- [x] compute_section_order()が安定した挿入順序を保証

**依存**: なし（新規基盤）

**完了**: 2026-01-25（PR #191）

---

### Phase 56: Style Archetype Core ✅

**目的**: RadarMetrics + MeaningTagsから棋風アーキタイプを判定。

**In-scope:**
- `StyleArchetype` frozen dataclass（id, name_key, summary_key, high_axes, low_axes, reinforcing_tags）
- 6アーキタイプ定義: KIAI_FIGHTER/COSMIC_ARCHITECT/PRECISION_MACHINE/SHINOBI_SURVIVOR/AI_NATIVE/BALANCE_MASTER
- `determine_style(radar, tag_counts)` ルールベース判定
- 相対評価: 5軸内の偏差で判定（バランス優先ルール）

**Out-of-scope:**
- ML分類器
- プロ棋士マッチング

**成果物:**
- `katrain/core/analysis/style/__init__.py`
- `katrain/core/analysis/style/models.py`（6アーキタイプ定義）
- `katrain/core/analysis/style/analyzer.py`（~200行）
- `tests/test_style_analyzer.py`（30テスト）

**受け入れ条件:**
- [x] RadarMetrics入力で6種のいずれかを返す
- [x] Fighting軸突出（deviation >= 0.5）+ reinforcing_tags significant → KIAI_FIGHTER
- [x] 全軸バランス（max |deviation| < 0.5）→ 常にBALANCE_MASTER

**依存**: Phase 48（Radar）, Phase 46（MeaningTags）

**完了**: 2026-01-25（PR #192）

---

### Phase 57: Style Karte Integration ✅

**目的**: 判定したスタイルをKarteに出力。

**実装内容:**
- Karte Metaセクションにスタイル情報追加
  - `- Style: 剛腕ファイター`（i18n対応）
  - `- Style Confidence: 85%`
- i18n対応（6アーキタイプ × 2言語 = 12キー、name_keyのみ）
- 12件の統合テスト（CI-safe）

**Deferred to future phases:**
- Summary「My Style Identity」セクション（SectionRegistry経由）
- `style:*:summary` i18nキー
- coach.mdプロンプト変更

**成果物:**
- `katrain/core/reports/karte_report.py`更新（+51行）
- `katrain/i18n/locales/*/katrain.po`更新（6キー×2言語）
- `tests/test_karte_style_integration.py`新規（12件）

**依存**: Phase 56

**完了**: 2026-01-25（PR #193）

---

### Phase 58: 時間データパーサー

**目的**: SGFの時間タグ（BL/WL等）を正規化して抽出。

**In-scope:**
- BL/WL（残り時間）タグの差分計算（Black→BL, White→WL）
- BL/WL は「着手後の残り時間」として解釈（SGF標準仕様）
- 整数・小数形式のパース（IGS/KGS等）
- `TimeMetrics` dataclass（move_number, player, time_left_sec, time_spent_sec）
- `GameTimeData` dataclass（常に返却、has_time_data フラグで判定）
- 浮動小数点許容誤差（EPS=0.001、微小負値は0.0として処理）
- Graceful degradation:
  - 時間データなし → has_time_data=False, metrics=()
  - 時間データあり → has_time_data=True, 全メインライン手を含む（move_number維持）
  - 一部タグ欠損 → 該当手は time_left_sec=None、次の手も time_spent_sec=None
  - 負の差分（秒読みリセット等、delta < -EPS）→ time_spent_sec=None + 警告ログ
  - 不正な値・空リスト → time_left_sec=None + 警告ログ
- メインライン走査のみ（変化図は対象外）
- ルートノードの子から走査開始（ルートはゲームプロパティのみ）
- move_number は実際の着手のみカウント（非着手ノードはスキップ）

**Out-of-scope:**
- SGFへの時間書き戻し
- リアルタイム時計UI
- 変化図の時間解析

**成果物:**
- `katrain/core/analysis/time/__init__.py`
- `katrain/core/analysis/time/models.py`
- `katrain/core/analysis/time/parser.py`（~110行）
- `tests/test_time_parser.py`

**受け入れ条件:**
- [x] 手ごとの時間タグ（BL/WL）が存在するSGFからtime_spentを正しく抽出
- [x] 時間タグなしSGFで GameTimeData(has_time_data=False, metrics=()) を返却
- [x] 整数形式（IGS）・小数形式（KGS）両方でテストパス
- [x] 時間データありの場合、全メインライン手を含む（move_number アライメント維持）
- [x] 部分的にタグ欠損があるSGFで、該当手は time_left_sec=None
- [x] タグ欠損後の有効タグで time_spent_sec=None（ギャップ越しの差分計算防止）
- [x] 微小負値（delta >= -EPS）は 0.0 として処理（浮動小数点許容誤差）
- [x] 負の差分（delta < -EPS、秒読みリセット等）で time_spent_sec=None + 警告ログ
- [x] 空リスト等のmalformed SGFで IndexError を発生させない
- [x] Black は BL、White は WL を読むことをテストで検証
- [x] BL/WL は「着手後の残り時間」であることをテストで検証（off-by-one防止）

**依存**: なし

**完了**: 2026-01-25（PR #194）

---

### Phase 59: Pacing & Tilt Core

**目的**: 消費時間とKataGo損失の相関から早打ち悪手・ティルトエピソードを検出。

**In-scope:**
- 相対メトリクス（プレイヤー別メディアン基準）:
  - is_blitz = time_spent < player_median × 0.3
  - is_long_think = time_spent > player_median × 3.0
  - tilt_trigger = canonical_loss > game_p90_loss（strict >）
- `PacingConfig`: 設定パラメータ（thresholds, window size等）
- `PacingMetrics`: 手ごとの分類（is_blitz, is_long_think, is_impulsive, is_overthinking）
- `TiltEpisode`: 連鎖ミスエピソード（trigger, start, end, cumulative_loss, severity）
- `TiltSeverity`: MILD/MODERATE/SEVERE（決定論的優先順位）
- `GamePacingStats`: ゲーム統計（medians, thresholds, coverage diagnostics）
- `LossSource`: 損失値のソース追跡（SCORE/LEELA/POINTS/NONE）
- Best-effort coverage: MoveEval欠損時は警告+スキップ+継続
- 混合エンジン検出: has_mixed_sources フラグ

**Out-of-scope:**
- ティルト確定診断（疑いフラグのみ）
- policy entropy計算
- GUI表示（Phase 60）

**成果物:**
- `katrain/core/analysis/time/pacing.py`（~360行）
- `katrain/core/analysis/time/__init__.py`更新
- `tests/test_pacing.py`（42件）

**受け入れ条件:**
- [x] プレイヤー別メディアン基準で早打ち/長考を判定
- [x] 連鎖ミス（トリガー後5手以内）をTiltEpisodeとしてグループ化
- [x] 時間データなし局では空リスト返却
- [x] p90 == 0.0 時はティルト検出無効化
- [x] Strict '>' トリガー条件（p90と同値はトリガーしない）
- [x] First-come-first-served でエピソード重複防止
- [x] Coverage gap検出とhas_coverage_gapsフラグ
- [x] 混合エンジン検出とhas_mixed_sourcesフラグ

**依存**: Phase 58

**完了**: 2026-01-25（PR #194）

---

### Phase 60: Pacing/Tilt統合

**目的**: 時間分析結果をSummary/Karteに出力。

**In-scope:**
- Summaryに「Time Management」セクション追加（Phase 55レジストリ使用）
- Karteの重要局面に時間アイコン（🐇/🐢/🔥）
- 時間データなしSGFではセクションをスキップ

**Out-of-scope:**
- 行動ルール自動生成（LLM任せ）
- GUI上の時間表示

**成果物:**
- `katrain/core/reports/sections/time_section.py`（~110行）
- `katrain/core/analysis/time/pacing.py`更新（`get_pacing_icon()`, `extract_pacing_stats_for_summary()`追加）
- `katrain/i18n/locales/*/katrain.po`更新（25キー）
- `tests/test_time_section.py`（新規）

**受け入れ条件:**
- [x] Summaryに早打ち悪手率（相対）、ティルト疑い回数を表示
- [x] Karteの該当局面に🐇/🐢/🔥アイコン付与
- [x] 時間タグなしSGFでセクション非表示

**依存**: Phase 55, Phase 59

**完了**: 2026-01-25（PR #195）

---

### Phase 61: Risk Context Core ✅

**目的**: 形勢に応じたリスクテイク行動を分析。ScoreStdev不在時のフォールバック付き。

**In-scope:**
- `RiskContext` dataclass（judgment_type, risk_behavior, is_strategy_mismatch）
- 状況判定: WINNING/LOSING/CLOSE（AND条件：WR AND Score両方必要）
- ScoreStdev利用時: delta_stdev計算
- フォールバック（ScoreStdev不在時）: volatility_metric（直近N手のScoreLead標準偏差）
- Graceful degradation

**Out-of-scope:**
- UIオーバーレイ
- KataGo設定自動変更

**成果物:**
- `katrain/core/analysis/risk/__init__.py`（~60行）
- `katrain/core/analysis/risk/models.py`（~210行）
- `katrain/core/analysis/risk/analyzer.py`（~320行）
- `tests/test_risk_analyzer.py`（69テスト）

**受け入れ条件:**
- [x] ScoreStdev存在時: delta_stdevで複雑化度を計算
- [x] ScoreStdev不在時: volatilityにフォールバック
- [x] RiskContext dataclassで結果返却

**依存**: なし

**完了**: 2026-01-25（PR #196）

---

### Phase 62: Risk統合

**目的**: リスク分析結果をKarteの「勝負術」セクションとして出力。

**In-scope:**
- Karteに「⚖️ Game Management」セクション追加（Phase 55レジストリ使用）
- 優勢時の振る舞い評価（Risk Taker / Solid）
- 劣勢時の振る舞い評価（Fighter / Resigned）
- フォールバック使用時は「(estimated)」ラベル

**Out-of-scope:**
- coach.mdプロンプト変更（Deferred）
- 形勢グラフオーバーレイ

**成果物:**
- `katrain/core/reports/sections/risk_section.py`（~80行）
- `katrain/i18n/locales/*/katrain.po`更新（10キー）

**受け入れ条件:**
- [x] Karteに「優勢時/劣勢時の振る舞い」評価を表示
- [x] 英語/日本語で正しく表示
- [x] フォールバック時は(estimated)表示
- [x] 3段階ラベル（Solid/Mixed/Risk Taker, Fighter/Mixed/Resigned）
- [x] Duck-typed stubによるPhase 61からのテスト分離
- [x] 全27テスト通過

**依存**: Phase 55, Phase 61

**完了**: 2026-01-26（PR #197）

---

### Phase 63: Curator Scoring

**目的**: プロ棋譜の「今の自分に合う度合い」をスコア化。

**In-scope:**
- `SuitabilityScore` dataclass（needs_match, complexity, total）
- needs_match: Phase 55の`UserRadarAggregate`弱点軸と棋譜MeaningTags一致度
- complexity: ScoreLead/WR変動の安定度（Phase 61フォールバックと同様）
- 相対スコア（バッチ内パーセンタイル）

**Out-of-scope:**
- Human-SLモデル統合
- 厳密な「ベスト1証明」ランキング

**成果物:**
- `katrain/core/curator/__init__.py`
- `katrain/core/curator/models.py`
- `katrain/core/curator/scoring.py`（~150行）
- `tests/test_curator_scoring.py`

**受け入れ条件:**
- [x] UserRadarAggregate + 棋譜MeaningTagsからスコア計算
- [x] スコアがバッチ内パーセンタイルで表現（ECDF-style）
- [x] ScoreStdev不在時もstability計算可能（volatilityフォールバック）

**依存**: Phase 55（UserRadarAggregate）, Phase 48, Phase 46

**完了**: 2026-01-26（PR #198）

---

### Phase 64: Curator出力 ✅

**目的**: 複数SGFのランキングと学習ガイド用データをJSON出力。

**In-scope:**
- `curator_ranking.json` 出力（title, score_percentile, recommended_tags）
- `replay_guide.json` 出力（game_title, highlight_moments[3-5]）
- highlight_moments = Critical 3ロジック応用
- バッチ完了時に自動生成（既存フローに追加）

**Out-of-scope:**
- 専用Curator UI画面
- バッチUI変更（v1はJSONのみ、UIトグルは将来検討）
- LLM自動呼び出し

**成果物:**
- `katrain/core/curator/batch.py`（310行）
- `katrain/core/curator/guide_extractor.py`（142行）
- `tests/test_curator_batch.py`（31テスト）
- BatchResult拡張（curator_ranking_written等のフィールド追加）
- orchestration.py統合（generate_curatorパラメータ追加）

**受け入れ条件:**
- [x] バッチ完了時に`curator_ranking_{timestamp}.json`生成
- [x] 選択SGFから`replay_guide_{timestamp}.json`（highlight_moments）生成
- [x] 各momentにMeaningTagベースのmeaning_tag_id/label付与
- [x] percentile=None は 0 に正規化
- [x] float フィールドは 3 桁に丸め
- [x] UNCERTAIN タグは recommended_tags から除外
- [x] 空バッチでも有効な空JSONファイル生成

**依存**: Phase 63, Phase 50（Critical 3）, Phase 42（Batch Core）

**完了日**: 2026-01-26

---

### Phase 65: Post-54 Integration ✅

**目的**: Phase 55-64の統合テストと既存機能への影響確認。

**In-scope:**
- 統合テスト（Style + Pacing + Risk + Curator組み合わせ）
- 既存機能回帰テスト（Phase 24ゴールデンテスト）
- パフォーマンス確認（バッチ処理速度）

**Out-of-scope:**
- 新機能追加

**成果物:**
- `tests/test_post54_integration.py`
- `tests/test_regression_post54.py`

**受け入れ条件:**
- [x] 全新規テストパス（22件）
- [x] Phase 24ゴールデンテストパス（62件）
- [x] 全テストスイートパス（2601件）

**依存**: Phase 55-64

**完了日**: 2026-01-26

---

### Phase 66: Post-54 品質強化 ✅

**目的**: ドキュメント整理、i18n完了、Summary/Karte品質改善。

**In-scope:**
- ドキュメント更新（usage-guide.md, 01-roadmap.md）
- i18n完了確認（全新規キー翻訳済み）
- 手動E2Eテスト（起動→バッチ→レポート確認）
- **Summary/Karte品質改善**（PR #202）:
  - A) ゲームラベル括弧バランス保証
  - B) Weakness Hypothesisエビデンス追加
  - C) Style信頼度ゲート（20%未満で「不明」表示）
  - D) MTag単一タグフォールバック（UNCERTAIN削減）
  - E) ミスカテゴリラベルローカライズ
  - F) Top Mistake Types明確化（分類済み/UNCERTAIN件数表示）

**Out-of-scope:**
- 新機能追加
- 公開リリース作業

**成果物:**
- `docs/usage-guide.md`更新（9章: Post-54新機能ガイド追加）
- `docs/01-roadmap.md`更新
- `katrain/core/batch/helpers.py`: `_ensure_balanced_brackets()`, `_smart_truncate()`, `format_game_display_label()`, `format_game_link_target()`
- `katrain/core/batch/stats.py`: `EvidenceMove`, `_select_evidence_moves()`, `_format_evidence_with_links()`
- `katrain/core/reports/karte_report.py`: `STYLE_CONFIDENCE_THRESHOLD`
- `katrain/core/analysis/meaning_tags/classifier.py`: Priority 11b単一タグフォールバック
- `katrain/core/analysis/presentation.py`: `get_mistake_category_label()`
- `tests/test_report_invariants.py`: 40件の不変条件テスト

**受け入れ条件:**
- [x] 手動E2E（起動→SGF読込→バッチ→レポート）パス
- [x] 英語/日本語UIで新セクション正しく表示
- [x] 全i18nキー翻訳済み（548キー、fuzzy: 0、未翻訳: 0）
- [x] 括弧バランス保証（全分岐で正しくネスト）
- [x] Weakness Hypothesisにエビデンス表示
- [x] Style信頼度 < 20%で「不明」表示
- [x] 単一タグ（atari, low_liberties, endgame_hint）がUNCERTAINにならない
- [x] 全テストパス（2640件）

**依存**: Phase 65

**完了日**: 2026-01-26

---

### Phase 67: Engine Stability Improvements ✅ **完了**

**目的**: KataGoEngine と LeelaEngine のシャットダウン安定性向上、テスト基盤強化。

**In-scope:**
- Robust shutdown sequence（ヘルパーメソッド追加）
  - `_safe_queue_put()`, `_safe_terminate()`, `_safe_close_pipes()`, `_safe_force_kill()`
- `put_nowait()` + タイムアウトフォールバックでデッドロック防止
- Leela engine shutdown の明示的パイプクローズ
- `critical_moves.py` インポート修正（`build_eval_snapshot` → `snapshot_from_game`）

**Out-of-scope:**
- 新機能追加
- Command Pattern導入（Phase 68）

**成果物:**
- `katrain/core/engine.py` 更新（+151行）
- `katrain/core/leela/engine.py` 更新（+17行）
- `tests/fakes.py` 新規（FakePopen, FakePipe, MinimalKatrain）
- `tests/test_engine_coverage.py` 新規（14テスト）
- `tests/tools/check_engine_leak.py` 新規（リーク検証ツール）

**受け入れ条件:**
- [x] `uv run pytest tests -v` パス（2640件）
- [x] `python -m katrain` 起動確認
- [x] エンジン終了時のリークなし

**依存**: Phase 66

**完了日**: 2026-01-26

---

### Phase 68: Command Pattern for KataGoEngine ✅ **完了**

**目的**: KataGoEngine のリクエスト処理を Command Pattern でリファクタリングし、テスト容易性と拡張性を向上。

**重要制約**: `katrain/core/engine.py` との名前衝突を避けるため、パッケージ名は `katrain/core/engine_cmd/` を使用。

#### Phase 68-A: Command Core ✅

**成果物:**
- `katrain/core/engine_query.py`: `build_analysis_query()` 関数（~140行）
- `katrain/core/engine_cmd/__init__.py`: 公開API
- `katrain/core/engine_cmd/commands.py`: `AnalysisCommand` ABC, `StandardAnalysisCommand`（~220行）
- `katrain/core/engine_cmd/executor.py`: `CommandExecutor`（~250行）
- `tests/test_engine_query.py`: クエリビルドテスト（14件）
- `tests/test_engine_commands.py`: コマンドテスト（30件）

**主な特徴:**
- `@dataclass(eq=False)` による identity-based hashing（Set対応）
- `_cancelled` threading.Event によるスレッドセーフなキャンセル検出
- `deque(maxlen=100)` による履歴管理
- Option A delivery guarantee（at most one late delivery）

**受け入れ条件:**
- [x] `uv run pytest tests/test_engine_commands.py tests/test_engine_query.py -v` パス（44件）
- [x] `python -m katrain` 起動確認

**完了日**: 2026-01-26（PR #204）

#### Phase 68-B: Engine統合 ✅

**成果物:**
- `katrain/core/engine.py` 更新（-33行、DRY化）

**変更内容:**
- `build_analysis_query()` を `engine_query.py` からインポート
- `request_analysis()` を `build_analysis_query()` 使用にリファクタリング
- 後方互換性を完全維持

**受け入れ条件:**
- [x] `uv run pytest tests -v` 全テストパス（2659件）
- [x] `python -m katrain` で解析動作確認

**完了日**: 2026-01-26（PR #205）

#### Phase 68-C: Pondering便利メソッド ✅

**In-scope:**
- `executor.is_pondering` プロパティ
- `executor.get_ponder_command()` メソッド
- `executor.stop_pondering()` メソッド
- 13件のponderingテスト追加

**成果物:**
- `katrain/core/engine_cmd/executor.py` にpondering関連メソッド追加
- `tests/test_engine_commands.py` にTestPonderingクラス追加

**受け入れ条件:**
- [x] `uv run pytest tests/test_engine_commands.py -v` パス（57テスト）
- [x] pondering テスト13件全パス

**完了日**: 2026-01-26（PR #206予定）

---

### Phase 69–79: Large Refactor & Maintainability ✅ **完了**（2026-01-28）

**目的**: コード品質向上、テストカバレッジ拡大、保守性改善のための段階的リファクタリング。

**背景（調査結果）:**
- `__main__.py`: 1,420行 / 109メソッド（God Object）
- `batch/stats.py`: 1,798行（単一責務違反）
- `karte_report.py`: 1,610行（単一責務違反）
- `except Exception`: 約90箇所（サイレント失敗リスク）

**共通の受け入れ条件:**
- [ ] `uv run pytest tests -v` パス
- [ ] `python -m katrain` 起動確認
- [ ] 後方互換維持（re-export で既存インポートパス保持）
- [ ] mypy（OPTIONAL、必須ではない）

---

#### Phase 69: テスト強化（sgf_parser + base_katrain）✓ 2026-01-27

**In-scope:**
- `tests/test_parser.py` 拡張（Move, ParseError, EdgeCases, RoundTrip）
- `tests/test_base_katrain.py` 新規（parse_version, Player, config, logging）

**成果物:**
- `tests/test_parser.py`: 19テスト追加
  - TestMoveClass (9): ラウンドトリップ、I列拒否、等価性・ハッシュ
  - TestParseError (3): 不正SGF検出
  - TestPropertyEdgeCases (5): KM/HA無効値、標準ボードサイズ
  - TestRoundTrip (2): 特殊文字、変化ツリーのセマンティック等価性
- `tests/test_base_katrain.py`: 17テスト新規
  - TestParseVersion (4): バージョン文字列パース
  - TestPlayerClass (7): プロパティ・メソッド
  - TestKaTrainBaseConfig (4): 設定取得（分離環境）
  - TestKaTrainBaseLogging (2): ログバッファ記録

**完了日**: 2026-01-27（PR #207）

---

#### Phase 70: 複雑関数リファクタリング ✓ 2026-01-27

**In-scope:**
- `game.py` の `analyze_extra()` 分割（119行→5メソッド）
- `_compute_important_moves()` の重複ループ解消
- 単体テスト追加

**成果物:**
- `katrain/core/game.py` 更新
- `tests/test_game_analysis.py`（26テスト）
- `tests/conftest.py` 共有フィクスチャ追加
- `tests/test_game_core.py` リファクタ

**完了日**: 2026-01-27（PR #208）

---

#### Phase 71: batch/stats.py 分割 ✓ 2026-01-27

**In-scope:**
- `katrain/core/batch/stats/` パッケージ化
  - `models.py`, `extraction.py`, `aggregation.py`, `formatting.py`
- `__init__.py` で re-export（後方互換）
- lazy import で循環依存回避

**成果物:**
- `katrain/core/batch/stats/` パッケージ（4モジュール）
  - `models.py`: EvidenceMove + i18n定数（239行）
  - `extraction.py`: extract_game_stats, extract_players_from_stats（343行）
  - `aggregation.py`: build_batch_summary, i18n getters, helpers（563行）
  - `formatting.py`: build_player_summary（766行、遅延ロード）
- `tests/test_batch_stats_imports.py`（17テスト）

**完了日**: 2026-01-27（PR #209）

---

#### Phase 72: karte_report.py 分割 ✓ 2026-01-27

**In-scope:**
- `katrain/core/reports/karte/` パッケージ化
  - `models.py`: 例外・定数（最下層）
  - `helpers.py`: 純粋関数
  - `builder.py`: メインエントリポイント
  - `json_export.py`: JSON出力
  - `llm_prompt.py`: LLMプロンプト生成
  - `sections/`: セクション生成関数群
    - `context.py`: KarteContext dataclass（閉包変数の明示化）
    - `summary.py`: サマリ・分布セクション
    - `important_moves.py`: 重要手・タグセクション
    - `diagnosis.py`: 弱点・練習優先度セクション
    - `metadata.py`: 定義・品質・リスクセクション
- `karte_report.py` をシムに変換（後方互換性維持）
- `karte/__init__.py` でlazy wrapper使用（循環インポート回避）

**成果物:**
- `katrain/core/reports/karte/` パッケージ（12ファイル）
- `katrain/core/reports/karte_report.py`（シム、~45行）
- `tests/test_karte_imports.py`（13テスト）

**完了日**: 2026-01-27

---

#### Phase 73: KaTrainGui分割 A（KeyboardManager）✓ 2026-01-27

**実装内容:**
- KaTrainGuiからキーボード処理（約145行）をKeyboardManagerに抽出
- 依存注入パターン（SGFManagerと同様）でKivy非依存テストを実現
- `_on_keyboard_down()`, `_on_keyboard_up()`, `_single_key_action()`, `shortcuts`プロパティを移動
- `KaTrainGui.shortcuts`は委譲プロパティとして後方互換維持

**成果物:**
- `katrain/gui/managers/__init__.py`（空パッケージ）
- `katrain/gui/managers/keyboard_manager.py`（~280行）
- `tests/test_keyboard_manager.py`（53テスト）

**テスト:** 2826件（+53件）

---

#### Phase 74: KaTrainGui分割 B（ConfigManager）✓ 2026-01-27

**In-scope:**
- 設定管理を ConfigManager に集約
- 3パターンのアクセスを統一インターフェースに

**成果物:**
- `katrain/gui/managers/config_manager.py`（~196行）
- `tests/test_config_manager.py`（36テスト）
- `tests/test_config_imports.py`（13テスト）

**設計特徴:**
- Kivy完全非依存（依存注入パターン）
- 更新セマンティクス明確化:
  - `set_section()`: REPLACE
  - `save_export_settings()`: PARTIAL UPDATE
  - `save_batch_options()`: PARTIAL UPDATE（batch_optionsのみMERGE）
- コピーセマンティクス:
  - `get()`: 直接参照（変更禁止ポリシー）
  - `get_section()`: SHALLOW COPY

**テスト:** 2875件（+49件）

---

#### Phase 75: KaTrainGui分割 C（PopupManager）✓ 2026-01-28

**In-scope:**
- `_do_*_popup` メソッド群を PopupManager に移動

**成果物:**
- `katrain/gui/managers/popup_manager.py`（~154行）
- `tests/test_popup_manager.py`（21テスト）

**テスト:** 2896件（+21件）

---

#### Phase 76: KaTrainGui分割 D（GameStateManager）✓ 2026-01-28

**In-scope:**
- ゲーム状態のライフサイクル管理を分離
- undo/redo、重要局面ナビゲーション、投了、ノート設定、挿入モード

**成果物:**
- `katrain/gui/managers/game_state_manager.py`（~130行）
- `tests/test_game_state_manager.py`（22テスト）
- PEP 562 lazy imports（Kivy非依存テスト実現）

**テスト:** 2918件（+22件）

---

#### Phase 77: エラーハンドリング A（監査・分類）✓ 2026-01-28

**In-scope:**
- 全 `except Exception` を監査（108箇所検出）
- 意図的（noqa付き）vs 改善対象を分類
- 分類結果をドキュメント化

**成果物:**
- `scripts/audit_exceptions.py`（AST解析スクリプト）
- `scripts/generate_audit_stub.py`（スタブ生成）
- `scripts/generate_audit_doc.py`（ドキュメント生成）
- `scripts/verify_audit.py`（検証スクリプト）
- `docs/archive/error-handling-audit.md`（108件分類済み）

**結果サマリ:**
- 検出パターン: except Exception, bare except, except BaseException
- 総数: 108件（intentional: 39件, improve: 69件）
- noqa付き: 18件
- 検証: 全DoD条件パス

---

#### Phase 78: エラーハンドリング B（ユーザー操作パス）✓ 2026-01-28

**In-scope:**
- Phase 77監査結果に基づき、ユーザー操作に直結する20箇所を改善
- 広範な`except Exception`を具体的な例外クラスに置換
- Safe Boundary Pattern の適用（既知例外→境界フォールバック）
- 例外ハンドラ内での安全なプレビュー構築（プライバシー保護）

**成果物（8ファイル、20ハンドラ）:**

| Sub-Phase | ファイル | 行番号 | 変更内容 |
|-----------|----------|--------|----------|
| 78A | `sgf_parser.py` | 681, 691, 705 | GIB komi/date抽出: (AttributeError, ValueError) |
| 78A | `settings_popup.py` | 202, 253, 286, 293, 1196 | Export/Import/Save: OSError, UnicodeDecodeError, JSONDecodeError |
| 78B | `sgf_manager.py` | 120, 153, 160, 176, 254 | クリップボード/ファイル操作: ParseError, OSError |
| 78C | `engine_compare_popup.py` | 96 | 比較ビルド: (ValueError, AttributeError) |
| 78C | `package_export_ui.py` | 79, 86 | カルテ/SGF生成: ドメイン固有例外 |
| 78C | `popups.py` | 245, 294 | Spinner/InputParse: ValueError, from e |
| 78C | `settings_export.py` | 259 | Atomic save cleanup: ログ付きre-raise |
| 78C | `batch_analyze_sgf.py` | 197 | エンジン起動: (OSError, RuntimeError, EngineError) |

**設計原則:**
- サイレントな例外無視を排除（全ハンドラでログ出力）
- `from e`によるtraceback保持
- ユーザー向けメッセージは簡潔、詳細はログのみ

**PRs:** #216

---

#### Phase 79: エラーハンドリング C（バックグラウンドパス）✓ 2026-01-28

**In-scope:**
- Phase 77監査結果に基づき、バックグラウンド処理の27箇所を改善
- 12ファイル更新: batch/analysis.py, batch/orchestration.py, curator/batch.py, reports/karte/builder.py, reports/karte/json_export.py, reports/karte/sections/important_moves.py, reports/karte/sections/metadata.py, reports/package_export.py, gui/features/summary_aggregator.py, gui/features/summary_io.py, gui/features/summary_ui.py, tests/test_karte_style_integration.py
- Expected例外（SGFError, OSError, ValueError, KeyError等）: 短いログ、tracebackなし
- Unexpected例外: traceback必須（exc_info=True or traceback.format_exc()）
- WriteError message prefix pattern: [generation], [write], [unexpected]

**成果物:**
- Phase 79A: Core Batch（6箇所）
- Phase 79B: Reports（11箇所）
- Phase 79C: Curator（3箇所）
- Phase 79D: Summary（7箇所）
- 新規テスト: test_error_handling_phase79.py（5テスト）
- テスト総数: 2924件（+6件）
- PRs: #217

---

### Phase 55–66 Deferred / Cut（20%）

| 項目 | 理由 |
|------|------|
| Weakness Repeater全体（案4） | SRS UI/ドリルモードが重い |
| coach.mdプロンプト自動変更 | LLM解釈に委ねる方針 |
| Human-SLモデル統合 | 追加モデル管理が複雑 |
| 厳密なBest-1ランキング証明 | チューニング負担大 |
| ティルト確定診断 | 疑いフラグのみ |
| Curator UI（バッチ画面トグル） | v1はJSONのみ |
| Replay Guide Side-by-Side UI | JSON出力優先 |
| 絶対閾値デフォルト | 相対メトリクス優先 |

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

- 2026-01-20: Phase 43 完了（Stability Audit）
  - **Issue 1 (P0)**: Config save atomic化
    - `config_store.py`: tempfile + os.replace + os.fsync
    - クラッシュ時のデータ損失防止
  - **Issue 2 (P0)**: save_config() エラーハンドリング
    - `base_katrain.py`: `_save_config_with_errors()`関数抽出
    - 部分失敗時も残りのセクションを保存継続
  - **Issue 3 (P1)**: Leela shutdown TimeoutExpired対応
    - `leela/engine.py`: kill()後のwait()でも例外をキャッチ
  - **Issue 4 (P1)**: LeelaEngine analysis thread join
    - プロセス終了後にスレッドjoin（blocking readline対策）
  - **Issue 5 (P2)**: Theme loader改善
    - `gui/theme_loader.py`: 新規モジュール（side-effect free）
    - UTF-8エンコーディング、hasattrチェック、logging使用
  - **テスト**: 18件追加（4ファイル）
  - **テスト総数**: 1529件
- 2026-01-20: Phase 42-C 完了（Batch Import Tests）
  - **新規テスト**: `tests/test_batch_core_imports.py`（19件）
    - 後方互換インポート検証（`tools.batch_analyze_sgf`）
    - 新API検証（`core.batch`）
    - 関数動作検証（parse_timeout, get_canonical_loss等）
    - `__all__`エクスポート検証
  - **テスト総数**: 1511件
- 2026-01-20: Phase 42-B 完了（Batch Analysis移行）
  - **新規モジュール**: `katrain/core/batch/`に分析・オーケストレーション・統計機能を移行
    - `analysis.py` (~400行): `analyze_single_file()`, `analyze_single_file_leela()`
    - `orchestration.py` (~440行): `run_batch()` メインエントリポイント
    - `stats.py` (~960行): ゲーム統計抽出、サマリー生成
  - **遅延インポート**: `__getattr__`による重いモジュールの遅延ロード
  - **後方互換**: `tools/batch_analyze_sgf.py`はCLI + 再エクスポートレイヤーに簡素化（~240行）
  - **GUI更新**: `batch_core.py`/`batch_ui.py`のインポートを`core.batch`に変更
  - **テスト総数**: 1492件
- 2026-01-20: Phase 42-A 完了（Batch Core移行）
  - **新規パッケージ**: `katrain/core/batch/`（Kivy非依存）
    - `models.py`: `WriteError`, `BatchResult` dataclass
    - `helpers.py`: 純粋関数15種（choose_visits_for_sgf, get_canonical_loss,
      parse_timeout_input, safe_write_file, read_sgf_with_fallback,
      parse_sgf_with_fallback, has_analysis, collect_sgf_files_recursive,
      collect_sgf_files, wait_for_analysis, sanitize_filename,
      get_unique_filename, normalize_player_name, safe_int,
      needs_leela_karte_warning）
    - `__init__.py`: パッケージエクスポート
  - **後方互換**: `tools/batch_analyze_sgf.py`から再エクスポート
  - **GUI更新**: `batch_core.py`のインポートを`core.batch`に変更
  - **アーキテクチャテスト**: `test_batch_does_not_import_kivy()`追加
  - **テスト総数**: 1492件
- 2026-01-20: Phase 41 完了（コード品質リファクタリング）
  - **Phase 41-A**: `AnalysisMode(str, Enum)`導入、`parse_analysis_mode()`関数
    - `game.py`/`__main__.py`のmode文字列をEnum化
    - 不明なmode値はSTOPにフォールバック（logging.warning出力）
  - **Phase 41-B**: コマンドハンドラ抽出
    - `gui/features/commands/`パッケージ新設（4モジュール）
    - `__main__.py`の`_do_*`メソッドを委譲パターンに変更
  - **Phase 41-C**: 例外ハンドリング改善
    - `# noqa: BLE001`コメント（理由付き）追加
    - スレッド例外: OUTPUT_ERROR + スタックトレース
    - シャットダウン例外: OUTPUT_DEBUG（継続処理）
  - **Phase 41-D**: Magic Number定数化
    - `AI_ACCURACY_DECAY_BASE`、`AI_PASS_LOSS_THRESHOLD`、`AI_ENDGAME_FILL_RATIO_DEFAULT`
  - **テスト**: 14件追加（test_analysis_mode.py）
  - **テスト総数**: 1491件
- 2026-01-19: Phase 40 完了（Leela Zero対戦機能）
  - **AI_LEELA定数**: `constants.py`にAI_LEELA追加、AI_STRATEGIES/RECOMMENDED_ORDER/STRENGTH統合
  - **LeelaStrategy**: `ai.py`に実装（~90行）
    - `LeelaNotAvailableError`例外クラス
    - `generate_move()`: Leela Zeroから着手を取得
    - 動的board_size/komi対応（9x9等の異サイズ盤対応）
    - 10秒タイムアウト、poll_interval=10ms（既存KataGoパターン踏襲）
  - **config.json**: `ai:leela: {}`と`leela.play_visits: 500`追加
  - **__main__.py**: `LeelaNotAvailableError`キャッチ＋ステータスバー表示
  - **settings_popup.py**: Play Visits UI追加（50〜max_visits範囲バリデーション）
  - **i18n**: EN/JP翻訳追加（10キー、エラーメッセージ含む）
  - **テスト**: 14件（test_leela_strategy.py）、test_ai.pyにAI_LEELAスキップ追加
  - **テスト総数**: 1477件
- 2026-01-19: Phase 39 完了（エンジン比較ビュー）
  - **PR-1**: 比較ロジック（`analysis/engine_compare.py`、~400行）
    - `ComparisonWarning` enum、`MoveComparison`/`EngineStats`/`EngineComparisonResult` dataclass
    - `build_comparison_from_game()` 関数
    - `compute_spearman_manual()` 手動Spearman相関（scipy不使用）
    - テスト38件（test_engine_compare.py）
  - **PR-2**: 比較UI（`gui/features/engine_compare_popup.py`、~660行）
    - タブ切替UI（手別比較 / 統計サマリー）
    - ScrollView固定 + 乖離フィルタ（デフォルトON）
    - 行クリックで該当手にジャンプ
    - MyKatrainメニューに「エンジン比較」項目追加
    - i18n 35+キー追加（en/jp）
  - **テスト総数**: 1463件
- 2026-01-18: Phase 38 完了（安定化）
  - **PR-1**: エラーハンドリング強化
    - `_safe_int()` ヘルパー関数（batch_core.py、サイレントデフォルト処理）
    - `save_manifest()`, `save_player_profile()` にtry-except追加（io.py）
    - `print()` を `katrain.log()` に変更（engine.py）
    - shutdown例外に`OUTPUT_EXTRA_DEBUG`ログ追加（engine.py）
    - 例外具体化 + binasciiインポート（summary_stats.py）
    - テスト8件（test_batch_validation.py）
  - **PR-2**: Gameコアモジュールテスト
    - Game初期化テスト（19x19, 9x9）
    - Game.play()テスト（single stone, pass, multiple stones）
    - test_board.py MockKaTrain/MockEngineパターン踏襲
    - テスト9件（test_game_core.py）
  - **テスト総数**: 1425件（+17件）
- 2026-01-18: Phase 36 PR-2 完了（Leelaバッチ解析実装）
  - **analyze_single_file_leela()**: per-move Leela解析関数（~180行）
  - **run_batch()拡張**: analysis_engine, leela_engine, per_move_timeout パラメータ追加
  - **エンジン検証**: バッチ開始時のLeela alive チェック
  - **インポート追加**: LeelaEngine, LeelaPositionEval, leela_position_to_move_eval, EvalSnapshot, MoveEval
  - **制限事項**: Leelaカルテ生成は未対応（Phase 36 MVP）
  - **テスト**: 13件（test_batch_leela_analysis.py）
- 2026-01-18: Phase 36 PR-1 完了（Leelaバッチ解析基盤）
  - **LeelaEngine.is_idle()**: スレッドセーフなアイドル状態チェック（ロック保護）
  - **cancel_analysis()**: ロック保護追加（_current_request_id）
  - **Batch UI engine selection**: KataGo/Leela Zero切替トグルボタン
  - **collect_batch_options()**: analysis_engineフィールド追加
  - **i18n**: EN/JP翻訳追加（5キー）
  - **テスト**: 22件（test_leela_engine_idle.py: 12件、test_batch_engine_option.py: 10件）
- 2026-01-18: Phase 35 完了（Leelaカルテ統合）
  - **has_loss_data()**: MoveEvalに損失データが存在するか判定するヘルパー関数
  - **format_loss_with_engine_suffix()**: 損失値フォーマット（Leelaは「(推定)」サフィックス付き）
  - **worst_move_for()**: has_loss_data()ベースでLeela対応（0.0損失も候補に含む）
  - **summary_lines_for()**: worst move表示にエンジンサフィックス追加
  - **opponent_summary_for()**: worst move表示にエンジンサフィックス追加
  - **Important Moves table**: Loss列にエンジンサフィックス追加
  - **テスト**: 21件（test_karte_leela_integration.py）
- 2026-01-18: Phase 34 完了（UIエンジン切替）
  - **needs_leela_warning()**: Leela選択時の整合性チェックヘルパー関数
  - **Settings UI**: Analysis タブにエンジン選択ラジオボタン追加
  - **保存ロジック**: MERGEパターン（他のengineキーを保持）+ 例外処理
  - **警告表示**: Leela選択 + Leela無効時に STATUS_INFO で通知
  - **TAB_RESET_KEYS**: Analysis タブリセットで KataGo に戻る
  - **i18n**: EN/JP 翻訳追加（5キー）
  - **テスト**: 20件（test_engine_ui_selection.py）
- 2026-01-18: Phase 33 完了（エンジン選択設定）
  - **VALID_ANALYSIS_ENGINES**: `FrozenSet[str]`（EngineTypeから派生、UNKNOWN除外）
  - **DEFAULT_ANALYSIS_ENGINE**: "katago"（定数）
  - **get_analysis_engine()**: 設定から解析エンジンを取得（unhashable型ガード付き）
  - **config.json**: `engine.analysis_engine` キー追加
  - **テスト**: 30件（test_analysis_engine_config.py）
- 2026-01-18: Phase 32 完了（レポートLeela対応）
  - **EngineType enum**: KATAGO/LEELA/UNKNOWNの3種別
  - **detect_engine_type()**: MoveEvalからエンジン種別を推定
  - **get_canonical_loss_from_move()**: leela_loss_est対応+全損失値クランプ
  - **format_loss_label()**: エンジン種別に応じた損失ラベルフォーマット
    - KataGo: `-3.5目` / `-3.5 pts`
    - Leela: `-3.5目(推定)` / `-3.5 pts(est.)`
  - **テスト**: 35件（test_engine_type_labels.py）
- 2026-01-18: Phase 31 完了（Leela→MoveEval変換）
  - **katrain/core/leela/conversion.py**: 変換モジュール新規作成（~280行）
  - **MoveEval.leela_loss_est**: Leela Zero推定損失フィールド追加
  - **leela_position_to_move_eval()**: 単一手の変換関数
  - **leela_sequence_to_eval_snapshot()**: シーケンス変換（検証付き）
  - **テスト**: 36件（test_leela_conversion.py）
- 2026-01-18: Phase 30-39 ロードマップ追加（Leela Zero解析パイプライン拡張 v2）
  - **Phase 30**: 解析強度抽象化（Quick/Deep）+ `leela.fast_visits`設定追加
  - **Phase 31**: Leela→MoveEval変換（`leela_loss_est`フィールド新設）
  - **Phase 32**: 既存レポートのLeela対応（推定損失ラベル区別）
  - **Phase 33**: エンジン選択設定（`engine.analysis_engine`）
  - **Phase 34**: UIエンジン切替 + フォールバック診断メッセージ
  - **Phase 35**: Leelaカルテ統合
  - **Phase 36**: Leelaバッチ解析（オプション、Phase 35後いつでも可）
  - **Phase 37**: テスト強化（既存`--update-goldens`活用）
  - **Phase 38**: 安定化（エラーハンドリング強化 + コアモジュールテスト追加）
  - **Phase 39**: エンジン比較ビュー
  - **Phase 40**: PLAYモード
  - **設計原則（v2強化）**:
    - 単一エンジンレポート（KataGo/Leela混合禁止）
    - 既存EvalSnapshot/MoveEvalパイプライン再利用
    - テストは実エンジン不使用（mock/stub + golden）
    - ハードコードvisits値禁止（`leela.fast_visits`設定可能）
    - 損失セマンティクス明確化（`score_loss` vs `leela_loss_est`）
  - **Phase 41+へ延期**: 初心者UX、ドキュメント整備
  - ※ 2026-01-18: 旧Phase 38-39（ドキュメント整備/仕上げ）を再編。安定化を優先。
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
  - **Phase 29**: Diagnostics - 診断画面、Bug Report zip（サニタイズ付き） ✅ **完了**
  - **Phase 30**: 検証テンプレ導線 → Phase 30-39 Leela解析パイプラインに変更
  - **優先度**: S = 24,25,27,29 / A = 26,28
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
- 2026-01-17: Phase 27完了（Settings UIスケーラブル化）
  - PR #145: settings_export.py（Core層、22テスト）
  - PR #146: タブ別リセット機能
  - PR #147: Export/Import UI（tkinter filedialog）
  - PR #148: 設定検索（opacity-based filtering）
  - 新規: `katrain/common/settings_export.py`
  - 拡張: `katrain/gui/features/settings_popup.py`
- 2026-01-23: Phase 46完了（Meaning Tags System Core）
  - 新規: `katrain/core/analysis/meaning_tags/`パッケージ
    - `models.py`: MeaningTagId enum（str継承、12タグ）、MeaningTag dataclass（frozen）
    - `registry.py`: MEANING_TAG_REGISTRY（全12タグ定義、5つにLexiconアンカー）
    - `classifier.py`: 分類ヒューリスティクス（~500行）
    - `__init__.py`: 公開API + 閾値定数エクスポート
  - 分類ロジック:
    - 12タグ: missed_tesuji, overplay, slow_move, direction_error, shape_mistake,
      reading_failure, endgame_slip, connection_miss, capture_race_loss,
      life_death_error, territorial_loss, uncertain
    - 優先度ベース判定（CAPTURE_RACE_LOSS > LIFE_DEATH_ERROR > ...）
    - 早期リターン: pass/resign/unreliable/no_loss
  - ヘルパー関数: get_loss_value(), classify_gtp_move(), compute_move_distance(), is_endgame()
  - Lexiconアンカー解決: resolve_lexicon_anchor()（モックフレンドリー設計）
  - pytest "slow" マーカー登録（pyproject.toml）
  - テスト197件追加（93 classifier + 7 integration）
- 2026-01-23: Phase 47完了（Meaning Tags Integration）
  - 新規: `katrain/core/analysis/meaning_tags/integration.py`
    - `normalize_lang()`: 言語コード正規化（"jp" → "ja"）
    - `get_meaning_tag_label_safe()`: 安全なラベル取得（None対応）
    - `format_meaning_tag_with_definition()`: 30文字truncation付き表示
  - MoveEval拡張: `meaning_tag_id: Optional[str]`フィールド追加
  - batch/stats.py拡張:
    - `meaning_tags_by_player`統計追加
    - `build_player_summary()`に"Top 3 Mistake Types"セクション
  - karte_report.py拡張:
    - `lang`パラメータ追加（日本語/英語切替対応）
    - Important Moves tableに"MTag"列追加
    - JSON出力に`meaning_tag`オブジェクト追加
  - Python 3.9互換性修正（`float | None` → `Optional[float]`）
  - ゴールデンファイル更新（karte_sgf_*.golden）
  - テスト49件追加、総数1946件
- 2026-01-23: Phase 45完了（Lexicon Core Infrastructure）
  - 新規: `katrain/common/lexicon/`パッケージ（Kivy非依存）
    - `models.py`: frozen dataclass（LexiconEntry, DiagramInfo, AIPerspective）
    - `validation.py`: 2段階パイプライン（validate_entry_dict → build_entry_from_dict）
    - `store.py`: LexiconStoreクラス（スレッドセーフ、アトミックスナップショット）
    - `__init__.py`: 公開API + get_default_lexicon_path()
  - 完全イミュータブル設計: frozen=True + Tuple[str, ...]
  - 検索API: get(), get_by_title(), get_by_category(), get_by_level()
  - バリデーション: 必須フィールド、Level 3専用、参照ID、タイトル衝突
  - 環境変数: LEXICON_PATH でパスオーバーライド可能
  - 依存関係: PyYAML追加（pyproject.toml）
  - テスト111件追加、総数1665件
- 2026-01-21: Phase 44完了（Batch Analysis Fixes、PR #177）
  - Issue 1: 信頼性閾値の一貫性修正
    - `target_visits`パラメータを`extract_game_stats()`, `build_karte_report()`に追加
    - カウントと表示で同じ有効閾値（例: visits=100→threshold=90）を使用
  - Issue 2: バッチ完了チャイム
    - `tools/generate_chime.py`（Python標準ライブラリのみでWAV生成）
    - `katrain/sounds/complete_chime.wav`（A major chord、0.4秒）
    - `Theme.COMPLETION_CHIME_SOUND`定数追加
  - テスト7件追加、総数1554件
- 2026-01-17: Phase 26完了（レポート導線改善、PR #144）
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
- 2026-01-29: Phase 80-94追加（Analysis Intelligence + Beginner Experience）
  - Phase 80-87: Karte/Summaryの意味付け強化（Ownership差分、Complexity、Pattern等）
  - Phase 88-94: KataGoセットアップ救済、初心者向けヒント、Active Review
  - 未定セクション更新（Phase 8等をPhase 88-94に移動）
  - 詳細仕様書を `docs/future/` に追加
- 2025-12-30: Claude Code移行対応で整理、Phase 4.5完了を反映
- 2025-12-26: v0.1作成
