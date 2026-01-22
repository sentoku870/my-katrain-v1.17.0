# -*- coding: utf-8 -*-
"""Meaning Tags Registry.

This module defines the static registry of all meaning tags:
- MeaningTagDefinition: Frozen dataclass for tag metadata
- MEANING_TAG_REGISTRY: Dict mapping MeaningTagId to definitions
- Helper functions for accessing tag metadata

Part of Phase 46: Meaning Tags System Core.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .models import MeaningTagId


@dataclass(frozen=True)
class MeaningTagDefinition:
    """Static definition of a meaning tag.

    Contains metadata for display and Lexicon integration:
    - id: The tag identifier
    - ja_label: Japanese display label
    - en_label: English display label
    - ja_description: Japanese description for LLM prompts
    - en_description: English description for LLM prompts
    - default_lexicon_anchor: Lexicon entry ID (None if no mapping exists)
    - related_reason_tags: MoveEval.reason_tags that trigger this tag

    Note:
        Lexicon anchor IDs were validated against the actual YAML file.
        Only 6 tags have valid anchors; others are set to None.
    """

    id: MeaningTagId
    ja_label: str
    en_label: str
    ja_description: str
    en_description: str
    default_lexicon_anchor: Optional[str] = None
    related_reason_tags: Tuple[str, ...] = ()


# =============================================================================
# MEANING_TAG_REGISTRY
# =============================================================================
# All 12 tags with validated Lexicon anchor IDs.
#
# Anchors with valid Lexicon entries (verified in go_lexicon_master_last.yaml):
#   - tesuji (line 1536)
#   - direction_of_play (line 4671)
#   - yose (line 2820)
#   - connection (line 868)
#   - semeai (line 2782)
#   - territory (line 86)
#
# Anchors set to None (ID does not exist in Lexicon):
#   - overplay, slow-move, shape, reading, life-death
# =============================================================================

MEANING_TAG_REGISTRY: Dict[MeaningTagId, MeaningTagDefinition] = {
    MeaningTagId.MISSED_TESUJI: MeaningTagDefinition(
        id=MeaningTagId.MISSED_TESUJI,
        ja_label="手筋見逃し",
        en_label="Missed Tesuji",
        ja_description="明らかな好手（手筋）を見逃しました。最善手のpolicyが高く、実戦手のpolicyが低い場合に検出されます。",
        en_description="You missed an obvious good move (tesuji). Detected when the best move has high policy but your actual move had low policy.",
        default_lexicon_anchor="tesuji",
        related_reason_tags=(),
    ),
    MeaningTagId.OVERPLAY: MeaningTagDefinition(
        id=MeaningTagId.OVERPLAY,
        ja_label="無理手",
        en_label="Overplay",
        ja_description="リスクの高い無理な手でした。局面が複雑（scoreStdevが高い）な状況で大きな損失が発生しました。",
        en_description="This was a risky overplay. A large loss occurred in a complex position (high score stdev).",
        default_lexicon_anchor=None,
        related_reason_tags=("heavy_loss",),
    ),
    MeaningTagId.SLOW_MOVE: MeaningTagDefinition(
        id=MeaningTagId.SLOW_MOVE,
        ja_label="緩手",
        en_label="Slow Move",
        ja_description="緊急性のない場所で、最善手に近い場所に打ちましたが、小さな損失がありました。",
        en_description="You played near the best move in a non-urgent area, but there was a small loss.",
        default_lexicon_anchor=None,
        related_reason_tags=(),
    ),
    MeaningTagId.DIRECTION_ERROR: MeaningTagDefinition(
        id=MeaningTagId.DIRECTION_ERROR,
        ja_label="方向違い",
        en_label="Direction Error",
        ja_description="序盤で大局観を外しました。最善手と実戦手が盤上で大きく離れています。",
        en_description="Your global sense was off in the opening. The best move and your actual move were far apart on the board.",
        default_lexicon_anchor="direction_of_play",
        related_reason_tags=(),
    ),
    MeaningTagId.SHAPE_MISTAKE: MeaningTagDefinition(
        id=MeaningTagId.SHAPE_MISTAKE,
        ja_label="愚形",
        en_label="Bad Shape",
        ja_description="AIがほとんど考慮しない「形の悪い手」でした。policyが極めて低い手です。",
        en_description="This was a 'bad shape' move that AI barely considered. The policy was extremely low.",
        default_lexicon_anchor=None,
        related_reason_tags=(),
    ),
    MeaningTagId.READING_FAILURE: MeaningTagDefinition(
        id=MeaningTagId.READING_FAILURE,
        ja_label="読み抜け",
        en_label="Reading Failure",
        ja_description="読みの失敗です。AIも有力と考えた手でしたが、結果的に大きな損失につながりました。",
        en_description="A reading failure. AI also considered this move promising, but it led to a large loss.",
        default_lexicon_anchor=None,
        related_reason_tags=("reading_failure",),
    ),
    MeaningTagId.ENDGAME_SLIP: MeaningTagDefinition(
        id=MeaningTagId.ENDGAME_SLIP,
        ja_label="ヨセのミス",
        en_label="Endgame Slip",
        ja_description="終盤でのヨセの計算ミスです。小〜中程度の損失が発生しました。",
        en_description="An endgame calculation error. A small to medium loss occurred.",
        default_lexicon_anchor="yose",
        related_reason_tags=("endgame_hint",),
    ),
    MeaningTagId.CONNECTION_MISS: MeaningTagDefinition(
        id=MeaningTagId.CONNECTION_MISS,
        ja_label="連絡見逃し",
        en_label="Connection Miss",
        ja_description="石の連絡に関するミスです。切断のリスクがあったか、連絡が必要な場面でした。",
        en_description="A mistake related to stone connection. There was a cutting risk or a need to connect.",
        default_lexicon_anchor="connection",
        related_reason_tags=("need_connect", "cut_risk"),
    ),
    MeaningTagId.CAPTURE_RACE_LOSS: MeaningTagDefinition(
        id=MeaningTagId.CAPTURE_RACE_LOSS,
        ja_label="攻め合い負け",
        en_label="Capture Race Loss",
        ja_description="攻め合い（セメアイ）に負けました。アタリと呼吸点の両方が関係する大きな損失です。",
        en_description="You lost a capture race (semeai). A large loss involving both atari and low liberties.",
        default_lexicon_anchor="semeai",
        related_reason_tags=("atari", "low_liberties"),
    ),
    MeaningTagId.LIFE_DEATH_ERROR: MeaningTagDefinition(
        id=MeaningTagId.LIFE_DEATH_ERROR,
        ja_label="死活ミス",
        en_label="Life/Death Error",
        ja_description="石の生死に関わる重大なミスです。ownership（所有権）の大きな変動、または壊滅的な損失が発生しました。",
        en_description="A critical mistake involving the life or death of stones. Large ownership flux or catastrophic loss.",
        default_lexicon_anchor=None,
        related_reason_tags=("atari", "low_liberties"),
    ),
    MeaningTagId.TERRITORIAL_LOSS: MeaningTagDefinition(
        id=MeaningTagId.TERRITORIAL_LOSS,
        ja_label="地の損失",
        en_label="Territorial Loss",
        ja_description="地の損失です。戦術的なタグがなく、終盤でもない状況での中程度以上の損失です。",
        en_description="A territorial loss. A medium or larger loss without tactical tags and not in the endgame.",
        default_lexicon_anchor="territory",
        related_reason_tags=(),
    ),
    MeaningTagId.UNCERTAIN: MeaningTagDefinition(
        id=MeaningTagId.UNCERTAIN,
        ja_label="分類困難",
        en_label="Uncertain",
        ja_description="どのカテゴリにも明確に分類できませんでした。",
        en_description="Could not be clearly classified into any category.",
        default_lexicon_anchor=None,
        related_reason_tags=(),
    ),
}


def get_tag_definition(tag_id: MeaningTagId) -> MeaningTagDefinition:
    """Get the definition for a meaning tag.

    Args:
        tag_id: The tag identifier

    Returns:
        MeaningTagDefinition for the tag

    Raises:
        KeyError: If tag_id is not in the registry
    """
    return MEANING_TAG_REGISTRY[tag_id]


def get_tag_label(tag_id: MeaningTagId, lang: str = "ja") -> str:
    """Get the localized label for a meaning tag.

    Args:
        tag_id: The tag identifier
        lang: Language code ("ja" or "en"), defaults to "ja"

    Returns:
        Localized label string

    Raises:
        KeyError: If tag_id is not in the registry
    """
    definition = MEANING_TAG_REGISTRY[tag_id]
    if lang == "en":
        return definition.en_label
    return definition.ja_label


def get_tag_description(tag_id: MeaningTagId, lang: str = "ja") -> str:
    """Get the localized description for a meaning tag.

    Args:
        tag_id: The tag identifier
        lang: Language code ("ja" or "en"), defaults to "ja"

    Returns:
        Localized description string

    Raises:
        KeyError: If tag_id is not in the registry
    """
    definition = MEANING_TAG_REGISTRY[tag_id]
    if lang == "en":
        return definition.en_description
    return definition.ja_description
