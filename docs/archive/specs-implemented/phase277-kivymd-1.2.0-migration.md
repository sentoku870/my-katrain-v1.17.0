# Phase 277 — KivyMD 0.104.1 → 1.2.0 migration

> 2026-07-20 / Lv3 / 13 ファイル変更 + 1 新規ファイル / `mypy` 0 issues / `ruff` clean / `pytest` 5963 PASS + 3 SKIP / PyInstaller Linux ビルド + バイナリ起動 OK

## Motivation

`pyproject.toml` had been pinned to ``kivymd==0.104.1`` (released 2020-04-27) since Phase 1. By mid-2026 that pin was four years old and prevented us from picking up:

- Material Design 3 / Material You theming (added in KivyMD 1.0.0)
- ``BaseButton`` consolidation and the new ``color_active`` / ``color_inactive`` API
- Several bug fixes for the drawer, card, and text-field widgets we use

Phase 273 deliberately kept the pin in place to scope the OSV-driven dep bump narrowly. Phase 277 picked it back up as a self-contained migration.

## Scope

We use a small subset of the KivyMD API:

| Module                                              | Use sites                                                            |
| --------------------------------------------------- | -------------------------------------------------------------------- |
| ``kivymd.app.MDApp``                                 | 10 files (app base class)                                            |
| ``kivymd.uix.button.{BaseFlatButton, BasePressedButton}`` | ``kivyutils/buttons.py`` (5-tier MRO)                            |
| ``kivymd.uix.textfield.MDTextField``                 | ``popups/_base.py`` (``LabelledTextInput`` etc.)                     |
| ``kivymd.uix.selectioncontrol.MDCheckbox``          | ``popups/_base.py`` (``LabelledCheckBox``)                           |
| ``kivymd.uix.navigationdrawer.MDNavigationDrawer``  | ``kivyutils/_panels.py`` (``MyNavigationDrawer``)                    |
| ``kivymd.uix.behaviors.{RectangularRippleBehavior, CircularRippleBehavior}`` | buttons.py / _panels.py |
| ``kivymd.uix.boxlayout.MDBoxLayout`` etc.           | layout helpers                                                       |
| ``MDLabel`` / ``MDSpinner`` / ``MDCard``            | ``progress_loader.py`` / ``selection_slider.py`` (KV only)           |

Plus four KV widgets: ``MDBoxLayout``, ``MDFloatLayout``, ``MDGridLayout``, ``MDCheckbox``.

## Breaking changes that affected us

### 1. ``BaseFlatButton`` / ``BasePressedButton`` removed (1.0.0)

In 0.104.1 the MRO was:

```
SizedButton → LeftButtonBehavior, RectangularRippleBehavior,
              BasePressedButton, BaseFlatButton, BackgroundMixin
```

In 1.2.0 those two KivyMD base classes are gone; ``BaseButton`` extends ``AnchorLayout`` and already provides ripple + button behaviour. The new MRO is:

```python
class SizedButton(LeftButtonBehavior, BaseButton, BackgroundMixin):
    theme_text_color = OptionProperty("Custom", ...)
    ...
```

We also pin ``theme_text_color = "Custom"`` so our explicit ``text_color`` is always honoured regardless of the new default-``Primary`` change in 0.104.2.

### 2. ``NavigationLayout`` → ``MDNavigationLayout`` (1.0.0)

``main_layout.kv`` referenced the bare ``NavigationLayout:`` class. The KivyMD class is now ``MDNavigationLayout``.

### 3. ``MDCheckbox.selected_color`` / ``unselected_color`` deprecated

Replaced by ``color_active`` / ``color_inactive``. We rewrote the binding in ``menu.kv`` to use the new names; both are still ``None`` at rule-evaluation time, so we fall back to ``disabled_color`` first when ``checkbox.disabled`` is true.

### 4. ``MDTextField.helper_text_mode: "none"`` removed (1.0.0)

Valid options in 1.2.0 are ``["on_error", "persistent", "on_focus"]``. We rely on ``helper_text: ""`` to keep the helper line empty under the new default.

### 5. ``MDTextField.color_mode`` removed

No replacement — the new ``MDTextField`` exposes ``line_color_focus`` / ``line_color_normal`` directly. The line was deleted from ``popup_widgets.kv``.

### 6. ``LabelledPathInput.on_text`` no longer has a ``super()`` chain

In 0.104.1 the parent ``MDTextField`` had an ``on_text`` method we could call; in 1.2.0 it does not, so ``super().on_text(widget, text)`` raises ``AttributeError``. We removed the call and kept the validation hook.

### 7. KivyMD 1.2.0 ships without its companion ``.kv`` files

Every ``kivymd.uix.<widget>`` module does ``open(os.path.join(uix_path, "<widget>", "<widget>.kv"))`` at module-import time. The 1.2.0 wheel / sdist ships **only the ``.py`` files** for these 36 widget modules. We solve this in two places:

- **Runtime (``katrain/gui/_kivymd_kv_loader.py``)** — creates a tempdir, writes 36 stub ``.kv`` rules, monkey-patches ``kivymd.uix_path`` to point at it. Called from both ``katrain/__main__.py`` (production) and ``tests/conftest.py`` (test discovery). The stub bodies match what the missing ``.kv`` files would have provided under 0.104.1.
- **PyInstaller (``spec/hook-kivymd.py``)** — generates the same 36 stubs in a tempdir at build time and adds them to ``datas``. The bundled binary finds them via the same ``kivymd.uix_path`` resolution.

The loader is idempotent and uses ``atexit`` to clean up the tempdir on process exit.

### 8. ``MDApp.get_running_app()`` must be set before instantiating any KivyMD widget (1.2.0)

This was already true for the project (tests bypass ``__init__`` via ``__new__``, production runs through ``KaTrainApp``), so no fix was needed.

### 9. PyInstaller missed ``katrain.gui.lang_bridge`` (pre-existing bug uncovered during build)

The KV files use ``#:import i18n katrain.gui.lang_bridge.i18n`` which PyInstaller's static analysis doesn't follow. We added it to ``hiddenimports`` in ``spec/KaTrain.spec``. This was technically a pre-existing latent issue but the migration surfaced it because we ran a full Linux build verification.

## File-by-file changes

### ``pyproject.toml``
```diff
-    "kivymd==0.104.1",
+    "kivymd==1.2.0",
+    "materialyoucolor>=1.0.0",
```

### ``katrain/gui/_kivymd_kv_loader.py`` (new, ~120 lines)
Runtime loader — see *7* above. Module-level contract documented in the file's docstring.

### ``katrain/__main__.py``
Inject the loader after ``kivy.require("2.0.0")`` and before any ``kivymd.uix.*`` import (line 71).

### ``tests/conftest.py``
Same loader call as ``__main__.py`` so test discovery doesn't crash on the missing ``.kv`` files.

### ``katrain/gui/kivyutils/buttons.py``
Rework the ``SizedButton`` MRO as described in *1*. ``theme_text_color = "Custom"`` is pinned so our ``text_color`` wins over the new default.

### ``katrain/gui/popups/_base.py``
Drop ``super().on_text(widget, text)`` in ``LabelledPathInput.on_text`` (see *6*).

### ``katrain/gui/kv/main_layout.kv``
```diff
-    NavigationLayout:
+    MDNavigationLayout:
```

### ``katrain/gui/kv/menu.kv``
```diff
- color: checkbox.disabled_color if root.disabled else (checkbox.selected_color if checkbox.active else checkbox.unselected_color)
+ color: (checkbox.color_active if checkbox.active else checkbox.color_inactive) if not checkbox.disabled else checkbox.disabled_color
```

### ``katrain/gui/kv/popup_widgets.kv``
```diff
  <LabelledTextInput>:
      font_name: Theme.DEFAULT_FONT
      font_size: sp(Theme.INPUT_FONT_SIZE)
-     helper_text_mode: "none"
      hint_text: ""
      helper_text: ""
-     color_mode: 'custom'
      line_color_focus: Theme.TEXT_COLOR
```

### ``katrain/gui/widgets/progress_loader.py``
Updated the file-header comment to reflect the new (1.2.0) ``MDSpinner`` / ``MDLabel`` situation and to credit the runtime loader.

### ``spec/hook-kivymd.py``
Mirrored the loader's 36-entry ``missing_kv_files`` table. Body strings must stay in sync — a comment cross-references ``katrain.gui._kivymd_kv_loader._STUB_KV``.

### ``spec/KaTrain.spec``
Added ``katrain.gui.lang_bridge`` to ``hiddenimports`` (see *9*).

## Verification

| Check                                | Result                                                              |
| ------------------------------------ | ------------------------------------------------------------------- |
| ``mypy katrain``                     | 0 issues (320 source files)                                         |
| ``ruff check katrain tests``         | clean                                                               |
| ``ruff format --check katrain tests`` | 568 files already formatted                                        |
| ``pytest tests -n auto``             | **5963 passed + 3 skipped**                                         |
| Headless GUI smoke (Python)          | ``KaTrainApp().build()`` returns ``<Screen>`` without error          |
| PyInstaller Linux bundle             | 396 MB binary launches and reaches ``app.run()`` (no crash)          |
| Widget instantiation                 | All ``SizedButton`` family + ``LabelledTextInput`` / ``LabelledCheckBox`` / ``MyNavigationDrawer`` instantiate cleanly under a dummy ``MDApp`` |

The 3 skipped tests are the pre-existing ``CI``-conditional ones in ``test_llm_coach_popup.py`` that require a real X server; they were skipped before this phase too.

## Known follow-ups (out of scope for Phase 277)

- Visual styling differs from Material Design 2 because of the new default colours and ripple animation; we did **not** chase Material You dynamic colour. A future phase can revisit if the user wants MD3 visuals.
- We did not delete the upstream ``kivymd.hooks_path`` in the spec — it still pulls in KivyMD's own ``hook-kivymd.py`` (which is harmless because it no longer matches the ``.kv`` files we generate). Removing it would change the bundle's font/image layout.
- Windows / macOS PyInstaller builds were not verified on this CI run (Linux only). The same spec/hook changes should work on both — they were not Windows-specific — but a Windows .exe build is still pending user-side verification.
