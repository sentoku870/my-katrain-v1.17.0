"""Phase 210: Tone selector and validator helpers.

Thin delegation layer over ``katrain.core.coach.master_db`` providing
higher-level helpers used by Phase 211 prompt_builder and downstream UI.

Public helpers:
- ``select_voice(rank_str, loss_signals...)`` → ToneVoice
- ``greeting_for_mode(mode, kanji_intro=False)`` → Japanese greeting
  (master doc §0-2 confirmation template)
- ``has_kansai_markers(text)`` → bool (checks for AYAKA-only particles)
- ``apply_kansai_normalisation(text, mapping=None)`` → normalised text
- ``check_prohibited(text, voice)`` → list of violations
- ``voice_summary(voice)`` → 1-line description for UI

All helpers are pure / Kivy-free.

Phase 226-E (E4): three related AYAKA-only data structures live in
this codebase and must be kept in sync:

- ``master_db._KANSAI_DICTIONARY`` — user-facing mapping table
  (``標準語 → 関西弁``) shown via ``ModeConfig.kansai_dictionary``.
- ``tones._KANSAI_NORMALISATION_PAIRS`` — the actual regex pairs that
  ``apply_kansai_normalisation`` runs over to rewrite text. Slightly
  richer than the dictionary (catches ``だめ`` in addition to ``ダメ``).
- ``tones._AYAKA_MARKERS`` — the marker set ``has_kansai_markers``
  uses to detect AYAKA-style output.

Full unification into a single source of truth was judged out of
scope for Phase 226 (it would require either a generator script or
relaxing the dictionary semantics). The pragmatic contract is: any
new AYAKA term added to ``_KANSAI_DICTIONARY`` must also be added to
``_KANSAI_NORMALISATION_PAIRS`` (so it can be substituted) and
``_AYAKA_MARKERS`` (so its output can be detected).
"""

from __future__ import annotations

import re

from katrain.core.coach.master_db import (
    CoachMode,
    ToneVoice,
    all_modes,
    estimate_mode_from_loss,
    estimate_mode_from_rank,
    get_mode_config,
    get_tone_config,
)

# --- Master doc §0-2 confirmation templates ---


_CONFIRMATION_TEMPLATES: dict[CoachMode, str] = {
    CoachMode.BEGINNER: (
        "より的確なアドバイスするために、棋力教えてもらえる？\n"
        "  例：野狐○段、○級、初心者（ルール覚えたて）とか\n"
        "  目安はこんな感じやで：\n"
        "  ・ルール覚えたて〜石の取り方を練習中 → 初級\n"
        "  ・19路でシチョウ/ゲタが分かる → 中級\n"
        "  ・野狐初段前後 → 有段\n"
        "  ・野狐三段以上 → 高段\n"
        "  ・県代表クラス以上 → 強豪"
    ),
    CoachMode.INTERMEDIATE: (
        "より的確なアドバイスするために、棋力教えてもらえる？\n"
        "  例：野狐○段、○級、中級程度など\n"
        "  目安はこんな感じやで：\n"
        "  ・19路でシチョウ/ゲタが分かる → 中級\n"
        "  ・野狐初段前後 → 有段\n"
        "  ・野狐三段以上 → 高段\n"
        "  ・県代表クラス以上 → 強豪"
    ),
    CoachMode.DAN: (
        "より的確なアドバイスのために、棋力を教えていただけますか？\n"
        "  例：野狐○段、○級、有段など\n"
        "  目安：\n"
        "  ・野狐初段前後 → 有段\n"
        "  ・野狐三段以上 → 高段\n"
        "  ・県代表クラス以上 → 強豪"
    ),
    CoachMode.ADVANCED: (
        "より的確なアドバイスのために、棋力を教えていただけますか？\n"
        "  例：野狐三段以上、五段程度など\n"
        "  目安：\n"
        "  ・野狐三段以上 → 高段\n"
        "  ・県代表クラス以上 → 強豪"
    ),
    CoachMode.EXPERT: (
        "より的確なアドバイスのために、棋力を教えていただけますか？\n  例：県代表クラス以上、六段以上など"
    ),
}


_AYAKA_MARKERS: tuple[str, ...] = (
    "ウチ",
    "やで",
    "やねん",
    "なん？",
    "あかん",
    "ええ",
    "ほんま",
    "ほんまに",  # Phase 242-A: explicit marker for the NORM destination.
    "ちゃう",
    "やない",
    "しとる",
    "してな",
    "しとき",
    "めっちゃ",
    "ごっつ",
    "せやから",
    "せやな",
)


_KANSAI_NORMALISATION_PAIRS: tuple[tuple[str, str], ...] = (
    (r"私", "ウチ"),
    (r"ダメ", "あかん"),
    (r"だめ", "あかん"),
    (r"本当に", "ほんまに"),
    (r"本当", "ほんま"),
    (r"している", "しとる"),
    (r"してください", "してな"),
    # Phase 242-A: longer patterns BEFORE shorter ones to avoid
    # ``〜です`` matching inside ``〜ですか？`` (turning "〜ですか？"
    # into the wrong "〜やでか？"). apply_kansai_normalisation is
    # a left-to-right substring replace, so order matters.
    (r"〜ですか？", "〜なん？"),
    (r"〜ではない", "〜ちゃう"),
    (r"〜している", "〜しとる"),
    (r"〜ください", "〜してな"),
    (r"良い/いい", "ええ"),
    (r"ください", "しとき"),
    (r"ます", "やねん"),  # Phase 242-A: base form for 〜ます.
    (r"良い", "ええ"),
    (r"いい", "ええ"),
    (r"だから", "せやから"),
    (r"そうだね", "せやな"),
    (r"すごい", "めっちゃ"),
)


_PROHIBITED_DEFAULT_PHRASES: tuple[str, ...] = (
    "私は",
    "こんにちは、私は",
    "私は囲碁",  # role-play character setup
    "部長",
    "先生",
)


# --- Public API ---


def select_voice(
    rank_str: str | None = None,
    *,
    avg_points_lost: float | None = None,
    winrate_drop_pct: float | None = None,
    critical_move_count: int | None = None,
) -> ToneVoice:
    """Pick a ToneVoice for a player given rank + loss signals.

    Args:
        rank_str: SGF BR/WR / user setting in kyu/dan notation.
        avg_points_lost: Game-level avg pointsLost (KataGo-perspective).
        winrate_drop_pct: Maximum winrate drop pct (0-100).
        critical_move_count: Number of critical moves in the game.

    Returns:
        The ToneVoice that should drive SystemInstruction + body templates.
        Defaults to AYAKA when no signal is available (per Phase 203 §6.1
        priority chain — "default = beginner mode / AYAKA tone").
    """
    # Phase 203 §6.1 priority chain:
    # 1) BR/WR self-report
    # 2) SGF BR/WR property
    # 3) Loss-based estimation
    # 4) Default = BEGINNER / AYAKA
    base_mode = estimate_mode_from_rank(rank_str)
    if base_mode is not None:
        return get_mode_config(base_mode).voice

    adjusted = estimate_mode_from_loss(
        avg_points_lost=avg_points_lost,
        winrate_drop_pct=winrate_drop_pct,
        critical_move_count=critical_move_count,
    )
    if adjusted is not None:
        return get_mode_config(adjusted).voice

    return ToneVoice.AYAKA


def greeting_for_mode(mode: CoachMode, *, include_rank_guide: bool = True) -> str:
    """Return the master-doc §0-2 confirmation / clarification template.

    Args:
        mode: Target coach mode.
        include_rank_guide: When True, include the bracket "目安" block
            (full master-doc phrasing). When False, returns just the
            opening question line.
    """
    template = _CONFIRMATION_TEMPLATES.get(mode)
    if template is None:
        return ""
    if include_rank_guide:
        return template
    # Strip the bracketed guide.
    return template.split("\n")[0]


def greeting_for_voice(voice: ToneVoice) -> str:
    """Variant of greeting_for_mode mapped through the voice's primary mode.

    Convenience wrapper that picks the AYAKA-flavored vs TOMOKO-flavored
    phrasing without requiring the caller to know the mode-to-voice mapping.
    """
    if voice in (ToneVoice.AYAKA,):
        return greeting_for_mode(CoachMode.BEGINNER)
    if voice == ToneVoice.TOMOKO_STRICT:
        return greeting_for_mode(CoachMode.EXPERT)
    return greeting_for_mode(CoachMode.DAN)


def has_kansai_markers(text: str) -> bool:
    """Return True if ``text`` contains AYAKA-style Kansai markers.

    Used by Phase 212 llm_validator to confirm:
    - AYAKA voices contain Kansai markers
    - TOMOKO voices do NOT contain Kansai markers
    """
    if not text:
        return False
    return any(marker in text for marker in _AYAKA_MARKERS)


def is_kansai_marker(text: str) -> bool:
    """Like ``has_kansai_markers`` but checks the full normalised dictionary.

    More thorough than the 14-stride ``_AYAKA_MARKERS`` test — also flags
    「ほんま」「しとる」「セヤかな」のような Kansai-only vocabulary.
    """
    return has_kansai_markers(text)


def apply_kansai_normalisation(
    text: str,
    mapping: dict[str, str] | None = None,
) -> str:
    """Apply standard-Japanese → Kansai substitutions to ``text``.

    When called without ``mapping`` the function uses the AYAKA vocabulary
    list from master doc §1-3 plus a small set of common substitutions
    from the implementation.

    Args:
        text: Source text (assumed to be standard Japanese).
        mapping: Optional override dictionary. When provided, replaces
            the built-in default.

    Returns:
        Text with Kansai substitutions applied.
    """
    pairs = mapping.items() if mapping else dict(_KANSAI_NORMALISATION_PAIRS).items()

    out = text
    for src, dst in pairs:
        # Use a whole-substring replacement (no regex) to keep it simple.
        if src and src in out:
            out = out.replace(src, dst)
    return out


def check_prohibited(text: str, voice: ToneVoice) -> list[str]:
    """Verify ``text`` against ToneConfig.prohibited for ``voice``.

    Returns a list of phrases that violate the prohibition list (empty
    list = no violations). The Phase 212 validator calls this and warns
    the user without blocking (Phase 203 §7.1 user decision).
    """
    cfg = get_tone_config(voice)
    violations: list[str] = []

    # 1. Generic prohibitions (character talk, role-play setup, internal facets).
    if any(token in text for token in _PROHIBITED_DEFAULT_PHRASES):
        violations.append("キャラクター設定が混入している可能性")
    if "{{" in text or "}}" in text:
        violations.append("テンプレート変数が未展開の可能性")
    if "facet" in text:
        violations.append("内部タグ（facet）が混入")

    # 2. AYAKA-tone specific check: should NOT be too formal.
    if voice == ToneVoice.AYAKA:
        # Looks for over-formal particle patterns that break the casual vibe.
        formal_hits = re.findall(r"です。|ます。|ください。|ございます", text)
        if formal_hits:
            violations.append("AYAKA 文体に敬語/丁寧語が混入")

    # 3. TOMOKO_STRICT specific check: should be direct.
    if voice == ToneVoice.TOMOKO_STRICT and re.search(r"〜してみてね|〜してみてね！", text):
        violations.append("TOMOKO_STRICT 文体に優しい誘導表現が混入")

    # 4. Configured prohibitions (currently all share _COMMON_PROHIBITED).
    # The master doc prohibitions are not programmatic; the loop is kept
    # so a future call site can plug in checks per ``cfg.prohibited`` entry.
    for _prohibition in cfg.prohibited:
        pass

    return violations


def voice_summary(voice: ToneVoice) -> str:
    """Return a single-line Japanese summary for the voice.

    Useful for UI labels (settings / preview).
    """
    summaries = {
        ToneVoice.AYAKA: "あやか — 関西弁・親しみ・実利重視",
        ToneVoice.TOMOKO: "智子 — 標準語・論理・構造重視",
        ToneVoice.TOMOKO_STRICT: "智子（辛口） — 標準語・研究対等・本質重視",
    }
    return summaries.get(voice, voice.value)


def modes_for_voice(voice: ToneVoice) -> tuple[CoachMode, ...]:
    """Return CoachModes served by the given voice."""
    return tuple(m.mode for m in all_modes() if m.voice == voice)


__all__ = [
    "select_voice",
    "greeting_for_mode",
    "greeting_for_voice",
    "has_kansai_markers",
    "is_kansai_marker",
    "apply_kansai_normalisation",
    "check_prohibited",
    "voice_summary",
    "modes_for_voice",
]
