# Phase 269 — AYAKA 完全削除 + 弱点抽出整合性修正 + voice 統一

> 実装日: 2026-07-18 / Lv3 / 1PR (4 コミット) / 11 ファイル変更 / 28 新規 unit tests
> 動機: ユーザー報告「5k とかに設定すると関西弁・親しみ・実利重視とかなるので全棋力同じキャラというか好き嫌いが分かれるので統一させたいです」

## 概要

LLM Coach 機能で 2 つの問題を統合的に解消:

1. **弱点抽出整合性の修正 (C 案)**: 複数局サマリ (Shape B) で弱点パターンに
   付いていた `phase="all"` メタタグが LLM 出力の contract line にそのまま
   反映され、validator が `phase_label_out_of_set` MEDIUM 警告を出していた
   問題を恒久的に解消。
2. **AYAKA 完全削除 + voice 統一**: `ToneVoice.AYAKA` enum 値と関連する
   関西弁処理データ・関数を全て削除し、Beginner/Intermediate でも TOMOKO
   (標準語・論理・構造重視) キャラが選択されるように統一。ユーザー要望
   「全棋力同じキャラに統一」を実現。

## サブフェーズ

### C 案-1: `phase="all"` → `"(全phase)"` 表示修正

- 対象ファイル: `katrain/core/coach/summary_prompt_builder.py`
- 変更内容: `_format_patterns_block` で `phase` 値が `"all"` の場合に
  表示を `phase=`(全phase)``` に置換。LLM がこの表示を phase 値では
  なく説明文と認識し、contract line では `{opening, middle, endgame}`
  のいずれかを別途選んで参照するようになる。

### C 案-2: SYSTEM_INSTRUCTION の `frequency_ratio` 指示を `pct` 併記に

- 対象ファイル: `katrain/core/coach/summary_prompt_builder.py`
- 変更内容: システム指示内の「頻度 (X / N局, X%) — use the injected
  ``frequency_ratio`` field」を「use the injected ``pct`` field when
  the pre-computed pattern shows ``phase=`(全phase)```」に書き換え。
  Shape B 経路では `frequency_ratio` が常に 0 で機能しないため、
  `pct` (per-move percentage) を主軸にする旨を明示。

### mode 統一: BEGINNER/INTERMEDIATE voice → TOMOKO

- 対象ファイル: `katrain/core/coach/master_db.py`
- 変更内容: `_MODE_TABLE` の BEGINNER (30k〜11k) と INTERMEDIATE
  (10k〜5k) の `voice` フィールドを `ToneVoice.AYAKA` → `ToneVoice.TOMOKO`
  に変更。`5k` 設定時に AYAKA 関西弁キャラが選ばれていた挙動を解消。

### AYAKA 完全削除

削除対象:

1. **enum 値**: `ToneVoice.AYAKA`
2. **テーブルエントリ**: `_TONE_TABLE` の先頭 AYAKA エントリ
3. **データ構造**:
   - `master_db._KANSAI_DICTIONARY` (16 エントリ)
   - `tones._AYAKA_MARKERS` (16 マーカー)
   - `tones._KANSAI_NORMALISATION_PAIRS` (15 ペア)
4. **ToneConfig フィールド**: `kansai_dictionary`
5. **公開 API 関数**:
   - `has_kansai_markers(text)` → bool
   - `is_kansai_marker(text)` → bool
   - `apply_kansai_normalisation(text, mapping=None)` → str
6. **voice_summary エントリ**: AYAKA 用サマリ削除
7. **greeting テンプレ**: BEGINNER / INTERMEDIATE 用関西弁調テンプレを
   TOMOKO 調 (標準語) に書き換え
8. **tone 整合性チェック**:
   - `llm_validator.py`: AYAKA-tone / TOMOKO-tone 不整合検出削除
   - `summary_validator.py`: 同上
9. **__init__.py exports**: `apply_kansai_normalisation`,
   `has_kansai_markers` 削除
10. **check_prohibited の AYAKA-tone 専用分岐** (敬語/丁寧語混入検出) 削除

## 影響範囲

### コード変更 (5 ファイル)

- `katrain/core/coach/master_db.py` (ModeConfig voice 2 件 + ToneVoice
  enum + _TONE_TABLE + ToneConfig フィールド + 関西弁データ全削除)
- `katrain/core/coach/tones.py` (全面書き換え: AYAKA helpers 削除 +
  greeting テンプレ TOMOKO 化 + check_prohibited 分岐削除)
- `katrain/core/coach/llm_validator.py` (tone 一貫性チェック削除 +
  docstring 更新)
- `katrain/core/coach/summary_validator.py` (ToneVoice import 削除 +
  tone 一貫性チェック削除)
- `katrain/core/coach/summary_prompt_builder.py` (C 案-1 + C 案-2)
- `katrain/core/coach/__init__.py` (Kansai helpers export 削除)
- `katrain/core/coach/prompt_builder.py` (validate_prompt_config
  docstring 更新)

### テスト更新 (11 ファイル + 1 新規)

- `tests/test_coach_tones.py` (全面書き換え)
- `tests/test_coach_master_db.py` (期待値更新 + Kansai 同期テスト削除)
- `tests/test_coach_e2e.py` (Scenario 1 → BEGINNER+TOMOKO + tone
  整合性テスト書き換え)
- `tests/test_coach_llm_validator.py` (beginner_config fixture 更新 +
  TestToneConsistency クラス placeholder 化)
- `tests/test_coach_llm_report_renderer.py` (AYAKA 設定 → TOMOKO)
- `tests/test_coach_summary_prompt_builder.py` (AYAKA → TOMOKO)
- `tests/test_coach_summary_validator.py` (TestValidationTone プレース
 ホルダ化)
- `tests/test_coach_prompt_builder.py` (AYAKA 10+ 箇所 → TOMOKO +
  validate_prompt_config テスト更新)
- `tests/test_coach_cli.py` (TestExports で voice.value == "ayaka"
  → "tomoko")
- `tests/test_coach_karte_detector.py` (コメント更新)
- `tests/test_prompt_builder_player_color.py` (AYAKA → TOMOKO)
- **新規**: `tests/test_phase269_summary_phase_all_and_voice_unify.py`
  (28 件)

## テスト結果

- coach 関連テスト: 460+ 件 全 pass
- LLM Coach 弱点抽出: `phase_label_out_of_set` MEDIUM 警告 0 件
  (恒久解消)
- AYAKA enum 参照: 0 件 (完全削除達成)

## 後方互換性

**破壊的変更 (意図的)**:
- `from katrain.core.coach.master_db import ToneVoice; ToneVoice.AYAKA`
  → `AttributeError`
- `from katrain.core.coach import has_kansai_markers, apply_kansai_normalisation`
  → `ImportError`
- `ToneConfig` の `kansai_dictionary` フィールド → 削除

**保持された機能**:
- `ToneVoice.TOMOKO` / `ToneVoice.TOMOKO_STRICT` の 2 値
- `CoachMode` 5 値 (BEGINNER / INTERMEDIATE / DAN / ADVANCED / EXPERT)
- rank → mode 自動推定 (`estimate_mode_from_rank`)
- LLM Coach popup, prompt builder, validators の主要 API

## 関連 Phase

- **Phase 207-213**: `core/coach/` パッケージ初期実装 (AYAKA 含む)
- **Phase 226-C C1**: `_RANK_ALIASES` 漢字段級対応 (AYAKA 選択経路とは独立)
- **Phase 228-A〜D**: LLM コーチ複数局対応 (Shape B extractor / prompt / validator)
- **Phase 241-A**: weakness pattern から「good」カテゴリ除外 (AYAKA 削除とは独立)
- **Phase 269 (本 Phase)**: AYAKA 完全削除 + C 案 fix

## 残課題

- master doc (`docs/resources/go_lexicon_master_last.yaml` 周辺資料) の
  関西弁セクションは外部資料のため未削除 (将来オプトイン復活時に再利用)
- `Katrain/core/coach/__init__.py` の public API 表面は縮小したが、
  `CoachMode` / `ToneVoice` / `select_voice` / `build_translation_prompt`
  等の主要シンボルは維持
