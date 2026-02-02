# -*- coding: utf-8 -*-
"""Style Archetype Data Models.

This module defines the core data structures for the Style Archetype system:
- StyleArchetypeId: Enum of all archetype identifiers
- StyleArchetype: Immutable archetype definition with matching criteria
- StyleResult: Immutable result of style analysis
- STYLE_ARCHETYPES: Registry of all archetype definitions

Part of Phase 56: Style Archetype Core.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.analysis.skill_radar import RadarAxis


class StyleArchetypeId(str, Enum):
    """Style archetype identifiers.

    Inherits from str for direct JSON serialization (no .value needed).

    All 6 archetypes represent positive playing style identities:
    - KIAI_FIGHTER: Aggressive fighter with fighting spirit
    - COSMIC_ARCHITECT: Grand visionary with opening sense
    - PRECISION_MACHINE: Precise calculator with endgame focus
    - SHINOBI_SURVIVOR: Resilient survivor with defensive skills
    - AI_NATIVE: Modern player with AI-influenced style
    - BALANCE_MASTER: Well-rounded player (fallback)
    """

    KIAI_FIGHTER = "kiai_fighter"
    COSMIC_ARCHITECT = "cosmic_architect"
    PRECISION_MACHINE = "precision_machine"
    SHINOBI_SURVIVOR = "shinobi_survivor"
    AI_NATIVE = "ai_native"
    BALANCE_MASTER = "balance_master"


@dataclass(frozen=True)
class StyleArchetype:
    """Immutable style archetype definition.

    Attributes:
        id: Archetype identifier
        name_key: i18n key for display name (e.g., "style:kiai_fighter:name")
        summary_key: i18n key for positive summary (e.g., "style:kiai_fighter:summary")
        high_axes: Radar axes that should be high (deviation >= 0.5)
        low_axes: Radar axes that should be low (deviation <= -0.5)
        reinforcing_tags: MeaningTags that reinforce this archetype

    Note:
        Translation happens at render time via i18n._("key") in Phase 57.
    """

    id: StyleArchetypeId
    name_key: str
    summary_key: str
    high_axes: frozenset[RadarAxis]
    low_axes: frozenset[RadarAxis]
    reinforcing_tags: frozenset[MeaningTagId]


@dataclass(frozen=True)
class StyleResult:
    """Result of style analysis.

    Attributes:
        archetype: The determined archetype
        confidence: Raw confidence value (0.0-1.0, NOT pre-rounded)
        axis_deviations: Deviation from mean for each axis (immutable)
        dominant_axis: The axis with highest deviation, or None if tied/balanced

    Note:
        confidence is stored as raw float. Rounding happens only in to_dict().
    """

    archetype: StyleArchetype
    confidence: float
    axis_deviations: Mapping[RadarAxis, float]
    dominant_axis: RadarAxis | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict. Rounding happens HERE only.

        Returns:
            Dictionary with archetype_id, confidence (rounded to 2 decimals),
            axis_deviations (rounded to 3 decimals), and dominant_axis.
        """
        return {
            "archetype_id": self.archetype.id.value,
            "confidence": round(self.confidence, 2),
            "axis_deviations": {
                k.value: round(v, 3) for k, v in self.axis_deviations.items()
            },
            "dominant_axis": self.dominant_axis.value if self.dominant_axis else None,
        }


# =============================================================================
# Archetype Registry
# =============================================================================

STYLE_ARCHETYPES: dict[StyleArchetypeId, StyleArchetype] = {
    StyleArchetypeId.KIAI_FIGHTER: StyleArchetype(
        id=StyleArchetypeId.KIAI_FIGHTER,
        name_key="style:kiai_fighter:name",
        summary_key="style:kiai_fighter:summary",
        high_axes=frozenset({RadarAxis.FIGHTING}),
        low_axes=frozenset({RadarAxis.STABILITY}),
        reinforcing_tags=frozenset({MeaningTagId.OVERPLAY, MeaningTagId.CAPTURE_RACE_LOSS}),
    ),
    StyleArchetypeId.COSMIC_ARCHITECT: StyleArchetype(
        id=StyleArchetypeId.COSMIC_ARCHITECT,
        name_key="style:cosmic_architect:name",
        summary_key="style:cosmic_architect:summary",
        high_axes=frozenset({RadarAxis.OPENING}),
        low_axes=frozenset({RadarAxis.ENDGAME}),
        reinforcing_tags=frozenset({MeaningTagId.DIRECTION_ERROR, MeaningTagId.SLOW_MOVE}),
    ),
    StyleArchetypeId.PRECISION_MACHINE: StyleArchetype(
        id=StyleArchetypeId.PRECISION_MACHINE,
        name_key="style:precision_machine:name",
        summary_key="style:precision_machine:summary",
        high_axes=frozenset({RadarAxis.ENDGAME}),
        low_axes=frozenset({RadarAxis.FIGHTING}),
        reinforcing_tags=frozenset({MeaningTagId.TERRITORIAL_LOSS}),
    ),
    StyleArchetypeId.SHINOBI_SURVIVOR: StyleArchetype(
        id=StyleArchetypeId.SHINOBI_SURVIVOR,
        name_key="style:shinobi_survivor:name",
        summary_key="style:shinobi_survivor:summary",
        high_axes=frozenset({RadarAxis.STABILITY}),
        low_axes=frozenset({RadarAxis.OPENING}),
        reinforcing_tags=frozenset({MeaningTagId.SHAPE_MISTAKE, MeaningTagId.CONNECTION_MISS}),
    ),
    StyleArchetypeId.AI_NATIVE: StyleArchetype(
        id=StyleArchetypeId.AI_NATIVE,
        name_key="style:ai_native:name",
        summary_key="style:ai_native:summary",
        high_axes=frozenset({RadarAxis.AWARENESS}),
        low_axes=frozenset(),  # No low axis requirement
        reinforcing_tags=frozenset(),  # No reinforcing tags
    ),
    StyleArchetypeId.BALANCE_MASTER: StyleArchetype(
        id=StyleArchetypeId.BALANCE_MASTER,
        name_key="style:balance_master:name",
        summary_key="style:balance_master:summary",
        high_axes=frozenset(),  # Fallback - no axis requirement
        low_axes=frozenset(),
        reinforcing_tags=frozenset(),
    ),
}
