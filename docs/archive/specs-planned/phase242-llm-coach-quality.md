# Phase 242 — LLM Coach 品質改善 統合実装スペック

> **作成日**: 2026-07-17
> **ステータス**: 実装中
> **起源**: ユーザー依頼「LLMコーチに関して問題点や改善点がないか詳しく調査して教えて下さい」の調査結果 (`docs/ideas/phase242-llm-coach-audit.md`) に基づく統合改修
> **Lv**: 3 (機能横断的な品質改善、popup Pure 化を含む)

## 1. 背景

`docs/ideas/phase242-llm-coach-audit.md` の調査で、LLM Coach 機能に **40 件以上の問題・改善余地** が発見された。本スペックはそれらのうち優先度の高いものを 5 つのサブフェーズに統合し、1 PR で対応する。

各サブフェーズは独立した commit に分割し、レビューとロールバックを容易にする。

## 2. サブフェーズ構成

| ID | タイトル | 優先度 | Lv | 推定規模 | サブコミット数 |
|----|---------|--------|----|----------|------------|
| 242-A | Kansai 辞書同期 + マーカー拡張 | 高 | 1 | 6 ファイル + 6 unit tests | 1 |
| 242-B | popup UI 改善 (定数化 + truncation/pe/schema-version/loading) | 高 | 2 | 5 ファイル + 12 unit tests | 1 |
| 242-C | 9 症状への Lexicon 紐付け追加 | 高 | 2 | 3 ファイル + 11 unit tests | 1 |
| 242-D | 検証レンダラ統合 (karte/summary 共通化) | 中 | 2 | 3 ファイル + 6 unit tests | 1 |
| 242-E | popup Pure ロジック抽出 + headless テスト可能化 | 高 | 3 | 4 ファイル + 30 unit tests | 1 |

## 3. サブフェーズ詳細

### 242-A: Kansai 辞書同期 + マーカー拡張

**問題**:
- `master_db._KANSAI_DICTIONARY` (12 エントリ) と `tones._KANSAI_NORMALISATION_PAIRS` (13 エントリ) と `tones._AYAKA_MARKERS` (16 エントリ) が完全には同期していない
- Phase 226-E E4 で「同期契約」と docstring に明記したが、実態は 31 箇所の乖離
- 特に `ほんまに` が pair destination だが markers に未登録 → `has_kansai_markers()` が AYAKA 文体を検知できない

**修正内容**:
1. `master_db._KANSAI_DICTIONARY` に不足している `〜やで/〜やねん` 等のターゲットに相当する marker を `_AYAKA_MARKERS` に追加
2. `〜...` プレフィックス付きパターンを `_KANSAI_NORMALISATION_PAIRS` に展開
3. `だめ` (小文字) を `ダメ` (大文字) に統一 (現状は両方がペアにある)
4. `ほんまに` を `_AYAKA_MARKERS` に追加
5. 3 系統間の整合性チェック用 unit test を追加

**変更ファイル**:
- `katrain/core/coach/tones.py` (markers 拡張)
- `katrain/core/coach/master_db.py` (KANSAI_DICTIONARY 拡張)
- `tests/test_coach_tones.py` (同期チェックテスト追加)
- `tests/test_coach_master_db.py` (同期チェックテスト追加)
- `docs/archive/specs-implemented/phase242-llm-coach-quality.md` (この spec)
- 必要に応じて `docs/resources/go_lexicon_master_last.yaml`

**テスト計画**:
- `_KANSAI_DICTIONARY` の値 ⊆ `_KANSAI_NORMALISATION_PAIRS` の値
- `_KANSAI_NORMALISATION_PAIRS` の値 ⊆ `_AYAKA_MARKERS` ∪ 既存マーカー
- `apply_kansai_normalisation` 後のテキストに `has_kansai_markers` が True を返す
- `ほんまに` が出力された場合に `has_kansai_markers` が True

### 242-B: popup UI 改善

**問題** (Phase 242 監査で発見):
- `perspective_value` の StringProperty デフォルト `"auto"` と実使用値 `""` の不整合
- 検証レポート 20,000 文字 truncation 時に status_label 警告なし
- response_input への巨大ペースト対策なし
- popup 上部に schema version 表示なし
- validate 中のローディング表示なし
- spinner テキストと内部値のマッピングが i18n 経由のためロケール変更に脆弱

**修正内容**:
1. `_PERSPECTIVE_AUTO_INTERNAL` 定数化 (値は `"auto"` 維持)
2. truncation 時に status_label に「⚠ 結果 N 文字省略、原本を確認してください」表示
3. response_input ペースト時に `_MAX_RESPONSE_CHARS = 100_000` で打ち切り
4. popup 上部に schema_version を表示 (small label)
5. validate ボタン押下時に `disabled: True` + 0.5s 後に解除
6. `_spinner_text_to_internal` を静的マッピング table 化 (i18n 変更耐性)

**変更ファイル**:
- `katrain/gui/popups/llm_coach_popup.py` (定数 + truncate 警告 + paste 制限)
- `katrain/gui/kv/llm_coach_popup.kv` (schema version label + loading indicator)
- `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` (新 i18n キー)
- `katrain/i18n/locales/en/LC_MESSAGES/katrain.po`
- `tests/test_llm_coach_popup.py` (新挙動テスト追加)

**新 i18n キー**:
- `mykatrain:llm-coach:truncation-warning` ("⚠ 結果 N 文字省略")
- `mykatrain:llm-coach:paste-too-long` ("LLM 応答が長すぎます (N 文字)、N 文字で打ち切りました")
- `mykatrain:llm-coach:schema-version` ("Schema: X.Y")

### 242-C: 9 症状への Lexicon 紐付け追加

**問題**:
- Phase 226-J で 5 つの auto-detected 症状に lexicon ID を追加したが、9 つの LLM-required 症状には未対応
- 該当: `time_pressure_loss` / `time_misallocation` / `time_drain` / `shallow_review` / `ai_overload` / `copy_without_understanding` / `tilt_discouragement` / `tilt_chain` / `tilt_emotional_interference`
- 影響: プロンプトに Lexicon エントリが注入されない → LLM が標準語彙なしで解説する

**修正内容**:
1. `docs/resources/go_lexicon_master_last.yaml` に新規 Lexicon エントリを追加 (慎重に — AGENTS.md マーカー)
2. `katrain/core/coach/symptom_index.py` の `_SYMPTOMS` で `related_lexicon_ids` を更新
3. `tests/test_coach_symptom_index.py` に Lexicon 紐付けテスト追加

**追加 Lexicon エントリ案**:
| ID | ja_term | level | category | 紐付け対象症状 |
|----|---------|-------|----------|----------------|
| `time_management` | 時間管理 | 2 | misc | time_* |
| `ai_overload` | AI 情報過多 | 2 | misc | ai_overload, copy_without_understanding, shallow_review |
| `tilt_recovery` | ティルト回復 | 2 | misc | tilt_* |
| `post_game_review` | 対局後検討 | 2 | misc | shallow_review |
| `mental_state` | 精神状態 | 2 | misc | tilt_* |

**変更ファイル**:
- `docs/resources/go_lexicon_master_last.yaml` (Lexicon 拡張 — 慎重に)
- `katrain/core/coach/symptom_index.py` (related_lexicon_ids 設定)
- `tests/test_coach_symptom_index.py` (Lexicon 紐付けテスト)
- `tests/test_coach_lexicon.py` (新規エントリ整合性テスト)

### 242-D: 検証レンダラ統合

**問題**:
- `_render_validation_report` (karte, `features/llm_coach.py`) と `_render_summary_validation_report` (summary, 同上) で重複コード多数
- severity 集計 / issues リスト / referenced items のレンダリングが同様

**修正内容**:
1. 共通基底レンダラ `_render_validation_report_core` を `core/coach/llm_report_renderer.py` に新設
2. karte / summary 別のカスタマイズポイントのみ残す
3. 統合レンダラを features 層から呼び出す

**変更ファイル**:
- `katrain/core/coach/llm_report_renderer.py` (新規 — 共通基底)
- `katrain/gui/features/llm_coach.py` (既存 2 関数を基底呼び出しに置換)
- `tests/test_coach_llm_report_renderer.py` (新規テスト)

**設計**:
- 関数 `_render_validation_report_core(report, *, title_prefix: str, extra_meta: dict | None = None) -> str`
- karte: `title_prefix=""`, `extra_meta=None`
- summary: `title_prefix="summary"`, `extra_meta={"games": N, "focus": "..."}`

### 242-E: popup Pure ロジック抽出 + headless テスト可能化

**問題** (Phase 242 監査の A-1):
- popup テスト 96 件中 94 件が headless 環境で `SystemExit: 1` で失敗
- 原因: KivyMD の `dp(400)` 呼び出しがモジュールロード時に Window を要求
- Phase 241-H で `conftest.py` に環境変数を設定したが Windows + 開発環境では不十分

**修正内容**:
1. popup の主要ロジック (`_populate_rank_and_perspective` / `_populate_summary_perspective` / `_detect_path_type` / `_resolve_player_color` / `_summary_index_to_internal` / `is_summary_birdseye`) を Pure 関数として `core/coach/popup_logic.py` に移植
2. popup 側は `self.karte_path_input` 等の Kivy 依存を Pure 関数の引数として渡す薄いラッパーに
3. popup ロジックの headless テストを `tests/test_coach_popup_logic.py` に追加
4. 既存の `test_llm_coach_popup.py` の重い popup テストは残しつつ、headless ロジックは新ファイルで完全にカバー

**変更ファイル**:
- `katrain/core/coach/popup_logic.py` (新規 — Pure ロジック)
- `katrain/gui/popups/llm_coach_popup.py` (Pure ロジック呼び出しに置換)
- `tests/test_coach_popup_logic.py` (新規 — headless テスト)
- `tests/test_llm_coach_popup.py` (必要に応じて整理)

**Pure ロジック API**:
- `resolve_summary_spinner_values(players: list[tuple[str, str | None]]) -> tuple[list[str], int, int]`
- `resolve_player_color_internal(perspective_value: str, detected: str | None) -> str | None`
- `is_summary_birdseye_value(value: str | None) -> bool`
- `detect_path_type_from_file(path: str) -> str` (UI 非依存)
- `format_validation_issue_counts(high: int, medium: int, low: int) -> str`

## 4. 影響範囲

| 領域 | 影響 |
|------|------|
| GUI | popup の表示改善 + spinner ロジック強化 |
| Core | Kansai 同期 + 症状 lexicon 紐付け + Pure ロジック層新設 |
| i18n | 3 キー追加 (242-B) |
| Tests | 95+ unit tests 追加 / popup テスト 94 件が headless で通る可能性 |
| ドキュメント | AGENTS.md / 01-roadmap.md 更新 |

## 5. 後方互換性

- 既存の config / JSON シェーマは変更なし
- 既存テストは全合格を維持
- 新しい Lexicon エントリ追加は症状 lexicon リストを空タプル → 1-3 個に拡張のみ (後方互換)
- 新しい i18n キーは popup のみで使用、翻訳未対応の言語ではキー名がそのまま表示されるが、既存パターンと同じ

## 6. リスク

| リスク | 緩和策 |
|--------|--------|
| Lexicon YAML 拡張が既存テストを破壊 | 既存テストの fixture を確認の上で段階的に追加 |
| popup ロジック Pure 化で挙動変化 | 既存 popup テストを修正前に全合格させてから着手 |
| 5 サブフェーズ同時 PR でコンフリクト | 各サブフェーズを独立 commit に分離 |
| Kansai 同期で AYAKA 文体判定の挙動変化 | AYAKA 文体テストを全合格させてから着手 |

## 7. 完了基準

- [ ] 全 5 サブフェーズの実装完了
- [ ] 既存テスト全合格維持
- [ ] 新規 unit tests 65+ 件追加、全合格
- [ ] i18n .po / .mo 同期
- [ ] AGENTS.md / 01-roadmap.md 更新
- [ ] CI lint 通過 (ruff, mypy)
