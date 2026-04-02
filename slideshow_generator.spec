# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec fuer Slideshow Generator
Erstellt ein einzelnes Executable (--onefile) fuer Windows (.exe) oder macOS.

Benutzen:
  Windows:  pyinstaller slideshow_generator.spec
  macOS:    pyinstaller slideshow_generator.spec
"""

import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

# ── Abhaengigkeiten sammeln ────────────────────────────────────────────────────
# imageio_ffmpeg enthaelt das plattformspezifische ffmpeg-Binary
datas_iio,  bins_iio,  hidden_iio  = collect_all("imageio_ffmpeg")
datas_img,  bins_img,  hidden_img  = collect_all("imageio")
datas_pil,  bins_pil,  hidden_pil  = collect_all("PIL")

all_datas    = datas_iio + datas_img + datas_pil
all_binaries = bins_iio  + bins_img  + bins_pil
all_hidden   = (hidden_iio + hidden_img + hidden_pil
                + ["create_slideshow", "imageio_ffmpeg", "imageio",
                   "PIL", "PIL.Image", "numpy"])

block_cipher = None

a = Analysis(
    ["slideshow_gui.py"],
    pathex=[os.path.dirname(os.path.abspath(SPEC))],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "pandas", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SlideshowGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Kein Konsolenfenster
    disable_windowed_traceback=False,
    argv_emulation=False,   # macOS: kein argv-Emulation
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Optional: Pfad zu .ico (Windows) oder .icns (macOS)
)

# macOS: .app-Bundle zusaetzlich erstellen
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="SlideshowGenerator.app",
        icon=None,
        bundle_identifier="com.slideshowgenerator.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,  # Dark Mode unterstuetzen
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
        },
    )
