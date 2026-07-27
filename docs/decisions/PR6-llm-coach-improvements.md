# PR-06: LLM Coach 改善 — スキーマ文書整備・デッドコード除去

## 結論

PR-06 は **Lv2（軽微な修正群）** として、LLM Coach 調査で浮上したドキュメント乖離・軽微なバグ・デッドコードを一括で解消する。`main` への直接マージ可。

## 背景

PR-01（重大バグ即効修正）と PR-02（Summary 検証堅牢化）に続く、計画書 §6 のスコープ。プロンプトロジックや症状検出には触れず、周辺の保守性を底上げする。

## 対象

| # | 件名 | 修正場所 |
|---|------|---------|
| M1 | `docs/karte-schema.md` の `position_difficulty` 値集合を実装（`easy/normal/hard/only/unknown`）に同期 | docs/karte-schema.md:263 |
| M3 | `summary_json_export.py` の `total_loss` 丸めを 2 桁に統一（Phase 158-H 方針） | summary_json_export.py:376 |
| M8 | `karte_aggregator.py:432` の `or` 短絡による `0.0` 落ちを `is None` チェックに置換 | karte_aggregator.py:432 |
| S9 | `cli.py:562` の `{}` リテラル（f-string 忘れ）を解消 | cli.py:562 |
| S11 | `llm_validator.py:181` の未使用 `_MOVE_COORD_RE` を削除 | llm_validator.py:181 |
| S11 | `summary_validator.py:323` の `range(1, 7)` ループ境界を `range(1, 6)`（5 グループ）に修正 | summary_validator.py:323 |
| S11 | `lexicon.py:567 all_ja_terms()` の虚偽 docstring を「未使用」と明記 | lexicon.py:567 |

## スコープ外（PR-06 では行わない）

- **L4（エラーカルテが Markdown で `.json` に書かれる問題）**: 呼び出し側 (`karte_export.py`) との整合性が複雑で、`builder.py` 単体の修正ではテストが大量に書き直しになるため別 PR
- **S10（tones.py の未使用 API 削除）**: `check_prohibited` は Phase 269 まで validator が呼んでいたため「完全未使用」と言い切れない。削除ではなく docstring 更新が妥当だが、本 PR のスコープからは外す
- **S12（トークン予算ガード）**: Karte JSON 切断は LLM の挙動に影響するため、閾値設計から再検討が必要
- **S13（i18n 化）**: spinner i18n 統合は PR-05 と合わせて実施するのが自然

## リスク

- **低**: すべて「虚偽修正」「精度統一」「デッドコード削除」の範疇で、振る舞いに新機能は追加しない
- `range(1, 7) → range(1, 6)` の修正は `IndexError` 予防で、実害はない

## 検証

- `pytest tests/test_coach_cli.py tests/test_karte_export.py tests/test_coach_karte_aggregator.py tests/test_coach_summary_validator.py tests/test_coach_llm_validator.py tests/test_coach_lexicon.py` 全 pass
- `ruff check / format --check` 全 pass