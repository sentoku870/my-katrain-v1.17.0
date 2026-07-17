# Phase 243: Popup Wrapper 本格移行

## 概要

Phase 242-E で `katrain/core/coach/popup_logic.py` に 13 個の pure helper を抽出したが、
popup 本体 (`katrain/gui/popups/llm_coach_popup.py`) はまだ旧ロジックのまま重複している。
本 Phase では popup を薄いラッパーに refactor して、ロジックの単一情報源を `popup_logic.py` に統一する。

## 動機

- 現状: popup.py に 1269 行、そのうち pure logic 部分（perspective 解決、type label 整形、
  validation status 整形、truncate 判定など）が ~150 行を占める
- 重複: 同じロジックが popup_logic.py にもあるため、片方を修正してももう片方が追従しないリスク
- テスタビリティ: pure logic が popup.py に残っていると headless CI でテストできない
- Phase 242-E 時点であえて popup の移行を「follow-up」としたのは、242 のスコープ膨張を防ぐため

## スコープ

### 移行対象（10 個所）

| popup.py の旧ロジック | popup_logic.py の新呼び出し | 行数削減 |
|----------------------|---------------------------|----------|
| `_resolve_player_color` | `resolve_player_color_internal` | -10 |
| `is_summary_birdseye` | `is_summary_birdseye_value` | -5 |
| `_summary_index_to_internal` | `_summary_index_to_internal` (popup_logic) | -10 |
| `_SUMMARY_BIRDSEYE_SENTINEL` 定数 | `SUMMARY_BIRDSEYE_SENTINEL` (popup_logic) re-export | -2 |
| `_detect_path_type` 内 JSON 読み込み | `detect_path_type_from_file` | -25 |
| `_refresh_type_label` 内 type_label 構築 | `format_type_label` | -15 |
| `on_validate` / `_on_validate_summary` 内 count | `count_issue_markers` | -6 |
| `on_validate` / `_on_validate_summary` 内 status 構築 | `format_validation_status_summary` | -15 |
| `_on_response_text` 内 truncate | `cap_response_text` | -10 |
| `_populate_summary_perspective` 内 values 構築 | `resolve_summary_spinner_values` | -20 |

**合計**: 約 -118 行の重複削除 + popup.py の責務を 1269 → ~1150 行に削減

### 移行しないもの

- `_spinner_text_to_internal`: `i18n._()` 呼び出しを含むため Kivy-free にできない。残す
- `_get_widget` / `_read_text` / `_set_widget_text` / `_set_status` / `_set_result`:
  Kivy ウィジェット操作なので popup 側に残す
- `on_kv_post` / `cancel_pending_clocks` / `_schedule_once`: Clock 周りなので Kivy 必須

## 影響範囲

### ファイル

- `katrain/gui/popups/llm_coach_popup.py`: 約 -118 行（移行と同時に re-export 削除）
- `katrain/core/coach/popup_logic.py`: 既に完成済み、変更なし
- `tests/test_llm_coach_popup.py`: テストの一部が Kivy 不要になる（headless で走る数を増やす）
- `tests/test_coach_popup_logic.py`: 既存 58 テストに追加なし（変更なし）

### リスク評価

- **低リスク**: pure logic は popup_logic.py に既に存在し、58 テストで全パス済み
- **中リスク**: popup_logic.py の戻り値を popup が「ids-first」で書き戻すパターンが崩れていないか
- **低リスク**: i18n キーの引数形式が popup_logic.py 側の `.format()` と一致しているか
  （`mykatrain:llm-coach:truncation-warning` / `paste-too-long` / `validation-clean` 等）

## 修正手順

### 1. popup_logic.py の定数を popup.py に re-export（後方互換）

```python
# popup.py (top of file, after popup_logic import)
from katrain.core.coach.popup_logic import (
    PERSPECTIVE_AUTO,
    PERSPECTIVE_BLACK,
    PERSPECTIVE_WHITE,
    SUMMARY_BIRDSEYE_SENTINEL,
    MAX_RESPONSE_INPUT_CHARS,
    resolve_player_color_internal as _resolve_player_color,
    is_summary_birdseye_value as is_summary_birdseye,
    _summary_index_to_internal,
    detect_path_type_from_file,
    format_type_label,
    count_issue_markers,
    format_validation_status_summary,
    cap_response_text,
    resolve_summary_spinner_values,
)
```

### 2. popup.py の旧ロジックを置換

- `_resolve_player_color` 定義を削除（import でカバー）
- `is_summary_birdseye` 定義を削除
- `_summary_index_to_internal` 定義を削除
- `_SUMMARY_BIRDSEYE_SENTINEL` 定数定義を削除
- `_detect_path_type` を `detect_path_type_from_file` 呼び出しに置換
- `_refresh_type_label` の type_label 構築を `format_type_label` 呼び出しに置換
- `on_validate` / `_on_validate_summary` の count + status を
  `count_issue_markers` + `format_validation_status_summary` 呼び出しに置換
- `_on_response_text` の truncate を `cap_response_text` 呼び出しに置換
- `_populate_summary_perspective` の values 構築を `resolve_summary_spinner_values` 呼び出しに置換

### 3. テスト確認

- 既存 58 popup_logic テスト: 全パス
- 既存 popup tests (`tests/test_llm_coach_popup.py`): 全パス（Kivy 必要）
- Lint: ruff check / format

### 4. コミット

- 1 コミット: "Phase 243: popup wrapper を popup_logic.py に本格移行 (Lv2)"

## テスト計画

### 自動テスト

```bash
# popup_logic テスト（Kivy 不要、headless CI で全パスを維持）
uv run pytest tests/test_coach_popup_logic.py -v

# popup テスト（Kivy 必要、Linux CI で実行）
uv run pytest tests/test_llm_coach_popup.py -v

# 全体コーチテスト
uv run pytest tests/test_coach_*.py tests/test_llm_coach.py -q
```

### 期待値

- popup_logic 58 テスト: 全パス
- popup テスト: 全パス（変更なし）
- 全体コーチ 909+ テスト: 全パス

## 成功基準

- [ ] popup.py が -100 行以上削減されている
- [ ] `_resolve_player_color` / `is_summary_birdseye` / `_summary_index_to_internal` /
      `_SUMMARY_BIRDSEYE_SENTINEL` の重複定義が popup.py から消えている
- [ ] popup_logic.py の 13 helper 全てが popup.py から呼ばれている（_spinner_text_to_internal 以外）
- [ ] 既存テストが全てパス
- [ ] lint クリーン

## スケジュール

- 仕様書: 2026-07-17（本ドキュメント）
- 実装: 2026-07-17（同日中）
- テスト: 2026-07-17
- コミット + PR: 2026-07-17
- マージ: CI 通過後

## 関連 Phase

- Phase 242-E: popup_logic.py を新設（pure logic 抽出のみ）
- **Phase 243（本 Phase）**: popup 本体を popup_logic 呼び出しに refactor
- Phase 244（予定）: Lexicon YAML 拡張
- Phase 245（予定）: POSITIONAL_DIFFICULTY 実装
