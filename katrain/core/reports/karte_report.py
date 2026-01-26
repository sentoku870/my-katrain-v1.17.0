"""Karte report generation.

PR #119: Phase B2 - karte_report.py抽出

game.pyから抽出されたカルテ（Karte）生成機能。
- build_karte_report: カルテレポート生成のエントリポイント
- _build_karte_report_impl: 実装本体
- _build_error_karte: エラー時のフォールバック

このモジュールはkatrain.guiをインポートしない（core層のみ）。

Note:
    現在の実装はGameオブジェクト全体を受け取ります。
    将来的にはProtocolベースのインターフェースに移行予定。
"""

import logging
import os
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

from katrain.core import eval_metrics
from katrain.core.lang import i18n
from katrain.core.analysis.models import (
    EngineType,
    EvalSnapshot,
    MistakeCategory,
    MoveEval,
)
from katrain.core.analysis.logic_loss import detect_engine_type
from katrain.core.analysis.meaning_tags import (
    ClassificationContext,
    classify_meaning_tag,
    get_meaning_tag_label_safe,
)
from katrain.core.analysis.presentation import format_loss_label, get_auto_confidence_label
from katrain.core.batch.helpers import format_wr_gap
from katrain.core.constants import OUTPUT_DEBUG
from katrain.core.eval_metrics import (
    aggregate_phase_mistake_stats,
    classify_game_phase,
    classify_mistake,
    detect_mistake_streaks,
    get_canonical_loss_from_move,
    get_practice_priorities_from_stats,
)
from katrain.core.analysis.critical_moves import CriticalMove, select_critical_moves
from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.analysis.skill_radar import compute_radar_from_moves
from katrain.core.analysis.style import StyleResult, determine_style
from katrain.core.analysis.time import (
    parse_time_data,
    analyze_pacing,
    get_pacing_icon,
    PacingMetrics,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions for Leela/KataGo engine-aware loss display (Phase 35)
# ---------------------------------------------------------------------------


def has_loss_data(mv: MoveEval) -> bool:
    """MoveEval に損失データが存在するか判定。

    Returns:
        True: score_loss, leela_loss_est, points_lost のいずれかが設定されている
        False: すべて None（解析データなし）

    Note:
        0.0 は有効な損失値（完璧な手）として True を返す。
        これにより「データなし」と「真の 0.0 損失」を区別できる。
    """
    return (
        mv.score_loss is not None
        or mv.leela_loss_est is not None
        or mv.points_lost is not None
    )


def format_loss_with_engine_suffix(
    loss_val: Optional[float],
    engine_type: EngineType,
) -> str:
    """損失値をフォーマット。Leelaは(推定)サフィックス付き。

    既存 fmt_float 完全互換: 符号なし、単位なし
    - None: "unknown"
    - KataGo/UNKNOWN: "6.0"
    - Leela: "6.0(推定)"

    Args:
        loss_val: 損失値（None は未解析）
        engine_type: エンジン種別

    Returns:
        フォーマット済み文字列

    Note:
        0.0 は有効な損失値（完璧な手）として "0.0" を返す。
        データなし（None）のみ "unknown" を返す。
    """
    if loss_val is None:
        return "unknown"
    base = f"{loss_val:.1f}"  # fmt_float と同一フォーマット
    if engine_type == EngineType.LEELA:
        return f"{base}(推定)"
    return base


class KarteGenerationError(Exception):
    """Exception raised when karte generation fails.

    Attributes:
        game_id: Identifier of the game being processed
        focus_player: Player filter if any ("B", "W", or None)
        context: Additional context about where the error occurred
        original_error: The underlying exception that caused this error
    """

    def __init__(
        self,
        message: str,
        game_id: str = "",
        focus_player: Optional[str] = None,
        context: str = "",
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.game_id = game_id
        self.focus_player = focus_player
        self.context = context
        self.original_error = original_error

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.game_id:
            parts.append(f"game_id={self.game_id}")
        if self.focus_player:
            parts.append(f"focus_player={self.focus_player}")
        if self.context:
            parts.append(f"context={self.context}")
        return " | ".join(parts)


class MixedEngineSnapshotError(ValueError):
    """Mixed-engine snapshot detection exception.

    Raised by build_karte_report() when raise_on_error=True and the snapshot
    contains analysis data from both KataGo and Leela engines.

    This is a dedicated exception to avoid catching unrelated ValueErrors.
    """

    pass


# Error code constants for stable test assertions
KARTE_ERROR_CODE_MIXED_ENGINE = "KARTE_ERROR_CODE: MIXED_ENGINE"
KARTE_ERROR_CODE_GENERATION_FAILED = "KARTE_ERROR_CODE: GENERATION_FAILED"

# Style confidence threshold (Phase 66)
# Below this threshold, style name is shown as "Unknown" and 勝負術 section is hidden
STYLE_CONFIDENCE_THRESHOLD = 0.2


def is_single_engine_snapshot(snapshot: EvalSnapshot) -> bool:
    """Check if snapshot contains data from only one engine type.

    Args:
        snapshot: EvalSnapshot to validate

    Returns:
        True if all moves are from a single engine (or no analysis data).
        False if both KataGo and Leela data exist in the same snapshot.

    Allowed patterns:
        - All moves have score_loss (KataGo) -> OK
        - All moves have leela_loss_est (Leela) -> OK
        - All moves have no loss data (unanalyzed) -> OK
        - Some moves analyzed, some not (partial) -> OK
        - At least one KataGo + at least one Leela -> NG (returns False)
    """
    has_katago = any(m.score_loss is not None for m in snapshot.moves)
    has_leela = any(m.leela_loss_est is not None for m in snapshot.moves)
    return not (has_katago and has_leela)


def build_karte_report(
    game: Any,  # Game object (Protocol in future)
    level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
    player_filter: Optional[str] = None,
    raise_on_error: bool = False,
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    target_visits: Optional[int] = None,
) -> str:
    """Build a compact, markdown-friendly report for the current game.

    Args:
        game: Game object providing game state and analysis data
        level: Important move level setting
        player_filter: Filter by player ("B", "W", or None for both)
                      Can also be a username string to match against player names
        raise_on_error: If True, raise exceptions on failure.
                       If False (default), return error markdown instead.
        skill_preset: Skill preset for strictness ("auto" or one of SKILL_PRESETS keys)
        target_visits: Target visits for effective reliability threshold calculation.
            If None, uses the hardcoded RELIABILITY_VISITS_THRESHOLD (200).

    Returns:
        Markdown-formatted karte report.
        On error with raise_on_error=False, returns a report with ERROR section.

    Raises:
        MixedEngineSnapshotError: If raise_on_error=True and snapshot contains
            both KataGo and Leela analysis data.
        KarteGenerationError: If raise_on_error=True and generation fails
            for other reasons.
    """
    game_id = game.game_id or game.sgf_filename or "unknown"

    try:
        # 1. Compute snapshot once (avoid double computation)
        snapshot = game.build_eval_snapshot()

        # 2. Mixed-engine check (Phase 37: enforcement point)
        if not is_single_engine_snapshot(snapshot):
            error_msg = (
                f"{KARTE_ERROR_CODE_MIXED_ENGINE}\n"
                "Mixed-engine analysis detected. "
                "KataGo and Leela data cannot be combined in a single karte."
            )
            if raise_on_error:
                raise MixedEngineSnapshotError(error_msg)
            return _build_error_karte(game_id, player_filter, error_msg)

        # 3. Pass snapshot as argument (avoid recomputation in impl)
        # Phase 44: Pass target_visits for consistent reliability threshold
        return _build_karte_report_impl(
            game, snapshot, level, player_filter, skill_preset, target_visits=target_visits
        )

    except MixedEngineSnapshotError:
        # Re-raise dedicated exception (explicitly requested)
        raise

    except Exception as e:
        error_msg = (
            f"{KARTE_ERROR_CODE_GENERATION_FAILED}\n"
            f"Failed to generate karte: {type(e).__name__}: {e}"
        )
        if game.katrain:
            game.katrain.log(error_msg, OUTPUT_DEBUG)

        if raise_on_error:
            raise KarteGenerationError(
                message=error_msg,
                game_id=game_id,
                focus_player=player_filter,
                context="build_karte_report",
                original_error=e,
            ) from e

        # Return error markdown instead of crashing
        return _build_error_karte(game_id, player_filter, error_msg)


def _build_error_karte(
    game_id: str,
    player_filter: Optional[str],
    error_msg: str,
) -> str:
    """Build a minimal karte with ERROR section when generation fails."""
    sections = [
        "# Karte (ERROR)",
        "",
        "## Meta",
        f"- Game: {game_id}",
        f"- Player Filter: {player_filter or 'both'}",
        "",
        "## ERROR",
        "",
        "Karte generation failed with the following error:",
        "",
        f"```",
        error_msg,
        f"```",
        "",
        "Please check:",
        "- The game has been analyzed (KT property present)",
        "- The SGF file is not corrupted",
        "- KataGo engine is running correctly",
        "",
    ]
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Style Archetype helpers (Phase 57)
# ---------------------------------------------------------------------------


def _build_tag_counts_from_moves(
    moves: List["MoveEval"],
    player: Optional[str]
) -> Dict[MeaningTagId, int]:
    """Build MeaningTagId counts from cached meaning_tag_id field."""
    filtered = [m for m in moves if player is None or m.player == player]
    tag_ids = [m.meaning_tag_id for m in filtered if m.meaning_tag_id is not None]

    valid_tags: List[MeaningTagId] = []
    for tid in tag_ids:
        try:
            valid_tags.append(MeaningTagId(tid))
        except ValueError:
            continue
    return dict(Counter(valid_tags))


def _compute_style_safe(
    moves: List["MoveEval"],
    player: Optional[str]
) -> Optional[StyleResult]:
    """Compute style with graceful fallback on error."""
    try:
        radar = compute_radar_from_moves(moves, player=player)
        tag_counts = _build_tag_counts_from_moves(moves, player)
        return determine_style(radar, tag_counts)
    except Exception:
        logger.debug("Style computation failed", exc_info=True)
        return None


def _build_karte_report_impl(
    game: Any,  # Game object
    snapshot: EvalSnapshot,  # Pre-computed snapshot (avoid double computation)
    level: str,
    player_filter: Optional[str],
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    target_visits: Optional[int] = None,
    lang: str = "ja",
) -> str:
    """Internal implementation of build_karte_report.

    Args:
        game: Game object providing game state
        snapshot: Pre-computed EvalSnapshot (passed from build_karte_report)
        level: Important move level setting
        player_filter: Filter by player ("B", "W", or None for both)
        skill_preset: Skill preset for strictness
        target_visits: Target visits for effective reliability threshold calculation.
            If None, uses the hardcoded RELIABILITY_VISITS_THRESHOLD (200).
        lang: Language code for localized labels ("ja" or "en"), defaults to "ja".

    Note:
        snapshot is now passed as an argument rather than computed here.
        This avoids double computation since build_karte_report() already
        computes the snapshot for mixed-engine validation.
    """
    thresholds = game.katrain.config("trainer/eval_thresholds") if game.katrain else []

    # PR#1: Compute confidence level for section gating
    confidence_level = eval_metrics.compute_confidence_level(snapshot.moves)
    settings = eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
        level, eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL]
    )

    # Phase 60: Build pacing map for Time column
    pacing_map: Optional[Dict[int, PacingMetrics]] = None
    try:
        time_data = parse_time_data(game.root)
        if time_data.has_time_data:
            pacing_result = analyze_pacing(time_data, list(snapshot.moves))
            pacing_map = {m.move_number: m for m in pacing_result.pacing_metrics}
    except Exception as e:
        logger.debug(f"Time analysis failed: {e}")
        # pacing_map remains None → all Time columns show "-"

    def fmt_val(val, default="unknown"):
        return default if val in [None, ""] else str(val)

    def fmt_float(val):
        return "unknown" if val is None else f"{val:.1f}"

    def normalize_name(name: Optional[str]) -> str:
        if not name:
            return ""
        return re.sub(r"[^0-9a-z]+", "", str(name).casefold())

    def read_aliases(value) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if v]
        if isinstance(value, str):
            return [v.strip() for v in re.split(r"[;,]", value) if v.strip()]
        return []

    # Meta
    board_x, board_y = game.board_size
    filename = os.path.splitext(os.path.basename(game.sgf_filename or ""))[0] or fmt_val(
        game.root.get_property("GN", None), default=game.game_id
    )
    meta_lines = [
        f"- Board: {board_x}x{board_y}",
        f"- Komi: {fmt_val(game.komi)}",
        f"- Rules: {fmt_val(game.rules)}",
        f"- Handicap: {fmt_val(getattr(game.root, 'handicap', None), default='none')}",
        f"- Game: {filename}",
        f"- Date: {fmt_val(game.root.get_property('DT', None), default=game.game_id)}",
    ]

    pb = fmt_val(game.root.get_property("PB", None))
    pw = fmt_val(game.root.get_property("PW", None))
    br = game.root.get_property("BR", None)
    wr = game.root.get_property("WR", None)
    players_lines = [
        f"- Black: {pb}" + (f" ({br})" if br else ""),
        f"- White: {pw}" + (f" ({wr})" if wr else ""),
    ]

    focus_color = None
    if game.katrain:
        focus_name = game.katrain.config("general/my_player_name")
        focus_aliases = read_aliases(game.katrain.config("general/my_player_aliases"))
        focus_names = [n for n in [focus_name, *focus_aliases] if n]
        if focus_names:
            focus_tokens = {normalize_name(n) for n in focus_names if normalize_name(n)}
            pb_norm = normalize_name(pb)
            pw_norm = normalize_name(pw)
            match_black = pb_norm and any(n in pb_norm for n in focus_tokens)
            match_white = pw_norm and any(n in pw_norm for n in focus_tokens)
            if match_black != match_white:
                focus_color = "B" if match_black else "W"

    # Phase 3: Process player_filter parameter
    # If player_filter is a username string, convert to "B" or "W"
    filtered_player = None
    if player_filter:
        if player_filter in ("B", "W"):
            filtered_player = player_filter
        else:
            # Try to match against player names
            user_norm = normalize_name(player_filter)
            pb_norm = normalize_name(pb)
            pw_norm = normalize_name(pw)
            match_black = pb_norm and user_norm in pb_norm
            match_white = pw_norm and user_norm in pw_norm
            if match_black and not match_white:
                filtered_player = "B"
            elif match_white and not match_black:
                filtered_player = "W"
            # If both or neither match, filtered_player stays None (show both)

    # Style Archetype (Phase 57, confidence gating added Phase 66)
    style_result = _compute_style_safe(snapshot.moves, filtered_player)
    if style_result is not None:
        confidence = style_result.confidence
        if confidence >= STYLE_CONFIDENCE_THRESHOLD:
            style_name = i18n._(style_result.archetype.name_key)
            meta_lines.append(f"- Style: {style_name}")
            meta_lines.append(f"- Style Confidence: {confidence:.0%}")
        else:
            # Low confidence: show "Unknown" with data insufficiency note
            unknown_label = i18n._("style:unknown")
            insufficient_label = i18n._("style:insufficient_data")
            meta_lines.append(f"- Style: {unknown_label}")
            meta_lines.append(f"- Style Confidence: {confidence:.0%} ({insufficient_label})")
    else:
        # style_result is None (computation failed)
        unknown_label = i18n._("style:unknown")
        meta_lines.append(f"- Style: {unknown_label}")

    def worst_move_for(player: str) -> Optional[MoveEval]:
        """worst move を canonical loss で選択（KataGo/Leela 両対応）。"""
        player_moves = [mv for mv in snapshot.moves if mv.player == player]
        # 損失データが存在する手のみ対象（0.0 も含む、データなしは除外）
        moves_with_data = [mv for mv in player_moves if has_loss_data(mv)]
        if not moves_with_data:
            return None
        return max(moves_with_data, key=get_canonical_loss_from_move)

    def mistake_label_from_loss(loss_val: Optional[float], thresholds: Tuple[float, float, float]) -> str:
        """Classify a loss value using the centralized classify_mistake function with given thresholds."""
        if loss_val is None:
            return "unknown"
        # Use classify_mistake with explicit thresholds for consistency with Definitions section
        category = classify_mistake(score_loss=loss_val, winrate_loss=None, score_thresholds=thresholds)
        return category.value

    def summary_lines_for(player: str) -> List[str]:
        player_moves = [mv for mv in snapshot.moves if mv.player == player]
        total_lost = sum(max(0.0, mv.points_lost) for mv in player_moves if mv.points_lost is not None)
        worst = worst_move_for(player)
        if worst:
            worst_loss = get_canonical_loss_from_move(worst)
            worst_engine = detect_engine_type(worst)
            worst_display = (
                f"#{worst.move_number} {worst.player or '-'} {worst.gtp or '-'} "
                f"loss {format_loss_with_engine_suffix(worst_loss, worst_engine)} "
                f"({mistake_label_from_loss(worst_loss, effective_thresholds)})"
            )
        else:
            worst_display = "unknown"
        return [
            f"- Moves analyzed: {len(player_moves)}",
            f"- Total points lost: {fmt_float(total_lost)}",
            f"- Worst move: {worst_display}",
        ]

    def opponent_summary_for(focus_player: str) -> List[str]:
        """相手プレイヤーのサマリーを生成（Phase 4: 相手情報追加）"""
        opponent = "W" if focus_player == "B" else "B"
        opponent_moves = [mv for mv in snapshot.moves if mv.player == opponent]
        if not opponent_moves:
            return []
        total_lost = sum(max(0.0, mv.points_lost) for mv in opponent_moves if mv.points_lost is not None)
        worst = worst_move_for(opponent)
        opponent_name = pw if opponent == "W" else pb
        if worst:
            worst_loss = get_canonical_loss_from_move(worst)
            worst_engine = detect_engine_type(worst)
            worst_display = (
                f"#{worst.move_number} {worst.player or '-'} {worst.gtp or '-'} "
                f"loss {format_loss_with_engine_suffix(worst_loss, worst_engine)} "
                f"({mistake_label_from_loss(worst_loss, effective_thresholds)})"
            )
        else:
            worst_display = "unknown"
        return [
            f"## Opponent Summary ({opponent_name})",
            f"- Moves analyzed: {len(opponent_moves)}",
            f"- Total points lost: {fmt_float(total_lost)}",
            f"- Worst move: {worst_display}",
            ""
        ]

    def common_difficult_positions() -> List[str]:
        """両者とも損失が大きい局面を検出（Phase 4: 共通困難局面）"""
        # 連続する手（手番交代）で両者とも損失が大きい箇所を検出
        difficult = []
        moves_list = list(snapshot.moves)
        for i in range(len(moves_list) - 1):
            mv = moves_list[i]
            next_mv = moves_list[i + 1]
            # 両者の損失がそれぞれ2目以上
            if (mv.points_lost is not None and mv.points_lost >= 2.0 and
                next_mv.points_lost is not None and next_mv.points_lost >= 2.0):
                # 手番が交代していることを確認
                if mv.player != next_mv.player:
                    total = mv.points_lost + next_mv.points_lost
                    # 黒/白の損失を正しく割り当て
                    if mv.player == "B":
                        b_loss, w_loss = mv.points_lost, next_mv.points_lost
                    else:
                        b_loss, w_loss = next_mv.points_lost, mv.points_lost
                    difficult.append((mv.move_number, b_loss, w_loss, total))

        if not difficult:
            return []

        difficult.sort(key=lambda x: x[3], reverse=True)
        lines = ["## Common Difficult Positions", ""]
        lines.append("Both players made significant errors (2+ points) in consecutive moves:")
        lines.append("")
        lines.append("| Move # | Black Loss | White Loss | Total Loss |")
        lines.append("|--------|------------|------------|------------|")
        for move_num, b_loss, w_loss, total in difficult[:5]:
            lines.append(f"| {move_num}-{move_num+1} | {b_loss:.1f} | {w_loss:.1f} | {total:.1f} |")
        lines.append("")
        return lines

    # Distributions using existing report helper if thresholds are available
    histogram = None
    if thresholds:
        try:
            from katrain.core import ai as ai_module

            _sum_stats, histogram, _ptloss = ai_module.game_report(game, thresholds=thresholds, depth_filter=None)

            def bucket_label(bucket_idx: int) -> str:
                cls_idx = len(thresholds) - 1 - bucket_idx
                if cls_idx == 0:
                    return f">= {thresholds[0]}"
                if cls_idx == len(thresholds) - 1:
                    return f"< {thresholds[-2]}"
                upper = thresholds[cls_idx - 1]
                lower = thresholds[cls_idx]
                return f"{lower} - {upper}"
        except Exception as exc:  # pragma: no cover - defensive fallback
            game.katrain.log(f"Failed to build histogram for Karte export: {exc}", OUTPUT_DEBUG)
            histogram = None

    def distribution_lines_for(player: str) -> List[str]:
        if histogram is None:
            return ["- Mistake buckets: unknown"]
        lines = ["- Mistake buckets (points lost):"]
        for idx, bucket in enumerate(histogram):
            label = bucket_label(idx)
            lines.append(f"  - {label}: {bucket[player]}")
        # Removed: "Freedom buckets: unknown" (Phase 8: always unknown, no value for LLM)
        return lines

    # Important moves table (top N derived from existing settings)
    important_moves = game.get_important_move_evals(level=level)

    # Phase 47: Classify meaning tags for each important move
    # MoveEval objects are recreated on each get_important_move_evals() call,
    # so we must classify here (not rely on stats.py assignment)
    total_moves = len(snapshot.moves)
    classification_context = ClassificationContext(total_moves=total_moves)
    for mv in important_moves:
        if mv.meaning_tag_id is None:
            meaning_tag = classify_meaning_tag(mv, context=classification_context)
            mv.meaning_tag_id = meaning_tag.id.value

    # Phase 2: コンテキスト情報（候補手数・最善手差・危険度・最善手）を取得
    def get_context_info_for_move(move_eval) -> dict:
        """MoveEval から候補手数・最善手差・危険度・最善手を取得

        CRITICAL FIX: Best move and candidates are now extracted from the PRE-MOVE node
        (node.parent), not the post-move node. This ensures we see the candidate moves
        that were available BEFORE the move was played.

        Returns:
            {
                "candidates": int or None,
                "best_gap": float or None (0.0-1.0),
                "danger": str or None ("High"/"Mid"/"Low"),
                "best_move": str or None (GTP format, e.g., "Q16")
            }
        """
        context = {
            "candidates": None,
            "best_gap": None,
            "danger": None,
            "best_move": None,
        }

        try:
            node = game._find_node_by_move_number(move_eval.move_number)
            if not node:
                return context

            # CRITICAL: Use parent node for candidate moves (PRE-MOVE position)
            # This is the position BEFORE the move was played, which contains
            # the candidate moves that were available to the player.
            parent_node = getattr(node, "parent", None)

            if parent_node and hasattr(parent_node, 'candidate_moves'):
                candidate_moves = parent_node.candidate_moves
                if candidate_moves:
                    context["candidates"] = len(candidate_moves)

                    # Best move is the first candidate (order=0)
                    if candidate_moves:
                        best_candidate = candidate_moves[0]
                        context["best_move"] = best_candidate.get("move")

                    # Best gap: find the played move in parent's candidates
                    actual_move_gtp = move_eval.gtp
                    if actual_move_gtp:
                        for candidate in candidate_moves:
                            if candidate.get("move") == actual_move_gtp:
                                # Use scoreLost or winrateLost if available
                                score_lost = candidate.get("scoreLost")
                                winrate_lost = candidate.get("winrateLost")
                                if winrate_lost is not None:
                                    context["best_gap"] = winrate_lost
                                break

            # 危険度（board_analysis から）- uses current node for danger assessment
            from katrain.core import board_analysis
            board_state = board_analysis.analyze_board_at_node(game, node)

            # プレイヤーのグループの最大危険度
            player = move_eval.player
            if player:
                my_groups = [g for g in board_state.groups if g.color == player]
                if my_groups:
                    max_danger = max(
                        (board_state.danger_scores.get(g.group_id, 0) for g in my_groups),
                        default=0
                    )

                    if max_danger >= 50:
                        context["danger"] = "High"
                    elif max_danger >= 25:
                        context["danger"] = "Mid"
                    else:
                        context["danger"] = "Low"

        except Exception as e:
            # エラー時は None のまま
            if game.katrain:
                game.katrain.log(f"Failed to get context info for move #{move_eval.move_number}: {e}", OUTPUT_DEBUG)

        return context

    def important_lines_for(player: str, label: str) -> List[str]:
        # PR#1: Confidence gating for important moves count
        confidence_limit = eval_metrics.get_important_moves_limit(confidence_level)
        max_count = min(settings.max_moves, confidence_limit)
        player_moves = [mv for mv in important_moves if mv.player == player][:max_count]

        # PR#1: Add "(候補)" suffix for LOW confidence
        title_suffix = " (候補)" if confidence_level == eval_metrics.ConfidenceLevel.LOW else ""
        lines = [f"## Important Moves ({label}){title_suffix} Top {len(player_moves) or max_count}"]
        if player_moves:
            # Added "Best" column for best move from PRE-MOVE node
            # Phase 47: Added "MTag" column for meaning tag
            # Phase 53: Renamed "Best Gap" to "WR Gap" with improved formatting
            # Phase 60: Added "Time" column for pacing icons
            lines.append("| # | Time | P | Coord | Loss | Best | Candidates | WR Gap | Danger | Mistake | MTag | Reason |")
            lines.append("|---|------|---|-------|------|------|------------|----------|--------|---------|------|--------|")
            for mv in player_moves:
                # canonical loss を使用（常に >= 0）
                loss = get_canonical_loss_from_move(mv)
                mistake = mistake_label_from_loss(loss, effective_thresholds)
                reason_str = ", ".join(mv.reason_tags) if mv.reason_tags else "-"

                # Phase 47: Get meaning tag label
                meaning_tag_label = get_meaning_tag_label_safe(mv.meaning_tag_id, lang) or "-"

                # コンテキスト情報を取得 (now includes best_move from PRE-MOVE node)
                context = get_context_info_for_move(mv)
                best_move_str = context["best_move"] or "-"
                candidates_str = str(context["candidates"]) if context["candidates"] is not None else "-"
                # Phase 53: Use format_wr_gap for consistent formatting with clamping
                wr_gap_str = format_wr_gap(context["best_gap"])
                danger_str = context["danger"] or "-"

                # Phase 60: Get pacing icon
                pacing_metrics = pacing_map.get(mv.move_number) if pacing_map else None
                time_icon = get_pacing_icon(pacing_metrics)

                # Leela データには (推定) サフィックスを付加
                loss_display = format_loss_with_engine_suffix(loss, detect_engine_type(mv))
                lines.append(
                    f"| {mv.move_number} | {time_icon} | {mv.player or '-'} | {mv.gtp or '-'} | "
                    f"{loss_display} | {best_move_str} | {candidates_str} | {wr_gap_str} | {danger_str} | "
                    f"{mistake} | {meaning_tag_label} | {reason_str} |"
                )
        else:
            lines.append("- No important moves found.")
        return lines

    def reason_tags_distribution_for(player: str, label: str) -> List[str]:
        """Phase 12: 理由タグ分布を生成（1局カルテ用）"""
        player_moves = [mv for mv in important_moves if mv.player == player]

        # タグをカウント
        reason_tags_counts = {}
        for mv in player_moves:
            for tag in mv.reason_tags:
                reason_tags_counts[tag] = reason_tags_counts.get(tag, 0) + 1

        lines = [f"## Reason Tags Distribution ({label})"]
        if reason_tags_counts:
            # カウント降順でソート
            sorted_tags = sorted(
                reason_tags_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )

            lines.append("")
            for tag, count in sorted_tags:
                label_text = eval_metrics.REASON_TAG_LABELS.get(tag, tag)
                lines.append(f"- {label_text}: {count}")
        else:
            lines.append("")
            lines.append("- No reason tags detected.")

        lines.append("")
        return lines

    def _critical_3_section_for(player: str, label: str) -> List[str]:
        """Generate Critical 3 section for focused review (Phase 50).

        Selects top 3 critical mistakes using weighted scoring with
        MeaningTag weights and diversity penalty.

        Args:
            player: "B" or "W"
            label: Display label (e.g., "Black", "White", "Focus")

        Returns:
            List of lines for the Critical 3 section (empty if no critical moves)
        """
        try:
            critical_moves = select_critical_moves(
                game,
                max_moves=3,
                lang=lang,
                level=level,
            )
        except Exception as exc:
            if game.katrain:
                game.katrain.log(f"Failed to compute Critical 3: {exc}", OUTPUT_DEBUG)
            return []

        # Filter by player
        player_critical = [cm for cm in critical_moves if cm.player == player]
        if not player_critical:
            return []

        unit = "目" if lang == "ja" else " pts"
        intro = (
            "最も重要なミス（重点復習用）:"
            if lang == "ja"
            else "Most impactful mistakes for focused review:"
        )

        lines = [f"## Critical 3 ({label})", ""]
        lines.append(intro)
        lines.append("")

        for i, cm in enumerate(player_critical, 1):
            lines.append(f"### {i}. Move #{cm.move_number} ({cm.player}) {cm.gtp_coord}")
            lines.append(f"- **Loss**: {cm.score_loss:.1f}{unit}")
            lines.append(f"- **Type**: {cm.meaning_tag_label}")
            lines.append(f"- **Phase**: {cm.game_phase}")
            lines.append(f"- **Difficulty**: {cm.position_difficulty.upper()}")
            if cm.reason_tags:
                lines.append(f"- **Context**: {', '.join(cm.reason_tags)}")
            else:
                lines.append("- **Context**: (none)")
            lines.append("")

        return lines

    focus_label = "Focus"

    # Compute auto recommendation if skill_preset is "auto"
    auto_recommendation: Optional[eval_metrics.AutoRecommendation] = None
    effective_preset = skill_preset
    if skill_preset == "auto":
        # Use focus_color if available, otherwise use all moves
        if focus_color:
            focus_moves = [m for m in snapshot.moves if m.player == focus_color]
        else:
            focus_moves = list(snapshot.moves)
        auto_recommendation = eval_metrics.recommend_auto_strictness(focus_moves, game_count=1)
        effective_preset = auto_recommendation.recommended_preset

    # Get effective thresholds for classification (used by mistake_label_from_loss and other helpers)
    effective_thresholds = eval_metrics.get_skill_preset(effective_preset).score_thresholds

    # Build Definitions section (uses SKILL_PRESETS thresholds based on effective preset)
    def definitions_section() -> List[str]:
        """Build the Definitions section with thresholds from SKILL_PRESETS."""
        preset = eval_metrics.SKILL_PRESETS.get(effective_preset, eval_metrics.SKILL_PRESETS[eval_metrics.DEFAULT_SKILL_PRESET])
        t1, t2, t3 = preset.score_thresholds

        # Get phase thresholds for this board size
        opening_end, middle_end = eval_metrics.get_phase_thresholds(board_x)

        # Get JP labels
        preset_labels = eval_metrics.SKILL_PRESET_LABELS
        conf_labels = eval_metrics.CONFIDENCE_LABELS

        # Build strictness info line with JP labels
        # Phase 53: Use get_auto_confidence_label for auto-strictness (推定確度, not 信頼度)
        if skill_preset == "auto" and auto_recommendation:
            preset_jp = preset_labels.get(auto_recommendation.recommended_preset, auto_recommendation.recommended_preset)
            conf_label = get_auto_confidence_label(auto_recommendation.confidence.value)
            strictness_info = (
                f"自動 → {preset_jp} "
                f"({conf_label}, "
                f"ブランダー={auto_recommendation.blunder_count}, 重要={auto_recommendation.important_count})"
            )
        else:
            preset_jp = preset_labels.get(effective_preset, effective_preset)
            strictness_info = f"{preset_jp} (手動)"

        lines = [
            "## Definitions",
            "",
            f"- Strictness: {strictness_info}",
        ]

        # Add auto hint for manual mode
        if skill_preset != "auto":
            # Compute auto recommendation for hint
            if focus_color:
                hint_moves = [m for m in snapshot.moves if m.player == focus_color]
            else:
                hint_moves = list(snapshot.moves)
            hint_rec = eval_metrics.recommend_auto_strictness(hint_moves, game_count=1)
            hint_preset_jp = preset_labels.get(hint_rec.recommended_preset, hint_rec.recommended_preset)
            hint_conf_label = get_auto_confidence_label(hint_rec.confidence.value)
            lines.append(f"- Auto recommended: {hint_preset_jp} ({hint_conf_label})")

        # Phase 54: Localized definitions
        if lang == "ja":
            lines.extend([
                "",
                "| 指標 | 定義 |",
                "|------|------|",
                "| 目数損失 | 実際の手と最善手との目数差（0以上にクランプ） |",
                "| WR Gap | 勝率変化（着手前→着手後）。大きな目数損でも勝率変化が小さい場合あり |",
                f"| Good | 損失 < {t1:.1f}目 |",
                f"| Inaccuracy | 損失 {t1:.1f} - {t2:.1f}目 |",
                f"| Mistake | 損失 {t2:.1f} - {t3:.1f}目 |",
                f"| Blunder | 損失 ≥ {t3:.1f}目 |",
                f"| Phase ({board_x}x{board_y}) | 序盤: <{opening_end}手, 中盤: {opening_end}-{middle_end-1}手, 終盤: ≥{middle_end}手 |",
                "",
            ])
        else:
            lines.extend([
                "",
                "| Metric | Definition |",
                "|--------|------------|",
                "| Points Lost | Score difference between actual move and best move (clamped to ≥0) |",
                "| WR Gap | Winrate change (before → after move). Large point loss may have small WR change |",
                f"| Good | Loss < {t1:.1f} pts |",
                f"| Inaccuracy | Loss {t1:.1f} - {t2:.1f} pts |",
                f"| Mistake | Loss {t2:.1f} - {t3:.1f} pts |",
                f"| Blunder | Loss ≥ {t3:.1f} pts |",
                f"| Phase ({board_x}x{board_y}) | Opening: <{opening_end}, Middle: {opening_end}-{middle_end-1}, Endgame: ≥{middle_end} |",
                "",
            ])
        return lines

    # Build Data Quality section (PR#1: confidence level display)
    def data_quality_section() -> List[str]:
        """Build the Data Quality section with reliability statistics."""
        # Phase 44: Pass target_visits for consistent reliability threshold
        rel_stats = eval_metrics.compute_reliability_stats(snapshot.moves, target_visits=target_visits)

        # PR#1: Add confidence level label
        confidence_label = eval_metrics.get_confidence_label(confidence_level, lang=lang)

        lines = [
            "## Data Quality",
            "",
            f"- **{confidence_label}**",  # PR#1: Show confidence level prominently
            f"- Moves analyzed: {rel_stats.total_moves}",
            f"- Coverage: {rel_stats.moves_with_visits} / {rel_stats.total_moves} ({rel_stats.coverage_pct:.1f}%)",  # PR#1: coverage_pct
            f"- Reliable (visits ≥ {rel_stats.effective_threshold}): "
            f"{rel_stats.reliable_count} ({rel_stats.reliability_pct:.1f}%)",
            f"- Low-confidence: {rel_stats.low_confidence_count} ({rel_stats.low_confidence_pct:.1f}%)",
        ]

        if rel_stats.moves_with_visits > 0:
            lines.append(f"- Avg visits: {rel_stats.avg_visits:,.0f}")
            # PR1-2: Add max visits to help users understand the data
            if rel_stats.max_visits > 0:
                lines.append(f"- Max visits: {rel_stats.max_visits:,}")
        if rel_stats.zero_visits_count > 0:
            lines.append(f"- No visits data: {rel_stats.zero_visits_count}")

        # PR#1: LOW confidence warning (replaces old is_low_reliability check)
        if confidence_level == eval_metrics.ConfidenceLevel.LOW:
            lines.append("")
            lines.append("⚠️ 解析訪問数が少ないため、結果が不安定な可能性があります。再解析を推奨します。")
        elif rel_stats.is_low_reliability:
            lines.append("")
            lines.append("⚠ Low analysis reliability (<20%). Results may be unstable.")

        # PR1-2: Add note about measured vs configured values
        lines.append("")
        lines.append("*Visits are measured from KataGo analysis (root_visits).*")

        lines.append("")
        return lines

    # Phase 62: Risk Management section
    def risk_management_section() -> List[str]:
        """Generate Risk Management section.

        Dependencies (via closure from file scope):
            - game: Game instance from enclosing function
            - i18n: Imported at file top (line 24)
            - logger: Defined at file top (line 59)
        """
        try:
            from katrain.core.analysis import analyze_risk
            from katrain.core.reports.sections.risk_section import (
                extract_risk_display_data,
                format_risk_stats,
                get_section_title,
            )
        except ImportError as e:
            logger.warning(f"Risk section import failed: {e}", exc_info=True)
            return []

        try:
            risk_result = analyze_risk(game)
            if not risk_result.contexts:
                return []

            lines = [f"## {get_section_title()}", ""]

            for player, label_key in [("B", "risk:black"), ("W", "risk:white")]:
                data = extract_risk_display_data(risk_result, player)
                if data.has_winning_data or data.has_losing_data:
                    lines.append(f"### {i18n._(label_key)}")
                    lines.extend(format_risk_stats(data, risk_result.fallback_used))
                    lines.append("")

            return lines if len(lines) > 2 else []
        except Exception as e:
            logger.debug(f"Risk section generation failed: {e}", exc_info=True)
            return []

    # Assemble sections
    sections = ["## Meta", *meta_lines, ""]
    sections += ["## Players", *players_lines, ""]
    sections += ["## Notes", "- loss is measured for the player who played the move.", ""]
    sections += definitions_section()
    sections += data_quality_section()
    # Phase 62: Risk Management - only include if style confidence is sufficient (Phase 66)
    if style_result is not None and style_result.confidence >= STYLE_CONFIDENCE_THRESHOLD:
        sections += risk_management_section()

    # Phase 3: Apply player filter to sections
    if filtered_player is None:
        # Show both players (current behavior)
        if focus_color:
            focus_name = "Black" if focus_color == "B" else "White"
            sections += [f"## Summary (Focus: {focus_name})", *summary_lines_for(focus_color), ""]
            # Phase 4: focus_color がある場合、相手サマリーを追加
            sections += opponent_summary_for(focus_color)
        sections += ["## Summary (Black)", *summary_lines_for("B"), ""]
        sections += ["## Summary (White)", *summary_lines_for("W"), ""]
        if focus_color:
            focus_name = "Black" if focus_color == "B" else "White"
            sections += [f"## Distributions (Focus: {focus_name})", *distribution_lines_for(focus_color), ""]
        sections += ["## Distributions (Black)", *distribution_lines_for("B"), ""]
        sections += ["## Distributions (White)", *distribution_lines_for("W"), ""]
        # Phase 4: focus_color がある場合、共通困難局面を追加
        if focus_color:
            sections += common_difficult_positions()
    else:
        # Show only filtered player
        filtered_name = "Black" if filtered_player == "B" else "White"
        # Show focus section only if it matches the filter
        if focus_color and focus_color == filtered_player:
            sections += [f"## Summary (Focus: {filtered_name})", *summary_lines_for(focus_color), ""]
        sections += [f"## Summary ({filtered_name})", *summary_lines_for(filtered_player), ""]
        # Phase 4: 相手サマリーを追加
        sections += opponent_summary_for(filtered_player)
        if focus_color and focus_color == filtered_player:
            sections += [f"## Distributions (Focus: {filtered_name})", *distribution_lines_for(focus_color), ""]
        sections += [f"## Distributions ({filtered_name})", *distribution_lines_for(filtered_player), ""]
        # Phase 4: 共通困難局面を追加
        sections += common_difficult_positions()

    # 弱点仮説セクション（Phase 7で追加、Phase 8で skill_preset 対応、PR#1で confidence gating）
    def weakness_hypothesis_for(player: str, label: str) -> List[str]:
        """単局の弱点仮説を生成（skill_preset の閾値を使用）"""
        player_moves = [mv for mv in snapshot.moves if mv.player == player]
        if not player_moves:
            return [f"## Weakness Hypothesis ({label})", "- No data available.", ""]

        # 盤サイズを取得（board_size は (x, y) タプル）
        board_x, _ = game.board_size

        # skill_preset から閾値を取得（ハードコード排除）
        preset = eval_metrics.get_skill_preset(skill_preset)
        score_thresholds = preset.score_thresholds

        # 共有アグリゲータを使用して Phase × Mistake 集計
        stats = aggregate_phase_mistake_stats(
            player_moves,
            score_thresholds=score_thresholds,
            board_size=board_x,
        )

        # 損失が大きい順にソート（GOOD は除外）
        sorted_combos = sorted(
            [(k, v) for k, v in stats.phase_mistake_loss.items() if k[1] != "GOOD" and v > 0],
            key=lambda x: x[1],
            reverse=True
        )

        phase_names = {"opening": "Opening", "middle": "Middle game", "yose": "Endgame"}
        cat_names_ja = {
            "BLUNDER": "大悪手",
            "MISTAKE": "悪手",
            "INACCURACY": "軽微なミス",
        }

        # PR#1: Confidence-based wording
        is_low_conf = confidence_level == eval_metrics.ConfidenceLevel.LOW
        is_medium_conf = confidence_level == eval_metrics.ConfidenceLevel.MEDIUM

        # PR#1: Add "(※参考情報)" suffix for LOW confidence
        header_suffix = " (※参考情報)" if is_low_conf else ""
        lines = [f"## Weakness Hypothesis ({label}){header_suffix}", ""]

        # PR#2: Get evidence count based on confidence level
        evidence_count = eval_metrics.get_evidence_count(confidence_level)

        if sorted_combos:
            # 上位2つの弱点を抽出
            for i, (key, loss) in enumerate(sorted_combos[:2]):
                phase, category = key
                count = stats.phase_mistake_counts.get(key, 0)

                # PR#2: Select representative moves for this phase/category
                def phase_cat_filter(mv):
                    mv_phase = mv.tag or "unknown"
                    mv_cat = mv.mistake_category.name if mv.mistake_category else "GOOD"
                    return mv_phase == phase and mv_cat == category

                evidence_moves = eval_metrics.select_representative_moves(
                    player_moves,
                    max_count=evidence_count,
                    category_filter=phase_cat_filter,
                )
                evidence_str = eval_metrics.format_evidence_examples(evidence_moves, lang=lang)

                # PR#1: Use hedged wording for MEDIUM/LOW confidence
                if is_low_conf:
                    # LOW: "〜の傾向が見られる"
                    lines.append(
                        f"{i+1}. {phase_names.get(phase, phase)}の{cat_names_ja.get(category, category)}の傾向が見られる "
                        f"({count}回、損失{loss:.1f}目)"
                    )
                elif is_medium_conf:
                    # MEDIUM: "〜の傾向あり"
                    lines.append(
                        f"{i+1}. **{phase_names.get(phase, phase)}の{cat_names_ja.get(category, category)}** 傾向あり "
                        f"({count}回、損失{loss:.1f}目)"
                    )
                else:
                    # HIGH: Assertive wording (original)
                    lines.append(
                        f"{i+1}. **{phase_names.get(phase, phase)}の{cat_names_ja.get(category, category)}** "
                        f"({count}回、損失{loss:.1f}目)"
                    )

                # PR#2: Add evidence examples on next line (indented)
                if evidence_str:
                    lines.append(f"   {evidence_str}")
        else:
            lines.append("- 明確な弱点パターンは検出されませんでした。")

        # PR#1: Add re-analysis recommendation for LOW confidence
        if is_low_conf:
            lines.append("")
            lines.append("⚠️ 解析訪問数が少ないため、visits増で再解析を推奨します。")

        lines.append("")
        return lines

    # Practice Priorities を生成（共有アグリゲータを使用、skill_preset 対応、PR#1で confidence gating）
    def practice_priorities_for(player: str, label: str) -> List[str]:
        """単局の練習優先事項を生成（skill_preset の閾値を使用）"""
        # PR#1: LOW confidence → placeholder only
        if confidence_level == eval_metrics.ConfidenceLevel.LOW:
            return [
                f"## 練習の優先順位 ({label})",
                "",
                "- ※ データ不足のため練習優先度は保留。visits増で再解析を推奨します。",
                "",
            ]

        player_moves = [mv for mv in snapshot.moves if mv.player == player]
        if not player_moves:
            return [f"## 練習の優先順位 ({label})", "- No data available.", ""]

        # 盤サイズを取得（board_size は (x, y) タプル）
        board_x, _ = game.board_size

        # skill_preset から閾値を取得（Weakness Hypothesis と一致させる）
        preset = eval_metrics.get_skill_preset(skill_preset)
        score_thresholds = preset.score_thresholds

        # 共有アグリゲータで Phase × Mistake 統計を計算（盤サイズ + 閾値対応）
        stats = aggregate_phase_mistake_stats(
            player_moves,
            score_thresholds=score_thresholds,
            board_size=board_x,
        )

        # 優先項目を取得
        # PR#1: MEDIUM confidence → shortened version (max 1)
        max_priorities = 1 if confidence_level == eval_metrics.ConfidenceLevel.MEDIUM else 2
        priorities = get_practice_priorities_from_stats(stats, max_priorities=max_priorities)

        lines = [f"## 練習の優先順位 ({label})", ""]
        lines.append("Based on the data above, consider focusing on:")
        lines.append("")
        if priorities:
            # PR#2: For each priority, find the worst move as anchor
            # Priority format is like "Endgameのblunderを減らす" or similar
            # We need to extract phase from the priority text and find worst move
            for i, priority in enumerate(priorities, 1):
                lines.append(f"- {i}. {priority}")

                # PR#2: Try to find anchor move for this priority
                # Extract phase from priority text (Opening/Middle/Endgame/etc.)
                anchor_move = None
                for phase_key, phase_name in [("opening", "Opening"), ("middle", "Middle"), ("yose", "Endgame")]:
                    if phase_name.lower() in priority.lower() or phase_key in priority.lower():
                        # Find worst move in this phase
                        phase_moves = [
                            mv for mv in player_moves
                            if (mv.tag or "unknown") == phase_key and mv.score_loss is not None
                        ]
                        if phase_moves:
                            anchor_move = max(phase_moves, key=lambda m: (m.score_loss or 0, -m.move_number))
                        break

                if anchor_move:
                    loss = get_canonical_loss_from_move(anchor_move)
                    if loss > 0.0:
                        engine_type = detect_engine_type(anchor_move)
                        loss_label = format_loss_label(loss, engine_type, lang=lang)
                        lines.append(f"   (#{anchor_move.move_number} {anchor_move.gtp or '-'} で {loss_label}の損失)")
        else:
            lines.append("- No specific priorities identified. Keep up the good work!")
        lines.append("")
        return lines

    # Mistake Streaks を検出して表示（skill_preset 対応）
    def mistake_streaks_for(player: str, label: str) -> List[str]:
        """同一プレイヤーの連続ミスを検出して表示（skill_preset の閾値を使用）"""
        player_moves = [mv for mv in snapshot.moves if mv.player == player]
        if not player_moves:
            return []

        # skill_preset から閾値を取得（URGENT_MISS_CONFIGS を使用）
        urgent_config = eval_metrics.get_urgent_miss_config(skill_preset)

        # 連続ミスを検出（急場見逃し設定を使用）
        streaks = detect_mistake_streaks(
            player_moves,
            loss_threshold=urgent_config.threshold_loss,
            min_consecutive=urgent_config.min_consecutive,
        )

        if not streaks:
            return []

        lines = [f"## Mistake Streaks ({label})", ""]
        lines.append("Consecutive mistakes by the same player:")
        lines.append("")
        for i, s in enumerate(streaks, 1):
            lines.append(
                f"- **Streak {i}**: moves {s.start_move}-{s.end_move} "
                f"({s.move_count} mistakes, {s.total_loss:.1f} pts lost, avg {s.avg_loss:.1f} pts)"
            )
        lines.append("")
        return lines

    # 急場見逃し検出セクション（Urgent Miss Detection、PR#1で confidence gating）
    def urgent_miss_section_for(player: str, label: str) -> List[str]:
        """急場見逃しの可能性がある連続ミスを検出（URGENT_MISS_CONFIGS を使用）"""
        player_moves = [mv for mv in snapshot.moves if mv.player == player]
        if not player_moves:
            return []

        # skill_preset から閾値を取得
        urgent_config = eval_metrics.get_urgent_miss_config(skill_preset)

        # 連続ミスを検出
        streaks = detect_mistake_streaks(
            player_moves,
            loss_threshold=urgent_config.threshold_loss,
            min_consecutive=urgent_config.min_consecutive,
        )

        if not streaks:
            return []

        # PR#1: Add "※要再解析" annotation for LOW confidence
        is_low_conf = confidence_level == eval_metrics.ConfidenceLevel.LOW
        header_suffix = " (※要再解析)" if is_low_conf else ""
        lines = [f"## Urgent Miss Detection ({label}){header_suffix}", ""]
        lines.append("**Warning**: 以下の連続手は急場見逃しの可能性があります:")
        lines.append("")
        # PR#2: Add Coords column for coordinate sequence
        lines.append("| Move Range | Consecutive | Total Loss | Avg Loss | Coords |")
        lines.append("|------------|-------------|------------|----------|--------|")
        for s in streaks:
            # PR#2: Build coordinate sequence from streak moves
            coords = "→".join(mv.gtp or "-" for mv in s.moves) if s.moves else "-"
            lines.append(
                f"| #{s.start_move}-{s.end_move} | {s.move_count} moves | "
                f"{s.total_loss:.1f} pts | {s.avg_loss:.1f} pts | {coords} |"
            )
        lines.append("")
        return lines

    # Phase 3: Apply player filter to weakness hypothesis and important moves
    if filtered_player is None:
        # Show both players
        if focus_color:
            focus_name = "Black" if focus_color == "B" else "White"
            # Urgent Miss Detection（急場見逃し検出）を先に表示
            sections += urgent_miss_section_for(focus_color, focus_name)
            sections += weakness_hypothesis_for(focus_color, focus_name)
            sections += practice_priorities_for(focus_color, focus_name)
            sections += mistake_streaks_for(focus_color, focus_name)

        if focus_color:
            sections += important_lines_for(focus_color, focus_label)
            sections.append("")
            # Phase 50: Critical 3 (Focus player) - after Important Moves
            sections += _critical_3_section_for(focus_color, focus_label)
            # Phase 12: タグ分布を Focus player に追加
            sections += reason_tags_distribution_for(focus_color, focus_label)
        sections += important_lines_for("B", "Black")
        sections.append("")
        # Phase 50: Critical 3 (Black) - after Important Moves
        sections += _critical_3_section_for("B", "Black")
        # Phase 12: タグ分布を Black に追加
        sections += reason_tags_distribution_for("B", "Black")
        sections += important_lines_for("W", "White")
        sections.append("")
        # Phase 50: Critical 3 (White) - after Important Moves
        sections += _critical_3_section_for("W", "White")
        # Phase 12: タグ分布を White に追加
        sections += reason_tags_distribution_for("W", "White")
    else:
        # Show only filtered player
        filtered_name = "Black" if filtered_player == "B" else "White"
        if focus_color and focus_color == filtered_player:
            # Urgent Miss Detection（急場見逃し検出）を先に表示
            sections += urgent_miss_section_for(focus_color, filtered_name)
            sections += weakness_hypothesis_for(focus_color, filtered_name)
            sections += practice_priorities_for(focus_color, filtered_name)
            sections += mistake_streaks_for(focus_color, filtered_name)

        if focus_color and focus_color == filtered_player:
            sections += important_lines_for(focus_color, focus_label)
            sections.append("")
            # Phase 50: Critical 3 (Focus player) - after Important Moves
            sections += _critical_3_section_for(focus_color, focus_label)
            sections += reason_tags_distribution_for(focus_color, focus_label)
        sections += important_lines_for(filtered_player, filtered_name)
        sections.append("")
        # Phase 50: Critical 3 (filtered player) - after Important Moves
        sections += _critical_3_section_for(filtered_player, filtered_name)
        sections += reason_tags_distribution_for(filtered_player, filtered_name)

    return "\n".join(sections)


# =============================================================================
# JSON export (Phase 23 PR #2)
# =============================================================================


def build_karte_json(
    game: Any,  # Game object (Protocol in future)
    level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
    player_filter: Optional[str] = None,
    skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
    lang: str = "ja",
) -> Dict[str, Any]:
    """Build a JSON-serializable karte structure for LLM consumption.

    Phase 23 PR #2: LLM用JSON出力オプション
    Phase 47: Added meaning_tag to important_moves

    Args:
        game: Game object providing game state and analysis data
        level: Important move level setting
        player_filter: Filter by player ("B", "W", or None for both)
        skill_preset: Skill preset for strictness
        lang: Language code for localized labels ("ja" or "en"), defaults to "ja".

    Returns:
        Dict with schema_version, meta, summary, and important_moves.

    Example output:
        {
            "schema_version": "1.0",
            "meta": {
                "game_name": "game1.sgf",
                "date": "2024-01-15",
                "players": {"black": "Player1", "white": "Player2"},
                "result": "B+5.5",
                "skill_preset": "standard",
                "units": {
                    "points_lost": "目数（着手前評価 - 着手後評価、手番視点で正規化、常に0以上）"
                }
            },
            "summary": {
                "total_moves": 250,
                "total_points_lost": {"black": 15.3, "white": 12.7},
                "mistake_distribution": {
                    "black": {"good": 100, "inaccuracy": 15, "mistake": 5, "blunder": 2},
                    "white": {"good": 105, "inaccuracy": 12, "mistake": 4, "blunder": 1}
                }
            },
            "important_moves": [
                {
                    "move_number": 45,
                    "player": "black",
                    "coords": "D4",
                    "points_lost": 3.2,
                    "importance": 4.5,
                    "reason_tags": ["shape_mistake"],
                    "phase": "middle"
                }
            ]
        }
    """
    snapshot = game.build_eval_snapshot()
    moves = list(snapshot.moves)
    board_x, board_y = game.board_size

    # Get effective preset and thresholds
    effective_preset = skill_preset
    if skill_preset == "auto":
        focus_moves = moves
        auto_rec = eval_metrics.recommend_auto_strictness(focus_moves, game_count=1)
        effective_preset = auto_rec.recommended_preset

    preset = eval_metrics.get_skill_preset(effective_preset)
    score_thresholds = preset.score_thresholds

    # Meta section
    def get_property(prop: str, default: Optional[str] = None) -> Optional[str]:
        val = game.root.get_property(prop, default)
        return val if val not in [None, ""] else default

    game_name = os.path.splitext(os.path.basename(game.sgf_filename or ""))[0]
    if not game_name:
        game_name = get_property("GN") or game.game_id or "unknown"

    meta = {
        "game_name": game_name,
        "date": get_property("DT"),
        "players": {
            "black": get_property("PB", "unknown"),
            "white": get_property("PW", "unknown"),
        },
        "result": get_property("RE"),
        "skill_preset": effective_preset,
        "units": {
            "points_lost": "目数（着手前評価 - 着手後評価、手番視点で正規化、常に0以上）"
        },
    }

    # Summary section
    def compute_summary_for(player: str) -> Tuple[float, Dict[str, int]]:
        player_moves = [m for m in moves if m.player == player]
        total_lost = sum(
            max(0.0, m.points_lost) for m in player_moves if m.points_lost is not None
        )

        # Count by mistake category
        counts = {"good": 0, "inaccuracy": 0, "mistake": 0, "blunder": 0}
        for m in player_moves:
            loss = get_canonical_loss_from_move(m)
            cat = classify_mistake(
                score_loss=loss, winrate_loss=None, score_thresholds=score_thresholds
            )
            key = cat.value.lower()
            if key in counts:
                counts[key] += 1

        return total_lost, counts

    black_lost, black_counts = compute_summary_for("B")
    white_lost, white_counts = compute_summary_for("W")

    summary = {
        "total_moves": len(moves),
        "total_points_lost": {"black": round(black_lost, 1), "white": round(white_lost, 1)},
        "mistake_distribution": {
            "black": black_counts,
            "white": white_counts,
        },
    }

    # Important moves section
    important_move_evals = game.get_important_move_evals(level=level)

    # Phase 47: Classify meaning tags for each important move
    # MoveEval objects are recreated on each get_important_move_evals() call,
    # so we must classify here (not rely on stats.py assignment)
    total_moves_for_ctx = len(moves)
    classification_context = ClassificationContext(total_moves=total_moves_for_ctx)
    for mv in important_move_evals:
        if mv.meaning_tag_id is None:
            meaning_tag = classify_meaning_tag(mv, context=classification_context)
            mv.meaning_tag_id = meaning_tag.id.value

    # Apply player filter if specified
    if player_filter in ("B", "W"):
        important_move_evals = [m for m in important_move_evals if m.player == player_filter]

    important_moves_list = []
    for mv in important_move_evals:
        # Coords: handle pass and normal moves
        coords: Optional[str] = None
        if mv.gtp:
            if mv.gtp.lower() == "pass":
                coords = "pass"
            else:
                coords = mv.gtp

        # points_lost: use get_canonical_loss_from_move for consistency
        points_lost = get_canonical_loss_from_move(mv)

        # importance score
        importance = mv.importance_score if mv.importance_score is not None else 0.0

        # reason_tags
        reason_tags = list(mv.reason_tags) if mv.reason_tags else []

        # phase: use classify_game_phase
        try:
            phase = classify_game_phase(mv.move_number, board_x)
        except Exception:
            phase = "unknown"

        # Phase 47: Get meaning tag info
        meaning_tag_id = mv.meaning_tag_id
        meaning_tag_label = get_meaning_tag_label_safe(meaning_tag_id, lang)

        important_moves_list.append({
            "move_number": mv.move_number,
            "player": "black" if mv.player == "B" else "white" if mv.player == "W" else None,
            "coords": coords,
            "points_lost": round(points_lost, 1),
            "importance": round(importance, 2),
            "reason_tags": reason_tags,
            "phase": phase,
            "meaning_tag": {
                "id": meaning_tag_id,
                "label": meaning_tag_label,
            } if meaning_tag_id else None,
        })

    return {
        "schema_version": "1.0",
        "meta": meta,
        "summary": summary,
        "important_moves": important_moves_list,
    }


# =============================================================================
# Critical 3 LLM Prompt (Phase 50)
# =============================================================================

CRITICAL_3_PROMPT_TEMPLATE = """# Go Game Review Request

## Player Context
- Level: {player_level}
- Focus: Learning from critical mistakes

## Critical Mistakes

{critical_moves_section}

## Analysis Request
Please analyze each mistake and provide:
1. What fundamental concept or pattern was missed?
2. A simple rule or mental check for similar positions
3. One recommended practice pattern or exercise

Keep explanations concise and actionable.
"""


def build_critical_3_prompt(
    critical_moves: List[CriticalMove],
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
    for i, cm in enumerate(critical_moves, 1):
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
