"""
eval_metrics.py - KARTE 解析の基盤モジュール

Perspective Convention (視点規約)
=================================

このモジュールでは以下の視点規約を使用:

1. **BLACK-PERSPECTIVE (黒視点)**:
   - score_before, score_after: 正=黒有利、負=白有利
   - delta_score, delta_winrate: 黒視点での変化量
   - KataGo / GameNode からの値をそのまま使用

2. **SIDE-TO-MOVE (手番視点)**:
   - points_lost: その手を打ったプレイヤーにとっての損失
   - GameNode.points_lost は内部で player_sign を適用済み

3. **CANONICAL LOSS (正準損失)**:
   - 常に >= 0 の損失値
   - compute_canonical_loss() で計算
   - points_lost を優先、delta からのフォールバックあり

重要: delta_score/delta_winrate は BLACK-PERSPECTIVE のまま保持。
      損失計算には compute_canonical_loss() を使用すること。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    List,
    Optional,
    Tuple,
    Dict,
)

# KaTrain 側の型に依存するのは最小限にする
#   - 型チェック時だけ GameNode を正しく import
#   - ランタイムでは Any として扱う
if TYPE_CHECKING:
    from katrain.core.game_node import GameNode
else:
    GameNode = Any


class MistakeCategory(Enum):
    """ミスの大きさを4段階で分類するカテゴリ。"""

    GOOD = "good"              # 実質問題なし
    INACCURACY = "inaccuracy"  # 軽い損
    MISTAKE = "mistake"        # はっきり損
    BLUNDER = "blunder"        # 大きな損

    def is_error(self) -> bool:
        """GOOD 以外ならミス扱い、といった判定用の補助メソッド。"""
        return self is not MistakeCategory.GOOD


# ---------------------------------------------------------------------------
# 基本データ構造
# ---------------------------------------------------------------------------


@dataclass
class MoveEval:
    """
    1 手分の評価情報を表す最小単位。

    Perspective (視点):
    - score_*, winrate_*, delta_*: BLACK-PERSPECTIVE (黒視点)
      - 正の値 = 黒有利 / 黒の方向に変化
    - points_lost: SIDE-TO-MOVE (手番視点)
      - 正の値 = その手を打ったプレイヤーにとっての損失

    損失計算には compute_canonical_loss() を使用すること。
    delta_score/delta_winrate を直接損失として使わないこと。
    """

    move_number: int                    # 手数（1, 2, 3, ...）
    player: Optional[str]               # 'B' / 'W' / None（ルートなど）
    gtp: Optional[str]                  # "D4" のような座標 or "pass" / None

    # 評価値（BLACK-PERSPECTIVE: 正=黒有利）
    score_before: Optional[float]       # この手を打つ前の評価
    score_after: Optional[float]        # この手を打った直後の評価
    delta_score: Optional[float]        # score_after - score_before (黒視点)

    winrate_before: Optional[float]     # この手を打つ前の勝率
    winrate_after: Optional[float]      # この手を打った直後の勝率
    delta_winrate: Optional[float]      # winrate_after - winrate_before (黒視点)

    # KaTrain 標準の指標（SIDE-TO-MOVE: 手番視点）
    points_lost: Optional[float]        # その手で失った期待値（手番視点、正=損失）
    realized_points_lost: Optional[float]  # 実際の進行で確定した損失
    root_visits: int                    # その局面の root 訪問回数（見ている深さの目安）
    is_reliable: bool = False           # visits を根拠にした信頼度フラグ（保守的に False）

    # 将来の拡張用メタ情報
    tag: Optional[str] = None           # "opening"/"middle"/"yose" など自由タグ
    importance_score: Optional[float] = None  # 後で計算する「重要度スコア」

    score_loss: Optional[float] = None
    """その手による地合損失（悪くなった分だけ、目単位）。"""

    winrate_loss: Optional[float] = None
    """その手による勝率損失（悪くなった分だけ、0〜1）。"""

    mistake_category: MistakeCategory = MistakeCategory.GOOD
    """ミス分類（GOOD / INACCURACY / MISTAKE / BLUNDER）。"""

    position_difficulty: Optional["PositionDifficulty"] = None
    """局面難易度（EASY / NORMAL / HARD / ONLY_MOVE / UNKNOWN など）。"""

    position_difficulty_score: Optional[float] = None
    """局面難易度を 0.0〜1.0 の連続値で表した補助スコア（大きいほど難しい想定）。"""

    reason_tags: List[str] = field(default_factory=list)
    """戦術的コンテキストの理由タグ（Phase 5: 構造の言語化）。

    例: ["atari", "low_liberties", "need_connect", "chase_mode", ...]
    盤面の戦術的状況に基づいて board_analysis モジュールで計算される。
    """


class PositionDifficulty(Enum):
    """局面難易度を表すラベル。"""

    EASY = "easy"        # 良い手が多く、多少ズレても致命傷になりにくい
    NORMAL = "normal"    # 標準的な難易度
    HARD = "hard"        # 良い手が少なく、正解の幅が狭い
    ONLY_MOVE = "only"   # ほぼ「この一手」に近い局面
    UNKNOWN = "unknown"  # 候補手情報が無いなどで評価不能


# ---------------------------------------------------------------------------
# 重要局面検出用の設定
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImportantMoveSettings:
    """重要局面の抽出条件をまとめた設定."""
    importance_threshold: float  # importance がこの値を超えたものだけ採用
    max_moves: int               # 最大件数（大きい順に上位だけ残す）


# 棋力イメージ別プリセット（あとで UI から切り替えやすくするための土台）
IMPORTANT_MOVE_SETTINGS_BY_LEVEL = {
    # 級位者向け: 本当に大きな損だけを拾う
    "easy": ImportantMoveSettings(
        importance_threshold=1.0,
        max_moves=10,
    ),
    # 標準: 現在の挙動に近い設定
    "normal": ImportantMoveSettings(
        importance_threshold=0.5,
        max_moves=20,
    ),
    # 段位者向け: 細かいヨセも含めて多めに拾う
    "strict": ImportantMoveSettings(
        importance_threshold=0.3,
        max_moves=40,
    ),
}

DEFAULT_IMPORTANT_MOVE_LEVEL = "normal"


# ---------------------------------------------------------------------------
# Canonical loss helper (used by EvalSnapshot, quiz, importance)
# ---------------------------------------------------------------------------


def get_canonical_loss_from_move(m: MoveEval) -> float:
    """
    MoveEval から正準損失 (canonical loss) を取得する。

    優先順位:
      1) score_loss が設定されていればそれを使用
      2) points_lost があれば max(points_lost, 0) を使用
      3) どちらもなければ 0.0

    Returns:
        float: 常に >= 0 の損失値
    """
    if m.score_loss is not None:
        return m.score_loss
    if m.points_lost is not None:
        return max(0.0, m.points_lost)
    return 0.0


# ---------------------------------------------------------------------------

@dataclass
class EvalSnapshot:
    """
    ある時点での「ゲーム全体の評価一覧」をまとめたスナップショット。

    プロパティについて:
    - total_points_lost: 生の points_lost 合計（負の値を含む、後方互換）
    - total_canonical_points_lost: score_loss 合計（>=0 のみ、推奨）
    - max_points_lost: 生の points_lost 最大値（後方互換）
    - max_canonical_points_lost: score_loss 最大値（推奨）
    - worst_move: points_lost 最大の手（後方互換）
    - worst_canonical_move: score_loss 最大の手（推奨）
    """

    moves: List[MoveEval] = field(default_factory=list)

    # -------------------------------------------------------------------------
    # Legacy properties (backward compatibility, may include negative values)
    # -------------------------------------------------------------------------

    @property
    def total_points_lost(self) -> float:
        """生の points_lost 合計（負の値を含む可能性あり）。後方互換用。"""
        return float(
            sum(m.points_lost for m in self.moves if m.points_lost is not None)
        )

    @property
    def max_points_lost(self) -> float:
        """生の points_lost 最大値。後方互換用。"""
        vals = [m.points_lost for m in self.moves if m.points_lost is not None]
        return float(max(vals)) if vals else 0.0

    @property
    def worst_move(self) -> Optional[MoveEval]:
        """points_lost 最大の手を返す。後方互換用。"""
        candidates = [m for m in self.moves if m.points_lost is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda m: m.points_lost or 0.0)

    # -------------------------------------------------------------------------
    # Canonical properties (always >= 0, recommended for loss calculations)
    # -------------------------------------------------------------------------

    @property
    def total_canonical_points_lost(self) -> float:
        """
        score_loss (正準損失) の合計。常に >= 0。

        score_loss が設定されていない場合は max(points_lost, 0) を使用。
        """
        total = 0.0
        for m in self.moves:
            if m.score_loss is not None:
                total += m.score_loss
            elif m.points_lost is not None:
                total += max(0.0, m.points_lost)
        return total

    @property
    def max_canonical_points_lost(self) -> float:
        """score_loss (正準損失) の最大値。"""
        vals = []
        for m in self.moves:
            if m.score_loss is not None:
                vals.append(m.score_loss)
            elif m.points_lost is not None:
                vals.append(max(0.0, m.points_lost))
        return float(max(vals)) if vals else 0.0

    @property
    def worst_canonical_move(self) -> Optional[MoveEval]:
        """score_loss 最大の手を返す。"""
        candidates = [m for m in self.moves if get_canonical_loss_from_move(m) > 0.0]
        if not candidates:
            # 全て良い手の場合は最初の手を返す（または None）
            return self.moves[0] if self.moves else None
        return max(candidates, key=get_canonical_loss_from_move)

    # -------------------------------------------------------------------------
    # Filtering methods
    # -------------------------------------------------------------------------

    def filtered(self, predicate: Callable[[MoveEval], bool]) -> "EvalSnapshot":
        return EvalSnapshot(moves=[m for m in self.moves if predicate(m)])

    def by_player(self, player: str) -> "EvalSnapshot":
        return self.filtered(lambda m: m.player == player)

    def first_n_moves(self, n: int) -> "EvalSnapshot":
        return EvalSnapshot(moves=self.moves[:n])

    def last_n_moves(self, n: int) -> "EvalSnapshot":
        if n <= 0:
            return EvalSnapshot()
        return EvalSnapshot(moves=self.moves[-n:])


# ---------------------------------------------------------------------------
# Multi-game summary structures (Phase 6)
# ---------------------------------------------------------------------------


@dataclass
class GameSummaryData:
    """1局分のデータ（複数局まとめ用）"""
    game_name: str
    player_black: str
    player_white: str
    snapshot: EvalSnapshot
    board_size: Tuple[int, int]
    date: Optional[str] = None


@dataclass
class SummaryStats:
    """複数局の集計統計"""
    player_name: str
    total_games: int = 0
    total_moves: int = 0
    total_points_lost: float = 0.0
    avg_points_lost_per_move: float = 0.0

    mistake_counts: Dict[MistakeCategory, int] = field(default_factory=dict)
    mistake_total_loss: Dict[MistakeCategory, float] = field(default_factory=dict)

    freedom_counts: Dict["PositionDifficulty", int] = field(default_factory=dict)

    phase_moves: Dict[str, int] = field(default_factory=dict)  # "opening"/"middle"/"yose"
    phase_loss: Dict[str, float] = field(default_factory=dict)

    # Phase × MistakeCategory クロス集計 (Phase 6.5で追加)
    phase_mistake_counts: Dict[Tuple[str, MistakeCategory], int] = field(default_factory=dict)
    phase_mistake_loss: Dict[Tuple[str, MistakeCategory], float] = field(default_factory=dict)

    worst_moves: List[Tuple[str, MoveEval]] = field(default_factory=list)  # (game_name, move)

    def get_mistake_percentage(self, category: MistakeCategory) -> float:
        """ミス分類の割合を計算"""
        if self.total_moves == 0:
            return 0.0
        count = self.mistake_counts.get(category, 0)
        return 100.0 * count / self.total_moves

    def get_mistake_avg_loss(self, category: MistakeCategory) -> float:
        """ミス分類ごとの平均損失を計算"""
        count = self.mistake_counts.get(category, 0)
        if count == 0:
            return 0.0
        total_loss = self.mistake_total_loss.get(category, 0.0)
        return total_loss / count

    def get_freedom_percentage(self, difficulty: "PositionDifficulty") -> float:
        """Freedom（手の自由度）の割合を計算"""
        if self.total_moves == 0:
            return 0.0
        count = self.freedom_counts.get(difficulty, 0)
        return 100.0 * count / self.total_moves

    def get_phase_percentage(self, phase: str) -> float:
        """局面タイプの割合を計算"""
        if self.total_moves == 0:
            return 0.0
        count = self.phase_moves.get(phase, 0)
        return 100.0 * count / self.total_moves

    def get_phase_avg_loss(self, phase: str) -> float:
        """局面タイプごとの平均損失を計算"""
        count = self.phase_moves.get(phase, 0)
        if count == 0:
            return 0.0
        total_loss = self.phase_loss.get(phase, 0.0)
        return total_loss / count

    def get_practice_priorities(self) -> List[str]:
        """統計から1-3個の練習優先項目を導出（Phase 6.5 改善版）"""
        priorities = []
        phase_name_ja = {"opening": "序盤", "middle": "中盤", "yose": "ヨセ"}

        # 1. Phase × Mistake クロス集計で最悪の組み合わせを特定
        if self.phase_mistake_loss:
            # (phase, category) ごとの損失を集計
            worst_combo = max(
                self.phase_mistake_loss.items(),
                key=lambda x: x[1],  # 損失の大きさでソート
                default=None
            )
            if worst_combo and worst_combo[1] > 0:
                phase, category = worst_combo[0]
                loss = worst_combo[1]
                count = self.phase_mistake_counts.get((phase, category), 0)
                cat_name_ja = {
                    MistakeCategory.BLUNDER: "大悪手",
                    MistakeCategory.MISTAKE: "悪手",
                    MistakeCategory.INACCURACY: "軽微なミス",
                }
                priorities.append(
                    f"**{phase_name_ja.get(phase, phase)}の{cat_name_ja.get(category, category.name)}を減らす**"
                    f"（{count}回、損失{loss:.1f}目）"
                )
        # フォールバック: クロス集計データがない場合は従来ロジック
        elif self.phase_loss:
            worst_phase = max(self.phase_loss.items(), key=lambda x: x[1], default=None)
            if worst_phase and worst_phase[1] > 0:
                priorities.append(
                    f"**{phase_name_ja.get(worst_phase[0], worst_phase[0])}の大きなミスを減らす**"
                    f"（損失: {worst_phase[1]:.1f}目）"
                )

        # 2. Freedom が高い（難しい）局面でのパフォーマンス
        hard_count = self.freedom_counts.get(PositionDifficulty.HARD, 0)
        only_count = self.freedom_counts.get(PositionDifficulty.ONLY_MOVE, 0)
        difficult_total = hard_count + only_count
        if difficult_total > 0 and self.total_moves > 0:
            difficult_pct = 100.0 * difficult_total / self.total_moves
            if difficult_pct > 15.0:  # 15%以上が難しい局面
                priorities.append(
                    f"**難しい局面での読みを改善**"
                    f"（{difficult_pct:.1f}%の手が狭い/一択）"
                )

        # 3. 全体的なミス率が高い
        mistake_count = self.mistake_counts.get(MistakeCategory.MISTAKE, 0)
        blunder_count = self.mistake_counts.get(MistakeCategory.BLUNDER, 0)
        serious_mistakes = mistake_count + blunder_count
        if serious_mistakes > 0 and self.total_moves > 0:
            serious_pct = 100.0 * serious_mistakes / self.total_moves
            if serious_pct > 5.0 and len(priorities) < 3:  # 5%以上がミス/大悪手
                priorities.append(
                    f"**全体的に悪手・大悪手を減らす**"
                    f"（{serious_mistakes}回、{serious_pct:.1f}%）"
                )

        # 最大3個に制限
        return priorities[:3]


# ---------------------------------------------------------------------------
# Phase × Mistake 集計（共有アグリゲータ）
# ---------------------------------------------------------------------------


@dataclass
class PhaseMistakeStats:
    """単局または複数局の Phase × Mistake 集計結果"""
    phase_mistake_counts: Dict[Tuple[str, str], int] = field(default_factory=dict)
    phase_mistake_loss: Dict[Tuple[str, str], float] = field(default_factory=dict)
    phase_moves: Dict[str, int] = field(default_factory=dict)
    phase_loss: Dict[str, float] = field(default_factory=dict)
    total_moves: int = 0
    total_loss: float = 0.0


def aggregate_phase_mistake_stats(
    moves: Iterable[MoveEval],
    *,
    score_thresholds: Optional[Tuple[float, float, float]] = None,
    board_size: int = 19,
) -> PhaseMistakeStats:
    """
    手のリストから Phase × Mistake クロス集計を行う共有アグリゲータ。

    single-game karte と multi-game summary の両方で使用できる。

    Args:
        moves: MoveEval のイテラブル（通常は snapshot.moves のフィルタ結果）
        score_thresholds: ミス分類の閾値 (inaccuracy, mistake, blunder)
                          None の場合はデフォルト (1.0, 3.0, 7.0) を使用
        board_size: 盤サイズ（9, 13, 19 など）。Phase分類に使用。

    Returns:
        PhaseMistakeStats: 集計結果

    Example:
        >>> player_moves = [m for m in snapshot.moves if m.player == "B"]
        >>> stats = aggregate_phase_mistake_stats(player_moves, board_size=13)
        >>> print(stats.phase_mistake_loss)
        {('middle', 'BLUNDER'): 15.2, ('opening', 'INACCURACY'): 3.5}
    """
    if score_thresholds is None:
        score_thresholds = (1.0, 3.0, 7.0)  # inaccuracy, mistake, blunder

    inaccuracy_th, mistake_th, blunder_th = score_thresholds

    result = PhaseMistakeStats()

    for mv in moves:
        if mv.points_lost is None:
            continue

        # Phase 判定（手数ベース、盤サイズ対応）
        phase = classify_game_phase(mv.move_number, board_size=board_size)

        # Mistake 分類
        loss = max(0.0, mv.points_lost)
        if loss < inaccuracy_th:
            category = "GOOD"
        elif loss < mistake_th:
            category = "INACCURACY"
        elif loss < blunder_th:
            category = "MISTAKE"
        else:
            category = "BLUNDER"

        # 集計
        key = (phase, category)
        result.phase_mistake_counts[key] = result.phase_mistake_counts.get(key, 0) + 1
        if loss > 0:
            result.phase_mistake_loss[key] = result.phase_mistake_loss.get(key, 0.0) + loss

        result.phase_moves[phase] = result.phase_moves.get(phase, 0) + 1
        if loss > 0:
            result.phase_loss[phase] = result.phase_loss.get(phase, 0.0) + loss

        result.total_moves += 1
        result.total_loss += loss

    return result


def get_practice_priorities_from_stats(
    stats: PhaseMistakeStats,
    *,
    max_priorities: int = 3,
) -> List[str]:
    """
    PhaseMistakeStats から練習優先項目を導出する。

    SummaryStats.get_practice_priorities() と同等のロジックだが、
    単局用にも使用できるよう分離した関数。

    Args:
        stats: 集計結果
        max_priorities: 最大優先項目数

    Returns:
        優先項目のリスト（日本語）
    """
    priorities = []
    phase_name_ja = {"opening": "序盤", "middle": "中盤", "yose": "ヨセ"}
    cat_names_ja = {
        "BLUNDER": "大悪手",
        "MISTAKE": "悪手",
        "INACCURACY": "軽微なミス",
    }

    # 1. Phase × Mistake で最悪の組み合わせを特定（GOODは除外）
    non_good_losses = [
        (k, v) for k, v in stats.phase_mistake_loss.items()
        if k[1] != "GOOD" and v > 0
    ]
    if non_good_losses:
        sorted_combos = sorted(non_good_losses, key=lambda x: x[1], reverse=True)
        # 上位2つを抽出
        for i, (key, loss) in enumerate(sorted_combos[:2]):
            phase, category = key
            count = stats.phase_mistake_counts.get(key, 0)
            priorities.append(
                f"**{phase_name_ja.get(phase, phase)}の{cat_names_ja.get(category, category)}を減らす**"
                f"（{count}回、損失{loss:.1f}目）"
            )

    # フォールバック: Phase別損失から最悪のフェーズを提案
    if not priorities and stats.phase_loss:
        worst_phase = max(stats.phase_loss.items(), key=lambda x: x[1], default=None)
        if worst_phase and worst_phase[1] > 0:
            priorities.append(
                f"**{phase_name_ja.get(worst_phase[0], worst_phase[0])}の大きなミスを減らす**"
                f"（損失: {worst_phase[1]:.1f}目）"
            )

    return priorities[:max_priorities]


# ---------------------------------------------------------------------------
# Quiz helper structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuizItem:
    """Large-mistake quiz entry derived from existing evaluations."""

    move_number: int
    player: Optional[str]
    loss: float


@dataclass(frozen=True)
class QuizConfig:
    """Configuration for extracting quiz items from an EvalSnapshot."""

    loss_threshold: float  # minimum loss (points) to consider a move
    limit: int             # maximum number of quiz items to return


@dataclass(frozen=True)
class ReasonTagThresholds:
    """Thresholds for reason tag detection (Phase 17)."""

    heavy_loss: float      # minimum loss for heavy_loss tag
    reading_failure: float  # minimum loss for reading_failure tag


@dataclass(frozen=True)
class SkillPreset:
    """Skill presets for quiz extraction and mistake thresholds."""

    quiz: QuizConfig
    score_thresholds: Tuple[float, float, float]
    winrate_thresholds: Tuple[float, float, float]
    reason_tag_thresholds: ReasonTagThresholds  # Phase 17


SKILL_PRESETS: Dict[str, SkillPreset] = {
    # Beginner: focus on large swings only (conservative thresholds).
    "beginner": SkillPreset(
        quiz=QuizConfig(loss_threshold=3.0, limit=10),
        score_thresholds=(2.0, 4.0, 8.0),
        winrate_thresholds=(0.08, 0.15, 0.30),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=20.0, reading_failure=25.0),
    ),
    # Standard: matches existing behavior (backward-compatible).
    "standard": SkillPreset(
        quiz=QuizConfig(loss_threshold=2.0, limit=10),
        score_thresholds=(1.0, 2.5, 5.0),
        winrate_thresholds=(0.05, 0.10, 0.20),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=15.0, reading_failure=20.0),
    ),
    # Advanced: more sensitive to small errors.
    "advanced": SkillPreset(
        quiz=QuizConfig(loss_threshold=1.0, limit=10),
        score_thresholds=(0.5, 1.5, 3.0),
        winrate_thresholds=(0.03, 0.07, 0.15),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=10.0, reading_failure=15.0),
    ),
}

DEFAULT_SKILL_PRESET = "standard"


def get_skill_preset(name: str) -> SkillPreset:
    """Return a skill preset, falling back to standard when unknown."""
    return SKILL_PRESETS.get(name, SKILL_PRESETS[DEFAULT_SKILL_PRESET])


# ---------------------------------------------------------------------------
# Reason tag labels (Phase 17, Option 0-B: centralized definition)
# ---------------------------------------------------------------------------

# 理由タグの日本語ラベル（カルテ・サマリーで使用）
REASON_TAG_LABELS: Dict[str, str] = {
    "atari": "アタリ (atari)",
    "low_liberties": "呼吸点少 (low liberties)",
    "cut_risk": "切断リスク (cut risk)",
    "need_connect": "連絡必要 (need connect)",
    "thin": "薄い形 (thin)",
    "chase_mode": "追込モード (chase mode)",
    "too_many_choices": "候補多数 (many choices)",
    "endgame_hint": "ヨセ局面 (endgame)",
    "heavy_loss": "大損失 (heavy loss)",
    "reading_failure": "読み抜け (reading failure)",
}


# Default configuration for the current quiz popup (backward-compatible).
QUIZ_CONFIG_DEFAULT = SKILL_PRESETS[DEFAULT_SKILL_PRESET].quiz


# ---------------------------------------------------------------------------
# 急場見逃し検出の棋力別閾値（Phase 5拡張）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UrgentMissConfig:
    """急場見逃しパターン検出の設定."""
    threshold_loss: float  # 損失閾値（この値を超える手を対象）
    min_consecutive: int   # 最小連続手数


# 棋力別の急場見逃し検出設定
URGENT_MISS_CONFIGS: Dict[str, UrgentMissConfig] = {
    # 級位者: 大石の生き死にでも見逃しやすい。30目以上の超大損失のみ検出
    "beginner": UrgentMissConfig(
        threshold_loss=30.0,
        min_consecutive=4
    ),
    # 標準: 20目超の損失で検出（有段者の急場見逃し）
    "standard": UrgentMissConfig(
        threshold_loss=20.0,
        min_consecutive=3
    ),
    # 高段者: より小さな急場（コウ、ヨセの急場）も検出
    "advanced": UrgentMissConfig(
        threshold_loss=15.0,
        min_consecutive=3
    ),
}


def get_urgent_miss_config(skill_preset: str) -> UrgentMissConfig:
    """Return urgent miss detection config for the given skill preset."""
    return URGENT_MISS_CONFIGS.get(skill_preset, URGENT_MISS_CONFIGS[DEFAULT_SKILL_PRESET])


@dataclass
class QuizChoice:
    """Choice shown in quiz mode for a single position."""

    move: str
    points_lost: Optional[float]


@dataclass
class QuizQuestion:
    """Quiz entry paired with candidate moves for the position before the mistake."""

    item: QuizItem
    choices: List[QuizChoice]
    best_move: Optional[str] = None
    node_before_move: Optional[GameNode] = None

    @property
    def has_analysis(self) -> bool:
        return self.node_before_move is not None and bool(self.choices)

# Backwards-compatible aliases used by existing helpers/UI.
DEFAULT_QUIZ_LOSS_THRESHOLD = QUIZ_CONFIG_DEFAULT.loss_threshold
DEFAULT_QUIZ_ITEM_LIMIT = QUIZ_CONFIG_DEFAULT.limit

# ---------------------------------------------------------------------------
# KaTrain GameNode とのブリッジ
# ---------------------------------------------------------------------------


def move_eval_from_node(node: GameNode) -> MoveEval:
    """
    KaTrain の GameNode 1 個から MoveEval を生成する。

    - GameNode.comment() 等の文字列には依存せず、
      数値的な評価値だけを見るようにする。
    - before/after/delta は snapshot_from_nodes 側で埋める。
    """
    move = getattr(node, "move", None)
    player = getattr(move, "player", None)
    gtp = move.gtp() if move is not None and hasattr(move, "gtp") else None

    score = getattr(node, "score", None)
    winrate = getattr(node, "winrate", None)
    points_lost = getattr(node, "points_lost", None)
    realized_points_lost = getattr(node, "parent_realized_points_lost", None)
    root_visits = getattr(node, "root_visits", 0) or 0

    # Position difficulty 計算（親ノードの候補手から判定）
    difficulty, difficulty_score = assess_position_difficulty_from_parent(node)

    # move_number の取得:
    # GameNode.move_number は初期値 0 のまま更新されないことがあるため、
    # depth プロパティ（SGFNode由来）を優先して使用する。
    # depth は SGF ツリー上の深さを正確に反映している。
    _move_number = getattr(node, "depth", None)
    if _move_number is None:
        # depth がない場合のフォールバック（通常は発生しない）
        _move_number = getattr(node, "move_number", 0) or 0

    return MoveEval(
        move_number=_move_number,
        player=player,
        gtp=gtp,
        score_before=None,
        score_after=score,
        delta_score=None,
        winrate_before=None,
        winrate_after=winrate,
        delta_winrate=None,
        points_lost=points_lost,
        realized_points_lost=realized_points_lost,
        root_visits=int(root_visits),
        position_difficulty=difficulty,
        position_difficulty_score=difficulty_score,
    )


# visits-based reliability (conservative defaults; tweakable later)
RELIABILITY_VISITS_THRESHOLD = 200
UNRELIABLE_IMPORTANCE_SCALE = 0.25
SWING_SCORE_SIGN_BONUS = 1.0
SWING_WINRATE_CROSS_BONUS = 1.0


def is_reliable_from_visits(root_visits: int, *, threshold: int = RELIABILITY_VISITS_THRESHOLD) -> bool:
    """
    visits のみを根拠にした簡易信頼度判定。

    - threshold 未満は False（保守的）。
    - Phase4.5 では stdev 等は見ない。
    """
    return int(root_visits or 0) >= threshold


def assess_position_difficulty_from_parent(
    node: GameNode,
    *,
    good_rel_threshold: float = 1.0,
    near_rel_threshold: float = 2.0,
) -> Tuple[Optional[PositionDifficulty], Optional[float]]:
    """
    親ノードの candidate_moves から局面難易度をざっくり評価する。

    - parent.candidate_moves は「手番側の候補手リスト」で、
      pointsLost / relativePointsLost を含むことを想定している。
    - relativePointsLost が小さい手が多いほど「易しい局面」、
      少ないほど「難しい局面」とみなす簡易ヒューリスティック。

    返り値:
        (PositionDifficulty, difficulty_score)
        - PositionDifficulty: EASY / NORMAL / HARD / ONLY_MOVE / UNKNOWN
        - difficulty_score: 0.0〜1.0 の連続値（大きいほど難しい）

    使用例:
        >>> difficulty, score = assess_position_difficulty_from_parent(node)
        >>> if difficulty == PositionDifficulty.ONLY_MOVE:
        ...     print("ほぼ一手しかない難しい局面")
    """
    parent = getattr(node, "parent", None)
    if parent is None:
        return None, None

    candidate_moves = getattr(parent, "candidate_moves", None)
    if not candidate_moves:
        return None, None

    good_moves: List[float] = []
    near_moves: List[float] = []

    for mv in candidate_moves:
        rel = mv.get("relativePointsLost")
        if rel is None:
            rel = mv.get("pointsLost")
        if rel is None:
            continue
        rel_f = float(rel)

        if rel_f <= good_rel_threshold:
            good_moves.append(rel_f)
        if rel_f <= near_rel_threshold:
            near_moves.append(rel_f)

    if not good_moves and not near_moves:
        return PositionDifficulty.UNKNOWN, None

    n_good = len(good_moves)
    n_near = len(near_moves)

    # ----- 簡易ルール -----
    # - ほぼ 1 手しか「損をしない手」がない → ONLY_MOVE
    # - 良い手が 2 手程度 → HARD
    # - 良い／そこそこ良い手がたくさん → EASY
    # - その中間 → NORMAL
    if n_good <= 1 and n_near <= 2:
        label = PositionDifficulty.ONLY_MOVE
        score = 1.0
    elif n_good <= 2:
        label = PositionDifficulty.HARD
        score = 0.8
    elif n_good >= 4 or n_near >= 6:
        label = PositionDifficulty.EASY
        score = 0.2
    else:
        label = PositionDifficulty.NORMAL
        score = 0.5

    return label, score


def snapshot_from_nodes(nodes: Iterable[GameNode]) -> EvalSnapshot:
    """
    任意の GameNode 群から EvalSnapshot を作成するユーティリティ。

    - nodes には「実際に打たれた手を持つノード」（move が None でない）を渡す想定。
    - score / winrate の before/after/delta は、この関数内で連鎖的に計算する。
    - position_difficulty, score_loss, mistake_category, importance を自動計算。

    使用例:
        >>> from katrain.core.game import Game
        >>> game = Game()
        >>> # ... 対局を進める ...
        >>> nodes = list(game.root.nodes_in_tree)
        >>> snapshot = snapshot_from_nodes(nodes)
        >>> print(f"Total moves: {len(snapshot.moves)}")
        >>> print(f"Total points lost: {snapshot.total_points_lost:.1f}")
    """
    # GameNode と MoveEval のペアを保持しておく
    node_evals: List[Tuple[GameNode, MoveEval]] = []

    for node in nodes:
        if getattr(node, "move", None) is None:
            continue
        mv = move_eval_from_node(node)
        node_evals.append((node, mv))

    # 手数順に並べる
    node_evals.sort(key=lambda pair: pair[1].move_number)

    # 連続する手から before / delta を埋める
    prev: Optional[MoveEval] = None
    for node, m in node_evals:
        if prev is not None:
            m.score_before = prev.score_after
            m.winrate_before = prev.winrate_after

            if m.score_before is not None and m.score_after is not None:
                m.delta_score = m.score_after - m.score_before
            else:
                m.delta_score = None

            if m.winrate_before is not None and m.winrate_after is not None:
                m.delta_winrate = m.winrate_after - m.winrate_before
            else:
                m.delta_winrate = None

        # score_loss / winrate_loss を計算
        # compute_canonical_loss を使用: points_lost を優先し、delta はフォールバック
        score_loss, winrate_loss = compute_canonical_loss(
            points_lost=m.points_lost,
            delta_score=m.delta_score,
            delta_winrate=m.delta_winrate,
            player=m.player,
        )
        m.score_loss = score_loss
        m.winrate_loss = winrate_loss

        # ミス分類（GOOD / INACCURACY / MISTAKE / BLUNDER）
        m.mistake_category = classify_mistake(
            score_loss=score_loss,
            winrate_loss=winrate_loss,
        )
        m.is_reliable = is_reliable_from_visits(m.root_visits)

        # position_difficulty は move_eval_from_node() で既に計算済み
        # （重複削除）

        prev = m

    # importance を自動計算（全手に対して）
    all_moves = [m for _, m in node_evals]
    compute_importance_for_moves(all_moves)

    # EvalSnapshot には MoveEval のみを渡す
    return EvalSnapshot(moves=all_moves)


# ここから下を eval_metrics.py の末尾に追加


def iter_main_branch_nodes(game: Any) -> Iterable[GameNode]:
    """
    KaTrain の Game インスタンスから、
    ルートからメイン分岐（main branch）と思われるノード列を順に返す。

    - root は通常「着手無しノード」なので、move を持つノードのみ yield する。
    - メイン分岐の判定は暫定:
        1) children のうち is_mainline==True のものがあればそれを優先
        2) それがなければ is_main==True を持つものを優先
        3) それもなければ children[0] をメインとみなす
    """
    root = getattr(game, "root", None)
    if root is None:
        return  # 何も yield しないジェネレータ

    node = root

    while True:
        # 実際に打たれた手を持つノードだけを対象にする
        if getattr(node, "move", None) is not None:
            yield node  # type: ignore[misc]

        children = getattr(node, "children", None)
        if not children:
            break

        # 1. is_mainline 優先
        main_children = [
            c for c in children if getattr(c, "is_mainline", False)
        ]
        # 2. 無ければ is_main
        if not main_children:
            main_children = [
                c for c in children if getattr(c, "is_main", False)
            ]

        # 3. それでも空なら、先頭 child をメイン扱い（暫定ルール）
        next_node = main_children[0] if main_children else children[0]
        node = next_node


def snapshot_from_game(game: Any) -> EvalSnapshot:
    """
    Game 全体（メイン分岐）から EvalSnapshot を生成するヘルパー。

    - Phase 1 では UI からは直接呼ばず、
      内部ロジックやデバッグ用途のエントリポイントとして使う想定。
    """
    nodes_iter = iter_main_branch_nodes(game)
    return snapshot_from_nodes(nodes_iter)


def quiz_items_from_snapshot(
    snapshot: EvalSnapshot,
    *,
    loss_threshold: float = DEFAULT_QUIZ_LOSS_THRESHOLD,
    limit: int = DEFAULT_QUIZ_ITEM_LIMIT,
    preset: Optional[str] = None,
) -> List[QuizItem]:
    """
    EvalSnapshot から「大きなミス」をクイズ形式で取り出す簡易ヘルパー。

    - score_loss (canonical loss, 常に >= 0) を優先し、なければ max(points_lost, 0) を用いる。
    - loss_threshold より大きいものだけを抽出し、損失の大きい順に返す。
    - preset を指定した場合は、その設定を優先する。
    """
    if not snapshot.moves or limit <= 0:
        return []

    if preset is not None:
        preset_cfg = get_skill_preset(preset).quiz
        loss_threshold = preset_cfg.loss_threshold
        limit = preset_cfg.limit

    items: List[QuizItem] = []
    for move in snapshot.moves:
        # score_loss も points_lost もない手はスキップ
        if move.score_loss is None and move.points_lost is None:
            continue
        loss_val = get_canonical_loss_from_move(move)
        if loss_val < loss_threshold:
            continue
        items.append(
            QuizItem(
                move_number=move.move_number,
                player=move.player,
                loss=float(loss_val),
            )
        )

    items.sort(key=lambda qi: qi.loss, reverse=True)
    return items[:limit]


def quiz_points_lost_from_candidate(
    candidate_move: Dict[str, Any],
    *,
    root_score: Optional[float],
    next_player: Optional[str],
) -> Optional[float]:
    """
    Extract a points-lost style metric from an existing candidate move entry.

    Preference order:
      1) explicit pointsLost
      2) relativePointsLost
      3) scoreLead difference from the root (if available)
    """
    if candidate_move.get("pointsLost") is not None:
        return float(candidate_move["pointsLost"])

    if candidate_move.get("relativePointsLost") is not None:
        return float(candidate_move["relativePointsLost"])

    if (
        root_score is not None
        and next_player is not None
        and candidate_move.get("scoreLead") is not None
    ):
        sign = GameNode.player_sign(next_player) if hasattr(GameNode, "player_sign") else (1 if next_player == "B" else -1)
        return sign * (root_score - float(candidate_move["scoreLead"]))

    return None


# ミス分類に使う閾値（Phase3 デフォルト＝standard）
SCORE_THRESHOLDS: Tuple[float, float, float] = SKILL_PRESETS[DEFAULT_SKILL_PRESET].score_thresholds
WINRATE_THRESHOLDS: Tuple[float, float, float] = SKILL_PRESETS[DEFAULT_SKILL_PRESET].winrate_thresholds


def compute_loss_from_delta(
    delta_score: Optional[float],
    delta_winrate: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """
    手番視点の delta_score / delta_winrate から損失量 (>=0) を計算する。

    - 良くなった手：loss = 0.0
    - 悪くなった手：loss = -delta

    注意: この関数は delta が既に手番視点であることを前提とする。
    黒視点の raw delta を渡す場合は、事前に player_sign を適用すること。
    """
    score_loss: Optional[float] = None
    winrate_loss: Optional[float] = None

    if delta_score is not None:
        score_loss = max(0.0, -delta_score)

    if delta_winrate is not None:
        winrate_loss = max(0.0, -delta_winrate)

    return score_loss, winrate_loss


def compute_canonical_loss(
    points_lost: Optional[float],
    delta_score: Optional[float] = None,
    delta_winrate: Optional[float] = None,
    player: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """
    正準的な損失量 (>=0) を計算する。

    優先順位:
      1) points_lost が利用可能なら max(points_lost, 0) を使用
         （points_lost は GameNode で既に player_sign が適用済み）
      2) delta_score/delta_winrate が利用可能ならフォールバック
         （注意: delta は黒視点の可能性があるため、player で補正）

    Args:
        points_lost: GameNode.points_lost（手番視点、正=損失）
        delta_score: score_after - score_before（黒視点の可能性あり）
        delta_winrate: winrate_after - winrate_before（黒視点の可能性あり）
        player: "B" or "W"（delta の視点補正に使用）

    Returns:
        (score_loss, winrate_loss): 両方とも >= 0 または None

    Perspective Convention:
        - GameNode.score/winrate: BLACK-PERSPECTIVE (from KataGo)
        - GameNode.points_lost: SIDE-TO-MOVE (uses player_sign internally)
        - delta_score/delta_winrate in MoveEval: Currently BLACK-PERSPECTIVE
          (score_after - score_before without player_sign)
        - This function returns: ALWAYS >= 0 (clamped loss magnitude)
    """
    score_loss: Optional[float] = None
    winrate_loss: Optional[float] = None

    # Primary: use points_lost if available (already has player_sign applied)
    if points_lost is not None:
        score_loss = max(0.0, points_lost)

    # Fallback: use delta with perspective correction
    if score_loss is None and delta_score is not None:
        # delta_score is black-perspective, need to convert to side-to-move
        player_sign = {"B": 1, "W": -1, None: 1}.get(player, 1)
        # For side-to-move: negative delta = loss
        # delta_black * player_sign = delta_side_to_move
        # loss = max(0, -delta_side_to_move)
        side_to_move_delta = player_sign * delta_score
        score_loss = max(0.0, -side_to_move_delta)

    # Winrate loss (same logic)
    if delta_winrate is not None:
        player_sign = {"B": 1, "W": -1, None: 1}.get(player, 1)
        side_to_move_delta = player_sign * delta_winrate
        winrate_loss = max(0.0, -side_to_move_delta)

    return score_loss, winrate_loss


def classify_mistake(
    score_loss: Optional[float],
    winrate_loss: Optional[float],
    *,
    score_thresholds: Tuple[float, float, float] = SCORE_THRESHOLDS,
    winrate_thresholds: Tuple[float, float, float] = WINRATE_THRESHOLDS,
) -> MistakeCategory:
    """
    損失量から MistakeCategory を決定する。

    優先順位:
      1) score_loss があればそれを使う
      2) なければ winrate_loss を使う
      3) 両方なければ GOOD
    """
    if score_loss is not None:
        loss = max(score_loss, 0.0)
        t1, t2, t3 = score_thresholds
        if loss < t1:
            return MistakeCategory.GOOD
        if loss < t2:
            return MistakeCategory.INACCURACY
        if loss < t3:
            return MistakeCategory.MISTAKE
        return MistakeCategory.BLUNDER

    if winrate_loss is not None:
        loss = max(winrate_loss, 0.0)
        t1, t2, t3 = winrate_thresholds
        if loss < t1:
            return MistakeCategory.GOOD
        if loss < t2:
            return MistakeCategory.INACCURACY
        if loss < t3:
            return MistakeCategory.MISTAKE
        return MistakeCategory.BLUNDER

    return MistakeCategory.GOOD


def classify_game_phase(move_number: int, board_size: int = 19) -> str:
    """
    手数と盤サイズから対局のフェーズを判定する（Phase 7で追加、PR3で盤サイズ対応）

    Args:
        move_number: 手数（0-indexed または 1-indexed どちらでも可）
        board_size: 盤サイズ（9, 13, 19 など）。デフォルト19。

    Returns:
        "opening" / "middle" / "yose"

    盤サイズ別の閾値:
        - 19路盤: opening < 50, middle < 200, yose >= 200
        - 13路盤: opening < 30, middle < 100, yose >= 100
        - 9路盤:  opening < 15, middle < 50,  yose >= 50

    Note:
        この分類は簡易版です。より正確には盤上の石の数や地合いで判定すべきですが、
        手数ベースで十分実用的です。
    """
    # 盤サイズ別の閾値（opening終了, middle終了）
    thresholds = {
        9: (15, 50),
        13: (30, 100),
        19: (50, 200),
    }
    # デフォルトは19路盤の閾値
    opening_end, middle_end = thresholds.get(board_size, (50, 200))

    if move_number < opening_end:
        return "opening"
    elif move_number < middle_end:
        return "middle"
    else:
        return "yose"


@dataclass
class MistakeStreak:
    """同一プレイヤーの連続ミス情報"""
    player: str  # "B" or "W"
    start_move: int  # 開始手数
    end_move: int  # 終了手数
    move_count: int  # ミスの回数（同一プレイヤーの手数）
    total_loss: float  # 合計損失
    moves: List[MoveEval] = field(default_factory=list)  # ミスした手のリスト

    @property
    def avg_loss(self) -> float:
        """平均損失"""
        return self.total_loss / self.move_count if self.move_count > 0 else 0.0


def detect_mistake_streaks(
    moves: List[MoveEval],
    *,
    loss_threshold: float = 2.0,
    min_consecutive: int = 2,
) -> List[MistakeStreak]:
    """
    同一プレイヤーの連続ミスを検出する（Go-aware streak detection）

    Args:
        moves: MoveEval のリスト（手数順にソート済み）
        loss_threshold: ミスとみなす最小損失（目）
        min_consecutive: 連続とみなす最小回数（同一プレイヤーの手数）

    Returns:
        MistakeStreak のリスト

    Note:
        囲碁では黒白交互に打つため、「連続ミス」は同一プレイヤーの
        連続する手（例: 黒10手目、黒12手目、黒14手目）を対象とする。
        単純な手数の連続（10, 11, 12）ではない。

    Example:
        >>> moves = [...]  # 手数順の MoveEval リスト
        >>> streaks = detect_mistake_streaks(moves, loss_threshold=3.0, min_consecutive=2)
        >>> for s in streaks:
        ...     print(f"{s.player}: moves {s.start_move}-{s.end_move}, {s.total_loss:.1f} pts lost")
    """
    if not moves:
        return []

    # プレイヤー別に手を分類
    player_moves: Dict[str, List[MoveEval]] = {"B": [], "W": []}
    for m in moves:
        if m.player in player_moves:
            player_moves[m.player].append(m)

    streaks = []

    for player, pmoves in player_moves.items():
        if not pmoves:
            continue

        # 手数順にソート
        sorted_moves = sorted(pmoves, key=lambda m: m.move_number)

        current_streak: List[MoveEval] = []

        for m in sorted_moves:
            loss = max(0.0, m.points_lost or 0.0)
            if loss >= loss_threshold:
                current_streak.append(m)
            else:
                # streak が途切れた
                if len(current_streak) >= min_consecutive:
                    total_loss = sum(max(0.0, mv.points_lost or 0.0) for mv in current_streak)
                    streaks.append(MistakeStreak(
                        player=player,
                        start_move=current_streak[0].move_number,
                        end_move=current_streak[-1].move_number,
                        move_count=len(current_streak),
                        total_loss=total_loss,
                        moves=list(current_streak),
                    ))
                current_streak = []

        # 最後の streak をチェック
        if len(current_streak) >= min_consecutive:
            total_loss = sum(max(0.0, mv.points_lost or 0.0) for mv in current_streak)
            streaks.append(MistakeStreak(
                player=player,
                start_move=current_streak[0].move_number,
                end_move=current_streak[-1].move_number,
                move_count=len(current_streak),
                total_loss=total_loss,
                moves=list(current_streak),
            ))

    # 開始手数順にソート
    streaks.sort(key=lambda s: s.start_move)
    return streaks

def compute_importance_for_moves(
    moves: Iterable[MoveEval],
    *,
    weight_delta_score: float = 1.0,
    weight_delta_winrate: float = 50.0,
    weight_points_lost: float = 1.0,
) -> None:
    """
    各 MoveEval について、delta_score / delta_winrate / points_lost から
    簡易な「重要度スコア」を計算し、importance_score に格納する。

    重みの意味（ざっくり）:
        - weight_delta_score : 形勢の点数変化（目）をどれだけ重く見るか
        - weight_delta_winrate : 勝率 1.0 の変化を「何目分」とみなすか
        - weight_points_lost : points_lost をどれだけ重く見るか

    ボーナス:
        - 形勢逆転（スコア符号変化）: +1.0
        - 勝率が50%をまたぐ: +1.0
        - is_reliable=False の場合: importance を 0.25 倍に減衰

    使用例:
        >>> moves = snapshot.moves
        >>> compute_importance_for_moves(moves)
        >>> important = [m for m in moves if m.importance_score and m.importance_score > 3.0]
        >>> print(f"Important moves: {len(important)}")

    注意:
        - この関数は moves を破壊的に変更します（各 m.importance_score を書き換え）
        - snapshot_from_nodes() で自動的に呼ばれるため、通常は手動で呼ぶ必要はありません
    """
    for m in moves:
        score_term = (
            weight_delta_score * abs(m.delta_score)
            if m.delta_score is not None
            else 0.0
        )
        winrate_term = (
            weight_delta_winrate * abs(m.delta_winrate)
            if m.delta_winrate is not None
            else 0.0
        )
        pl_term = (
            weight_points_lost * max(m.points_lost or 0.0, 0.0)
            if m.points_lost is not None
            else 0.0
        )

        # swing_bonus: 形勢逆転を検出して重要度にボーナスを加算
        # - score: 符号が反転（正→負 or 負→正）、または互角(0.0)を通過した場合
        # - winrate: 50%ラインを跨いだ場合
        # 注: score == 0.0 は「完全互角」を意味し、互角からの変化も重要な局面として扱う
        swing_bonus = 0.0
        if m.score_before is not None and m.score_after is not None:
            # 符号変化の判定:
            # - 正→負 または 負→正 への変化
            # - 互角(0.0)から有利/不利への変化
            # - 有利/不利から互角(0.0)への変化
            score_sign_changed = (
                (m.score_before > 0) != (m.score_after > 0)  # 符号反転
                or m.score_before == 0.0  # 互角からの変化
                or m.score_after == 0.0   # 互角への変化
            )
            if score_sign_changed:
                swing_bonus += SWING_SCORE_SIGN_BONUS
        if (
            m.winrate_before is not None
            and m.winrate_after is not None
            and (m.winrate_before < 0.5) != (m.winrate_after < 0.5)
        ):
            swing_bonus += SWING_WINRATE_CROSS_BONUS

        importance = score_term + winrate_term + pl_term + swing_bonus
        if not m.is_reliable:
            importance *= UNRELIABLE_IMPORTANCE_SCALE

        m.importance_score = importance


def pick_important_moves(
    snapshot: EvalSnapshot,
    level: str = DEFAULT_IMPORTANT_MOVE_LEVEL,
    settings: Optional[ImportantMoveSettings] = None,
    recompute: bool = True,
    weight_delta_score: float = 1.0,
    weight_delta_winrate: float = 50.0,
    weight_points_lost: float = 1.0,
) -> List[MoveEval]:
    """
    snapshot から重要局面の手数だけを抽出して返す。

    Args:
        snapshot: 解析済みの EvalSnapshot
        level:
            "easy" / "normal" / "strict" のような棋力イメージを表すキー。
            settings が None の場合に使用される（デフォルト "normal"）。
        settings:
            直接設定を渡したい場合用。通常は None のままでよい。
        recompute: importance_score を再計算するかどうか
        weight_delta_score: delta_score の重み
        weight_delta_winrate: delta_winrate の重み
        weight_points_lost: points_lost の重み

    Returns:
        MoveEval オブジェクトのリスト（手数順）。
    """
    # 設定の決定
    if settings is None:
        settings = IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
            level, IMPORTANT_MOVE_SETTINGS_BY_LEVEL[DEFAULT_IMPORTANT_MOVE_LEVEL]
        )

    threshold = settings.importance_threshold
    max_moves = settings.max_moves

    moves = snapshot.moves
    if not moves:
        # そもそも解析済みの手がない場合は何も返さない
        return []

    # 必要なら importance_score を再計算
    if recompute:
        compute_importance_for_moves(
            moves,
            weight_delta_score=weight_delta_score,
            weight_delta_winrate=weight_delta_winrate,
            weight_points_lost=weight_points_lost,
        )

    # 1) 通常ルート: importance_score ベース
    candidates: List[Tuple[float, MoveEval]] = []
    for move in moves:
        importance = move.importance_score or 0.0
        if importance > threshold:
            candidates.append((importance, move))

    # 2) フォールバック:
    #    1) で 1 手も選ばれなかったときだけ、
    #    「評価変化＋canonical loss」が大きい順で上位を取る。
    if not candidates:
        def raw_score(m: MoveEval) -> float:
            score_term = abs(m.delta_score or 0.0)
            winrate_term = 50.0 * abs(m.delta_winrate or 0.0)
            pl_term = get_canonical_loss_from_move(m)
            base = score_term + winrate_term + pl_term
            if not m.is_reliable:
                base *= UNRELIABLE_IMPORTANCE_SCALE
            return base

        for move in moves:
            raw_sc = raw_score(move)
            if raw_sc > 0.0:
                candidates.append((raw_sc, move))

    # importance の大きい順に並べ替えて上位だけ残す
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[:max_moves]

    # その後手数順にソート
    important_moves = sorted([m for _, m in top], key=lambda m: m.move_number)
    return important_moves


# ---------------------------------------------------------------------------
# Phase 13: 段級位自動推定（Skill Level Estimation）
# ---------------------------------------------------------------------------

@dataclass
class SkillEstimation:
    """棋力推定結果"""
    estimated_level: str  # "beginner" / "standard" / "advanced" / "unknown"
    confidence: float     # 0.0-1.0（推定の確度）
    reason: str          # 推定理由（日本語）
    metrics: Dict[str, float]  # 判定に使用したメトリクス


def estimate_skill_level_from_tags(
    reason_tags_counts: Dict[str, int],
    total_important_moves: int
) -> SkillEstimation:
    """
    理由タグ分布から棋力を推定（Phase 13）

    Args:
        reason_tags_counts: タグごとのカウント（例: {"heavy_loss": 20, "reading_failure": 17}）
        total_important_moves: 重要局面の総数

    Returns:
        SkillEstimation: 推定結果

    判定ロジック:
        - heavy_loss の出現率が高い → beginner
        - reading_failure の出現率が高い → standard
        - 両方とも低い → advanced
        - データ不足 → unknown
    """
    if total_important_moves < 5:
        return SkillEstimation(
            estimated_level="unknown",
            confidence=0.0,
            reason="重要局面数が不足（< 5手）",
            metrics={}
        )

    heavy_loss_count = reason_tags_counts.get("heavy_loss", 0)
    reading_failure_count = reason_tags_counts.get("reading_failure", 0)

    # 出現率を計算
    heavy_loss_rate = heavy_loss_count / total_important_moves
    reading_failure_rate = reading_failure_count / total_important_moves

    metrics = {
        "heavy_loss_rate": heavy_loss_rate,
        "reading_failure_rate": reading_failure_rate,
        "total_important_moves": float(total_important_moves)
    }

    # 判定ロジック
    # beginner: 大損失が多い（判断ミス）
    if heavy_loss_rate >= 0.4:  # 40%以上が大損失
        return SkillEstimation(
            estimated_level="beginner",
            confidence=min(0.9, heavy_loss_rate * 1.5),
            reason=f"大損失の出現率が高い（{heavy_loss_rate:.1%}）→ 大局観・判断力を強化する段階",
            metrics=metrics
        )

    # advanced: 大損失も読み抜けも少ない
    if heavy_loss_rate < 0.15 and reading_failure_rate < 0.1:
        confidence = 1.0 - (heavy_loss_rate + reading_failure_rate) * 2
        return SkillEstimation(
            estimated_level="advanced",
            confidence=min(0.9, max(0.5, confidence)),
            reason=f"大損失・読み抜けともに少ない（大損失{heavy_loss_rate:.1%}、読み抜け{reading_failure_rate:.1%}）→ 高段者レベル",
            metrics=metrics
        )

    # standard: 読み抜けが目立つ（戦術的な読みに課題）
    if reading_failure_rate >= 0.15:  # 15%以上が読み抜け
        return SkillEstimation(
            estimated_level="standard",
            confidence=min(0.9, reading_failure_rate * 2),
            reason=f"読み抜けの出現率が高い（{reading_failure_rate:.1%}）→ 戦術的な読み・形判断を強化する段階",
            metrics=metrics
        )

    # デフォルト: standard（中間レベル）
    confidence = 0.5  # やや不確実
    return SkillEstimation(
        estimated_level="standard",
        confidence=confidence,
        reason=f"大損失{heavy_loss_rate:.1%}、読み抜け{reading_failure_rate:.1%} → 標準的な有段者レベル",
        metrics=metrics
    )
