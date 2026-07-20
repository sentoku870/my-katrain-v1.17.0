"""Phase 277: PyInstaller hook for KivyMD 1.2.0.

KivyMD 1.2.0 ships without its companion ``.kv`` files in the sdist
(see the runtime counterpart ``katrain/gui/_kivymd_kv_loader.py``).
The frozen build also needs the missing ``.kv`` files baked in,
otherwise the first ``from kivymd.uix.X import Y`` import at startup
crashes with ``FileNotFoundError``.

This hook reuses the runtime loader's ``STUB_KV`` table so the two
paths (dev / CI vs frozen bundle) can never drift. PyInstaller picks
up the stub directory via the ``datas`` list below.
"""

from PyInstaller.utils.hooks import collect_data_files, get_package_paths
import os
import sys
import tempfile


# Collect all KivyMD data files (fonts/images directories). The .kv
# files themselves are not present in the 1.2.0 wheel and are
# generated below.
datas = collect_data_files("kivymd")

# Add specific KivyMD paths explicitly -- ``collect_data_files`` can
# miss per-subpackage data when the sdist ships only the ``.py``
# files (as 1.2.0 does).
kivymd_path = get_package_paths("kivymd")[1]
for data_dir in ("fonts", "images", "uix"):
    dir_path = os.path.join(kivymd_path, data_dir)
    if os.path.exists(dir_path):
        datas.append((dir_path, f"kivymd/{data_dir}"))


# Import the stub .kv table from the runtime loader. The loader is
# pure-Python with no Kivy / KivyMD side-effects at module import time,
# so it is safe to pull into the build-time hook.
_katrain_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _katrain_root not in sys.path:
    sys.path.insert(0, _katrain_root)

from katrain.gui._kivymd_kv_loader import STUB_KV  # noqa: E402


# Write stubs to a tempdir and add them to datas so PyInstaller ships
# them inside the bundle at the relative path the runtime expects.
temp_dir = tempfile.mkdtemp(prefix="kivymd_1_2_kv_stubs_")
for kv_path, kv_content in STUB_KV.items():
    full_temp_path = os.path.join(temp_dir, kv_path)
    os.makedirs(os.path.dirname(full_temp_path), exist_ok=True)
    with open(full_temp_path, "w", encoding="utf-8") as f:
        f.write(kv_content)
    datas.append((full_temp_path, kv_path))


# Hidden imports -- the upstream KivyMD hook does not include these,
# but we reference them transitively and PyInstaller's static
# analyser misses the .so symbols in compiled packages.
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
