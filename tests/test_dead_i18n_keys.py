"""Regression test: dead i18n keys must not reappear.

These msgids were identified as unreferenced in source during the Phase 285
project audit. They are leftovers from removed features (contribute, quiz,
Phase 230 menu removal, Phase 250 important-moves refactor, Phase 227-D
LLM Coach popup unused keys, Phase 280 AI strategy cleanup, etc.).

If a key here is needed again, re-add it to the corresponding .po file and
remove it from this test list.
"""

from __future__ import annotations

import polib

REGRESSION_DEAD_KEYS = {
    # Phase 285 project audit — Phase 230-A.2 removed menu items
    "mykatrain:export-package",
    "mykatrain:training-set",
    "mykatrain:player-profile",
    "mykatrain:practice-report",
    # Phase 285 — contribute (distributed training) feature never used in fork
    "contribute settings title",
    "contribute:viewer settings",
    "contribute:login",
    "contribute:register",
    "contribute:start",
    "contribute:username",
    "contribute:password",
    "contribute:passwordwarning",
    "contribute:maxgames",
    "contribute:maxgames:hint",
    "contribute:ownership",
    "contribute:ownership:hint",
    "contribute:movespeed",
    "contribute:movespeed:hint",
    "contribute:savesgf",
    "contribute:savesgf:hint",
    "menu:distributed",
    "link_here",
    "gui-locked",
    "reanalyze mistakes only",
    # Phase 285 — quiz UI was removed (only used by removed popup)
    "Correct!",
    "Incorrect",
    "Best move: {move}",
    "Selected move loss: {loss_text}",
    "Played move {move} loss: {loss_text}",
    "Generate quiz (beta)",
    "Quiz mode (beta)",
    "No quiz items to show.",
    "No analysis data for this position.",
    "Start quiz",
    "Review the worst moves on the main line.",
    "Question {idx}/{total}: Move {move} ({player})",
    "No moves with loss greater than {loss:.1f} points were found on the main line.",
    "Showing up to {limit} moves with loss > {loss:.1f} points.",
    "Click a row to jump to the position before the move.",
    "Points lost unknown",
    "Unknown move",
    "Delta vs played: {delta:+.1f} points",
    # Phase 285 — Phase 250 important-moves refactor (replaced by -black/-white)
    "Entire Game",
    "Midgame",
    # Phase 285 — Phase 227-D LLM Coach popup keys that were added but never wired
    "mykatrain:llm-coach:type-detection-failed",
    "mykatrain:llm-coach:summary-perspective-label",
    # Phase 285 — Phase 229-C skill_preset radio group removed
    "mykatrain:settings:skill_preset",
    "mykatrain:settings:skill_relaxed",
    "mykatrain:settings:skill_beginner",
    "mykatrain:settings:skill_standard",
    "mykatrain:settings:skill_advanced",
    "mykatrain:settings:skill_pro",
    "mykatrain:settings:skill_auto",
    # Phase 285 — Phase 280 AI strategy slimdown: only 2 strategies remain
    # (ai:default, ai:handicap). Note: beginner_hint:* body/why keys are
    # still alive (consumed dynamically via ``f\"beginner_hint:{cat}:{suffix}\"``
    # in core/beginner/hints/_dispatch.py).
}


def test_dead_i18n_keys_absent_jp() -> None:
    po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
    found = [e.msgid for e in po if e.msgid in REGRESSION_DEAD_KEYS]
    assert found == [], f"Dead i18n keys reappeared in jp catalog: {found}"


def test_dead_i18n_keys_absent_en() -> None:
    po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
    found = [e.msgid for e in po if e.msgid in REGRESSION_DEAD_KEYS]
    assert found == [], f"Dead i18n keys reappeared in en catalog: {found}"
