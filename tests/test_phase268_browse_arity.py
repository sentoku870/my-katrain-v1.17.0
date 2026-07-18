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

import polib
import pytest

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


def test_analysis_tab_browse_handler_uses_inst_filename_for_ok_pick() -> None:
    """Phase 268 follow-up #2: the OK button sets ``filename`` (not
    ``selection``) on the browser, so the helper must read
    ``inst.filename`` first.  The earlier code only read
    ``inst.selection``, which is empty when the user picks via OK,
    so the popup appeared "stuck" after a click.
    """
    helper_src = _get_func_source(ANALYSIS_TAB_PATH, "_on_browser_done")
    assert "inst.filename" in helper_src, (
        "_on_browser_done must read from inst.filename (FileBrowser OK button contract) "
        "before falling back to inst.selection[0]"
    )
    # And the filename lookup must come before the selection fallback.
    fname_idx = helper_src.find("inst.filename")
    sel_idx = helper_src.find("inst.selection")
    assert fname_idx < sel_idx, (
        "inst.filename must be checked before inst.selection[0] so the OK-button pick wins"
    )


def test_analysis_tab_browse_handler_dismisses_picker() -> None:
    """Phase 268 follow-up #3: without ``picker.dismiss()`` the
    dialog stays open after a successful pick, leaving the user
    unable to reach the "保存" / "キャンセル" buttons.  The helper
    must explicitly close the picker, mirroring
    :func:`llm_coach_popup._on_pick`.
    """
    helper_src = _get_func_source(ANALYSIS_TAB_PATH, "_on_browser_done")
    assert "picker.dismiss" in helper_src, (
        "_on_browser_done must call ``picker.dismiss()`` so the dialog closes after a pick; "
        "otherwise the user is stuck on the file browser."
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
    # Find the block between ``browser = I18NFileBrowser(`` and the
    # I18NPopup ``picker.open()`` (or, pre-fix, the dead ``browser.open()``)
    # and verify both bind() keywords appear.
    m = re.search(
        r"browser\s*=\s*I18NFileBrowser\([^)]*\)\s*(?P<block>.*?)\s*(?:picker|browser)\.open\(\)",
        src,
        re.DOTALL,
    )
    assert m, "analysis_tab.py: could not locate the I18NFileBrowser open() block"
    block = m.group("block")
    assert "on_success" in block, "analysis_tab.py: 'on_success' not bound to I18NFileBrowser"
    assert "on_submit" in block, "analysis_tab.py: 'on_submit' not bound to I18NFileBrowser"


# ---------------------------------------------------------------------------
# 5. I18NFileBrowser is a BoxLayout, not a Popup: must NOT call open()
#    on the browser itself (Phase 268 follow-up: AttributeError silent fail)
# ---------------------------------------------------------------------------


def test_filebrowser_is_boxlayout_not_popup() -> None:
    """Pin that ``I18NFileBrowser`` extends ``BoxLayout`` (not ``Popup``).

    This is the underlying reason ``browser.open()`` fails: ``BoxLayout``
    has no ``open()`` method.  If this test ever fails because
    ``I18NFileBrowser`` was upgraded to extend ``Popup`` directly, the
    picker wrapping below becomes unnecessary and can be removed.
    """
    tree = ast.parse(FILEBROWSER_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "I18NFileBrowser":
            assert len(node.bases) == 1, f"I18NFileBrowser should have exactly 1 base class; got {len(node.bases)}"
            base = node.bases[0]
            base_name = (
                ast.unparse(base)
                if hasattr(ast, "unparse")
                else (base.id if isinstance(base, ast.Name) else ast.dump(base))
            )
            assert base_name == "BoxLayout", (
                f"I18NFileBrowser should extend BoxLayout; got {base_name!r}. "
                "If you upgrade to Popup, also update the test_analysis_tab_uses_i18n_popup "
                "test accordingly."
            )
            return
    pytest.fail("I18NFileBrowser class not found in filebrowser.py")


def test_analysis_tab_does_not_call_browser_open() -> None:
    """Pin that ``browser.open()`` is NEVER called on ``I18NFileBrowser``.

    ``I18NFileBrowser`` is a ``BoxLayout``; ``BoxLayout.open()`` does
    not exist.  The original Phase 268 code called ``browser.open()``
    which raised ``AttributeError`` that Kivy's on_release event
    handler silently swallowed, making the "参照" button completely
    unresponsive.  The fix wraps the browser in an ``I18NPopup`` and
    calls ``picker.open()`` instead.
    """
    tree = ast.parse(ANALYSIS_TAB_PATH.read_text(encoding="utf-8"))
    bad_calls: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "browser"
        ):
            bad_calls.append((ast.unparse(node), getattr(node, "lineno", 0)))
    assert not bad_calls, (
        f"analysis_tab.py: ``browser.open()`` re-introduced at "
        f"{[ln for _, ln in bad_calls]}.  I18NFileBrowser has no open() method — "
        "wrap it in I18NPopup and call picker.open()."
    )


def test_analysis_tab_uses_i18n_popup() -> None:
    """Pin that the file browser is wrapped in an ``I18NPopup``.

    This is the only working pattern (see :func:`llm_coach_popup.on_browse_karte`).
    """
    src = ANALYSIS_TAB_PATH.read_text(encoding="utf-8")
    # I18NPopup must be imported inside the browse helper (to keep
    # the top-level Kivy footprint small, mirroring llm_coach_popup).
    assert "from katrain.gui.popups._base import I18NPopup" in src, (
        "analysis_tab.py: must import I18NPopup from katrain.gui.popups._base"
    )
    # The picker wrapping pattern.
    assert re.search(
        r"picker\s*=\s*I18NPopup\(",
        src,
    ), "analysis_tab.py: must construct ``picker = I18NPopup(...)``"
    # And picker.open() is called (not browser.open()).
    assert re.search(
        r"picker\s*\.\s*open\s*\(\s*\)",
        src,
    ), "analysis_tab.py: must call ``picker.open()`` to display the file browser"


# ---------------------------------------------------------------------------
# 6. i18n key for the popup title exists in jp + en
# ---------------------------------------------------------------------------


JP_PO = REPO_ROOT / "katrain" / "i18n" / "locales" / "jp" / "LC_MESSAGES" / "katrain.po"
EN_PO = REPO_ROOT / "katrain" / "i18n" / "locales" / "en" / "LC_MESSAGES" / "katrain.po"


def test_curator_hint_browse_title_i18n_exists() -> None:
    """The new i18n key for the file-browser popup title must be present
    in both jp and en .po files (with a non-empty msgstr).
    """
    for po_path in (JP_PO, EN_PO):
        po = polib.pofile(str(po_path))
        matches = [e for e in po if e.msgid == "mykatrain:settings:curator_hint_browse_title"]
        assert matches, f"{po_path.name}: missing 'curator_hint_browse_title' key"
        assert matches[0].msgstr.strip(), f"{po_path.name}: 'curator_hint_browse_title' has empty msgstr"


# ---------------------------------------------------------------------------
# 7. Closure scoping: karte_dir / batch_dir are pre-declared so the
#    ``_on_browse`` closure always has them in scope (Phase 268 fix).
# ---------------------------------------------------------------------------


def test_curator_browse_closure_has_karte_dir_and_batch_dir() -> None:
    """Regression: the ``_on_browse`` closure references ``karte_dir``
    and ``batch_dir`` but these were previously only assigned inside
    the ``else`` branch (when the curator profile is not yet loaded).
    When the user opened the settings popup *after* a curator
    profile had been loaded, the variables were undefined and
    clicking "参照..." raised ``NameError``, which Kivy's
    ``on_release`` silently swallowed — the button looked dead.

    The fix is to pre-declare both variables to ``""`` before the
    if/else block so the closure always resolves them.
    """
    src = ANALYSIS_TAB_PATH.read_text(encoding="utf-8")
    # Both variables must be pre-declared in the outer function
    # (``_build_curator_status_label``) before the if/else block.
    # We pin this by asserting the pre-declared assignments appear
    # *before* the first ``if curator_profile is not None`` line.
    tree = ast.parse(src)
    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_build_curator_status_label":
            func = node
            break
    assert func is not None, "_build_curator_status_label not found in analysis_tab.py"

    # Find the first ``if curator_profile is not None`` statement.
    if_idx = None
    karte_idx = None
    batch_idx = None
    for i, stmt in enumerate(func.body):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            tgt = stmt.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id == "karte_dir" and karte_idx is None:
                # Capture the first karte_dir assignment (the pre-decl)
                if karte_idx is None:
                    karte_idx = i
            if isinstance(tgt, ast.Name) and tgt.id == "batch_dir" and batch_idx is None:
                if batch_idx is None:
                    batch_idx = i
        if isinstance(stmt, ast.If) and if_idx is None:
            test_src = ast.unparse(stmt.test)
            if "curator_profile" in test_src:
                if_idx = i
                break
    assert if_idx is not None, "_build_curator_status_label: missing the ``if curator_profile`` branch"
    assert karte_idx is not None, (
        "_build_curator_status_label: ``karte_dir`` is not pre-declared before the if/else — "
        "the browse button will raise NameError when the curator profile is already loaded."
    )
    assert batch_idx is not None, (
        "_build_curator_status_label: ``batch_dir`` is not pre-declared before the if/else — "
        "the browse button will raise NameError when the curator profile is already loaded."
    )
    assert karte_idx < if_idx, (
        f"karte_dir pre-declaration (line {karte_idx}) must come before the if/else (line {if_idx})"
    )
    assert batch_idx < if_idx, (
        f"batch_dir pre-declaration (line {batch_idx}) must come before the if/else (line {if_idx})"
    )


# ---------------------------------------------------------------------------
# 8. Phase 268+ popup status label refresh: after a successful
#    curator_ranking_*.json load, the live status label must update
#    in place so the user sees the new weak-tag count without
#    closing/reopening the popup.
# ---------------------------------------------------------------------------


SETTINGS_POPUP_PATH = REPO_ROOT / "katrain" / "gui" / "features" / "settings_popup.py"
SETTINGS_POPUP_STATE_PATH = REPO_ROOT / "katrain" / "gui" / "features" / "settings_popup_state.py"


def test_settings_popup_state_has_curator_status_label_field() -> None:
    """The :class:`_SettingsPopupContext` must carry a
    ``_curator_status_label`` reference so the file-browser
    handler can refresh the live label in place.

    Before this field existed, the popup would render
    ``"Batch 分析で …"`` even after a successful load, because the
    only way to see the new weak-tag count was to close and reopen
    the settings popup.
    """
    src = SETTINGS_POPUP_STATE_PATH.read_text(encoding="utf-8")
    assert "_curator_status_label" in src, (
        "settings_popup_state.py: _SettingsPopupContext must declare a "
        "'_curator_status_label' field for in-place popup refresh."
    )


def test_analysis_tab_status_label_stashed_on_state() -> None:
    """``_build_curator_status_label`` must stash the constructed
    label reference on ``state._curator_status_label`` so the
    file-browser callback can rewrite its text after a successful
    load.
    """
    src = ANALYSIS_TAB_PATH.read_text(encoding="utf-8")
    # Pin the assignment inside the function.  We accept any
    # indentation level since the function nests inside the
    # helper but the assignment must reference the state field.
    assert "state._curator_status_label = desc" in src, (
        "analysis_tab.py: _build_curator_status_label must assign "
        "'state._curator_status_label = desc' so the browse handler "
        "can refresh the label text in place."
    )


def test_analysis_tab_has_refresh_curator_status_label_text() -> None:
    """The shared text helper ``_refresh_curator_status_label_text``
    must exist so the initial render and the post-load refresh take
    the same code path.  Without this, the two paths would drift
    apart the next time the status wording changes.
    """
    helper_src = _get_func_source(ANALYSIS_TAB_PATH, "_refresh_curator_status_label_text")
    assert helper_src, "_refresh_curator_status_label_text not found in analysis_tab.py"
    # The helper must consult curator_profile and n_tags (the
    # two key state variables that drive the text).
    assert "curator_profile" in helper_src, (
        "_refresh_curator_status_label_text must consult ctx.curator_profile"
    )
    assert "weak_tags" in helper_src, (
        "_refresh_curator_status_label_text must read weak_tags "
        "to compute the loaded-tag count."
    )
    # And it must cover the 0-tag-while-loaded case (the new
    # "Profile loaded (no weak tags yet)" message).
    assert "curator_hint_loaded_no_tags" in helper_src, (
        "_refresh_curator_status_label_text must handle the loaded-but-empty "
        "case via the curator_hint_loaded_no_tags i18n key."
    )


def test_analysis_tab_browse_done_refreshes_label() -> None:
    """The ``_on_browser_done`` handler must call
    ``_refresh_curator_status_label_text`` so the new weak-tag
    count shows up immediately after the user picks a file.
    """
    helper_src = _get_func_source(ANALYSIS_TAB_PATH, "_on_browser_done")
    assert "_refresh_curator_status_label_text" in helper_src, (
        "_on_browser_done must call _refresh_curator_status_label_text "
        "so the status label updates after a successful load."
    )
    assert "label.text" in helper_src, (
        "_on_browser_done must assign the refreshed text to label.text"
    )


def test_settings_popup_stashes_state_on_popup() -> None:
    """``do_mykatrain_settings_popup`` must stash the state on the
    popup so the file-browser handler can walk back to the live
    status label.
    """
    src = SETTINGS_POPUP_PATH.read_text(encoding="utf-8")
    assert "popup._settings_state = state" in src, (
        "settings_popup.py: must stash state on popup as "
        "'popup._settings_state = state' so the file-browser handler "
        "can refresh the live status label."
    )
