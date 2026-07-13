# Phase 189 — Auto Setup Module Coverage

## 概要

`core/auto_setup.py` の行カバレッジを **9.8% → 97%** に引き上げる。
Architecture Review（2026-07-14）で全コア層中カバレッジ最低値と判明したファイルの改善。
Auto Setup Mode は初心者 UX の入口（"Just Make It Work" mode, Phase 89-90）を担う重要モジュール。

## 背景

### トリガー

2026-07-14 アーキテクチャレビュー（Plan Mode）で、`core/auto_setup.py`（368 行）のカバレッジが **9.8%**（36/368 行）と判明。

- 全プロダクションコア層ファイル中で最低値
- 既存テストファイルなし（`tests/` に `test_auto_setup*` ファイルが一切無し）
- 10 個の pure 関数で構成されるが、ファイル I/O 絡み（モデル検索 / CPU KataGo 検索）で未テスト

### auto_setup.py の責務

| 関数 | 役割 |
|------|------|
| `_get_packaged_defaults` | パッケージ内 config.json キャッシュ |
| `get_packaged_engine_defaults` | 公開ラッパー |
| `get_auto_setup_config` | 新規/既存ユーザー判定 + モード割り当て |
| `_has_custom_engine_settings` | パッケージ既定との差分検出 |
| `should_show_auto_tab_first` | 設定ゲート (mode × first_run_completed) |
| `get_model_search_dirs` | ユーザー / パッケージ ディレクトリ列挙 |
| `find_lightweight_model` | b10c128 軽量モデル検索 |
| `find_cpu_katago` | CPU KataGo 検索（OpenCL 拒否） |
| `_is_likely_opencl_binary` | ファイル名ヒューリスティック |
| `resolve_auto_engine_settings` | auto モード用 engine 設定生成 |
| `prepare_reset_to_auto` | 自動モードへのリセット準備 |

## 実装

### 新規ファイル

| ファイル | 行数 | テスト数 |
|---------|----:|---------:|
| `tests/test_auto_setup_coverage.py` | 490 | **53** |

### テスト構成（10 セクション）

| Section | 内容 | テスト数 |
|---------|------|---------:|
| 1. `should_show_auto_tab_first` | mode × first_run_completed 6 パラメタ + empty dict | 7 |
| 2. `_has_custom_engine_settings` | 各種カスタム設定判定（katago / model / config / all-match / empty） | 6 |
| 3. `get_auto_setup_config` | 既存 / 新規ユーザー / カスタム設定マトリクス | 7 |
| 4. `get_packaged_engine_defaults` | キャッシュ + コピー独立性 + フォールバック + テスト用 autouse fixture | 5 |
| 5. `get_model_search_dirs` | ユーザー自動作成 / 既存保持 / パッケージ含有 | 3 |
| 6. `find_lightweight_model` | 単一 / 複数タイムスタンプ / mtime フォールバック / 空 | 5 |
| 7. `_is_likely_opencl_binary` | opencl/cuda/tensorrt/eigen/cpu 7 パラメタ | 7 |
| 8. `find_cpu_katago` | OpenCL 拒否 / 単一マッチ / 全失敗 / Windows .exe | 4 |
| 9. `resolve_auto_engine_settings` | success / failure / EngineTestResult インスタンス | 4 |
| 10. `prepare_reset_to_auto` | mode / first_run / last_test / 二回呼び出し同等性 | 5 |
| **合計** | | **53** |

### 設計上の決定

#### autouse fixture でキャッシュクリア

```python
@pytest.fixture(autouse=True)
def reset_packaged_defaults():
    saved = auto_setup_mod._PACKAGED_DEFAULTS
    auto_setup_mod._PACKAGED_DEFAULTS = None
    yield
    auto_setup_mod._PACKAGED_DEFAULTS = saved
```

`_PACKAGED_DEFAULTS` は モジュールグローバル mutable なキャッシュ。テスト間状態漏れを防ぐため各テスト前後で初期化。

#### monkeypatch の正しい API

`pytest.MonkeyPatch.setattr(target, value)` は **value を MagicMock として渡せない**（`return_value=` をキーワード引数として解釈してしまう）。
正しくは `monkeypatch.setattr("katrain.core.x.y", MagicMock(return_value=Z))` の形式。
Phase 188 で学んだパターンの再確認。

#### tmp_path / monkeypatch によるファイルシステム制御

- `find_package_resource` は monkeypatch でダミー値返却
- `DATA_FOLDER` は monkeypatch で `tmp_path` にリダイレクト
- `os.path.isfile` は `unittest.mock.patch` で True/False 切替

## 検証結果

### カバレッジ

| 指標 | Before | After |
|------|-------:|------:|
| Line coverage | 9.8% (36/368) | **97%** (97/100 stmts) |
| Branch coverage | n/a | **97%** (29/30 branches) |
| Uncovered lines | n/a | 3 (195-196 OSError fallback, 272 shutil.which) |

未カバーは環境固有のフォールバックパス（macOS の `shutil.which` 分岐 + ユーザー ディレクトリ作成失敗パス）。

### テスト実行

```
tests/test_auto_setup_coverage.py  53 passed
```

### lint / mypy

```
ruff check tests/test_auto_setup_coverage.py : All checks passed
mypy tests/test_auto_setup_coverage.py        : Success: no issues found
```

## 関連ドキュメント

- AGENTS.md 変更履歴エントリ
- `.opencode/skills/architecture/SKILL.md`
- Phase 187（同 A1 系統: beginner_hints.py カバレッジ 16.5% → 97% の先行事例）
- Phase 188（同 A3 系統: KifunarabeController God Class 分割）

## アーキテクチャレビュー優先度リスト完遂

| 案件 | 状態 |
|------|------|
| A1: `core/beginner/hints.py` カバレッジ | ✅ Phase 187 |
| **A2: `core/auto_setup.py` カバレッジ** | ✅ **Phase 189（本 Phase）** |
| A3: `KifunarabeController` God Class 分割 | ✅ Phase 188 |

Architecture Review（2026-07-14）の Priority 1（カバレッジ + God Class 分割）は全て解消。次の改善対象は Priority 2（B1-B4）に移行。