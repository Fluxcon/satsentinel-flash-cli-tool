# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for satsentinel-cli

import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata, collect_data_files

block_cipher = None

a = Analysis(
    ['satsentinel_flash/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('satsentinel_flash/_nvs_partition_gen.py', 'satsentinel_flash'),
        *copy_metadata('satsentinel-cli'),
        *collect_data_files('esptool'),
    ],
    hiddenimports=[
        'esptool',
        'esptool.cmds',
        'esptool.targets',
        'esptool.targets.esp32s3',
        'esptool.loader',
        'esptool.bin_image',
        'esptool.util',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'questionary',
        'rich',
        'rich.console',
        'rich.panel',
        'rich.progress',
        'click',
        'requests',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='satsentinel-cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
