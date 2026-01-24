# Phase 12 実装計画: MuZero 3分解難易度

> **ステータス**: ✅ 完了（PR #103 計算ロジック、PR #104 UI表示）
> **作成日**: 2026-01-13
> **完了日**: 2026-01-14
> **仕様書**: `docs/specs/muzero-difficulty.md`
> **修正レベル**: Lv3（複数ファイル）

---

## 0. 概要

### 0.1 目的
局面の「難しさ」を3つの性質（Policy/Transition/State）に分解し、以下の用途で活用する：
1. **難所抽出**: 1局の中で復習すべき局面を相対ランキングで抽出
2. **解説の出し分け**: Viewer Preset（Lite/Standard/Deep）に応じた説明の切替

### 0.2 非目的（v1でやらないこと）
- 難易度の絶対値で「この局面は難しい」と断定する
- 棋力評価・段級位推定への直接利用
- Top Movesフィルタ（Phase 11）への自動連動

### 0.3 スコープ
**In:**
- `DifficultyMetrics` dataclass（policy/transition/state/overall）
- 計算ロジック（`compute_difficulty_metrics()`）
- 難所抽出関数（`extract_difficult_positions()`）
- 信頼性ガード（visits/候補数による判定）
- 30-40件のユニットテスト

**Out:**
- UI表示（Phase 12.5 で検討）
- Viewer Preset連動（将来）
- 棋譜内正規化（v2）

---

## 1. データモデル

### 1.1 新規 Dataclass

```python
# katrain/core/analysis/models.py に追加

@dataclass(frozen=True)
class DifficultyMetrics:
    """局面難易度の3分解メトリクス（Phase 12）。

    Attributes:
        policy_difficulty: 迷いやすさ（候補が拮抗）。0-1、高いほど難。
        transition_difficulty: 崩れやすさ（一手のミスが致命傷）。0-1、高いほど難。
        state_difficulty: 盤面の複雑さ（v1は控えめ）。0-1、高いほど難。
        overall_difficulty: 合成値（抽出・表示の優先度用）。0-1。
        is_reliable: 信頼性フラグ（visits/候補数が十分か）。
        debug_factors: 計算の内訳（デバッグ用、任意）。
    """
    policy_difficulty: float
    transition_difficulty: float
    state_difficulty: float
    overall_difficulty: float
    is_reliable: bool
    debug_factors: Optional[Dict[str, Any]] = None
```

### 1.2 定数

```python
# 信頼性ガードの閾値
DIFFICULTY_MIN_VISITS = 500       # 最低探索数
DIFFICULTY_MIN_CANDIDATES = 3     # 最低候補手数

# overall 合成の重み（v1推奨）
DIFFICULTY_WEIGHT_POLICY = 0.45
DIFFICULTY_WEIGHT_TRANSITION = 0.45
DIFFICULTY_WEIGHT_STATE = 0.10

# Policy難易度の正規化パラメータ
POLICY_GAP_MAX = 5.0  # この差以上は「迷いなし」(difficulty=0)

# Transition難易度の正規化パラメータ
TRANSITION_DROP_MAX = 10.0  # Top1→Top3の落差がこれ以上で「崩れやすい」(difficulty=1)

# 難所抽出のデフォルト設定
DEFAULT_DIFFICULT_POSITIONS_LIMIT = 10
```

---

## 2. 計算ロジック

### 2.1 Policy Difficulty（迷い）

Top1とTop2の評価差が小さいほど「迷いやすい」。

```python
def _compute_policy_difficulty(candidates: List[Dict]) -> float:
    """候補手の拮抗度から Policy 難易度を計算。

    Args:
        candidates: KataGo候補手リスト（order順でソート済み）

    Returns:
        0-1 の難易度値。候補が拮抗しているほど高い。
    """
    if len(candidates) < 2:
        return 0.0

    top1_score = candidates[0].get("scoreLead", 0.0)
    top2_score = candidates[1].get("scoreLead", 0.0)
    gap = abs(top1_score - top2_score)

    # gap が 0 なら difficulty=1、POLICY_GAP_MAX 以上なら difficulty=0
    difficulty = max(0.0, 1.0 - gap / POLICY_GAP_MAX)
    return difficulty
```

### 2.2 Transition Difficulty（崩れやすさ）

Top1と下位候補（Top3-5）の評価差が大きいほど「一手で崩れやすい」。

```python
def _compute_transition_difficulty(candidates: List[Dict]) -> float:
    """評価の急落度から Transition 難易度を計算。

    Args:
        candidates: KataGo候補手リスト（order順でソート済み）

    Returns:
        0-1 の難易度値。少し外すと急に悪化するほど高い。
    """
    if len(candidates) < 3:
        return 0.0

    top1_score = candidates[0].get("scoreLead", 0.0)
    # Top3-5の平均（存在する分だけ）
    lower_candidates = candidates[2:5]
    if not lower_candidates:
        return 0.0

    lower_avg = sum(c.get("scoreLead", 0.0) for c in lower_candidates) / len(lower_candidates)
    drop = abs(top1_score - lower_avg)

    # drop が TRANSITION_DROP_MAX 以上なら difficulty=1
    difficulty = min(1.0, drop / TRANSITION_DROP_MAX)
    return difficulty
```

### 2.3 State Difficulty（盤面の複雑さ）

v1は控えめに、有力候補の数のみで簡易計算。

```python
def _compute_state_difficulty(candidates: List[Dict], threshold: float = 2.0) -> float:
    """盤面の複雑さ（有力候補数）から State 難易度を計算。

    Args:
        candidates: KataGo候補手リスト
        threshold: この損失以下を「有力候補」とみなす（目数）

    Returns:
        0-1 の難易度値。有力候補が多いほど高い。
    """
    if not candidates:
        return 0.0

    top1_score = candidates[0].get("scoreLead", 0.0)
    viable_count = sum(
        1 for c in candidates
        if abs(top1_score - c.get("scoreLead", 0.0)) <= threshold
    )

    # 1-3個: 低、4-6個: 中、7個以上: 高
    if viable_count <= 3:
        return 0.0
    elif viable_count <= 6:
        return 0.5
    else:
        return 1.0
```

### 2.4 統合関数

```python
def compute_difficulty_metrics(
    candidates: List[Dict],
    root_visits: Optional[int] = None,
) -> DifficultyMetrics:
    """局面の難易度メトリクスを計算。

    Args:
        candidates: KataGo候補手リスト
        root_visits: ルートの探索数（信頼性判定用）

    Returns:
        DifficultyMetrics インスタンス
    """
    # 信頼性チェック
    is_reliable = (
        (root_visits is None or root_visits >= DIFFICULTY_MIN_VISITS)
        and len(candidates) >= DIFFICULTY_MIN_CANDIDATES
    )

    # 各成分の計算
    policy = _compute_policy_difficulty(candidates)
    transition = _compute_transition_difficulty(candidates)
    state = _compute_state_difficulty(candidates)

    # overall 合成
    overall = (
        DIFFICULTY_WEIGHT_POLICY * policy
        + DIFFICULTY_WEIGHT_TRANSITION * transition
        + DIFFICULTY_WEIGHT_STATE * state
    )

    # unreliable の場合は overall を減衰
    if not is_reliable:
        overall *= 0.7

    return DifficultyMetrics(
        policy_difficulty=policy,
        transition_difficulty=transition,
        state_difficulty=state,
        overall_difficulty=overall,
        is_reliable=is_reliable,
        debug_factors={
            "policy_gap": ...,  # 実装時に追加
            "transition_drop": ...,
            "viable_count": ...,
        },
    )
```

---

## 3. 難所抽出

### 3.1 関数定義

```python
def extract_difficult_positions(
    moves: List[MoveEval],
    limit: int = DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    min_move_number: int = 10,
    exclude_unreliable: bool = True,
) -> List[Tuple[int, MoveEval, DifficultyMetrics]]:
    """1局から難所候補を抽出。

    Args:
        moves: MoveEval リスト（解析済み）
        limit: 抽出する最大局面数
        min_move_number: この手数以降のみ対象（序盤を除外）
        exclude_unreliable: 信頼性の低い局面を除外するか

    Returns:
        (move_number, MoveEval, DifficultyMetrics) のリスト（overall降順）
    """
    results = []
    for move in moves:
        if move.move_number < min_move_number:
            continue

        # candidates は move.analysis から取得（実装時に調整）
        candidates = move.analysis.get("moveInfos", []) if move.analysis else []
        root_visits = move.analysis.get("rootInfo", {}).get("visits") if move.analysis else None

        metrics = compute_difficulty_metrics(candidates, root_visits)

        if exclude_unreliable and not metrics.is_reliable:
            continue

        results.append((move.move_number, move, metrics))

    # overall 降順でソート
    results.sort(key=lambda x: x[2].overall_difficulty, reverse=True)

    return results[:limit]
```

---

## 4. ファイル構成

### 4.1 変更ファイル

| ファイル | 変更内容 | 行数 |
|----------|----------|------|
| `katrain/core/analysis/models.py` | DifficultyMetrics, 定数 | +50 |
| `katrain/core/analysis/logic.py` | compute_difficulty_metrics, extract_difficult_positions | +120 |
| `katrain/core/analysis/__init__.py` | 再エクスポート | +10 |
| `tests/test_difficulty_metrics.py` | ユニットテスト（新規） | +300 |

**合計**: 約480行（テスト含む）

### 4.2 新規ファイル

- `tests/test_difficulty_metrics.py` - Phase 12 専用テスト

---

## 5. テスト計画

### 5.1 テストカテゴリ

| カテゴリ | テスト内容 | 件数 |
|----------|----------|------|
| Policy | gap=0で1.0、gap>=MAX で0.0、中間値 | 5 |
| Transition | drop=0で0.0、drop>=MAXで1.0、中間値 | 5 |
| State | 候補1-3個で0.0、4-6個で0.5、7+で1.0 | 4 |
| Overall | 重み合成の確認、unreliable減衰 | 4 |
| Reliability | visits/候補数の閾値判定 | 4 |
| 境界値 | 空リスト、候補1件、候補2件 | 5 |
| 抽出 | limit、min_move_number、ソート順 | 6 |
| 統合 | 複数局面のランキング | 3 |

**合計**: 約36件

### 5.2 テストデータ

```python
# Fixture: 標準的な候補手リスト
FIXTURE_CANDIDATES_BALANCED = [
    {"order": 0, "scoreLead": 2.0, "move": "D4"},
    {"order": 1, "scoreLead": 1.8, "move": "E5"},  # gap=0.2 → policy高
    {"order": 2, "scoreLead": 1.5, "move": "C3"},
    {"order": 3, "scoreLead": 1.0, "move": "F6"},
    {"order": 4, "scoreLead": 0.5, "move": "G7"},
]

FIXTURE_CANDIDATES_CLEAR_BEST = [
    {"order": 0, "scoreLead": 5.0, "move": "D4"},
    {"order": 1, "scoreLead": 0.0, "move": "E5"},  # gap=5.0 → policy低
    {"order": 2, "scoreLead": -1.0, "move": "C3"},
]
```

---

## 6. 実装手順

### Step 1: models.py に Dataclass と定数を追加
- DifficultyMetrics dataclass
- 閾値定数（DIFFICULTY_MIN_VISITS 等）
- 重み定数（DIFFICULTY_WEIGHT_* 等）

### Step 2: logic.py に計算ロジックを追加
- `_compute_policy_difficulty()`
- `_compute_transition_difficulty()`
- `_compute_state_difficulty()`
- `compute_difficulty_metrics()`
- `extract_difficult_positions()`

### Step 3: __init__.py で再エクスポート
- DifficultyMetrics
- 定数
- 関数

### Step 4: テスト作成
- `tests/test_difficulty_metrics.py`

### Step 5: 全テスト実行・確認
- `uv run pytest tests`

---

## 7. 受け入れ条件

### 7.1 機能要件
- [ ] `compute_difficulty_metrics()` が 3成分 + overall を返す
- [ ] 各成分が 0-1 の範囲に収まる
- [ ] `is_reliable` が visits/候補数で正しく判定される
- [ ] `extract_difficult_positions()` が overall 降順でソートする
- [ ] unreliable 局面が抽出から除外される（オプション）

### 7.2 品質要件
- [ ] 全テストがパス（既存535件 + 新規36件 = 571件）
- [ ] 既存機能にリグレッションなし

### 7.3 ドキュメント要件
- [ ] 関数に docstring 付与
- [ ] models.py の Dataclass に Attributes 記載

---

## 8. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| 計算が重い | 解析時間増加 | 遅延計算（必要時のみ計算）で回避 |
| 正規化パラメータが不適切 | 難易度が偏る | ログ出力で調整可能に、v2で棋譜内正規化 |
| 既存コードとの整合性 | リグレッション | MoveEval との連携は最小限に（独立計算） |

---

## 9. 将来の拡張（v2以降）

- **棋譜内正規化**: percentile ベースで安定化
- **局面タイプ推定**: ヨセ/攻め合い等の分類
- **State難易度強化**: 盤面特徴量の活用
- **UI表示**: 難易度バッジ、ツールチップ
- **Viewer Preset連動**: 解説の出し分け実装

---

## 10. 決定事項の確認

ユーザーに確認したい点：

1. **score vs winrate**: 計算に `scoreLead` を使用（仕様書推奨）でよいか？
2. **State難易度**: v1は簡易版（候補数のみ）でよいか、それとも0固定にするか？
3. **抽出のデフォルト**: limit=10、min_move_number=10 でよいか？

---

## 付録A: Phase 11 との比較

| 項目 | Phase 11 (PV Filter) | Phase 12 (Difficulty) |
|------|---------------------|----------------------|
| 目的 | 候補手の表示フィルタ | 局面の難易度分解 |
| 入力 | 候補手リスト | 候補手リスト + visits |
| 出力 | フィルタ済みリスト | DifficultyMetrics |
| UI連動 | 即時（盤面表示） | 将来（Phase 12.5） |
| テスト | 30件 | 36件（予定） |

---

## 付録B: 仕様書との対応

| 仕様書セクション | 実装計画セクション | 備考 |
|------------------|-------------------|------|
| 5. 入出力 | 1. データモデル | DifficultyMetrics |
| 6. 信頼度ガード | 2.4 統合関数 | is_reliable |
| 7.1 Policy | 2.1 | Top1-Top2差 |
| 7.2 Transition | 2.2 | Top1→Top3-5落差 |
| 7.3 State | 2.3 | 有力候補数（v1簡易版） |
| 8. 正規化と合成 | 2.4 | 固定スケール（v1） |
| 9. 難所抽出 | 3.1 | extract_difficult_positions |
