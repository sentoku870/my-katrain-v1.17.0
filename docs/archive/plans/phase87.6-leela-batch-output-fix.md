# Phase 87.6: Leela Zero Batch Analysis Output Fix

## 問題の概要

Leela Zeroのフォルダ一括解析で、解析済みSGF・カルテ・サマリーが生成されない問題を修正する。

**ユーザー報告**:
- カルテ: 0/0（0件エラー）
- サマリー: ERROR: No valid game statistics available
- SGF: 0

---

## 戻り値の契約（コード検索による証明）

### analyze_single_file_leela() の戻り値

**場所**: [analysis.py:207-211](katrain/core/batch/analysis.py#L207)

**全ての戻り箇所**:
| Line | 状況 | 戻り値 |
|------|------|--------|
| 243 | キャンセル（開始前） | `fail_result()` |
| 252 | SGFパースエラー | `fail_result()` |
| 257 | キャンセル（パース後） | `fail_result()` |
| **291** | **0手SGF** | **`success_result(game, EvalSnapshot(moves=[]))`** ← 問題 |
| 314 | ファイルタイムアウト | `fail_result()` |
| 319 | キャンセル（解析中） | `fail_result()` |
| 387 | output_path未指定 | `fail_result()` |
| 405 | 正常完了 | `success_result(game, snapshot)` |
| 411-427 | 例外発生 | `fail_result()` |

---

## 呼び出し元の調査結果

### analyze_single_file_leela の呼び出し元

| 場所 | 用途 | 0手SGF動作への依存 |
|------|------|-------------------|
| `orchestration.py:276` | バッチ処理 | なし（修正対象） |
| `batch_analyze_sgf.py:77` | 再エクスポート | インポートのみ |
| テストファイル | シグネチャテスト | なし |

**結論**: 0手SGFを`fail_result()`に変更しても影響はない。

### extract_game_stats の呼び出し元

| 場所 | log_cb渡し | 対応 |
|------|----------|------|
| `orchestration.py:405` | なし（修正対象） | 追加する |
| `benchmark_batch.py:166` | なし | デフォルト値Noneで後方互換 |

**結論**: シグネチャは既に`log_cb=None`を持つため後方互換。

---

## 修正計画（レビュー指摘対応版 v4）

### 修正レベル: Lv3（複数ファイル、3ファイル）

### 変更ファイル

1. `katrain/core/batch/analysis.py` - 0手SGF処理修正、エラーログ強化
2. `katrain/core/batch/orchestration.py` - Success gate修正、karte_failed追跡、古いメッセージ削除、log_cb渡し
3. `katrain/core/batch/stats/extraction.py` - 空snapshot時のログ追加

---

## 実装手順

### Step 1: 古いログメッセージを削除（Lv0）

**ファイル**: `katrain/core/batch/orchestration.py`

Line 144-146を削除:
```python
# 削除:
# Note: Karte generation is limited for Leela in Phase 36 MVP
if generate_karte:
    log("Note: Karte generation is not yet supported for Leela analysis")
```

### Step 2: 0手SGFを「失敗」として処理（Lv1）

**ファイル**: `katrain/core/batch/analysis.py`

Line 289-291を修正:
```python
# Before:
if total_moves == 0:
    log("    No moves to analyze")
    return success_result(game, EvalSnapshot(moves=[]))

# After:
if total_moves == 0:
    log("    ERROR: Empty SGF (0 moves)")
    return fail_result()  # Phase 87.6: Empty SGF is treated as analysis failure
```

### Step 3: Leela解析のエラーログを強化（Lv1）

**ファイル**: `katrain/core/batch/analysis.py`

**指摘対応**: `getattr`を使用し、None要素に対してガード。

Step 4（MoveEval変換）の後（Line 381付近、snapshot作成後）にログ追加:
```python
# After: snapshot = EvalSnapshot(moves=move_evals)

# Phase 87.6: Log analysis quality using parse_error as single source of truth
valid_count = len(move_evals)
if valid_count < total_moves:
    # Count errors by type from position_evals.parse_error field
    # Use getattr for robustness against None or missing attribute
    timeout_count = sum(1 for ev in position_evals
                        if getattr(ev, "parse_error", None) == "timeout")
    no_result_count = sum(1 for ev in position_evals
                          if getattr(ev, "parse_error", None) == "no result")
    other_error_count = sum(1 for ev in position_evals
                            if getattr(ev, "parse_error", None) not in (None, "timeout", "no result"))

    log(f"    Analysis quality: {valid_count}/{total_moves} valid moves")
    if timeout_count > 0:
        log(f"      - {timeout_count} timeouts")
    if no_result_count > 0:
        log(f"      - {no_result_count} no results")
    if other_error_count > 0:
        log(f"      - {other_error_count} parse errors")
```

**注**: `LeelaPositionEval` dataclass ([models.py:44-55](katrain/core/leela/models.py#L44)) は `parse_error: Optional[str] = None` フィールドを持つため、`getattr`は追加の安全策。

### Step 4: Success Gate を修正し、karte_failed を追跡（Lv2）

**ファイル**: `katrain/core/batch/orchestration.py`

**Part A**: Line 289-296を修正（Success gate の強化）:

```diff
             # Leela returns (Game, EvalSnapshot) tuple
-            if isinstance(game_result, tuple):
+            # Leela returns (Game, EvalSnapshot) tuple per contract (analysis.py:207-211)
+            if isinstance(game_result, tuple) and len(game_result) == 2:
                 game, leela_snapshot = game_result
-                success = game is not None
+                # Phase 87.6: Success requires both game and valid analysis data
+                if game is None:
+                    success = False
+                    # fail_result() was called - detailed error already logged in analysis.py
+                    # Log file identification here for consistency
+                    log(f"  FAILED: Analysis error for {rel_path}")
+                elif leela_snapshot is None or len(leela_snapshot.moves) == 0:
+                    success = False
+                    # Could be: empty SGF (0 moves) or all moves failed
+                    # Detailed reason already logged by analysis.py
+                    log(f"  FAILED: No valid analysis data for {rel_path}")
+                else:
+                    success = True
             else:
+                # Defensive: unexpected return type from analyze_single_file_leela
                 game = None
                 leela_snapshot = None
                 success = False
+                log(f"  ERROR: Unexpected return type from Leela analysis for {rel_path}: {type(game_result)}")
```

**Part B**: Line 425-430の`else:`ブロック内に karte_failed 追跡を追加:

```diff
         else:
             if cancel_flag and cancel_flag[0]:
                 log("Cancelled by user")
                 result.cancelled = True
                 break
             result.fail_count += 1
+            # Phase 87.6: Track karte_failed for files that couldn't be analyzed
+            # This ensures karte_total reflects input count, not just successful analyses
+            if generate_karte:
+                result.karte_failed += 1
```

**構造の確認**: `else:` (Line 425) は `if success:` (Line 320) に対応するブロック。ここに追加することで、`success=False` の場合に `karte_failed` がインクリメントされる。

### Step 5: extract_game_statsにlog_cbを渡す（Lv1）

**ファイル**: `katrain/core/batch/orchestration.py`

Line 405-410を修正:
```diff
                     stats = extract_game_stats(
                         game, rel_path,
+                        log_cb=log_cb,  # Phase 87.6: Wire logging callback
                         target_visits=visits,
                         source_index=i,
                         snapshot=leela_snapshot,
                     )
```

**後方互換性**: `extract_game_stats` のシグネチャ ([extraction.py:30](katrain/core/batch/stats/extraction.py#L30)) は既に `log_cb: Optional[Callable[[str], None]] = None` を持つため、他の呼び出し元（`benchmark_batch.py`）への影響なし。

### Step 6: 空snapshot時のログ追加（Lv1）

**ファイル**: `katrain/core/batch/stats/extraction.py`

Line 68-69を修正:
```diff
         if not snapshot.moves:
+            if log_cb:
+                log_cb(f"  Stats skipped for {rel_path}: no valid moves in snapshot")
             return None
```

### Step 7: テスト追加（Lv2）

**ファイル**: `tests/test_batch_leela.py`（新規または既存）

```python
def test_leela_empty_sgf_returns_false():
    """Empty SGF (0 moves) should return False when return_game=False."""
    # Setup: Create empty SGF file (root node only, no moves)
    # Call analyze_single_file_leela with return_game=False
    result = analyze_single_file_leela(..., return_game=False)
    assert result is False

def test_leela_empty_sgf_returns_none_game_with_return_game_true():
    """Empty SGF (0 moves) should return (None, empty snapshot) when return_game=True."""
    result = analyze_single_file_leela(..., return_game=True)
    assert isinstance(result, tuple)
    assert len(result) == 2
    game, snapshot = result
    assert game is None
    assert len(snapshot.moves) == 0

def test_batch_karte_counters_track_failures():
    """karte_total should include failed files, not just successful ones."""
    # Create 3 test SGF files (e.g., 1 valid, 2 empty)
    # Run batch with generate_karte=True, analysis_engine="leela"
    result = run_batch(..., generate_karte=True, analysis_engine="leela")

    # Assert: karte_total = karte_written + karte_failed = 3 (not 0/0)
    karte_total = result.karte_written + result.karte_failed
    assert karte_total == 3, f"Expected karte_total=3, got {karte_total}"

    # Assert: counters are consistent
    assert result.success_count + result.fail_count == 3

def test_batch_counters_with_all_failures():
    """Batch counters should reflect input count even when all files fail."""
    # Create 3 empty SGF files
    # Run batch with analysis_engine="leela"
    result = run_batch(..., analysis_engine="leela")

    assert result.success_count == 0
    assert result.fail_count == 3
    assert result.success_count + result.fail_count == 3
    # karte_failed should also be 3 if generate_karte=True
```

---

## parse_error による分類（単一ソース）

**調査結果**: [models.py:44-55](katrain/core/leela/models.py#L44)

```python
@dataclass
class LeelaPositionEval:
    candidates: List[LeelaCandidate] = field(default_factory=list)
    root_visits: int = 0
    parse_error: Optional[str] = None  # ← エラー種別を格納
```

`position_evals` は `LeelaPositionEval` のリストで、各要素は必ず `parse_error` フィールドを持つ（dataclass）。ただし、`getattr` を使用することで将来の変更に対してより堅牢。

---

## 検証方法

### 1. 単体テスト
```powershell
uv run pytest tests/test_batch_leela.py -v
```

### 2. Leelaテスト
```powershell
uv run pytest tests -k "leela" -v
```

### 3. 手動テスト
1. KaTrainを起動: `python -m katrain`
2. 空のSGF（0手）を含むフォルダでバッチ解析（Leela選択）
3. 結果を確認:
   - 空のSGF: 「ERROR: Empty SGF (0 moves)」がログに表示
   - 解析失敗時: 「FAILED: No valid analysis data for [filename]」がログに表示
   - **カウンター**: 「失敗: N」「カルテ: 0/N (N件エラー)」（**0/0ではない**）

### 4. 全テスト
```powershell
uv run pytest tests
```

---

## 指摘対応サマリー v5（最終レビュー対応）

### v4 の指摘対応

| 指摘 | 対応 |
|------|------|
| 1. Step 4 の構文/制御フロー | diff形式で明確に記述、`else:`ブロック内に追加 |
| 2. parse_error カウントのクラッシュ | `getattr(ev, "parse_error", None)` を使用 |
| 3. log_cb の後方互換性 | シグネチャは既に`log_cb=None`、他呼び出し元に影響なし |
| 4. 0手SGF 変更の影響 | 呼び出し元を調査、依存なしを確認 |

### v5 の指摘対応（最終レビュー）

| 指摘 | 対応 | 検証結果 |
|------|------|----------|
| 1. fail_result() 戻り値契約の統一 | analysis.py L229-232で確認済み | `return_game=True`時: `(None, EvalSnapshot(moves=[]))` |
| 2. game is Noneパスのログ追加 | Step 4 Part Aに追加 | `log(f"  FAILED: Analysis error for {rel_path}")` |
| 3. parse_error文字列の検証 | analysis.py L343, L348で確認済み | `"timeout"`, `"no result"` のみ使用 |
| 4. rel_pathのクラッシュ耐性 | orchestration.py L222で確認済み | ループ変数として利用可能、例外なし |

### parse_error文字列の検証結果

**ファイル**: [analysis.py](katrain/core/batch/analysis.py)

| Line | 文字列 | 条件 |
|------|--------|------|
| 343 | `"timeout"` | `result_event.wait(timeout=per_move_timeout)` がFalse |
| 348 | `"no result"` | `result_holder[0]` がNone |

**Step 3のカウント分類との整合性**: ✅ 一致
```python
timeout_count = ... if getattr(ev, "parse_error", None) == "timeout"
no_result_count = ... if getattr(ev, "parse_error", None) == "no result"
other_error_count = ... if getattr(ev, "parse_error", None) not in (None, "timeout", "no result")
```

---

## リスク評価

| リスク | 確率 | 影響 | 対策 |
|--------|------|------|------|
| KataGoパスへの影響 | 低 | 高 | 変更はLeela条件内のみ |
| 既存テストの失敗 | 中 | 中 | 0手SGFの扱い変更により期待値修正が必要な可能性 |
| karte_failed の意味変更 | 低 | 中 | 「生成失敗」から「解析失敗を含む」に拡張 |

---

## 実装順序

1. Step 1: 古いログメッセージ削除
2. Step 2: 0手SGF処理修正
3. Step 3: エラーログ強化
4. Step 5: log_cb渡し
5. Step 6: 空snapshot時のログ
6. Step 4: Success gate修正 + karte_failed追跡（根本原因）
7. Step 7: テスト追加

---

## 実装結果

**完了日**: 2026-01-30
**PR**: #227
**テスト**: 3202件パス（+3件）

### 実装した変更

1. **analysis.py**:
   - `_DummyEngine`クラス追加（engine=None時のクラッシュ防止）
   - 0手SGFを`fail_result()`に変更
   - 解析品質ログ追加（parse_errorカウント）

2. **orchestration.py**:
   - Success gate強化（game + snapshot.moves検証）
   - karte_failed追跡追加
   - 古いログメッセージ削除

3. **extraction.py**:
   - 空snapshot時のログ追加

4. **tests/test_batch_leela_analysis.py**:
   - Phase 87.6テスト4件追加
   - `_make_mock_katrain()`ヘルパー追加
   - `LeelaCandidate`モック修正
