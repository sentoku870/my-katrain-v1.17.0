# Phase 192 — Position Difficulty サブパッケージ化

## 概要

`core/analysis/logic_difficulty.py`（756 行・13 関数 / 単一ファイル）を
`analysis/difficulty/` サブパッケージ（6 モジュール）に分割。
既存の `analysis/cluster_*` / `analysis/meaning_tags/` / `analysis/time/`
/ `analysis/models/` サブパッケージパターンに揃える。

## 動機

### トリガー

2026-07-14 アーキテクチャレビューで `core/analysis/logic_difficulty.py`
が 756 行・13 関数 / 単一ファイルと判明。

`analysis/` ディレクトリに既に複数あるサブパッケージ:
- `analysis/cluster_classifier.py`
- `analysis/cluster_detectors.py`
- `analysis/cluster_geometry.py`
- `analysis/meaning_tags/classifier.py`
- `analysis/meaning_tags/context_builder.py`
- `analysis/models/difficulty.py`  他
- `analysis/time/` 複数モジュール

に対して `logic_difficulty.py` のみが「独立単一ファイル」で、サブパターン
と整合性が悪い。

### 採用戦略: **シム残し再エクスポート**

新規サブパッケージに分割しつつ、`katrain/core/analysis/logic_difficulty.py`
を残して**完全シム化**:
- `difficulty_metrics_from_node` 等 4 公開関数を再エクスポート
- `_compute_policy_difficulty` / `_get_root_visits` / `_normalize_candidates` 等の private 関数も再エクスポート（既存テストが direct import しているため）
- 新旧両方の命名 `_compute_X` と `compute_X` を提供し、段階移行を可能に

メリット: 外部 4 ファイル（`logic.py` / `logic_reliability.py` / `__init__.py` /
`test_difficulty_metrics.py`）を無修正のまま動作維持。負債としてのシムを
明示的に残すことで、削除タイミングを将来判断可能。

## ファイル構成（After）

```
katrain/core/analysis/
├── difficulty/
│   ├── __init__.py            # 公開 API の re-export (~30 行)
│   ├── api.py                  # 公開 4 関数: assess_position_difficulty_from_parent,
│   │                          # compute_difficulty_metrics, extract_difficult_positions,
│   │                          # difficulty_metrics_from_node (~250 行)
│   ├── _io.py                  # normalize_candidates, get_root_visits,
│   │                          # determine_reliability, get_candidates_from_node (~110 行)
│   ├── _policy.py              # assess_difficulty_from_policy, compute_policy_difficulty
│   │                          # (~150 行)
│   ├── _transition.py          # compute_transition_difficulty (~70 行)
│   ├── _state.py               # compute_state_difficulty (~30 行)
│   ├── _error_pressure.py      # compute_error_pressure (~60 行)
│   └── _lcb_gap.py             # compute_lcb_gap (~75 行)
└── logic_difficulty.py        # シム: 全部 re-export (~80 行, 旧 756 行)
```

合計: 6 ファイル（分割）+ 1 シム。サブパッケージは合計 760 行程度（旧 756 と
ほぼ同等の振る舞い）。

## 分割の判断軸

| 軸 | 配置 | 理由 |
|----|------|------|
| I/O (analysis / GameNode 抽出) | `_io.py` | 副作用系をまとめて隔離 |
| policy エントロピー + top-1/top-2 gap | `_policy.py` | policy 系統の signal 系 |
| transition drop | `_transition.py` | 単一概念 |
| state (board complexity) | `_state.py` | v1 placeholder（将来拡張時に編集範囲最小化） |
| error_pressure (shorttermScoreError) | `_error_pressure.py` | Phase 154 で追加 |
| lcb_gap | `_lcb_gap.py` | Phase 154 で追加 |
| 公開 4 関数 | `api.py` | 内部 helper を集約する層 |
| 公開 API 入口 | `__init__.py` | `from ... import X` が最短経路に |

## 設計上の決定

### 命名規則

新サブパッケージでは **private 関数のアンダースコアプレフィックスを削除**:

| 旧 (`logic_difficulty.py`) | 新 (`difficulty/*`) |
|--------------------------|-------------------|
| `_compute_policy_difficulty` | `compute_policy_difficulty` |
| `_compute_transition_difficulty` | `compute_transition_difficulty` |
| `_compute_state_difficulty` | `compute_state_difficulty` |
| `_compute_error_pressure` | `compute_error_pressure` |
| `_compute_lcb_gap` | `compute_lcb_gap` |
| `_normalize_candidates` | `normalize_candidates` |
| `_get_root_visits` | `get_root_visits` |
| `_determine_reliability` | `determine_reliability` |
| `_get_candidates_from_node` | `get_candidates_from_node` |
| `_assess_difficulty_from_policy` | `assess_difficulty_from_policy` |

理由:
- サブパッケージ内に隔離された時点で、private プレフィックスは冗長
- 公開 API 境界が module レベルで明確なので、ファイル内の関数名に
  `_` プレフィックスを付ける必要がない
- 外部モジュールからの呼び出しがそのまま内部表現に一致（読みやすさ向上）

### 後方互換シム

`katrain/core/analysis/logic_difficulty.py` を完全シムに変更:

```python
# 旧名前（_プレフィックス付き）と新名前（_なし）の両方を提供
_compute_policy_difficulty = compute_policy_difficulty
_compute_transition_difficulty = compute_transition_difficulty
_compute_state_difficulty = compute_state_difficulty
_determine_reliability = determine_reliability
_get_root_visits = get_root_visits
_get_candidates_from_node = get_candidates_from_node
_normalize_candidates = normalize_candidates
_assess_difficulty_from_policy = assess_difficulty_from_policy
```

`__all__` には新旧両方を列挙し、`from logic_difficulty import X` も
`from logic_difficulty import _compute_X` も動作する状態に。

### 影響範囲

| ファイル | 修正必要 |
|---------|---------|
| `core/analysis/__init__.py` | × (シム経由で動作) |
| `core/analysis/logic.py` | × (シム経由で動作) |
| `core/analysis/logic_reliability.py` | × (lazy import でシム経由) |
| `tests/test_difficulty_metrics.py` | × (シム経由で動作、867 行・78 tests) |

→ **外部参照 4 ファイル無修正** でサブパッケージへの内部移行が完了。

## 検証結果

### テスト

| ファイル | 結果 |
|---------|:----:|
| `tests/test_difficulty_metrics.py` (867 行) | 78 PASS |
| `tests/test_difficulty_modifier.py` | PASS |
| `tests/test_critical_moves.py` (903 行) | PASS |
| `tests/test_beginner_hints_main.py` (Phase 187) | 137 PASS |
| `tests/test_summary_analyzer.py` | PASS |
| **合計** | **309 PASS** |

既存テストファイル無修正で全件通過 → シムの実効性を実証。

### lint / mypy

```
ruff check katrain/core/analysis/difficulty/ katrain/core/analysis/logic_difficulty.py
  → All checks passed

mypy katrain/core/analysis/difficulty/ katrain/core/analysis/logic_difficulty.py
  → no issues found in 9 source files
```

## Architecture Review B 系列進捗

| 案件 | 状態 |
|------|:----:|
| B1: engine TYPE_CHECKING 循環解消 | ✅ Phase 191 |
| **B2: logic_difficulty.py 分割** | ✅ **Phase 192（本 Phase）** |
| B3-Bn: 残り | 未着手 |

## 関連ドキュメント

- AGENTS.md 変更履歴エントリ
- `analysis/cluster_classifier.py` / `analysis/cluster_detectors.py` / `analysis/cluster_geometry.py`（参照パターン）
- `analysis/meaning_tags/` サブパッケージ構造（参照パターン）
- `analysis/models/` サブパッケージ構造（参照パターン）
- Phase 188 KifunarabeController 分割（God Class 分割パターン）
- Phase 191 TYPE_CHECKING 集約（依存関係の構造化パターン）

## 次の段階（任意）

1. **シム削除**: 全ての `from katrain.core.analysis.logic_difficulty` を新パスに書き換え後、シムを deprecated 化（Phase XXX）
2. **サブパッケージ間の dependency を整理**: 現状 `_io.py` → `models.py` の直接依存（`DIFFICULTY_MIN_*` 定数）。必要に応じて難易度関連の定数もサブパッケージ内に移動
3. **`_state.py` の実装拡張**: v1 placeholder のままなので、将来「候補数・分岐多様性」を実装する際に module 単位で分離できる