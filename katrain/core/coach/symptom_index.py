"""Phase 209: Symptom index — §2-0 reverse-lookup table.

Maps the 30 symptom labels in `囲碁コーチング_統合マスター_完全版_v3.1.md`
§2-0 (症状別クイック逆引き) to automatic KataGo-metric detectors.

Source: master doc §2-0, replicated in `phase203-llm-translator.md` §4.1
(per user request "§2-0 症状別クイック逆引き表のみ").

Schema per symptom:
- id: stable machine name
- ja_label: Japanese label from §2-0
- en_label: English label (added for downstream tooling)
- description_jp: short Japanese description
- related_lexicon_ids: Linked Lexicon entry ids
- related_hint_category: Existing HintCategory enum value (or None)
- difficulty_range: Tuple of CoachMode indicating who this symptom
  applies to. (e.g. atari blindness is universal, sacrifice judgment
  is intermediate+ only)
- auto_detected: True if the detector is reliable from KataGo data alone.
  False means LLM-delegated (Phase 203 §4.2 user decision).
- detector: Optional callable that takes a SymptomContext and returns
  bool. Only populated for auto_detected=True.

`list_all_symptoms()` / `lookup_symptom()` provide the public lookup API.
`detect_auto_symptoms()` runs all auto-detectable symptoms against a
given SymptomContext.

No Kivy — pure core layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.beginner.models import HintCategory

from katrain.core.coach.master_db import CoachMode


# --- Symptom ID enum ---


class SymptomId(Enum):
    """30 symptoms defined in master doc §2-0 + Phase 203 §4.1.

    Order matches master doc §2-0 row order for stability.
    """

    # 1. 「石が取られる」「大石が死ぬ」
    ATARI_BLINDNESS = "atari_blindness"
    CAPTURE_OVERSIGHT = "capture_oversight"
    LADDER_NET_OVERSIGHT = "ladder_net_oversight"
    LIFE_DEATH_MISJUDGMENT = "life_death_misjudgment"
    # 2. 「切られる」「分断される」
    CONNECTION_NEGLECT = "connection_neglect"
    CUT_PANIC = "cut_panic"
    WEAK_GROUP_NEGLECT = "weak_group_neglect"
    # 3. 「どこに打てばいいか分からない」
    FIRST_MOVE_CONFUSION = "first_move_confusion"
    BIG_POINT_BLINDNESS = "big_point_blindness"
    TOO_MANY_CHOICES = "too_many_choices"
    # 4. 「大場が見えない」「小さい手を打ってしまう」
    SMALL_MOVE_ADDICTION = "small_move_addiction"
    OVERCONCENTRATION = "overconcentration"
    # 5. 「定石が分からない」「定石後に迷う」
    JOSEKI_ROTE = "joseki_rote"
    JOSEKI_OVERSTUDY = "joseki_overstudy"
    POST_JOSEKI_DIRECTION = "post_joseki_direction"
    # 6. 「攻めが空振りする」「無理攻めしてしまう」
    OVERPLAY_RECKLESS_ATTACK = "overplay_reckless_attack"
    OVERFIGHT = "overfight"
    ATTACK_WITH_PURPOSE = "attack_with_purpose"
    # 7. 「時間が足りない」「秒読みでミスる」
    TIME_PRESSURE_LOSS = "time_pressure_loss"  # LLM-required
    TIME_MISALLOCATION = "time_misallocation"  # LLM-required
    TIME_DRAIN = "time_drain"                  # LLM-required
    # 8. 「ヨセで逆転される」「終盤が苦手」
    ENDGAME_VALUATION_ERROR = "endgame_valuation_error"
    SENTE_GOTE_CONFUSION = "sente_gote_confusion"
    ENDGAME_PRECISION = "endgame_precision"
    # 9. 「同じミスを繰り返す」「上達しない」
    SAME_MISTAKE_LOOP = "same_mistake_loop"
    SHALLOW_REVIEW = "shallow_review"             # LLM-required
    STAGNATION_LOOP = "stagnation_loop"
    LOCAL_OPTIMUM = "local_optimum"               # LLM-required
    # 10. 「AIを見ても分からない」「AI依存」
    AI_OVERLOAD = "ai_overload"                   # LLM-required
    COPY_WITHOUT_UNDERSTANDING = "copy_without_understanding"  # LLM-required
    AUTHORITY_BIAS = "authority_bias"             # LLM-required
    # 11. 「焦る」「連敗する」「萎える」
    TILT_DISCOURAGEMENT = "tilt_discouragement"
    TILT_CHAIN = "tilt_chain"
    TILT_EMOTIONAL_INTERFERENCE = "tilt_emotional_interference"  # LLM-required
    # 12. 「形勢判断が合わない」「優勢から逆転される」
    EVALUATION_ERRORS = "evaluation_errors"
    POSITION_EVALUATION = "position_evaluation"
    RISK_MISCALIBRATION = "risk_miscalibration"
    # 13. 「捨て石ができない」「全部助けようとする」
    SAVING_EVERYTHING = "saving_everything"
    SACRIFICE_JUDGMENT = "sacrifice_judgment"     # LLM-required
    ENDOWMENT_EFFECT_SUNK_COST = "endowment_effect_sunk_cost"  # LLM-required


# --- Symptom context ---


@dataclass(frozen=True)
class SymptomContext:
    """Snapshot of metrics available for symptom detection.

    Captures both per-move and aggregate signals so detectors have a
    uniform input shape. Not every field is meaningful for every symptom;
    detectors can ignore irrelevant ones.

    Attributes:
        points_lost: Current move's pointsLost (None if unknown).
        winrate_lost: Current move's winrate drop (None if unknown).
        move_number: 1-indexed move number (None if unknown).
        good_move_count: Number of KataGo candidates with relativePointsLost <= 1.0.
        near_move_count: Number of candidates with relativePointsLost <= 2.0.
        overall_difficulty: DifficultyMetrics.overall_difficulty (None if unknown).
        score_stdev: rootInfo.scoreStdev (None if unknown).
        is_endgame: True when within ~30 moves of estimated endgame.
        meaning_tag_ids: Tuple of MeaningTagId values attached to this move.
        hint_categories: Tuple of HintCategory values attached to this move.
        avg_points_lost: Game-level average pointsLost (None if unknown).
        game_count: Total games played so far (None if unknown).
        weakness_concentration: Top weakness's share of total loss (None if unknown).
        board_size: Board size (19 / 13 / 9).
        current_phase: Phase 226-F (F-A) — the dominant phase this
            context belongs to (``"opening"`` / ``"middle"`` /
            ``"endgame"`` / ``"unknown"``). Populated from
            ``important_moves`` move_number median when available,
            so karte-derived contexts can fire phase-gated detectors
            (FIRST_MOVE_CONFUSION, TOO_MANY_CHOICES, OVERCONCENTRATION,
            POST_JOSEKI_DIRECTION, ATTACK_WITH_PURPOSE) which were
            previously dead because per-move ``move_number`` is unknown.
    """

    points_lost: float | None = None
    winrate_lost: float | None = None
    move_number: int | None = None
    good_move_count: int | None = None
    near_move_count: int | None = None
    overall_difficulty: float | None = None
    score_stdev: float | None = None
    is_endgame: bool = False
    meaning_tag_ids: tuple[MeaningTagId, ...] = ()
    hint_categories: tuple[HintCategory, ...] = ()
    avg_points_lost: float | None = None
    game_count: int | None = None
    weakness_concentration: float | None = None
    board_size: int = 19
    current_phase: str = "unknown"

    def is_phase(self, phase: str) -> bool:
        """Return True if the current move is in the given phase.

        Phases:
        - ``"opening"``: move_number <= 50 (19x19 approx)
        - ``"middle"``: 50 < move_number <= 200
        - ``"endgame"``: move_number > 200

        Phase 226-F (F-A): when ``move_number`` is unknown (the karte
        case), fall back to the ``current_phase`` field which the karte
        builder populates from the dominant ``important_moves`` move
        range. Without this fallback the phase-gated detectors never
        fired for karte contexts.
        """
        if self.move_number is not None:
            # Scale thresholds roughly for smaller boards
            scale = self.board_size / 19 if self.board_size else 1.0
            opening_max = max(15, int(50 * scale))
            middle_max = max(60, int(200 * scale))
            if phase == "opening":
                return self.move_number <= opening_max
            if phase == "middle":
                return opening_max < self.move_number <= middle_max
            if phase == "endgame":
                return self.move_number > middle_max
            return False
        # Fallback: trust current_phase (populated by the karte builder)
        return self.current_phase == phase


# --- Symptom dataclass ---


# A detector is a callable taking SymptomContext and returning bool.
Detector = Callable[[SymptomContext], bool]


@dataclass(frozen=True)
class Symptom:
    """Single entry in the §2-0 reverse-lookup table.

    Attributes:
        id: Stable identifier.
        ja_label: Japanese label from §2-0.
        en_label: English label (added for tooling).
        description_jp: Short Japanese description.
        related_lexicon_ids: Tuple of relevant Lexicon entry ids.
        related_hint_category: Existing HintCategory or None.
        difficulty_range: Tuple of (min, max) CoachMode this applies to.
        auto_detected: True if a reliable KataGo-metric detector exists.
        context_hint: Japanese note for the LLM explaining how to discuss
            this symptom (Phase 203 §4.2 contract — used in the
            "LLM-delegated" prompt block).
        detector: Optional detector function. Only present when
            ``auto_detected`` is True.
    """

    id: SymptomId
    ja_label: str
    en_label: str
    description_jp: str
    related_lexicon_ids: tuple[str, ...]
    related_hint_category: HintCategory | None
    difficulty_range: tuple[CoachMode, CoachMode]
    auto_detected: bool
    context_hint: str = ""
    detector: Detector | None = field(default=None, compare=False)


# --- Detector helpers ---


def _has_tag(ctx: SymptomContext, tag_id: str) -> bool:
    return any(t.value == tag_id for t in ctx.meaning_tag_ids)


def _has_hint(ctx: SymptomContext, hint: HintCategory) -> bool:
    return hint in ctx.hint_categories


def _points_lost_exceeds(ctx: SymptomContext, threshold: float) -> bool:
    return ctx.points_lost is not None and ctx.points_lost > threshold


def _winrate_drop_exceeds(ctx: SymptomContext, pct: float) -> bool:
    return ctx.winrate_lost is not None and ctx.winrate_lost * 100.0 > pct


# --- §2-0 master table ---


_SYMPTOMS: tuple[Symptom, ...] = (
    # 1. 石が取られる・大石が死ぬ
    Symptom(
        id=SymptomId.ATARI_BLINDNESS,
        ja_label="アタリの見落とし",
        en_label="Atari Blindness",
        description_jp="アタリ（呼吸点1）の手を見落とし、自分の石を取られる。",
        related_lexicon_ids=("liberty", "atari"),
        related_hint_category=HintCategory.SELF_ATARI,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.INTERMEDIATE),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "capture_race_loss")
        and _points_lost_exceeds(c, 1.0),
    ),
    Symptom(
        id=SymptomId.CAPTURE_OVERSIGHT,
        ja_label="取り残し",
        en_label="Capture Oversight",
        description_jp="相手の石を取れる局面で別の手を打ち、形勢を崩す。",
        related_lexicon_ids=("capture", "atari"),
        related_hint_category=HintCategory.MISSED_CAPTURE,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.INTERMEDIATE),
        auto_detected=True,
        detector=lambda c: _has_hint(c, HintCategory.MISSED_CAPTURE)
        and _points_lost_exceeds(c, 1.0),
    ),
    Symptom(
        id=SymptomId.LADDER_NET_OVERSIGHT,
        ja_label="シチョウ/ゲタの読み違い",
        en_label="Ladder/Net Oversight",
        description_jp="シチョウやゲタの基本手筋を見落とし、大石を死なせる。",
        related_lexicon_ids=("ladder_breaker",),
        related_hint_category=None,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.INTERMEDIATE),
        auto_detected=False,  # Requires board-shape detection (future Phase).
        context_hint="KataGo 数値からは直接判定不能。シチョウ形状の検出には盤面解析が必要。",
    ),
    Symptom(
        id=SymptomId.LIFE_DEATH_MISJUDGMENT,
        ja_label="死活の誤認",
        en_label="Life/Death Misjudgment",
        description_jp="自分の石が死んでいるか生きているか読み違える。",
        related_lexicon_ids=("life_and_death", "eye", "two_eyes"),
        related_hint_category=HintCategory.SELF_CAPTURE_LIKE,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.INTERMEDIATE),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "life_death_error"),
    ),
    # 2. 切られる・分断される
    Symptom(
        id=SymptomId.CONNECTION_NEGLECT,
        ja_label="連携の軽視",
        en_label="Connection Neglect",
        description_jp="分断される危険を見落とし、弱いグループを切り離される。",
        related_lexicon_ids=("connection",),
        related_hint_category=HintCategory.MISSED_DEFENSE,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.INTERMEDIATE),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "connection_miss"),
    ),
    Symptom(
        id=SymptomId.CUT_PANIC,
        ja_label="切られる恐怖での硬直",
        en_label="Cut Panic",
        description_jp="切られる恐怖で過剰に守り、形勢を崩す。",
        related_lexicon_ids=("cutting_point",),
        related_hint_category=HintCategory.CUT_RISK,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.DAN),
        auto_detected=True,
        detector=lambda c: _has_hint(c, HintCategory.CUT_RISK)
        and ctx_points_lost_high(c),
    ),
    Symptom(
        id=SymptomId.WEAK_GROUP_NEGLECT,
        ja_label="弱い石の見落とし",
        en_label="Weak Group Neglect",
        description_jp="呼吸点の少ない弱い石を見殺しにして大損する。",
        related_lexicon_ids=("liberty", "damezumari_lv1"),
        related_hint_category=HintCategory.IGNORE_ATARI,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.INTERMEDIATE),
        auto_detected=True,
        detector=lambda c: _has_hint(c, HintCategory.IGNORE_ATARI)
        or _has_tag(c, "capture_race_loss"),
    ),
    # 3. どこに打てばいいか分からない
    Symptom(
        id=SymptomId.FIRST_MOVE_CONFUSION,
        ja_label="最初の一手が分からない",
        en_label="First Move Confusion",
        description_jp="着手すべき場所が分からず、対局開始で詰まる。",
        related_lexicon_ids=("komoku", "star_point"),
        related_hint_category=None,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.BEGINNER),
        auto_detected=True,
        detector=lambda c: ctx_is_phase(c, "opening")
        and _points_lost_exceeds(c, 5.0),
    ),
    Symptom(
        id=SymptomId.BIG_POINT_BLINDNESS,
        ja_label="大場の見落とし",
        en_label="Big Point Blindness",
        description_jp="盤面全体の最大地点を見落とし、小さな手に流れる。",
        related_lexicon_ids=("urgent_vs_big",),
        related_hint_category=HintCategory.URGENT_VS_BIG,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.DAN),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "slow_move")
        and _points_lost_exceeds(c, 2.0),
    ),
    Symptom(
        id=SymptomId.TOO_MANY_CHOICES,
        ja_label="候補が多すぎる",
        en_label="Too Many Choices",
        description_jp="良い候補手が多すぎて選べず、無難手で時間を浪費。",
        related_lexicon_ids=(),
        related_hint_category=HintCategory.FREEDOM_WIDE,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.INTERMEDIATE),
        auto_detected=True,
        detector=lambda c: _has_hint(c, HintCategory.FREEDOM_WIDE)
        and ctx_is_phase(c, "opening"),
    ),
    # 4. 大場が見えない
    Symptom(
        id=SymptomId.SMALL_MOVE_ADDICTION,
        ja_label="小さい手依存",
        en_label="Small Move Addiction",
        description_jp="中盤で局所的な小利に拘り、大場を見失う。",
        related_lexicon_ids=("urgent_vs_big",),
        related_hint_category=HintCategory.MISTAKE_MISTAKE,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.DAN),
        auto_detected=False,  # 連続 mid-game failure pattern — needs sequence detector.
        context_hint="単独の手では判定不能。連続する中盤の ミスを §5 で時系列パターンとして提示。",
    ),
    Symptom(
        id=SymptomId.OVERCONCENTRATION,
        ja_label="過密（厚みで身動き取れず）",
        en_label="Overconcentration",
        description_jp="石を近くに集中させて効率を下げ、形を崩す。",
        related_lexicon_ids=("overconcentration", "heavy_shape"),
        related_hint_category=HintCategory.HEAVY_GROUP,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.ADVANCED),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "overplay")
        and ctx_in_middle_phase(c),
    ),
    # 5. 定石が分からない
    Symptom(
        id=SymptomId.JOSEKI_ROTE,
        ja_label="定石の暗記偏重",
        en_label="Joseki Rote",
        description_jp="定石を外れた時に対応できず、定石座標に固執する。",
        related_lexicon_ids=("komoku",),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.INTERMEDIATE),
        auto_detected=False,  # Requires SGF-move comparison against known joseki DB.
        context_hint="KataGo 数値からは判定不能。SGF を定石データベースと照合するには Phase 209.5 の追加実装が必要。",
    ),
    Symptom(
        id=SymptomId.JOSEKI_OVERSTUDY,
        ja_label="定石の勉強過多",
        en_label="Joseki Overstudy",
        description_jp="定石ばかり勉強し、力戦や中盤の読みが弱い。",
        related_lexicon_ids=("joseki",),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.INTERMEDIATE),
        auto_detected=False,  # User-behaviour symptom.
        context_hint="KataGo 数値からは判定不能。ユーザーの対局履歴（特定局面の着手座標）から推定可能。",
    ),
    Symptom(
        id=SymptomId.POST_JOSEKI_DIRECTION,
        ja_label="定石後の次の一手",
        en_label="Post-Joseki Direction",
        description_jp="定石から次の方向（厚み・地）を見誤る。",
        related_lexicon_ids=("direction_of_play",),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.DAN),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "direction_error")
        and ctx_is_phase(c, "opening"),
    ),
    # 6. 攻めが空振り
    Symptom(
        id=SymptomId.OVERPLAY_RECKLESS_ATTACK,
        ja_label="打ち過ぎ・無理攻め",
        en_label="Overplay/Reckless Attack",
        description_jp="相手の厚みや強度に反し、無謀な攻めに出て大損する。",
        related_lexicon_ids=("overplay", "thickness"),
        related_hint_category=HintCategory.HEAVY_GROUP,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "overplay")
        and (c.score_stdev is not None and c.score_stdev > 1.5),
    ),
    Symptom(
        id=SymptomId.OVERFIGHT,
        ja_label="過剰な戦闘",
        en_label="Overfight",
        description_jp="続けて攻め合いに踏み込み、手番を失って形勢が傾く。",
        related_lexicon_ids=("overplay",),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=False,  # Pattern requires streak detection across multiple moves.
        context_hint="連続 MISTAKE_BLUNDER (3 連以上) のパターンを §5 で提示。",
    ),
    Symptom(
        id=SymptomId.ATTACK_WITH_PURPOSE,
        ja_label="目的のない攻め",
        en_label="Attack without Purpose",
        description_jp="利益（地・外勢・先手）のない攻めを打ち、形勢を損なう。",
        related_lexicon_ids=("direction_of_play", "attack_for_profit"),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.DAN),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "direction_error")
        and ctx_in_attack_phase(c),
    ),
    # 7. 時間が足りない（すべて LLM-required）
    Symptom(
        id=SymptomId.TIME_PRESSURE_LOSS,
        ja_label="時間圧による損失",
        en_label="Time Pressure Loss",
        description_jp="秒読みで精度が落ち、ミスが増える。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。SGF の時間データ（GT プロパティ 'TM' / 'BL'）が必要。",
    ),
    Symptom(
        id=SymptomId.TIME_MISALLOCATION,
        ja_label="時間配分の偏り",
        en_label="Time Misallocation",
        description_jp="大局に時間をかけ過ぎ、終盤で慌てる。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。SGF の時間データまたはユーザー自己申告が必要。",
    ),
    Symptom(
        id=SymptomId.TIME_DRAIN,
        ja_label="局面ごとの時間消費",
        en_label="Time Drain",
        description_jp="特定局面で異常に時間を浪費する。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。SGF の時間データから特定可能。",
    ),
    # 8. ヨセで逆転される
    Symptom(
        id=SymptomId.ENDGAME_VALUATION_ERROR,
        ja_label="ヨセの値打ち読み違い",
        en_label="Endgame Valuation Error",
        description_jp="ヨセの大小を読み違え、無駄な個所に着手する。",
        related_lexicon_ids=("endgame_sente",),
        related_hint_category=HintCategory.URGENT_VS_BIG,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: c.is_endgame and _has_tag(c, "endgame_slip"),
    ),
    Symptom(
        id=SymptomId.SENTE_GOTE_CONFUSION,
        ja_label="先手/後手の混同",
        en_label="Sente/Gote Confusion",
        description_jp="先手で打つべき所を後手で打ち、利益を失う。",
        related_lexicon_ids=("endgame_sente",),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: c.is_endgame and _has_tag(c, "territorial_loss"),
    ),
    Symptom(
        id=SymptomId.ENDGAME_PRECISION,
        ja_label="ヨセ精度不足",
        en_label="Endgame Precision",
        description_jp="ヨセ段階で致命的なミスを連発する。",
        related_lexicon_ids=(),
        related_hint_category=HintCategory.MISTAKE_BLUNDER,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: c.is_endgame and _has_hint(c, HintCategory.MISTAKE_BLUNDER),
    ),
    # 9. 同じミス繰り返し
    Symptom(
        id=SymptomId.SAME_MISTAKE_LOOP,
        ja_label="同パターン反復",
        en_label="Same Mistake Loop",
        description_jp="同じ局面で同じミスを繰り返す。",
        related_lexicon_ids=(),
        related_hint_category=HintCategory.CURATOR_WEAK_AXIS,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: _has_hint(c, HintCategory.CURATOR_WEAK_AXIS)
        and (c.game_count is not None and c.game_count >= 3),
    ),
    Symptom(
        id=SymptomId.SHALLOW_REVIEW,
        ja_label="検討の浅さ",
        en_label="Shallow Review",
        description_jp="対局後の検討が浅く、学びが定着しない。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。ユーザー行動（検討の深さ・頻度）が必要。",
    ),
    Symptom(
        id=SymptomId.STAGNATION_LOOP,
        ja_label="停滞ループ",
        en_label="Stagnation Loop",
        description_jp="弱点上位が改善せず、何局も同じパターンが続く。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: (
            c.weakness_concentration is not None
            and c.weakness_concentration > 0.6
            and c.game_count is not None
            and c.game_count >= 5
        ),
    ),
    Symptom(
        id=SymptomId.LOCAL_OPTIMUM,
        ja_label="局所最適",
        en_label="Local Optimum",
        description_jp="慎重に打つが、局面が動かずチャンスを逃す。",
        related_lexicon_ids=(),
        related_hint_category=HintCategory.FREEDOM_NARROW,
        difficulty_range=(CoachMode.DAN, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは完全判定不能。FREEDOM_NARROW + 勝率停滞の複合パターンが必要。",
    ),
    # 10. AI を見ても分からない（すべて LLM-required）
    Symptom(
        id=SymptomId.AI_OVERLOAD,
        ja_label="AI 情報過多",
        en_label="AI Overload",
        description_jp="KataGo の出力を見すぎて判断材料を処理できない。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。ユーザー行動（検討時間・参照回数）が必要。",
    ),
    Symptom(
        id=SymptomId.COPY_WITHOUT_UNDERSTANDING,
        ja_label="理解なしコピー",
        en_label="Copy without Understanding",
        description_jp="KataGoの候補手を理由なくコピーし、学びがない。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。ユーザーの思考ログまたは自己申告が必要。",
    ),
    Symptom(
        id=SymptomId.AUTHORITY_BIAS,
        ja_label="権威バイアス",
        en_label="Authority Bias",
        description_jp="KataGo が最強だから反論できない、と過信する。",
        related_lexicon_ids=("winrate", "score_lead"),
        related_hint_category=None,
        difficulty_range=(CoachMode.DAN, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。ユーザー発言またはプロンプト文脈から推定。",
    ),
    # 11. 焦る・連敗
    Symptom(
        id=SymptomId.TILT_DISCOURAGEMENT,
        ja_label="ティルト・意気消沈",
        en_label="Tilt/Discouragement",
        description_jp="連敗で意欲が減退し、判断が雑になる。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.EXPERT),
        auto_detected=False,  # Requires streak detection (implemented later).
        context_hint="連敗（loss 3 連以上）+ MISTAKE_BLUNDER 頻度増 のパターンが必要。",
    ),
    Symptom(
        id=SymptomId.TILT_CHAIN,
        ja_label="ティルト連鎖",
        en_label="Tilt Chain",
        description_jp="一つのミスが次のミスを呼び、連鎖する。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="連敗中の pointsLost 増大パターンを §5 で提示。",
    ),
    Symptom(
        id=SymptomId.TILT_EMOTIONAL_INTERFERENCE,
        ja_label="感情による判断干渉",
        en_label="Tilt/Emotional Interference",
        description_jp="感情が判断を歪め、最適手を打てなくなる。",
        related_lexicon_ids=(),
        related_hint_category=None,
        difficulty_range=(CoachMode.BEGINNER, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。ユーザー自己申告または感情分析が必要。",
    ),
    # 12. 形勢判断が合わない
    Symptom(
        id=SymptomId.EVALUATION_ERRORS,
        ja_label="形勢判断の誤り",
        en_label="Evaluation Errors",
        description_jp="勝率・点差を誤読し、無駄な攻めや守りを打つ。",
        related_lexicon_ids=("winrate", "score_lead"),
        related_hint_category=None,
        difficulty_range=(CoachMode.DAN, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: _winrate_drop_exceeds(c, 15.0)
        and ctx_in_middle_or_end(c),
    ),
    Symptom(
        id=SymptomId.POSITION_EVALUATION,
        ja_label="局面評価の歪み",
        en_label="Position Evaluation",
        description_jp="scoreLead と winrate のズレを大きく見積もり損なう。",
        related_lexicon_ids=("score_lead", "winrate"),
        related_hint_category=None,
        difficulty_range=(CoachMode.DAN, CoachMode.EXPERT),
        auto_detected=False,  # Computed at aggregate level, needs game-summary.
        context_hint="複数局面の winrate/scoreLead 相関分析が必要（Phase 209.5 で実装検討）。",
    ),
    Symptom(
        id=SymptomId.RISK_MISCALIBRATION,
        ja_label="リスク調整ミス",
        en_label="Risk Miscalibration",
        description_jp="ビハインド時の強攻め・優勢時の安全策判断を誤る。",
        related_lexicon_ids=("playing_ahead_vs_behind",),
        related_hint_category=None,
        difficulty_range=(CoachMode.ADVANCED, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: (
            c.score_stdev is not None and c.score_stdev > 2.0
            and (c.winrate_lost is not None and c.winrate_lost > 0.1)
        ),
    ),
    # 13. 捨て石できない
    Symptom(
        id=SymptomId.SAVING_EVERYTHING,
        ja_label="全石救助志向",
        en_label="Saving Everything",
        description_jp="見込みの薄い石も無理に助けて、形勢を損なう。",
        related_lexicon_ids=("sacrifice_strategy",),
        related_hint_category=HintCategory.MISSED_DEFENSE,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=True,
        detector=lambda c: _has_tag(c, "connection_miss")
        and ctx_multiple_weak_groups(c),
    ),
    Symptom(
        id=SymptomId.SACRIFICE_JUDGMENT,
        ja_label="捨て石判断の誤り",
        en_label="Sacrifice Judgment",
        description_jp="捨て時が遅く、助けるコストが利得を上回る。",
        related_lexicon_ids=("sacrifice_strategy", "heavy_vs_light"),
        related_hint_category=None,
        difficulty_range=(CoachMode.INTERMEDIATE, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。ユーザー意図（'なぜ捨てなかったか'）が必要。",
    ),
    Symptom(
        id=SymptomId.ENDOWMENT_EFFECT_SUNK_COST,
        ja_label="サンクコスト錯視",
        en_label="Endowment Effect/Sunk Cost",
        description_jp="投資した石への拘りで、合理的な判断ができない。",
        related_lexicon_ids=("sacrifice_strategy",),
        related_hint_category=None,
        difficulty_range=(CoachMode.DAN, CoachMode.EXPERT),
        auto_detected=False,
        context_hint="KataGo 数値からは判定不能。ユーザー行動データまたは発言が必要。",
    ),
)


# --- Lookup indices ---


_SYMPTOM_BY_ID: dict[SymptomId, Symptom] = {s.id: s for s in _SYMPTOMS}

_AUTO_SYMPTOMS: tuple[Symptom, ...] = tuple(s for s in _SYMPTOMS if s.auto_detected)
_LLM_REQUIRED: tuple[Symptom, ...] = tuple(s for s in _SYMPTOMS if not s.auto_detected)


# --- Detector helper close-outs ---
# These were declared as lambdas in the table above for readability; we
# need them defined as named callables so Symptom is hashable/frozen.

def ctx_is_phase(c: SymptomContext, phase: str) -> bool:
    return c.is_phase(phase)


def ctx_points_lost_high(c: SymptomContext) -> bool:
    return c.points_lost is not None and c.points_lost > 3.0


def ctx_in_middle_phase(c: SymptomContext) -> bool:
    return c.is_phase("middle")


def ctx_in_attack_phase(c: SymptomContext) -> bool:
    return c.is_phase("middle") or c.is_phase("endgame")


def ctx_in_middle_or_end(c: SymptomContext) -> bool:
    return c.is_phase("middle") or c.is_phase("endgame") or c.is_endgame


def ctx_multiple_weak_groups(c: SymptomContext) -> bool:
    # Without board-shape data we approximate via low_liberties frequency.
    tags = [t.value for t in c.meaning_tag_ids]
    return tags.count("low_liberties") + tags.count("connection_miss") >= 2


# Public API ---


def list_all_symptoms() -> tuple[Symptom, ...]:
    """Return all 30 symptoms in master doc §2-0 row order."""
    return _SYMPTOMS


def lookup_symptom(symptom_id: SymptomId) -> Symptom | None:
    """Look up a single symptom by id."""
    return _SYMPTOM_BY_ID.get(symptom_id)


def list_auto_detected_symptoms() -> tuple[Symptom, ...]:
    """Return the subset of symptoms with reliable KataGo-metric detectors."""
    return _AUTO_SYMPTOMS


def list_llm_required_symptoms() -> tuple[Symptom, ...]:
    """Return symptoms marked for LLM delegation (Phase 203 §4.2)."""
    return _LLM_REQUIRED


def detect_auto_symptoms(ctx: SymptomContext) -> list[SymptomId]:
    """Run every auto-detectable symptom detector against ``ctx``.

    Symptoms whose detector is missing (e.g. implemented in a future
    Phase 209.x) are silently skipped, NOT raised. Returns the IDs of
    symptoms that fired.

    Args:
        ctx: SymptomContext with whatever KataGo signals are available.

    Returns:
        List of fired SymptomId. May be empty.
    """
    fired: list[SymptomId] = []
    for symptom in _AUTO_SYMPTOMS:
        detector = symptom.detector
        if detector is None:
            continue
        try:
            if detector(ctx):
                fired.append(symptom.id)
        except Exception:
            # Phase 203 risk-mitigation: never let LLM prompt-generation
            # crash on partial KataGo data.
            continue
    return fired


__all__ = [
    "SymptomId",
    "SymptomContext",
    "Symptom",
    "list_all_symptoms",
    "lookup_symptom",
    "list_auto_detected_symptoms",
    "list_llm_required_symptoms",
    "detect_auto_symptoms",
]
