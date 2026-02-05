"""LLM prompt generation for karte report.

Contains:
- build_critical_3_prompt(): Build LLM prompt from Critical 3 moves
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from katrain.core.reports.karte.models import CRITICAL_3_PROMPT_TEMPLATE

if TYPE_CHECKING:
    from katrain.core.analysis.critical_moves import CriticalMove


def build_critical_3_prompt(
    critical_moves: list[CriticalMove],
    player_level: str = "intermediate",
) -> str:
    """Build an LLM prompt from Critical 3 moves.

    Args:
        critical_moves: List of CriticalMove objects (max 3)
        player_level: Player skill description (e.g., "intermediate", "dan-level")

    Returns:
        Self-contained markdown prompt for LLM analysis.

    Example:
        >>> critical = select_critical_moves(game, max_moves=3)
        >>> prompt = build_critical_3_prompt(critical, "4-5 dan amateur")
        >>> # Send prompt to LLM
    """
    if not critical_moves:
        return ""

    move_sections = []
    for _i, cm in enumerate(critical_moves, 1):
        section = f"""### Move #{cm.move_number} ({cm.player}) {cm.gtp_coord}
- Loss: {cm.score_loss:.1f} pts (side-to-move perspective)
- Type: {cm.meaning_tag_label}
- Phase: {cm.game_phase}
- Difficulty: {cm.position_difficulty.upper()}"""

        if cm.reason_tags:
            section += f"\n- Context: {', '.join(cm.reason_tags)}"

        move_sections.append(section)

    critical_moves_section = "\n\n".join(move_sections)

    return CRITICAL_3_PROMPT_TEMPLATE.format(
        player_level=player_level,
        critical_moves_section=critical_moves_section,
    )
