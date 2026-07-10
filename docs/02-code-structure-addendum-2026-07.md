# 2026-07 Code Structure Addendum (Phases A/B/C)

> 最終更新: 2026-07-10
>
> 親ドキュメント `docs/02-code-structure.md` は Phase 89 (2026-01-30) 時点で
> 凍結されています。本書は 2026-07 に行った一連のリファクタリング（A/B/C 計
> 6 マージ済み PR）の構造的影響を記録します。
>
> 影響範囲: 3 つの god function 分割、9 ファイルの独立化、6 ファイルの
> リファクタリング、CI ガードレール新設、93 テストの復活。

---

## 1. 新設されたファイル

| ファイル | 行数 | 概要 |
|---|---|---|
| `tests/test_sgf_manager_url_safety.py` | 105 | SSRF 防御 20 ケース |
| `tests/test_game_phase_enum.py` | 90 | `GamePhase` enum 17 ケース |
| `.github/dependabot.yml` | 50 | uv + GitHub Actions 週次更新 |

## 2. 分割された god function

| 元 (行数) | 分割後 (各関数の行数) | 場所 |
|---|---|---|
| `_build_player_stats_block` (215行) | `_build_overall_block` 12 / `_build_mistake_distribution` 15 / `_build_phase_distribution` 21 / `_build_reason_tags_block` 32 / `_build_mistake_sequences_block` 39 / `_build_top_mistakes_block` 42 / `_format_top_mistake_item` 23 / `_build_opponent_correlation_block` 10 / `_build_empty_player_stats_block` 38 | `katrain/core/reports/summary_json_export.py` |
| `classify_meaning_tag` (227行) | `_classify_early_uncertains` 24 / `_extract_classification_flags` 24 / `_classify_by_priority` 30 / 11 priority rules (各 5-10 行) | `katrain/core/analysis/meaning_tags/classifier.py` |
| `_process_single_file` (146行) | `_prepare_file_processing` 38 / `_run_analysis_with_circuit_breaker` 50 / `_record_engine_failure_and_maybe_abort` 11 / `_post_success_processing` 40 / `_handle_analysis_failure` 8 | `katrain/core/batch/orchestration.py` |

各関数は最大 50 行、テストカバレッジは現状維持（リファクタ前後で全 3673 テスト pass）。

## 3. データモデルの追加

| 追加 | 場所 | 説明 |
|---|---|---|
| `ClassificationFlags` (frozen dataclass) | `katrain/core/analysis/meaning_tags/classifier.py` | 11 個の reason_tag ブール値 + 派生フラグ |
| `GamePhase` (Enum) | `katrain/core/reports/constants.py` | OPENING / MIDDLE / YOSE / UNKNOWN、`.value` 文字列で JSON 互換 |
| `InternalLangCode`, `IsoLangCode` (Phase 52 で既設) | `katrain/common/locale_utils.py` | "jp"/"ja" 境界の正規化 |

## 4. セキュリティ修正

| 修正 | 場所 |
|---|---|
| `_safe_fetch_url()` ヘルパー新設 (SSRF 防御) | `katrain/gui/sgf_manager.py` |
| `altcommand` を `shlex.split` + `shell=False` | `katrain/core/engine.py` |
| `JsonFileConfigStore.reload()` 公開 API (ロック保護) | `katrain/common/config_store.py` |
| `wmic` を `shell=False` 化 | `katrain/core/diagnostics.py` |

## 5. CI ガードレール (Phase A-2)

| 項目 | 値 |
|---|---|
| ruff check | 必須 (lint job) |
| ruff format | 必須 (--check) |
| カバレッジゲート | 60% (実態 65%) |
| uv キャッシュ | `~/.cache/uv` + `.venv` |
| mypy strict | 0 errors in 255 files |

## 6. i18n 規約準拠 (Phase B-1)

| 旧 (生英語 msgid) | 新 (semantic key) |
|---|---|
| `i18n._("OK")` | `i18n._("button:ok")` |
| `i18n._("Close")` | `i18n._("button:close")` |
| `i18n._("Cancel")` | `i18n._("button:cancel")` |
| `i18n._("Error")` | `i18n._("dialog:title:error")` |

20 箇所を 8 ファイル + 1 KV ファイルで置換、`.po` / `.mo` 再コンパイル済み。

## 7. 復活したテスト (Phase A-5)

93 テストが CI で実行可能に。skipif `CI` ガードを 6 ファイルで除去。

| ファイル | テスト数 |
|---|---|
| `test_main_smoke.py` | 14 |
| `test_phase106_subscribe.py` | 11 |
| `test_p2_gui_leaks.py` | 18 |
| `test_p3_stability.py` | 17 |
| `test_popups_helpers.py` | 10 |
| `test_import_resolution.py` | 3 |

## 8. 累積変更量

| 期間 | PR | 変更ファイル | 追加/削除 |
|---|---|---|---|
| Phase A | #354-#358 | 197 | +2029/-1290 |
| Phase B | #359 | 19 | +268/-58 |
| Phase C | (open) | 7 | +892/-510 (見込み) |

合計: 約 220 ファイル、+3000/-1800 行。
