# Phase 82: Consequence判定 + Karteへ限定統合

**Revision**: Rev.6 (2026-01-30)

## 概要

Phase 81で実装されたOwnershipクラスタを3分類（Group Death / Territory Loss / Missed Kill）に落とし込み、KarteのCritical 3でContextが(none)のときのみ注入する。

**修正レベル**: Lv3（複数ファイル）

### Rev.6 主要修正点（Final Consistency Pass）

| # | 問題 | 対策 |
|---|------|------|
| 1 | 自殺手の扱いが矛盾 | 統一: 自殺手は自グループを除去（AMBIGUOUS表記を削除） |
| 2 | SGF座標が誤り | "aa"=(0,height-1)=TOP-LEFT。テストを内部座標(col,row)で記述 |
| 3 | AE順序の検証不足 | SGF仕様準拠: AB/AW→B/W→AE（KaTrain実装とは異なる正しい順序） |
| 4 | mainline解決失敗時の動作 | 明示的ガード追加: 解決失敗→None（注入スキップ） |

### Rev.5からの差分

1. **自殺手契約の統一**: Rev.5表では"AMBIGUOUS"、コードでは"除去"→「自グループを除去」に統一
2. **SGF座標を内部座標に変換**: テストはMove.from_sgf()結果の内部座標(col,row)で記述
3. **AE順序の明示**: SGF仕様準拠（AB/AW→B/W→AE）。KaTrainの既存実装とは異なるが正しい
4. **mainline解決ガード追加**: `_get_cluster_context_for_move()`でノード解決失敗時にNone返却

---

## 目標

1. **3分類ロジックの実装**: クラスタの特性から意味的な分類を判定
2. **Karteへの限定統合**: `reason_tags`が空の場合のみContext注入

---

## 変更点サマリー（Rev.4）

| 項目 | Rev.3 | Rev.4 | 理由 |
|------|-------|-------|------|
| 盤面再構築 | move_with_placements一括処理 | placements/moves分離処理 | AB/AWで取りが発生しないよう |
| ノード探索 | children[0] | ordered_children[0] | mainline保証 |
| BFS実装 | list.pop(0) | deque.popleft() | O(n)→O(1) |
| Missed Kill入力 | 未詳細 | クラスタ座標のownership平均 | 明示的な仕様 |
| 座標規約 | 文書のみ | sgf_parser.pyリファレンス追加 | 検証可能性 |

### Rev.3からの主要変更点

1. **AB/AW setup stonesは取りを発生させない**（最重要）
2. **ordered_children[0]でmainline保証**
3. **deque使用でBFSパフォーマンス改善**
4. **Missed Kill用のownership平均計算を明示化**

---

## 用語定義（視点の明確化）

| 用語 | 定義 |
|------|------|
| **actor** | ミスをした側 = `CriticalMove.player` |
| **opponent** | actorの相手 = "W" if actor == "B" else "B" |

### sum_delta符号規約（Phase 81で定義済み）

```python
# ownership_cluster.py:41-42
TO_BLACK = "to_black"  # sum_delta > 0: 黒に有利化
TO_WHITE = "to_white"  # sum_delta < 0: 白に有利化
```

**actorとの関係**:
- `actor == "B"` のとき、opponentの得 = 白に有利化 = `sum_delta < 0`
- `actor == "W"` のとき、opponentの得 = 黒に有利化 = `sum_delta > 0`

**クラスタ選択ロジック** (ClusterType名に依存しない):
```python
def is_opponent_gain(cluster: OwnershipCluster, actor: str) -> bool:
    """actorのミスによりopponentが得をしたクラスタか判定。"""
    if actor == "B":
        return cluster.sum_delta < 0  # 白に有利化
    else:
        return cluster.sum_delta > 0  # 黒に有利化
```

---

## 3分類の定義と判定条件

| 分類 | 意味 | 判定条件 |
|------|------|----------|
| **Group Death** | actorの石が取られた | クラスタ内でactorの石が消失 |
| **Territory Loss** | actorの地が減った | 石の消失なし + actorに不利なownership変動 + `abs(sum_delta) >= 1.0` |
| **Missed Kill** | opponentの弱い石を殺せなかった | opponentの弱い石がクラスタ内で生還 |

---

## 石の位置取得（安全な実装 - Rev.4）

### 問題: set_current_node()のUI副作用

```python
# game.py:971-975 (InteractiveGame)
def set_current_node(self, node):
    if self.insert_mode:
        self.katrain.controls.set_status(...)  # UI副作用
        return
    super().set_current_node(node)  # _calculate_groups()を呼ぶ
```

### 問題: AB/AW（setup stones）の取り扱い

SGFの石は2種類:
- **moves（B/W）**: 実際の着手 → **取りが発生する**
- **placements（AB/AW）**: 置き石セットアップ → **取りが発生しない**

```python
# sgf_parser.py:266-312
@property
def moves(self) -> List[Move]:      # B/W properties (actual game moves)
@property
def placements(self) -> List[Move]: # AB/AW properties (setup stones)
@property
def move_with_placements(self):     # placements + moves (both)
```

**重要**: Rev.3では`move_with_placements`を一括処理していたため、AB/AWでも取りが発生してしまう問題があった。

### 解決策: placements/movesを分離処理（Rev.4）

```python
from collections import deque
from typing import Set, List, Optional, Tuple, FrozenSet

StonePosition = Tuple[int, int, str]  # (col, row, player)
StoneSet = FrozenSet[StonePosition]


def compute_stones_at_node(node: "GameNode", board_size: Tuple[int, int]) -> StoneSet:
    """
    指定ノードでの石を、nodes_from_rootから再構築。

    current_nodeを変更しない。副作用なし。スレッドセーフ。

    **重要な処理順序**:
    1. placements (AB/AW): 取りなしで配置
    2. moves (B/W): 取りありで配置
    3. clear_placements (AE): 石を除去

    Args:
        node: 石を取得したいノード
        board_size: (width, height)

    Returns:
        FrozenSet of (col, row, player) tuples

    座標規約:
        (col, row) は 0-indexed
        col: 左から右 (0 = 左端 = A列)
        row: 下から上 (0 = 下辺)
        参照: sgf_parser.py Move.from_sgf()
    """
    width, height = board_size
    # board[row][col] = player ("B", "W", or None)
    board: List[List[Optional[str]]] = [[None] * width for _ in range(height)]

    for n in node.nodes_from_root:
        # Step 1: placements (AB/AW) - NO CAPTURE LOGIC
        for move in n.placements:
            if move.is_pass:
                continue
            col, row = move.coords
            board[row][col] = move.player

        # Step 2: moves (B/W) - WITH CAPTURE LOGIC
        for move in n.moves:
            if move.is_pass:
                continue
            col, row = move.coords
            player = move.player

            # 石を配置
            board[row][col] = player

            # 相手の石を取る（隣接グループの呼吸点チェック）
            opponent = "W" if player == "B" else "B"
            for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nc, nr = col + dc, row + dr
                if 0 <= nc < width and 0 <= nr < height:
                    if board[nr][nc] == opponent:
                        group = _find_group(board, nc, nr, width, height)
                        if not _has_liberty(board, group, width, height):
                            for gc, gr in group:
                                board[gr][gc] = None

            # 自殺手チェック（Rev.6: 自グループを除去）
            # 相手を取った後、自分に呼吸点がなければ自グループを除去する。
            # 標準ルールでは自殺手は禁止だが、SGFには含まれる可能性がある。
            # 例外を投げずに安全に処理し、盤面状態を一貫させる。
            own_group = _find_group(board, col, row, width, height)
            if not _has_liberty(board, own_group, width, height):
                for gc, gr in own_group:
                    board[gr][gc] = None

        # Step 3: AE (clear) の処理
        for clear_move in n.clear_placements:
            if not clear_move.is_pass:
                col, row = clear_move.coords
                board[row][col] = None

    # 結果を StoneSet に変換
    stones: Set[StonePosition] = set()
    for row in range(height):
        for col in range(width):
            if board[row][col] is not None:
                stones.add((col, row, board[row][col]))

    return frozenset(stones)


def _find_group(
    board: List[List[Optional[str]]],
    start_col: int,
    start_row: int,
    width: int,
    height: int,
) -> Set[Tuple[int, int]]:
    """BFSで連結した同色の石を探索（deque使用でO(1)）。"""
    player = board[start_row][start_col]
    if player is None:
        return set()

    visited: Set[Tuple[int, int]] = set()
    queue: deque[Tuple[int, int]] = deque([(start_col, start_row)])

    while queue:
        col, row = queue.popleft()  # O(1) with deque
        if (col, row) in visited:
            continue
        if not (0 <= col < width and 0 <= row < height):
            continue
        if board[row][col] != player:
            continue

        visited.add((col, row))
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            queue.append((col + dc, row + dr))

    return visited


def _has_liberty(
    board: List[List[Optional[str]]],
    group: Set[Tuple[int, int]],
    width: int,
    height: int,
) -> bool:
    """グループに呼吸点があるか判定。"""
    for col, row in group:
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nc, nr = col + dc, row + dr
            if 0 <= nc < width and 0 <= nr < height:
                if board[nr][nc] is None:
                    return True
    return False
```

### 処理順序の根拠

SGF仕様では、1つのノード内の処理順序は:
1. AB/AW (setup) → 2. B/W (move) → 3. AE (clear)

この順序により、置碁のセットアップ後に着手、という自然な流れになる。

### 座標規約の検証（sgf_parser.py参照）

```python
# sgf_parser.py:88-95 Move.from_sgf()
def from_sgf(cls, sgf_coords, board_size, player="B"):
    return cls(
        coords=(
            Move.SGF_COORD.index(sgf_coords[0]),           # col: 'a'=0, 'b'=1, ...
            board_size[1] - Move.SGF_COORD.index(sgf_coords[1]) - 1,  # row: 下から
        ),
        player=player,
    )

# 例: board_size=(19,19), sgf_coords="dd" (D4)
# col = index('d') = 3
# row = 19 - index('d') - 1 = 19 - 3 - 1 = 15
# つまり (col=3, row=15) = D4 (左から4列目、下から16行目)
```

### 利点

- **副作用なし**: current_nodeを変更しない
- **スレッドセーフ**: 状態を変更しない純粋関数
- **UI安全**: コールバックが発生しない
- **テスト容易**: モック不要で単体テスト可能
- **正確性**: AB/AWで取りが発生しない
- **パフォーマンス**: deque使用でBFSがO(n)

---

## キャッシュ戦略（Rev.4）

### 問題: Karte生成中のノード切り替えコスト

Critical 3では最大3手を処理し、各手で親ノードと子ノードの石が必要。
ノード毎に石を再計算するのは非効率。

### 問題: children[0] はmainlineを保証しない

Rev.3では`node.children[0]`を使用していたが、これはmainlineを保証しない。
KaTrainでは`ordered_children[0]`がmainline慣習。

```python
# game.py:834-842 (既存パターン)
def _iter_main_branch_nodes(self):
    """ルートからメイン分岐（ordered_children[0] を辿った一本の線）"""
    node = self.root
    while node.children:
        node = node.ordered_children[0]  # ← これがmainline
        yield node
```

### 解決策: ordered_children[0]でmainline保証（Rev.4）

```python
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.core.game_node import GameNode


class StoneCache:
    """Karte生成中の石のキャッシュ（1局分）。"""

    def __init__(self, game: "Game"):
        self._game = game
        self._board_size = game.board_size
        self._cache: Dict[int, StoneSet] = {}  # move_number -> stones

    def get_stones_at_move(self, move_number: int) -> StoneSet:
        """
        指定手番での石を取得（キャッシュあり）。

        Args:
            move_number: 1-indexed手番（0=root）

        Returns:
            FrozenSet of (col, row, player) tuples
        """
        if move_number in self._cache:
            return self._cache[move_number]

        node = self._find_node_by_move_number(move_number)
        if node is None:
            return frozenset()

        stones = compute_stones_at_node(node, self._board_size)
        self._cache[move_number] = stones
        return stones

    def _find_node_by_move_number(self, move_number: int) -> Optional["GameNode"]:
        """
        手番からノードを探索（mainline上）。

        Note:
            ordered_children[0] を使用してmainlineを辿る。
            これはKaTrain全体で使われる慣習（game.py:841参照）。
        """
        node = self._game.root
        for _ in range(move_number):
            if not node.children:
                return None
            # ordered_children[0] = mainline (game.py:841 pattern)
            node = node.ordered_children[0]
        return node
```

### 呼び出し頻度

- Critical 3: 最大3手 × 2ノード（親/子）= 最大6回
- キャッシュにより実質3-4回の計算で済む（親子が重複）

### 変化手順（variations）への対応

現時点ではmainlineのみをサポート。変化手順のCritical Moveは想定外。
将来的に必要になった場合は、`node.nodes_from_root`を直接使って再構築可能。

### Mainline解決ガード（Rev.6追加）

`_get_cluster_context_for_move()`でノード解決に失敗した場合、例外ではなくNoneを返す。

```python
def _get_cluster_context_for_move(
    game: "Game",
    move_number: int,
    lang: Optional[str],
    cache: Optional[StoneCache] = None,
) -> Optional[str]:
    """
    指定手番のクラスタ分類からContext文字列を取得。

    Mainline解決ガード（Rev.6）:
      - move_numberがmainline上で解決できない場合はNoneを返す
      - 例外は全てキャッチしてNoneを返す

    Returns:
        ローカライズされたラベル文字列、または None（注入スキップ）
    """
    try:
        # キャッシュまたは直接ノード解決
        if cache:
            parent_stones = cache.get_stones_at_move(move_number - 1)
            child_stones = cache.get_stones_at_move(move_number)
            # 空のStoneSetはOK（root等）、Noneが返ることはない
        else:
            # 直接ノード解決
            child_node = game._find_node_by_move_number(move_number)
            if child_node is None:
                return None  # mainline上に存在しない → スキップ

            parent_node = child_node.parent
            if parent_node is None:
                return None  # root → スキップ

            parent_stones = compute_stones_at_node(parent_node, game.board_size)
            child_stones = compute_stones_at_node(child_node, game.board_size)

        # ... 以降の分類ロジック ...

    except Exception:
        return None  # 全例外をキャッチして安全にスキップ
```

---

## クラスタ座標→石のマッピング（Rev.3）

### 座標規約

```python
# OwnershipCluster.coords: FrozenSet[Tuple[int, int]]
# 座標は (col, row) で 0-indexed
# col: 左から右 (0 = 左端)
# row: 下から上 (0 = 下辺) ← KataGo/ownership_cluster.pyの規約

# StonePosition: Tuple[int, int, str]
# 座標は (col, row, player) で 0-indexed
# 同じ座標規約
```

### マッピング関数

```python
def get_stones_in_cluster(
    cluster: OwnershipCluster,
    stones: StoneSet,
) -> Tuple[StonePosition, ...]:
    """
    クラスタ内の石を抽出。

    Args:
        cluster: OwnershipCluster
        stones: 全石のセット

    Returns:
        クラスタ内の石のタプル（ソート済み）
    """
    cluster_points: FrozenSet[Tuple[int, int]] = cluster.coords
    stones_in_cluster = [
        (col, row, player)
        for (col, row, player) in stones
        if (col, row) in cluster_points
    ]
    # 決定論的な順序
    return tuple(sorted(stones_in_cluster))
```

### ユニットテスト

```python
def test_get_stones_in_cluster_mapping():
    """座標マッピングの決定論的テスト。"""
    cluster = OwnershipCluster(
        coords=frozenset([(0, 0), (1, 0), (0, 1)]),  # 左下の3点
        cluster_type=ClusterType.TO_WHITE,
        sum_delta=-3.0,
        avg_delta=-1.0,
        max_abs_delta=1.0,
        primary_area=BoardArea.CORNER,
        cell_count=3,
    )
    stones: StoneSet = frozenset([
        (0, 0, "B"),  # クラスタ内
        (1, 0, "B"),  # クラスタ内
        (2, 0, "W"),  # クラスタ外
        (0, 1, "B"),  # クラスタ内
    ])

    result = get_stones_in_cluster(cluster, stones)

    assert result == ((0, 0, "B"), (0, 1, "B"), (1, 0, "B"))  # ソート済み
```

---

## 言語コード処理（Rev.3）

### API契約: lang: Optional[str]

```python
from katrain.common.locale_utils import normalize_lang_code

def get_semantics_label(semantics: ClusterSemantics, lang: Optional[str]) -> str:
    """
    クラスタ分類のローカライズラベルを取得。

    Args:
        lang: 言語コード（None, "", "jp", "ja", "en", "en_US"など）
              None/"" の場合は "en" にフォールバック

    Returns:
        ローカライズされたラベル
    """
    # normalize_lang_code(None) -> "en"
    # normalize_lang_code("") -> "en"
    # normalize_lang_code("ja") -> "jp"
    # normalize_lang_code("jp") -> "jp"
    # normalize_lang_code("en") -> "en"
    # normalize_lang_code("fr") -> "en"
    internal_lang = normalize_lang_code(lang)

    labels = SEMANTICS_LABELS.get(semantics, SEMANTICS_LABELS[ClusterSemantics.AMBIGUOUS])
    return labels.get(internal_lang, labels["en"])
```

### テストケース

```python
def test_get_semantics_label_none():
    assert get_semantics_label(ClusterSemantics.GROUP_DEATH, None) == "Group captured"

def test_get_semantics_label_empty():
    assert get_semantics_label(ClusterSemantics.GROUP_DEATH, "") == "Group captured"

def test_get_semantics_label_jp():
    assert get_semantics_label(ClusterSemantics.GROUP_DEATH, "jp") == "石が取られた"

def test_get_semantics_label_ja():
    assert get_semantics_label(ClusterSemantics.GROUP_DEATH, "ja") == "石が取られた"

def test_get_semantics_label_en():
    assert get_semantics_label(ClusterSemantics.GROUP_DEATH, "en") == "Group captured"

def test_get_semantics_label_unknown():
    assert get_semantics_label(ClusterSemantics.GROUP_DEATH, "fr") == "Group captured"
```

---

## 信頼度/ノイズ制御（Rev.3）

### 問題: TERRITORY_LOSSが注入されすぎる

Rev.2では `base=0.4, threshold=0.3` で、ほぼ全ての territory 変動が注入される。

### 解決策: semantics別閾値 + sum_delta最小値

```python
# 基本信頼度（分類タイプ別）
BASE_CONFIDENCE: Dict[ClusterSemantics, float] = {
    ClusterSemantics.GROUP_DEATH: 0.7,      # 石の消失は具体的
    ClusterSemantics.MISSED_KILL: 0.5,      # 閾値判定
    ClusterSemantics.TERRITORY_LOSS: 0.3,   # フォールバック的（下げた）
    ClusterSemantics.AMBIGUOUS: 0.0,
}

# 分類ごとの注入閾値
INJECTION_THRESHOLD: Dict[ClusterSemantics, float] = {
    ClusterSemantics.GROUP_DEATH: 0.3,      # 低め（石取りは重要）
    ClusterSemantics.MISSED_KILL: 0.4,      # 中程度
    ClusterSemantics.TERRITORY_LOSS: 0.5,   # 高め（ノイズ削減）
    ClusterSemantics.AMBIGUOUS: 1.0,        # 注入しない
}

# Territory Loss の最小 |sum_delta|
TERRITORY_LOSS_MIN_DELTA = 1.0  # 1目以上の変動のみ


def should_inject(classified: ClassifiedCluster) -> bool:
    """
    分類をKarteに注入すべきか判定。

    Returns:
        True if injection should occur
    """
    threshold = INJECTION_THRESHOLD.get(classified.semantics, 1.0)

    # TERRITORY_LOSS は追加条件
    if classified.semantics == ClusterSemantics.TERRITORY_LOSS:
        if abs(classified.cluster.sum_delta) < TERRITORY_LOSS_MIN_DELTA:
            return False

    return classified.confidence >= threshold
```

### 信頼度計算（決定論的）

```python
DELTA_SCALING_FACTOR = 0.1  # |sum_delta| * 0.1 を加算

def compute_confidence(
    semantics: ClusterSemantics,
    sum_delta: float,
    affected_stone_count: int,
) -> float:
    """
    分類の信頼度を計算（0.0-1.0）。

    計算式:
        confidence = base + |sum_delta| * DELTA_SCALING_FACTOR + stone_bonus
        capped to [0.0, 1.0]
    """
    base = BASE_CONFIDENCE.get(semantics, 0.0)
    delta_bonus = abs(sum_delta) * DELTA_SCALING_FACTOR
    stone_bonus = min(0.2, affected_stone_count * 0.05) if affected_stone_count > 0 else 0.0

    confidence = base + delta_bonus + stone_bonus
    return max(0.0, min(1.0, confidence))
```

### ノイズ削減テスト

```python
def test_low_impact_territory_not_injected():
    """小さなTerritory変動は注入されない。"""
    classified = ClassifiedCluster(
        cluster=OwnershipCluster(
            coords=frozenset([(0, 0)]),
            cluster_type=ClusterType.TO_WHITE,
            sum_delta=-0.5,  # 0.5目 < 1.0
            avg_delta=-0.5,
            max_abs_delta=0.5,
            primary_area=BoardArea.CENTER,
            cell_count=1,
        ),
        semantics=ClusterSemantics.TERRITORY_LOSS,
        confidence=0.35,  # > 0.3 だが < 0.5
        affected_stones=(),
        debug_reason="small territory change",
    )

    assert not should_inject(classified)  # 注入されない


def test_significant_territory_injected():
    """大きなTerritory変動は注入される。"""
    classified = ClassifiedCluster(
        cluster=OwnershipCluster(
            coords=frozenset([(0, 0), (1, 0), (2, 0)]),
            cluster_type=ClusterType.TO_WHITE,
            sum_delta=-3.0,  # 3目 >= 1.0
            avg_delta=-1.0,
            max_abs_delta=1.0,
            primary_area=BoardArea.CORNER,
            cell_count=3,
        ),
        semantics=ClusterSemantics.TERRITORY_LOSS,
        confidence=0.6,  # >= 0.5
        affected_stones=(),
        debug_reason="corner invasion",
    )

    assert should_inject(classified)  # 注入される
```

---

## Missed Kill閾値（符号混乱を排除 - Rev.4）

### 方針: 正の閾値のみ使用、actor視点に変換してから比較

### Ownership平均の計算（Rev.5: OwnershipContext使用）

**入力**: クラスタ座標のownership値の平均

```python
def compute_cluster_ownership_avg(
    cluster: OwnershipCluster,
    ownership_ctx: OwnershipContext,
) -> float:
    """
    クラスタ内座標のownership値の平均を計算。

    Phase 81のOwnershipContext.get_ownership_at()を使用し、
    座標アクセスの一貫性を保証。

    Args:
        cluster: OwnershipCluster（座標セットを含む）
        ownership_ctx: Phase 81のOwnershipContext

    Returns:
        クラスタ内のownership平均（黒視点）
        座標が範囲外の場合は0.0として扱う

    Note:
        +1.0 = 黒の確定地、-1.0 = 白の確定地、0 = 半々。
    """
    if not cluster.coords or ownership_ctx.ownership_grid is None:
        return 0.0

    total = 0.0
    valid_count = 0
    for col, row in cluster.coords:
        # OwnershipContext.get_ownership_at() を使用
        val = ownership_ctx.get_ownership_at((col, row))
        if val is not None:
            total += val
            valid_count += 1

    return total / valid_count if valid_count > 0 else 0.0
```

### 判定ロジック

```python
WEAK_ADVANTAGE_THRESHOLD = 0.3   # 親ノードでactorが有利だった閾値
SURVIVED_ADVANTAGE_THRESHOLD = 0.3  # 子ノードでopponentが生還した閾値

def is_missed_kill(
    parent_ownership_avg: float,
    child_ownership_avg: float,
    actor: str,
) -> bool:
    """
    Missed Kill判定。

    ownership（黒視点）をactor視点に変換し、正の閾値で判定。

    判定ロジック:
        1. ownership を actor視点に変換（actor="W"なら符号反転）
        2. 親ノードでactorが有利（actor_adv_parent >= WEAK_ADVANTAGE_THRESHOLD）
           → actorがその領域を取れそうだった
        3. 子ノードでopponentが有利（actor_adv_child <= -SURVIVED_ADVANTAGE_THRESHOLD）
           → opponentが生還した

    例: actor="B"（黒がミスした）、クラスタ = 白の弱石周辺
        親: ownership_avg = 0.4（黒が取れそう）
        子: ownership_avg = -0.4（白が生還）
        → Missed Kill

    例: actor="W"（白がミスした）、クラスタ = 黒の弱石周辺
        親: ownership_avg = -0.4（白視点で+0.4 = 取れそう）
        子: ownership_avg = 0.4（白視点で-0.4 = 黒が生還）
        → Missed Kill
    """
    if actor == "B":
        actor_adv_parent = parent_ownership_avg
        actor_adv_child = child_ownership_avg
    else:
        actor_adv_parent = -parent_ownership_avg
        actor_adv_child = -child_ownership_avg

    actor_was_advantaged = actor_adv_parent >= WEAK_ADVANTAGE_THRESHOLD
    opponent_now_advantaged = actor_adv_child <= -SURVIVED_ADVANTAGE_THRESHOLD

    return actor_was_advantaged and opponent_now_advantaged
```

### Ownership取得のソース（Rev.5: Phase 81ヘルパー再利用）

**重要**: Phase 81で定義された`extract_ownership_context()`を再利用し、座標変換の一貫性を保証。

```python
# board_context.py の extract_ownership_context() を使用
from katrain.core.analysis.board_context import extract_ownership_context, OwnershipContext

def get_ownership_context_pair(
    parent_node: "GameNode",
    child_node: "GameNode",
) -> Optional[Tuple[OwnershipContext, OwnershipContext]]:
    """
    親子ノードのOwnershipContextを取得。

    どちらかのownership_gridがNoneなら全体としてNoneを返す。
    Phase 81のextract_ownership_context()を再利用し座標変換の一貫性を保証。

    Returns:
        (parent_ctx, child_ctx) or None
    """
    parent_ctx = extract_ownership_context(parent_node)
    child_ctx = extract_ownership_context(child_node)

    # どちらかのgridがNoneなら注入しない（Rev.5契約）
    if parent_ctx.ownership_grid is None or child_ctx.ownership_grid is None:
        return None

    return (parent_ctx, child_ctx)
```

**座標変換の根拠**（Phase 81 board_context.py:194）:

```python
# extract_ownership_context() 内部で var_to_grid() を呼ぶ
ownership_grid = var_to_grid(list(ownership), final_size)

# var_to_grid (utils.py:15-22):
# KataGo 1D出力 → grid[row][col], row 0 = 盤面下辺
for y in range(size[1] - 1, -1, -1):  # y を逆順に
    grid[y] = array_var[ix : ix + size[0]]
```

**ClusterClassificationContext（ownership欠損時は生成しない）**:

```python
@dataclass(frozen=True)
class ClusterClassificationContext:
    """分類に必要なコンテキスト。

    Note:
        ownership_gridは常にNone以外（生成時にチェック済み）。
        どちらかのownershipが欠損している場合、このcontextは生成されない。
    """
    actor: str  # ミスをした側 ("B" or "W") = CriticalMove.player
    parent_stones: StoneSet  # 親ノードの石
    child_stones: StoneSet   # 子ノードの石
    parent_ownership_ctx: OwnershipContext  # Phase 81のOwnershipContext
    child_ownership_ctx: OwnershipContext   # Phase 81のOwnershipContext
    board_size: Tuple[int, int]
```

---

## ファイル構成

### 新規作成

| ファイル | 内容 | 行数目安 |
|----------|------|:--------:|
| `katrain/core/analysis/cluster_classifier.py` | 3分類ロジック + 石再構築 + キャッシュ | ~400行 |
| `tests/test_cluster_classifier.py` | ユニットテスト | ~400行 |

### 変更

| ファイル | 変更内容 | 行数目安 |
|----------|----------|:--------:|
| `katrain/core/reports/karte/sections/important_moves.py` | Context注入ロジック追加 | +50行 |
| `katrain/core/analysis/__init__.py` | エクスポート追加 | +2行 |

---

## データモデル定義

### ClusterSemantics Enum

```python
class ClusterSemantics(str, Enum):
    """クラスタの意味的分類。"""
    GROUP_DEATH = "group_death"        # actorの石が取られた
    TERRITORY_LOSS = "territory_loss"  # actorの地が減った
    MISSED_KILL = "missed_kill"        # opponentを殺し損ねた
    AMBIGUOUS = "ambiguous"            # 判定不能
```

### StonePosition 型エイリアス

```python
StonePosition = Tuple[int, int, str]  # (col, row, player) where player is "B" or "W"
StoneSet = FrozenSet[StonePosition]
```

### ClassifiedCluster Dataclass

```python
@dataclass(frozen=True)
class ClassifiedCluster:
    """分類済みクラスタ。"""
    cluster: OwnershipCluster
    semantics: ClusterSemantics
    confidence: float  # 0.0-1.0
    affected_stones: Tuple[StonePosition, ...]  # (col, row, player)
    debug_reason: str  # テスト・ログ用の説明
```

### ClusterClassificationContext Dataclass（Rev.5更新）

```python
@dataclass(frozen=True)
class ClusterClassificationContext:
    """分類に必要なコンテキスト。

    Note:
        このcontextはownership_gridが両ノードで利用可能な場合のみ生成される。
        欠損時は生成されず、_get_cluster_context_for_move()がNoneを返す。
    """
    actor: str  # ミスをした側 ("B" or "W") = CriticalMove.player
    parent_stones: StoneSet  # 親ノードの石
    child_stones: StoneSet   # 子ノードの石
    parent_ownership_ctx: OwnershipContext  # Phase 81のOwnershipContext（gridはNone以外保証）
    child_ownership_ctx: OwnershipContext   # Phase 81のOwnershipContext（gridはNone以外保証）
    board_size: Tuple[int, int]
```

**Ownership欠損時の契約（Rev.5追加）**:

```python
def build_classification_context(
    actor: str,
    parent_node: "GameNode",
    child_node: "GameNode",
    parent_stones: StoneSet,
    child_stones: StoneSet,
) -> Optional[ClusterClassificationContext]:
    """
    分類コンテキストを構築。

    どちらかのノードでownershipが欠損している場合はNoneを返す。
    これにより、Karte注入はスキップされる。

    Returns:
        ClusterClassificationContext or None (if ownership missing)
    """
    ownership_pair = get_ownership_context_pair(parent_node, child_node)
    if ownership_pair is None:
        return None  # ownership欠損→注入なし

    parent_ctx, child_ctx = ownership_pair
    return ClusterClassificationContext(
        actor=actor,
        parent_stones=parent_stones,
        child_stones=child_stones,
        parent_ownership_ctx=parent_ctx,
        child_ownership_ctx=child_ctx,
        board_size=parent_ctx.board_size,
    )
```

---

## API契約

### classify_cluster（常にClassifiedClusterを返す）

```python
def classify_cluster(
    cluster: OwnershipCluster,
    ctx: ClusterClassificationContext,
) -> ClassifiedCluster:
    """
    クラスタを3分類に分類する。

    Returns:
        ClassifiedCluster - 常に返す（判定不能時はAMBIGUOUS）

    Note:
        例外は発生しない（内部でキャッチしてAMBIGUOUSを返す）
    """
```

### _get_cluster_context_for_move（Optional[str]を返す）

```python
def _get_cluster_context_for_move(
    game: "Game",
    move_number: int,
    lang: Optional[str],
    cache: Optional[StoneCache] = None,
) -> Optional[str]:
    """
    指定手番のクラスタ分類からContext文字列を取得。

    Args:
        game: Gameオブジェクト
        move_number: 1-indexed手番
        lang: 言語コード（Optional、Noneは"en"）
        cache: 石のキャッシュ（再利用時に指定）

    Returns:
        ローカライズされたラベル文字列、または None

    Note:
        すべての例外をキャッチしてNoneを返す（Karte出力を壊さない）
    """
```

---

## Karte統合

### 変更箇所: important_moves.py:321-324

```python
# Before
if cm.reason_tags:
    lines.append(f"- **Context**: {', '.join(cm.reason_tags)}")
else:
    lines.append("- **Context**: (none)")

# After
if cm.reason_tags:
    lines.append(f"- **Context**: {', '.join(cm.reason_tags)}")
else:
    # Phase 82: reason_tagsが空のときのみクラスタ分類を注入
    # キャッシュは関数の外で作成し、複数のCritical Moveで共有
    cluster_context = _get_cluster_context_for_move(
        ctx.game, cm.move_number, ctx.lang, stone_cache
    )
    if cluster_context:
        lines.append(f"- **Context**: {cluster_context}")
    else:
        lines.append("- **Context**: (none)")
```

### キャッシュの利用

```python
def critical_3_section_for(...) -> List[str]:
    # ... existing code ...

    # Phase 82: キャッシュを作成（Critical 3全体で共有）
    stone_cache = StoneCache(ctx.game) if player_critical else None

    for i, cm in enumerate(player_critical, 1):
        # ... lines for each critical move ...
        if cm.reason_tags:
            lines.append(f"- **Context**: {', '.join(cm.reason_tags)}")
        else:
            cluster_context = _get_cluster_context_for_move(
                ctx.game, cm.move_number, ctx.lang, stone_cache
            )
            if cluster_context:
                lines.append(f"- **Context**: {cluster_context}")
            else:
                lines.append("- **Context**: (none)")
```

---

## テスト計画

### ユニットテスト (test_cluster_classifier.py)

| テストグループ | 内容 |
|---------------|------|
| `TestClusterSemantics` | Enum値、str変換 |
| `TestIsOpponentGain` | sum_delta符号によるフィルタリング |
| `TestComputeStonesAtNode` | nodes_from_rootからの石再構築 |
| `TestGetStonesInCluster` | 座標マッピングの決定論的テスト |
| `TestDetectGroupDeath` | 単石/複数石の取り |
| `TestDetectTerritoryLoss` | ownership変動、sum_delta>=1.0条件 |
| `TestDetectMissedKill` | 閾値テスト、actor視点変換 |
| `TestComputeConfidence` | 決定論的計算、境界値テスト |
| `TestShouldInject` | semantics別閾値、ノイズ削減テスト |
| `TestGetSemanticsLabel` | lang=None, "", "jp", "ja", "en", unknown |
| `TestStoneCache` | キャッシュヒット、キャッシュミス、ordered_children |
| **`TestSuicideHandling`** | **自殺手は自グループを除去（Rev.6統一）** |
| **`TestOwnershipGridOrientation`** | **座標変換一貫性（Rev.6修正）** |
| **`TestMoveNumberIndexing`** | **1-indexed整合性** |
| **`TestOwnershipMissing`** | **parent/child ownership欠損** |
| **`TestAEOrderAfterPlacements`** | **AEはAB/AW後に適用（Rev.6追加）** |
| **`TestMainlineResolutionFailure`** | **mainline解決失敗→None（Rev.6追加）** |

### 盤面再構築の重要テスト（Rev.6: 内部座標で記述）

**重要: SGF座標規約**
```
SGF "aa" on 5x5 board:
  col = index('a') = 0
  row = 5 - index('a') - 1 = 4  ← TOP row (row 0 = bottom)

つまり: "aa" = (0, 4) = 左上隅、"ae" = (0, 0) = 左下隅
```

テストは**内部座標(col, row)**を直接使用し、SGF文字列の変換誤りを防ぐ。

```python
class TestComputeStonesAtNode:
    """盤面再構築のテスト（Rev.6: 内部座標で明確化）。"""

    def test_setup_stones_no_capture(self):
        """置き石（AB/AW）は取りを発生させない。

        5x5 Board (row 0 = bottom):

           0 1 2 3 4  (col)
        4  . . . . .   (row 4, top)
        3  . . . . .
        2  . . . . .
        1  W . . . .   (row 1) - (0,1)=W
        0  B B . . .   (row 0, bottom) - (0,0)=B, (1,0)=B

        内部座標で指定（SGF変換なし）。
        """
        node = create_mock_node_with_internal_coords(
            board_size=(5, 5),
            placements=[
                Move(coords=(0, 0), player="B"),  # 左下隅
                Move(coords=(1, 0), player="B"),  # その右
                Move(coords=(0, 1), player="W"),  # 1つ上
            ],
            moves=[],
        )
        stones = compute_stones_at_node(node, (5, 5))

        assert len(stones) == 3
        assert (0, 0, "B") in stones
        assert (1, 0, "B") in stones
        assert (0, 1, "W") in stones

    def test_setup_stones_corner_surrounded_not_captured(self):
        """AB/AWで囲まれても取りが発生しない。

        5x5 Board:

           0 1 2 3 4
        4  . . . . .
        3  . . . . .
        2  . . . . .
        1  W . . . .   (0,1)=W
        0  B W . . .   (0,0)=B, (1,0)=W

        黒(0,0)は呼吸点0だが、AB/AWなので取られない。
        """
        node = create_mock_node_with_internal_coords(
            board_size=(5, 5),
            placements=[
                Move(coords=(0, 0), player="B"),  # 左下隅、囲まれている
                Move(coords=(0, 1), player="W"),
                Move(coords=(1, 0), player="W"),
            ],
            moves=[],
        )
        stones = compute_stones_at_node(node, (5, 5))

        # 全3石残る（セットアップでは取りなし）
        assert len(stones) == 3
        assert (0, 0, "B") in stones  # 囲まれていても残る

    def test_move_captures_opponent(self):
        """着手（B/W）で相手の石を取る。

        Initial (after setup):
           0 1 2 3 4
        4  . . . . .
        3  . . . . .
        2  . . . . .
        1  . . . . .
        0  W B . . .   (0,0)=W, (1,0)=B (setup)

        After B plays (0,1):
           0 1 2 3 4
        4  . . . . .
        3  . . . . .
        2  . . . . .
        1  B . . . .   (0,1)=B (capturing move)
        0  . B . . .   W at (0,0) captured!
        """
        node = create_mock_node_with_internal_coords(
            board_size=(5, 5),
            placements=[
                Move(coords=(0, 0), player="W"),  # 取られる白
                Move(coords=(1, 0), player="B"),  # 白の右
            ],
            moves=[
                Move(coords=(0, 1), player="B"),  # 白の上 → 囲み完成
            ],
        )
        stones = compute_stones_at_node(node, (5, 5))

        # 白は取られ、黒2子のみ
        assert len(stones) == 2
        assert (0, 0, "W") not in stones  # captured
        assert (1, 0, "B") in stones
        assert (0, 1, "B") in stones

    def test_ae_clears_stones(self):
        """AE（clear）は石を除去する。

        Setup: (0,0)=B, (1,0)=B
        AE: (0,0) cleared
        Result: (1,0)=B only
        """
        node = create_mock_node_with_internal_coords(
            board_size=(5, 5),
            placements=[
                Move(coords=(0, 0), player="B"),
                Move(coords=(1, 0), player="B"),
            ],
            clears=[Move(coords=(0, 0), player=None)],  # AE
        )
        stones = compute_stones_at_node(node, (5, 5))

        assert len(stones) == 1
        assert (1, 0, "B") in stones
        assert (0, 0, "B") not in stones  # cleared

    def test_suicide_move_removes_self(self):
        """自殺手は自グループを除去（Rev.6統一）。

        Setup:
           0 1 2 3 4
        4  . . . . .
        3  . . . . .
        2  . . . . .
        1  W . . . .   (0,1)=W
        0  . W . . .   (1,0)=W

        B plays (0,0) → suicide (no liberties) → removed
        """
        node = create_mock_node_with_internal_coords(
            board_size=(5, 5),
            placements=[
                Move(coords=(0, 1), player="W"),
                Move(coords=(1, 0), player="W"),
            ],
            moves=[
                Move(coords=(0, 0), player="B"),  # 自殺手
            ],
        )
        stones = compute_stones_at_node(node, (5, 5))

        # 黒は自殺で消え、白2子のみ
        assert len(stones) == 2
        assert (0, 0, "B") not in stones  # suicide removed
        assert (0, 1, "W") in stones
        assert (1, 0, "W") in stones

    def test_ae_order_after_placements(self):
        """AEはAB/AWの後に適用される（Rev.6追加）。

        SGF仕様: setup properties (AB/AW/AE) は同時に盤面状態を定義。
        実装順序: AB/AW → AE（AEで石を消せる）。

        Setup: (0,0)=B, (1,0)=B
        AE: (0,0)
        Result: (1,0)=B のみ（(0,0)はAEで消された）
        """
        node = create_mock_node_with_internal_coords(
            board_size=(5, 5),
            placements=[
                Move(coords=(0, 0), player="B"),
                Move(coords=(1, 0), player="B"),
            ],
            clears=[Move(coords=(0, 0), player=None)],  # AE same node
        )
        stones = compute_stones_at_node(node, (5, 5))

        # AEがAB/AWの後に適用され、(0,0)が消される
        assert len(stones) == 1
        assert (0, 0, "B") not in stones
        assert (1, 0, "B") in stones
```

### 統合テスト (test_karte_cluster_context.py)

| テスト | 内容 |
|--------|------|
| `test_context_injected_when_reason_tags_empty` | reason_tags空 + クラスタあり → 注入 |
| `test_context_not_injected_when_reason_tags_present` | reason_tagsあり → 注入なし |
| `test_context_none_when_no_clusters` | クラスタなし → "(none)" |
| `test_context_none_on_exception` | 例外発生時 → "(none)" |
| `test_context_none_when_confidence_low` | confidence < threshold → "(none)" |
| `test_low_impact_territory_not_injected` | 小さなterritory変動 → "(none)" |
| `test_cache_reused_across_critical_moves` | キャッシュ共有の検証 |
| `test_context_none_when_parent_ownership_missing` | 親ノードownership欠損 → "(none)" |
| `test_context_none_when_child_ownership_missing` | 子ノードownership欠損 → "(none)" |
| `test_context_none_when_move_not_on_mainline` | mainline外のmove_number → "(none)" |

### Ownership Grid座標検証テスト（Rev.6修正）

```python
def test_ownership_grid_coordinate_mapping():
    """座標変換がPhase 81と一致することを検証。

    KataGo ownership (1D) → var_to_grid() → ownership_grid[row][col]

    var_to_grid の動作 (utils.py:15-22):
      1D index 0-4   → grid[4] (top row)
      1D index 20-24 → grid[0] (bottom row)

    つまり KataGo 1D は row 0 = top、var_to_grid で反転して grid[0] = bottom。
    """
    from katrain.core.analysis.board_context import extract_ownership_context
    from katrain.core.sgf_parser import Move

    board_size = (5, 5)

    # 左下隅(internal: col=0, row=0)に黒優勢+0.9を設定
    # var_to_grid反転後: grid[0][0] = 1D array index 20
    ownership_1d = [0.0] * 25
    ownership_1d[20] = 0.9  # grid[0][0] after var_to_grid

    node = create_mock_node_with_ownership(board_size, ownership_1d)
    ctx = extract_ownership_context(node)

    # 内部座標 (0, 0) = 左下隅
    assert ctx.ownership_grid[0][0] == 0.9  # 左下隅
    assert ctx.ownership_grid[4][4] == 0.0  # 右上隅

    # SGF座標 "aa" の内部座標を確認
    # SGF "aa" = (col=0, row=4) = 左上隅（NOT 左下隅！）
    move_aa = Move.from_sgf("aa", board_size, player="B")
    assert move_aa.coords == (0, 4)  # 左上隅

    # SGF "ae" = (col=0, row=0) = 左下隅
    move_ae = Move.from_sgf("ae", board_size, player="B")
    assert move_ae.coords == (0, 0)  # 左下隅

    # クラスタ座標との整合性
    # cluster.coords = {(col, row)} なので {(0, 0)} = 左下隅
    cluster_coords = frozenset([(0, 0)])
    # OwnershipContext.get_ownership_at() は (col, row) を受け取る
    avg = sum(ctx.get_ownership_at((col, row)) or 0.0 for col, row in cluster_coords) / len(cluster_coords)
    assert avg == 0.9
```

### Move Number Indexing検証テスト（Rev.6: 内部座標で記述）

```python
def test_move_number_indexing_consistency():
    """CriticalMove.move_numberとStoneCache.get_stones_at_moveの整合性。

    CriticalMove.move_number: 1-indexed (models.py:281)
    Game._find_node_by_move_number: 1-indexed (game.py:586-599)
    StoneCache.get_stones_at_move: 1-indexed (0=root)

    このテストで off-by-one エラーを防止。
    """
    # 内部座標で指定（SGF変換なし）
    game = create_mock_game_with_internal_moves([
        Move(coords=(0, 0), player="B"),  # move 1
        Move(coords=(1, 1), player="W"),  # move 2
        Move(coords=(2, 2), player="B"),  # move 3
    ])

    cache = StoneCache(game)

    # move_number=0 → root (石なし)
    stones_0 = cache.get_stones_at_move(0)
    assert len(stones_0) == 0

    # move_number=1 → 黒(0,0)配置後
    stones_1 = cache.get_stones_at_move(1)
    assert len(stones_1) == 1

    # move_number=2 → 黒(0,0) + 白(1,1)
    stones_2 = cache.get_stones_at_move(2)
    assert len(stones_2) == 2

    # CriticalMoveのmove_numberと同じ規約であることを確認
    node = game._find_node_by_move_number(2)
    assert len(node.nodes_from_root) - 1 == 2  # root含めて3ノード、move_number=2


def test_mainline_resolution_failure_returns_none():
    """mainline上に存在しないmove_numberはNoneを返す（Rev.6追加）。

    3手のゲームでmove_number=10を要求→None（注入スキップ）。
    """
    game = create_mock_game_with_internal_moves([
        Move(coords=(0, 0), player="B"),  # move 1
        Move(coords=(1, 1), player="W"),  # move 2
        Move(coords=(2, 2), player="B"),  # move 3
    ])

    # move_number=10はmainline上に存在しない
    result = _get_cluster_context_for_move(game, move_number=10, lang="en")
    assert result is None  # 注入スキップ


def test_move_number_zero_returns_none():
    """move_number=0（root）は親がないのでNoneを返す。"""
    game = create_mock_game_with_internal_moves([
        Move(coords=(0, 0), player="B"),
    ])

    # move_number=0 = root、親ノードがないので分類不可
    result = _get_cluster_context_for_move(game, move_number=0, lang="en")
    assert result is None
```

### 受け入れ基準（Acceptance Criteria）

**注入される場合（MUST）**:
1. `CriticalMove.reason_tags` が空タプル `()`
2. 該当手番に opponent gain クラスタが存在（sum_delta符号で判定）
3. `should_inject(classified)` が True

**注入されない場合（MUST NOT）**:
1. `CriticalMove.reason_tags` に1つ以上のタグがある
2. クラスタが存在しない
3. `should_inject(classified)` が False
4. 例外が発生

### ゴールデンテスト更新の注意

既存のKarteゴールデンテストで `reason_tags` が空のフィクスチャがある場合、出力が変わる可能性がある。

```powershell
# 変更確認後、必要に応じてゴールデン更新
uv run pytest tests/test_golden_karte.py --update-golden
```

---

## 信頼度閾値一覧

| 定数 | 値 | 用途 |
|------|-----|------|
| `BASE_CONFIDENCE[GROUP_DEATH]` | 0.7 | 石取りの基本信頼度 |
| `BASE_CONFIDENCE[MISSED_KILL]` | 0.5 | 殺し損ねの基本信頼度 |
| `BASE_CONFIDENCE[TERRITORY_LOSS]` | 0.3 | 地変動の基本信頼度 |
| `INJECTION_THRESHOLD[GROUP_DEATH]` | 0.3 | 石取りの注入閾値 |
| `INJECTION_THRESHOLD[MISSED_KILL]` | 0.4 | 殺し損ねの注入閾値 |
| `INJECTION_THRESHOLD[TERRITORY_LOSS]` | 0.5 | 地変動の注入閾値 |
| `TERRITORY_LOSS_MIN_DELTA` | 1.0 | 地変動の最小sum_delta |
| `WEAK_ADVANTAGE_THRESHOLD` | 0.3 | Missed Kill: 親でactorが有利 |
| `SURVIVED_ADVANTAGE_THRESHOLD` | 0.3 | Missed Kill: 子でopponentが有利 |
| `DELTA_SCALING_FACTOR` | 0.1 | 信頼度計算のスケーリング |

---

## リスク軽減策（Rev.6更新）

| リスク | 対策 |
|--------|------|
| UI副作用 | current_nodeを変更しない（nodes_from_rootから再構築） |
| 並行処理 | 純粋関数、状態変更なし |
| 分類精度 | semantics別閾値 + sum_delta最小値でノイズ削減 |
| 安定性 | _get_cluster_context_for_move で全例外キャッチ→None |
| パフォーマンス | move_numberでキャッシュ + deque使用 |
| ゴールデン破壊 | テスト前にゴールデン出力を確認、必要に応じて更新 |
| AB/AW誤処理 | placements/moves分離処理（Rev.4） |
| mainline逸脱 | ordered_children[0]使用（Rev.4） |
| 座標不整合 | sgf_parser.py参照の明示（Rev.4） |
| 自殺手 | 自グループを除去（Rev.6統一） |
| Ownership欠損 | parent/child両方必須、欠損→None |
| 座標変換不一致 | Phase 81のextract_ownership_context()再利用 |
| move_number off-by-one | 1-indexed確認テスト追加 |
| **SGF座標誤解** | **テストは内部座標(col,row)で記述（Rev.6）** |
| **AE順序** | **AB/AW→B/W→AEの順序を明示（Rev.6）** |
| **mainline解決失敗** | **解決失敗→None返却のガード追加（Rev.6）** |

---

## 検証手順

1. **新規テスト**: `uv run pytest tests/test_cluster_classifier.py -v`
2. **既存Karteテスト**: `uv run pytest tests/test_karte*.py -v`
3. **ゴールデンテスト**: `uv run pytest tests/test_golden_karte.py -v`
4. **起動確認**: `python -m katrain`
5. **実際のKarte出力**: SGFを読み込み、Karteエクスポートで確認

---

## 変更ファイル一覧

| ファイル | 種別 |
|----------|------|
| `katrain/core/analysis/cluster_classifier.py` | 新規 |
| `katrain/core/analysis/__init__.py` | 変更（エクスポート追加） |
| `katrain/core/reports/karte/sections/important_moves.py` | 変更（Context注入） |
| `tests/test_cluster_classifier.py` | 新規 |
| `tests/test_karte_cluster_context.py` | 新規（統合テスト） |
