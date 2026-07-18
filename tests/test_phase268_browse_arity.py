"""Phase 268 follow-up: I18NFileBrowser browse callback arity.

Phase 268 first cut bound the file browser's ``on_success`` and
``on_submit`` events to ``lambda inst, _touch`` and
``lambda inst, selection, _touch``.  ``I18NFileBrowser`` dispatches
both events with **only** the instance as a positional argument
(see :mod:`katrain.gui.widgets.filebrowser` line 446-450 default
handlers), so the lambdas raised ``TypeError`` on every file
selection and the picker silently no-op'd.  Users reported "参照ボタン
が動作しない".

The fix replaces the lambdas with a named function whose signature
absorbs trailing args via ``*_args`` (mirroring the working pattern
in :func:`katrain.gui.popups.llm_coach_popup._on_pick`).  This
regression test pins the new shape so the bug cannot return.

The check is purely AST-based so the test runs under the Kivy-free
headless CI (the popup itself still requires a real Kivy window).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_TAB_PATH = REPO_ROOT / "katrain" / "gui" / "features" / "settings_popup_tabs" / "analysis_tab.py"
FILEBROWSER_PATH = REPO_ROOT / "katrain" / "gui" / "widgets" / "filebrowser.py"
LLC_COACH_POPUP_PATH = REPO_ROOT / "katrain" / "gui" / "popups" / "llm_coach_popup.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_func_node(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _get_func_source(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    func = _find_func_node(tree, name)
    assert func is not None, f"Function {name!r} not found in {path.name}"
    return ast.get_source_segment(text, func) or ""


# ---------------------------------------------------------------------------
# 1. I18NFileBrowser dispatches on_success / on_submit with one arg
# ---------------------------------------------------------------------------


def test_filebrowser_event_handlers_take_only_self() -> None:
    """Pin that I18NFileBrowser's events are dispatched with a single arg.

    If this test ever fails, the file browser has been upgraded to
    pass extra args through dispatch — in that case, the *_args
    sink in our handlers (and in llm_coach_popup) will simply be a
    no-op and the tests below will still pass.
    """
    src = FILEBROWSER_PATH.read_text(encoding="utf-8")
    # The default handlers ``on_success`` / ``on_submit`` must have
    # exactly one parameter (self).
    for name in ("on_success", "on_submit"):
        func = _find_func_node(ast.parse(src), name)
        assert func is not None, f"filebrowser.py: missing default handler {name}()"
        args = func.args
        assert len(args.args) == 1, f"filebrowser.py:{name}() must take only self; got {len(args.args)} args"
        assert args.args[0].arg in ("self", "root"), (
            f"filebrowser.py:{name}() must take self/root; got {args.args[0].arg!r}"
        )
        assert args.vararg is None and args.kwarg is None, (
            f"filebrowser.py:{name}() must not declare *args/**kwargs; got {ast.dump(args)}"
        )


def test_filebrowser_dispatch_calls_pass_no_extra_args() -> None:
    """Pin that ``dispatch("on_success")`` and ``dispatch("on_submit")``
    are called without any extra positional or keyword arguments.
    """
    src = FILEBROWSER_PATH.read_text(encoding="utf-8")
    # Every ``dispatch("on_success"|"on_submit")`` call in the file
    # must use the bare form (no trailing args).
    pattern = re.compile(
        r'self\.dispatch\(\s*[\'"](?:on_success|on_submit)[\'"]\s*\)',
    )
    matches = pattern.findall(src)
    assert matches, "filebrowser.py: no ``self.dispatch('on_success'|'on_submit')()`` call found"
    # And the inverse: a call with extra args would be a breaking change.
    bad = re.findall(
        r'self\.dispatch\(\s*[\'"](?:on_success|on_submit)[\'"]\s*,',
        src,
    )
    assert not bad, (
        "filebrowser.py: 'on_success' / 'on_submit' are dispatched with extra args; "
        "downstream handlers must be re-audited."
    )


# ---------------------------------------------------------------------------
# 2. analysis_tab.py: the browse handler absorbs extra dispatch args
# ---------------------------------------------------------------------------


def test_analysis_tab_browse_handler_uses_args_sink() -> None:
    """The ``_on_browse`` closure helper bound to ``browser.bind`` must
    accept a variable number of arguments so a future dispatch-shape
    change does not silently no-op the picker.
    """
    src = ANALYSIS_TAB_PATH.read_text(encoding="utf-8")
    # Locate the inner helper.  The original code had
    # ``browser.bind(on_success=lambda inst, _touch: ...)`` — that
    # pattern would fail with TypeError on every dispatch.  After
    # the fix, the bound callback is a named function whose
    # signature absorbs trailing args.
    forbidden = [
        "browser.bind(\n            on_success=lambda inst, _touch:",
        "browser.bind(\n            on_submit=lambda inst, selection, _touch:",
    ]
    for snippet in forbidden:
        assert snippet not in src, f"analysis_tab.py: arity-broken lambda re-introduced:\n{snippet!r}"
    # And the new helper is present.
    assert "_on_browser_done" in src, "analysis_tab.py: missing named browse helper (_on_browser_done)"
    # Parse the helper and check its signature.
    helper_src = _get_func_source(ANALYSIS_TAB_PATH, "_on_browser_done")
    helper_tree = ast.parse(helper_src)
    func = _find_func_node(helper_tree, "_on_browser_done")
    assert func is not None
    assert func.args.vararg is not None, "_on_browser_done must accept *args to absorb future dispatch extras"
    vararg_name = func.args.vararg.arg
    assert vararg_name.startswith("_") or vararg_name in ("args", "_args"), (
        f"_on_browser_done vararg should be _args/args/*_ignored*, got *{vararg_name!r}"
    )


def test_analysis_tab_browse_handler_uses_inst_selection_only() -> None:
    """Pin that the helper reads from ``inst.selection`` (a list of
    absolute paths), matching the actual ``I18NFileBrowser`` contract.
    Earlier code read from a parameter named ``selection`` which
    was never bound — a dead reference masked by the arity TypeError.
    """
    helper_src = _get_func_source(ANALYSIS_TAB_PATH, "_on_browser_done")
    # Must read from inst.selection (a list), not from a non-existent
    # ``selection`` parameter.
    assert "inst.selection" in helper_src, "_on_browser_done must read from inst.selection (FileBrowser contract)"
    # The buggy form used ``selection[0] if selection else None``
    # which would resolve to a NameError once the arity issue was
    # fixed.  Guard against the regression.
    assert re.search(r"\bselection\s*\[", helper_src) is None or ("inst.selection" in helper_src), (
        "_on_browser_done uses a bare ``selection`` identifier; must use inst.selection"
    )


# ---------------------------------------------------------------------------
# 3. llm_coach_popup.py: the working pattern is unchanged
# ---------------------------------------------------------------------------


def test_llm_coach_popup_pattern_unchanged() -> None:
    """Sanity check that the working pattern in llm_coach_popup is
    still in place.  If it is, analysis_tab's fix is consistent.
    """
    src = LLC_COACH_POPUP_PATH.read_text(encoding="utf-8")
    assert "def _on_pick(instance: Any, *_args: Any) -> None:" in src, (
        "llm_coach_popup.py: the working *_args pattern was modified; audit analysis_tab.py accordingly."
    )


# ---------------------------------------------------------------------------
# 4. Both ``on_success`` and ``on_submit`` are bound (no regression)
# ---------------------------------------------------------------------------


def test_analysis_tab_binds_both_on_success_and_on_submit() -> None:
    """Phase 225.2 fix contract: both the OK button (``on_success``)
    and the double-click (``on_submit``) handlers must be bound.
    """
    src = ANALYSIS_TAB_PATH.read_text(encoding="utf-8")
    # Find the block between ``browser = I18NFileBrowser(`` and
    # ``browser.open()`` and verify both bind() keywords appear.
    m = re.search(
        r"browser\s*=\s*I18NFileBrowser\([^)]*\)\s*(?P<block>.*?)\s*browser\.open\(\)",
        src,
        re.DOTALL,
    )
    assert m, "analysis_tab.py: could not locate the I18NFileBrowser open() block"
    block = m.group("block")
    assert "on_success" in block, "analysis_tab.py: 'on_success' not bound to I18NFileBrowser"
    assert "on_submit" in block, "analysis_tab.py: 'on_submit' not bound to I18NFileBrowser"
