"""Regression tests for side-panel font sizes in katrain/gui/kv/panels.kv.

Phase 283 restored upstream v1.18.1 font scaling by removing the Phase 277.1
``min(sp(N), ...)`` caps on the three labels highlighted in the
user-reported screenshots:

* PlayerInfo top label (player_type — 人間 / AI)
* PlayerInfo subtype label (player_subtype — 通常対局 / 指導対局)
* StatsLabel desc label (勝率 / 推定目差 / 損失目数 / 獲得目数)

These tests are source-static (no Kivy runtime) so they run unconditionally
on CI. They guard against the Phase 277.1 caps accidentally being reinstated
by future contributors who see "the text is too big" without reading the
commit message that explains why the caps were removed in Phase 283.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PANELS_KV = REPO_ROOT / "katrain" / "gui" / "kv" / "panels.kv"


def _extract_kv_rule(source: str, rule_name: str) -> str:
    """Return the body of the ``<rule_name>:`` rule (top-level only).

    A rule body extends from the line after ``<rule_name>:`` to (exclusive)
    either the next sibling rule at column 0, or end of file.
    """
    pattern = (
        rf"^{re.escape(rule_name)}\s*:\s*"
        rf"$(.*?)"
        rf"(?=^[<A-Za-z_][\w@]*\s*:|^[A-Z]\w+\s*:|\Z)"
    )
    m = re.search(pattern, source, re.MULTILINE | re.DOTALL)
    if m is None:
        raise AssertionError(f"KV rule <{rule_name}> not found in {PANELS_KV.name}")
    return m.group(1)


def _iter_label_blocks(rule_body: str):
    """Yield all inner ``Label:`` blocks (top-most in this rule body).

    A ``Label:`` block runs from the ``Label:`` line to (exclusive) the
    next sibling at the same indentation, or a parent-level line at lower
    indentation, or end of the body. Sibling ``Label:`` lines are
    detected by identical leading-whitespace length.
    """
    lines = rule_body.split("\n")
    label_re = re.compile(r"^([ \t]*)Label(?:\s+\w+)?\s*:\s*(#.*)?$")

    # Index every Label: line
    label_lines = []
    for i, line in enumerate(lines):
        m = label_re.match(line)
        if m:
            label_lines.append((i, len(m.group(1))))

    for idx, indent in label_lines:
        end = len(lines)
        for k in range(idx + 1, len(lines)):
            stripped = lines[k].strip()
            if not stripped:
                continue
            lead = re.match(r"^([ \t]*)", lines[k])
            lead_len = len(lead.group(1)) if lead else 0
            # End this Label when we hit a sibling at equal indent, or a
            # parent line at lesser indent.
            if lead_len <= indent:
                end = k
                break
        yield "\n".join(lines[idx:end])


def _nth_label_block(rule_body: str, n: int) -> str:
    blocks = list(_iter_label_blocks(rule_body))
    if n >= len(blocks):
        raise AssertionError(f"Label index {n} out of range — rule has {len(blocks)} Labels")
    return blocks[n]


class TestPlayerInfoFontSizes:
    """PlayerInfo: matches upstream v1.18.1 — no ``min(sp(...))`` caps."""

    def _rule_body(self) -> str:
        return _extract_kv_rule(PANELS_KV.read_text(encoding="utf-8"), "<PlayerInfo>")

    def test_player_type_label_uses_height_proportional_uncapped(self):
        body = self._rule_body()
        block = _nth_label_block(body, 0)
        assert re.search(r"font_size:\s*0\.8\s*\*\s*self\.height", block), (
            f"PlayerInfo player_type Label must use 'font_size: 0.8 * self.height' (uncapped). Found:\n{block}"
        )
        assert "min(sp(" not in block, (
            f"Phase 277.1 min(sp(...)) cap has reappeared in PlayerInfo player_type Label. Found:\n{block}"
        )

    def test_subtype_label_human_branch_uses_height_proportional(self):
        body = self._rule_body()
        block = _nth_label_block(body, 1)
        assert "self.height * 0.7" in block, f"PlayerInfo subtype_label must use 'self.height * 0.7'. Found:\n{block}"
        assert "min(sp(" not in block, (
            f"Phase 277.1 min(sp(...)) cap has reappeared in PlayerInfo subtype_label. Found:\n{block}"
        )

    def test_subtype_label_keeps_shorten_formula_for_ai(self):
        """AI branch must still use ``min(1, 18/len(self.text))`` so longer
        AI subtype labels (e.g. 指導対局) shrink to fit."""
        body = self._rule_body()
        block = _nth_label_block(body, 1)
        assert re.search(
            r"PLAYER_HUMAN\s*else\s*self\.height\s*\*\s*0\.7\s*\*\s*"
            r"min\(1,\s*18/len\(self\.text\)\)",
            block,
        ), f"PlayerInfo subtype_label must keep the AI-branch shrink formula. Found:\n{block}"


class TestStatsLabelFontSizes:
    """StatsLabel: matches upstream v1.18.1 — height × 0.7 uncapped."""

    def _rule_body(self) -> str:
        return _extract_kv_rule(PANELS_KV.read_text(encoding="utf-8"), "<StatsLabel>")

    def test_desc_label_uses_height_proportional_uncapped(self):
        body = self._rule_body()
        block = _nth_label_block(body, 0)
        assert re.search(r"font_size:\s*self\.height\s*\*\s*0\.7\b", block), (
            f"StatsLabel desc Label must use 'font_size: self.height * 0.7' "
            f"(uncapped, matching upstream v1.18.1). Found:\n{block}"
        )
        assert "min(sp(" not in block, (
            f"Phase 277.1 min(sp(...)) cap has reappeared in StatsLabel desc Label. Found:\n{block}"
        )
        assert "0.55" not in block, f"Phase 277.1 used a 0.55 multiplier (smaller than upstream's 0.7). Found:\n{block}"

    def test_value_label_inherits_desc_font_size(self):
        body = self._rule_body()
        # Second inner Label = value (right side, colored)
        block = _nth_label_block(body, 1)
        assert re.search(r"font_size:\s*desc\.font_size", block), (
            f"StatsLabel value Label must inherit desc.font_size. Found:\n{block}"
        )


class TestNoLegacyPhase2771Caps:
    """Whole-file guard: no Phase 277.1 ``min(sp(...))`` cap forms remain in
    panels.kv on the three documented labels."""

    def test_no_min_sp_caps_left_in_panels_kv(self):
        source = PANELS_KV.read_text(encoding="utf-8")
        forbidden_patterns = [
            r"min\(\s*sp\(16\),\s*0\.8",
            r"min\(\s*sp\(12\),\s*self\.height\s*\*\s*0\.[57]",
            r"min\(\s*sp\(12\),\s*self\.height\s*\*\s*0\.7\s*\*",
            r"min\(\s*sp\(12\),\s*self\.height\s*\*\s*0\.55",
        ]
        violations = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            # Skip comment lines so documented references (e.g. inside a
            # ``# Phase 277.1 ...`` comment block) don't trip the guard.
            if line.lstrip().startswith("#"):
                continue
            for pat in forbidden_patterns:
                if re.search(pat, line):
                    violations.append((lineno, line.strip(), pat))
        assert not violations, "Phase 277.1 min(sp(...)) cap has reappeared in panels.kv:\n" + "\n".join(
            f"  L{ln}: {line_text}  (matched /{pat_text}/)" for ln, line_text, pat_text in violations
        )
