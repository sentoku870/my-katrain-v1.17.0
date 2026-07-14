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
from typing import TYPE_CHECKING, Any

from katrain.core.constants import OUTPUT_ERROR
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
        return json.load(f)


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


def _render_validation_report(report: Any) -> str:
    """Render a :class:`ValidationReport` as a multi-line Markdown string."""
    lines: list[str] = [
        f"**{i18n._('mykatrain:llm-coach:status')}**: {report.summary_line()}",
        f"**HIGH**: {report.high_count} · "
        f"**MEDIUM**: {report.medium_count} · "
        f"**LOW**: {report.low_count}",
        "",
    ]
    if report.referenced_symptom_ids:
        lines.append(
            f"**{i18n._('mykatrain:llm-coach:referenced-symptoms')}**: "
            f"{', '.join(report.referenced_symptom_ids)}"
        )
    if report.referenced_move_numbers:
        lines.append(
            f"**{i18n._('mykatrain:llm-coach:referenced-moves')}**: "
            f"{list(report.referenced_move_numbers)}"
        )
    if report.referenced_points_lost:
        lines.append(
            f"**{i18n._('mykatrain:llm-coach:referenced-points-lost')}**: "
            f"{list(report.referenced_points_lost)}"
        )
    if report.referenced_lexicon_ids:
        lines.append(
            f"**{i18n._('mykatrain:llm-coach:referenced-lexicon')}**: "
            f"{', '.join(report.referenced_lexicon_ids)}"
        )
    if report.issues:
        lines.append("")
        lines.append(f"## {i18n._('mykatrain:llm-coach:issues')}")
        lines.append("")
        for issue in report.issues:
            lines.append(f"- [{issue.severity.value.upper()}] **{issue.kind}**: {issue.message}")
    return "\n".join(lines) + "\n"


def find_latest_karte(ctx: FeatureContext) -> Path | None:
    """Locate the most recent ``karte_*.json`` in the configured output dir.

    Returns ``None`` if the directory does not exist or no karte report is
    present (in which case the popup will leave the path empty for the user
    to fill in manually).
    """
    from katrain.common.platform import resolve_output_directory
    from katrain.gui.features.report_navigator import get_latest_report

    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    config_dir = mykatrain_settings.get("karte_output_directory", "")
    output_dir = resolve_output_directory(config_dir)

    if not output_dir.is_dir():
        return None

    report = get_latest_report(output_dir)
    if report is None or report.report_type != "karte":
        return None
    return report.path


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
    if (
        info
        and isinstance(info, dict)
        and isinstance(info.get("black"), dict)
        and isinstance(info.get("white"), dict)
    ):
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
    """Phase 225.6 / Phase 226-B (B4): determine which side the
    configured default user plays and return ``(color, rank)``.

    ``color`` is ``"B"`` / ``"W"`` / ``None``; ``rank`` is the matching
    rank string from the Karte / SGF. ``None`` is returned when the
    user setting is empty or no match is found.

    Phase 226-B (B4): the caller may pass an already-loaded
    ``player_info`` dict (as returned by :func:`detect_player_info`) to
    avoid reading & parsing the same JSON a second time. When
    ``player_info`` is ``None`` we fall back to the previous behaviour
    of reading the file ourselves.
    """
    if ctx is None:
        return None, None
    default_user = (ctx.config("mykatrain_settings") or {}).get(
        "default_user_name", ""
    )
    if not default_user:
        return None, None
    info = player_info if player_info is not None else detect_player_info(ctx, karte_path)
    from katrain.core.coach.sgf_player_info import extract_player_info_for_user

    pseudo = _SgfInfoLike(info["black"], info["white"])
    return extract_player_info_for_user(pseudo, default_user)


class _SgfInfoLike:
    """Bridge: convert our ``detect_player_info`` dict shape into
    the :class:`SgfPlayerInfo` interface that
    :func:`extract_player_info_for_user` expects."""

    def __init__(self, black: dict[str, Any], white: dict[str, Any]) -> None:
        from katrain.core.coach.sgf_player_info import PlayerInfo

        self.black = PlayerInfo(name=black.get("name"), rank=black.get("rank"))
        self.white = PlayerInfo(name=white.get("name"), rank=white.get("rank"))
