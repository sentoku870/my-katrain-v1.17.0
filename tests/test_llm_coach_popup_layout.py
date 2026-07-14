"""Phase 225.3 layout regression: ensure button widths are uniform.

The Phase 225.0 / 225.1 / 225.2 popup had ``AutoSizedRoundedRectangleButton``
siblings with no explicit width, so each button auto-sized to its own
text content ("プロンプト生成 & コピー" rendered much wider than
"応答をクリア" / "検証実行", causing awkward wrapping and oversized
buttons that overflowed the popup).

The fix in ``katrain/gui/kv/llm_coach_popup.kv`` sets ``size_hint_x: 0.5``
on every action button in the two two-column BoxLayout rows, plus
explicit ``size_hint_x`` values on the karte-path row.

These tests verify the layout contract by static analysis of the KV file
(so they don't need a live Kivy window and stay headless-CI friendly).
"""

from __future__ import annotations

import re
from pathlib import Path


KV_PATH = Path(__file__).resolve().parents[1] / "katrain" / "gui" / "kv" / "llm_coach_popup.kv"


def _read_kv() -> str:
    return KV_PATH.read_text(encoding="utf-8")


def _find_button_blocks(kv: str, *, rule_pattern: str | None = None) -> list[str]:
    """Return each ``AutoSizedRoundedRectangleButton:`` block.

    Optional ``rule_pattern`` restricts to blocks whose first non-empty
    line matches the regex (e.g. ``r"id:\\s*generate_button"``).
    """
    blocks: list[str] = []
    for m in re.finditer(
        r"AutoSizedRoundedRectangleButton:.*?(?=\n\s*(?:AutoSizedRoundedRectangleButton:|<|\Z))",
        kv,
        re.DOTALL,
    ):
        block = m.group(0)
        if rule_pattern is not None:
            # Look at the first 5 lines after the colon to find an id
            first_lines = "\n".join(block.splitlines()[:6])
            if not re.search(rule_pattern, first_lines):
                continue
        blocks.append(block)
    return blocks


def _find_block_with_id(kv: str, widget_id: str) -> str:
    """Find the smallest indented block containing ``id: <widget_id>``.

    For Phase 225.3 we only care about ``size_hint_x`` / ``size_hint``
    values on the widget rule (the first ~10 lines after the id), so we
    just return the surrounding lines rather than the whole rule.
    """
    m = re.search(rf"\bid:\s*{re.escape(widget_id)}\b", kv)
    if m is None:
        raise AssertionError(f"No rule block found with id: {widget_id}")
    # The block starts at the matching widget rule (look backward for the
    # nearest indented rule header like "    AutoSizedRoundedRectangleButton:")
    block_start = kv.rfind("\n        ", 0, m.start())
    if block_start < 0:
        block_start = kv.rfind("\n    ", 0, m.start())
    if block_start < 0:
        block_start = 0
    # Find the matching end (next sibling at the same indent level)
    line_start = kv.rfind("\n", 0, block_start) + 1
    # Look for the next sibling header (4-8 spaces indent)
    sibling_pattern = re.compile(r"\n        [A-Z][A-Za-z_]+:|^\Z", re.MULTILINE)
    sibling = sibling_pattern.search(kv, m.end())
    end = sibling.start() if sibling else len(kv)
    return kv[line_start:end]


class TestActionButtonWidths:
    """All four action buttons must declare size_hint_x: 0.5."""

    def test_generate_button_size_hint(self) -> None:
        kv = _read_kv()
        blocks = _find_button_blocks(kv, rule_pattern=r"id:\s*generate_button")
        assert len(blocks) == 1, "expected exactly one generate_button block"
        assert "size_hint_x: 0.5" in blocks[0], (
            "generate_button must declare size_hint_x: 0.5 — otherwise it "
            "auto-sizes to its text and overflows the popup."
        )

    def test_clear_button_size_hint(self) -> None:
        kv = _read_kv()
        blocks = _find_button_blocks(kv, rule_pattern=r"id:\s*clear_button")
        assert len(blocks) == 1
        assert "size_hint_x: 0.5" in blocks[0]

    def test_validate_button_size_hint(self) -> None:
        kv = _read_kv()
        blocks = _find_button_blocks(kv, rule_pattern=r"id:\s*validate_button")
        assert len(blocks) == 1
        assert "size_hint_x: 0.5" in blocks[0]

    def test_copy_result_button_size_hint(self) -> None:
        kv = _read_kv()
        block = _find_block_with_id(kv, "copy_result_button")
        assert "size_hint_x: 0.5" in block, (
            "copy_result_button must declare size_hint_x: 0.5"
        )

    def test_browse_button_size_hint(self) -> None:
        """Browse button sits in a 75/25 row with the karte path input."""
        kv = _read_kv()
        blocks = _find_button_blocks(kv, rule_pattern=r"id:\s*browse_button")
        assert len(blocks) == 1
        assert "size_hint_x: 0.25" in blocks[0]


class TestRowProportions:
    """Two-column rows must use 0.5 / 0.5 splits for their buttons."""

    def test_action_row1_two_columns(self) -> None:
        kv = _read_kv()
        # The row that contains generate_button and clear_button
        # must have both buttons at size_hint_x: 0.5.
        gen = _find_button_blocks(kv, rule_pattern=r"id:\s*generate_button")[0]
        clr = _find_button_blocks(kv, rule_pattern=r"id:\s*clear_button")[0]
        assert "size_hint_x: 0.5" in gen
        assert "size_hint_x: 0.5" in clr

    def test_action_row2_two_columns(self) -> None:
        kv = _read_kv()
        val = _find_button_blocks(kv, rule_pattern=r"id:\s*validate_button")[0]
        cp = _find_block_with_id(kv, "copy_result_button")
        assert "size_hint_x: 0.5" in val
        assert "size_hint_x: 0.5" in cp


class TestPopupCompactness:
    """The popup must remain under 700x700 to fit common screen sizes."""

    def test_no_explicit_huge_heights(self) -> None:
        kv = _read_kv()
        # Nothing taller than 200dp for a single row
        for m in re.finditer(r"height:\s*dp\((\d+)\)", kv):
            assert int(m.group(1)) <= 200, (
                f"Row height {m.group(0)} is too tall for a popup row"
            )

    def test_result_label_is_scrollable(self) -> None:
        """The result label must be inside a ScrollView so long reports
        don't push the popup past its size."""
        kv = _read_kv()
        assert "ScrollView" in kv, "Popup must contain a ScrollView for the result label"
        # The ScrollView must come after the result-label header
        idx_scroll = kv.find("ScrollView")
        idx_result_label = kv.find("id: result_label")
        assert idx_scroll < idx_result_label, (
            "ScrollView must contain result_label, not the other way around"
        )