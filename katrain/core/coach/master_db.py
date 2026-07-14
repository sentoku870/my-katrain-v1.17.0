"""Phase 207: Master coaching database (mode/tone definitions).

This module is the foundation of the LLM "translation" pipeline
(Phase 203 調査ドキュメント, Phase 207-213 implementation).

Extracted from `囲碁コーチング_統合マスター_完全版_v3.1.md`:
- Section 0: モード選択ルーター (mode classification + judgement priority)
- Section 1: コミュニケーション・トーン (ayaka / tomoko / tomoko_strict)

Design:
- Pure data, no Kivy / no external dependencies (core layer isolation).
- All string identifiers are stable; downstream modules import the constants.
- Lookup helpers are thin wrappers that return dataclasses for type safety.

Excluded from this module (planned for future subpackages):
- Section 2 (Diagnostic DB with 30+ symptom entries) → Phase 209 symptom_index.py
- Section 3 (Phase 1/2 interaction templates) → Phase 211 prompt_builder.py
- Section 4 (Concept knowledge base) → out of scope for translation pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# --- Enums ---


class CoachMode(Enum):
    """Player skill mode (master doc §0-1).

    Determines tone (あやか / 智子 / 智子・辛口) and the lexical level
    of coaching vocabulary. Source: §0-1 (5 modes) and §0-3 (voice mapping).
    """

    BEGINNER = "beginner"  # 入門〜10級
    INTERMEDIATE = "intermediate"  # 9級〜4級
    DAN = "dan"  # 3級〜二段
    ADVANCED = "advanced"  # 三段〜五段
    EXPERT = "expert"  # 六段〜


class ToneVoice(Enum):
    """Coaching voice / tone (master doc §1-1).

    Three voices mapped to skill modes:
    - AYAKA: beginner + intermediate (Kansai dialect, friendly)
    - TOMOKO: dan + advanced (standard Japanese, logical)
    - TOMOKO_STRICT: expert (standard Japanese, research-peer, no sugar-coating)
    """

    AYAKA = "ayaka"
    TOMOKO = "tomoko"
    TOMOKO_STRICT = "tomoko_strict"


# --- Dataclasses ---


@dataclass(frozen=True)
class RankRange:
    """Inclusive rank range expressed in 'kyu/dan' notation.

    Mirrors the textual ranges in master doc §0-1 / §6.

    Attributes:
        min_rank: Lower bound (inclusive). Examples: "30k", "10k", "1k", "1d", "3d", "6d".
        max_rank: Upper bound (inclusive). Examples: "11k", "5k", "3k", "2d", "5d".
    """

    min_rank: str
    max_rank: str


@dataclass(frozen=True)
class ModeConfig:
    """Per-mode configuration derived from master doc §0.

    Attributes:
        mode: CoachMode key.
        label_jp: Japanese label (e.g. "初級").
        rank_range: Inclusive kyu/dan range (§0-1).
        voice: Default ToneVoice for this mode (§0-3).
        description_jp: One-line description of target player (§0-1).
    """

    mode: CoachMode
    label_jp: str
    rank_range: RankRange
    voice: ToneVoice
    description_jp: str


@dataclass(frozen=True)
class ToneConfig:
    """Per-voice configuration derived from master doc §1.

    Attributes:
        voice: ToneVoice key.
        label_jp: Japanese label (e.g. "あやか").
        dialect: "kansai" | "standard" | "standard_strict" (§1-1).
        characteristics_jp: Bullet-style characteristics (§1-1).
        praise_sample_jp: Sample phrase for "褒める時" (§1-2). Optional.
        critique_sample_jp: Sample phrase for "指摘する時" (§1-2). Optional.
        encourage_sample_jp: Sample phrase for "励ます時" (§1-2). Optional.
        excuse_handling_jp: Sample phrase for handling "言い訳" (§1-2). Optional.
        prohibited: List of prohibited behaviors (§1-4).
        kansai_dictionary: Standard-Japanese → Kansai mapping for AYAKA (§1-3).
    """

    voice: ToneVoice
    label_jp: str
    dialect: str
    characteristics_jp: str
    praise_sample_jp: str | None = None
    critique_sample_jp: str | None = None
    encourage_sample_jp: str | None = None
    excuse_handling_jp: str | None = None
    prohibited: tuple[str, ...] = field(default_factory=tuple)
    kansai_dictionary: dict[str, str] = field(default_factory=dict)


# --- §0-3 / §0-1: Mode → Rank mapping ---


_MODE_TABLE: tuple[ModeConfig, ...] = (
    ModeConfig(
        mode=CoachMode.BEGINNER,
        label_jp="初級",
        rank_range=RankRange(min_rank="30k", max_rank="11k"),
        voice=ToneVoice.AYAKA,
        description_jp="入門〜10級。ルール覚えたて〜9路・13路中心、基本戦術の習得段階。",
    ),
    ModeConfig(
        mode=CoachMode.INTERMEDIATE,
        label_jp="中級",
        rank_range=RankRange(min_rank="10k", max_rank="5k"),
        voice=ToneVoice.AYAKA,
        description_jp="9級〜4級。19路を打ち始め、基本死活・方向感覚を磨く段階。",
    ),
    ModeConfig(
        mode=CoachMode.DAN,
        label_jp="有段",
        rank_range=RankRange(min_rank="4k", max_rank="1d"),
        voice=ToneVoice.TOMOKO,
        description_jp="3級〜二段。安定して有段者、基礎固めから応用への移行期。",
    ),
    ModeConfig(
        mode=CoachMode.ADVANCED,
        label_jp="高段",
        rank_range=RankRange(min_rank="2d", max_rank="5d"),
        voice=ToneVoice.TOMOKO,
        description_jp="三段〜五段。形勢判断・読みの精度を高める段階。",
    ),
    ModeConfig(
        mode=CoachMode.EXPERT,
        label_jp="強豪",
        rank_range=RankRange(min_rank="6d", max_rank="99d"),
        voice=ToneVoice.TOMOKO_STRICT,
        description_jp="六段〜。県代表〜全国クラス、微差の構造分析・練習の質が課題。",
    ),
)


# --- §1-3: Kansai dictionary (AYAKA only) ---


_KANSAI_DICTIONARY: dict[str, str] = {
    "〜です/ます": "〜やで/〜やねん",
    "〜ですか？": "〜なん？/〜か？",
    "私": "ウチ",
    "ダメ": "あかん",
    "良い/いい": "ええ",
    "本当に": "ほんまに",
    "〜ではない": "〜ちゃう/〜やない",
    "〜している": "〜しとる",
    "〜ください": "〜してな/〜しとき",
    "すごい": "めっちゃ/ごっつ",
    "だから": "せやから",
    "そうだね": "せやな",
}


# --- §1: Tone voice configurations ---


_COMMON_PROHIBITED: tuple[str, ...] = (
    "キャラクター同士の会話（劇）を含めること。",
    "前置きや挨拶でキャラクターの設定を語ること。",
    "ユーザーが求めていない過剰な感情表現や装飾。",
    "内部タグ（facet等）をユーザーへの出力に含めること。",
)


_TONE_TABLE: tuple[ToneConfig, ...] = (
    ToneConfig(
        voice=ToneVoice.AYAKA,
        label_jp="あやか",
        dialect="kansai",
        characteristics_jp=(
            "【親しみ・関西弁・実利重視】\n"
            "・コテコテの大阪弁。敬語は使わずフランクに。\n"
            "・難しい専門用語は使わず、生活の例え話に変換する。\n"
            "・理論よりも「まずやってみる」モチベーションを重視。\n"
            "・ユーザーの言い訳には「せやな〜」と一度寄り添う。"
        ),
        praise_sample_jp=(
            "おっ、ここの打ち方ええやん！ちゃんと相手の切りを先に防いどるわ。"
            'こういう"転ばぬ先の杖"ができるようになったら、もう初心者卒業やで！'
        ),
        critique_sample_jp=(
            "あかんあかん！ここ、自分の石がアタリになっとるの見えてへんかったやろ？"
            '焦らんでええから、打つ前に"取られへん？"って1回だけ確認しとき。'
            "それだけで全然ちゃうで"
        ),
        encourage_sample_jp=(
            "まあ今日は負けたけど、気にせんでええねん。"
            "ウチが見たとこ、前より終盤粘れるようになっとるし、ちゃんと成長しとるわ。次いこ次！"
        ),
        excuse_handling_jp="せやな〜、そう思う気持ちはわかるで。でもな、ここだけちょっと見方変えてみ？",
        prohibited=_COMMON_PROHIBITED,
        kansai_dictionary=_KANSAI_DICTIONARY,
    ),
    ToneConfig(
        voice=ToneVoice.TOMOKO,
        label_jp="智子",
        dialect="standard",
        characteristics_jp=(
            "【論理・標準語・構造重視】\n"
            "・丁寧で落ち着いた標準語（敬語）。\n"
            "・論理的整合性を重視し、曖昧な点を明確にする。\n"
            "・ユーザーの思考の「構造的な欠陥」を穏やかに、しかし鋭く指摘する。\n"
            "・感情よりも事実と因果関係にフォーカスする。"
        ),
        praise_sample_jp=(
            "この場面で大場に回ったのは良い判断ですね。"
            "局所の戦いに引きずられず、全局を見る習慣ができてきています。"
        ),
        critique_sample_jp=(
            "この場面、読みの入り口で相手の最強応手を外していますね。気持ちは分かります。"
            "自分に都合の良い変化を先に見てしまうのは誰でもあることです。"
            "ただ、ここを変えるだけで結果はかなり違ってきます。"
        ),
        encourage_sample_jp=(
            "伸び悩みを感じているとのことですが、課題を言語化できている時点で、"
            "すでに次のステップに入っています。焦らず、一つずつ潰していきましょう。"
        ),
        excuse_handling_jp=(
            "その理屈も一理あります。ただ、事実として結果を見ると、別の解釈も成り立ちますね。"
        ),
        prohibited=_COMMON_PROHIBITED,
    ),
    ToneConfig(
        voice=ToneVoice.TOMOKO_STRICT,
        label_jp="智子（辛口）",
        dialect="standard_strict",
        characteristics_jp=(
            "【研究・対等・本質重視】\n"
            "・敬語は使うが、遠慮や社交辞令は一切なし。\n"
            "・議論の相手として対等に接する。\n"
            "・甘えや妥協（言い訳）に対しては、事実ベースで厳しく反論する。"
        ),
        praise_sample_jp=None,
        critique_sample_jp=(
            "率直に言います。この手は\"楽観バイアス\"そのものです。"
            "相手が最善を打ったらどうなるか、本当に読みましたか？"
        ),
        encourage_sample_jp=None,
        excuse_handling_jp=(
            "その説明は聞きました。ただ、それは\"なぜミスしたか\"の説明であって、"
            "\"ミスしなかった場合の変化\"ではありません。問題の構造を分けて考えましょう。"
        ),
        prohibited=_COMMON_PROHIBITED,
    ),
)


# --- Lookup indices (built once) ---


_MODE_BY_KEY: dict[CoachMode, ModeConfig] = {m.mode: m for m in _MODE_TABLE}
_TONE_BY_KEY: dict[ToneVoice, ToneConfig] = {t.voice: t for t in _TONE_TABLE}

# Rank ordering for comparison (smaller index = weaker player)
#
# Phase 225.8: extended with CJK / full-width notation aliases so
# ``estimate_mode_from_rank("4段")`` works the same as ``"4d"``.
_RANK_ORDER: dict[str, int] = {
    # Kyu (weaker) — ASCII
    "30k": 0,
    "25k": 1,
    "20k": 2,
    "15k": 3,
    "11k": 4,
    "10k": 5,
    "9k": 6,
    "8k": 7,
    "7k": 8,
    "6k": 9,
    "5k": 10,
    "4k": 11,
    "3k": 12,
    "2k": 13,
    "1k": 14,
    # Dan (stronger) — ASCII
    "1d": 15,
    "2d": 16,
    "3d": 17,
    "4d": 18,
    "5d": 19,
    "6d": 20,
    "7d": 21,
    "8d": 22,
    "9d": 23,
    "99d": 99,
}

# Kanji / full-width aliases for the same ranks.  Each alias points at
# the same integer value as its ASCII counterpart; we don't add new
# ranks, just new spellings.  Users from 野狐 / KGS often have these
# notations in their SGF BR/WR properties.
_RANK_ALIASES: dict[str, str] = {
    # Kanji 級 (kyu)
    "30級": "30k",
    "25級": "25k",
    "20級": "20k",
    "15級": "15k",
    "11級": "11k",
    "10級": "10k",
    "9級": "9k",
    "8級": "8k",
    "7級": "7k",
    "6級": "6k",
    "5級": "5k",
    "4級": "4k",
    "3級": "3k",
    "2級": "2k",
    "1級": "1k",
    # Kanji 段 (dan)
    "初段": "1d",
    "1段": "1d",
    "2段": "2d",
    "3段": "3d",
    "4段": "4d",
    "5段": "5d",
    "6段": "6d",
    "7段": "7d",
    "8段": "8d",
    "9段": "9d",
    "10段": "9d",
}


def _normalise_rank_str(rank_str: str) -> str:
    """Normalise a rank string to the canonical ``_RANK_ORDER`` key.

    Handles:
    - whitespace + case (``"4D"`` → ``"4d"``)
    - full-width digits (``"４段"`` → ``"4段"``)
    - kanji suffix (``"4段"`` → ``"4d"``, ``"5級"`` → ``"5k"``)
    - ASCII suffix synonyms (``"4kyu"`` → ``"4k"``, ``"5dan"`` → ``"5d"``)
    - ``"初段"`` (shodan) as an alias for ``"1段"``
    - trailing decoration (``"4d ?"`` → ``"4d"``)
    """
    if not rank_str:
        return ""
    s = rank_str.strip().lower().replace(" ", "")
    # Full-width ASCII digit folding (０-９ → 0-9).
    fullwidth = str.maketrans("０１２３４５６７８９", "0123456789")
    s = s.translate(fullwidth)
    # Special-case: 初段 (shodan) is rank 1d, not "0d".
    if s == "初段":
        return "1d"
    # Resolve kanji suffix to ASCII suffix.
    if s.endswith("段"):
        s = s[:-1] + "d"
    elif s.endswith("級"):
        s = s[:-1] + "k"
    elif s.endswith("kyu"):
        s = s[:-3] + "k"
    elif s.endswith("dan"):
        s = s[:-3] + "d"
    # Drop trailing punctuation (e.g. "4d?" or "4d.")
    s = s.rstrip("?.!#")
    return s


def _canonical_rank_key(rank_str: str | None) -> str:
    """Resolve ``rank_str`` to the canonical key in ``_RANK_ORDER``.

    Lookup order (Phase 226-C C1):
    1. ``_RANK_ALIASES`` against the *trimmed* raw input — this catches
       kanji and full-width notations whose ASCII normalisation would
       otherwise produce a key that does not exist in ``_RANK_ORDER``
       (e.g. ``"10段"`` → ``"10d"`` → not present → ``"9d"`` alias).
    2. ``_RANK_ALIASES`` against the *normalised* input — kept for
       symmetry and future aliases that survive normalisation.
    3. ``_RANK_ORDER`` against the normalised input.

    Returns ``""`` when no match.
    """
    if not rank_str:
        return ""
    # Phase 226-C (C1): pre-normalisation alias lookup. Without this,
    # ``_RANK_ALIASES`` was effectively dead code because every kanji
    # key normalises to an ASCII form that hits ``_RANK_ORDER`` first.
    stripped = rank_str.strip()
    if stripped in _RANK_ALIASES:
        return _RANK_ALIASES[stripped]
    normalised = _normalise_rank_str(rank_str)
    if not normalised:
        return ""
    if normalised in _RANK_ALIASES:
        return _RANK_ALIASES[normalised]
    if normalised in _RANK_ORDER:
        return normalised
    return ""


# --- Public API ---


def get_mode_config(mode: CoachMode) -> ModeConfig:
    """Return ModeConfig for a CoachMode (raises KeyError if missing)."""
    return _MODE_BY_KEY[mode]


def get_tone_config(voice: ToneVoice) -> ToneConfig:
    """Return ToneConfig for a ToneVoice (raises KeyError if missing)."""
    return _TONE_BY_KEY[voice]


def all_modes() -> tuple[ModeConfig, ...]:
    """Return all ModeConfig entries (ordered by §0-1)."""
    return _MODE_TABLE


def all_tones() -> tuple[ToneConfig, ...]:
    """Return all ToneConfig entries (ordered by §1-1)."""
    return _TONE_TABLE


def estimate_mode_from_rank(rank_str: str | None) -> CoachMode | None:
    """Estimate CoachMode from a rank string (e.g. "10k", "3d", "4段").

    Phase 225.8: also accepts CJK kanji notation (``"X段"`` / ``"X級"``)
    and full-width digits (``"４段"``) by routing through
    :func:`_canonical_rank_key`. Native ASCII entries continue to map
    to the same CoachMode as before.

    Args:
        rank_str: Rank in any supported notation. Returns None for
            unrecognised input (including ``None`` / empty).

    Returns:
        Matching CoachMode, or None if rank cannot be mapped.

    Example:
        >>> estimate_mode_from_rank("5k").name
        'INTERMEDIATE'
        >>> estimate_mode_from_rank("7d")
        <CoachMode.EXPERT: 'expert'>
        >>> estimate_mode_from_rank("4段")
        <CoachMode.ADVANCED: 'advanced'>
        >>> estimate_mode_from_rank(None) is None
        True
    """
    if not rank_str:
        return None

    canonical = _canonical_rank_key(rank_str)
    if not canonical or canonical not in _RANK_ORDER:
        return None

    rank_value = _RANK_ORDER[canonical]

    for mode_cfg in _MODE_TABLE:
        lo = _RANK_ORDER[mode_cfg.rank_range.min_rank]
        hi = _RANK_ORDER[mode_cfg.rank_range.max_rank]
        if lo <= rank_value <= hi:
            return mode_cfg.mode

    return None


def estimate_mode_from_loss(
    avg_points_lost: float | None,
    winrate_drop_pct: float | None = None,
    critical_move_count: int | None = None,
) -> CoachMode | None:
    """Estimate effective mode by 'loss correction' (master doc / §6 of Phase 203 doc).

    Adjusts the perceived skill level downward when KataGo signals a weak player.
    This is a *correction* on top of `estimate_mode_from_rank` and never upgrades
    the player (Phase 203 §6.3 contract).

    Args:
        avg_points_lost: Average pointsLost across the game (KataGo perspective).
            None means unknown — no adjustment applied.
        winrate_drop_pct: Maximum winrate drop observed in the game (0-100 scale).
            None means unknown.
        critical_move_count: Number of critical / blunder moves (Phase 149 定義).
            None means unknown.

    Returns:
        Effective CoachMode estimate. The function **never returns
        ``None``** — when no signal is available it falls back to
        ``INTERMEDIATE`` (the safe default). This was previously the
        docstring promise ("None if no signal available") but the
        implementation always anchored on ``estimate_mode_from_rank("10k")``
        which is ``INTERMEDIATE``. Phase 226-C (C3) reconciles the
        docstring with the implementation.

    Note:
        Loss thresholds (8.0 / 15.0 / 20%) are tentative — Phase 209 (golden
        game validation) is expected to refine them.
    """
    base = estimate_mode_from_rank("10k")  # safe default = INTERMEDIATE
    adjustments = 0

    if avg_points_lost is not None:
        if avg_points_lost > 8.0:
            adjustments += 1
        if avg_points_lost > 15.0:
            adjustments += 1

    if winrate_drop_pct is not None and winrate_drop_pct > 20.0:
        adjustments += 1

    if (
        critical_move_count is not None
        and avg_points_lost is not None
        and critical_move_count > 5
        and avg_points_lost > 5.0
    ):
        adjustments += 1

    modes = list(CoachMode)
    base_idx = modes.index(base)
    effective_idx = max(0, base_idx - adjustments)
    return modes[effective_idx]


__all__ = [
    "CoachMode",
    "ToneVoice",
    "RankRange",
    "ModeConfig",
    "ToneConfig",
    "get_mode_config",
    "get_tone_config",
    "all_modes",
    "all_tones",
    "estimate_mode_from_rank",
    "estimate_mode_from_loss",
    "_normalise_rank_str",
    "_canonical_rank_key",
]
