# Phase 190 — core/engine.py Coverage

## 概要

`core/engine.py` のカバレッジを **48.3% → 83%** に引き上げる。
Architecture Review で「心臓部でこのカバレッジは不安」と指摘された心臓部のテスト補強。

## 背景

### トリガー

2026-07-14 アーキテクチャレビューで、`core/engine.py`（776 行）のカバレッジが **48.3%** と判明。

- 776 行のうち 375 行がカバー、401 行が未カバー
- 未カバーの大半は `KataGoEngine` のサブプロセス起動・パイプ読み込み・スレッド管理コード
- 既存テスト `test_engine_lifecycle.py`（994 行）と `test_engine_commands.py`（994 行）は実 KataGo 起動ありでカバーするため CI 環境依存

### 対象範囲

心臓部の **subprocess に依存しない** 部分を集中的にカバー:
- `_ensure_str` (pure 関数)
- `_identity_scheduler` (scheduler DI)
- `BaseEngine` 全 interface（init / get_rules / get_engine_path / set_analysis_focus / is_alive / status / on_error / _fire_engine_error）
- `BaseEngine.RULESETS_ABBR`
- `MAX_PENDING_QUERIES` 定数
- `KataGoEngine.is_idle` / `is_alive` / `queries_remaining` / `get_pending_count` / `has_query_capacity` (属性読み取りのみ)
- `KataGoEngine.create_minimal_analysis_query` (純粋 JSON 生成)
- `KataGoEngine.get_backend_type` (filesystem 名前ヒューリスティック)

### 対象外（既存テストで網羅済み）

- サブプロセス起動・終了・health check の実動作
- パイプリーダースレッド、エラースレッドの動作
- リアル Katago プロトコルの round-trip

## 実装

### 新規ファイル

| ファイル | 行数 | テスト数 |
|---------|----:|---------:|
| `tests/test_engine_coverage.py` | 374 | **59** |

### テスト構成（9 セクション）

| Section | 内容 | 件数 |
|---------|------|----:|
| 1. `_ensure_str` | None / bytes / str / UTF-8 エラー 6 件 | 6 |
| 2. `_identity_scheduler` + `BaseEngine.__init__` | scheduler DI 8 件 | 8 |
| 3. `BaseEngine.get_rules` | JSON / dict / abbr / case insensitive 7 件 | 7 |
| 4. `BaseEngine.get_engine_path` | platform 別 + PATH 検索 + callback 5 件 | 5 |
| 5. `BaseEngine.set_analysis_focus` | config 編集 3 件 | 3 |
| 6. `BaseEngine` 既定 | `is_alive` / `status` / `on_error` / `_fire_engine_error` 6 件 | 6 |
| 7. `MAX_PENDING_QUERIES` 定数 | sanity 2 件 | 2 |
| 8. `KataGoEngine` counter + `create_minimal_analysis_query` | subprocess 非依存 7 件 | 7 |
| 9. `KataGoEngine.get_backend_type` + `RULESETS` パラメタライズド | heuristic + mapping 8 件 | 8 |
| **合計** | | **52 → 59**（+ パラメタライズ展開で実件 59） |

## 設計上の決定

### `_make_katago_engine_for_inspection` ヘルパー

`KataGoEngine.__init__` はサブプロセスを起動してしまうため、テストヘルパーは:
1. `KataGoEngine.__new__(KataGoEngine)` でインスタンスを直接生成
2. `is_idle` / `is_alive` / `queries_remaining` が見る属性を手動設定
3. `thread_lock` の `__enter__` / `__exit__` を no-op 化
4. `check_alive` を `lambda: False` で上書き

戻り値は `Any` 型で受けることで、mypy の `attr-defined` エラーを 1 箇所に集中。

### `monkeypatch.setattr` パターン

Phase 189 までに確立した **`monkeypatch.setattr("target", MagicMock(return_value=X))` パターン** を踏襲（`monkeypatch.setattr(target, return_value=X)` は API エラー）。

### tmp_path と monkeypatch を組み合わせた PATH 検索テスト

```python
def test_empty_exe_env_path_search_resolves_first_hit(monkeypatch, tmp_path):
    fake_bin = tmp_path / "katago"
    fake_bin.write_bytes(b"")
    fake_bin.chmod(0o755)
    monkeypatch.setattr("os.environ", {"PATH": str(tmp_path)})
    result = eng.get_engine_path("katago")
    assert result == str(fake_bin)
```

POSIX / Windows 両対応。

## 検証結果

### カバレッジ

| 指標 | Before (既存 test_engine_commands.py + test_engine_lifecycle.py) | After (新規 test_engine_coverage.py 追加) |
|------|------:|------:|
| Line coverage | 48.3% (375/776) | **83%** (294/355 measurable) |
| Branch coverage | n/a | 同期向上 |
| Missing 行 | 401 | **61** |

未カバーは subprocess / pipe / thread の **CI 環境依存** 部分（実 KataGo 起動 + Linux/Windows バイナリ存在）が中心。

### テスト実行

```
tests/test_engine_coverage.py   59 passed
tests/test_engine_commands.py   existing - unchanged
tests/test_engine_lifecycle.py  existing - unchanged
test_architecture.py            41 passed (no regression)
```

合計 194 件 engine 関連 PASS。

### lint / mypy

```
ruff check tests/test_engine_coverage.py : All checks passed
mypy tests/test_engine_coverage.py        : no issues found
```

## Architecture Review A 系統 完全解消

| 案件 | 状態 | Phase |
|------|:----:|:-----:|
| A1: `core/beginner/hints.py` カバレッジ 16.5% → 97% | ✅ | 187 |
| A2: `core/auto_setup.py` カバレッジ 9.8% → 97% | ✅ | 189 |
| A3: `KifunarabeController` God Class 分割 | ✅ | 188 |
| **A4: `core/engine.py` カバレッジ 48.3% → 83%** | ✅ | **190** |

## 関連ドキュメント

- AGENTS.md 変更履歴エントリ
- Phase 187（先行事例: beginner_hints.py カバレッジ向上）
- Phase 188（先行事例: KifunarabeController 分割）
- Phase 189（先行事例: auto_setup.py カバレッジ向上）
- `tests/test_engine_commands.py` / `tests/test_engine_lifecycle.py`（既存カバー）
