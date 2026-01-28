# Phase 79: エラーハンドリング C（バックグラウンドパス）- Final v3

## 概要

Phase 77-78で確立されたエラーハンドリング改善の継続。バックグラウンド処理における広範な`except Exception`を、**実際のコードパス監査に基づいた**具体的な例外クラスに置換する。

**修正レベル**: Lv3（複数ファイル）
**対象ハンドラ数**: 27箇所
**対象ファイル数**: 12ファイル

---

## ログポリシー（統一ルール - 厳格版）

| 例外タイプ | ログ内容 | Traceback | 実装 |
|-----------|----------|-----------|------|
| **Expected** | 短いコンテキスト（パス、操作名） | **なし** | `log(f"SGF parse failed: {path.name}: {e}")` |
| **Unexpected** | コンテキスト + **必ずtraceback** | **必須** | 下記参照 |

### Unexpected例外のtraceback実装

**Python logging使用時**:
```python
except Exception:
    logger.warning("Unexpected error in X", exc_info=True)
```

**katrain.log使用時（exc_info非対応）**:
```python
except Exception as e:
    import traceback
    log(f"Unexpected error in X: {e}\n{traceback.format_exc()}", OUTPUT_ERROR)
```

### 条件付きDebug traceback（オプション機能のみ）
```python
except Exception:
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Optional feature X failed", exc_info=True)
    else:
        logger.debug("Optional feature X failed")
```

---

## 既存ドメイン例外階層

```
katrain/core/errors.py:
├── KaTrainError (base)
│   ├── EngineError      # エンジン起動・通信
│   ├── ConfigError      # 設定読み書き
│   ├── UIStateError     # UI状態保存・復元
│   └── SGFError         # SGF読み込み・解析

katrain/core/reports/karte/models.py:
├── KarteGenerationError  # カルテ生成失敗
└── MixedEngineSnapshotError(ValueError)  # 混合エンジン検出
```

---

## Phase 79A: Core Batch（6箇所）

### A1: `analyze_single_file()` - 解析失敗

**Grep Pattern**: `"except Exception as e:" after "fail_result()"`

| 項目 | 値 |
|------|-----|
| **Expected例外** | `SGFError`, `OSError`, `UnicodeDecodeError` |
| **Unexpected例外** | その他すべて |
| **フォールバック** | `fail_result()` を返す |
| **バッチ継続** | ✅ YES |

**変更後**:
```python
except SGFError as e:
    log(f"    SGF parse error ({sgf_path.name}): {e}")
    return fail_result()
except OSError as e:
    log(f"    File I/O error ({sgf_path.name}): {e}")
    return fail_result()
except UnicodeDecodeError as e:
    log(f"    Encoding error ({sgf_path.name}): {e}")
    return fail_result()
except Exception as e:
    # Unexpected: traceback必須
    log(f"    Unexpected error ({sgf_path.name}): {e}")
    log(f"    {traceback.format_exc()}")
    return fail_result()
```

---

### A2: `analyze_single_file_leela()` - Leela解析失敗

**変更後**: A1と同様のパターン適用

---

### A3: `run_batch()` - カルテ生成失敗

**Grep Pattern**: `"karte_failed"` 周辺

| 項目 | 値 |
|------|-----|
| **Expected例外** | `KarteGenerationError`, `MixedEngineSnapshotError`, `OSError` |
| **Unexpected例外** | その他 |
| **フォールバック** | `result.karte_failed += 1`, `WriteError` 追加 |
| **バッチ継続** | ✅ YES |

**エラー種別の区別**: `message`フィールドにプレフィックス追加（Option B採用）

```python
except (KarteGenerationError, MixedEngineSnapshotError) as e:
    result.karte_failed += 1
    log(f"  Karte generation error ({sgf_path.name}): {e}")
    result.write_errors.append(WriteError(
        file_kind="karte",
        sgf_id=sgf_path.name,
        target_path=str(karte_path),
        exception_type=type(e).__name__,
        message=f"[generation] {e}",
    ))
except OSError as e:
    result.karte_failed += 1
    log(f"  Karte write error ({sgf_path.name}): {e}")
    result.write_errors.append(WriteError(
        file_kind="karte",
        sgf_id=sgf_path.name,
        target_path=str(karte_path),
        exception_type=type(e).__name__,
        message=f"[write] {e}",
    ))
except Exception as e:
    # Unexpected: traceback必須
    result.karte_failed += 1
    log(f"  Unexpected karte error ({sgf_path.name}): {e}")
    log(f"    {traceback.format_exc()}")
    result.write_errors.append(WriteError(
        file_kind="karte",
        sgf_id=sgf_path.name,
        target_path=str(karte_path),
        exception_type=type(e).__name__,
        message=f"[unexpected] {e}",
    ))
```

**WriteError既存フィールド確認済み**: `file_kind`, `sgf_id`, `target_path`, `exception_type`, `message`
→ 新規フィールド追加不要、`message`内プレフィックスで区別

---

### A4: `run_batch()` - 統計抽出失敗

| 項目 | 値 |
|------|-----|
| **Expected例外** | `KeyError`, `ValueError` (外部SGFデータ由来) |
| **Unexpected例外** | その他（内部バグ） |

**変更後**:
```python
except (KeyError, ValueError) as e:
    log(f"  Stats extraction error ({sgf_path.name}): {e}")
except Exception as e:
    # Unexpected: traceback必須
    log(f"  Unexpected stats error ({sgf_path.name}): {e}")
    log(f"    {traceback.format_exc()}")
```

---

### A5: `run_batch()` - サマリー生成失敗

| 項目 | 値 |
|------|-----|
| **Expected例外** | `OSError`, `KeyError`, `ValueError` |
| **Unexpected例外** | その他 |

---

### A6: `run_batch()` - Curator生成失敗

| 項目 | 値 |
|------|-----|
| **Expected例外** | `OSError`, `json.JSONDecodeError` |
| **Unexpected例外** | その他 |

---

## Phase 79B: Reports（11箇所）

### B1: `_compute_style_safe()` - スタイル計算

| 項目 | 値 |
|------|-----|
| **Expected例外** | `ValueError`, `KeyError` |
| **Unexpected例外** | その他 |
| **正当性** | オプション機能。失敗してもカルテ生成継続 |

**変更後**:
```python
except (ValueError, KeyError) as e:
    logger.debug(f"Style computation skipped: {e}")
    return None
except Exception:
    # Unexpected: オプション機能だがtraceback必要
    logger.debug("Unexpected style computation error", exc_info=True)
    return None
```

---

### B2: `build_karte_report()` - カルテ生成メイン

| 項目 | 値 |
|------|-----|
| **Expected例外** | `MixedEngineSnapshotError`（既に個別ハンドル） |
| **Unexpected例外** | その他すべて |

**変更後**: Unexpected部分は `exc_info=True` または `traceback.format_exc()` 追加

---

### B3-B4: `_build_karte_report_impl()` - 時間解析/ヒストグラム

| 項目 | 値 |
|------|-----|
| **Expected例外** | `ValueError`, `KeyError` (時間データ欠損・不正) |
| **正当性** | オプション機能。SGFに時間データがない場合は正常に失敗 |

---

### B5: `build_karte_json()` - フェーズ分類

| 項目 | 値 |
|------|-----|
| **Expected例外** | `ValueError` |
| **Unexpected例外** | その他 |
| **ループ内** | ⚠️ YES |

**変更後**:
```python
except ValueError as e:
    logger.debug(f"Phase classification defaulted for move {mv.move_number}: {e}")
    phase = "unknown"
except Exception:
    # Unexpected: traceback必須
    logger.debug(f"Unexpected phase error for move {mv.move_number}", exc_info=True)
    phase = "unknown"
```

---

### B6-B7: `important_moves.py` - コンテキスト/Critical 3

| 項目 | 値 |
|------|-----|
| **Expected例外** | `KeyError` (SGFツリー構造) |
| **Unexpected例外** | その他 |
| **ループ内** | B6: YES、B7: 4-6回/ゲーム |

**Unexpected例外のtraceback戦略**: `katrain.log`は`exc_info`非対応のため、`traceback.format_exc()`を追加

**変更後** (B6):
```python
except KeyError as e:
    game.katrain.log(f"Context extraction skipped: {e}", OUTPUT_DEBUG)
    return context
except Exception as e:
    # Unexpected: traceback必須（katrain.log用）
    import traceback
    game.katrain.log(
        f"Unexpected context error: {e}\n{traceback.format_exc()}",
        OUTPUT_DEBUG
    )
    return context
```

---

### B8: `metadata.py` - リスク管理セクション

| 項目 | 値 |
|------|-----|
| **Expected例外** | `KeyError`, `ValueError` |
| **正当性** | オプション機能（Phase 62追加） |

---

### B9-B11: `package_export.py` - ディレクトリ検証/coach.md/ZIP作成

| ID | Expected例外 | 正当性 |
|----|-------------|--------|
| B9 | `OSError` | `Path.is_dir()` が無効パスで発生可能 |
| B10 | `OSError` | PyInstaller環境でファイル欠損 |
| B11 | `OSError`, `zipfile.BadZipFile` | ZIP作成I/O |

**B9 変更後**:
```python
except OSError as e:
    logger.debug(f"Directory not writable: {path} ({e})")
    return False
except Exception:
    # Unexpected: traceback必須
    logger.debug(f"Unexpected directory check error: {path}", exc_info=True)
    return False
```

---

## Phase 79C: Curator（3箇所）

| ID | Expected例外 | フォールバック |
|----|-------------|----------------|
| C1 | `OSError`, `json.JSONDecodeError` | `result.errors.append()` |
| C2 | `KeyError`, `ValueError` | 次のゲームへ |
| C3 | `OSError`, `json.JSONDecodeError` | `result.errors.append()` |

---

## Phase 79D: Summary（7箇所）

### D1: `summary_aggregator.py` - SGFスキャン

| 項目 | 値 |
|------|-----|
| **Expected例外** | `SGFError`, `OSError` |
| **ループ内** | ⚠️ YES |

---

### D2-D5: `summary_io.py` - サマリー保存

| ID | Expected例外 | ループ |
|----|-------------|--------|
| D2 | `OSError` | YES (player loop) |
| D3 | `OSError` | YES (max 3 categories) |
| D4 | Kivy `RuntimeError` | NO |
| D5 | `OSError` | NO |

---

### D6-D7: `summary_stats.py` - 統計抽出（整合性修正）

**現状分析**:
- D6 (reason_tags, line 247): `OUTPUT_ERROR` + traceback → **Unexpected扱い**
- D7 (time analysis, line 285): `logger.debug()` tracebackなし → **Expected扱い**
- 外側 (line 291): `OUTPUT_ERROR` + traceback → **Unexpected扱い**

**設計根拠**:
- **D6/外側**: `reason_tags`計算失敗や全体失敗は内部ロジック問題 → Unexpected（traceback必須）✅ 現状OK
- **D7**: 時間データはSGFに含まれないことが多い（Expected失敗）→ debug、tracebackなし ✅ 現状OK

**結論**: 現状は意図通り。D7は Expected（時間データ欠損は頻繁）で `logger.debug()` が妥当。変更不要。

---

## 除外項目（intentional - 変更しない）

| カテゴリ | 理由 | 対象ファイル |
|----------|------|--------------|
| `thread-exception` | スレッドクラッシュ防止 | engine.py, leela/engine.py |
| `shutdown-cleanup` | 終了処理の確実な完了 | engine.py |
| `callback-protection` | コールバック呼び出し元保護 | lang.py, lang_bridge.py |
| `traceback-format` | エラーハンドラ自身の保護 | error_handler.py |

---

## TypeError/AttributeError 使用ポリシー

**原則**: Expected例外として使用しない（内部バグを隠す）。
**Unexpected バケット**に分類し、traceback付きでログ。

---

## 検証計画

### 1. 既存テスト + アーキテクチャテスト

```powershell
uv run pytest tests -v
uv run pytest tests/test_architecture.py -v
```

### 2. 手動バッチテスト

```powershell
python -m katrain
# Settings → Batch Analyze Folder → 破損SGF含むフォルダで実行
# 確認: クラッシュしない、エラーログ出力される
```

### 3. 新規ターゲットテスト（最小セット - 3テスト）

`tests/test_error_handling_phase79.py`:

```python
"""Phase 79 error handling tests - Core Batch + Package Export.

Focused on 3 high-value paths:
1. analyze_single_file with invalid SGF (A1)
2. _is_writable_directory edge case (B9)
3. create_llm_package with ZIP error (B11)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestAnalyzeSingleFileSGFError:
    """A1: Invalid SGF should fail gracefully with log output."""

    def test_invalid_sgf_returns_false_and_logs_error(self, tmp_path):
        """Invalid SGF content should return False and log an error."""
        from katrain.core.batch.analysis import analyze_single_file

        # Create invalid SGF file
        bad_sgf = tmp_path / "invalid.sgf"
        bad_sgf.write_text("not valid sgf content", encoding="utf-8")

        # Capture logs
        logs: list[str] = []

        # Create minimal mocks
        mock_katrain = MagicMock()
        mock_engine = MagicMock()
        mock_engine.is_idle.return_value = True

        result = analyze_single_file(
            katrain=mock_katrain,
            engine=mock_engine,
            sgf_path=str(bad_sgf),
            output_path=None,
            visits=10,
            timeout=5.0,
            cancel_flag=None,
            log_cb=logs.append,
            save_sgf=False,
            return_game=False,
        )

        # Assertions: graceful failure + logged
        assert result is False, "Invalid SGF should return False"
        assert any("error" in log.lower() for log in logs), (
            f"Should log error message, got: {logs}"
        )


class TestIsWritableDirectory:
    """B9: Path validation edge cases should return False, not raise."""

    def test_none_path_returns_false(self):
        """None path should return False immediately."""
        from katrain.core.reports.package_export import _is_writable_directory

        result = _is_writable_directory(None)
        assert result is False

    def test_invalid_path_type_returns_false(self):
        """Invalid path (causes exception in Path()) should return False."""
        from katrain.core.reports.package_export import _is_writable_directory

        # Path with embedded null byte raises ValueError on some platforms
        # or TypeError with wrong type - both should be caught
        result = _is_writable_directory(12345)  # int, not path-like
        assert result is False, "Invalid path type should return False"

    def test_nonexistent_directory_returns_false(self, tmp_path):
        """Non-existent directory should return False (is_dir() returns False)."""
        from katrain.core.reports.package_export import _is_writable_directory

        nonexistent = tmp_path / "does_not_exist"
        result = _is_writable_directory(nonexistent)
        assert result is False


class TestCreateLlmPackageZipError:
    """B11: ZIP creation failure should return structured error result."""

    def test_zip_write_error_returns_failure_result(self, tmp_path, monkeypatch):
        """OSError during ZIP write should return PackageResult(success=False)."""
        from katrain.core.reports.package_export import (
            create_llm_package,
            PackageContent,
        )
        import zipfile

        # Create test content
        content = PackageContent(
            karte_md="# Test Karte",
            sgf_content="(;GM[1])",
            coach_md="# Coach",
            game_info={"black": "Test", "white": "Test"},
            skill_preset="standard",
            anonymized=False,
        )

        # Use a path that will fail (directory instead of file)
        # This simulates OSError during file creation
        output_path = tmp_path  # tmp_path is a directory, not a file

        # Patch ZipFile in the target module to raise OSError
        original_zipfile_class = zipfile.ZipFile

        class MockZipFile:
            def __init__(self, *args, **kwargs):
                raise OSError("Cannot write to path")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        # Patch at the usage site
        import katrain.core.reports.package_export as pkg_mod
        monkeypatch.setattr(pkg_mod.zipfile, "ZipFile", MockZipFile)

        result = create_llm_package(content=content, output_path=output_path)

        # Assertions
        assert result.success is False, "ZIP error should return success=False"
        assert result.error_message is not None, "Should have error message"
```

### 4. 確認チェックリスト

- [ ] 全テスト通過（2918件 + 3件新規）
- [ ] アーキテクチャテスト通過
- [ ] 手動バッチテスト: 破損SGFでクラッシュしない
- [ ] 手動バッチテスト: エラーログ出力される
- [ ] Expected例外: tracebackなし
- [ ] Unexpected例外: traceback **必ず** あり
- [ ] 除外項目（intentional）が変更されていないこと

---

## 実装順序

1. **79A**: Core Batch（6箇所）
2. **79B**: Reports（11箇所）
3. **79C**: Curator（3箇所）
4. **79D**: Summary（7箇所）
5. **テスト追加**: `tests/test_error_handling_phase79.py`

各サブフェーズ完了後に `uv run pytest tests -v` 実行。

---

## 決定事項サマリー

| 項目 | 決定 | 根拠 |
|------|------|------|
| WriteError拡張 | **Option B（messageプレフィックス）** | 既存フィールド構造を維持、ripple回避 |
| D6/D7整合性 | **現状維持** | D7は時間データ欠損（Expected）、D6は内部ロジック（Unexpected）で意図通り |
| katrain.log traceback | **traceback.format_exc()追加** | exc_info非対応のため文字列追加 |
| TypeError/AttributeError | **Unexpectedバケット** | 内部バグを隠さない |
