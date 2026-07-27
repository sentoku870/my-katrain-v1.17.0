# Karte / Summary JSON Schema Reference

> **Phase 233**: 単局カルテ（Karte）と複数局サマリ（Summary）の JSON
> スキーマを 1 箇所に集約した正本ドキュメント。Phase 149 / 153 / 155 /
> 157 / 158 / 225 での拡張、Phase 221 / 227 / 228 でのサマリ対応、
> Phase 231 / 232 でのリファクタを反映した最新版（**2026-07-24**）。

このドキュメントは現役スキーマ v3.5 を対象とする。古い v2.x 系の
JSON を開いた場合のマイグレーションは**未実装**（v2 系はゴールデン
テストでも対象外）。

---

## 1. 全体像

### 1.1 2 種類の JSON レポート

myKatrain は **2 種類の JSON レポート** を出力する。GUI / CLI / テストは
同じダウンストリーム処理系で扱えるよう、Phase 221 で型判別を統一した。

| 種類 | 1 ファイルあたりの局数 | 生成元 | ファイル名例 |
|------|----------------------|--------|--------------|
| **Karte** | 1 局 | `build_karte_json_string()` | `karte_<date>_<id>.json` |
| **Summary** | N 局 | `build_summary_json()` | `summary_<date>_<id>.json` |

### 1.2 型判別ロジック（`katrain.core.coach.json_type.detect_json_type`）

Phase 226-C C4 で karte 優先判定に修正済み。優先順位:

1. **karte 判定**: `weaknesses` が dict かつ `important_moves` が非空 list
2. **summary 判定**:
   - `meta.games_analyzed` 存在
   - `meta.game_count > 1`
   - `players` block 存在
   - `phase_x_mistake` 存在（fallback）
3. **unknown**: どれにもマッチしない

> **注意**: `meta.game_count == 1` の単局は karte 扱い（`game_count` だけでは
> summary と判定しない）。`games_analyzed` の存在を summary の正本マーカーとする。

### 1.3 主要エントリポイント（Phase 231 / 232 リファクタ後）

```python
# 単局カルテ
from katrain.core.reports.karte import build_karte_json_string, build_karte_json

# 内部実装
from katrain.core.reports.karte.builder import build_karte_json_string
from katrain.core.reports.karte.builder import _build_karte_json_string_impl  # Phase 232 rename

# 複数局サマリ
from katrain.core.reports.summary_report import build_summary_report
from katrain.core.reports.summary_json_export import build_summary_json

# CLI（Kivy 不要）
python -m katrain.core.coach.cli <karte.json>          # 単局
python -m katrain.core.coach.cli <summary.json> --summary-mode  # 複数局
```

> **Phase 232 削除済み**: `katrain.core.reports.karte_report` 互換シム。
> 旧名 `build_karte_report` での import は `ImportError` になる。

---

## 2. 単局カルテ（Karte）スキーマ v3.5

### 2.1 トップレベル

```python
class KarteReport(TypedDict):
    schema_version: str                              # 常に "3.5"
    meta: MetaData
    summary: dict[str, Any]
    important_moves: list[MistakeItem]
    weaknesses: dict[str, list[WeaknessItem]] | None        # {"black": [...], "white": [...]}
    weaknesses_meta: dict[str, WeaknessMeta] | None          # Phase 158-I
    weaknesses_by_tag: dict[str, list[WeaknessTagItem]]     # v3.5 追加（§2.6a）
    score_trajectory: list[ScoreTrajectoryPoint]            # v3.5 追加（§2.6b）
    mistake_streaks: dict[str, list[StreakItem]] | None
    critical_3: dict[str, list[CriticalMoveItem]] | None    # {"black": [...], "white": [...]}
    data_quality: DataQualityStats | None
    reason_tags_distribution: dict[str, dict[str, int]] | None
    win_loss_analysis: dict[str, Any] | None                # Phase 154-D
    loss_progression: list[dict[str, Any]] | None
    opponent_strength_loss_correlation: None                # v3.5 から常に None（単局では相関不能）
```

### 2.2 `meta` セクション

| フィールド | 型 | 必須 | 説明 |
|----------|----|----|------|
| `schema_version` | `str` | ✓ | 常に `"3.5"` |
| `schema_hash` | `str` | ✓ | Phase 158-I 追加。schema_version + 各種定数の SHA-1 先頭 8 文字。LLM 側でこのプロジェクトのビルドバージョンを識別 |
| `run_id` | `str` | ✓ | `run_<ts>_<8文字ハッシュ>` 形式。同一生成実行内の一意性保証 |
| `game_id` | `str` | ✓ | `Game.game_id` または `unknown` |
| `generated_at` | `str` | ✓ | `"YYYY-MM-DD HH:MM:SS"` 形式 |
| `source_filename` | `str` | ✓ | 解析元 SGF のファイル名（拡張子含む） |
| `date` | `str \| None` | - | SGF の `DT` プロパティ |
| `players` | `{"black": str, "white": str}` | ✓ | PB / PW プロパティ |
| `result` | `str \| None` | - | `B+R` / `W+2.5` 等 |
| `komi` | `float` | ✓ | コミ |
| `handicap` | `int` | ✓ | ハンディキャップ数 |
| `board_size` | `[int, int]` | ✓ | 盤サイズ（[19, 19] 形式） |
| `skill_preset` | `str` | ✓ | `"beginner"` / `"standard"` / `"advanced"` / `"auto"` |
| `loss_unit` | `str` | ✓ | 常に `"territory_points"` |
| `score_perspective` | `str` | ✓ | v3.5 追加。常に `"black"`。`score_before` / `score_after` / `score_trajectory` が黒視点（正=黒リード）であることを明示 |
| `definitions` | `Definitions \| None` | - | opt-in (`include_definitions=True` 時のみ埋まる) |
| `player_info` | `{"black": {"name": str, "rank": str \| None, "color": "B"}, "white": {..., "color": "W"}}` | - | Phase 225.6 追加。SGF BR/WR から抽出。`color` は Phase 236 追加の安定識別子 |

### 2.3 `summary` セクション

```python
{
    "total_moves": int,
    "total_points_lost": {
        "black": float,    # 2 桁丸め（Phase 158-H）
        "white": float,
    },
    "mistake_distribution": {
        "black": {"good": int, "inaccuracy": int, "mistake": int, "blunder": int},
        "white": {"good": int, "inaccuracy": int, "mistake": int, "blunder": int},
    },
}
```

### 2.4 `important_moves` セクション

```python
class MistakeItem(TypedDict):
    # v3.5: 単局カルテでは game_name / game_id を省略（全手が meta と同値で冗長なため）。
    #       Summary の top_mistakes では複数局識別のため引き続き付与される。
    move_number: int
    player: str                              # "black" | "white"
    coords: str                              # GTP 座標
    phase: str                               # "opening" / "middle" / "endgame"
    loss_clamped: float                      # 0.0 以上にクランプ
    loss_raw: float | None
    importance: float                        # 0.0+, 大きいほど重要
    mistake_type: str                        # "inaccuracy" / "mistake" / "blunder"
    reason_codes: list[str]                  # Phase 158-F で正規化済み
    primary_tag: str | None                  # MeaningTagId enum value
    # --- v3.5 (2026-07) 追加: コーチングコンテキスト ---
    winrate_lost: float | None               # この手の勝率損失 (0.0-1.0, 4桁丸め)
    score_before: float | None               # 着手前の形勢 (黒視点, 2桁丸め)
    score_after: float | None                # 着手後の形勢 (黒視点, 2桁丸め)
    score_stdev: float | None                # KataGo root scoreStdev (2桁丸め)
    difficulty_score: float | None           # 局面難易度 0.0-1.0 (大きいほど難しい)
```

> v3.5 の新規 5 フィールドは、解析データがない手（未解析・旧 KataGo）では
> すべて `None` になる。`score_before` / `score_after` は**黒視点**
> （`meta.score_perspective` 参照）。これらの追加により、LLM は
> 「どれくらいのリード局面でどれだけ落としたか」を語れるようになり、
> coach 層の勝率系・局面評価系の症状検出器（EVALUATION_ERRORS /
> POSITION_EVALUATION 等）も実データで動作する。

### 2.5 `weaknesses` セクション

Phase 149 C-3 で再導入。`{"black": [...], "white": [...]}` の dict で、
各 player について**上位 2 件**の弱点（phase × category 単位）を返す。

```python
class WeaknessItem(TypedDict):
    phase: str                               # "opening" / "middle" / "endgame"
    category: str                            # "INACCURACY" / "MISTAKE" / "BLUNDER"
    count: int
    total_loss: float                        # 2 桁丸め
    avg_loss: float
    confidence: str                          # "low" / "medium" / "high" (Karte 全体)
    evidence: list[MoveEvidence]             # 代表手（通常 1-3 件）

class MoveEvidence(TypedDict):
    move_number: int
    gtp: str
    loss: float
    category: str
```

### 2.6 `weaknesses_meta` セクション（Phase 158-I）

弱点集計がプレイヤー損失の**何 % をカバーしているか**を示す。
LLM が「weakness A: 18.5 points」と読んだ時に、それがプレイヤー損失
全体の何割に相当するかを即座に把握できる。

```python
class WeaknessMeta(TypedDict):
    covered_count: int                       # weakness bucket に含まれた手数
    total_count: int                         # プレイヤー側の非ゼロ損失手数
    coverage_pct: float                      # covered_count / total_count × 100
    covered_loss: float                      # covered された手の合計 loss
    total_loss: float                        # プレイヤー損失合計
    loss_coverage_pct: float                 # covered_loss / total_loss × 100
```

### 2.6a `weaknesses_by_tag` セクション（v3.5 追加）

`weaknesses`（phase × category）が「いつ・どれくらい」の診断軸なのに対し、
こちらは**意味タグ（12 種類の診断カテゴリ）軸**で「どんな種類のミスか」を
集計する。LLM は「死活の誤判断が 3 件・計 15.0 目」のような、コーチングに
直結する弱点の言語化ができる。

```python
class WeaknessTagItem(TypedDict):
    tag: str                                 # MeaningTagId enum value（例: "life_death_error"）
    count: int                               # このタグの重要ミス手数
    total_loss: float                        # 2 桁丸め
    avg_loss: float
    evidence: list[MoveEvidence]             # 代表手（信頼度連動で 1-3 件）
```

- 集計対象: `important_moves` に分類済みの意味タグを持つ手（同色、タグ非 None）
- 並び順: `total_loss` 降順（同値はタグ名昇順）、**上位 3 タグ**まで
- タグが付かなかった場合は空リスト

### 2.6b `score_trajectory` セクション（v3.5 追加）

形勢（scoreLead）の推移を **10 手ごと + 最終手** でサンプリングした
コンパクトなカーブ（19 路で ~25 点・約 1KB）。`loss_progression` が
「損失の分布」しか示さないのに対し、こちらは実際のリード推移なので、
LLM は「終始劣勢」「中盤で逆転」「大きくリード後に崩壊」といった
**対局の流れ**を叙述できる。

```python
class ScoreTrajectoryPoint(TypedDict):
    move: int                                # 手数（1-indexed）
    score: float                             # その手後の形勢（黒視点・1 桁丸め）
```

- 視点は常に黒（`meta.score_perspective` 参照）
- 未解析手（`score_after` が None）はサンプルを欠番（0 を捏造しない）

### 2.7 `mistake_streaks` セクション

連続ミスのストリーク。`{"black": [...], "white": [...]}` 形式。

```python
class StreakItem(TypedDict):
    start_move: int
    end_move: int
    move_count: int
    total_loss: float
    avg_loss: float
    moves: list[MoveEvidence]
```

> **Phase 158-F**: 閾値を `MISTAKE_STREAK_THRESHOLD_LOSS = 2.0` /
> `MISTAKE_STREAK_MIN_CONSECUTIVE = 2` に緩和。以前は 20 点以上の
> 「致命的ミス」しか拾えなかった。

### 2.8 `critical_3` セクション

各プレイヤー上位 3 件の致命的ミス（`select_critical_moves` 由来）。

```python
class CriticalMoveItem(TypedDict):
    move_number: int
    gtp_coord: str
    player: str                              # "B" / "W"
    score_loss: float
    meaning_tag_id: str | None               # MeaningTagId enum value
    meaning_tag_label: str | None            # タグの人間可読ラベル（lang 依存）
    game_phase: str
    position_difficulty: str                 # "easy" / "normal" / "hard" / "only" / "unknown"
    area: str | None
    reason_tags: list[str]                   # v3.5 から REASON_CODE_ALIASES 正規化済み
    complexity_discounted: bool
    best_move: str | None                    # v3.5 追加。着手前局面の KataGo 最善手 (GTP)
```

> v3.5 の `best_move` は pre-move ノード（`node.parent`）の候補手リスト
> 先頭（order=0）から取得する。LLM がルール 2（座標の捏造禁止）を
> 守ったまま「正解の方向性」を述べられるようにするためのフィールド。

> **Phase 158-G**: `player_filter` を渡して greedy セレクタが該当
> プレイヤーの候補のみから選ぶように修正。**Phase 158-H**: pre-classified
> moves を渡して re-classify せず同じ分類を再利用。

### 2.9 `data_quality` セクション

```python
class DataQualityStats(TypedDict):
    confidence_level: str                    # "high" / "medium" / "low"
    total_moves: int
    moves_with_visits: int
    coverage_pct: float
    reliable_count: int
    reliability_pct: float
    low_confidence_count: int
    low_confidence_pct: float
    avg_visits: int
    max_visits: int
    effective_threshold: int
    is_low_reliability: bool
    visits: {                                # Phase 158-I 追加
        "min": int | None,
        "max": int | None,
        "avg": int | None,
        "stddev": float | None,
    }
    zero_visits_count: int                   # 0-visits があった場合のみ
```

### 2.10 `reason_tags_distribution` セクション

`{"black": {"liberties": 5, "heavy": 3, ...}, "white": {...}}` 形式。
Phase 158-F で `REASON_CODE_ALIASES` によりタグ名が正規化される
（例: `low_liberties` → `liberties`）。

### 2.11 `win_loss_analysis` / `loss_progression` / `opponent_strength_loss_correlation`

Phase 154-D / 155-D で追加。詳細は各 Phase のスペックを参照:
- Phase 154-D: 勝ち負け分析 + 損失進行
- Phase 155-D: 対局相手強度の損失相関

---

## 3. 複数局サマリ（Summary）スキーマ v3.5

### 3.1 トップレベル

```python
class SummaryReport(TypedDict):
    schema_version: str                              # 常に "3.5"
    meta: MetaData
    games: list[GameMeta]
    players: dict[str, SummaryPlayerStats]           # プレイヤー名 → 統計
    loss_progression: LossProgressionByType | None   # Phase 157-C
    # Phase 157-D: top-level win_loss_analysis 削除
    # Phase 154-D: per-player win/loss は players[...].win_loss_analysis に
```

### 3.2 `meta` セクション（Summary 用拡張）

Karte と同じだが、以下が追加:

| フィールド | 型 | 説明 |
|----------|----|------|
| `games_analyzed` | `int` | 解析対象局数（Summary 固有の正本マーカー） |
| `data_status` | `str` | Phase H-4 追加。`"computed"` / `"insufficient_data"` / `"not_applicable_no_games"` |
| `games_by_type` | `{"even": int, "handicapped": int, "unknown": int}` | Phase 157-C 追加 |
| `date_range` | `[str, str] \| None` | 解析対象局の日付範囲 |

### 3.3 `players.<name>.mistakes` セクション（Shape B）

Phase 228-A で実 export シェーマに対応。**真の summary 出力**は
このシェーマで書かれている。

```json
{
    "mistakes": {
        "good":       {"count": 310, "pct": 79.9, "denominator": 388, "avg_loss": 0.28, "total_loss": 86.8},
        "inaccuracy": {"count": 51,  "pct": 13.1, "denominator": 388, "avg_loss": 3.11, "total_loss": 158.6},
        "mistake":    {"count": 22,  "pct": 5.7,  "denominator": 388, "avg_loss": 5.69, "total_loss": 125.2},
        "blunder":    {"count": 5,   "pct": 1.3,  "denominator": 388, "avg_loss": 19.04, "total_loss": 95.2}
    }
}
```

> カテゴリは `_PLAYER_MISTAKE_CATEGORIES = ("blunder", "mistake", "inaccuracy", "good")`
> の順（severity 降順）で出力される。LLM プロンプトビルダはこの順序を
> 前提に severity 順でレンダリング。

### 3.4 `players.<name>.phases` セクション（Shape B）

```json
{
    "phases": {
        "opening": {"moves": 75,  "total_loss": 47.01, "avg_loss": 0.627},
        "middle":  {"moves": 173, "total_loss": 370.78, "avg_loss": 2.143},
        "endgame": {"moves": 140, "total_loss": 48.6,  "avg_loss": 0.347}
    }
}
```

> フェーズは `_PLAYER_PHASE_LABELS = ("opening", "middle", "endgame")`
> の順（時系列順）で出力される。

### 3.5 Shape A vs Shape B の互換性

| 項目 | Shape A (Phase 227-A / fixture 互換) | Shape B (Phase 228-A / 実 export) |
|------|--------------------------------------|------------------------------------|
| 弱点場所 | top-level `weaknesses` | per-player `players.<name>.mistakes` |
| 粒度 | (color, phase, category) | (player, category) + 別 (player, phase) |
| `total_loss` 精度 | 正確 | 再構成（`avg_loss × count`） |
| `frequency_ratio` | `count / games_analyzed` | `0.0`（per-move なので誤誘導、`pct` を使用） |
| extractor | `extract_summary_weakness_patterns` 自動 | 同左 |

両シェーマが**同一ファイルに共存**する場合は Shape A を優先（より精密な
`total_loss` を保持するため）。

### 3.6 Summary 検証ルール（`summary_validator.py`）

LLM 出力の検証は 6 種類:

| severity | kind | 説明 |
|----------|------|------|
| HIGH | `unknown_pattern_category` | LLM が弱点を未知カテゴリで書いた |
| HIGH | `forbidden_move_number` | 全体サマリに具体的な手番号を書いた（鳥瞰違反） |
| MEDIUM | `too_many_patterns` | 弱点パターン数が `top_n` を超過 |
| MEDIUM | `phase_label_out_of_set` | フェーズラベルが `opening/middle/endgame` 以外 |
| LOW | `specific_game_id_referenced` | `g1`, `game_3` 等の具体ゲーム ID 参照 |
| LOW | `tone_inconsistency` | voice と矛盾する口調表現 |

---

## 4. 共通定数・列挙（`katrain.core.reports.definitions`）

### 4.1 スキーマバージョン

```python
REPORT_SCHEMA_VERSION = "3.5"
# 2026-07: coaching-context enrichment (MistakeItem +5 fields,
#          CriticalMoveItem.best_move, meta.score_perspective)
```

### 4.2 ミス分類閾値

```python
MISTAKE_THRESHOLDS = {
    "inaccuracy": 1.0,   # standard preset の正本値
    "mistake": 2.5,
    "blunder": 5.0,
}
# 注: skill_preset により動的閾値も使うが、JSON 出力は標準値で固定
```

### 4.3 フィルタリング閾値

```python
FILTERING_THRESHOLDS = {
    "bad_move_loss": 0.5,
    "urgent_miss": {
        "loss": 20.0,
        "min_consecutive": 3,
    },
    "phase": {
        "opening_max": 50,
        "middle_max": 200,
        "endgame_min": 201,
    },
}
```

### 4.4 ミスカテゴリ（`MistakeCategory` enum）

```python
# katrain.core.analysis.MistakeCategory
class MistakeCategory(str, Enum):
    GOOD = "good"            # < 1.0
    INACCURACY = "inaccuracy"  # 1.0 - 2.5
    MISTAKE = "mistake"      # 2.5 - 5.0
    BLUNDER = "blunder"      # >= 5.0
```

### 4.5 フェーズラベル

```python
PHASES = ["opening", "middle", "endgame"]
PHASE_ALIASES = {"yose": "endgame"}
```

### 4.6 重要度スケール

```python
IMPORTANCE_DEF = {
    "scale": "0.0 to unbounded (logarithmic)",
    "description": "Combined score of loss and semantic interest",
    "thresholds": {"interesting": 0.3, "important": 0.5, "critical": 1.0},
}
```

### 4.7 Reason code aliases（Phase 158-F）

`REASON_CODE_ALIASES` で MeaningTag 由来の長形式名を短形式に正規化:

```python
{
    "low_liberties": "liberties",
    "need_connect": "connection",
    "heavy_loss": "heavy",
    "reading_failure": "reading",
    "shape_mistake": "shape",
    "endgame_slip": "endgame_hint",
    "cut_risk": "cut_risk",
    "thin": "thin",
    "chase_mode": "chase_mode",
    "connection_mistake": "connection",
    "liberties_mistake": "liberties",
    "joseki_mistake": "joseki",
}
```

### 4.8 Schema hash（Phase 158-I）

```python
REPORT_SCHEMA_HASH = sha1(
    f"{REPORT_SCHEMA_VERSION}|{REPORT_THRESHOLDS}|{MISTAKE_TYPES}|{PRIMARY_TAGS}|{REASON_CODES}"
)[:8]
# 8 hex chars (32 bits)。セキュリティ目的ではなくバージョン識別用。
```

---

## 5. バージョン履歴

| Version | Phase | 変更点 |
|---------|-------|--------|
| 3.0 | 149-C | weakness, mistake_streak, critical_3, data_quality, reason_tags を JSON で再導入（死にコード復活） |
| 3.1 | 153-B | `practice_priorities` / `common_difficult_positions` 削除（冗長） |
| 3.1 | 153-D | `include_definitions` のデフォルトを `False` に |
| 3.2 | 155-D | `opponent_strength_loss_correlation` 追加 |
| 3.3 | 154-D | `win_loss_analysis` / `loss_progression` 追加 |
| 3.3 | 158-I | `schema_hash`, `weaknesses_meta`, visits 分布追加 |
| 3.4 | 157-C | Summary: `games_by_type`, `loss_progression` dict 化 |
| 3.4 | 157-D | Summary: top-level `win_loss_analysis` 削除 |
| 3.4 | 221 | `detect_json_type` で karte / summary 自動判別 |
| 3.4 | 225.6 | Karte `meta.player_info` 追加（BR/WR） |
| 3.4 | 228 | Summary Shape B 対応（`players.<name>.mistakes`） |
| 3.5 | 2026-07 | コーチング強化: MistakeItem に `winrate_lost` / `score_before` / `score_after` / `score_stdev` / `difficulty_score`、CriticalMoveItem に `best_move`、`meta.score_perspective` 追加。critical_3 の reason_tags をエイリアス正規化。coach 層のフィールド名不一致（症状検出が実データで不発だった問題）を修繕。`weaknesses_by_tag` / `score_trajectory` 新設、単局 `opponent_strength_loss_correlation` を None 化、単局 `important_moves` の `game_name` / `game_id` 省略、`unknown` プレースホルダータグの出力抑制 |

---

## 6. マイグレーションガイド

### 6.1 v2.x → v3.x（未実装）

v2 系の Karte JSON を v3 系のダウンストリーム（LLM Coach, CLI）に
投入した場合、`build_prompt` が **`summary.avg_points_lost` 不在** の
警告を出す。実害は限定的（デフォルト 0.0 で動作）。

正式な v2→v3 マイグレーションは **未実装**。ゴールデンファイルは
すべて v3 で再生成されている。

### 6.2 Karte vs Summary の混在ディレクトリ運用

`karte_output_directory` に `karte_*.json` と `summary_*.json` が
**混在**する想定。`find_latest_llm_input` (Phase 227-C) が
`llm_package_*.zip` 等を除外して最新 1 つを返す。**LLM Coach popup**
は型判別後に karte / summary ビルダーに振り分ける（Phase 227-D）。

---

## 7. 関連ドキュメント

- [`docs/usage-guide.md`](./usage-guide.md) — Karte / Summary 出力手順
- [`docs/architecture.md`](./architecture.md) — `core/reports/` パッケージ構成
- 各 Phase 仕様の詳細は git log を参照

---

## 8. テスト

| テストファイル | カバー範囲 |
|--------------|-----------|
| `tests/karte/test_*.py` | Karte 生成 / エラー / スキル統合 |
| `tests/test_karte_*.py` | JSON 構造 / v3 セクション / プレイヤー情報 |
| `tests/test_golden_karte.py` | ゴールデンファイルでのリグレッション |
| `tests/test_architecture.py` | シム無し（Phase 232 確認） |
| `tests/test_coach_*.py` | 症状検出 / カリブレーション |
| `tests/karte/test_*.py` | Summary / Karte フィクスチャ |
| `tests/eval_metrics/test_loss.py` | 閾値一貫性 |

Phase 231/232 で `build_karte_report` → `build_karte_json_string`
リネーム後の全テスト合格状態（**424 tests passed, 0 warnings**, 2026-07-17）。
