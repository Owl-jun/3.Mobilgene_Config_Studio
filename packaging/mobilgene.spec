# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Mobilgene Config Studio portable (Windows x64)
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
SCRIPTS = ROOT / "scripts"
UI = ROOT / "ui"
SCHEMAS = ROOT / "schemas"

block_cipher = None

a = Analysis(
    [str(SCRIPTS / "launcher_main.py")],
    pathex=[str(SCRIPTS)],
    binaries=[],
    datas=[
        (str(UI), "ui"),
        (str(SCHEMAS), "schemas"),
    ],
    hiddenimports=[
        "app_paths",
        "arxml_parser",
        "ref_index",
        "related_context",
        "module_graph",
        "workspace_browser",
        "tkinter",
        "tkinter.filedialog",
        "_tkinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MobilgeneConfigStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MobilgeneConfigStudio",
)
