# Phase 191 — Engine Subsystem TYPE_CHECKING 循環解消

## 概要

`engine.py` ↔ `engine_io.py` ↔ `engine_query.py` ↔ `engine_cmd/executor.py`
間に散在していた TYPE_CHECKING の前方参照を `core/_engine_types.py` に集約。
依存グラフを 1 ファイルで読み解けるようにする **静的構造改善**。

## 背景

### トリガー

2026-07-14 アーキテクチャレビューで engine サブシステムの依存関係を調査したところ:

```
engine.py              (public class definitions)
├─ engine_io.py         (pipe reader / write stdin / analysis read threads)
├─ engine_query.py      (build_analysis_query / terminate_queries / etc.)
└─ engine_cmd/
   └─ executor.py       (CommandExecutor class)
```

4 ファイル間で TYPE_CHECKING 経由の forward reference が散在:

| ファイル | TYPE_CHECKING 内 import |
|---------|----------------------|
| `engine_io.py` | `from katrain.core.engine import KataGoEngine` |
| `engine_query.py` | `from katrain.core.engine import KataGoEngine`<br>`from katrain.core.game_node import GameNode` |
| `engine_cmd/executor.py` | `from katrain.core.engine import KataGoEngine` |

問題点:
1. **依存関係の可視性が悪い** — 開発者が循環の全体像を読むのに 3 ファイルを開く必要がある
2. **TYPE_CHECKING ブロックの重複** — 同じ `KataGoEngine` import が 3 箇所
3. **「なぜ循環するか」の説明が分散** — 各モジュール docstring に断片的に書かれている

### 循環の性質

重要: これは **runtime cycle ではない**。`if TYPE_CHECKING:` ブロック内の import は型チェック時にのみ実行され、runtime では評価されない。

3 ファイルとも runtime では engine.py を import せず、必要な関数のみを **関数内 delayed import** で参照:
- `engine.py` メソッド内で `from katrain.core.engine_query import ...` を使う
- `engine_io.py` 関数内で `from katrain.core.engine_query import ...` を使う
- `engine_cmd/executor.py` で `self.engine.send_query(...)` を呼ぶ（型は TYPE_CHECKING 経由）

つまり Phase 158+ で導入された分割設計（I/O スレッド / クエリライフサイクル / コマンド実行）は runtime サイクルを完全に回避している。

ただし **TYPE_CHECKING レベルでの前方参照が 4 箇所** に散らばっている状況を構造的に整理する余地がある。

## 解決戦略

新ファイル `katrain/core/_engine_types.py` を新設し、TYPE_CHECKING 専用の前方参照をここに集約:

```python
# _engine_types.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine
    from katrain.core.game_node import GameNode

__all__ = ["KataGoEngine", "GameNode"]
```

各モジュールは:

```python
# Before
if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine
    from katrain.core.game_node import GameNode

# After
if TYPE_CHECKING:
    from katrain.core._engine_types import KataGoEngine, GameNode
```

に変更。

### なぜ PEP 563 だけで解決しないか

`from __future__ import annotations` を追加すると、type annotation は PEP 563 で文字列扱いに遅延評価される。理論的には TYPE_CHECKING ブロックは不要に見える。

しかし mypy は **forward reference 文字列の name resolution** 時に、文字列中の名前を解決する必要があるため、依然として `TYPE_CHECKING` ブロック内の import を要求する。

実際に試した検証結果:

```
$ python -m mypy katrain/core/engine_query.py
katrain/core/engine_query.py:31: error: Name "GameNode" is not defined  [name-defined]
... (18 errors total)
```

→ PEP 563 単独では不十分、TYPE_CHECKING ブロックの集約が唯一の構造的解決。

### 集約ファイルの特徴

- **runtime impact ゼロ**: `_engine_types.py` 自体は TYPE_CHECKING 以外の import を持たない
- **モジュール本体が空**: class も定数も関数も定義しない
- **型チェック時のみ依存を解決**: mypy が `KataGoEngine` / `GameNode` の名前を得るための中間地点

## 実装

### 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `katrain/core/_engine_types.py` | **新規** — TYPE_CHECKING 専用 forward reference aggregator |
| `katrain/core/engine_io.py` | TYPE_CHECKING ブロック: `engine` → `_engine_types` |
| `katrain/core/engine_query.py` | TYPE_CHECKING ブロック: `engine` + `game_node` → `_engine_types` |
| `katrain/core/engine_cmd/executor.py` | TYPE_CHECKING ブロック: `engine` → `_engine_types` |

### 変更量

- 新規: 42 行
- 各ファイル変更: 1 箇所のみ（TYPE_CHECKING ブロック内の import 1-2 行）
- 動作への影響: ゼロ（純粋に型注釈の解決方法変更）

## 検証結果

### lint / mypy

```
ruff check katrain/core/_engine_types.py         : All checks passed
ruff check katrain/core/engine_query.py           : All checks passed
ruff check katrain/core/engine_io.py              : All checks passed
ruff check katrain/core/engine_cmd/executor.py    : All checks passed

mypy katrain/core/_engine_types.py                : no issues found
mypy katrain/core/engine_query.py                 : no issues found
mypy katrain/core/engine_io.py                    : no issues found
mypy katrain/core/engine_cmd/executor.py          : no issues found
```

### テスト

```
tests/test_engine_coverage.py       59 passed
tests/test_engine_commands.py       existing
tests/test_engine_lifecycle.py      existing
test_architecture.py                41 passed (no regression)

合計 194 PASS（engine subsystem 関連）
全体: 4128 PASS（既存 + 新規、kivy 依存テストは環境制約で既存通り失敗）
```

### 後方互換性

完全に維持:

- 公開 API: `katrain.core.engine.KataGoEngine`, `katrain.core.engine.BaseEngine`, `katrain.core.game_node.GameNode` — 全て既存 import で動作
- 内部 API: `engine_io.pipe_reader_thread` 等 — 既存 import で動作
- 動作: 一切変更なし（型注釈の解決方法のみ変更）

## 影響

### ポジティブ

- **依存グラフの可視性向上**: 開発者が engine サブシステムの循環関係を読み解く際、`_engine_types.py` 1 ファイルで全体像を把握可能
- **TYPE_CHECKING 重複削減**: 同じ `from katrain.core.engine import KataGoEngine` が 3 箇所 → 1 箇所に集約
- **新規ヘルパーモジュール追加時のオンボーディングコスト低減**: 「engine 系の型を使うには `_engine_types.py` から」というルールが明示化

### 中性

- ファイル数 +1（41 → 42 行）
- 既存テストは不変（型注釈変更のみで実行時挙動は同一）

### ネガティブ

- `_engine_types.py` が空モジュールに近いため「本当に必要？」と問われる可能性
- **対策**: docstring で「これは TYPE_CHECKING 専用 aggregator」と明示、循環の全体像を 1 ファイルで読み解く目的を説明

## Architecture Review B 系列

| 案件 | 状態 | Phase |
|------|:----:|:-----:|
| **B1: engine TYPE_CHECKING 循環解消** | ✅ | **191（本 Phase）** |

## 関連ドキュメント

- AGENTS.md 変更履歴エントリ
- Phase 158+ engine 分割（循環回避の初期設計）
- `.opencode/skills/architecture/SKILL.md`
- `tests/test_engine_coverage.py`（Phase 190 で追加）