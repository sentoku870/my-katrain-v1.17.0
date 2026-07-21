"""Regression tests for SizedButton padding reset.

Phase 277 migrated KivyMD 0.104.1 → 1.2.0. As part of this migration the
``SizedButton`` class went from extending ``BaseFlatButton`` to extending
KivyMD 1.2.0's ``BaseButton`` (which inherits ``AnchorLayout``). The
``AnchorLayout`` default ``padding = [dp(16), dp(8), dp(16), dp(8)]`` was
not reset in the ``<SizedButton>`` KV rule, so any sub-class using a small
fixed ``size:`` (notably ``<QuickInputButton@SizedRectangleButton>`` at
``sp(18)*2 × sp(18)*2 = 36×36``) renders with its inner ``Label`` clipped
to ``~4×20`` px. Text like ``0.5`` / ``6.5`` / ``9`` / ``19`` becomes
invisible — only the ``BackgroundMixin`` outline is visible as dots.

Phase 283 fixed this by adding ``padding: 0, 0, 0, 0`` to the
``<SizedButton>:`` KV rule. These tests guard against that line being
removed by future refactors.

All assertions are source-static (no Kivy runtime) and run unconditionally
on CI.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WIDGETS_KV = REPO_ROOT / "katrain" / "gui" / "kv" / "widgets.kv"
POPUP_WIDGETS_KV = REPO_ROOT / "katrain" / "gui" / "kv" / "popup_widgets.kv"
GAME_POPUPS_KV = REPO_ROOT / "katrain" / "gui" / "kv" / "game_popups.kv"
BUTTONS_PY = REPO_ROOT / "katrain" / "gui" / "kivyutils" / "buttons.py"


def _strip_kv_comments(source: str) -> str:
    """Return ``source`` with all ``# ...`` comment lines removed.

    Indentation-prefixed ``#`` comments are kept on their lines.
    """
    out_lines = []
    for line in source.splitlines():
        if line.lstrip().startswith("#") or line.strip() == "":
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _extract_kv_rule(source: str, rule_name: str) -> str:
    """Return the body of the ``<rule_name>:`` rule (top-level only).

    Supports rule names like ``<Foo@Bar>``, ``<Foo@Bar+Baz>`` and ``<Foo>``
    at column 0, with or without a trailing colon (KV rules can omit the
    colon when they are pure class aliases / inheritance markers).
    """
    lines = source.split("\n")
    rule_pat = re.compile(rf"^{re.escape(rule_name)}\s*:?\s*$")
    next_pat = re.compile(r"^[<A-Z][\w@>+\-]*\s*:?\s*$")

    rule_idx = None
    for i, line in enumerate(lines):
        if rule_pat.match(line):
            rule_idx = i
            break
    if rule_idx is None:
        raise AssertionError(f"KV rule <{rule_name}> not found")

    next_idx = len(lines)
    for j in range(rule_idx + 1, len(lines)):
        if next_pat.match(lines[j]):
            next_idx = j
            break
    return "\n".join(lines[rule_idx + 1 : next_idx])


class TestSizedButtonPaddingReset:
    """Source-static guard: <SizedButton> MUST reset AnchorLayout padding to 0."""

    def test_sized_button_kv_rule_resets_padding(self):
        """The <SizedButton>: rule must contain ``padding: 0,…`` (zero).

        With KivyMD 1.2.0 ``BaseButton`` inheriting ``AnchorLayout`` whose
        default ``padding = [dp(16), dp(8), dp(16), dp(8)]``,
        not resetting it makes any small-size SizedButton sub-class render
        blank inside its BackgroundMixin outline.
        """
        kv = WIDGETS_KV.read_text(encoding="utf-8")
        rule = _extract_kv_rule(kv, "<SizedButton>")

        assert re.search(
            r"^\s*padding\s*:\s*\[?\s*0(?:\s*,\s*0){0,3}\s*\]?",
            rule,
            re.MULTILINE,
        ), (
            "<SizedButton>: KV rule must reset padding to 0 to override the KivyMD 1.2.0 "
            "BaseButton (→ AnchorLayout) default [dp(16), dp(8), dp(16), dp(8)].\n"
            f"Current rule body:\n{rule}"
        )

    def test_sized_button_kv_rule_does_not_reintroduce_anchor_padding(self):
        """Regression guard: the SizedButton rule must not actively assign a
        non-zero padding that reintroduces the inherited AnchorLayout default.

        We scan only non-comment lines so documented references inside the
        Phase 283 inline comment don't trip the guard.
        """
        kv = _strip_kv_comments(WIDGETS_KV.read_text(encoding="utf-8"))
        rule = _extract_kv_rule(kv, "<SizedButton>")

        forbidden_active = [
            re.compile(r"^\s*padding\s*:\s*\[?\s*16\b", re.MULTILINE),
            re.compile(r"^\s*padding\s*:\s*\[?\s*dp\(\s*16\b", re.MULTILINE),
        ]
        for pat in forbidden_active:
            m = pat.search(rule)
            assert m is None, (
                f"<SizedButton>: rule re-introduces padding that would consume "
                f"inner Label area for small sub-classes. Match: {m.group(0)!r}"
            )

    def test_sized_button_rule_has_phase_283_comment(self):
        """The Phase 283 padding reset must be accompanied by a comment that
        explains WHY (so future contributors don't think it's stray)."""
        kv = WIDGETS_KV.read_text(encoding="utf-8")
        rule = _extract_kv_rule(kv, "<SizedButton>")
        assert "Phase 283" in rule and "AnchorLayout" in rule, (
            "<SizedButton>: rule must carry a comment explaining the KivyMD 1.2.0 "
            "AnchorLayout padding reason (search 'Phase 283' and 'AnchorLayout').\n"
            f"Current rule body:\n{rule}"
        )


class TestQuickInputButtonContract:
    """QuickInputButton: regression guard that all 9 buttons are still defined in the
    New Game popup with their expected texts and targets."""

    def test_all_nine_quick_input_button_texts_present(self):
        """The 9 New-Game-Popup quick-select buttons must still be defined."""
        kv = GAME_POPUPS_KV.read_text(encoding="utf-8")
        # Komi quick-input buttons
        for text in ("0.5", "6.5", "7.5"):
            count = kv.count(f"text: '{text}'")
            assert count >= 1, f"QuickInputButton text='{text}' missing from game_popups.kv (expected ≥1)."
        # Board-size quick-input buttons (must coexist with other buttons of same text)
        for text in ("9", "13", "19"):
            count = kv.count(f"text: '{text}'")
            assert count >= 1, f"QuickInputButton text='{text}' missing from game_popups.kv (expected ≥1)."
        # Handicap quick-input buttons
        for text in ("0", "2", "9"):
            count = kv.count(f"text: '{text}'")
            assert count >= 1, f"QuickInputButton text='{text}' missing from game_popups.kv (expected ≥1)."

    def test_nine_quick_input_button_instances_in_new_game_popup(self):
        """There must be exactly 9 ``QuickInputButton:`` instances in the
        NewGamePopup section (komi×3 + boardsize×3 + handicap×3).
        """
        kv = GAME_POPUPS_KV.read_text(encoding="utf-8")
        new_game_popup_start = kv.find("<NewGamePopup>")
        assert new_game_popup_start != -1, "<NewGamePopup> rule not found"
        new_game_section = kv[new_game_popup_start:]
        count = new_game_section.count("QuickInputButton:")
        assert count == 9, (
            f"Expected exactly 9 QuickInputButton instances in <NewGamePopup>; "
            f"found {count}. Komi/boardsize/handicap preset rows are each 3 buttons."
        )

    def test_quick_input_button_rule_unchanged_size(self):
        """The QuickInputButton rule's size formula must remain compatible with
        the SizedButton padding reset. If someone reverts the SizedButton
        padding reset AND changes QuickInputButton's size, both fixes should
        be reviewed in tandem."""
        kv = POPUP_WIDGETS_KV.read_text(encoding="utf-8")
        rule = _extract_kv_rule(kv, "<QuickInputButton@SizedRectangleButton>")
        assert "sp(Theme.DESC_FONT_SIZE) * 2, sp(Theme.DESC_FONT_SIZE) * 2" in rule, (
            "QuickInputButton size formula unexpectedly changed. SizedButton padding "
            "reset depends on this fixed 36×36 sp size for visibility regression to surface."
        )

    def test_quick_input_button_rule_uses_size_hint_none(self):
        """Phase 283 root-cause fix: the SizedButton padding reset alone was
        insufficient. With default ``size_hint=(1, 1)`` the parent
        ``MDBoxLayout(adaptive_size=True)`` does NOT include each child's
        explicit ``size:`` in its ``minimum_width`` / ``minimum_height``
        calculation (BoxLayout only counts children with ``size_hint_*=None``).
        Result: MDBoxLayout collapses to a 12×0 minimum rectangle and the
        three 36×36 sp buttons are rendered at 0×0 px. Setting
        ``size_hint: None, None`` makes MDBoxLayout respect the explicit
        ``size:`` and report a correct 120×36 minimum_size.

        Without this line the buttons are entirely invisible in the
        New Game popup — only an empty third column of each row.
        """
        kv = POPUP_WIDGETS_KV.read_text(encoding="utf-8")
        rule = _extract_kv_rule(kv, "<QuickInputButton@SizedRectangleButton>")
        assert "size_hint: None, None" in rule, (
            "<QuickInputButton@SizedRectangleButton> must declare size_hint: None, None "
            "so that MDBoxLayout(adaptive_size=True) includes each button's explicit "
            "size in its minimum dimensions. Without this the buttons render at 0x0 px."
        )

    def test_quick_input_button_uses_target_text_binding(self):
        """The on_left_press handler must still copy self.text into target.text."""
        kv = POPUP_WIDGETS_KV.read_text(encoding="utf-8")
        rule = _extract_kv_rule(kv, "<QuickInputButton@SizedRectangleButton>")
        assert "target.text = self.text" in rule, (
            "QuickInputButton on_left_press contract changed. The preset buttons no longer update their target input."
        )


class TestSizedButtonPythonClass:
    """Python-side: SizedButton must remain compatible with the padding reset in KV."""

    def test_sized_button_padding_is_reset_somewhere(self):
        """Either the SizedButton Python class resets padding, OR the KV rule
        does — at least one is required for the SizedButton sub-classes to
        render properly under KivyMD 1.2.0 BaseButton's inherited
        AnchorLayout default.
        """
        py = BUTTONS_PY.read_text(encoding="utf-8")
        kv = WIDGETS_KV.read_text(encoding="utf-8")
        sized_rule = _extract_kv_rule(kv, "<SizedButton>")

        kv_resets = re.search(
            r"^\s*padding\s*:\s*\[?\s*0(?:\s*,\s*0){0,3}\s*\]?",
            sized_rule,
            re.MULTILINE,
        )
        py_resets = re.search(
            r"class\s+SizedButton\b.*?padding\s*=\s*\[0",
            py,
            re.DOTALL,
        )
        assert kv_resets or py_resets, (
            "SizedButton must reset the KivyMD 1.2.0 BaseButton (→ AnchorLayout) padding "
            "in either Python (class attribute) or KV (<SizedButton>: padding: 0). "
            "Neither was found."
        )
