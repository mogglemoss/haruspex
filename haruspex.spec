# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for HARUSPEX
# Build: uv run pyinstaller haruspex.spec

a = Analysis(
    ["haruspex/main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("haruspex/data/ships.json", "haruspex/data"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="haruspex",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="universal2",
    codesign_identity=None,
    entitlements_file=None,
)
