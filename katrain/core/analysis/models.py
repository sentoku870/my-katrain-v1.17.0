"""
katrain.core.analysis.models - データモデル定義

このモジュールには以下が含まれます:
- Enum クラス（MistakeCategory, PositionDifficulty, AutoConfidence, ConfidenceLevel, AnalysisStrength）
- Dataclass（MoveEval, EvalSnapshot, など）
- 設定定数（SKILL_PRESETS, PRESET_ORDER, ENGINE_VISITS_DEFAULTS, など）

Note: EvalSnapshot.worst_canonical_move などは logic.py の関数を使用するため、
      一部のメソッドはプロパティ内でインポートを遅延実行しています。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
)

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode
else:
    GameNode = Any


# =============================================================================
# Enums
# =============================================================================


class MistakeCategory(Enum):
    """ミスの大きさを4段階で分類するカテゴリ。"""

    GOOD = "good"              # 実質問題なし
    INACCURACY = "inaccuracy"  # 軽い損
    MISTAKE = "mistake"        # はっきり損
    BLUNDER = "blunder"        # 大きな損

    def is_error(self) -> bool:
        """GOOD 以外ならミス扱い、といった判定用の補助メソッド。"""
        return self is not MistakeCategory.GOOD


class PVFilterLevel(Enum):
    """候補手フィルタのレベル（Phase 11）。

    盤面に表示するTop Movesをフィルタリングするための設定レベル。
    難解なPV（長い読み筋）や大きな損失の手を除外して、
    ユーザーにとって理解しやすい候補手のみを表示する。
    """

    OFF = "off"          # フィルタなし（全候補手を表示）
    WEAK = "weak"        # 緩め（候補手多め、激甘〜甘口向け）
    MEDIUM = "medium"    # 標準
    STRONG = "strong"    # 厳しめ（候補手少なめ、辛口〜激辛向け）
    AUTO = "auto"        # Skill Presetに連動


class PositionDifficulty(Enum):
    """局面難易度を表すラベル。"""

    EASY = "easy"        # 良い手が多く、多少ズレても致命傷になりにくい
    NORMAL = "normal"    # 標準的な難易度
    HARD = "hard"        # 良い手が少なく、正解の幅が狭い
    ONLY_MOVE = "only"   # ほぼ「この一手」に近い局面
    UNKNOWN = "unknown"  # 候補手情報が無いなどで評価不能


class AutoConfidence(Enum):
    """Confidence level for auto-strictness recommendation."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceLevel(Enum):
    """Confidence level for analysis results.

    Used to control section visibility and wording in Karte/Summary output.
    """

    HIGH = auto()  # Full output, assertive wording
    MEDIUM = auto()  # Reduced output, hedged wording
    LOW = auto()  # Minimal output, reference-only, re-analysis recommended


# =============================================================================
# Analysis Strength (Phase 30)
# =============================================================================


class AnalysisStrength(Enum):
    """解析強度レベル（エンジン共通抽象）。

    - QUICK: 高速解析（fast_visits使用、概要把握向け）
    - DEEP: 詳細解析（max_visits使用、精密評価向け）

    Note:
        Phase 30で追加。Phase 31以降でエンジン統合に使用予定。
        This is NOT related to player skill presets (G0-G4).
    """

    QUICK = "quick"
    DEEP = "deep"

    @property
    def is_fast(self) -> bool:
        """高速解析モードかどうか"""
        return self == AnalysisStrength.QUICK


class EngineType(Enum):
    """解析エンジン種別。

    MoveEvalから推定するために使用。
    - KATAGO: KataGo解析（score_loss設定あり）
    - LEELA: Leela Zero解析（leela_loss_est設定あり）
    - UNKNOWN: エンジン不明（両方None）

    Note:
        Phase 32で追加。損失ラベルの区別表示に使用。
    """

    KATAGO = "katago"
    LEELA = "leela"
    UNKNOWN = "unknown"


# =============================================================================
# Analysis Engine Selection (Phase 33)
# =============================================================================

# Derive from EngineType to prevent drift (EngineType.UNKNOWN excluded)
VALID_ANALYSIS_ENGINES: frozenset[str] = frozenset({
    EngineType.KATAGO.value,
    EngineType.LEELA.value,
})
DEFAULT_ANALYSIS_ENGINE: str = EngineType.KATAGO.value


def get_analysis_engine(engine_config: dict[str, Any]) -> str:
    """設定から解析エンジンを取得する。

    Args:
        engine_config: engine セクションの設定dict

    Returns:
        str: "katago" or "leela"（無効値/未設定は "katago" にフォールバック）

    Behavior:
        - キーなし: DEFAULT_ANALYSIS_ENGINE を返す
        - 無効値（大文字、typo、None、非文字列等）: warning log + フォールバック
        - 大文字小文字は厳格（"LEELA" は無効）

    Note:
        Phase 33で追加。Phase 34でUI連携・エンジン起動ロジックに使用予定。
        leela/enabled との整合性チェックは Phase 34 の責務。
    """
    value = engine_config.get("analysis_engine", DEFAULT_ANALYSIS_ENGINE)
    # Type guard: unhashable types (list, dict) would crash `in frozenset`
    if not isinstance(value, str) or value not in VALID_ANALYSIS_ENGINES:
        _log.warning(
            "Invalid analysis_engine %r, falling back to %r",
            value,
            DEFAULT_ANALYSIS_ENGINE,
        )
        return DEFAULT_ANALYSIS_ENGINE
    return value


def needs_leela_warning(selected_engine: str, leela_enabled: bool) -> bool:
    """Leela選択時にLeela未有効の警告が必要かどうかを判定する。

    Args:
        selected_engine: 選択されたエンジン ("katago" or "leela")
        leela_enabled: Leelaが有効かどうか

    Returns:
        True if warning should be shown (Leela selected but not enabled)

    Note:
        Phase 34で追加。UIとテストで共有するための純粋関数。
    """
    return selected_engine == EngineType.LEELA.value and not leela_enabled


# Engine-specific default visits values.
# These are HARD SAFETY DEFAULTS used when config.json is missing keys.
# User-facing defaults should be set in config.json itself.
ENGINE_VISITS_DEFAULTS: dict[str, dict[str, int]] = {
    "katago": {"max_visits": 500, "fast_visits": 25},
    "leela": {"max_visits": 1000, "fast_visits": 200},
}

# UI minimum for leela fast_visits (practical lower bound for meaningful analysis)
LEELA_FAST_VISITS_MIN = 50


def resolve_visits(
    strength: AnalysisStrength,
    engine_config: dict[str, Any],
    engine_type: str = "katago",
) -> int:
    """解析強度からvisits数を解決する。

    Args:
        strength: 解析強度（QUICK/DEEP）
        engine_config: エンジン設定dict（max_visits, fast_visitsを含む可能性）
        engine_type: エンジン種別 ("katago" or "leela")

    Returns:
        int: visits数（1以上保証）

    Behavior:
        - engine_configにキーが存在しない場合はデフォルト値を使用
        - 不明なengine_typeの場合はkatagoのデフォルトにフォールバック（warning log出力）
        - 不正な値（文字列、None等）の場合もデフォルトにフォールバック（防御的）
        - 文字列の場合はstrip()後にint変換を試行

    Note:
        この関数はconfig.jsonからの値読み取り用。単一の強度に対する値解決のみ行う。
        fast_visits <= max_visits の整合性チェックは呼び出し側の責務。
        UIでのユーザー入力バリデーション（例: Leelaは50以上）も呼び出し側の責務。
    """
    if engine_type not in ENGINE_VISITS_DEFAULTS:
        _log.warning(
            "Unknown engine_type '%s', falling back to katago defaults", engine_type
        )
    defaults = ENGINE_VISITS_DEFAULTS.get(engine_type, ENGINE_VISITS_DEFAULTS["katago"])
    key = "fast_visits" if strength == AnalysisStrength.QUICK else "max_visits"

    raw_value = engine_config.get(key)
    if raw_value is None:
        return defaults[key]

    try:
        # 文字列の場合はstrip()してから変換
        if isinstance(raw_value, str):
            raw_value = raw_value.strip()
            if not raw_value:  # 空文字列
                return defaults[key]
        visits = int(raw_value)
        return max(1, visits)
    except (ValueError, TypeError):
        # 不正な値の場合はデフォルトにフォールバック
        return defaults[key]


# =============================================================================
# Dataclasses - Basic structures
# =============================================================================


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
    player: str | None               # 'B' / 'W' / None（ルートなど）
    gtp: str | None                  # "D4" のような座標 or "pass" / None

    # 評価値（BLACK-PERSPECTIVE: 正=黒有利）
    score_before: float | None       # この手を打つ前の評価
    score_after: float | None        # この手を打った直後の評価
    delta_score: float | None        # score_after - score_before (黒視点)

    winrate_before: float | None     # この手を打つ前の勝率
    winrate_after: float | None      # この手を打った直後の勝率
    delta_winrate: float | None      # winrate_after - winrate_before (黒視点)

    # KaTrain 標準の指標（SIDE-TO-MOVE: 手番視点）
    points_lost: float | None        # その手で失った期待値（手番視点、正=損失）
    realized_points_lost: float | None  # 実際の進行で確定した損失
    root_visits: int                    # その局面の root 訪問回数（見ている深さの目安）
    is_reliable: bool = False           # visits を根拠にした信頼度フラグ（保守的に False）

    # 将来の拡張用メタ情報
    tag: str | None = None           # "opening"/"middle"/"yose" など自由タグ
    importance_score: float | None = None  # 後で計算する「重要度スコア」

    score_loss: float | None = None
    """その手による地合損失（悪くなった分だけ、目単位）。"""

    winrate_loss: float | None = None
    """その手による勝率損失（悪くなった分だけ、0〜1）。"""

    mistake_category: MistakeCategory = MistakeCategory.GOOD
    """ミス分類（GOOD / INACCURACY / MISTAKE / BLUNDER）。"""

    position_difficulty: PositionDifficulty | None = None
    """局面難易度（EASY / NORMAL / HARD / ONLY_MOVE / UNKNOWN など）。"""

    position_difficulty_score: float | None = None
    """局面難易度を 0.0〜1.0 の連続値で表した補助スコア（大きいほど難しい想定）。"""

    reason_tags: list[str] = field(default_factory=list)
    """戦術的コンテキストの理由タグ（Phase 5: 構造の言語化）。

    例: ["atari", "low_liberties", "need_connect", "chase_mode", ...]
    盤面の戦術的状況に基づいて board_analysis モジュールで計算される。
    """

    leela_loss_est: float | None = None
    """Leela Zero による推定損失（0以上、Noneは非Leela解析）。

    Note:
    - score_loss（目単位）とは異なるセマンティクス
    - K係数でスケール変換済み（デフォルト K=0.5）
    - 0.0 = 最善手、正の値 = 損失
    - 最大値: LEELA_LOSS_EST_MAX（50.0）
    """

    meaning_tag_id: str | None = None
    """意味タグID（Phase 47: Meaning Tags Integration）。

    classify_meaning_tag() で分類された結果のID文字列。
    例: "overplay", "missed_tesuji", "life_death_error", "uncertain"

    Note:
    - str型（循環インポート回避のため MeaningTagId enum は使わない）
    - None = 未分類（classify未呼び出し or 分類不能）
    - MeaningTagId enum の .value と一致する
    """


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


# =============================================================================
# Canonical loss helper
# =============================================================================


def get_canonical_loss_from_move(m: MoveEval) -> float:
    """
    MoveEval から正準損失 (canonical loss) を取得する。

    優先順位:
      1) score_loss が設定されていればそれを使用（KataGo）
      2) leela_loss_est が設定されていればそれを使用（Leela）
      3) points_lost があれば使用
      4) どちらもなければ 0.0

    Returns:
        float: 常に >= 0 の損失値（負の値は 0 にクランプ）

    Note:
        - Phase 32 で leela_loss_est を追加
        - データ層で一貫してクランプすることで、
          将来の他UI/エクスポートでも安全に利用可能。
    """
    if m.score_loss is not None:
        return max(0.0, m.score_loss)
    if m.leela_loss_est is not None:
        return max(0.0, m.leela_loss_est)
    if m.points_lost is not None:
        return max(0.0, m.points_lost)
    return 0.0


# =============================================================================
# EvalSnapshot
# =============================================================================


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

    moves: list[MoveEval] = field(default_factory=list)

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
    def worst_move(self) -> MoveEval | None:
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
    def worst_canonical_move(self) -> MoveEval | None:
        """score_loss 最大の手を返す。"""
        candidates = [m for m in self.moves if get_canonical_loss_from_move(m) > 0.0]
        if not candidates:
            # 全て良い手の場合は最初の手を返す（または None）
            return self.moves[0] if self.moves else None
        return max(candidates, key=get_canonical_loss_from_move)

    # -------------------------------------------------------------------------
    # Freedom / Position Difficulty statistics
    # -------------------------------------------------------------------------

    @property
    def difficulty_unknown_count(self) -> int:
        """position_difficulty が UNKNOWN の手の数。"""
        return sum(
            1
            for m in self.moves
            if m.position_difficulty is None
            or m.position_difficulty == PositionDifficulty.UNKNOWN
        )

    @property
    def difficulty_unknown_rate(self) -> float:
        """position_difficulty が UNKNOWN の手の割合 (0.0-1.0)。"""
        if not self.moves:
            return 0.0
        return self.difficulty_unknown_count / len(self.moves)

    @property
    def difficulty_distribution(self) -> dict[PositionDifficulty, int]:
        """局面難易度の分布を返す。"""
        dist: dict[PositionDifficulty, int] = {d: 0 for d in PositionDifficulty}
        for m in self.moves:
            if m.position_difficulty is not None:
                dist[m.position_difficulty] += 1
            else:
                dist[PositionDifficulty.UNKNOWN] += 1
        return dist

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


# =============================================================================
# Multi-game summary structures (Phase 6)
# =============================================================================


@dataclass
class GameSummaryData:
    """1局分のデータ（複数局まとめ用）"""
    game_name: str
    player_black: str
    player_white: str
    snapshot: EvalSnapshot
    board_size: tuple[int, int]
    date: str | None = None


@dataclass
class SummaryStats:
    """複数局の集計統計"""
    player_name: str
    total_games: int = 0
    total_moves: int = 0
    total_points_lost: float = 0.0
    avg_points_lost_per_move: float = 0.0

    mistake_counts: dict[MistakeCategory, int] = field(default_factory=dict)
    mistake_total_loss: dict[MistakeCategory, float] = field(default_factory=dict)

    freedom_counts: dict[PositionDifficulty, int] = field(default_factory=dict)

    phase_moves: dict[str, int] = field(default_factory=dict)  # "opening"/"middle"/"yose"
    phase_loss: dict[str, float] = field(default_factory=dict)

    # Phase × MistakeCategory クロス集計 (Phase 6.5で追加)
    phase_mistake_counts: dict[tuple[str, MistakeCategory], int] = field(default_factory=dict)
    phase_mistake_loss: dict[tuple[str, MistakeCategory], float] = field(default_factory=dict)

    worst_moves: list[tuple[str, MoveEval]] = field(default_factory=list)  # (game_name, move)

    # PR#1: Store all moves for confidence level computation
    all_moves: list[MoveEval] = field(default_factory=list)

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

    def get_practice_priorities(self) -> list[str]:
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


# =============================================================================
# Phase × Mistake 集計（共有アグリゲータ）
# =============================================================================


@dataclass
class PhaseMistakeStats:
    """単局または複数局の Phase × Mistake 集計結果"""
    phase_mistake_counts: dict[tuple[str, str], int] = field(default_factory=dict)
    phase_mistake_loss: dict[tuple[str, str], float] = field(default_factory=dict)
    phase_moves: dict[str, int] = field(default_factory=dict)
    phase_loss: dict[str, float] = field(default_factory=dict)
    total_moves: int = 0
    total_loss: float = 0.0


# =============================================================================
# Quiz helper structures
# =============================================================================


@dataclass(frozen=True)
class QuizItem:
    """Large-mistake quiz entry derived from existing evaluations."""

    move_number: int
    player: str | None
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
    score_thresholds: tuple[float, float, float]
    winrate_thresholds: tuple[float, float, float]
    reason_tag_thresholds: ReasonTagThresholds  # Phase 17


# =============================================================================
# Skill Presets
# =============================================================================


SKILL_PRESETS: dict[str, SkillPreset] = {
    # Relaxed (Lv1): very forgiving, for absolute beginners or casual review.
    # t3=15.0, t2=0.5*t3=7.5, t1=0.2*t3=3.0
    "relaxed": SkillPreset(
        quiz=QuizConfig(loss_threshold=6.0, limit=10),
        score_thresholds=(3.0, 7.5, 15.0),
        winrate_thresholds=(0.15, 0.30, 0.60),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=45.0, reading_failure=60.0),
    ),
    # Beginner (Lv2): focus on large swings only (conservative thresholds).
    # t3=10.0, t2=0.5*t3=5.0, t1=0.2*t3=2.0
    # NOTE: Values updated from (2.0, 4.0, 8.0) to follow t1=0.2*t3, t2=0.5*t3 formula.
    "beginner": SkillPreset(
        quiz=QuizConfig(loss_threshold=4.0, limit=10),
        score_thresholds=(2.0, 5.0, 10.0),
        winrate_thresholds=(0.10, 0.20, 0.40),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=30.0, reading_failure=40.0),
    ),
    # Standard (Lv3): matches existing behavior (backward-compatible).
    # t3=5.0, t2=2.5, t1=1.0 (unchanged)
    "standard": SkillPreset(
        quiz=QuizConfig(loss_threshold=2.0, limit=10),
        score_thresholds=(1.0, 2.5, 5.0),
        winrate_thresholds=(0.05, 0.10, 0.20),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=15.0, reading_failure=20.0),
    ),
    # Advanced (Lv4): more sensitive to small errors (unchanged).
    # t3=3.0, t2=1.5, t1=0.5 (preserved for backward compatibility)
    "advanced": SkillPreset(
        quiz=QuizConfig(loss_threshold=1.0, limit=10),
        score_thresholds=(0.5, 1.5, 3.0),
        winrate_thresholds=(0.03, 0.07, 0.15),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=10.0, reading_failure=15.0),
    ),
    # Pro (Lv5): strictest thresholds for dan-level analysis.
    # t3=1.0, t2=0.5*t3=0.5, t1=0.2*t3=0.2
    "pro": SkillPreset(
        quiz=QuizConfig(loss_threshold=0.4, limit=10),
        score_thresholds=(0.2, 0.5, 1.0),
        winrate_thresholds=(0.01, 0.02, 0.04),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=3.0, reading_failure=4.0),
    ),
}

DEFAULT_SKILL_PRESET = "standard"

# Preset order from loosest to strictest (for tie-breaking toward standard)
# Index 2 = "standard" is the center for tie-breaking
PRESET_ORDER: list[str] = ["relaxed", "beginner", "standard", "advanced", "pro"]


# =============================================================================
# Labels (re-exported from presentation.py for backward compatibility)
# =============================================================================

# Note: Label constants are now defined in presentation.py
# They are re-exported here to maintain backward compatibility
# with code that imports them from models.py

# Lazy import to avoid circular dependency
def __getattr__(name: str) -> Any:
    """Lazy import for label constants from presentation module."""
    if name in ("SKILL_PRESET_LABELS", "CONFIDENCE_LABELS", "REASON_TAG_LABELS", "VALID_REASON_TAGS"):
        from katrain.core.analysis.presentation import (
            SKILL_PRESET_LABELS,
            CONFIDENCE_LABELS,
            REASON_TAG_LABELS,
            VALID_REASON_TAGS,
        )
        return {
            "SKILL_PRESET_LABELS": SKILL_PRESET_LABELS,
            "CONFIDENCE_LABELS": CONFIDENCE_LABELS,
            "REASON_TAG_LABELS": REASON_TAG_LABELS,
            "VALID_REASON_TAGS": VALID_REASON_TAGS,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# =============================================================================
# Auto-strictness structures
# =============================================================================


@dataclass
class AutoRecommendation:
    """Result of auto-strictness recommendation algorithm."""
    recommended_preset: str      # "relaxed", "beginner", "standard", "advanced", "pro"
    confidence: AutoConfidence
    blunder_count: int           # Blunder count using recommended preset's t3
    important_count: int         # Mistake+blunder count using recommended preset's t2
    score: int                   # Distance score (lower is better)
    reason: str                  # Human-readable explanation


# =============================================================================
# Urgent miss detection
# =============================================================================


@dataclass(frozen=True)
class UrgentMissConfig:
    """急場見逃しパターン検出の設定."""
    threshold_loss: float  # 損失閾値（この値を超える手を対象）
    min_consecutive: int   # 最小連続手数


# 棋力別の急場見逃し検出設定
URGENT_MISS_CONFIGS: dict[str, UrgentMissConfig] = {
    # Relaxed: only detect catastrophic oversight (50+ points)
    "relaxed": UrgentMissConfig(
        threshold_loss=50.0,
        min_consecutive=5
    ),
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
    # Pro: detect even small urgent oversights (10+ points)
    "pro": UrgentMissConfig(
        threshold_loss=10.0,
        min_consecutive=2
    ),
}


# =============================================================================
# Quiz structures
# =============================================================================


@dataclass
class QuizChoice:
    """Choice shown in quiz mode for a single position."""

    move: str
    points_lost: float | None


@dataclass
class QuizQuestion:
    """Quiz entry paired with candidate moves for the position before the mistake."""

    item: QuizItem
    choices: list[QuizChoice]
    best_move: str | None = None
    node_before_move: GameNode | None = None

    @property
    def has_analysis(self) -> bool:
        return self.node_before_move is not None and bool(self.choices)


# Backwards-compatible aliases
QUIZ_CONFIG_DEFAULT = SKILL_PRESETS[DEFAULT_SKILL_PRESET].quiz
DEFAULT_QUIZ_LOSS_THRESHOLD = QUIZ_CONFIG_DEFAULT.loss_threshold
DEFAULT_QUIZ_ITEM_LIMIT = QUIZ_CONFIG_DEFAULT.limit


# =============================================================================
# Reliability constants and structures
# =============================================================================


RELIABILITY_VISITS_THRESHOLD = 200
RELIABILITY_RATIO = 0.9  # 90% of target visits considered reliable (Phase 44)
UNRELIABLE_IMPORTANCE_SCALE = 0.25
SWING_SCORE_SIGN_BONUS = 1.0
SWING_WINRATE_CROSS_BONUS = 1.0

# Importance Scoring Constants (PR#4: Ranking Redesign)
DIFFICULTY_MODIFIER_HARD = 1.0
DIFFICULTY_MODIFIER_ONLY_MOVE = -1.0  # Phase 23: -2.0 → -1.0 (緩和)
DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_BONUS = 0.5  # Phase 23: 大損失時の追加緩和
DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_THRESHOLD = 2.0  # Phase 23: 大損失閾値（目数）
DIFFICULTY_MODIFIER_EASY = 0.0
DIFFICULTY_MODIFIER_NORMAL = 0.0

STREAK_START_BONUS = 2.0
SWING_MAGNITUDE_WEIGHT = 0.5

# Reliability scale thresholds
RELIABILITY_SCALE_THRESHOLDS = [
    (500, 1.0),   # visits >= 500: full weight
    (200, 0.8),   # visits >= 200: 80%
    (100, 0.5),   # visits >= 100: 50%
    (0, 0.3),     # visits < 100: 30%
]


@dataclass
class ReliabilityStats:
    """Data Quality / Reliability statistics for a set of moves."""
    total_moves: int = 0
    reliable_count: int = 0
    low_confidence_count: int = 0
    zero_visits_count: int = 0
    total_visits: int = 0
    moves_with_visits: int = 0
    max_visits: int = 0
    effective_threshold: int = RELIABILITY_VISITS_THRESHOLD  # Phase 44: for display

    @property
    def reliability_pct(self) -> float:
        """Percentage of analyzed moves that are reliable."""
        if self.moves_with_visits == 0:
            return 0.0
        return 100.0 * self.reliable_count / self.moves_with_visits

    @property
    def coverage_pct(self) -> float:
        """Percentage of total moves that have valid analysis."""
        if self.total_moves == 0:
            return 0.0
        return 100.0 * self.moves_with_visits / self.total_moves

    @property
    def low_confidence_pct(self) -> float:
        """Percentage of moves that are low confidence."""
        if self.total_moves == 0:
            return 0.0
        return 100.0 * self.low_confidence_count / self.total_moves

    @property
    def avg_visits(self) -> float:
        """Average visits for moves that have valid visits."""
        if self.moves_with_visits == 0:
            return 0.0
        return self.total_visits / self.moves_with_visits

    @property
    def is_low_reliability(self) -> bool:
        """True if reliability percentage is below 20%."""
        return self.reliability_pct < 20.0


# Constants for confidence level computation
MIN_COVERAGE_MOVES = 5

_CONFIDENCE_THRESHOLDS = {
    "high_reliability_pct": 50.0,
    "high_avg_visits": 400,
    "medium_reliability_pct": 30.0,
    "medium_avg_visits": 150,
}


# =============================================================================
# Skill Estimation
# =============================================================================


@dataclass
class MistakeStreak:
    """同一プレイヤーの連続ミス情報"""
    player: str  # "B" or "W"
    start_move: int  # 開始手数
    end_move: int  # 終了手数
    move_count: int  # ミスの回数（同一プレイヤーの手数）
    total_loss: float  # 合計損失
    moves: list[MoveEval] = field(default_factory=list)  # ミスした手のリスト

    @property
    def avg_loss(self) -> float:
        """平均損失"""
        return self.total_loss / self.move_count if self.move_count > 0 else 0.0


@dataclass
class SkillEstimation:
    """棋力推定結果（Phase 13）"""
    estimated_level: str  # "beginner", "standard", "advanced", etc.
    confidence: float     # 0.0〜1.0
    reason: str           # 推定理由の説明
    metrics: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Phase thresholds
# =============================================================================


SCORE_THRESHOLDS: tuple[float, float, float] = SKILL_PRESETS[DEFAULT_SKILL_PRESET].score_thresholds
WINRATE_THRESHOLDS: tuple[float, float, float] = SKILL_PRESETS[DEFAULT_SKILL_PRESET].winrate_thresholds


# =============================================================================
# PV Filter (Phase 11)
# =============================================================================


@dataclass(frozen=True)
class PVFilterConfig:
    """候補手フィルタの設定（Phase 11）。

    Attributes:
        max_candidates: フィルタ後の最大候補手数（best_moveは別枠で上限外）
        max_points_lost: この値以下の損失の手のみ表示（<=比較）
        max_pv_length: この値以下のPV長の手のみ表示（<=比較）
    """

    max_candidates: int
    max_points_lost: float
    max_pv_length: int


# PVFilterLevelごとのプリセット設定
PV_FILTER_CONFIGS: dict[str, PVFilterConfig] = {
    "weak": PVFilterConfig(
        max_candidates=15,
        max_points_lost=4.0,
        max_pv_length=15,
    ),
    "medium": PVFilterConfig(
        max_candidates=8,
        max_points_lost=2.0,
        max_pv_length=10,
    ),
    "strong": PVFilterConfig(
        max_candidates=4,
        max_points_lost=1.0,
        max_pv_length=6,
    ),
}

# skill_preset から pv_filter_level へのマッピング（AUTO用）
# skill_presetは「ミス判定の厳しさ」: 激甘=大きな損失のみ指摘、激辛=小さな損失も指摘
# PVフィルタは逆方向: 激甘→候補手多め(WEAK)、激辛→候補手少なめ(STRONG)
SKILL_TO_PV_FILTER: dict[str, str] = {
    "relaxed": "weak",     # 激甘 → 候補手多め
    "beginner": "weak",    # 甘口 → 候補手多め
    "standard": "medium",  # 標準 → 標準
    "advanced": "strong",  # 辛口 → 候補手少なめ
    "pro": "strong",       # 激辛 → 候補手少なめ
}

DEFAULT_PV_FILTER_LEVEL = "auto"


# =============================================================================
# Phase 12: 難易度分解（Difficulty Metrics）
# =============================================================================


@dataclass(frozen=True)
class DifficultyMetrics:
    """局面難易度の3分解メトリクス（Phase 12）。

    MuZero風の難易度分解を提供。v1は難所抽出用のセンサーとして使用。
    「採点」ではなく、同一棋譜内の相対比較に使用。

    Attributes:
        policy_difficulty: 迷いやすさ（候補が拮抗）。0-1、高いほど難。
        transition_difficulty: 崩れやすさ（一手のミスが致命傷）。0-1、高いほど難。
        state_difficulty: 盤面の複雑さ。v1は常に0（将来用）。
        overall_difficulty: 合成値（抽出・表示の優先度用）。0-1。
        is_reliable: 信頼性フラグ（visits/候補数が十分か）。
        is_unknown: UNKNOWN状態フラグ。欠損/計算不可を示す。
        debug_factors: 計算の内訳（デバッグ用、オプション）。

    Note:
        欠損時は DIFFICULTY_UNKNOWN（モジュールレベル定数）を使用。
        is_unknown フラグで判定（`is` 比較より堅牢）。
    """

    policy_difficulty: float
    transition_difficulty: float
    state_difficulty: float  # v1: always 0.0
    overall_difficulty: float
    is_reliable: bool
    is_unknown: bool = False
    debug_factors: dict[str, Any] | None = None


# モジュールレベル定数（frozen dataclass + ClassVar 問題を回避）
DIFFICULTY_UNKNOWN = DifficultyMetrics(
    policy_difficulty=0.0,
    transition_difficulty=0.0,
    state_difficulty=0.0,
    overall_difficulty=0.0,
    is_reliable=False,
    is_unknown=True,
    debug_factors={"reason": "unknown"},
)


# === Phase 12: 難易度計算の定数 ===

# 信頼性ガードの閾値
DIFFICULTY_MIN_VISITS: int = 500  # 最低探索数（root_visits が必要）
DIFFICULTY_MIN_CANDIDATES: int = 2  # 最低候補手数（計算可能な最小値）

# Policy難易度の正規化パラメータ
POLICY_GAP_MAX: float = 5.0  # この差（目数）以上は「迷いなし」(difficulty=0)

# Transition難易度の正規化パラメータ
TRANSITION_DROP_MAX: float = 8.0  # Top1→Top2の落差がこれ以上で最大難易度

# 難所抽出のデフォルト設定
DEFAULT_DIFFICULT_POSITIONS_LIMIT: int = 10
DEFAULT_MIN_MOVE_NUMBER: int = 10  # 序盤を除外


# =============================================================================
# __all__
# =============================================================================


__all__ = [
    # Enums
    "MistakeCategory",
    "PositionDifficulty",
    "AutoConfidence",
    "ConfidenceLevel",
    "PVFilterLevel",
    # Dataclasses
    "MoveEval",
    "EvalSnapshot",
    "GameSummaryData",
    "SummaryStats",
    "PhaseMistakeStats",
    "ImportantMoveSettings",
    "ReasonTagThresholds",
    "QuizItem",
    "QuizConfig",
    "QuizChoice",
    "QuizQuestion",
    "SkillPreset",
    "AutoRecommendation",
    "UrgentMissConfig",
    "ReliabilityStats",
    "MistakeStreak",
    "SkillEstimation",
    "PVFilterConfig",
    "DifficultyMetrics",
    # Preset dictionaries and lists
    "SKILL_PRESETS",
    "DEFAULT_SKILL_PRESET",
    "PRESET_ORDER",
    "URGENT_MISS_CONFIGS",
    "PV_FILTER_CONFIGS",
    "SKILL_TO_PV_FILTER",
    "DEFAULT_PV_FILTER_LEVEL",
    # Settings dictionaries
    "IMPORTANT_MOVE_SETTINGS_BY_LEVEL",
    "DEFAULT_IMPORTANT_MOVE_LEVEL",
    # Quiz constants
    "QUIZ_CONFIG_DEFAULT",
    "DEFAULT_QUIZ_LOSS_THRESHOLD",
    "DEFAULT_QUIZ_ITEM_LIMIT",
    # Reliability/importance constants
    "RELIABILITY_VISITS_THRESHOLD",
    "UNRELIABLE_IMPORTANCE_SCALE",
    "SWING_SCORE_SIGN_BONUS",
    "SWING_WINRATE_CROSS_BONUS",
    "SWING_MAGNITUDE_WEIGHT",
    "DIFFICULTY_MODIFIER_HARD",
    "DIFFICULTY_MODIFIER_ONLY_MOVE",
    "DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_BONUS",
    "DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_THRESHOLD",
    "DIFFICULTY_MODIFIER_EASY",
    "DIFFICULTY_MODIFIER_NORMAL",
    "STREAK_START_BONUS",
    "RELIABILITY_SCALE_THRESHOLDS",
    # Thresholds
    "SCORE_THRESHOLDS",
    "WINRATE_THRESHOLDS",
    "MIN_COVERAGE_MOVES",
    "_CONFIDENCE_THRESHOLDS",
    # Labels
    "REASON_TAG_LABELS",
    "VALID_REASON_TAGS",
    "SKILL_PRESET_LABELS",
    "CONFIDENCE_LABELS",
    # Helper function
    "get_canonical_loss_from_move",
    # Phase 12: Difficulty Metrics
    "DIFFICULTY_UNKNOWN",
    "DIFFICULTY_MIN_VISITS",
    "DIFFICULTY_MIN_CANDIDATES",
    "POLICY_GAP_MAX",
    "TRANSITION_DROP_MAX",
    "DEFAULT_DIFFICULT_POSITIONS_LIMIT",
    "DEFAULT_MIN_MOVE_NUMBER",
]
