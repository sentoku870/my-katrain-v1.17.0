"""Phase 277: PyInstaller hook for KivyMD 1.2.0.

KivyMD 1.2.0 ships without its companion ``.kv`` files in the sdist
(see ``spec/hook-kivymd.py`` history and the runtime counterpart
``katrain/gui/_kivymd_kv_loader.py``). The frozen build also needs the
missing ``.kv`` files baked in, otherwise the first
``from kivymd.uix.X import Y`` import at startup crashes with
``FileNotFoundError``.

This hook mirrors the runtime loader: it generates stub ``.kv`` files
in a tempdir and adds them to ``datas``. PyInstaller then copies the
files into the bundle and the bundled ``kivymd.uix_path`` (which still
points at the original package directory inside the bundle) finds
them.

The body strings must stay in sync with
``katrain/gui/_kivymd_kv_loader._STUB_KV``.
"""

from PyInstaller.utils.hooks import collect_data_files, get_package_paths
import os
import shutil
import tempfile


# Collect all KivyMD data files (the .kv files inside the bundle plus
# the fonts/images directories).
datas = collect_data_files("kivymd")

# Add specific KivyMD paths explicitly -- ``collect_data_files`` can
# miss per-subpackage data when the sdist ships only the ``.py``
# files (as 1.2.0 does).
kivymd_path = get_package_paths("kivymd")[1]

for data_dir in ("fonts", "images", "uix"):
    dir_path = os.path.join(kivymd_path, data_dir)
    if os.path.exists(dir_path):
        datas.append((dir_path, f"kivymd/{data_dir}"))


# KivyMD 1.2.0 ships without these ``.kv`` files. Generate stub rules
# so ``Builder.load_string`` finds something on every import path.
# Body strings MUST match ``katrain.gui._kivymd_kv_loader._STUB_KV``.
missing_kv_files = {
    "kivymd/uix/backdrop/backdrop.kv": "<MDBackdrop>:\n",
    "kivymd/uix/banner/banner.kv": "<MDBanner>:\n",
    "kivymd/uix/bottomnavigation/bottomnavigation.kv": "<MDBottomNavigation>:\n",
    "kivymd/uix/bottomsheet/bottomsheet.kv": "<MDBottomSheet>:\n",
    "kivymd/uix/button/button.kv": (
        "<MDButton>:\n"
        "    disabled_color: self.theme_cls.disabled_hint_text_color\n"
    ),
    "kivymd/uix/card/card.kv": (
        "<MDCard>:\n"
        "    elevation: 0\n"
        "    md_bg_color: self.theme_cls.bg_light\n"
    ),
    "kivymd/uix/chip/chip.kv": "<MDChip>:\n",
    "kivymd/uix/datatables/datatables.kv": "<MDDataTable>:\n",
    "kivymd/uix/dialog/dialog.kv": "<MDDialog>:\n",
    "kivymd/uix/dropdownitem/dropdownitem.kv": "<MDDropDownItem>:\n",
    "kivymd/uix/expansionpanel/expansionpanel.kv": "<MDExpansionPanel>:\n",
    "kivymd/uix/filemanager/filemanager.kv": "<MDFileManager>:\n",
    "kivymd/uix/imagelist/imagelist.kv": "<MDSmartTile>:\n",
    "kivymd/uix/label/label.kv": (
        "<MDLabel>:\n"
        "    disabled_color: self.theme_cls.disabled_hint_text_color\n"
        "    text_size: self.size\n"
    ),
    "kivymd/uix/list/list.kv": "<MDList>:\n",
    "kivymd/uix/menu/menu.kv": "<MDDropdownMenu>:\n",
    "kivymd/uix/navigationdrawer/navigationdrawer.kv": (
        "<MDNavigationDrawer>:\n"
        "    close_on_click: True\n"
    ),
    "kivymd/uix/navigationrail/navigationrail.kv": "<MDNavigationRail>:\n",
    "kivymd/uix/pickers/colorpicker/colorpicker.kv": "<MDColorPicker>:\n",
    "kivymd/uix/pickers/datepicker/datepicker.kv": "<MDDatePicker>:\n",
    "kivymd/uix/pickers/timepicker/timepicker.kv": "<MDTimePicker>:\n",
    "kivymd/uix/progressbar/progressbar.kv": "<MDProgressBar>:\n",
    "kivymd/uix/refreshlayout/refreshlayout.kv": "<MDRefreshLayout>:\n",
    "kivymd/uix/segmentedbutton/segmentedbutton.kv": "<MDSegmentedButton>:\n",
    "kivymd/uix/segmentedcontrol/segmentedcontrol.kv": "<MDSegmentedControl>:\n",
    "kivymd/uix/selection/selection.kv": "<MDSelection>:\n",
    "kivymd/uix/selectioncontrol/selectioncontrol.kv": (
        "<MDCheckbox>:\n"
        "    ripple_effect: True\n"
    ),
    "kivymd/uix/slider/slider.kv": "<MDSlider>:\n",
    "kivymd/uix/sliverappbar/sliverappbar.kv": "<MDSliverAppBar>:\n",
    "kivymd/uix/snackbar/snackbar.kv": "<MDSnackbar>:\n",
    "kivymd/uix/spinner/spinner.kv": "<MDSpinner>:\n",
    "kivymd/uix/tab/tab.kv": "<MDTabs>:\n",
    "kivymd/uix/textfield/textfield.kv": (
        "<MDTextField>:\n"
        "    disabled_color: self.theme_cls.disabled_hint_text_color\n"
    ),
    "kivymd/uix/toolbar/toolbar.kv": "<MDTopAppBar>:\n",
    "kivymd/uix/tooltip/tooltip.kv": "<MDTooltip>:\n",
    "kivymd/uix/transition/transition.kv": "<MDScreenTransition>:\n",
}


# Write stubs to a tempdir and add them to datas so PyInstaller ships
# them inside the bundle at the relative path the runtime expects.
temp_dir = tempfile.mkdtemp(prefix="kivymd_1_2_kv_stubs_")
for kv_path, kv_content in missing_kv_files.items():
    full_temp_path = os.path.join(temp_dir, kv_path)
    os.makedirs(os.path.dirname(full_temp_path), exist_ok=True)
    with open(full_temp_path, "w") as f:
        f.write(kv_content)
    datas.append((full_temp_path, kv_path))


# Hidden imports -- the upstream hook does not include these, but we
# reference them transitively and PyInstaller's static analyser misses
# the .so symbols in compiled packages.
hiddenimports = [
    "kivymd.icon_definitions",
    "kivymd.font_definitions",
    "kivymd.color_definitions",
    "kivymd.uix.label.label",
    "kivymd.uix.button.button",
    "kivymd.uix.textfield.textfield",
    "kivymd.uix.card.card",
    "kivymd.uix.navigationdrawer.navigationdrawer",
    "kivymd.uix.selectioncontrol.selectioncontrol",
    "kivymd.uix.behaviors.ripple_behavior",
    "kivymd.theming",
    "materialyoucolor",
]
