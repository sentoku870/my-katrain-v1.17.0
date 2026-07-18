"""PV filter configuration and complexity-based candidate filtering.

Phase 144-C: Extracted from logic.py (1494 lines → 6 focused modules).
Phase 246-A: Added ``PVFilterDisplayInfo`` + ``get_effective_pv_filter_info``
to surface the AUTO→level mapping in the settings UI (H2).

Contains:
- get_pv_filter_config: Get PV filter config by level (with auto-mapping)
- filter_candidates_by_pv_complexity: Filter candidates by PV length and loss
- get_effective_pv_filter_info: Resolve the display-effective level for UI
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any

from katrain.core.analysis.models import (
    DEFAULT_SKILL_PRESET,
    PV_FILTER_CONFIGS,
    SKILL_TO_PV_FILTER,
    PVFilterConfig,
)

# =============================================================================
# PV Filter (Phase 11)
# =============================================================================


def get_pv_filter_config(
    pv_filter_level: str,
    skill_preset: str = DEFAULT_SKILL_PRESET,
    board_size: int | None = None,
    player_rank: str | None = None,
) -> PVFilterConfig | None:
    """
    PVフィルタ設定を取得する。

    Args:
        pv_filter_level: "off", "weak", "medium", "strong", "auto", "expert"
            (Phase 246-D M2: added "expert" for pro skill_preset)
        skill_preset: AUTOモード時に参照するskill_preset名。
            ``player_rank`` が指定された場合は上書きされる (Phase 246-E L7
            API 統一: ``rank_to_skill_preset`` 経由で自動推定)。
        board_size: 盤サイズ (Phase 246-D M1)。None または 0 の場合は
            19路基準のデフォルト値そのまま。9/13路では max_pv_length を
            線形縮小 (board_size / 19 倍) して、STRONG/EXPERT のような
            厳しい閾値が 9路でほぼ全候補を除外してしまう問題を緩和する。
        player_rank: Phase 246-E (L7) で追加。``pv_filter_level="auto"``
            かつ ``skill_preset`` が DEFAULT の場合、``player_rank`` から
            自動推定する口。``resolve_skill_preset`` 経由の呼び出しを
            ここに集約することで、呼び出し側の boilerplate を削減する。

    Returns:
        PVFilterConfig または None（OFFの場合）
    """
    level = pv_filter_level.lower()

    if level == "off":
        return None

    if level == "auto":
        # Phase 246-E (L7): if caller passes player_rank, derive
        # the preset on their behalf. Lazy import to avoid the
        # module-level cycle with logic_skill.
        if player_rank:
            from katrain.core.analysis.logic_skill import rank_to_skill_preset

            skill_preset = rank_to_skill_preset(player_rank)
        # skill_presetからpv_filter_levelを決定
        mapped_level = SKILL_TO_PV_FILTER.get(skill_preset, "medium")
        config = PV_FILTER_CONFIGS.get(mapped_level)
        return _scale_for_board(config, board_size)

    config = PV_FILTER_CONFIGS.get(level)
    return _scale_for_board(config, board_size)


# =============================================================================
# Phase 247-A (L5): LRU cache for hot-path config resolution
# =============================================================================


@functools.lru_cache(maxsize=32)
def resolve_pv_filter_config_cached(
    pv_filter_level: str,
    skill_preset: str,
    board_size: int | None,
    player_rank: str | None,
) -> PVFilterConfig | None:
    """LRU-cached wrapper around :func:`get_pv_filter_config` (Phase 247-A / L5).

    ``prepare_hint_moves`` is called on every hover / every node change
    in the GUI. The 4 inputs that drive ``get_pv_filter_config`` rarely
    change in practice (level is a single user choice, preset is
    derived from rank, board_size is fixed per game), so an LRU cache
    of 32 entries is more than enough to cover the realistic input
    space (``5 levels × 5 presets × 3 board_sizes × N ranks = ~75 worst
    case``, capped to 32 keeps memory bounded).

    Contract:
    - Pure function: same input → same output (the underlying
      ``get_pv_filter_config`` is deterministic given fixed rank and
      preset).
    - Cache key: ``(level, skill_preset, board_size, player_rank)``.
    - Cached across calls; ``cache_clear()`` is exposed for tests.
    - The function is intentionally a *thin* wrapper — no logic
      changes, just memoization.
    """
    return get_pv_filter_config(
        pv_filter_level,
        skill_preset=skill_preset or DEFAULT_SKILL_PRESET,
        board_size=board_size,
        player_rank=player_rank,
    )


def _scale_for_board(
    config: PVFilterConfig | None,
    board_size: int | None,
) -> PVFilterConfig | None:
    """Phase 246-D (M1): scale ``max_pv_length`` linearly with board size.

    19路ベースで設計された ``max_pv_length`` 閾値を 9路/13路で使うと
    終盤で全候補が除外される問題があった (例: STRONG の 6手 PV は
    9路では 1/3 局面程度しか残らない)。盤サイズに比例して縮小する
    ことで、全サイズで「中盤の読み筋の複雑さ」を一貫した指標にする。

    Returns a NEW PVFilterConfig (frozen dataclass) so the original
    preset table is not mutated. Returns ``config`` unchanged when
    ``board_size`` is missing / non-positive / not standard.
    """
    if config is None or not board_size or board_size < 2 or board_size > 25:
        return config
    if board_size == 19:
        return config  # canonical, no scaling needed
    # Linear scaling: 19路 → 1.0x, 9路 → 9/19 ≈ 0.47x.
    # Round to int with min 1 so the threshold never collapses to 0.
    # 5/7 路の超小型盤でも同じ式が使える (scale = 5/19 ≈ 0.26 など)。
    scale = board_size / 19.0
    return PVFilterConfig(
        max_candidates=config.max_candidates,  # cap stays the same
        max_points_lost=config.max_points_lost,  # loss threshold is board-agnostic
        max_pv_length=max(1, round(config.max_pv_length * scale)),
    )


def filter_candidates_by_pv_complexity(
    candidates: list[dict[str, Any]],
    config: PVFilterConfig,
) -> list[dict[str, Any]]:
    """
    候補手リストをPV複雑度でフィルタリングする（Phase 11）。

    データ仕様:
    - pv: 常にList[str]で存在（GTP座標の着手列）
    - pointsLost: 常に存在（game_node.pyで計算追加）
    - relativePointsLost: Phase 182+ で追加 (best_move との差)
    - order: 常に存在（欠損時はADDITIONAL_MOVE_ORDER=999）

    上限ルール:
    - max_candidates はフィルタ通過手の上限（best_move は別枠）
    - best_move（order=0）は上限に含めず常に表示

    Args:
        candidates: candidate_moves から取得した候補手リスト
        config: PVFilterConfig（閾値設定）

    Returns:
        フィルタ済みの候補手リスト
    """
    if not candidates:
        return []

    # Phase 246-D (L1): choose which loss field drives the filter.
    # Default ("pointsLost") is the absolute loss from next-player's view.
    # "relativePointsLost" is the gap to the best move (best_move is
    # always 0 in that field, so the threshold controls "how much worse
    # than best is acceptable").
    loss_key = getattr(config, "loss_metric", "pointsLost") or "pointsLost"

    # Step 1: order=0（最善手）を特定
    best_move = None
    for c in candidates:
        if c.get("order", 999) == 0:
            best_move = c
            break

    # Step 2: フィルタ条件でチェック（best_move以外）
    filtered = []
    for c in candidates:
        if c is best_move:
            continue  # best_moveは別枠で処理
        # Phase 246-C (H5): coerce ``None`` / missing values to 0.0 so
        # the ``<=`` comparison doesn't TypeError. Defensive against
        # half-populated analysis (e.g. a candidate without pointsLost
        # because KataGo only ran policy probing on that branch).
        points_lost = c.get(loss_key) or 0.0
        pv = c.get("pv") or []
        pv_length = len(pv)

        # 条件: 損失が閾値以下 AND PV長が閾値以下
        if points_lost <= config.max_points_lost and pv_length <= config.max_pv_length:
            filtered.append(c)

    # Step 3: max_candidates 制限（order順でカット、best_move除外済み）
    # Phase 246-C (M7): secondary sort key (pointsLost asc, visits desc)
    # makes the cap deterministic when multiple candidates share the
    # same ``order`` (e.g. ``ADDITIONAL_MOVE_ORDER=999`` from a merged
    # analysis). Without this, ``sorted`` is stable but the input order
    # is dict-iteration order — not stable across runs.
    #
    # Phase 247-D (M3): composite sort alternative. When
    # ``config.sort_mode == "composite"`` the cap is decided by a
    # single weighted score combining pointsLost and pv_length
    # normalized to ``max_pv_length``. The two sorts are independent
    # (the default ``order_loss_visits`` path is preserved bit-for-bit
    # so all 246-C tests keep passing).
    sort_mode = getattr(config, "sort_mode", "order_loss_visits")
    if sort_mode == "composite":
        alpha = float(getattr(config, "composite_alpha", 1.0) or 0.0)
        max_pv_length = max(1, config.max_pv_length)

        def _composite_key(c: dict[str, Any]) -> tuple[float, int, int, float]:
            loss = c.get(loss_key) or 0.0
            pv_len = len(c.get("pv") or [])
            composite = loss + alpha * (pv_len / max_pv_length)
            return (composite, c.get("order", 999), pv_len, -c.get("visits", 0))

        filtered = sorted(filtered, key=_composite_key)
    else:
        # Default: Phase 246-C (M7) 3-key sort
        filtered = sorted(
            filtered,
            key=lambda c: (
                c.get("order", 999),
                c.get(loss_key) or 0.0,
                -c.get("visits", 0),
            ),
        )
    filtered = filtered[: config.max_candidates]

    # Step 4: best_moveを先頭に挿入（別枠、上限外）
    if best_move:
        filtered.insert(0, best_move)

    return filtered


# =============================================================================
# Phase 247-B (H3): position-aware preview counts
# =============================================================================


@dataclass(frozen=True)
class PVFilterPreview:
    """Counts of how the PV filter applies to a specific node (H3).

    Used by the settings popup status label and (Phase 247-C) the
    controls panel live preview. The dataclass is the single source
    of truth for ``raw / filtered / best / config_active`` so both UI
    surfaces can format the same numbers consistently.

    Attributes:
        raw_count: Number of candidates KataGo returned for the node
            (0 if no analysis yet).
        filtered_count: Number of candidates after the filter applies
            (== raw_count if filter is OFF or in kifunarabe mode).
        best_count: Always 1 if a best_move exists, else 0. The
            filter keeps best_move as a separate quota (Phase 11).
        config_active: True if the filter actually ran (i.e., not
            OFF and not in kifunarabe bypass). When False, the
            UI can suppress the "N → M" arrow and just show
            "all candidates".
    """

    raw_count: int
    filtered_count: int
    best_count: int
    config_active: bool


def compute_pv_filter_preview(
    node: Any,
    config: PVFilterConfig | None,
    *,
    in_kifu: bool = False,
) -> PVFilterPreview:
    """Compute the N → M preview for a given node and filter config.

    Phase 247-B (H3): the settings popup wants to show the user the
    actual count reduction for the current node, not just the static
    cap from the level. This function is a thin, Kivy-free wrapper
    over :func:`filter_candidates_by_pv_complexity`.

    Args:
        node: The current GameNode (or any object with a
            ``candidate_moves`` list and ``analysis_exists`` flag).
        config: The active PVFilterConfig, or ``None`` (= OFF).
        in_kifu: True if kifunarabe mode is active — the filter
            is bypassed (Phase 246-D H4 contract) and all
            candidates are passed through.

    Returns:
        :class:`PVFilterPreview` with the four counts.
    """
    if node is None or not getattr(node, "analysis_exists", False):
        return PVFilterPreview(0, 0, 0, False)

    candidates = list(getattr(node, "candidate_moves", []) or [])
    raw_count = len(candidates)
    best_count = sum(1 for c in candidates if c.get("order", 999) == 0)

    # Filter is bypassed in kifunarabe mode (Phase 246-D H4) or
    # when the level is OFF.
    config_active = config is not None and not in_kifu
    if not config_active:
        return PVFilterPreview(raw_count, raw_count, best_count, False)

    assert config is not None  # for mypy: narrowed by the check above
    filtered = filter_candidates_by_pv_complexity(candidates, config)
    return PVFilterPreview(raw_count, len(filtered), best_count, True)


# =============================================================================
# Phase 246-A: Display-effective level resolution
# =============================================================================


@dataclass(frozen=True)
class PVFilterDisplayInfo:
    """UI-facing summary of the effective PV filter level.

    Used by the analysis-tab settings popup to show the user what the
    AUTO mode will actually do (H2). The runtime path still calls
    :func:`get_pv_filter_config`; this dataclass only exists for
    display.

    Attributes:
        effective_level: Resolved level name. One of
            ``"off"`` / ``"weak"`` / ``"medium"`` / ``"strong"``.
        max_candidates: Cap for the resolved level (0 if ``"off"``,
            which means "unlimited / no filter").
        is_auto: True when the user selected ``"auto"`` and we
            resolved a concrete level from ``player_rank``.
        resolved_preset: skill_preset the AUTO mapping landed on
            (``None`` if not AUTO or ``player_rank`` was empty).
    """

    effective_level: str
    max_candidates: int
    is_auto: bool
    resolved_preset: str | None


def get_effective_pv_filter_info(
    pv_filter_level: str | None,
    player_rank: str | None = "",
) -> PVFilterDisplayInfo:
    """Resolve the display-effective PV filter level and its cap.

    Phase 246-A: makes the ``AUTO → weak/medium/strong`` mapping visible
    to the user via the settings popup status label (H2). Behavioural
    parity with :func:`get_pv_filter_config` is preserved — this function
    does NOT change runtime filtering, only the description returned to
    the UI layer.

    Args:
        pv_filter_level: The user's selected level
            (``"off"`` / ``"weak"`` / ``"medium"`` / ``"strong"`` /
            ``"auto"``). ``None`` and empty string are treated as
            ``"auto"`` (matches the runtime fallback in
            ``badukpan_hints.prepare_hint_moves``).
        player_rank: The user's rank string for AUTO resolution
            (e.g. ``"5d"`` / ``"4段"``). May be empty.

    Returns:
        :class:`PVFilterDisplayInfo` with the effective level and cap.

    Note:
        This function does NOT import ``logic_skill`` at module load
        time to avoid an import cycle — ``logic_skill`` imports
        models which already import nothing from ``logic_pv``, but
        the lazy import keeps the dependency graph one-directional.
    """
    # Mirror the runtime fallback: None / empty → "auto".
    level = (pv_filter_level or "").strip().lower()
    if not level:
        level = "auto"

    if level == "off":
        # 0 max_candidates sentinel: "unlimited" (no filter applied).
        return PVFilterDisplayInfo("off", 0, False, None)

    if level == "auto":
        # Lazy import to avoid module-level cycle with logic_skill.
        from katrain.core.analysis.logic_skill import rank_to_skill_preset

        resolved = rank_to_skill_preset(player_rank) if player_rank else DEFAULT_SKILL_PRESET
        mapped = SKILL_TO_PV_FILTER.get(resolved, "medium")
        config = PV_FILTER_CONFIGS.get(mapped)
        if config is None:
            return PVFilterDisplayInfo(mapped, 0, True, resolved)
        return PVFilterDisplayInfo(mapped, config.max_candidates, True, resolved)

    # Explicit level (weak / medium / strong)
    config = PV_FILTER_CONFIGS.get(level)
    if config is None:
        # Unknown level: keep the name but report 0 cap so the UI
        # can show "?" or fall back to "auto".
        return PVFilterDisplayInfo(level, 0, False, None)
    return PVFilterDisplayInfo(level, config.max_candidates, False, None)


# =============================================================================
# Phase 246-C (M5): PV clipping for animated playback
# =============================================================================


#: Hard cap on the number of PV steps we feed into the GUI animation.
#: 30 is well above any realistic PV length and well below the per-frame
#: skip cost that ``draw_pv`` would otherwise incur on a 50+ step line.
#: Kept here in the Kivy-free analysis package so the helper can be
#: unit-tested without booting a Kivy app.
PV_ANIMATION_MAX_STEPS: int = 30


def clip_pv_for_animation(pv: Any) -> list[str]:
    """Clip a PV sequence to :data:`PV_ANIMATION_MAX_STEPS` steps.

    Phase 246-C (M5): the candidate-marker path in the GUI feeds the
    animated playback in :mod:`katrain.gui.badukpan_pv`. KataGo can
    occasionally return a very long PV (50+ moves) when the position
    has a long forcing sequence. Rendering 50+ stones is both visually
    noisy and performance-wasteful — we cap to 30 so the user sees a
    meaningful slice without the animation stuttering.

    Defensive contract:
    - ``None`` or non-list input → returns ``[]`` (caller skips the
      marker).
    - Lists shorter than the cap are returned as a fresh list (the
      caller's list is not mutated).
    - Lists longer than the cap are sliced to the first ``cap`` items.
    - Non-string elements are coerced via ``str()`` so downstream
      :func:`Move.from_gtp` doesn't crash on bad data.
    """
    if not isinstance(pv, list):
        return []
    # Always coerce to str so downstream ``Move.from_gtp`` never sees
    # a non-string. For short lists we also return a fresh list to
    # guarantee the input is not mutated.
    if len(pv) <= PV_ANIMATION_MAX_STEPS:
        return [str(x) for x in pv]
    return [str(x) for x in pv[:PV_ANIMATION_MAX_STEPS]]
