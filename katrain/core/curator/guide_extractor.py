"""Replay guide extractor for Curator (Phase 64).

This module extracts highlight moments from analyzed games using Critical 3 logic.
The output is designed for replay guidance and LLM coaching integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from katrain.common import to_iso_lang_code
from katrain.core.analysis.meaning_tags import get_meaning_tag_label_safe

if TYPE_CHECKING:
    from katrain.core.game import Game


@dataclass(frozen=True)
class HighlightMoment:
    """A single highlight moment from a game.

    Represents a critical move worthy of review during replay.
    All fields are populated from CriticalMove data.

    Attributes:
        move_number: 1-indexed move number
        player: "B" or "W"
        gtp_coord: GTP coordinate (e.g., "D4", "pass")
        meaning_tag_id: MeaningTagId.value (e.g., "overplay"), always str
        meaning_tag_label: Localized label (None if tag not found)
        score_loss: Loss from the move, rounded to 2 decimals in JSON
        game_phase: "opening", "middle", or "yose"
    """

    move_number: int
    player: str
    gtp_coord: str
    meaning_tag_id: str
    meaning_tag_label: Optional[str]
    score_loss: float
    game_phase: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict with score_loss rounded to 2 decimals."""
        return {
            "move_number": self.move_number,
            "player": self.player,
            "gtp_coord": self.gtp_coord,
            "meaning_tag_id": self.meaning_tag_id,
            "meaning_tag_label": self.meaning_tag_label,
            "score_loss": round(self.score_loss, 2),
            "game_phase": self.game_phase,
        }


@dataclass(frozen=True)
class ReplayGuide:
    """Replay guide for a single game.

    Contains metadata and highlight moments for guiding replay review.

    Attributes:
        game_id: Relative path to SGF file (e.g., "pro_games/2026/game_001.sgf")
        game_title: Display title (e.g., "Shin Jinseo vs Ke Jie")
        total_moves: Total number of moves in the game
        highlight_moments: List of critical moments to review
    """

    game_id: str
    game_title: str
    total_moves: int
    highlight_moments: List[HighlightMoment]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "game_id": self.game_id,
            "game_title": self.game_title,
            "total_moves": self.total_moves,
            "highlight_moments": [h.to_dict() for h in self.highlight_moments],
        }


def extract_replay_guide(
    game: "Game",
    game_id: str,
    game_title: str,
    total_moves: int,
    max_highlights: int = 5,
    lang: str = "jp",
    level: str = "normal",
) -> ReplayGuide:
    """Extract replay guide using Critical 3 logic.

    Args:
        game: Analyzed Game object
        game_id: Relative path to SGF file (stats["game_name"])
        game_title: Display title for the game
        total_moves: Total number of moves (from stats["total_moves"])
        max_highlights: Maximum number of highlight moments (default: 5)
        lang: Internal language code ("jp" or "en", default: "jp")
        level: Difficulty level for select_critical_moves ("normal" recommended)

    Returns:
        ReplayGuide with extracted highlight moments

    Note:
        - lang is converted to ISO via to_iso_lang_code() for select_critical_moves()
        - lang is passed directly to get_meaning_tag_label_safe() (handles conversion)
        - level is passed through to select_critical_moves()
    """
    from katrain.core.analysis import select_critical_moves

    # select_critical_moves expects ISO lang code ("ja" or "en")
    iso_lang = to_iso_lang_code(lang)
    critical = select_critical_moves(
        game,
        max_moves=max_highlights,
        lang=iso_lang,
        level=level,
    )

    highlights = [
        HighlightMoment(
            move_number=cm.move_number,
            player=cm.player,
            gtp_coord=cm.gtp_coord,
            meaning_tag_id=cm.meaning_tag_id,
            meaning_tag_label=get_meaning_tag_label_safe(cm.meaning_tag_id, lang),
            score_loss=cm.score_loss,
            game_phase=cm.game_phase,
        )
        for cm in critical
    ]

    return ReplayGuide(
        game_id=game_id,
        game_title=game_title,
        total_moves=total_moves,
        highlight_moments=highlights,
    )
