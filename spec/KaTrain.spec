# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import subprocess
from pathlib import Path

# Prevent Kivy from creating windows during build process
os.environ['KIVY_HEADLESS'] = '1'
os.environ['KIVY_NO_WINDOW'] = '1'
os.environ['KIVY_GL_BACKEND'] = 'mock'

block_cipher = None

# Platform detection
is_windows = sys.platform.startswith('win')
is_macos = sys.platform == 'darwin'
is_linux = sys.platform.startswith('linux')

print(f"Building for platform: {sys.platform}")

# Cross-platform imports
from kivymd import hooks_path as kivymd_hooks_path
from kivy.tools.packaging.pyinstaller_hooks import get_deps_minimal

# Get base Kivy dependencies (cross-platform)
kivy_deps = get_deps_minimal()

# Platform-specific additions
if is_windows:
    from kivy_deps import sdl2, glew
   # Windows version info
    sys.path.append(SPECPATH)
    try:
        import file_version as versionModule
        version_info = versionModule.versionInfo
    except:
        version_info = None

# Define common data files - all paths relative to spec file location
base_path = "../katrain"
sep = "/"

datas = [
    (f"{base_path}/gui/kv", "katrain/gui/kv"),
    (f"{base_path}/config.json", "katrain"),
    (f"{base_path}/models", "katrain/models"),
    (f"{base_path}/sounds", "katrain/sounds"),
    (f"{base_path}/img", "katrain/img"),
    (f"{base_path}/fonts", "katrain/fonts"),
    (f"{base_path}/i18n", "katrain/i18n"),
    (f"{base_path}/KataGo", "katrain/KataGo"),
    # PR-03: Bundle the Go Lexicon YAML so LLM Coach prompts can resolve
    # terminology in the distributed Windows binary (PR-03 ⑤). The source
    # path is the repo root's docs/resources/; we expose it as a sibling
    # directory next to ``katrain/`` inside the bundle so the lexicon
    # loader can locate it via ``sys._MEIPASS`` at runtime.
    ("../docs/resources", "docs/resources"),
]

# KivyMD data files will be handled by the custom hook

# Platform-specific binaries
binaries = kivy_deps.get('binaries', [])
if is_macos:
    # Add macOS-specific KataGo binary if it exists
    katago_osx_path = f'{base_path}/KataGo/katago-osx'
    if os.path.exists(katago_osx_path):
        binaries.append((katago_osx_path, 'katrain/KataGo/'))
    else:
        print(f"Warning: {katago_osx_path} not found, skipping macOS KataGo binary")

# Platform-specific hidden imports (add to Kivy's base)
hiddenimports = kivy_deps.get('hiddenimports', [])
if is_windows:
    hiddenimports.extend(["win32file", "win32timezone", "six"])

# Phase 277: KV files reference these modules via #:import directives
# that PyInstaller's static analysis misses. ``lang_bridge`` was the
# immediate crash in the KivyMD 1.2.0 bundle; the others are listed
# proactively because they are imported by KV the same way.
hiddenimports.extend(
    [
        "katrain.gui.lang_bridge",
    ]
)

# Phase 284: legacy Kivy widgets referenced by lazy imports that the
# Clock-based dispatcher triggers after startup. PyInstaller's static
# analysis misses these because they are only reached when the user
# opens the settings popup or batch analyze popup; the corresponding
# symbols are never encountered during frozen-build time collection.
# Without these explicit entries the frozen bundle crashes with
# ``ModuleNotFoundError: No module named 'kivy.uix.tabbedpanel'`` or
# ``kivy.uix.checkbox'`` the first time the user navigates to either
# popup (user-reported after Phase 283 merge).
hiddenimports.extend(
    [
        "kivy.uix.tabbedpanel",
        "kivy.uix.checkbox",
    ]
)

# Platform-specific hooks and excludes
hookspath = kivy_deps.get('hookspath', [])
hookspath.append(kivymd_hooks_path)
# Add custom KivyMD hook directory
hookspath.append(SPECPATH)

# Exclude problematic modules
excludes = kivy_deps.get('excludes', []) + ["scipy", "pandas", "numpy", "matplotlib", "docutils"]
if is_windows:
    excludes.append("mkl")

# Fix SDL2 conflicts on macOS by excluding ffpyplayer
if is_macos:
    excludes.extend(["ffpyplayer", "pygame"])

# Entry point - relative to spec file location
entry_point = f"{base_path}/__main__.py"

a = Analysis(
    [entry_point],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspath,
    runtime_hooks=kivy_deps.get('runtime_hooks', []),
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

print("SCRIPTS", len(a.scripts), "BIN", len(a.binaries), "ZIP", len(a.zipfiles), "DATA", len(a.datas))

# Filter out unnecessary data files
EXCLUDE_SUFFIX = ["katago"]
EXCLUDE = ["KataGoData", "anim_", "screenshot_", "__pycache__"]
a.datas = [
    (ff, ft, tp)
    for ff, ft, tp in a.datas
    if not any(ff.endswith(suffix) for suffix in EXCLUDE_SUFFIX)
    and not any(kw in ff for kw in EXCLUDE)
]

print("DATA FILTERED", len(a.datas))

# Platform-specific build configurations
if is_windows:
    console_names = {True: "DebugKaTrain", False: "KaTrain"}

    # Setup PowerShell for signing (Windows only)
    try:
        powershell = subprocess.Popen(["powershell"], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    except:
        powershell = None

    for console, name in console_names.items():
        pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

        exe = EXE(
            pyz,
            a.scripts,
            [],
            exclude_binaries=True,
            name=name,
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=True,
            console=console,
            icon=f"{base_path}/img/icon.ico",
            version=version_info,
        )

        coll = COLLECT(
            exe,
            a.binaries,
            a.zipfiles,
            a.datas,
            *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins)],
            strip=False,
            upx=True,
            upx_exclude=[],
            name=name,
        )

        # Single file executable (Windows)
        exe_single = EXE(
            pyz,
            a.scripts,
            a.binaries,
            a.zipfiles,
            a.datas,
            *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins)],
            debug=False,
            strip=False,
            upx=True,
            name=name,
            console=console,
            icon=f"{base_path}/img/icon.ico",
            version=version_info,
        )

        # Code signing (Windows) - skip in CI environment
        if powershell and not os.environ.get('GITHUB_ACTIONS'):
            powershell.stdin.write(f"Set-AuthenticodeSignature dist/{name}.exe -Certificate (Get-ChildItem Cert:\\CurrentUser\\My -CodeSigningCert)\n".encode('ascii'))
            powershell.stdin.write(f"Set-AuthenticodeSignature dist/{name}/{name}.exe -Certificate (Get-ChildItem Cert:\\CurrentUser\\My -CodeSigningCert)\n".encode('ascii'))
            powershell.stdin.flush()

else:
    # macOS and Linux build
    pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='KaTrain',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='KaTrain',
    )

    # macOS app bundle
    if is_macos:
        # Get version from environment or default
        app_version = os.environ.get('KATRAIN_VERSION', '1.0.0')

        app = BUNDLE(
            coll,
            name='KaTrain.app',
            icon=f'{base_path}/img/icon.icns',
            bundle_identifier='org.katrain.KaTrain',
            version=app_version,
            info_plist={
                'NSHighResolutionCapable': 'True',
                'NSAppleScriptEnabled': False,
                'CFBundleDocumentTypes': [
                    {
                        'CFBundleTypeName': 'Stone Game Format',
                        'CFBundleTypeRole': 'Editor',
                        'LSHandlerRank': 'Owner',
                        'LSItemContentTypes': ['org.katrain.sgf'],
                        'CFBundleTypeExtensions': ['sgf', 'SGF']
                    }
                ],
                'UTExportedTypeDeclarations': [
                    {
                        'UTTypeIdentifier': 'org.katrain.sgf',
                        'UTTypeDescription': 'KaTrain SGF File',
                        'UTTypeConformsTo': ['public.data', 'public.text'],
                        'UTTypeTagSpecification': {
                            'public.filename-extension': ['sgf', 'SGF']
                        }
                    }
                ]
            },
        )
