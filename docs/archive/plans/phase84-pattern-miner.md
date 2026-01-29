# Phase 84: Recurring Pattern 集計コア（MVP）

## 1. 目的

複数SGFを横断して「同じミスの繰り返し」を検出する基盤を作る。
Phase 85（Summary統合）の前段として、MistakeSignatureの生成と集計ロジックをテスト駆動で固める。

## 2. 成果物

| ファイル | 種別 | 内容 |
|---------|------|------|
| `katrain/core/batch/stats/pattern_miner.py` | 新規 | MistakeSignature, PatternCluster, 集計ロジック |
| `katrain/core/batch/stats/__init__.py` | 修正 | pattern_miner のエクスポート追加 |
| `tests/test_pattern_miner.py` | 新規 | ユニットテスト（合成データ使用） |

## 3. コード確認済みの前提

### 3.1 MoveEval（models.py:267-346）

```python
@dataclass
class MoveEval:
    # 必須フィールド（12個）
    move_number: int
    player: Optional[str]           # 'B' / 'W' / None
    gtp: Optional[str]              # "D4" / "pass" / None
    score_before: Optional[float]
    score_after: Optional[float]
    delta_score: Optional[float]
    winrate_before: Optional[float]
    winrate_after: Optional[float]
    delta_winrate: Optional[float]
    points_lost: Optional[float]
    realized_points_lost: Optional[float]
    root_visits: int

    # デフォルト付きフィールド（create_signatureで使用するもの）
    score_loss: Optional[float] = None
    leela_loss_est: Optional[float] = None
    mistake_category: MistakeCategory = MistakeCategory.GOOD
    meaning_tag_id: Optional[str] = None  # str型、Enumではない
```

**インポートパス**: `from katrain.core.analysis.models import MoveEval, MistakeCategory`

### 3.2 MistakeCategory（models.py:43-54）

```python
class MistakeCategory(Enum):
    GOOD = "good"              # 実質問題なし
    INACCURACY = "inaccuracy"  # 軽い損
    MISTAKE = "mistake"        # はっきり損
    BLUNDER = "blunder"        # 大きな損
```

**インポートパス**: `from katrain.core.analysis.models import MistakeCategory`

### 3.3 EvalSnapshot（models.py:416-429）

```python
@dataclass
class EvalSnapshot:
    moves: List[MoveEval] = field(default_factory=list)
```

**インポートパス**: `from katrain.core.analysis.models import EvalSnapshot`

### 3.4 get_loss_value（classifier.py:112-133）

```python
def get_loss_value(move_eval: "MoveEval") -> Optional[float]:
    """優先順位: score_loss > leela_loss_est > points_lost > None"""
    if move_eval.score_loss is not None:
        return move_eval.score_loss
    if move_eval.leela_loss_est is not None:
        return move_eval.leela_loss_est
    if move_eval.points_lost is not None:
        return move_eval.points_lost
    return None
```

**インポートパス**: `from katrain.core.analysis.meaning_tags.classifier import get_loss_value`

### 3.5 classify_area（board_context.py:41-74）

```python
def classify_area(
    coords: Optional[Tuple[int, int]],      # (col, row) 0-indexed
    board_size: Tuple[int, int] = (19, 19), # (width, height)
    corner_threshold: int = 4,
    edge_threshold: int = 4,
) -> Optional[BoardArea]:
    if coords is None:
        return None
    col, row = coords
    width, height = board_size
    if not (0 <= col < width and 0 <= row < height):
        return None

    min_col_dist = min(col, width - 1 - col)
    min_row_dist = min(row, height - 1 - row)

    if min_col_dist < corner_threshold and min_row_dist < corner_threshold:
        return BoardArea.CORNER
    if min_col_dist < edge_threshold or min_row_dist < edge_threshold:
        return BoardArea.EDGE
    return BoardArea.CENTER
```

**インポートパス**: `from katrain.core.analysis.board_context import classify_area, BoardArea`

### 3.6 is_endgame（classifier.py:221-243）

```python
def is_endgame(
    move_number: int, total_moves: Optional[int], has_endgame_hint: bool
) -> bool:
    """Criteria (OR):
        1. has_endgame_hint == True
        2. total_moves is not None and move_number > total_moves * 0.7
        3. move_number > 150
    """
    if has_endgame_hint:
        return True
    if total_moves is not None and move_number > total_moves * THRESHOLD_ENDGAME_RATIO:
        return True
    return move_number > THRESHOLD_MOVE_ENDGAME_ABSOLUTE  # 150
```

**インポートパス**: `from katrain.core.analysis.meaning_tags.classifier import is_endgame`

**total_moves=None の動作**:
- 条件1: `has_endgame_hint` で判定
- 条件2: **スキップ**（total_moves が None なので評価されない）
- 条件3: `move_number > 150` で判定

つまり、`is_endgame(100, None, False)` → False、`is_endgame(151, None, False)` → True

### 3.7 Move.from_gtp（sgf_parser.py:24-54）

```python
@classmethod
def from_gtp(cls, gtp_coords, player="B"):
    # "pass" → Move(coords=None, player=player)
    # 無効形式 → ValueError発生（例外をキャッチ必要）
    # board_size引数なし、範囲チェックなし
```

**インポートパス**: `from katrain.core.sgf_parser import Move`

### 3.8 MeaningTagId（meaning_tags/models.py:16-40）

```python
class MeaningTagId(str, Enum):
    UNCERTAIN = "uncertain"  # フォールバック用タグ（存在確認済み）
    # ... 他11種類
```

**インポートパス**: `from katrain.core.analysis.meaning_tags import MeaningTagId`

### 3.9 leela_loss_est のスケール（conversion.py:195-199）

```python
loss_pct = (best.eval_pct - played_candidate.eval_pct)  # 勝率差（0-100）
loss_est = loss_pct * k  # k = LEELA_K_DEFAULT = 0.5
```

**重要**: `leela_loss_est` は「目数」ではなく「スケール済み勝率損失」。
例: 勝率差10% → `10 * 0.5 = 5.0`

## 4. データモデル

### 4.1 MistakeSignature（frozen dataclass）

```python
@dataclass(frozen=True)
class MistakeSignature:
    phase: str          # "opening" | "middle" | "endgame"
    area: str           # "corner" | "edge" | "center"
    primary_tag: str    # MeaningTagId.value（例: "overplay", "uncertain"）
    severity: str       # "mistake" | "blunder"

    def sort_key(self) -> Tuple[str, str, str, str]:
        """決定論的ソート用キー"""
        return (self.phase, self.area, self.primary_tag, self.severity)
```

### 4.2 GameRef（frozen dataclass）

```python
@dataclass(frozen=True)
class GameRef:
    game_name: str
    move_number: int
    player: str  # "B" | "W"
```

### 4.3 PatternCluster

```python
MAX_GAME_REFS_PER_CLUSTER = 10  # メモリ制限

@dataclass
class PatternCluster:
    signature: MistakeSignature
    count: int
    total_loss: float
    game_refs: List[GameRef]  # 最大MAX_GAME_REFS_PER_CLUSTER件

    @property
    def impact_score(self) -> float:
        return self.total_loss * (1.0 + 0.1 * self.count)
```

### 4.4 game_refs のセマンティクス

- **最大件数**: `MAX_GAME_REFS_PER_CLUSTER = 10`
- **重複許可**: 同一ゲームの複数手を含むことを許可（per-game uniqueではない）
- **順序**: **遭遇順（encounter order）** で最初のN件を保持
- **決定論性**: ゲームリストの順序とMoveEvalの順序が同じなら、常に同じgame_refsになる

```python
# 集約時の処理
if len(cluster.game_refs) < MAX_GAME_REFS_PER_CLUSTER:
    cluster.game_refs.append(game_ref)
# キャップ到達後は追加しない（countとtotal_lossは継続更新）
```

## 5. severity の導出（MistakeCategory → severity）

### 5.1 マッピング表

| MistakeCategory | severity | 動作 |
|-----------------|----------|------|
| `GOOD` | - | **スキップ**（署名生成しない） |
| `INACCURACY` | - | **スキップ**（署名生成しない） |
| `MISTAKE` | `"mistake"` | 署名生成 |
| `BLUNDER` | `"blunder"` | 署名生成 |
| 未知の値 | - | **スキップ**（安全側にフォールバック） |

### 5.2 実装

```python
def get_severity(mistake_category: MistakeCategory) -> Optional[str]:
    """MistakeCategoryからseverityを導出。

    Returns:
        "mistake" | "blunder" | None（スキップ対象）
    """
    if mistake_category == MistakeCategory.MISTAKE:
        return "mistake"
    if mistake_category == MistakeCategory.BLUNDER:
        return "blunder"
    return None  # GOOD, INACCURACY, 未知の値
```

### 5.3 create_signature での使用

```python
def create_signature(...) -> Optional[MistakeSignature]:
    # ... loss チェック後
    severity = get_severity(move_eval.mistake_category)
    if severity is None:
        return None  # GOOD/INACCURACY はスキップ
    # ... 署名生成
```

**注意**: `LOSS_THRESHOLD >= 2.5` でフィルタしているため、通常は GOOD/INACCURACY は到達しないが、明示的なスキップで安全性を確保。

## 6. primary_tag の正規化

```python
def normalize_primary_tag(meaning_tag_id: Optional[str]) -> str:
    """meaning_tag_id を正規化。

    - None → "uncertain"
    - 空文字列 → "uncertain"
    - str → そのまま使用（MeaningTagId.value形式を想定）
    """
    if not meaning_tag_id:
        return MeaningTagId.UNCERTAIN.value  # "uncertain"
    return meaning_tag_id
```

**注意**: `meaning_tag_id` は `Optional[str]` 型（Enumではない）。

**インポートパス**: MeaningTagIdとTHRESHOLD定数は package-level から import する：
```python
from katrain.core.analysis.meaning_tags import (
    MeaningTagId,
    THRESHOLD_ENDGAME_RATIO,
    THRESHOLD_MOVE_ENDGAME_ABSOLUTE,
)
```

## 7. 損失抽出の方針

### 7.1 閾値と制限事項

```python
LOSS_THRESHOLD = 2.5  # ベストエフォート閾値
```

**重要**: この閾値は `get_loss_value()` の戻り値に適用されるが、score_loss（目数）と leela_loss_est（スケール済み勝率損失）は**異なるセマンティクス**を持つ。

- **KataGo (score_loss)**: 2.5目以上のミス → 妥当
- **Leela (leela_loss_est)**: 2.5 = 勝率差5%相当 → やや緩い可能性あり

Phase 84では「ベストエフォート」とし、Phase 85以降でエンジン別閾値の検討を行う。

### 7.2 使用する属性（最小セット）

`create_signature()` で使用する MoveEval の属性:
- `move_number: int`
- `player: Optional[str]`
- `gtp: Optional[str]`
- `score_loss: Optional[float]`
- `leela_loss_est: Optional[float]`
- `points_lost: Optional[float]`
- `mistake_category: MistakeCategory`
- `meaning_tag_id: Optional[str]`

## 8. phase判定の盤サイズ対応

```python
OPENING_THRESHOLDS = {
    9: 15,   # 9x9: 15手まで序盤
    13: 25,  # 13x13: 25手まで序盤
    19: 40,  # 19x19: 40手まで序盤
}
DEFAULT_OPENING_THRESHOLD = 40

def determine_phase(
    move_number: int,
    total_moves: Optional[int],
    board_size: int = 19,
) -> str:
    opening_threshold = OPENING_THRESHOLDS.get(board_size, DEFAULT_OPENING_THRESHOLD)
    if move_number <= opening_threshold:
        return "opening"
    if is_endgame(move_number, total_moves, has_endgame_hint=False):
        return "endgame"
    return "middle"
```

## 9. BoardArea分類の盤サイズ対応

### 9.1 classify_area() のセマンティクス

`threshold` は「盤端からの距離（0-indexed）が `threshold` **未満**なら隅/辺」を意味する。

```python
min_col_dist = min(col, width - 1 - col)  # 最寄りの縦辺までの距離
min_row_dist = min(row, height - 1 - row)  # 最寄りの横辺までの距離

CORNER: min_col_dist < threshold AND min_row_dist < threshold
EDGE:   min_col_dist < threshold OR  min_row_dist < threshold
CENTER: otherwise
```

### 9.2 「線」と「閾値」の関係

囲碁の「N線」は盤端からN番目の線を指す（1-indexed）。
0-indexed座標では「N線」は座標 N-1 に対応。

| threshold | 「隅」になる座標範囲 | 囲碁用語での「線」 |
|-----------|---------------------|-------------------|
| 2 | col < 2 AND row < 2 → (0,0), (0,1), (1,0), (1,1) | 1-2線（2線まで） |
| 3 | col < 3 AND row < 3 → 3x3領域 | 1-3線（3線まで） |
| 4 | col < 4 AND row < 4 → 4x4領域 | 1-4線（4線まで） |

### 9.3 閾値マッピング

```python
AREA_THRESHOLDS = {
    9: 3,    # 9x9: 3線まで（囲碁的に妥当）
    13: 4,   # 13x13: 4線まで
    19: 4,   # 19x19: 4線まで（デフォルト）
}
DEFAULT_AREA_THRESHOLD = 4

def get_area_threshold(board_size: int) -> int:
    """盤サイズに応じたエリア分類閾値を取得。"""
    return AREA_THRESHOLDS.get(board_size, DEFAULT_AREA_THRESHOLD)
```

### 9.4 期待される分類結果（検証済み）

**GTP座標から0-indexed座標への変換**:

**重要**: GTP座標は 'I' をスキップする（1と紛らわしいため）。
`Move.GTP_COORD = "ABCDEFGHJKLMNOPQRSTUVWXYZ"` （'I'なし）

| Letter | Index | 備考 |
|--------|-------|------|
| A-H | 0-7 | 通常通り |
| J | 8 | 'I'スキップ後 |
| K | 9 | |
| L | 10 | |

具体例:
- D4 → col=3, row=3
- C3 → col=2, row=2
- B2 → col=1, row=1
- E5 → col=4, row=4
- K10 → col=9, row=9（**Iスキップにより K=9**）

**19x19盤（threshold=4）**:

| GTP | coords | min_dist | CORNER条件 | EDGE条件 | 結果 |
|-----|--------|----------|-----------|---------|------|
| D4 | (3,3) | (3,3) | 3<4 AND 3<4 ✓ | - | **CORNER** |
| D10 | (3,9) | (3,9) | 3<4 AND 9<4 ✗ | 3<4 ✓ | **EDGE** |
| K10 | (9,9) | (9,9) | 9<4 ✗ | 9<4 ✗ | **CENTER** |

**9x9盤（threshold=3）**:

| GTP | coords | min_dist | CORNER条件 | EDGE条件 | 結果 |
|-----|--------|----------|-----------|---------|------|
| D4 | (3,3) | (3,3) | 3<3 ✗ | 3<3 ✗ | **CENTER** |
| C3 | (2,2) | (2,2) | 2<3 AND 2<3 ✓ | - | **CORNER** |
| B2 | (1,1) | (1,1) | 1<3 AND 1<3 ✓ | - | **CORNER** |
| D3 | (3,2) | (3,2) | 3<3 ✗ | 2<3 ✓ | **EDGE** |
| E5 | (4,4) | (4,4) | 4<3 ✗ | 4<3 ✗ | **CENTER** |

## 10. GTP座標のパース（正規化強化）

```python
def get_area_from_gtp(gtp: Optional[str], board_size: int = 19) -> Optional[str]:
    """GTP座標からエリア文字列を取得。

    正規化:
        1. None チェック
        2. strip() で前後空白除去
        3. 小文字化して pass/resign/empty を早期リターン
        4. upper() で大文字化してパース

    Returns:
        "corner" | "edge" | "center" | None（pass/resign/invalid/None）
    """
    if gtp is None:
        return None

    # 正規化
    gtp = gtp.strip()
    if not gtp:
        return None

    gtp_lower = gtp.lower()
    if gtp_lower in ("pass", "resign"):
        return None

    try:
        move = Move.from_gtp(gtp.upper())  # 大文字化してパース
        if move.coords is None:
            return None

        threshold = get_area_threshold(board_size)
        area = classify_area(
            move.coords,
            (board_size, board_size),
            corner_threshold=threshold,
            edge_threshold=threshold,
        )
        return area.value if area else None
    except (ValueError, AttributeError):
        return None
```

**Move.from_gtp() の挙動**:
- "PASS" → `coords=None`（例外なし）
- "RESIGN" → `ValueError`（例外発生）
- 無効形式 → `ValueError`（例外発生）
- board_size引数なし、範囲チェックなし

## 11. mine_patterns() の total_moves 導出

```python
def mine_patterns(
    games: List[Tuple[str, EvalSnapshot]],
    board_size: int = 19,
    min_count: int = 2,
    top_n: int = 5,
) -> List[PatternCluster]:
    """複数ゲームから頻出パターンを抽出。

    Args:
        games: (game_name, snapshot) のリスト
        board_size: 盤サイズ
        min_count: 最小発生回数
        top_n: 上位N件

    Note:
        各ゲームの total_moves は len(snapshot.moves) から導出。
        呼び出し元でオーバーライドしたい場合は、
        create_signature() を直接呼ぶか、本関数を拡張すること。
    """
    clusters: Dict[MistakeSignature, PatternCluster] = {}

    for game_name, snapshot in games:
        total_moves = len(snapshot.moves)  # ゲーム総手数を導出
        for move_eval in snapshot.moves:
            sig = create_signature(move_eval, total_moves, board_size)
            # ... 集約処理
```

## 12. 決定論的ソート

```python
def mine_patterns(...) -> List[PatternCluster]:
    # ...
    # ソートキー: (-impact_score, signature.sort_key())
    clusters.sort(key=lambda c: (-c.impact_score, c.signature.sort_key()))
```

**signature.sort_key()**: `(phase, area, primary_tag, severity)` のタプル

## 13. テスト戦略

### 13.1 FakeMoveEval（テスト専用）

MoveEvalのコンストラクタドリフトを避けるため、必要な属性のみを持つダミーオブジェクトを使用。

```python
from types import SimpleNamespace

def make_fake_move_eval(
    move_number: int,
    player: Optional[str],           # None → 署名スキップ
    gtp: Optional[str],              # None → 署名スキップ
    score_loss: Optional[float] = None,
    leela_loss_est: Optional[float] = None,
    points_lost: Optional[float] = None,
    mistake_category: MistakeCategory = MistakeCategory.MISTAKE,
    meaning_tag_id: Optional[str] = "overplay",
) -> SimpleNamespace:
    """テスト用の軽量MoveEval代替。

    get_loss_value()とcreate_signature()が使用する属性のみを含む。

    Note:
        player/gtp が None の場合は create_signature() が None を返す
        （スキップケースのテスト用）
    """
    return SimpleNamespace(
        move_number=move_number,
        player=player,
        gtp=gtp,
        score_loss=score_loss,
        leela_loss_est=leela_loss_est,
        points_lost=points_lost,
        mistake_category=mistake_category,
        meaning_tag_id=meaning_tag_id,
    )
```

**利点**:
- MoveEvalの12必須フィールドを気にしなくてよい
- `get_loss_value()` は属性アクセスのみ行うためダックタイプで動作
- コンストラクタ変更に影響されない

### 13.2 FakeEvalSnapshot（テスト専用）

```python
def make_fake_snapshot(moves: List[SimpleNamespace]) -> SimpleNamespace:
    """テスト用の軽量EvalSnapshot代替。"""
    return SimpleNamespace(moves=moves)
```

### 13.3 テストケース一覧

| テスト名 | 検証内容 |
|---------|---------|
| **署名生成** | |
| `test_create_signature_basic` | 基本的な署名生成 |
| `test_create_signature_skip_small_loss` | `loss < 2.5` はNone |
| `test_create_signature_skip_loss_none` | `loss=None` はNone |
| `test_create_signature_skip_pass` | gtp="pass" はNone |
| `test_create_signature_skip_resign` | gtp="resign" はNone |
| `test_create_signature_skip_no_player` | `player=None` はNone |
| `test_create_signature_meaning_tag_none` | `meaning_tag_id=None` → "uncertain" |
| **severity マッピング** | |
| `test_get_severity_mistake` | MISTAKE → "mistake" |
| `test_get_severity_blunder` | BLUNDER → "blunder" |
| `test_get_severity_good_skip` | GOOD → None |
| `test_get_severity_inaccuracy_skip` | INACCURACY → None |
| `test_create_signature_skip_good` | GOOD カテゴリは署名スキップ |
| **フェーズ判定** | |
| `test_determine_phase_opening_19x19` | 19路: 40手以下 → "opening" |
| `test_determine_phase_opening_9x9` | 9路: 15手以下 → "opening" |
| `test_determine_phase_middle` | 中盤判定 |
| `test_determine_phase_endgame_absolute` | 151手、total_moves=None → "endgame"（THRESHOLD_MOVE_ENDGAME_ABSOLUTEを使用） |
| `test_determine_phase_endgame_ratio` | total_moves=200、閾値超え → "endgame"（THRESHOLD_ENDGAME_RATIOをインポートして使用） |
| **エリア判定（19x19, threshold=4）** | |
| `test_get_area_from_gtp_corner_19x19` | D4 → "corner" |
| `test_get_area_from_gtp_edge_19x19` | D10 → "edge" |
| `test_get_area_from_gtp_center_19x19` | K10 → "center" |
| **エリア判定（9x9, threshold=3）** | |
| `test_get_area_from_gtp_d4_9x9` | D4 on 9x9 → "center"（3<3は偽） |
| `test_get_area_from_gtp_c3_9x9` | C3 on 9x9 → "corner"（2<3は真） |
| `test_get_area_from_gtp_d3_9x9` | D3 on 9x9 → "edge"（col=3≮3, row=2<3） |
| **GTP正規化** | |
| `test_get_area_from_gtp_lowercase` | "d4" → "corner"（小文字対応） |
| `test_get_area_from_gtp_whitespace` | " D4 " → "corner"（空白除去） |
| `test_get_area_from_gtp_invalid` | "ZZ" → None（例外なし） |
| `test_get_area_from_gtp_i_skip` | J1 → col=8, K1 → col=9（Iスキップ検証） |
| **集計** | |
| `test_mine_patterns_count_filter` | `min_count` フィルタ |
| `test_mine_patterns_ranking` | `impact_score` 降順 |
| `test_mine_patterns_stable_sort` | 同スコア時の決定論的ソート |
| `test_mine_patterns_top_n` | `top_n` 制限 |
| `test_mine_patterns_empty_input` | 空入力 → 空リスト |
| `test_mine_patterns_game_refs_cap` | game_refs が MAX_GAME_REFS_PER_CLUSTER 以下 |
| `test_mine_patterns_game_refs_encounter_order` | game_refs は遭遇順 |
| `test_mine_patterns_total_moves_from_snapshot` | total_moves = len(snapshot.moves) |
| `test_recurring_pattern_aggregation` | 同一署名の正しい集約 |

## 14. エッジケース

| ケース | 期待動作 |
|--------|---------|
| **損失関連** | |
| `loss=None` | 署名スキップ |
| `loss=2.4999` | 署名スキップ |
| `loss=2.5` | 署名生成 |
| **プレイヤー関連** | |
| `player=None` | 署名スキップ |
| **GTP関連** | |
| `gtp="pass"` | 署名スキップ |
| `gtp="PASS"` | 署名スキップ（大文字対応） |
| `gtp="resign"` | 署名スキップ |
| `gtp=None` | 署名スキップ |
| `gtp="ZZ"` | 署名スキップ（ValueError → None） |
| `gtp="d4"` | 署名生成（小文字 → 大文字変換） |
| `gtp=" D4 "` | 署名生成（空白除去） |
| **severity関連** | |
| `mistake_category=GOOD` | 署名スキップ |
| `mistake_category=INACCURACY` | 署名スキップ |
| `mistake_category=MISTAKE` | severity="mistake" |
| `mistake_category=BLUNDER` | severity="blunder" |
| **meaning_tag関連** | |
| `meaning_tag_id=None` | "uncertain" として署名生成 |
| `meaning_tag_id=""` | "uncertain" として署名生成 |
| **盤サイズ関連** | |
| `board_size=9` | 序盤閾値15、エリア閾値3 |
| `board_size=13` | 序盤閾値25、エリア閾値4 |
| `board_size=19` | 序盤閾値40、エリア閾値4 |
| **終盤判定** | |
| `total_moves=None, move=100` | "middle"（100 <= THRESHOLD_MOVE_ENDGAME_ABSOLUTE） |
| `total_moves=None, move=151` | "endgame"（151 > THRESHOLD_MOVE_ENDGAME_ABSOLUTE=150） |
| `total_moves=200, move=141` | "endgame"（141 > 200*THRESHOLD_ENDGAME_RATIO=140） |
| `total_moves=200, move=140` | "middle"（140 <= 閾値） |
| **集計関連** | |
| `min_count=0` | 全パターン返却 |
| `top_n=0` | 空リスト返却 |
| `games=[]` | 空リスト返却 |
| 同一`impact_score` | `sort_key()` タプルでソート |
| game_refs > 10件 | 最初の10件のみ保持（遭遇順） |

## 15. リスクと軽減策

| リスク | 軽減策 |
|--------|--------|
| `get_loss_value()`がダックタイプで動作しない | テストで明示的に確認 |
| leela_loss_estの閾値が不適切 | 「ベストエフォート」と明記、Phase 85で再評価 |
| Move.from_gtp()のresign処理漏れ | try/exceptで例外をキャッチ |
| MoveEvalコンストラクタ変更 | FakeMoveEval使用でテスト分離 |
| 盤サイズ混在 | mine_patterns()は単一サイズ前提、呼び出し元で分離 |
| メモリ爆発（大量game_refs） | MAX_GAME_REFS_PER_CLUSTER=10 で制限 |
| MistakeCategory未知の値 | get_severity()でNone返却（安全側） |
| 小文字GTP座標 | upper()で正規化 |

## 16. 受け入れ基準

1. **フィルタリング**: `get_loss_value() >= 2.5` の手のみ署名生成
2. **severity**: MISTAKE/BLUNDER のみ署名生成、GOOD/INACCURACY はスキップ
3. **min_count**: 指定回数未満のパターンは結果に含まれない
4. **決定論的ソート**: `(-impact_score, signature.sort_key())` で常に同一順序
5. **top_n**: 指定件数を超えるパターンは結果に含まれない
6. **出力安定性**: 同一入力 → 同一出力（ランダム性なし）
7. **エッジケース**: 上記表の全ケースでクラッシュしない
8. **game_refs制限**: 各クラスタのgame_refsは最大10件（遭遇順）
9. **盤サイズ対応**: 9x9/13x13/19x19 でエリア分類が検証済みの期待値と一致
10. **GTP正規化**: 小文字・空白入力でも正しく処理
11. **total_moves導出**: `len(snapshot.moves)` から自動導出
12. **テスト通過**: `uv run pytest tests/test_pattern_miner.py -v` 全パス
13. **既存テスト**: `uv run pytest tests -x` 全パス

## 17. 修正レベル

**Lv2: 中程度単一**

| ファイル | 変更内容 |
|---------|---------|
| `katrain/core/batch/stats/pattern_miner.py` | 新規作成（~160行） |
| `katrain/core/batch/stats/__init__.py` | エクスポート追加（~5行） |
| `tests/test_pattern_miner.py` | 新規作成（~250行） |

## 18. 実装チェックリスト

### Step 1: 定数・データモデル
- [ ] `LOSS_THRESHOLD = 2.5`
- [ ] `OPENING_THRESHOLDS`, `DEFAULT_OPENING_THRESHOLD`
- [ ] `AREA_THRESHOLDS`, `DEFAULT_AREA_THRESHOLD`
- [ ] `MAX_GAME_REFS_PER_CLUSTER = 10`
- [ ] `MistakeSignature` frozen dataclass + `sort_key()`
- [ ] `GameRef` frozen dataclass
- [ ] `PatternCluster` dataclass + `impact_score`

### Step 2: ヘルパー関数
- [ ] `get_severity(mistake_category)` → "mistake" | "blunder" | None
- [ ] `normalize_primary_tag(meaning_tag_id)`
- [ ] `get_opening_threshold(board_size)`
- [ ] `get_area_threshold(board_size)`
- [ ] `determine_phase(move_number, total_moves, board_size)`
- [ ] `get_area_from_gtp(gtp, board_size)` （正規化+try/except）

### Step 3: コア関数
- [ ] `create_signature(move_eval, total_moves, board_size)`
- [ ] `mine_patterns(games, board_size, min_count, top_n)`

### Step 4: エクスポート
- [ ] `__init__.py` に追加

### Step 5: テスト
- [ ] `make_fake_move_eval()`, `make_fake_snapshot()`
- [ ] 署名生成テスト（7件）
- [ ] severityマッピングテスト（5件）
- [ ] フェーズ判定テスト（5件）
- [ ] エリア判定テスト（9件）
- [ ] 集計テスト（9件）

### Step 6: 動作確認
- [ ] `uv run pytest tests/test_pattern_miner.py -v`
- [ ] `uv run pytest tests -x`

## 19. ファイル構成（実装後）

```
katrain/core/batch/stats/
├── __init__.py          ← エクスポート追加
├── pattern_miner.py     ← 【新規】
├── models.py
├── aggregation.py
├── extraction.py
└── formatting.py

tests/
└── test_pattern_miner.py    ← 【新規】
```

## 20. コード確認済み参照一覧

| 項目 | ファイル | 行番号 |
|------|---------|--------|
| MoveEval定義 | models.py | 267-346 |
| MistakeCategory定義 | models.py | 43-54 |
| EvalSnapshot定義 | models.py | 416-429 |
| get_loss_value | classifier.py | 112-133 |
| classify_area | board_context.py | 41-74 |
| BoardArea | board_context.py | 20-25 |
| is_endgame | classifier.py | 221-243 |
| THRESHOLD_ENDGAME_* | classifier.py | 61-62 |
| Move.from_gtp | sgf_parser.py | 24-54 |
| MeaningTagId.UNCERTAIN | meaning_tags/models.py | 40 |
| leela_loss_est計算 | leela/conversion.py | 195-199 |
| LEELA_K_DEFAULT | leela/logic.py | 14 |
