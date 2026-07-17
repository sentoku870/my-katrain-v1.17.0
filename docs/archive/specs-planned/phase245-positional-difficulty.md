# Phase 245: POSITION_EVALUATION 自動検出の実装

## 概要

Phase 217 で `extract_winrate_scorelead_correlation()` を実装したが、`POSITION_EVALUATION`
症状の自動検出は「相関閾値不安定のため placeholder」とされていた。Phase 245 では
この placeholder を解消し、winrate/scoreLead ペアの相関分析から局面評価の歪みを
検出する detector を実装する。

## 動機

### 現状

- `SymptomId.POSITION_EVALUATION` は `symptom_index.py` に登録されている
- `auto_detected=False` で detector なし
- context_hint: 「複数局面の winrate/scoreLead 相関分析が必要（Phase 209.5 で実装検討）」
- Phase 217 で `extract_winrate_scorelead_correlation()` と `extract_winrate_scorelead_pairs()`
  を実装済み → 検出器の入力データは揃っている

### ユーザー影響

- LLM Coach が局面評価の歪み（大きなビハインドなのに高勝率と思っている、逆も然り）を
  警告できない
- SymptomId としては登録されているのに実際にはトリガーされない「空約束」状態

## スコープ

### 1. `detect_position_evaluation` 関数の追加（karte_detector.py）

```python
def detect_position_evaluation(
    karte: dict[str, Any],
    *,
    abs_correlation_threshold: float = 0.5,
) -> bool:
    """Detect POSITION_EVALUATION symptom via winrate/scoreLead correlation.

    局面評価が正確なら winrate と scoreLead は正相関（r > 0.5）。
    局面評価の歪み = 大きなビハインドなのに winrate が高い、またはその逆 → r < 0.5。
    強歪み = r < 0 まで反転。

    Phase 245: placeholder 解消。閾値は保守的に設定（0.5）。
    ゴールデン棋譜検証は次 Phase で精緻化予定。
    """
    pairs = extract_winrate_scorelead_pairs(karte)
    if len(pairs) < 8:  # 少なすぎると相関が不安定
        return False
    corr = extract_winrate_scorelead_correlation(karte)
    return abs(corr) < abs_correlation_threshold
```

### 2. `symptom_index.py` の POSITION_EVALUATION を更新

```python
Symptom(
    id=SymptomId.POSITION_EVALUATION,
    ja_label="局面評価の歪み",
    en_label="Position Evaluation",
    description_jp="scoreLead と winrate のズレを大きく見積もり損なう。",
    related_lexicon_ids=("score_lead", "winrate"),
    related_hint_category=None,
    difficulty_range=(CoachMode.DAN, CoachMode.EXPERT),
    auto_detected=True,  # Phase 245: was False
    detector=lambda c: detect_position_evaluation(c.karte),  # 新規
    context_hint="Phase 245 で相関分析ベースの detector を実装。閾値 0.5。",
)
```

### 3. テスト追加

- `tests/test_coach_karte_detector.py` に `TestDetectPositionEvaluation` クラス追加
  - 強い正相関の karte で False
  - 弱い相関 / 逆相関の karte で True
  - pairs < 8 の karte で False
  - threshold 境界値テスト

### 4. Calibration fixture 追加

`tests/test_coach_calibration_fixtures.py` または
`katrain/core/coach/calibration_fixtures.py` に `position_evaluation_distorted` を追加
（winrate/scoreLead が弱い相関 / 逆相関になる局面列を含む karte）

## 影響範囲

### ファイル

- `katrain/core/coach/karte_detector.py`: `detect_position_evaluation` 追加
- `katrain/core/coach/symptom_index.py`: POSITION_EVALUATION の `auto_detected=True` + `detector` 追加
- `tests/test_coach_karte_detector.py`: 4 テスト追加
- `katrain/core/coach/calibration_fixtures.py`: 1 fixture 追加
- `docs/archive/specs-planned/phase245-positional-difficulty.md`: 本仕様書
- `docs/01-roadmap.md` / `AGENTS.md`: Phase 245 マイルストーン追記

### リスク評価

- **中リスク**: 閾値 0.5 が妥当かは実棋譜で確認が必要
  - 対策: 閾値は configurable (`abs_correlation_threshold=0.5`) でテストから上書き可能
  - ゴールデン棋譜検証は次 Phase で精緻化
- **低リスク**: `extract_winrate_scorelead_correlation()` は Phase 217 で 14 テスト追加済み
  - 入力データ品質は担保されている

## 修正手順

1. `karte_detector.py` に `detect_position_evaluation` 関数追加
2. `symptom_index.py` の POSITION_EVALUATION を更新
3. テスト追加
4. fixture 追加
5. lint / 全体テスト確認
6. コミット + PR 作成
7. CI 通過 → マージ

## テスト計画

```bash
uv run pytest tests/test_coach_karte_detector.py -v
uv run pytest tests/test_coach_*.py tests/test_llm_coach.py -q
uv run ruff check katrain/core/coach/
uv run ruff format --check katrain/core/coach/
```

### 期待値

- 新規 4 テスト: 全パス
- 既存 coach 916 テスト: 全パス維持
- lint clean

## 成功基準

- [ ] `detect_position_evaluation` 関数が `karte_detector.py` にある
- [ ] POSITION_EVALUATION が `auto_detected=True` になり `detector` が設定されている
- [ ] 4 件の新規テストが追加されている
- [ ] 1 件の calibration fixture が追加されている
- [ ] 既存テストが全パス
- [ ] lint クリーン

## スケジュール

- 仕様書: 2026-07-17（本ドキュメント）
- 実装: 2026-07-17（同日中）
- テスト: 2026-07-17
- コミット + PR: 2026-07-17
- マージ: CI 通過後

## 関連 Phase

- Phase 217: `extract_winrate_scorelead_correlation` / `extract_winrate_scorelead_pairs` 実装 (placeholder)
- **Phase 245（本 Phase）**: detector 実装 + symptom_index 更新 + fixture 追加
- Phase 246（将来）: 閾値のゴールデン棋譜検証と精緻化
