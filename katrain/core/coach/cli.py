"""Phase 214-A: CLI tool for LLM prompt generation.

Standalone CLI that builds an LLM prompt from a Karte JSON file.
Does NOT require Kivy startup — safe to invoke from a terminal.

Usage::

    # 1. Generate the Karte JSON (in the GUI):
    #    KaTrain → Analysis → Export Karte → reports/karte/karte_xxx.json
    #
    # 2. Build the LLM prompt from that JSON:
    #
    #    python -m katrain.core.coach.cli <karte.json> --rank 5k --out prompt.md
    #
    # 3. Open prompt.md, copy/paste into Claude / ChatGPT / Gemini.
    #
    # 4. Optionally validate the LLM response:
    #
    #    python -m katrain.core.coach.cli <karte.json> --validate llm_response.txt

This module is intentionally Kivy-free so it can be invoked from a CI
context (Phase 213 e2e tests use the same internal helpers).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from katrain.core.coach.lexicon import get_entry
from katrain.core.coach.llm_validator import validate_llm_output
from katrain.core.coach.master_db import CoachMode
from katrain.core.coach.prompt_builder import (
    PromptConfig,
    build_translation_prompt,
)
from katrain.core.coach.symptom_index import (
    SymptomId,
    detect_auto_symptoms,
    list_llm_required_symptoms,
    lookup_symptom,
)
from katrain.core.coach.tones import select_voice, voice_summary


_DEFAULT_LLM_REQUIRED = (
    SymptomId.TIME_PRESSURE_LOSS,
    SymptomId.SHALLOW_REVIEW,
    SymptomId.AI_OVERLOAD,
)


def _load_karte(path: Path) -> dict[str, Any]:
    """Load and lightly validate a Karte JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Karte JSON not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object, got {type(data).__name__}")
    if "summary" not in data:
        # Phase 203 §9 — older Karte JSONs may lack summary; warn but continue.
        print(f"⚠️ {path}: no 'summary' field; LLM validation features limited.", file=sys.stderr)
    return data


def _auto_detect(karte: dict[str, Any]) -> tuple[SymptomId, ...]:
    """Run auto-detection against an aggregate SymptomContext derived from Karte JSON.

    The detector logic operates per-move, but a Karte JSON gives aggregate
    info. We pick the worst-signalled symptoms heuristically:

    - If weaknesses is populated, use the first category as a detected hint
    - Use any meaning_tag_id from important_moves[*] as a detected hint
    - Always include the "Endgame Precision" baseline if is_endgame implied
    """
    detected: list[SymptomId] = []
    seen: set[SymptomId] = set()

    # 1. From weaknesses[*].category
    for color in ("black", "white"):
        for w in karte.get("weaknesses", {}).get(color, []) or []:
            cat = str(w.get("category", "")).lower()
            # Best-effort mapping
            for sid in SymptomId:
                if sid.value == cat and sid not in seen:
                    detected.append(sid)
                    seen.add(sid)

    # 2. From important_moves[*].meaning_tag_id
    for move in karte.get("important_moves", []) or []:
        mtag = str(move.get("meaning_tag_id", "")).lower()
        for sid in SymptomId:
            if sid.value == mtag and sid not in seen:
                detected.append(sid)
                seen.add(sid)

    # 3. Cap to avoid token bloat (Phase 203 §15 recommendation: 5-7 max).
    return tuple(detected[:7])


def build_prompt(
    karte: dict[str, Any],
    *,
    rank: str | None = None,
    avg_points_lost: float | None = None,
    include_expanded: bool = True,
    detected_ids: tuple[SymptomId, ...] | None = None,
    llm_required_ids: tuple[SymptomId, ...] | None = None,
) -> Any:
    """Build an LlmPrompt from a Karte JSON dict (CLI helper).

    Returns the LlmPrompt produced by ``build_translation_prompt``.
    Caller decides what to do with ``prompt.full_markdown``.
    """
    voice = select_voice(rank, avg_points_lost=avg_points_lost)
    # Map voice -> mode via simple lookup
    from katrain.core.coach.tones import modes_for_voice

    modes = modes_for_voice(voice)
    if modes:
        mode = modes[0]
    else:
        mode = CoachMode.INTERMEDIATE

    if detected_ids is None:
        detected_ids = _auto_detect(karte)
    if llm_required_ids is None:
        # Default: include a small set of LLM-required symptoms the user
        # should consider. They become "candidate" hints in the prompt.
        llm_required_ids = _DEFAULT_LLM_REQUIRED

    cfg = PromptConfig(
        voice=voice,
        mode=mode,
        detected_symptom_ids=detected_ids,
        llm_required_symptom_ids=llm_required_ids,
        include_expanded=include_expanded,
        schema_version=str(karte.get("schema_version", "unknown")),
        player_rank_str=rank,
        average_points_lost=avg_points_lost,
    )
    return build_translation_prompt(karte, cfg)


def cmd_build(args: argparse.Namespace) -> int:
    """Sub-command: build an LLM prompt and write to file or stdout."""
    karte = _load_karte(Path(args.karte_json))
    prompt = build_prompt(
        karte,
        rank=args.rank,
        avg_points_lost=args.avg_loss,
        include_expanded=not args.no_expanded,
    )
    output = prompt.full_markdown
    if args.out:
        out_path = Path(args.out)
        out_path.write_text(output, encoding="utf-8")
        print(
            f"✅ Wrote prompt to {out_path} ({len(output)} chars, "
            f"{len(prompt.referenced_symptom_ids)} symptoms, "
            f"{len(prompt.referenced_lexicon_ids)} lexicon entries)"
        )
    else:
        # Print summary line to stderr, full prompt to stdout.
        print(
            f"# voice={args.rank or 'default'} → "
            f"{voice_summary(prompt.config.voice)}; "
            f"{len(prompt.referenced_symptom_ids)} symptoms; "
            f"{len(prompt.referenced_lexicon_ids)} lex entries",
            file=sys.stderr,
        )
        sys.stdout.write(output)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Sub-command: validate an LLM response against the Karte JSON."""
    karte = _load_karte(Path(args.karte_json))
    llm_text = Path(args.llm_response).read_text(encoding="utf-8")

    # Reuse the same prompt config so the validator sees the same symptom
    # ground truth.
    prompt = build_prompt(
        karte,
        rank=args.rank,
        avg_points_lost=args.avg_loss,
        include_expanded=not args.no_expanded,
    )
    report = validate_llm_output(
        llm_text,
        karte,
        prompt,
        config=prompt.config,
    )

    # Render report as Markdown
    lines = [
        f"# LLM Output Validation Report",
        f"",
        f"**Status**: {report.summary_line()}",
        f"",
        f"**High**: {report.high_count} · **Medium**: {report.medium_count} · **Low**: {report.low_count}",
        f"",
    ]
    if report.referenced_symptom_ids:
        lines.append(f"**Referenced symptom ids**: {', '.join(report.referenced_symptom_ids)}")
    if report.referenced_move_numbers:
        lines.append(f"**Referenced move numbers**: {report.referenced_move_numbers}")
    if report.referenced_points_lost:
        lines.append(f"**Referenced pointsLost**: {report.referenced_points_lost}")
    if report.issues:
        lines.append("")
        lines.append("## Issues")
        lines.append("")
        for issue in report.issues:
            lines.append(
                f"- [{issue.severity.value.upper()}] **{issue.kind}**: {issue.message}"
            )
    output = "\n".join(lines) + "\n"

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"✅ Wrote validation report to {args.out}")
    else:
        sys.stdout.write(output)
    return 0 if report.is_clean else 1


def cmd_symptoms(args: argparse.Namespace) -> int:
    """Sub-command: list all symptoms and their detection status."""
    from katrain.core.coach.symptom_index import list_all_symptoms

    for symptom in list_all_symptoms():
        marker = "🟢" if symptom.auto_detected else "🟡"
        lex = ", ".join(symptom.related_lexicon_ids) or "(none)"
        line = (
            f"{marker} {symptom.id.value:36s} | "
            f"{symptom.ja_label:24s} | "
            f"lex=[{lex}]"
        )
        print(line)
    return 0


def cmd_lexicon(args: argparse.Namespace) -> int:
    """Sub-command: lookup a Lexicon entry by id."""
    entry = get_entry(args.entry_id)
    if entry is None:
        print(f"❌ No entry found for id: {args.entry_id}", file=sys.stderr)
        return 1
    output = (
        f"【{entry.ja_term} ({entry.id})】\n"
        f"定義: {entry.ja_one_liner}\n"
        f"詳細: {entry.ja_short}\n"
        f"注意点: {' / '.join(entry.pitfalls)}\n"
    )
    if entry.ja_expanded:
        output += f"拡張: {entry.ja_expanded}\n"
    sys.stdout.write(output)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="katrain.core.coach.cli",
        description="myKatrain LLM-coach pipeline CLI (Phase 214-A)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # build
    p_build = sub.add_parser("build", help="Build an LLM prompt from a Karte JSON")
    p_build.add_argument("karte_json", help="Path to Karte JSON file")
    p_build.add_argument(
        "--rank",
        help="Player rank (e.g. '5k', '3d')",
    )
    p_build.add_argument(
        "--avg-loss",
        type=float,
        help="Average pointsLost (loss-correction signal)",
    )
    p_build.add_argument(
        "--no-expanded",
        action="store_true",
        help="Omit ja_expanded from lexicon entries (shorter prompt)",
    )
    p_build.add_argument(
        "--out",
        help="Write prompt to this file (default: stdout)",
    )
    p_build.set_defaults(func=cmd_build)

    # validate
    p_val = sub.add_parser(
        "validate", help="Validate an LLM response against the Karte JSON"
    )
    p_val.add_argument("karte_json", help="Path to Karte JSON file")
    p_val.add_argument("llm_response", help="Path to LLM-generated text")
    p_val.add_argument("--rank", help="Player rank (must match build)")
    p_val.add_argument("--avg-loss", type=float)
    p_val.add_argument("--no-expanded", action="store_true")
    p_val.add_argument("--out", help="Write report to file (default: stdout)")
    p_val.set_defaults(func=cmd_validate)

    # symptoms (debugging)
    p_sym = sub.add_parser("symptoms", help="List all symptoms + detection status")
    p_sym.set_defaults(func=cmd_symptoms)

    # lexicon (debugging)
    p_lex = sub.add_parser("lexicon", help="Print a Lexicon entry by id")
    p_lex.add_argument("entry_id", help="Lexicon entry id (e.g. 'liberty')")
    p_lex.set_defaults(func=cmd_lexicon)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns process exit code (0 success, non-zero failure)."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())