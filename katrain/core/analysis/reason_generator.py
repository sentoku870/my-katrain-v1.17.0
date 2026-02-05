"""Reason Generator for Mistake Pattern Explanations.

Phase 86: Generates natural language "reason" text from MistakeSignature
(phase/area/tag) combinations. Limited implementation with single-tag
and selected combination templates.

Public API:
    - generate_reason: Generate reason text (returns None if no match)
    - generate_reason_safe: Safe version that never raises (returns "" if no match)
    - SUPPORTED_TAGS: Set of tags with reason templates
    - PHASE_VOCABULARY: Valid phase values
    - AREA_VOCABULARY: Valid area values
"""

from dataclasses import dataclass

from katrain.common.locale_utils import normalize_lang_code

# =============================================================================
# Constants
# =============================================================================

# Valid internal language codes
_VALID_LANGS: frozenset[str] = frozenset({"jp", "en"})

# Supported meaning tags (Phase 86 scope)
SUPPORTED_TAGS: frozenset[str] = frozenset(
    {
        "life_death_error",
        "overplay",
        "direction_error",
        "capture_race_loss",
        "connection_miss",
        "reading_failure",
        "shape_mistake",
        "slow_move",
        "missed_tesuji",
        "endgame_slip",
        "territorial_loss",
        "uncertain",
    }
)

# Valid phase values (from MistakeSignature.phase)
PHASE_VOCABULARY: frozenset[str] = frozenset({"opening", "middle", "endgame"})

# Valid area values (from BoardArea enum .value)
AREA_VOCABULARY: frozenset[str] = frozenset({"corner", "edge", "center"})


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class ReasonTemplate:
    """Bilingual reason template.

    Attributes:
        jp: Japanese template text
        en: English template text
    """

    jp: str
    en: str

    def get(self, lang: str) -> str:
        """Get template for the specified language.

        Args:
            lang: Normalized language code ("jp" or "en")

        Returns:
            Template text for the language
        """
        return self.jp if lang == "jp" else self.en


# =============================================================================
# Template Data
# =============================================================================

# Single-tag reason templates (12 entries)
SINGLE_TAG_REASONS: dict[str, ReasonTemplate] = {
    "life_death_error": ReasonTemplate(
        jp="石の生死に関わる読み間違いです。",
        en="A reading mistake involving life and death.",
    ),
    "overplay": ReasonTemplate(
        jp="無理な手で損失が発生しました。",
        en="An overplay that led to a loss.",
    ),
    "direction_error": ReasonTemplate(
        jp="攻める方向を間違えました。",
        en="Attacked in the wrong direction.",
    ),
    "capture_race_loss": ReasonTemplate(
        jp="攻め合いで負けました。",
        en="Lost a capturing race.",
    ),
    "connection_miss": ReasonTemplate(
        jp="石の連絡を見逃しました。",
        en="Missed a connection opportunity.",
    ),
    "reading_failure": ReasonTemplate(
        jp="読み抜けがありました。",
        en="A reading oversight occurred.",
    ),
    "shape_mistake": ReasonTemplate(
        jp="石の形が悪くなりました。",
        en="Created bad shape.",
    ),
    "slow_move": ReasonTemplate(
        jp="緩い手で先手を失いました。",
        en="A slow move that lost initiative.",
    ),
    "missed_tesuji": ReasonTemplate(
        jp="手筋を見逃しました。",
        en="Missed a tesuji.",
    ),
    "endgame_slip": ReasonTemplate(
        jp="ヨセで計算ミスがありました。",
        en="A calculation mistake in endgame.",
    ),
    "territorial_loss": ReasonTemplate(
        jp="地を損しました。",
        en="Lost territory.",
    ),
    "uncertain": ReasonTemplate(
        jp="分類困難な局面です。",
        en="Difficult to classify.",
    ),
}

# Combination reason templates (15 entries)
# Key: (phase, area, tag) where "*" means "don't inspect this slot"
COMBINATION_REASONS: dict[tuple[str, str, str], ReasonTemplate] = {
    ("opening", "corner", "direction_error"): ReasonTemplate(
        jp="隅での方向判断ミス。布石の基本を復習しましょう。",
        en="Direction misjudgment in the corner. Review opening fundamentals.",
    ),
    ("opening", "edge", "direction_error"): ReasonTemplate(
        jp="辺での展開方向を見誤りました。",
        en="Misjudged the direction of development on the side.",
    ),
    ("middle", "corner", "life_death_error"): ReasonTemplate(
        jp="隅の死活で読み間違いが発生しました。",
        en="A reading mistake in corner life and death.",
    ),
    ("middle", "edge", "connection_miss"): ReasonTemplate(
        jp="辺での石の連絡を見逃しました。",
        en="Missed a connection opportunity on the side.",
    ),
    ("middle", "center", "capture_race_loss"): ReasonTemplate(
        jp="中央の攻め合いで負けました。",
        en="Lost a capturing race in the center.",
    ),
    ("endgame", "corner", "endgame_slip"): ReasonTemplate(
        jp="隅のヨセで計算ミスがありました。",
        en="A calculation mistake in corner endgame.",
    ),
    ("endgame", "edge", "territorial_loss"): ReasonTemplate(
        jp="辺のヨセで地を損しました。",
        en="Lost territory in side endgame.",
    ),
    # Area wildcard: matches any area value (including None)
    ("middle", "*", "overplay"): ReasonTemplate(
        jp="中盤での無理な攻めが裏目に出ました。",
        en="An overplay in the midgame backfired.",
    ),
    # Phase 87: Additional combination templates (7 entries)
    ("opening", "corner", "overplay"): ReasonTemplate(
        jp="隅での定石選択が無理でした。相手の反撃に備えましょう。",
        en="An overplay in the corner joseki. Be prepared for counterattacks.",
    ),
    ("opening", "edge", "slow_move"): ReasonTemplate(
        jp="序盤の辺で緩い手を打ちました。大場を優先しましょう。",
        en="A slow move on the side in the opening. Prioritize big points.",
    ),
    ("middle", "corner", "capture_race_loss"): ReasonTemplate(
        jp="隅の攻め合いで手数を読み間違えました。",
        en="Miscounted liberties in a corner capturing race.",
    ),
    ("middle", "edge", "life_death_error"): ReasonTemplate(
        jp="辺の石の死活で判断ミスがありました。",
        en="A life and death misjudgment on the side.",
    ),
    ("middle", "center", "direction_error"): ReasonTemplate(
        jp="中央の戦いで攻め方向を誤りました。",
        en="Wrong direction of attack in the center fight.",
    ),
    ("endgame", "edge", "slow_move"): ReasonTemplate(
        jp="辺のヨセで大きな先手を逃しました。",
        en="Missed a big sente move in side endgame.",
    ),
    ("endgame", "center", "territorial_loss"): ReasonTemplate(
        jp="中央の地の出入りで損をしました。",
        en="Lost points in center territory exchange.",
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================


def _normalize_lang(lang: str | None) -> str:
    """Normalize language code for reason_generator.

    Args:
        lang: Input language code (None allowed)

    Returns:
        "jp" or "en"

    Behavior:
        - None → "jp" (Japanese default for this app)
        - "" or whitespace-only → "en"
        - Otherwise → normalize_lang_code() with fallback
        - Unknown codes → "en"
    """
    if lang is None:
        return "jp"
    if not lang.strip():
        return "en"
    try:
        normalized = normalize_lang_code(lang)
    except Exception:
        return "en"
    if normalized not in _VALID_LANGS:
        return "en"
    return normalized


def _find_combo_match(
    phase: str | None,
    area: str | None,
    tag: str,
    lang: str,
) -> str | None:
    """Find matching combination template.

    Matching order:
        1. (phase, area, tag) - Complete match (both non-None)
        2. (phase, "*", tag) - Area wildcard (phase non-None)
        3. ("*", area, tag) - Phase wildcard (area non-None)

    Args:
        phase: Game phase or None
        area: Board area or None
        tag: Meaning tag ID
        lang: Normalized language code

    Returns:
        Matched template text or None
    """
    # Step 1: Complete match (phase and area both non-None)
    if phase is not None and area is not None:
        key = (phase, area, tag)
        if key in COMBINATION_REASONS:
            return COMBINATION_REASONS[key].get(lang)

    # Step 2: Area wildcard (phase non-None, area can be anything)
    if phase is not None:
        key = (phase, "*", tag)
        if key in COMBINATION_REASONS:
            return COMBINATION_REASONS[key].get(lang)

    # Step 3: Phase wildcard (area non-None)
    if area is not None:
        key = ("*", area, tag)
        if key in COMBINATION_REASONS:
            return COMBINATION_REASONS[key].get(lang)

    return None


# =============================================================================
# Public API
# =============================================================================


def generate_reason(
    meaning_tag_id: str | None,
    phase: str | None = None,
    area: str | None = None,
    lang: str | None = None,
) -> str | None:
    """Generate natural language reason text.

    Args:
        meaning_tag_id: MeaningTagId.value (e.g., "overplay") or None
        phase: "opening" / "middle" / "endgame" or None
        area: "corner" / "edge" / "center" or None
        lang: Language code or None (None → "jp")

    Returns:
        Reason text string, or None if no match

    Matching order:
        1. (phase, area, tag) - Complete combination match
        2. (phase, "*", tag) - Area wildcard match
        3. ("*", area, tag) - Phase wildcard match
        4. tag only - Single tag template
        5. None - No match
    """
    if not meaning_tag_id:
        return None

    normalized_lang = _normalize_lang(lang)

    # Try combination match first
    combo_result = _find_combo_match(phase, area, meaning_tag_id, normalized_lang)
    if combo_result is not None:
        return combo_result

    # Fall back to single tag
    if meaning_tag_id in SINGLE_TAG_REASONS:
        return SINGLE_TAG_REASONS[meaning_tag_id].get(normalized_lang)

    return None


def generate_reason_safe(
    meaning_tag_id: str | None,
    phase: str | None = None,
    area: str | None = None,
    lang: str | None = None,
    fallback_label: str | None = None,
) -> str:
    """Safe version of generate_reason that never raises.

    Args:
        meaning_tag_id: MeaningTagId.value or None
        phase: Game phase or None
        area: Board area or None
        lang: Language code or None (None → "jp")
        fallback_label: Label to return if no match (default: "")

    Returns:
        Reason text string. Returns fallback_label (or "") if no match.
    """
    try:
        result = generate_reason(meaning_tag_id, phase, area, lang)
        if result is not None:
            return result
    except Exception:
        pass
    return fallback_label if fallback_label is not None else ""
