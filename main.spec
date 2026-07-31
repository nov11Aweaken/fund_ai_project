# -*- mode: python ; coding: utf-8 -*-

import certifi

certifi_cacert_path = certifi.where()

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (certifi_cacert_path, 'certifi'),
        ('.\\assets\\echarts.min.js', 'assets'),
        ('.\\assets\\icon.png', 'assets'),
        ('.\\assets\\fonts', 'assets\\fonts'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
