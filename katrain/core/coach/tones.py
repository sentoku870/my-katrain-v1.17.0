"""Phase 210: Tone selector and validator helpers.

Thin delegation layer over ``katrain.core.coach.master_db`` providing
higher-level helpers used by Phase 211 prompt_builder and downstream UI.

Public helpers:
- ``select_voice(rank_str, loss_signals...)`` → ToneVoice
- ``greeting_for_mode(mode)`` → Japanese greeting (master doc §0-2)
- ``check_prohibited(text, voice)`` → list of violations
- ``voice_summary(voice)`` → 1-line description for UI

All helpers are pure / Kivy-free.

Phase 269: AYAKA voice removed entirely. The Kansai dialect helpers
(``has_kansai_markers``, ``is_kansai_marker``, ``apply_kansai_normalisation``)
are gone. The tone consistency check (AYAKA must contain Kansai
markers; TOMOKO must not) is also gone — dialect preference is a
matter of taste and no longer surfaced as a validation issue.
"""

from __future__ import annotations

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
        "より的確なアドバイスのために、棋力を教えていただけますか？\n"
        "  例：野狐○段、○級、初心者（ルール覚えたて）など\n"
        "  目安：\n"
        "  ・ルール覚えたて〜石の取り方を練習中 → 初級\n"
        "  ・19路でシチョウ/ゲタが分かる → 中級\n"
        "  ・野狐初段前後 → 有段\n"
        "  ・野狐三段以上 → 高段\n"
        "  ・県代表クラス以上 → 強豪"
    ),
    CoachMode.INTERMEDIATE: (
        "より的確なアドバイスのために、棋力を教えていただけますか？\n"
        "  例：野狐○段、○級、中級程度など\n"
        "  目安：\n"
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
        Phase 269: defaults to TOMOKO (the unified standard-Japanese
        voice). EXPERT maps to TOMOKO_STRICT; everything else maps to
        TOMOKO.
    """
    # Phase 203 §6.1 priority chain (unchanged structure, voice default
    # changed in Phase 269 to TOMOKO):
    # 1) BR/WR self-report
    # 2) SGF BR/WR property
    # 3) Loss-based estimation
    # 4) Default = BEGINNER / TOMOKO
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

    return ToneVoice.TOMOKO


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

    Convenience wrapper that picks the TOMOKO-flavored vs TOMOKO_STRICT
    phrasing without requiring the caller to know the mode-to-voice mapping.
    """
    if voice == ToneVoice.TOMOKO_STRICT:
        return greeting_for_mode(CoachMode.EXPERT)
    return greeting_for_mode(CoachMode.DAN)


def check_prohibited(text: str, voice: ToneVoice) -> list[str]:
    """Verify ``text`` against ToneConfig.prohibited for ``voice``.

    Returns a list of phrases that violate the prohibition list (empty
    list = no violations). The Phase 212 validator calls this and warns
    the user without blocking (Phase 203 §7.1 user decision).

    Phase 269: AYAKA-tone specific check (敬語/丁寧語 violation) is
    removed along with the AYAKA voice. Only generic prohibitions and
    TOMOKO_STRICT's "no gentle phrases" check remain.
    """
    violations: list[str] = []

    # 1. Generic prohibitions (character talk, role-play setup, internal facets).
    if any(token in text for token in _PROHIBITED_DEFAULT_PHRASES):
        violations.append("キャラクター設定が混入している可能性")
    if "{{" in text or "}}" in text:
        violations.append("テンプレート変数が未展開の可能性")
    if "facet" in text:
        violations.append("内部タグ（facet）が混入")

    # 2. TOMOKO_STRICT specific check: should be direct.
    import re

    if voice == ToneVoice.TOMOKO_STRICT and re.search(r"〜してみてね|〜してみてね！", text):
        violations.append("TOMOKO_STRICT 文体に優しい誘導表現が混入")

    # 3. Configured prohibitions (currently all share _COMMON_PROHIBITED).
    # The master doc prohibitions are not programmatic; the loop is kept
    # so a future call site can plug in checks per the voice's
    # ``ToneConfig.prohibited`` entries.
    cfg = get_tone_config(voice)
    for _prohibition in cfg.prohibited:
        pass

    return violations


def voice_summary(voice: ToneVoice) -> str:
    """Return a single-line Japanese summary for the voice.

    Useful for UI labels (settings / preview).

    Phase 269: AYAKA entry removed. Only TOMOKO and TOMOKO_STRICT
    remain.
    """
    summaries = {
        ToneVoice.TOMOKO: "智子 — 標準語・論理・構造重視",
        ToneVoice.TOMOKO_STRICT: "智子（辛口） — 標準語・研究対等・本質重視",
    }
    return summaries.get(voice, voice.value)


def modes_for_voice(voice: ToneVoice) -> tuple[CoachMode, ...]:
    """Return CoachModes served by the given voice.

    Phase 269: all non-EXPERT modes are TOMOKO; only EXPERT is STRICT.
    """
    return tuple(m.mode for m in all_modes() if m.voice == voice)


__all__ = [
    "select_voice",
    "greeting_for_mode",
    "greeting_for_voice",
    "check_prohibited",
    "voice_summary",
    "modes_for_voice",
]
