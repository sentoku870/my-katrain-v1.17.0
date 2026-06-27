"""katrain.core.analysis.models.skill - Skill preset, summary stats, and recommendation models.

Phase 144-B: Extracted from models.py (1230 lines → 6 focused modules).

Contains:
- GameSummaryData: Per-game summary
- SummaryStats: Multi-game aggregate statistics
- PhaseMistakeStats: Phase × Mistake cross-tabulation
- MistakeStreak, SkillEstimation: Streak and skill estimation
- ReasonTagThresholds, SkillPreset, SKILL_PRESETS, PRESET_ORDER: Skill presets
- AutoRecommendation, UrgentMissConfig + URGENT_MISS_CONFIGS: Recommendation
- SCORE_THRESHOLDS, WINRATE_THRESHOLDS: Default skill thresholds
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from katrain.core.analysis.models.enums import AutoConfidence, MistakeCategory, PositionDifficulty
from katrain.core.analysis.models.move_eval import EvalSnapshot, MoveEval
from katrain.core.analysis.models.quiz import QuizConfig


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
    game_id: str | None = None
    # Phase 6.5: Export Metadata
    result: str | None = None
    handicap: int = 0
    komi: float = 6.5
    skill_preset: str | None = None


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

    # Reason Tags Aggregation (Phase 128)
    # Mapping: tag_id -> count of occurrences across all games
    reason_tags_counts: dict[str, int] = field(default_factory=dict)
    # Count of important moves analyzed (the denominator for "per important move" stats)
    important_moves_count: int = 0
    # Count of moves that had at least one tag
    tagged_moves_count: int = 0
    # Total count of all tag occurrences (the denominator for "share of tags" stats)
    tag_occurrences_total: int = 0

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

    def get_freedom_percentage(self, difficulty: PositionDifficulty) -> float:
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
                default=None,
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
                priorities.append(f"**難しい局面での読みを改善**（{difficult_pct:.1f}%の手が狭い/一択）")

        # 3. 全体的なミス率が高い
        mistake_count = self.mistake_counts.get(MistakeCategory.MISTAKE, 0)
        blunder_count = self.mistake_counts.get(MistakeCategory.BLUNDER, 0)
        serious_mistakes = mistake_count + blunder_count
        if serious_mistakes > 0 and self.total_moves > 0:
            serious_pct = 100.0 * serious_mistakes / self.total_moves
            if serious_pct > 5.0 and len(priorities) < 3:  # 5%以上がミス/大悪手
                priorities.append(f"**全体的に悪手・大悪手を減らす**（{serious_mistakes}回、{serious_pct:.1f}%）")

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
# Mistake streak / Skill estimation
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
    confidence: float  # 0.0〜1.0
    reason: str  # 推定理由の説明
    metrics: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Skill Preset structures
# =============================================================================


@dataclass(frozen=True)
class ReasonTagThresholds:
    """Thresholds for reason tag detection (Phase 17)."""

    heavy_loss: float  # minimum loss for heavy_loss tag
    reading_failure: float  # minimum loss for reading_failure tag


@dataclass(frozen=True)
class SkillPreset:
    """Skill presets for quiz extraction and mistake thresholds."""

    score_thresholds: tuple[float, float, float]
    winrate_thresholds: tuple[float, float, float]
    reason_tag_thresholds: ReasonTagThresholds  # Phase 17
    quiz: QuizConfig  # Phase 98


# =============================================================================
# Skill Presets
# =============================================================================


SKILL_PRESETS: dict[str, SkillPreset] = {
    # Relaxed (Lv1): very forgiving, for absolute beginners or casual review.
    # t3=15.0, t2=0.5*t3=7.5, t1=0.2*t3=3.0
    "relaxed": SkillPreset(
        score_thresholds=(3.0, 7.5, 15.0),
        winrate_thresholds=(0.15, 0.30, 0.60),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=45.0, reading_failure=60.0),
        quiz=QuizConfig(loss_threshold=7.5, limit=5),
    ),
    # Beginner (Lv2): focus on large swings only (conservative thresholds).
    # t3=10.0, t2=0.5*t3=5.0, t1=0.2*t3=2.0
    # NOTE: Values updated from (2.0, 4.0, 8.0) to follow t1=0.2*t3, t2=0.5*t3 formula.
    "beginner": SkillPreset(
        score_thresholds=(2.0, 5.0, 10.0),
        winrate_thresholds=(0.10, 0.20, 0.40),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=30.0, reading_failure=40.0),
        quiz=QuizConfig(loss_threshold=5.0, limit=10),
    ),
    # Standard (Lv3): Phase 148-C3 - reason_tag thresholds tightened for more
    # sensitive detection of heavy_loss (5) and reading_failure (8).
    # t3=5.0, t2=2.5, t1=1.0 (unchanged)
    "standard": SkillPreset(
        score_thresholds=(1.0, 2.5, 5.0),
        winrate_thresholds=(0.05, 0.10, 0.20),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=5.0, reading_failure=8.0),
        quiz=QuizConfig(loss_threshold=2.5, limit=10),
    ),
    # Advanced (Lv4): more sensitive to small errors (unchanged).
    # t3=3.0, t2=1.5, t1=0.5 (preserved for backward compatibility)
    "advanced": SkillPreset(
        score_thresholds=(0.5, 1.5, 3.0),
        winrate_thresholds=(0.03, 0.07, 0.15),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=10.0, reading_failure=15.0),
        quiz=QuizConfig(loss_threshold=1.5, limit=15),
    ),
    # Pro (Lv5): strictest thresholds for dan-level analysis.
    # t3=1.0, t2=0.5*t3=0.5, t1=0.2*t3=0.2
    "pro": SkillPreset(
        score_thresholds=(0.2, 0.5, 1.0),
        winrate_thresholds=(0.01, 0.02, 0.04),
        reason_tag_thresholds=ReasonTagThresholds(heavy_loss=3.0, reading_failure=4.0),
        quiz=QuizConfig(loss_threshold=0.5, limit=20),
    ),
}

DEFAULT_SKILL_PRESET = "standard"

# Preset order from loosest to strictest (for tie-breaking toward standard)
# Index 2 = "standard" is the center for tie-breaking
PRESET_ORDER: list[str] = ["relaxed", "beginner", "standard", "advanced", "pro"]


# =============================================================================
# Auto-strictness structures
# =============================================================================


@dataclass
class AutoRecommendation:
    """Result of auto-strictness recommendation algorithm."""

    recommended_preset: str  # "relaxed", "beginner", "standard", "advanced", "pro"
    confidence: AutoConfidence
    blunder_count: int  # Blunder count using recommended preset's t3
    important_count: int  # Mistake+blunder count using recommended preset's t2
    score: int  # Distance score (lower is better)
    reason: str  # Human-readable explanation


# =============================================================================
# Urgent miss detection
# =============================================================================


@dataclass(frozen=True)
class UrgentMissConfig:
    """急場見逃しパターン検出の設定."""

    threshold_loss: float  # 損失閾値（この値を超える手を対象）
    min_consecutive: int  # 最小連続手数


# 棋力別の急場見逃し検出設定
URGENT_MISS_CONFIGS: dict[str, UrgentMissConfig] = {
    # Relaxed: only detect catastrophic oversight (50+ points)
    "relaxed": UrgentMissConfig(threshold_loss=50.0, min_consecutive=5),
    # 級位者: 大石の生き死にでも見逃しやすい。30目以上の超大損失のみ検出
    "beginner": UrgentMissConfig(threshold_loss=30.0, min_consecutive=4),
    # 標準: 20目超の損失で検出（有段者の急場見逃し）
    "standard": UrgentMissConfig(threshold_loss=20.0, min_consecutive=3),
    # 高段者: より小さな急場（コウ、ヨセの急場）も検出
    "advanced": UrgentMissConfig(threshold_loss=15.0, min_consecutive=3),
    # Pro: detect even small urgent oversights (10+ points)
    "pro": UrgentMissConfig(threshold_loss=10.0, min_consecutive=2),
}


# =============================================================================
# Phase thresholds (derived from default skill preset)
# =============================================================================


SCORE_THRESHOLDS: tuple[float, float, float] = SKILL_PRESETS[DEFAULT_SKILL_PRESET].score_thresholds
WINRATE_THRESHOLDS: tuple[float, float, float] = SKILL_PRESETS[DEFAULT_SKILL_PRESET].winrate_thresholds
