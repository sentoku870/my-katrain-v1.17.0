# Phase 179: Beginner Hints Summary Extension

> AGENTS.md: 1.3 節「現在のフェーズ」参照
> 実装日: 2026-07-14
> 関連: Phase 91（MVP）/ Phase 92（MeaningTag fallback）/ Phase 178（kifunarabe docs）

---

## 1. 背景

### 1.1 既存の Beginner Hints（Phase 91-92）

`katrain/core/beginner/` に実装済み:

- **Phase 91（MVP）**: 4 つの構造検出器
  - `SELF_ATARI` / `IGNORE_ATARI` / `MISSED_CAPTURE` / `CUT_RISK`
  - 盤上の `Group` 構造から直接判定
- **Phase 92（拡張）**: 6 つの MeaningTag フォールバック
  - `LOW_LIBERTIES` / `SELF_CAPTURE_LIKE` / `BAD_SHAPE` / `HEAVY_GROUP` / `MISSED_DEFENSE` / `URGENT_VS_BIG`
  - バッチ解析時に `node.meaning_tag_id` で付与されたタグから逆引き

合計 10 カテゴリ。表示は右パネル `notes_panel` 内 `info` ScrollableLabel の末尾に
`[Hint] {title}: {body}` 形式で 1 行追加。

### 1.2 課題

ユーザーから「右下のミス・手の自由度・局面難易度の数値から初心者向けヒントみたいな
テンプレート機能が実装できないか？」との要望。既存実装では:

- 既存の数値行（`ミス: 悪（N点損）` / `手の自由度: 狭い` / `局面難易度: 難`）は表示
- ただし**ヒントとしては統合されておらず**、ユーザーが値を自力で解釈する必要
- `KataGo` 派生データ（`scoreStdev` / `ownership` / `policy entropy` 等）は Hint に未活用

### 1.3 解決方針

既存の Beginner Hints システムに**第 3 層「Summary Hint」**を追加。`Phase 91-92`
の Specific Hint とは独立した優先度チェーンで動作し、同じ `i18n` テンプレート
機構を再利用する。

---

## 2. 設計

### 2.1 3 層優先度チェーン

```
[Layer 1] Specific (既存 10 カテゴリ, severity 2-3)
  ├─ Structural (Phase 91: SELF_ATARI / IGNORE_ATARI / MISSED_CAPTURE / CUT_RISK)
  └─ MeaningTag  (Phase 92: LOW_LIBERTIES / ... / URGENT_VS_BIG)

[Layer 2] Summary (Phase 179 新規 9 カテゴリ, severity 0-2)
  ├─ Mistake     (severity 0-2): MISTAKE_BLUNDER / MISTAKE_MISTAKE / MISTAKE_GOOD
  ├─ Freedom     (severity 1)   : FREEDOM_ONLY_MOVE / NARROW / WIDE
  ├─ Difficulty  (severity 1)   : DIFFICULTY_TRICKY / CALM
  └─ KataGo      (severity 0)   : KATAGO_UNCERTAIN
```

同一 Layer 内では priority chain で最初のヒットを採用。Layer 1 → Layer 2 の
順で**両方表示**（Specific を残しつつ、Summary も追加する「併記」設計）。

### 2.2 SummaryHintContext（新規データクラス）

`core/beginner/models.py` に追加。Mistake / Freedom / Difficulty / KataGo
の 4 系統が共通の入力として受け取る純粋データ:

```python
@dataclass(frozen=True)
class SummaryHintContext:
    points_lost: float | None = None
    winrate_lost: float | None = None
    good_move_count: int = 0
    near_move_count: int = 0
    overall_difficulty: float | None = None
    is_reliable: bool = False
    score_stdev: float | None = None
    root_visits: int = 0
    move_number: int = 0
    is_endgame: bool = False
    score_loss_threshold_blunder: float = 8.0
    score_loss_threshold_mistake: float = 2.0
    score_stdev_threshold: float = 1.5
```

`GameNode` に直接依存しないので、detector は Kivy 非依存のままで
ユニットテストが容易。

### 2.3 9 新規カテゴリの判定ロジック

| カテゴリ | 発火条件 | severity |
|----------|----------|---------:|
| `MISTAKE_BLUNDER` | `pointsLost >= 8.0` | 2 |
| `MISTAKE_MISTAKE` | `2.0 <= pointsLost < 8.0` | 1 |
| `MISTAKE_GOOD` | `pointsLost < 0.5` AND `is_endgame` AND `root_visits >= 300` | 0 |
| `FREEDOM_ONLY_MOVE` | `good_move_count <= 1` (and `near > 0`) | 1 |
| `FREEDOM_NARROW` | `2 <= good_move_count <= 3` | 1 |
| `FREEDOM_WIDE` | `good_move_count >= 4` | 1 |
| `DIFFICULTY_TRICKY` | `overall_difficulty >= 0.7` AND `is_reliable` | 1 |
| `DIFFICULTY_CALM` | `overall_difficulty <= 0.3` AND `is_reliable` | 1 |
| `KATAGO_UNCERTAIN` | `score_stdev >= 1.5` AND `root_visits >= 200` | 0 |

信頼度ゲート:
- Structural Hint: `root_visits >= 200` (Phase 92 から継承)
- Summary Hint: `root_visits >= 100` (Phase 179 で緩和)
- `MISTAKE_GOOD` のみ追加で `root_visits >= 300` を要求（終盤の精度確保）

### 2.4 表示形式

ユーザー指示「併記：数値行 + Hint 両方表示」に従い、既存数値行を保持して
Hint 行を追加。右パネル `info` の表示順序:

```
[既存コメント]
[既存 KataGoStats]

ミス: 悪（3.5目損）
手の自由度: 狭い（0.80）
局面難易度: 難（0.72）⚠
  迷い=0.65 崩れ=0.80
[Hint] 致命的なミス: 形勢が大きく傾く一手でした。別の候補手も検討しましょう。
```

---

## 3. 実装

### 3.1 変更ファイル一覧

| 区分 | パス | 種別 | 行 |
|------|------|------|----|
| Core | `katrain/core/beginner/models.py` | 編集 | +132 |
| Core | `katrain/core/beginner/detector_mistake.py` | 新規 | +73 |
| Core | `katrain/core/beginner/detector_freedom.py` | 新規 | +64 |
| Core | `katrain/core/beginner/detector_difficulty.py` | 新規 | +64 |
| Core | `katrain/core/beginner/detector_katago.py` | 新規 | +56 |
| Core | `katrain/core/beginner/hints.py` | 編集 | +265 / -30 |
| Core | `katrain/core/beginner/__init__.py` | 編集 | +20 / -5 |
| GUI | `katrain/gui/controlspanel.py` | 編集 | +60 / -10 |
| GUI | `katrain/gui/features/settings_popup_state.py` | 編集 | +5 |
| GUI | `katrain/gui/features/settings_popup.py` | 編集 | +7 / -1 |
| GUI | `katrain/gui/features/settings_popup_savers.py` | 編集 | +15 / -3 |
| GUI | `katrain/gui/features/settings_popup_tabs/analysis_tab.py` | 編集 | +55 / -3 |
| Config | `katrain/config.json` | 編集 | +5 |
| i18n | `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` | 編集 | +60 |
| i18n | `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` | 編集 | +60 |
| i18n | `katrain/i18n/locales/{jp,en}/LC_MESSAGES/katrain.mo` | 再生成 | — |
| Test | `tests/test_beginner_hints.py` | 編集 | +3 / -1 |
| Test | `tests/test_beginner_hints_summary.py` | 新規 | +680 |

**合計: 約 +1500 行 / -50 行**

### 3.2 主要 API

```python
from katrain.core.beginner import (
    HintCategory, BeginnerHint, SummaryHintContext,
    compute_summary_hint, get_summary_hint_cached,
    detect_mistake_summary, detect_freedom_summary,
    detect_difficulty_summary, detect_katago_uncertain,
    MIN_SUMMARY_VISITS,
)
```

新規 `compute_summary_hint(node, summary_flags=...)` は Summary Layer 専用の
エントリ。`node` から `SummaryHintContext` を組み立てて 4 系統の detector を
順に呼び、最初に見つかった `BeginnerHint` を返す（priority chain）。

`get_summary_hint_cached(node, ...)` は `node._summary_hint_cache` に
`(flags_key, hint)` を保存。`flags_key` をキーに含むので、`summary_flags`
の変更時にキャッシュが正しく無効化される。

### 3.3 設定

`katrain/config.json` の `beginner_hints` セクションに 4 トグル追加:

```json
"beginner_hints": {
    "enabled": false,
    "board_highlight": true,
    "require_reliable": true,
    "summary_mistake": true,
    "summary_freedom": true,
    "summary_difficulty": true,
    "katago_uncertain": true
}
```

Settings UI の Analysis タブで個別 ON/OFF 可能。デフォルトはすべて ON
（既存ユーザー後方互換: 旧 `config.json` は新キーなしで動く、欠落時は
デフォルト True）。

### 3.4 i18n

新規 35 キー追加（既存 30 + 新規 35 = 65 ヒント + 8 設定）:

- `beginner_hint:<cat>:<title|body|why>` × 9 カテゴリ × 3 suffix = 27 ヒント
- `mykatrain:settings:summary_<key>` × 8 (label + desc)

日本語・英語ともユーザー向けの自然な文章を整備（LLM 不要）。

---

## 4. 互換性

### 4.1 後方互換

- 既存 10 カテゴリの挙動・i18n キーは完全不変
- 既存 `beginner_hints/enabled` フラグの解釈不変
- 既存 `test_beginner_hints.py`（25 テスト）は Phase 179 後も全件 PASS
- 既存 `config.json` から新キーが欠落してもデフォルト True で動作

### 4.2 テスト

`tests/test_beginner_hints_summary.py` 新規（680 行 / 65 テスト）:

- `TestHintCategoryExtension`: 9 カテゴリ存在 / 19 total / `is_structural` / `is_summary` / `config_key`
- `TestSummaryHintContext`: デフォルト値 / immutable
- `TestDetectMistakeSummary`: 7 テスト（blunder / mistake / neutral / good / endgame gate / visits gate / 負値 / custom threshold）
- `TestDetectFreedomSummary`: 6 テスト（境界値含む）
- `TestDetectDifficultySummary`: 6 テスト（unknown / unreliable / tricky / calm / normal / 境界値）
- `TestDetectKatagoUncertain`: 5 テスト（境界値・threshold 含む）
- `TestComputeSummaryHintPriority`: 7 テスト（priority chain 全体）
- `TestComputeSummaryHintFlags`: 4 テスト（per-category gating）
- `TestGetSummaryHintCached`: 3 テスト（キャッシュ動作）
- `TestShouldShowSummaryHint`: 5 テスト（pure function gating）
- `TestSummaryHintI18n`: 6 テスト（jp/en 全 35 キー存在確認 + 空 msgstr 検出）
- `TestModuleExports`: 3 テスト（`MIN_SUMMARY_VISITS == 100` / 後方互換）

### 4.3 アーキテクチャ整合

- `core/beginner/` は Kivy 非依存を維持（`tests/test_architecture.py` PASS）
- `core/beginner/detector_*.py` は `kivy*` を import しない
- `MIN_SUMMARY_VISITS = 100` を `core.beginner.hints` から export
- `HintCategory.config_key` プロパティで settings key マッピングを内包

---

## 5. 動作確認ポイント

### 5.1 起動

```bash
python -m katrain
```

→ 右パネル初心者ヒントトグル（`mykatrain:settings:beginner_hints`）を有効化。
棋譜を進めて各手で Hint 行が追加されることを確認。

### 5.2 テスト実行

```bash
uv run pytest tests/test_beginner_hints.py tests/test_beginner_hints_summary.py
uv run pytest tests/test_architecture.py -v
uv run ruff check katrain/core/beginner/ katrain/gui/
uv run mypy katrain/core/beginner/
```

### 5.3 i18n 再コンパイル

```bash
uv run pybabel compile -D katrain -d katrain/i18n/locales -f
```

---

## 6. 将来の拡張余地

- **Popup 化**: Beginner Hint を 1 行テキストから専用 Popup に格上げ
- **キーボードショートカット**: H キーで Hint を手動表示
- **候補手単位の Hint**: `parent.candidate_moves` の各手に Hint 付与
- **バッチ解析サマリー**: 棋譜全体での Mistake 傾向を集約（Curator 連携）
- **ownership / policy 派生**: 本 Phase で除外した `OWNERSHIP_INFLUENCE` /
  `POLICY_CONFLICT` を次フェーズで再評価
- **ユーザーカスタマイズ**: ユーザーが hint テンプレートを編集できる UI

---

## 7. 変更履歴

- 2026-07-14: Phase 179 初版作成（sentoku870 + opencode 共同作業）