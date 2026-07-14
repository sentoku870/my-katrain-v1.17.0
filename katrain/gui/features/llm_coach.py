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
    ctx: "FeatureContext | None",
    karte_path: str | Path,
    *,
    rank: str | None = None,
    avg_points_lost: float | None = None,
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
    ctx: "FeatureContext | None",
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


def find_latest_karte(ctx: "FeatureContext") -> Path | None:
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