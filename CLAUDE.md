# CLAUDE.md - myKatrain PC版 開発ガイド

> このファイルはClaude Codeがプロジェクトを理解するための主要ドキュメントです。
> 補助ルールは `.claude/rules/` を参照してください。

---

## 1. プロジェクト概要

### 1.1 基本情報
- **プロジェクト名**: myKatrain（KaTrain fork）
- **技術スタック**: Python 3.9+ / Kivy（GUI）/ KataGo（解析エンジン）
- **リポジトリ**: `sentoku870/my-katrain-v1.17.0`
- **ローカルパス**: `D:\github\katrain-1.17.0`

### 1.2 目的（1文）
KataGo解析を元に「カルテ（Karte）」を生成し、LLM囲碁コーチングで的確な改善提案を引き出す。

### 1.3 現在のフェーズ
- **完了**: Phase 1-42B（解析基盤、カルテ、リファクタリング、Guardrails、SGF E2Eテスト、LLM Package Export、レポート導線改善、Settings UI拡張、Smart Kifu運用強化、Diagnostics、解析強度抽象化、Leela→MoveEval変換、レポートLeela対応、エンジン選択設定、UIエンジン切替、Leelaカルテ統合、Leelaバッチ解析、テスト強化、安定化、エンジン比較ビュー、PLAYモード、コード品質リファクタリング、Batch Core Package完成）
- **次**: Phase 42-C（Batch Import Tests + Cleanup）

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
- **コード変更**: 原則 Claude Code で実行（手動編集は最小限）
- **説明**: 専門用語は初出時に1-2文で定義
- **手順**: コピペで完結する具体的なコマンドを提示
- **確認**: 動作確認ポイントを明示

### 2.3 作業の快適さ優先順位
1. **最優先**: 自分だけで動作ロジック修正をしない
2. **可能**: GPT/Claude指示ありの最小修正（タイポ、数値調整）
3. **許容**: ファイル全体のコピペ差し替え
4. **避けたい**: 複数ファイルの整合性判断

---

## 3. 開発ルール（必須）

### 3.1 修正レベルの判定（簡易版）

| Lv | 規模 | 対応方法 |
|:--:|------|----------|
| 0 | 超軽微（コメント/文言） | Claude Code で直接修正 |
| 1 | 軽微（〜50行、1ファイル） | Claude Code で直接修正 |
| 2 | 中程度（〜100行、1-2ファイル） | Plan Mode → 承認 → 実行 |
| 3 | 複数ファイル（2-3ファイル） | Plan Mode + 段階的実行 |
| 4 | 大規模（4ファイル超） | 分割案を先に提示 |
| 5 | 根本変更 | 設計相談のみ（実装保留） |

詳細は `.claude/rules/01-correction-levels.md` を参照。

### 3.2 Git ワークフロー（簡易版）

```
code-change（コード修正を含む）:
  → ブランチ: feature/YYYY-MM-DD-<short-desc>
  → PR経由でmainにマージ

docs-only（ドキュメントのみ）:
  → main直接コミット可
```

詳細は `.claude/rules/02-git-workflow.md` を参照。

### 3.3 動作確認（必須）
- **起動確認**: `python -m katrain`
- **テスト**: `uv run pytest tests`
- **UTF-8強制**（PowerShell）: `$env:PYTHONUTF8 = "1"`

### 3.4 トークン削減ルール（必須）

Claude Codeは以下のルールに従って、効率的にファイルを読み取ること。

#### 原則
- **ファイル全体の読み込みを避ける**: 必要な部分のみを読み取る
- **Grep → Read パターン**: まず検索で場所を特定、次に範囲読み込み
- **段階的アプローチ**: 広範囲→狭範囲の順で絞り込む

#### 具体的な手順

**❌ 悪い例（トークン浪費）**:
```
User: "_save_export_settings メソッドを見せて"
Assistant: [__main__.py 全体を Read（3000行）]
```

**✅ 良い例（トークン削減）**:
```
User: "_save_export_settings メソッドを見せて"
Assistant:
  1. Grep で "_save_export_settings" を検索 → Line 153 で発見
  2. Read(file_path="katrain/__main__.py", offset=150, limit=20) で該当範囲のみ読み込み
```

#### パターン別の推奨手順

| 目的 | 手順 | 例 | 推奨範囲 |
|------|------|-----|----------|
| **関数定義の確認** | 1. Grep で検索<br>2. Read で**前後を含めて**読む | `def _save_export_settings` → 140-220行（前後30-40行含む） | **80-120行** |
| **クラス全体の把握** | 1. Grep でクラス定義検索<br>2. Read でクラス範囲+周辺 | `class KaTrainGui` → 100-300行（周辺含む） | **150-250行** |
| **特定機能の調査** | 1. Grep でキーワード検索<br>2. 候補を絞り込み<br>3. Read で関連箇所+コンテキスト | "export_settings" → 各箇所±40行 | **60-100行/箇所** |
| **エラー原因の特定** | 1. エラーメッセージでGrep<br>2. Read でスタックトレース周辺+依存 | `AttributeError` → 該当行±30行 | **60-80行** |
| **全体構造の理解** | 1. Glob でファイル一覧<br>2. 主要ファイルのみ Read | `**/*.py` → __init__.py, game.py など | **全体でOK** |
| **小さいファイル** | Grep せず直接 Read | ファイル全体が500行未満 | **全体読み込み** |

#### 重要: 緩めな削減を推奨

**エラーを減らすための原則**:
- ✅ **前後のコンテキストを含める**: 関数定義だけでなく、その前後30-40行を読む
- ✅ **依存関係を確認**: インポート文や親クラスも確認
- ✅ **段階的に範囲を広げる**: 不明点があれば追加で読む
- ✅ **小さいファイルは全体読み**: 500行未満のファイルはGrep不要

**トークン削減目標**:
- 厳格（96%削減）ではなく、**緩め（70-80%削減）** を目指す
- エラーリスクを大幅に下げつつ、十分なトークン削減効果を得る

#### Grep 活用のコツ

```python
# パターン1: 関数定義検索
Grep(pattern="def _save_export_settings", path="katrain", type="py")

# パターン2: クラス定義検索
Grep(pattern="class KaTrainGui", path="katrain", type="py")

# パターン3: 変数使用箇所検索
Grep(pattern="export_settings", path="katrain/__main__.py", output_mode="content", -n=True)

# パターン4: インポート文検索
Grep(pattern="^import |^from .* import", path="katrain/core", type="py")
```

#### Read 範囲指定のコツ

```python
# 関数定義を読む（開始行が分かっている場合）
Read(file_path="katrain/__main__.py", offset=153, limit=15)  # 15行程度で十分

# クラス定義を読む
Read(file_path="katrain/__main__.py", offset=121, limit=80)  # クラス全体

# エラー周辺を読む（スタックトレースから）
Read(file_path="katrain/__main__.py", offset=160, limit=10)  # エラー行±5行
```

#### 効果測定

| 手法 | トークン消費 | 削減率 |
|------|------------|--------|
| ファイル全体読み込み（3000行） | ~12,000 tokens | - |
| Grep + 範囲Read（30行） | ~500 tokens | 96% 削減（厳格すぎ） |
| Grep + 範囲Read（100行） | ~1,500 tokens | 87% 削減 |
| **Grep + 範囲Read（150行）** | **~2,500 tokens** | **79% 削減（推奨）** |
| Grep + 範囲Read（200行） | ~3,200 tokens | 73% 削減 |

#### 例外ケース（全体読み込みが必要な場合）

- **初回の全体把握**: 新しいファイルの構造を理解する場合
- **リファクタリング**: ファイル全体の整合性が必要な場合
- **小さなファイル**: 100行未満のファイル

この場合でも、まず Glob でファイルサイズを確認してから判断すること。

---

## 4. コード構造（概要）

```
katrain/
├── __main__.py      ← アプリ起動、KaTrainGui クラス（~1200行）
├── common/          ← 共有定数（循環依存解消用）
│   ├── platform.py     ← get_platform()（Kivy非依存OS判定）
│   └── config_store.py ← JsonFileConfigStore（Mapping実装）
├── core/
│   ├── game.py       ← Game クラス（対局状態）
│   ├── game_node.py  ← GameNode（手/解析結果）
│   ├── engine.py     ← KataGoEngine（解析プロセス）
│   ├── lang.py       ← Lang クラス（Kivy非依存、コールバックベース）
│   ├── eval_metrics.py ← ファサード（後方互換用、実体は analysis/）
│   ├── analysis/     ← 解析基盤パッケージ
│   │   ├── models.py    ← Enum, Dataclass, 定数
│   │   ├── logic.py     ← 計算関数
│   │   └── presentation.py ← 表示/フォーマット
│   └── batch/        ← バッチ処理パッケージ（Phase 42）
│       ├── models.py       ← WriteError, BatchResult
│       ├── helpers.py      ← 純粋関数（Kivy非依存）
│       ├── analysis.py     ← analyze_single_file, analyze_single_file_leela
│       ├── orchestration.py ← run_batch() メインエントリ
│       └── stats.py        ← 統計抽出、サマリ生成
├── gui/
│   ├── controlspanel.py ← 右パネル
│   ├── badukpan.py      ← 盤面表示
│   ├── lang_bridge.py   ← KivyLangBridge（i18n Kivyブリッジ）
│   ├── widgets/
│   │   └── graph.py     ← ScoreGraph
│   └── features/        ← 機能モジュール（__main__.pyから抽出）
│       ├── context.py       ← FeatureContext Protocol
│       ├── karte_export.py  ← カルテエクスポート
│       ├── summary_*.py     ← サマリ関連（stats/aggregator/formatter/ui/io）
│       ├── quiz_*.py        ← クイズ（popup/session）
│       ├── batch_*.py       ← バッチ解析（core/ui）
│       └── settings_popup.py ← 設定ポップアップ
├── gui.kv            ← Kivy レイアウト定義
└── i18n/             ← 翻訳ファイル
```

### データフロー
```
KataGo(JSON) → KataGoEngine → GameNode.set_analysis()
           → KaTrainGui.update_state() → UI更新
```

詳細は `docs/02-code-structure.md` を参照。

### ロック設計ガイドライン（engine.py）

KataGoEngine はマルチスレッドで動作するため、デッドロック防止のルールを定義。

| ルール | 説明 |
|--------|------|
| `*_unlocked()` サフィックス | 呼び出し元がロックを保持している前提 |
| ロック内でコールバック/停止操作を呼ばない | 例: `stop_pondering()` はロック外で呼ぶ |
| 長時間操作はロック外 | I/O, sleep, 外部呼び出しをロック内で行わない |

**例**: `_stop_pondering_unlocked()` (PR #101 で追加)
- 検索: `Select-String -Path katrain\core\engine.py -Pattern "_stop_pondering_unlocked"`

**関連**: `daemon=True` スレッドはメインプロセス終了時に自動終了するため、アプリ終了時のスレッド join はスキップ可能。

### フォールバックポリシー（Phase 36）

| 文脈 | Leela選択時の動作 | 根拠 |
|------|------------------|------|
| **Settings UI保存** | 警告表示（STATUS_INFO）＋保存続行 | 後で有効化する可能性 |
| **Batch開始** | 即座にエラー＋中断（`is_alive()=False`時） | 長時間処理の無駄を防ぐ |
| **Export Karte** | 呼び出し元でチェック | エクスポート時は既にエンジン選択済み |
| **Config読み込み** | KataGoにフォールバック＋警告ログ | 起動時クラッシュ防止 |

### バッチLeela visits仕様（Phase 36 MVP）

1. `analysis_engine="leela"` 選択時:
   - `visits = resolve_visits(AnalysisStrength.QUICK, katrain.config("leela"), "leela")`
   - UIの `visits_input` フィールドは無視される

2. UIの振る舞い:
   - Leela選択時: `visits_input` を disabled 表示または "[設定値を使用]" と表示
   - 警告ラベル: "Leelaはleela.fast_visitsを使用します"

### 混合エンジン検出仕様（Phase 37）

判定ロジック:
```python
has_katago = any(m.score_loss is not None for m in moves)
has_leela = any(m.leela_loss_est is not None for m in moves)
is_mixed = has_katago and has_leela
```

許容パターン:
- 全手KataGo（`score_loss`設定）→ OK
- 全手Leela（`leela_loss_est`設定）→ OK
- 全手データなし（両方None）→ OK（未解析）
- 一部解析済み＋一部未解析 → OK（部分解析）
- 1手でもKataGo + 1手でもLeela → NG（`MixedEngineSnapshotError`）

エンフォースメントポイント:
- `build_karte_report()` 冒頭でのみチェック
- `EvalSnapshot`作成時はチェックしない（パフォーマンス考慮）

---

## 5. 囲碁ドメイン（参照）

### 5.1 棋力レベル定義
| ラベル | 目安 | 説明 |
|:------:|------|------|
| G0 | 〜10級 | ルール〜基本死活 |
| G1 | 5〜1級 | 一般級位者 |
| G2 | 初段〜二段 | 基本形理解あり |
| G3 | 三〜四段 | 戦い強いがムラあり |
| G4 | 五段相当 | ユーザー本人 |

### 5.2 解説レベル定義
| ラベル | 説明 |
|:------:|------|
| A | 方向性だけ伝えるヒント |
| B | 石の役割・構図まで触れる |
| C | プロ並みの構想説明（重い） |
| D | KataGo並みの詳細（非現実的） |

詳細は `.claude/rules/04-go-domain.md` を参照。

---

## 6. 技術選定の判断基準（4軸）

新機能/設計変更時は以下で判断：

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

---

## 9. ドキュメント配置

```
docs/
├── 00-purpose-and-scope.md  ← 目的とスコープ（固定）
├── 01-roadmap.md            ← ロードマップ（更新可）
└── 02-code-structure.md     ← コード構造（参照）

.claude/rules/
├── 01-correction-levels.md  ← 修正レベル詳細
├── 02-git-workflow.md       ← Git操作詳細
├── 03-debug-workflow.md     ← デバッグ手順
└── 04-go-domain.md          ← 囲碁ドメイン詳細
```

---

## 10. 変更履歴

- 2026-01-20: Phase 42-B 完了（Batch Orchestration移行）
  - 新規: `katrain/core/batch/analysis.py`（~394行、analyze_single_file, analyze_single_file_leela）
  - 新規: `katrain/core/batch/orchestration.py`（~439行、run_batch）
  - 新規: `katrain/core/batch/stats.py`（~961行、extract_game_stats, build_player_summary等）
  - 拡張: `__init__.py`にlazy `__getattr__`追加（重量モジュールの遅延インポート）
  - 軽量化: tools/batch_analyze_sgf.py（~1900行→~240行、CLI + 再エクスポートのみ）
  - 更新: gui/features/batch_core.py, batch_ui.pyのインポート先変更
  - テスト総数: 1492件
- 2026-01-20: Phase 42-A 完了（Batch Core移行）
  - 新規: `katrain/core/batch/`パッケージ（Kivy非依存）
  - models.py: WriteError, BatchResult dataclass
  - helpers.py: 純粋関数15種（choose_visits_for_sgf, safe_int, needs_leela_karte_warning等）
  - 後方互換: tools/batch_analyze_sgf.pyから再エクスポート
  - アーキテクチャテスト: test_batch_does_not_import_kivy()追加
  - テスト総数: 1492件
- 2026-01-20: Phase 41 完了（コード品質リファクタリング）
  - Phase 41-A: `AnalysisMode(str, Enum)` + `parse_analysis_mode()`関数（constants.py）
  - Phase 41-B: コマンドハンドラ抽出（gui/features/commands/パッケージ新設）
  - Phase 41-C: 例外ハンドリング改善（`# noqa: BLE001`、OUTPUT_ERROR統一）
  - Phase 41-D: Magic Number定数化（AI_ACCURACY_DECAY_BASE等3定数）
  - テスト14件追加（test_analysis_mode.py）
  - テスト総数: 1491件
- 2026-01-19: Phase 40 完了（Leela Zero対戦機能）
  - AI_LEELA定数追加（constants.py）、AI_STRATEGIES/RECOMMENDED_ORDER/STRENGTH統合
  - LeelaStrategy + LeelaNotAvailableError実装（ai.py、~90行）
  - config.json: `ai:leela: {}`と`leela.play_visits: 500`追加
  - __main__.py: LeelaNotAvailableErrorキャッチ＋ステータスバー表示
  - settings_popup.py: Play Visits UI追加
  - i18n: EN/JP翻訳追加（10キー）
  - テスト14件（test_leela_strategy.py）
  - テスト総数: 1477件
- 2026-01-19: Phase 39 完了（エンジン比較ビュー）
  - PR-1: `katrain/core/analysis/engine_compare.py`（~400行）
    - `ComparisonWarning` enum、`MoveComparison`/`EngineStats`/`EngineComparisonResult` dataclass
    - `build_comparison_from_game()` 関数
    - `compute_spearman_manual()` 手動Spearman相関（scipy不使用）
  - PR-1: テスト38件（test_engine_compare.py）
  - PR-2: `katrain/gui/features/engine_compare_popup.py`（~660行）
    - タブ切替UI（手別比較 / 統計サマリー）
    - ScrollView固定 + 乖離フィルタ（デフォルトON）
    - 行クリックで該当手にジャンプ
  - PR-2: MyKatrainメニューに「エンジン比較」項目追加
  - PR-2: i18n 35+キー追加（en/jp）
  - テスト総数: 1463件
- 2026-01-18: Phase 38 完了（安定化）
  - PR-1: `_safe_int()` ヘルパー関数（batch_core.py、サイレントデフォルト処理）
  - PR-1: `save_manifest()`, `save_player_profile()` にtry-except追加（io.py）
  - PR-1: `BaseEngine.on_error` のprint()削除、サブクラスでオーバーライド
  - PR-1: `_stderr_thread` のprint()をkatrain.log()に変更（engine.py）
  - PR-1: shutdown例外にOUTPUT_EXTRA_DEBUGログ追加（engine.py）
  - PR-1: `extract_analysis_from_sgf_node()` 例外具体化 + binasciiインポート（summary_stats.py）
  - PR-1: テスト8件（test_batch_validation.py）
  - PR-2: Game初期化/playテスト9件（test_game_core.py、test_board.pyパターン踏襲）
  - テスト総数: 1425件
- 2026-01-18: Phase 37 完了（テスト強化）
  - PR-2: `MixedEngineSnapshotError` 専用例外導入（karte_report.py）
  - PR-2: `KARTE_ERROR_CODE_*` エラーコード定数導入
  - PR-2: `is_single_engine_snapshot()` 混合エンジン検出関数
  - PR-2: `needs_leela_karte_warning()` 純粋関数（batch_core.py）
  - PR-2: T1混合エンジン防止テスト（test_mixed_engine_guard.py、17件）
  - PR-2: T2 Leela+karte警告テスト（test_batch_engine_option.py拡張）
  - PR-2: T3 resolve_visits契約テスト（定数参照、test_analysis_strength.py）
  - PR-2: T4 config fallback契約テスト（test_analysis_engine_config.py）
  - PR-3: T6 Leelaゴールデンテスト（test_golden_karte.py、3件）
  - PR-3: ゴールデンファイル（karte_leela_standard.golden）
  - PR-3: UI visits_input disabled（Leela選択時、batch_ui.py）
  - テスト総数: 1408件
- 2026-01-18: Phase 36 完了（Leelaバッチ解析）
  - PR-2: `analyze_single_file_leela()` per-move解析関数（~180行）
  - PR-2: `run_batch()` 拡張（analysis_engine, leela_engine, per_move_timeout）
  - PR-2: エンジン検証（バッチ開始時Leela aliveチェック）
  - PR-2: テスト13件（test_batch_leela_analysis.py）
  - PR-1: `LeelaEngine.is_idle()` メソッド（スレッドセーフ）
  - PR-1: `cancel_analysis()` ロック保護
  - PR-1: Batch UIエンジン選択行（KataGo/Leela切替）
  - PR-1: `collect_batch_options()` に `analysis_engine` 追加
  - PR-1: i18n 5キー追加
  - PR-1: テスト22件（test_leela_engine_idle.py, test_batch_engine_option.py）
  - 制限: Leelaカルテ生成は未対応（Phase 36 MVP）
- 2026-01-18: Phase 35 完了（Leelaカルテ統合）
  - 新規: `has_loss_data()` 関数（MoveEvalに損失データが存在するか判定）
  - 新規: `format_loss_with_engine_suffix()` 関数（Leelaは「(推定)」サフィックス付き）
  - 拡張: `worst_move_for()` がLeela対応（has_loss_data()ベースで0.0も候補に含む）
  - 拡張: `summary_lines_for()`, `opponent_summary_for()` のworst move表示
  - 拡張: Important Moves table の Loss 列にエンジンサフィックス
  - テスト: 21件（test_karte_leela_integration.py）
- 2026-01-18: Phase 33 完了（エンジン選択設定）
  - 新規: `VALID_ANALYSIS_ENGINES: FrozenSet[str]`（EngineTypeから派生、UNKNOWN除外）
  - 新規: `DEFAULT_ANALYSIS_ENGINE` 定数（"katago"）
  - 新規: `get_analysis_engine()` 関数（unhashable型ガード付き）
  - 設定: `engine.analysis_engine` キー追加
  - テスト: 30件（test_analysis_engine_config.py）
- 2026-01-18: Phase 32 完了（レポートLeela対応）
  - 新規: `EngineType` enum（KATAGO/LEELA/UNKNOWN）
  - 新規: `detect_engine_type()` 関数（MoveEvalからエンジン種別推定）
  - 拡張: `get_canonical_loss_from_move()` にleela_loss_est対応+全クランプ
  - 新規: `format_loss_label()` 関数（エンジン種別ラベルフォーマット）
  - 更新: `format_evidence_examples()`, `karte_report.py` Leela対応
  - テスト: 35件（test_engine_type_labels.py）
- 2026-01-18: Phase 31 完了（Leela→MoveEval変換）
  - 新規: `katrain/core/leela/conversion.py`（変換モジュール、~280行）
  - 新規: `MoveEval.leela_loss_est` フィールド（Leela Zero推定損失）
  - 機能: `leela_position_to_move_eval()` 単一手変換
  - 機能: `leela_sequence_to_eval_snapshot()` シーケンス変換（検証付き）
  - 機能: Winrate視点変換（side-to-move → black perspective）
  - テスト: 36件（test_leela_conversion.py）
- 2026-01-18: Phase 30 完了（解析強度抽象化）
  - 新規: `AnalysisStrength` enum（QUICK/DEEP、エンジン共通抽象）
  - 新規: `ENGINE_VISITS_DEFAULTS` 定数（KataGo/Leela別デフォルト値）
  - 新規: `resolve_visits()` 関数（防御的パース、フォールバック付き）
  - 新規: `LEELA_FAST_VISITS_MIN` 定数（UI最小値 50）
  - 設定: `leela.fast_visits` 追加（デフォルト 200）
  - UI: Settings > Leela > Fast Visits 入力欄追加（clampバリデーション付き）
  - テスト: 28件（test_analysis_strength.py）
- 2026-01-17: Phase 29 完了（Diagnostics + Bug Report Bundle）
  - 新規: `common/sanitize.py`（パス/テキストサニタイズ、Kivy非依存）
  - 新規: `core/log_buffer.py`（スレッドセーフな循環ログバッファ）
  - 新規: `core/diagnostics.py`（システム情報収集、ZIP生成）
  - 新規: `gui/features/diagnostics_popup.py`（診断ポップアップUI）
  - 機能: MyKatrain メニュー → Diagnostics で診断画面表示
  - 機能: Bug Report ZIP生成（プライバシー保護付き）
  - テスト: 71件（test_sanitize.py, test_log_buffer.py, test_diagnostics.py）
- 2026-01-17: Phase 28 完了（Smart Kifu運用強化）
  - 新規: `ImportErrorCode` enum（文字列マッチング脆弱性を解消）
  - 新規: `TrainingSetSummary` dataclass（サマリー計算）
  - 拡張: `import_sgf_to_training_set()` に `compute_ratio` オプション追加
  - 新規: `import_analyzed_sgf_folder()` バッチ出力フォルダのインポート
  - 機能: Training Set Manager に解析率表示（色分け付き）
  - 機能: バッチインポートダイアログ（`show_import_batch_output_dialog()`）
  - テスト: 36件（test_smart_kifu_analyzed_ratio.py, test_smart_kifu_import.py）
- 2026-01-17: Phase 27 完了（Settings UIスケーラブル化）
  - 新規: `common/settings_export.py`（Export/Import/Resetロジック、Kivy非依存）
  - 拡張: `gui/features/settings_popup.py`（検索バー、Export/Import/Resetボタン）
  - 機能: 設定検索、設定Export/Import（JSON）、タブ別リセット
  - テスト: 22件（test_settings_export.py）
- 2026-01-17: Phase 26 完了（レポート導線改善）
  - 新規: `common/file_opener.py`（クロスプラットフォームファイル/フォルダオープナー）
  - 新規: `gui/features/report_navigator.py`（レポート導線UI）
  - 機能: 「最新レポートを開く」「出力フォルダを開く」メニュー項目
- 2026-01-17: Phase 24 完了（SGF E2E Regression Tests）
  - 新規: `tests/helpers/` パッケージ（mock_analysis.py, stats_extraction.py）
  - 拡張: `tests/conftest.py`（CI検出、改行正規化）
  - 追加: TestKarteFromSGF, TestSummaryFromSGF（3 SGFファイル対応）
- 2026-01-16: Phase 20 完了、コード構造更新
  - core層のKivy依存を大幅削減（許可リスト6→1エントリ）
  - 新規: `common/platform.py`, `common/config_store.py`, `gui/lang_bridge.py`
  - 変更: `core/lang.py`（Observable→コールバックベース）
- 2025-12-30: v1.0 作成（Claude Code移行対応）
