# katrain/gui/features/karte_export.py
#
# カルテエクスポート機能モジュール
#
# __main__.py から抽出したカルテ関連の関数を配置します。
# Pure関数（状態に依存しない関数）を優先して抽出し、
# UI依存の関数は後続PRで追加します。

import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from katrain.core.game import Game


def determine_user_color(game: "Game", username: str) -> Optional[str]:
    """Determine user's color based on player names in SGF.

    Args:
        game: Game instance containing SGF root properties
        username: Username to match against player names

    Returns:
        "B" for black, "W" for white, None if no match or ambiguous

    Example:
        >>> color = determine_user_color(game, "sentoku")
        >>> if color == "B":
        ...     print("User played as Black")
    """
    if not username or not game:
        return None

    def normalize_name(name: Optional[str]) -> str:
        """Normalize player name for matching.

        Removes non-alphanumeric characters and converts to lowercase.
        """
        if not name:
            return ""
        return re.sub(r"[^0-9a-z]+", "", str(name).casefold())

    pb = game.root.get_property("PB", None)
    pw = game.root.get_property("PW", None)

    user_norm = normalize_name(username)
    pb_norm = normalize_name(pb)
    pw_norm = normalize_name(pw)

    match_black = pb_norm and user_norm in pb_norm
    match_white = pw_norm and user_norm in pw_norm

    if match_black and not match_white:
        return "B"
    elif match_white and not match_black:
        return "W"
    else:
        # Ambiguous or no match
        return None
