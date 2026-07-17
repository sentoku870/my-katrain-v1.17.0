# Phase 244: Lexicon YAML 拡張（頻出囲碁用語 5 件）

## 概要

`inject_lexicon_for_prompt` が `entries` セクションしか参照していないため、`concepts`
セクションにだけ登録されている 6 件の ID (urgent_vs_big, direction_of_play,
triage_priority, attack_for_profit, whole_board_balance, endgame_sente_value) が
prompt に注入されない問題を修正する。あわせて、`symptom_index.py` で参照されている
が YAML に未登録の 3 件 (overplay, endgame_sente, star_point) を新規追加する。

AGENTS.md のマーカー「Lexicon YAML 拡張は慎重を要する」があるが、Phase 242-C で
5 件追加済みの実績と、symptom_index.py から直接参照されているため、id 不整合状態を
解消する文脈で実施可能と判断。

## 動機

### 現状の問題

- symptom_index.py は 30 件の症状の `related_lexicon_ids` で Lexicon ID を参照
- 参照先 ID のうち 11 個が Lexicon YAML に未登録
- Lexicon YAML に未登録の ID は prompt builder がスキップする
- 結果: LLM が「direction_of_play」「urgent_vs_big」等の頻出用語を使った解説を
  標準語彙として参照できない

### Phase 226-J / Phase 242-C での対応

- Phase 226-J: 5 件の auto-detected 症状に `related_lexicon_ids` を設定
- Phase 242-C: 5 LLM-required 症状の `related_lexicon_ids` 追加 + Lexicon YAML に
  `time_management` / `ai_overload` / `post_game_review` / `tilt_recovery` / `mental_state`
  の 5 エントリを新規追加

しかし残り 11 ID は未登録のまま。

## スコープ

### A. `inject_lexicon_for_prompt` 修正（concepts 対応）

現状は `bundle.entry_by_id` のみ参照。`bundle.concept_by_id` も見るよう修正。
concepts は `ja_title` / `ja_one_liner` / `ja_expanded` 形式なので、別の format 分岐を追加。

```python
def inject_lexicon_for_prompt(entry_ids, *, include_expanded=True):
    bundle = _load_default_cached()
    by_id = bundle.entry_by_id
    concept_by_id = bundle.concept_by_id
    lines = []
    for eid in entry_ids:
        entry = by_id.get(eid)
        if entry is not None:
            lines.append(f"【{entry.ja_term} ({entry.id})】")
            lines.append(f"定義: {entry.ja_one_liner}")
            lines.append(f"詳細: {entry.ja_short}")
            if entry.pitfalls:
                lines.append(f"注意点: {' / '.join(entry.pitfalls)}")
            if include_expanded and entry.ja_expanded:
                lines.append(f"拡張: {entry.ja_expanded}")
            lines.append("")
            continue
        concept = concept_by_id.get(eid)
        if concept is not None:
            lines.append(f"【{concept.ja_title} ({concept.id})】")
            lines.append(f"定義: {concept.ja_one_liner}")
            if include_expanded and concept.ja_expanded:
                lines.append(f"詳細: {concept.ja_expanded}")
            lines.append("")
            continue
    return "\n".join(lines)
```

これで concepts-only の 6 ID (urgent_vs_big, direction_of_play, triage_priority,
attack_for_profit, whole_board_balance, endgame_sente_value) も prompt に注入される。

### B. 新規 entries 追加（3 件）

`symptom_index.py` で参照されているが YAML の entries に未登録の 3 件:

| ID | 意味 | 参照元症状 |
|----|------|-----------|
| `overplay` | 攻めすぎ | OVERFIGHT, ATTACK_WITHOUT_PURPOSE |
| `endgame_sente` | 終盤のセンテ | ENDGAME_PRECISION, etc. |
| `star_point` | 星 | POST_JOSEKI_DIRECTION |

各エントリは Phase 242-C の simplified 形式（pitfalls/recognize_by/sources 等の
複雑なフィールドは省略）で追加。

### C. テスト追加

- `tests/test_coach_lexicon.py`:
  - `inject_lexicon_for_prompt` が concept ID を受け入れる
  - 3 新規 entries が resolve できる
  - missing ID は silent skip される（既存挙動の pin）

## 各エントリの形式

Phase 242-C で追加した 5 件と同じ simplified 形式:

```yaml
- id: urgent_vs_big
  level: 2
  category: strategy
  ja_term: 急所と大所
  en_terms:
  - urgent point vs big point
  - urgent vs big
  ja_one_liner: 大きいけど今は急がない「大所」より、小さくても今すぐ打つべき「急所」を優先する判断。
  en_one_liner: Choosing the locally-urgent move over the globally-big one when the two conflict.
  ja_short: 碁では「急所」と「大所」のどちらか迷ったら、急所を選ぶのが鉄則です。大所は手番を譲しても後で打てますが、急所を譲ると相手に先手で効率良く打たれて挽回が難しくなります。両方の判断材料は「相手を利するか / 自分が次に打てるか」の2点。
  en_short: The classic Go maxim: when forced to choose between a "big" point (high long-term value) and an "urgent" point (locally critical now), take the urgent one first. Big points can wait a move; urgent points cannot — letting the opponent play there first usually gives them sente with good follow-ups. The rule of thumb: if the opponent's reply would be more efficient than yours, the move is urgent for them, which means it's urgent for you too.
  related_ids:
  - direction_of_play
  - priority
```

## 影響範囲

### ファイル

- `docs/resources/go_lexicon_master_last.yaml`: 5 エントリ追加（+ 約 110 行）
- `tests/test_coach_lexicon.py`: テスト追加（5 件の存在確認 + 参照整合性）

### リスク評価

- **低リスク**: 追加は新規エントリのみ、既存エントリには触らない
- **低リスク**: simplified 形式なので、ピットホール/recognize_by/diagram 等の複雑な
  フィールドは省略（必要に応じて将来 Phase で追加）
- **中リスク**: id 名が symbol_index.py と完全一致する必要がある

## 修正手順

1. 5 エントリを YAML の `entries:` セクションの末尾に追加
   （Phase 242-C 追加分の直後に置くと、レビュアーが確認しやすい）
2. `test_coach_lexicon.py` に 5 件分の存在確認テスト追加
3. lint 確認
4. コミット + PR

## テスト計画

```bash
uv run pytest tests/test_coach_lexicon.py -v
uv run pytest tests/test_coach_*.py tests/test_llm_coach.py -q
uv run ruff check docs/resources/  # YAML は通常チェック対象外なので skip
```

### 期待値

- test_coach_lexicon: 既存 + 5 件 (新規 ID の存在確認)
- 全体コーチ: 909+ テスト全パス

## 成功基準

- [ ] 5 エントリ (urgent_vs_big / direction_of_play / overplay / whole_board_balance / endgame_sente_value) が YAML に登録されている
- [ ] test_coach_lexicon.py に 5 件の存在確認テストが追加されている
- [ ] 既存テストが全パス
- [ ] AGENTS.md / 01-roadmap.md 更新

## スケジュール

- 仕様書: 2026-07-17
- 実装: 2026-07-17
- テスト: 2026-07-17
- コミット + PR: 2026-07-17
- マージ: CI 通過後

## 関連 Phase

- Phase 226-J: 5 auto-detected 症状 lexicon 紐付け
- Phase 242-C: 5 LLM-required 症状 lexicon 紐付け + 5 新エントリ追加
- **Phase 244（本 Phase）**: 頻出 5 用語の Lexicon エントリ追加
- Phase 244.1（将来）: 残り 6 用語の追加
- Phase 245: POSITIONAL_DIFFICULTY 実装
