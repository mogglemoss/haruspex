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
    hiddenimports=[
        # Textual's Linux input driver and key parser are dynamically loaded
        # and not detected by PyInstaller's static analysis.
        "textual.drivers.linux_driver",
        "textual.drivers._input_reader_linux",
        "textual.drivers._writer_thread",
        "textual.drivers._byte_stream",
        "textual._xterm_parser",
        "textual._parser",
        "textual._loop",
        "textual._keyboard_protocol",
        "textual.keys",
        # Ensure terminal raw-mode modules are bundled on Linux
        "termios",
        "tty",
    ],
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
