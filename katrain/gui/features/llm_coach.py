# katrain/gui/features/llm_coach.py
#
# Phase 225: LLM Coach GUI helper functions.
#
# Thin wrappers around the Phase 207-213 ``core/coach/`` CLI helpers so the
# Kivy popup (Phase 225) can drive them without re-implementing the
# prompt-building and validation logic. All Kivy imports are deferred to
# the popup module so this file stays import-safe in CI.
#
# Workflow (manual paste, no API):
#   1. User exports a Karte (MyKatrain → Export Karte).
#   2. User opens MyKatrain → LLM Coach.
#   3. Popup auto-fills the latest Karte path; user can edit it.
#   4. "Generate & Copy Prompt" → builds Markdown and copies to clipboard.
#   5. User pastes into Claude / ChatGPT / Gemini manually.
#   6. User pastes the LLM response back into the popup.
#   7. "Validate" → runs ``validate_llm_output`` and shows a Markdown report.

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from katrain.core.constants.output import OUTPUT_ERROR
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


# Reasonable upper bound to prevent the result label from freezing the UI
# when a user pastes a megabyte-sized response.
_MAX_REPORT_CHARS = 20_000


def _read_karte(karte_path: str | Path) -> dict[str, Any]:
    """Load a Karte JSON file. Raises on missing / malformed input."""
    p = Path(karte_path)
    with open(p, encoding="utf-8") as f:
        return cast("dict[str, Any]", json.load(f))


# ---------------------------------------------------------------------------
# Phase 229-D: Rank auto-detection fallback chain
# ---------------------------------------------------------------------------


def resolve_rank_fallback_chain(
    info: dict[str, Any] | None,
    perspective_value: str,
    *,
    general_player_rank: str | None = None,
    default_user_rank: str | None = None,
) -> str | None:
    """Pick the rank to display in the LLM Coach popup (Phase 229-D).

    The priority chain (first non-empty wins):

    1. Karte/SGF ``info`` dict (``_pick_detected_rank``)
    2. ``general/player_rank`` (the new global setting from Phase 229-C)
    3. ``mykatrain_settings.default_user_rank`` (Phase 225.8 legacy fallback)

    Args:
        info: The Karte/SGF player info dict, or ``None`` if unavailable.
        perspective_value: Spinner internal value (``"auto"`` / ``"B"`` / ``"W"``).
        general_player_rank: Value of ``general/player_rank``. May be empty.
        default_user_rank: Value of ``mykatrain_settings.default_user_rank``.
            May be empty.

    Returns:
        The first non-empty rank string, or ``None`` if none of the
        sources have rank information.

    Note:
        This function is a pure helper with no Kivy dependency so it
        can be unit-tested on CI without a display.
    """
    if info:
        detected = _pick_detected_rank(info, perspective_value)
        if detected:
            return detected
    if general_player_rank:
        return general_player_rank
    if default_user_rank:
        return default_user_rank
    return None


def _pick_detected_rank(info: dict[str, Any], perspective_value: str) -> str | None:
    """Pick the rank to show for the active perspective.

    Phase 225.6: the rank hint shows the player's own rank when the
    perspective is Auto / B / W. Returns ``None`` when nothing is known.

    Phase 226-B (B3): ``perspective_value`` is now always one of
    ``"auto"`` / ``"B"`` / ``"W"`` (the spinner's internal value), so
    we no longer need ``startswith("黒")`` heuristics.
    """
    black = (info.get("black") or {}).get("rank") or None
    white = (info.get("white") or {}).get("rank") or None
    if perspective_value == "B":
        return black
    if perspective_value == "W":
        return white
    return black or white


def build_llm_prompt(
    ctx: FeatureContext | None,
    karte_path: str | Path,
    *,
    rank: str | None = None,
    avg_points_lost: float | None = None,
    player_color: str | None = None,
) -> tuple[bool, str]:
    """Build an LLM-ready Markdown prompt from a Karte JSON file.

    Thin wrapper around ``core.coach.cli.build_prompt``. The Markdown is
    ready to be pasted into Claude / ChatGPT / Gemini.

    Args:
        ctx: FeatureContext for logging. May be None (e.g. unit tests).
        karte_path: Path to a Karte JSON file.
        rank: Optional rank string (e.g. ``"5k"``).
        avg_points_lost: Optional average points lost (overrides Karte's
            own average).
        player_color: Phase 225.6. ``"B"`` / ``"W"`` / ``None``. When
            ``None``, the SystemInstruction is told "PlayerColor:
            unknown" so the LLM doesn't bias its review.

    Returns:
        (success, content). On success ``content`` is the full prompt
        Markdown. On failure ``content`` is an i18n error message.
    """
    from katrain.core.coach.cli import build_prompt as _build_prompt

    try:
        karte = _read_karte(karte_path)
        prompt = _build_prompt(
            karte,
            rank=rank,
            avg_points_lost=avg_points_lost,
            player_color=player_color,
        )
    except FileNotFoundError:
        msg = i18n._("mykatrain:llm-coach:file-not-found").format(path=str(karte_path))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        msg = i18n._("mykatrain:llm-coach:invalid-karte").format(error=str(exc))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg
    return True, prompt.full_markdown


def validate_llm_response(
    ctx: FeatureContext | None,
    karte_path: str | Path,
    llm_text: str,
    *,
    rank: str | None = None,
) -> tuple[bool, str]:
    """Validate a user-pasted LLM response against a Karte JSON.

    The validation report is returned as Markdown so the GUI can display
    it directly in a label. Reports longer than ``_MAX_REPORT_CHARS`` are
    truncated to keep the UI responsive.

    Phase 242-B: when truncation happens, the trailing marker
    (``i18n._("mykatrain:llm-coach:truncated")``) is appended to the
    Markdown. The popup detects this marker to surface a status
    warning so the user knows the displayed report is incomplete.

    Args:
        ctx: FeatureContext for logging. May be None (e.g. unit tests).
        karte_path: Path to the Karte JSON used as ground truth.
        llm_text: The user-pasted LLM response.
        rank: Optional rank string passed through to the prompt builder.

    Returns:
        (is_clean, markdown_report). ``is_clean`` mirrors
        ``ValidationReport.is_clean`` (no issues).
    """
    from katrain.core.coach.cli import build_prompt as _build_prompt
    from katrain.core.coach.llm_validator import validate_llm_output

    try:
        karte = _read_karte(karte_path)
        prompt = _build_prompt(karte, rank=rank)
        report = validate_llm_output(
            llm_text,
            karte,
            prompt,
            config=prompt.config,
        )
    except FileNotFoundError:
        msg = i18n._("mykatrain:llm-coach:file-not-found").format(path=str(karte_path))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        msg = i18n._("mykatrain:llm-coach:invalid-karte").format(error=str(exc))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg

    markdown = _render_validation_report(report)
    if len(markdown) > _MAX_REPORT_CHARS:
        markdown = markdown[:_MAX_REPORT_CHARS] + i18n._("mykatrain:llm-coach:truncated")
    return report.is_clean, markdown


# Phase 242-B: helper to detect if a validate result was truncated.
# The popup uses this to surface a status warning. The marker is the
# i18n-truncated suffix that validate_llm_response appends. We check
# the substring rather than recomputing the length so we stay
# robust to i18n edits to the truncated marker.
def was_truncated(markdown: str) -> bool:
    """Phase 242-B: detect whether ``markdown`` is a truncated report.

    Args:
        markdown: The Markdown string returned by
            :func:`validate_llm_response` or
            :func:`validate_summary_llm_response`.

    Returns:
        True if the trailing truncation marker is present, False
        otherwise.
    """
    marker = i18n._("mykatrain:llm-coach:truncated")
    return bool(marker) and markdown.endswith(marker)


def _render_validation_report(report: Any) -> str:
    """Render a :class:`ValidationReport` as a multi-line Markdown string.

    Phase 242-D: thin wrapper around the unified
    :func:`katrain.core.coach.llm_report_renderer.render_validation_report`.
    """
    from katrain.core.coach.llm_report_renderer import (
        ReferencedItem,
    )
    from katrain.core.coach.llm_report_renderer import (
        render_validation_report as _render,
    )

    referenced = [
        ReferencedItem(
            label_key="mykatrain:llm-coach:referenced-symptoms",
            values=report.referenced_symptom_ids,
        ),
        ReferencedItem(
            label_key="mykatrain:llm-coach:referenced-moves",
            values=list(report.referenced_move_numbers),
        ),
        ReferencedItem(
            label_key="mykatrain:llm-coach:referenced-points-lost",
            values=list(report.referenced_points_lost),
        ),
        ReferencedItem(
            label_key="mykatrain:llm-coach:referenced-lexicon",
            values=report.referenced_lexicon_ids,
        ),
    ]
    return _render(report, referenced)


# Phase 241-G: ``find_latest_karte`` was removed. It only matched
# ``karte_*.json`` and silently ignored ``summary_*.json``, which
# the LLM Coach popup (Phase 227-D) added as a first-class input
# type. The popup already uses
# :func:`find_latest_llm_input_for_ctx` exclusively, so the legacy
# function had no remaining callers in the production code. Tests
# that referenced it have been removed in the same commit
# (see :file:`tests/test_llm_coach.py` for the cleanup).
#
# Migration: replace ``find_latest_karte(ctx)`` with
# ``find_latest_llm_input_for_ctx(ctx)``. The new helper returns the
# most recent ``karte_*.json`` OR ``summary_*.json`` and is what
# the popup calls.


# --- Phase 227-D: Multi-game summary wrappers --------------------------

# Reasonable upper bound for the summary prompt, mirroring the karte
# prompt cap from above. Summary prompts are typically shorter (no
# per-move data) so this is mostly a safety net.
_MAX_SUMMARY_REPORT_CHARS = 25_000


def build_summary_llm_prompt(
    ctx: FeatureContext | None,
    summary_path: str | Path,
    *,
    rank: str | None = None,
    player_name: str | None = None,
) -> tuple[bool, str]:
    """Phase 227-D: build an LLM-ready summary prompt and copy to clipboard.

    Thin wrapper around the Phase 227-A ``build_summary_weakness_prompt``
    core helper. The popup calls this when the user clicks
    "集約サマリプロンプト".

    Args:
        ctx: FeatureContext for logging. May be None (e.g. unit tests).
        summary_path: Path to a multi-game Summary JSON.
        rank: Optional rank string (e.g. ``"5k"``).
        player_name: Optional focus player name. ``None`` (default)
            means "bird's-eye view" (全体俯瞰). When set, the LLM is
            told to focus on that player's perspective.

    Returns:
        ``(success, content)``. On success ``content`` is the full
        prompt Markdown. On failure ``content`` is an i18n error
        message ready to display in the status label.
    """
    from katrain.core.coach.summary_prompt_builder import (
        SummaryPromptConfig,
        build_summary_weakness_prompt,
    )
    from katrain.core.coach.tones import select_voice

    try:
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)
        if not isinstance(summary, dict):
            raise ValueError(f"Expected JSON object, got {type(summary).__name__}")
    except FileNotFoundError:
        msg = i18n._("mykatrain:llm-coach:file-not-found").format(path=str(summary_path))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        msg = i18n._("mykatrain:llm-coach:invalid-karte").format(error=str(exc))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg

    voice = select_voice(rank)
    # Phase 269 follow-up: ``mode`` is independent of ``voice`` after the
    # AYAKA removal (all voices serve multiple modes). Derive the mode
    # directly from the rank so a 4d player sees Level: DAN, not
    # Level: BEGINNER (which is what the previous modes[0] fallback
    # produced for any TOMOKO-served rank).
    from katrain.core.coach.master_db import CoachMode, estimate_mode_from_rank

    mode = estimate_mode_from_rank(rank) or CoachMode.INTERMEDIATE

    games = summary.get("meta", {}).get("games_analyzed", 0) or 0
    cfg = SummaryPromptConfig(
        voice=voice,
        mode=mode,
        games_analyzed=games,
        player_name=player_name,
        player_rank=rank,
        schema_version=str(summary.get("schema_version", "unknown")),
    )
    try:
        prompt = build_summary_weakness_prompt(summary, cfg)
    except Exception as exc:  # noqa: BLE001 — propagate as user-facing error
        msg = i18n._("mykatrain:llm-coach:summary-build-failed").format(error=str(exc))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg
    return True, prompt.full_markdown


def validate_summary_llm_response(
    ctx: FeatureContext | None,
    summary_path: str | Path,
    llm_text: str,
    *,
    rank: str | None = None,
    player_name: str | None = None,
) -> tuple[bool, str]:
    """Phase 227-D: validate a user-pasted LLM response against a Summary JSON.

    Thin wrapper around :func:`katrain.core.coach.summary_validator.validate_summary_llm_output`.
    Mirrors :func:`validate_llm_response` for the karte case so the
    popup can dispatch on the file type.

    Args:
        ctx: FeatureContext for logging. May be None.
        summary_path: Path to the Summary JSON used as ground truth.
        llm_text: The user-pasted LLM response.
        rank: Optional rank string forwarded to the prompt builder.
        player_name: Optional focus player name forwarded to the prompt
            builder. Must match the value used in ``build_summary_llm_prompt``
            so the validator sees the same prompt config.

    Returns:
        ``(is_clean, markdown_report)``. Reports longer than
        ``_MAX_SUMMARY_REPORT_CHARS`` are truncated to keep the UI
        responsive.
    """
    from katrain.core.coach.summary_prompt_builder import (
        SummaryPromptConfig,
        build_summary_weakness_prompt,
    )
    from katrain.core.coach.summary_validator import validate_summary_llm_output
    from katrain.core.coach.tones import select_voice

    try:
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)
        if not isinstance(summary, dict):
            raise ValueError(f"Expected JSON object, got {type(summary).__name__}")
    except FileNotFoundError:
        msg = i18n._("mykatrain:llm-coach:file-not-found").format(path=str(summary_path))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        msg = i18n._("mykatrain:llm-coach:invalid-karte").format(error=str(exc))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg

    voice = select_voice(rank)
    # Phase 269 follow-up: same fix as build_summary_llm_prompt above.
    # Derive mode from rank, not from modes[0] (which is always
    # BEGINNER after the AYAKA removal).
    from katrain.core.coach.master_db import CoachMode, estimate_mode_from_rank

    mode = estimate_mode_from_rank(rank) or CoachMode.INTERMEDIATE

    games = summary.get("meta", {}).get("games_analyzed", 0) or 0
    cfg = SummaryPromptConfig(
        voice=voice,
        mode=mode,
        games_analyzed=games,
        player_name=player_name,
        player_rank=rank,
        schema_version=str(summary.get("schema_version", "unknown")),
    )
    try:
        prompt = build_summary_weakness_prompt(summary, cfg)
        report = validate_summary_llm_output(llm_text, summary, prompt)
    except Exception as exc:  # noqa: BLE001
        msg = i18n._("mykatrain:llm-coach:summary-build-failed").format(error=str(exc))
        if ctx is not None:
            ctx.log(msg, OUTPUT_ERROR)
        return False, msg

    markdown = _render_summary_validation_report(report, cfg, summary)
    if len(markdown) > _MAX_SUMMARY_REPORT_CHARS:
        markdown = markdown[:_MAX_SUMMARY_REPORT_CHARS] + i18n._("mykatrain:llm-coach:truncated")
    return report.is_clean, markdown


def _render_summary_validation_report(
    report: Any,
    cfg: Any,
    summary: dict[str, Any],
) -> str:
    """Phase 227-D + 242-D: render a :class:`SummaryValidationReport` as Markdown.

    Thin wrapper around the unified
    :func:`katrain.core.coach.llm_report_renderer.render_validation_report`.
    The only Summary-specific extra is the ``summary-report-meta`` line
    ("N局 / focus") inserted between the severity banner and the
    referenced items.
    """
    from katrain.core.coach.llm_report_renderer import (
        ReferencedItem,
    )
    from katrain.core.coach.llm_report_renderer import (
        render_validation_report as _render,
    )

    games = cfg.games_analyzed
    focus = cfg.player_name or "全体俯瞰"
    extra_meta = i18n._("mykatrain:llm-coach:summary-report-meta").format(games=games, focus=focus)
    referenced = [
        ReferencedItem(
            label_key="mykatrain:llm-coach:summary-referenced-categories",
            values=report.referenced_categories,
        ),
        ReferencedItem(
            label_key="mykatrain:llm-coach:summary-referenced-phases",
            values=report.referenced_phases,
        ),
        ReferencedItem(
            label_key="mykatrain:llm-coach:summary-referenced-moves",
            values=list(report.referenced_move_numbers),
        ),
        ReferencedItem(
            label_key="mykatrain:llm-coach:summary-referenced-game-ids",
            values=report.referenced_game_ids,
        ),
    ]
    return _render(report, referenced, extra_meta=extra_meta)


def find_latest_llm_input_for_ctx(ctx: FeatureContext) -> Path | None:
    """Phase 227-C: locate the most recent karte/summary for the LLM Coach.

    Thin wrapper around :func:`katrain.gui.features.report_navigator.find_latest_llm_input`
    that resolves the configured output directory first. Returns
    ``None`` when no LLM-input JSON exists. The caller is responsible
    for re-detecting the type (via :func:`katrain.core.coach.is_karte`
    / :func:`katrain.core.coach.is_summary`) to pick the right
    downstream handler.

    This is the multi-game-aware file picker that the popup
    (Phase 227-D) calls. Phase 241-G removed the legacy
    ``find_latest_karte`` helper that only matched ``karte_*.json``.
    """
    from katrain.common.platform import resolve_output_directory
    from katrain.gui.features.report_navigator import find_latest_llm_input

    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    config_dir = mykatrain_settings.get("karte_output_directory", "")
    output_dir = resolve_output_directory(config_dir)

    if not output_dir.is_dir():
        return None
    report = find_latest_llm_input(output_dir)
    return report.path if report is not None else None


def detect_player_info_for_summary(
    summary_path: str | Path,
    *,
    default_user_name: str | None = None,
) -> dict[str, Any]:
    """Phase 227-C: extract player info from a multi-game Summary JSON.

    The summary JSON shape differs from a karte: the ``players`` block
    is keyed by **player name** (e.g. ``players["sentoku870"]``), and
    per-player aggregate stats live under ``players[<name>].overall``.
    The Karte's ``meta.player_info.{black,white}`` block does not
    exist.

    Selection priority:
    1. ``default_user_name`` if it matches a key in ``players``.
    2. The first player key in ``players`` (alphabetical order for
       determinism when multiple players exist and no default_user is
       configured).

    Args:
        summary_path: Path to the summary JSON file.
        default_user_name: Optional name to look up in ``players``. When
            omitted (e.g. in tests where no settings are available),
            the first player is picked.

    Returns:
        Dict shaped like::

            {
                "matched_player": {
                    "name": str | None,
                    "rank": str | None,
                },
                "all_players": [
                    {"name": str, "rank": str | None},
                    ...
                ],
                "default_user_matched": bool,
                "source": "summary_meta" | "missing",
            }

        - ``matched_player`` is the player we'll focus on (default_user
          match or first available). Used by the GUI to auto-fill the
          rank input.
        - ``all_players`` is the full list, used to populate the
          perspective selector (Phase 227-D).
        - ``default_user_matched`` distinguishes "we picked someone
          because the default matched" from "we fell back to the
          first player because no default was configured".
        - ``source`` mirrors the karte variant: ``"summary_meta"`` when
          a ``players`` block was found, ``"missing"`` otherwise.
    """
    path = Path(summary_path)
    if not path.exists():
        return _empty_summary_player_info("missing")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _empty_summary_player_info("missing")

    players = data.get("players", {}) or {}
    if not isinstance(players, dict) or not players:
        return _empty_summary_player_info("missing")

    # Build a stable list of all players (alphabetical by name for
    # determinism — the test fixtures rely on this).
    all_players: list[dict[str, str | None]] = []
    for name in sorted(players.keys()):
        block = players.get(name) or {}
        if not isinstance(block, dict):
            block = {}
        rank = _extract_player_rank(block)
        all_players.append({"name": str(name), "rank": rank})

    # Selection: default_user first, then first player.
    matched_name: str | None = None
    default_user_matched = False
    if default_user_name and default_user_name in players:
        matched_name = default_user_name
        default_user_matched = True
    elif all_players:
        matched_name = all_players[0]["name"]
    else:
        return _empty_summary_player_info("missing")

    # Re-resolve the matched player's rank from the original dict
    # (we want the canonical form, not the post-sort snapshot).
    matched_block = players.get(matched_name) or {}
    matched_rank = _extract_player_rank(matched_block) if isinstance(matched_block, dict) else None

    return {
        "matched_player": {"name": matched_name, "rank": matched_rank},
        "all_players": all_players,
        "default_user_matched": default_user_matched,
        "source": "summary_meta",
    }


def _extract_player_rank(player_block: dict[str, Any]) -> str | None:
    """Phase 227-C: extract rank from ``players[<name>]`` block.

    The summary export stores rank under several possible keys
    depending on schema version. We try them in priority order:

    1. ``player_block["rank"]`` (flat, used in newer exports)
    2. ``player_block["overall"]["rank"]`` (Phase 158+ nested form)
    3. ``player_block["stats"]["rank"]`` (legacy form)

    Returns ``None`` when none of these are populated.
    """
    if not isinstance(player_block, dict):
        return None
    direct = player_block.get("rank")
    if isinstance(direct, str) and direct:
        return direct
    overall = player_block.get("overall")
    if isinstance(overall, dict):
        r = overall.get("rank")
        if isinstance(r, str) and r:
            return r
    stats = player_block.get("stats")
    if isinstance(stats, dict):
        r = stats.get("rank")
        if isinstance(r, str) and r:
            return r
    return None


def _empty_summary_player_info(source: str) -> dict[str, Any]:
    return {
        "matched_player": {"name": None, "rank": None},
        "all_players": [],
        "default_user_matched": False,
        "source": source,
    }


def detect_player_info(
    ctx: FeatureContext | None,
    karte_path: str | Path,
) -> dict[str, Any]:
    """Phase 225.6: extract black/white player info from a Karte JSON.

    Looks at ``meta.player_info`` first (the field Phase 225.6 added
    to the Karte schema), then falls back to the SGF file referenced
    by ``source_filename`` in meta (in case the Karte was built from a
    legacy export without the player_info block).

    Returns a dict shaped like::

        {
            "black": {"name": str | None, "rank": str | None},
            "white": {"name": str | None, "rank": str | None},
            "source": "karte_meta" | "sgf_file" | "missing",
        }
    """
    path = Path(karte_path)
    if not path.exists():
        return _empty_player_info("missing")

    try:
        with open(path, encoding="utf-8") as f:
            karte = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _empty_player_info("missing")

    info = (karte.get("meta") or {}).get("player_info")
    if info and isinstance(info, dict) and isinstance(info.get("black"), dict) and isinstance(info.get("white"), dict):
        return {
            "black": dict(info["black"]),
            "white": dict(info["white"]),
            "source": "karte_meta",
        }

    # Fallback: parse the source SGF (if any).
    source_filename = (karte.get("meta") or {}).get("source_filename")
    if source_filename:
        from katrain.core.coach.sgf_player_info import (
            extract_player_info_from_sgf,
        )

        try:
            sgf_info = extract_player_info_from_sgf(source_filename)
        except (OSError, ValueError):
            sgf_info = None
        if sgf_info is not None:
            return {
                "black": {"name": sgf_info.black.name, "rank": sgf_info.black.rank},
                "white": {"name": sgf_info.white.name, "rank": sgf_info.white.rank},
                "source": "sgf_file",
            }

    return _empty_player_info("missing")


def _empty_player_info(source: str) -> dict[str, Any]:
    return {
        "black": {"name": None, "rank": None},
        "white": {"name": None, "rank": None},
        "source": source,
    }


def detect_player_color_for_user(
    ctx: FeatureContext | None,
    karte_path: str | Path,
    *,
    player_info: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """Phase 225.6 / Phase 226-B (B4) / Phase 241-F: determine which
    side the configured default user plays and return ``(color, rank)``.

    ``color`` is ``"B"`` / ``"W"`` / ``None``; ``rank`` is the matching
    rank string from the Karte / SGF. ``None`` is returned when the
    user setting is empty or no match is found.

    Phase 226-B (B4): the caller may pass an already-loaded
    ``player_info`` dict (as returned by :func:`detect_player_info`) to
    avoid reading & parsing the same JSON a second time. When
    ``player_info`` is ``None`` we fall back to the previous behaviour
    of reading the file ourselves.

    Phase 241-F: build a real :class:`SgfPlayerInfo` instance instead
    of the previous ``_SgfInfoLike`` + ``cast()`` shim. The
    ``cast(SgfPlayerInfo, pseudo)`` bypassed Python's runtime type
    system: any future ``isinstance(pseudo, SgfPlayerInfo)`` check
    inside :func:`extract_player_info_for_user` would silently break.
    Constructing the dataclass directly is honest and lets the
    runtime validator catch a future schema drift.
    """
    if ctx is None:
        return None, None
    default_user = (ctx.config("mykatrain_settings") or {}).get("default_user_name", "")
    if not default_user:
        return None, None
    info = player_info if player_info is not None else detect_player_info(ctx, karte_path)
    from katrain.core.coach.sgf_player_info import (
        PlayerInfo,
        SgfPlayerInfo,
        extract_player_info_for_user,
    )

    black = info.get("black") or {}
    white = info.get("white") or {}
    if not isinstance(black, dict):
        black = {}
    if not isinstance(white, dict):
        white = {}
    sgf_info = SgfPlayerInfo(
        black=PlayerInfo(name=black.get("name"), rank=black.get("rank")),
        white=PlayerInfo(name=white.get("name"), rank=white.get("rank")),
        sgf_path=str(karte_path),
    )
    return extract_player_info_for_user(sgf_info, default_user)
