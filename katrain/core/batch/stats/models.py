"""Data models and constants for batch statistics.

This module contains:
- EvidenceMove dataclass
- All i18n constants

No dependencies on other stats submodules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict

# Phase 49: Radar imports for type hints
from katrain.core.analysis.skill_radar import (
    RadarAxis,
    SkillTier,
)

if TYPE_CHECKING:
    from katrain.core.analysis.models import MistakeCategory


# Generic player names to skip
SKIP_PLAYER_NAMES = frozenset({"Black", "White", "黒", "白", "", "?", "Unknown", "不明"})


# =============================================================================
# Evidence Support (Phase 66)
# =============================================================================


@dataclass(frozen=True)
class EvidenceMove:
    """Lightweight evidence holder - avoids synthesizing MoveEval.

    Contains only the fields needed for evidence display.
    Does NOT inherit from or synthesize MoveEval.

    Attributes:
        game_name: Name/path of the game file
        move_number: Move number in the game
        player: "B" or "W"
        gtp: GTP coordinate (e.g., "D4")
        points_lost: Loss in points
        mistake_category: MistakeCategory enum value
    """

    game_name: str
    move_number: int
    player: str
    gtp: str
    points_lost: float
    mistake_category: "MistakeCategory"


# =============================================================================
# Phase 49: Skill Profile Constants
# =============================================================================

# Tier label mapping (i18n keys with English fallback)
TIER_LABELS = {
    SkillTier.TIER_1: "Tier 1 (Novice)",
    SkillTier.TIER_2: "Tier 2 (Apprentice)",
    SkillTier.TIER_3: "Tier 3 (Proficient)",
    SkillTier.TIER_4: "Tier 4 (Advanced)",
    SkillTier.TIER_5: "Tier 5 (Elite)",
    SkillTier.TIER_UNKNOWN: "N/A",
}

# Axis label mapping (i18n keys with English fallback)
AXIS_LABELS = {
    RadarAxis.OPENING: "Opening",
    RadarAxis.FIGHTING: "Fighting",
    RadarAxis.ENDGAME: "Endgame",
    RadarAxis.STABILITY: "Stability",
    RadarAxis.AWARENESS: "Awareness",
}

# Practice hints for weak axes (English - default)
AXIS_PRACTICE_HINTS = {
    RadarAxis.OPENING: "Study fuseki patterns and joseki choices",
    RadarAxis.FIGHTING: "Practice life & death problems and fighting tesuji",
    RadarAxis.ENDGAME: "Study yose counting and endgame sequences",
    RadarAxis.STABILITY: "Focus on solid shape; avoid overplays in won positions",
    RadarAxis.AWARENESS: "Review AI's top choices to calibrate intuition",
}


# =============================================================================
# Phase 54: Localization Constants
# =============================================================================

# Localized axis practice hints
AXIS_PRACTICE_HINTS_LOCALIZED: Dict[str, Dict[RadarAxis, str]] = {
    "jp": {
        RadarAxis.OPENING: "布石のパターンと定石選択を学ぶ",
        RadarAxis.FIGHTING: "詰碁と戦いの手筋を練習する",
        RadarAxis.ENDGAME: "ヨセの計算と終盤の手順を学ぶ",
        RadarAxis.STABILITY: "堅実な形を心がけ、優勢での無理を避ける",
        RadarAxis.AWARENESS: "AIの候補手を確認し、直感を調整する",
    },
    "en": AXIS_PRACTICE_HINTS,  # Use English defaults
}

# Meaning tag practice hints (lowercase snake_case IDs)
MTAG_PRACTICE_HINTS: Dict[str, Dict[str, str]] = {
    "jp": {
        "connection_miss": "石の連絡を意識した打ち方を練習",
        "reading_failure": "詰碁で読みを強化",
        "life_death_error": "死活問題を集中的に解く",
        "overplay": "形勢判断を意識し、無理な手を避ける",
        "slow_move": "盤面全体を見渡し、大きな場所を探す",
        "direction_error": "石の方向性と全局的なバランスを意識",
        "shape_error": "良い形・悪い形を学び、効率を高める",
        "timing_error": "手順の優先度を見直す",
    },
    "en": {
        "connection_miss": "Practice connecting moves and cut prevention",
        "reading_failure": "Strengthen reading with tsumego",
        "life_death_error": "Focus on life & death problems",
        "overplay": "Consider whole-board evaluation before aggressive moves",
        "slow_move": "Look for bigger moves across the board",
        "direction_error": "Study directional play and whole-board balance",
        "shape_error": "Learn good/bad shapes to improve efficiency",
        "timing_error": "Review move order priorities",
    },
}

# Reason tag practice hints (lowercase snake_case keys)
RTAG_PRACTICE_HINTS: Dict[str, Dict[str, str]] = {
    "jp": {
        "need_connect": "石の連絡と切断に注意",
        "low_liberties": "呼吸点の管理を意識",
        "atari": "アタリへの反応を確認",
        "reading_failure": "読みの深さを意識",
        "life_death": "死活の判断を磨く",
        "territory_loss": "地の損失を意識",
    },
    "en": {
        "need_connect": "Pay attention to connections and cuts",
        "low_liberties": "Manage liberties carefully",
        "atari": "Check responses to atari",
        "reading_failure": "Deepen reading depth",
        "life_death": "Improve life & death judgment",
        "territory_loss": "Consider territory implications",
    },
}

# Localized intro texts
PRACTICE_INTRO_TEXTS: Dict[str, str] = {
    "jp": "上記のデータに基づき、以下を重点的に練習してください：\n",
    "en": "Based on the data above, consider focusing on:\n",
}

# Localized notes headers
NOTES_HEADERS: Dict[str, str] = {
    "jp": "## 注記",
    "en": "## Notes",
}

# Localized hint line formats
HINT_LINE_FORMATS: Dict[str, str] = {
    "jp": "**{label}**（{count}回）→ {hint}",
    "en": "**{label}** ({count}x) -> {hint}",
}

# Localized percentage notes
PERCENTAGE_NOTES: Dict[str, str] = {
    "jp": "*パーセンテージはタグ出現回数の割合です（重要局面あたりではありません）*",
    "en": "*Percentages represent tag occurrence ratios (not per critical move)*",
}

# Localized color bias notes
COLOR_BIAS_NOTES: Dict[str, Dict[str, str]] = {
    "jp": {
        "B": "*注: 全て黒番のデータです*",
        "W": "*注: 全て白番のデータです*",
    },
    "en": {
        "B": "*Note: All games played as Black*",
        "W": "*Note: All games played as White*",
    },
}

# Localized phase-based priority texts
PHASE_PRIORITY_TEXTS: Dict[str, Dict[str, str]] = {
    "jp": {
        "opening": "**布石の原理と定石**を学ぶ（平均損失が最も高い）",
        "middle": "**戦いと読み**を練習する（中盤での平均損失が高い）",
        "yose": "**ヨセの技術**を学ぶ（平均損失が最も高い）",
        "blunder_review": "{phase}の大悪手を復習（{count}回発生）",
        "life_death": "**死活問題**を練習して大悪手を減らす",
        "no_priority": "特に優先すべき課題なし。バランスの良い練習を続けてください！",
        "no_weakness": "明確な弱点パターンなし。この調子で頑張ってください！",
    },
    "en": {
        "opening": "Study **opening principles and joseki** (highest avg loss)",
        "middle": "Practice **fighting and reading** (highest avg loss in middle game)",
        "yose": "Study **endgame techniques** (highest avg loss)",
        "blunder_review": "Review {phase} blunders ({count} occurrences)",
        "life_death": "Practice **life and death problems** to reduce blunders",
        "no_priority": "No specific priorities identified. Continue balanced practice!",
        "no_weakness": "No clear weakness pattern detected. Keep up the good work!",
    },
}

# Localized phase labels
PHASE_LABELS_LOCALIZED: Dict[str, Dict[str, str]] = {
    "jp": {
        "opening": "序盤",
        "middle": "中盤",
        "yose": "終盤",
    },
    "en": {
        "opening": "opening",
        "middle": "middle game",
        "yose": "endgame",
    },
}

# Localized section headers
SECTION_HEADERS: Dict[str, Dict[str, str]] = {
    "jp": {
        "practice_priorities": "## 練習の優先順位",
        "games_included": "## 含まれる対局",
        "skill_profile": "## スキルプロファイル",
        "weak_areas": "**弱点エリア (< 2.5)**",
        "practice_label": "**練習の優先順位:**",
    },
    "en": {
        "practice_priorities": "## Practice Priorities",
        "games_included": "## Games Included",
        "skill_profile": "## Skill Profile",
        "weak_areas": "**Weak areas (< 2.5)**",
        "practice_label": "**Practice priorities:**",
    },
}
