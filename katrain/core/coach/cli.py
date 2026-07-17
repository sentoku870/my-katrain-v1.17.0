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
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from katrain.common.rank import canonical_rank_key
from katrain.core.coach.karte_detector import detect_symptoms_from_karte
from katrain.core.coach.lexicon import get_entry
from katrain.core.coach.llm_validator import validate_llm_output
from katrain.core.coach.master_db import CoachMode
from katrain.core.coach.prompt_builder import (
    PromptConfig,
    build_translation_prompt,
)
from katrain.core.coach.symptom_index import (
    SymptomId,
)
from katrain.core.coach.tones import select_voice, voice_summary

_DEFAULT_LLM_REQUIRED = (
    SymptomId.TIME_PRESSURE_LOSS,
    SymptomId.SHALLOW_REVIEW,
    SymptomId.AI_OVERLOAD,
)


def _load_karte(path: Path) -> dict[str, Any]:
    """Load and lightly validate a Karte / Summary JSON file.

    Auto-detects whether the file is a single-game Karte or a
    multi-game Summary (Phase 221). Summary JSONs are projected into
    a Karte-shaped view via ``normalize_summary_to_karte_shape`` so
    the downstream pipeline can consume them uniformly.

    Returns the (possibly projected) dict.
    """
    from katrain.core.coach.json_type import (
        detect_json_type,
        normalize_summary_to_karte_shape,
    )

    if not path.exists():
        raise FileNotFoundError(f"Karte JSON not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object, got {type(data).__name__}")

    jtype = detect_json_type(data)
    if jtype == "unknown":
        print(
            f"⚠️ {path}: unrecognised JSON shape; treating as karte.",
            file=sys.stderr,
        )
        return data
    if jtype == "summary":
        print(
            f"ℹ️  {path}: detected multi-game Summary; projecting to karte shape.",
            file=sys.stderr,
        )
        return normalize_summary_to_karte_shape(data)
    # karte
    if "summary" not in data:
        # Phase 203 §9 — older Karte JSONs may lack summary; warn but continue.
        print(
            f"⚠️ {path}: no 'summary' field; LLM validation features limited.",
            file=sys.stderr,
        )
    return data


def _validate_rank_arg(rank: str | None) -> str | None:
    """Validate / canonicalise the ``--rank`` CLI argument (Phase 240).

    Returns:
        - ``None`` when the user did not pass ``--rank`` (default behaviour).
        - The canonical ASCII key (e.g. ``"5k"`` / ``"4d"``) when the
          input matches :data:`_RANK_ALIASES` or :data:`_RANK_ORDER`
          after the standard normalisation (kanji, full-width, aliases
          like ``"10段" → "9d"``).
        - Raises ``SystemExit`` with a usage message when the input is
          non-empty but does not match any known rank notation. This
          guards against typos that would otherwise be forwarded as
          garbage to the LLM prompt and produce a confused review.

    Examples:
        >>> _validate_rank_arg(None)
        None
        >>> _validate_rank_arg("5k")
        '5k'
        >>> _validate_rank_arg("4段")
        '4d'
        >>> _validate_rank_arg("10段")  # alias for 9d
        '9d'
        >>> _validate_rank_arg("")       # treated as "not provided"
        None
    """
    if rank is None:
        return None
    stripped = rank.strip()
    if not stripped:
        return None
    key = canonical_rank_key(stripped)
    if not key:
        print(
            f"❌ Invalid --rank '{rank}'. "
            f"Expected formats: '5k', '4d', '5段', '10級', "
            f"'beginner' / 'standard' / 'advanced' / 'expert' / 'master' / 'dan', etc.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


def build_prompt(
    karte: dict[str, Any],
    *,
    rank: str | None = None,
    avg_points_lost: float | None = None,
    include_expanded: bool = True,
    detected_ids: tuple[SymptomId, ...] | None = None,
    llm_required_ids: tuple[SymptomId, ...] | None = None,
    player_color: str | None = None,
) -> Any:
    """Build an LlmPrompt from a Karte JSON dict (CLI helper).

    Returns the LlmPrompt produced by ``build_translation_prompt``.
    Caller decides what to do with ``prompt.full_markdown``.

    Detection:
        When ``detected_ids`` is None, uses Phase 215's
        ``detect_symptoms_from_karte`` for proper Karte-aware detection
        (weakness categories + per-move SymptomContext).

    Phase 225.6: ``player_color`` (``"B"`` / ``"W"`` / ``None``) is
    forwarded to :class:`PromptConfig` so the SystemInstruction tells
    the LLM which side to focus on.
    """
    voice = select_voice(rank, avg_points_lost=avg_points_lost)
    from katrain.core.coach.tones import modes_for_voice

    modes = modes_for_voice(voice)
    mode = modes[0] if modes else CoachMode.INTERMEDIATE

    if detected_ids is None:
        detected_ids = detect_symptoms_from_karte(karte)
    if llm_required_ids is None:
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
        player_color=player_color,
    )
    return build_translation_prompt(karte, cfg)


def cmd_build(args: argparse.Namespace) -> int:
    """Sub-command: build an LLM prompt and write to file or stdout.

    Phase 227-A: when ``--summary-mode`` is set, uses the multi-game
    summary prompt builder (:func:`build_summary_weakness_prompt`)
    instead of the single-game Karte prompt. The file MUST be a summary
    JSON; otherwise the command errors out.
    """
    raw_data = _load_raw_json(Path(args.karte_json))

    if args.summary_mode:
        return _cmd_build_summary(raw_data, args)

    # Default path: existing Karte-aware behaviour. ``_load_karte``
    # already auto-projects summaries into karte shape.
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


def _load_raw_json(path: Path) -> dict[str, Any]:
    """Phase 227-A: load a JSON file without any projection.

    Used by ``--summary-mode`` to inspect the original shape before
    deciding which prompt builder to invoke.
    """
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object, got {type(data).__name__}")
    return data


def _cmd_build_summary(raw_data: dict[str, Any], args: argparse.Namespace) -> int:
    """Phase 227-A: ``--summary-mode`` path.

    Uses :func:`build_summary_weakness_prompt` to generate a multi-game
    pattern-extraction prompt. Errors if the file is not a summary.
    """
    from katrain.core.coach.json_type import detect_json_type
    from katrain.core.coach.summary_prompt_builder import (
        SummaryPromptConfig,
        build_summary_weakness_prompt,
    )
    from katrain.core.coach.tones import modes_for_voice, select_voice

    jtype = detect_json_type(raw_data)
    if jtype != "summary":
        print(
            f"❌ --summary-mode requires a multi-game Summary JSON, "
            f"but detection returned '{jtype}'. "
            f"Remove --summary-mode to use the single-game Karte path.",
            file=sys.stderr,
        )
        return 2

    voice = select_voice(args.rank)
    modes = modes_for_voice(voice)
    mode = modes[0] if modes else CoachMode.INTERMEDIATE

    cfg = SummaryPromptConfig(
        voice=voice,
        mode=mode,
        games_analyzed=raw_data.get("meta", {}).get("games_analyzed", 0) or 0,
        player_name=args.player or None,
        player_rank=args.rank,
        schema_version=str(raw_data.get("schema_version", "unknown")),
    )
    prompt = build_summary_weakness_prompt(raw_data, cfg)
    output = prompt.full_markdown
    if args.out:
        out_path = Path(args.out)
        out_path.write_text(output, encoding="utf-8")
        print(
            f"✅ Wrote summary prompt to {out_path} ({len(output)} chars, "
            f"{len(prompt.referenced_patterns)} patterns, "
            f"{cfg.games_analyzed} games)"
        )
    else:
        print(
            f"# summary-mode voice={args.rank or 'default'} → "
            f"{voice_summary(voice)}; "
            f"{len(prompt.referenced_patterns)} patterns; "
            f"{cfg.games_analyzed} games; "
            f"focus={args.player or '全体俯瞰'}",
            file=sys.stderr,
        )
        sys.stdout.write(output)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Sub-command: validate an LLM response against a Karte / Summary JSON.

    Phase 227-B: when ``--summary-mode`` is set, uses the multi-game
    summary validator (:func:`validate_summary_llm_output`) instead of
    the per-move Karte validator. The file MUST be a summary JSON;
    otherwise the command errors out.

    Default behaviour (no flag) auto-detects the JSON type and routes
    to the appropriate validator.
    """
    raw_data = _load_raw_json(Path(args.karte_json))

    if args.summary_mode:
        return _cmd_validate_summary(raw_data, args)

    # Default: existing Karte-aware behaviour. The summary branch
    # below is auto-detected when the file is actually a summary.
    jtype = _detect_jtype(raw_data)
    if jtype == "summary":
        return _cmd_validate_summary(raw_data, args)

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
        "# LLM Output Validation Report",
        "",
        f"**Status**: {report.summary_line()}",
        "",
        f"**High**: {report.high_count} · **Medium**: {report.medium_count} · **Low**: {report.low_count}",
        "",
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
            lines.append(f"- [{issue.severity.value.upper()}] **{issue.kind}**: {issue.message}")
    output = "\n".join(lines) + "\n"

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"✅ Wrote validation report to {args.out}")
    else:
        sys.stdout.write(output)
    return 0 if report.is_clean else 1


def _detect_jtype(data: dict[str, Any]) -> str:
    """Thin wrapper around :func:`detect_json_type` for cli internals."""
    from katrain.core.coach.json_type import detect_json_type

    return detect_json_type(data)


def _cmd_validate_summary(raw_data: dict[str, Any], args: argparse.Namespace) -> int:
    """Phase 227-B: summary-mode validate path.

    Uses :func:`validate_summary_llm_output` to validate a multi-game
    pattern-extraction LLM response. Errors if the file is not a
    summary.
    """
    from katrain.core.coach.summary_prompt_builder import (
        SummaryPromptConfig,
        build_summary_weakness_prompt,
    )
    from katrain.core.coach.summary_validator import validate_summary_llm_output
    from katrain.core.coach.tones import modes_for_voice, select_voice

    jtype = _detect_jtype(raw_data)
    if jtype != "summary":
        print(
            f"❌ --summary-mode requires a multi-game Summary JSON, but detection returned '{jtype}'.",
            file=sys.stderr,
        )
        return 2

    voice = select_voice(args.rank)
    modes = modes_for_voice(voice)
    mode = modes[0] if modes else CoachMode.INTERMEDIATE

    cfg = SummaryPromptConfig(
        voice=voice,
        mode=mode,
        games_analyzed=raw_data.get("meta", {}).get("games_analyzed", 0) or 0,
        player_name=getattr(args, "player", None) or None,
        player_rank=args.rank,
        schema_version=str(raw_data.get("schema_version", "unknown")),
    )
    prompt = build_summary_weakness_prompt(raw_data, cfg)
    llm_text = Path(args.llm_response).read_text(encoding="utf-8")
    report = validate_summary_llm_output(llm_text, raw_data, prompt)

    # Render report as Markdown
    lines = [
        "# LLM Output Validation Report (Summary Mode)",
        "",
        f"**Status**: {report.summary_line()}",
        "",
        f"**High**: {report.high_count} · **Medium**: {report.medium_count} · **Low**: {report.low_count}",
        "",
    ]
    if report.referenced_categories:
        lines.append(f"**Referenced patterns**: {', '.join(report.referenced_categories)}")
    if report.referenced_phases:
        lines.append(f"**Referenced phases**: {', '.join(report.referenced_phases)}")
    if report.referenced_move_numbers:
        lines.append(f"**Forbidden move refs**: {report.referenced_move_numbers}")
    if report.referenced_game_ids:
        lines.append(f"**Specific game IDs**: {', '.join(report.referenced_game_ids)}")
    if report.issues:
        lines.append("")
        lines.append("## Issues")
        lines.append("")
        for issue in report.issues:
            lines.append(f"- [{issue.severity.value.upper()}] **{issue.kind}**: {issue.message}")
    output = "\n".join(lines) + "\n"

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"✅ Wrote summary validation report to {args.out}")
    else:
        sys.stdout.write(output)
    return 0 if report.is_clean else 1


def cmd_symptoms(args: argparse.Namespace) -> int:
    """Sub-command: list all symptoms and their detection status."""
    from katrain.core.coach.symptom_index import list_all_symptoms

    for symptom in list_all_symptoms():
        marker = "🟢" if symptom.auto_detected else "🟡"
        lex = ", ".join(symptom.related_lexicon_ids) or "(none)"
        line = f"{marker} {symptom.id.value:36s} | {symptom.ja_label:24s} | lex=[{lex}]"
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


def cmd_calibrate(args: argparse.Namespace) -> int:
    """Sub-command: run the golden fixture suite and report detector calibration.

    Iterates over ``calibration_fixtures.ALL_FIXTURES`` and reports for
    each: name, expected symptom ids, actually-fired symptom ids, and
    pass/fail. The current implementation does NOT mutate detector
    thresholds — it's a read-only verifier that doubles as the user's
    diagnostic command.

    Exit code:
    - 0 when all fixtures pass
    - 1 when any fixture fails
    """
    from katrain.core.coach.calibration_fixtures import (
        ALL_FIXTURES,
        list_fixture_names,
    )
    from katrain.core.coach.json_type import (
        detect_json_type,
    )
    from katrain.core.coach.karte_detector import detect_symptoms_from_karte

    if args.fixture:
        names: list[str] | tuple[str, ...] = [args.fixture]
    else:
        names = list(list_fixture_names())

    lines: list[str] = ["# Coach Detector Calibration", ""]
    fail_count = 0
    pass_count = 0

    for name in names:
        if name not in ALL_FIXTURES:
            lines.append(f"⚠️ Unknown fixture: {name}")
            fail_count += 1
            continue
        fix = ALL_FIXTURES[name]
        # Phase 227-E: summary fixtures pin the pattern extraction
        # and prompt/validator rendering, NOT the per-move symptom
        # detectors. The karte projection of a summary has different
        # semantics (e.g. the projected ``loss_progression`` is
        # the ``all`` bucket, not the per-game list), so running
        # ``detect_symptoms_from_karte`` on a projected summary
        # would produce meaningless results. We skip symptom
        # detection entirely for summary fixtures and verify
        # the pattern extractor instead.
        if detect_json_type(fix.karte) == "summary":
            from katrain.core.coach.json_type import (
                extract_summary_weakness_patterns,
            )

            lines.append(f"## ⏭️  {fix.name} (summary, skipped symptom detection)")
            lines.append(fix.description)
            lines.append("")
            lines.append("(summary fixtures pin pattern extraction, not per-move symptoms)")
            patterns = extract_summary_weakness_patterns(fix.karte)
            lines.append(f"- extracted patterns: {len(patterns)}")
            lines.append("- expected_symptom_ids: {} (n/a for summaries)")
            lines.append(f"- notes: {fix.tolerance_notes}")
            lines.append("")
            pass_count += 1
            continue
        fired = set(detect_symptoms_from_karte(fix.karte))
        expected = set(fix.expected_symptom_ids)
        ok = fired == expected

        marker = "✅" if ok else "❌"
        lines.append(f"## {marker} {fix.name}")
        lines.append(fix.description)
        lines.append("")
        lines.append(f"- expected: {[s.value for s in sorted(expected, key=lambda x: x.value)]}")
        lines.append(f"- fired:    {[s.value for s in sorted(fired, key=lambda x: x.value)]}")
        if not ok:
            missing = expected - fired
            extra = fired - expected
            if missing:
                lines.append(f"- MISSING:  {[s.value for s in missing]}")
            if extra:
                lines.append(f"- EXTRA:    {[s.value for s in extra]}")
            fail_count += 1
        else:
            pass_count += 1
        if fix.tolerance_notes:
            lines.append(f"- notes: {fix.tolerance_notes}")
        lines.append("")

    lines.extend(
        [
            "## Summary",
            f"- passed: {pass_count}",
            f"- failed: {fail_count}",
            f"- total:  {pass_count + fail_count}",
        ]
    )

    output = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"✅ Wrote calibration report to {args.out}")
    else:
        sys.stdout.write(output)

    return 0 if fail_count == 0 else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    """Sub-command: detailed overview of a Karte JSON.

    Renders a Markdown report with:
    - Schema version + meta summary
    - Aggregate metrics (avg points_lost, winrate/scoreLead correlation,
      longest streak, total streak loss, weakness concentration, etc.)
    - All auto-detected symptoms (per-move + weakness + streak)
    - Winrate/scoreLead pairs (count + first/last)

    Phase 217: this is the "diagnose your karte" CLI helper that the
    LLM-coach pipeline uses internally as a debugging view.
    """
    from katrain.core.coach.karte_detector import (
        detect_symptoms_from_karte,
        extract_avg_points_lost,
        extract_avg_streak_loss,
        extract_avg_winrate_lost,
        extract_consecutive_loss_run,
        extract_critical_move_count,
        extract_game_count,
        extract_longest_streak,
        extract_max_overall_difficulty,
        extract_max_score_stdev,
        extract_max_winrate_drop,
        extract_streak_count,
        extract_total_streak_loss,
        extract_weakness_concentration,
        extract_winrate_scorelead_correlation,
        extract_winrate_scorelead_pairs,
    )
    from katrain.core.coach.tones import modes_for_voice, select_voice

    karte = _load_karte(Path(args.karte_json))

    lines: list[str] = ["# Karte Analysis", ""]

    # Meta
    meta = karte.get("meta", {}) or {}
    lines.append("## Meta")
    lines.append(f"- schema_version: `{karte.get('schema_version', 'unknown')}`")
    lines.append(f"- game_id: `{meta.get('game_id', 'unknown')}`")
    lines.append(f"- players: {meta.get('players', {})}")
    lines.append(f"- board_size: {meta.get('board_size', '?')}")
    lines.append(f"- result: `{meta.get('result', '?')}`")
    lines.append("")

    # Aggregate metrics
    lines.append("## Aggregate Metrics")
    avg_loss = extract_avg_points_lost(karte)
    if avg_loss is not None:
        lines.append(f"- avg_points_lost: {avg_loss:.2f}")
    avg_wr = extract_avg_winrate_lost(karte)
    if avg_wr is not None:
        lines.append(f"- avg_winrate_lost: {avg_wr:.4f}")
    max_wr = extract_max_winrate_drop(karte)
    if max_wr is not None:
        lines.append(f"- max_winrate_drop: {max_wr:.4f}")
    max_std = extract_max_score_stdev(karte)
    if max_std is not None:
        lines.append(f"- max_score_stdev: {max_std:.2f}")
    max_diff = extract_max_overall_difficulty(karte)
    if max_diff is not None:
        lines.append(f"- max_overall_difficulty: {max_diff:.2f}")
    crit = extract_critical_move_count(karte)
    if crit:
        lines.append(f"- critical_move_count: {crit}")
    wc = extract_weakness_concentration(karte)
    if wc is not None:
        lines.append(f"- weakness_concentration: {wc:.2%}")
    gc = extract_game_count(karte)
    if gc is not None:
        lines.append(f"- game_count: {gc}")
    lines.append("")

    # Streak metrics
    lines.append("## Streak Metrics")
    longest = extract_longest_streak(karte)
    total = extract_total_streak_loss(karte)
    sc = extract_streak_count(karte)
    lr = extract_consecutive_loss_run(karte)
    avg_s = extract_avg_streak_loss(karte)
    lines.append(f"- longest_streak: {longest}")
    lines.append(f"- total_streak_loss: {total:.2f}")
    lines.append(f"- streak_count: {sc}")
    lines.append(f"- consecutive_loss_run: {lr}")
    lines.append(f"- avg_streak_loss: {avg_s:.2f}")
    lines.append("")

    # Correlation
    corr = extract_winrate_scorelead_correlation(karte)
    pairs = extract_winrate_scorelead_pairs(karte)
    lines.append("## Correlation")
    if corr is None:
        lines.append("- winrate / scoreLead correlation: (insufficient data)")
    else:
        lines.append(f"- winrate / scoreLead correlation: **{corr:+.3f}**")
    lines.append(f"- numeric pairs: {len(pairs)}")
    lines.append("")

    # Voice (would-be-prompt configuration)
    voice = select_voice(args.rank)
    modes = modes_for_voice(voice)
    lines.append("## Would-be Coach Configuration")
    lines.append(f"- rank_arg: `{args.rank or '(default)'}`")
    lines.append(f"- voice: `{voice.value}` ({voice.name})")
    if modes:
        lines.append(f"- modes: {[m.name for m in modes]}")
    lines.append("")

    # Detected symptoms
    fired = detect_symptoms_from_karte(karte)
    lines.append("## Detected Symptoms")
    lines.append(f"- count: {len(fired)}")
    if fired:
        lines.append("")
        for sid in fired:
            lines.append(f"  - `{sid.value}`")
    lines.append("")

    output = "\n".join(lines) + "\n"

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"✅ Wrote analysis to {args.out}")
    else:
        sys.stdout.write(output)
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    """Sub-command: trace the detection pipeline step-by-step (Phase 220).

    Shows which detection source fired each symptom, useful for debugging
    threshold tuning. Sources are:
    - per_move: SymptomContext-based detectors
    - weakness: weakness[*].category → SymptomId mapping
    - streak: Phase 216 streak / loss_run aggregators
    - aggregate: Phase 217 placeholder (currently no symptoms fired here)
    """
    from katrain.core.coach.karte_detector import (
        _symptom_ids_from_aggregate_patterns,
        _symptom_ids_from_streaks,
        _symptom_ids_from_weakness_categories,
        build_symptom_context_from_karte,
    )
    from katrain.core.coach.symptom_index import detect_auto_symptoms

    karte = _load_karte(Path(args.karte_json))

    # Per-source detection
    ctx = build_symptom_context_from_karte(karte)
    per_move = set(detect_auto_symptoms(ctx))
    from_categories = set(_symptom_ids_from_weakness_categories(karte))
    from_streaks = set(_symptom_ids_from_streaks(karte))
    from_aggregate = set(_symptom_ids_from_aggregate_patterns(karte))
    combined = per_move | from_categories | from_streaks | from_aggregate

    # Build sets with sources
    sources: dict[Any, list[str]] = {}
    for sid in per_move:
        sources.setdefault(sid, []).append("per_move")
    for sid in from_categories:
        sources.setdefault(sid, []).append("weakness_category")
    for sid in from_streaks:
        sources.setdefault(sid, []).append("streak")
    for sid in from_aggregate:
        sources.setdefault(sid, []).append("aggregate")

    lines: list[str] = ["# Detection Pipeline Trace (Phase 220)", ""]
    lines.append("## Sources")
    lines.append(f"- per_move:          {[s.value for s in sorted(per_move, key=lambda x: x.value)]}")
    lines.append(f"- weakness_category: {[s.value for s in sorted(from_categories, key=lambda x: x.value)]}")
    lines.append(f"- streak:           {[s.value for s in sorted(from_streaks, key=lambda x: x.value)]}")
    lines.append(f"- aggregate:        {[s.value for s in sorted(from_aggregate, key=lambda x: x.value)]}")
    lines.append(f"- **union**:          {[s.value for s in sorted(combined, key=lambda x: x.value)]}")
    lines.append("")

    lines.append("## Per-Symptom Sources")
    for sid in sorted(combined, key=lambda x: x.value):
        srcs = sources.get(sid, [])
        lines.append(f"- `{sid.value}`: {', '.join(srcs)}")
    lines.append("")

    lines.append("## SymptomContext Snapshot")
    lines.append(f"- avg_points_lost:    {ctx.avg_points_lost}")
    lines.append(f"- score_stdev:        {ctx.score_stdev}")
    lines.append(f"- overall_difficulty: {ctx.overall_difficulty}")
    lines.append(f"- is_endgame:         {ctx.is_endgame}")
    lines.append(f"- good_move_count:    {ctx.good_move_count}")
    lines.append(f"- weakness_concentration: {ctx.weakness_concentration}")
    lines.append(f"- game_count:         {ctx.game_count}")
    lines.append(f"- meaning_tags:       {[m.value for m in ctx.meaning_tag_ids]}")
    lines.append(f"- hint_categories:    {[h.value for h in ctx.hint_categories]}")
    lines.append("")

    output = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"✅ Wrote trace to {args.out}")
    else:
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
    # Phase 227-A: multi-game summary mode
    p_build.add_argument(
        "--summary-mode",
        action="store_true",
        help=(
            "Build a multi-game Summary prompt (pattern extraction) "
            "instead of a single-game Karte prompt. Requires the input "
            "to be a multi-game Summary JSON."
        ),
    )
    p_build.add_argument(
        "--player",
        help=(
            "Player name to focus on in summary-mode (default: bird's-eye "
            "view across all players). Only meaningful with --summary-mode."
        ),
    )
    p_build.set_defaults(func=cmd_build)

    # validate
    p_val = sub.add_parser("validate", help="Validate an LLM response against the Karte JSON")
    p_val.add_argument("karte_json", help="Path to Karte JSON file")
    p_val.add_argument("llm_response", help="Path to LLM-generated text")
    p_val.add_argument("--rank", help="Player rank (must match build)")
    p_val.add_argument("--avg-loss", type=float)
    p_val.add_argument("--no-expanded", action="store_true")
    p_val.add_argument("--out", help="Write report to file (default: stdout)")
    # Phase 227-B: multi-game summary mode (auto-detected by default)
    p_val.add_argument(
        "--summary-mode",
        action="store_true",
        help=("Force the multi-game Summary validator. Auto-detected by default; explicit only for clarity."),
    )
    p_val.set_defaults(func=cmd_validate)

    # symptoms (debugging)
    p_sym = sub.add_parser("symptoms", help="List all symptoms + detection status")
    p_sym.set_defaults(func=cmd_symptoms)

    # lexicon (debugging)
    p_lex = sub.add_parser("lexicon", help="Print a Lexicon entry by id")
    p_lex.add_argument("entry_id", help="Lexicon entry id (e.g. 'liberty')")
    p_lex.set_defaults(func=cmd_lexicon)

    # analyze (Phase 217)
    p_an = sub.add_parser(
        "analyze",
        help="Print a structured Karte analysis (meta + metrics + symptoms)",
    )
    p_an.add_argument("karte_json", help="Path to Karte JSON file")
    p_an.add_argument(
        "--rank",
        help="Player rank (would-be prompt configuration)",
    )
    p_an.add_argument(
        "--out",
        help="Write analysis to this file (default: stdout)",
    )
    p_an.set_defaults(func=cmd_analyze)

    # calibrate (Phase 219)
    p_cal = sub.add_parser(
        "calibrate",
        help="Run golden-fixture calibration suite (Phase 218/219)",
    )
    p_cal.add_argument(
        "--fixture",
        help="Run a single fixture by name (default: all fixtures)",
    )
    p_cal.add_argument(
        "--out",
        help="Write calibration report to file (default: stdout)",
    )
    p_cal.set_defaults(func=cmd_calibrate)

    # trace (Phase 220)
    p_tr = sub.add_parser(
        "trace",
        help="Trace detection pipeline: which source fired each symptom",
    )
    p_tr.add_argument("karte_json", help="Path to Karte JSON file")
    p_tr.add_argument(
        "--out",
        help="Write trace to file (default: stdout)",
    )
    p_tr.set_defaults(func=cmd_trace)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns process exit code (0 success, non-zero failure)."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    # Phase 240: validate / canonicalise ``--rank`` once at the entry
    # point so every subcommand sees the same normalised value. Empty
    # / None → None (default behaviour). Invalid → SystemExit(2) with
    # a usage message. Subcommands that don't accept ``--rank`` (e.g.
    # ``symptoms``, ``lexicon``, ``calibrate``, ``trace``) simply
    # don't have the attribute; ``getattr`` returns ``None`` and
    # validation passes through.
    args.rank = _validate_rank_arg(getattr(args, "rank", None))
    ret: int = args.func(args)
    return ret


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
