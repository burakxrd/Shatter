# -*- mode: python ; coding: utf-8 -*-
"""
Shatter — PyInstaller spec file for portable one-folder build.

Usage:
    pyinstaller shatter.spec --noconfirm

Output:
    dist/Shatter/  → portable folder, zip it and distribute.
"""

import sys
from pathlib import Path

ROOT = Path('.').resolve()

a = Analysis(
    ['shatter.pyw'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Web UI assets (HTML, CSS, JS, fonts, images)
        (str(ROOT / 'ui' / 'web'), 'ui/web'),
        # App icon / logo
        (str(ROOT / 'assets' / 'Shatter.png'), 'assets'),
    ],
    hiddenimports=[
        # pywebview EdgeChromium backend (Windows)
        'webview',
        'webview.platforms',
        'webview.platforms.edgechromium',
        'clr_loader',
        'pythonnet',
        # name-that-hash
        'name_that_hash',
        'name_that_hash.runner',
        'name_that_hash.hashes',
        # psutil
        'psutil',
        # py7zr (for hashcat .7z extraction)
        'py7zr',
        'py7zr.archiveinfo',
        'py7zr.compressor',
        'py7zr.properties',
        'multivolumefile',
        'inflate64',
        'pybcj',
        'pyppmd',
        'texttable',
        'pycryptodomex',
        'Cryptodome',
        'Cryptodome.Cipher',
        'Cryptodome.Cipher.AES',
        'Cryptodome.Hash',
    ],
    excludes=[
        # Reduce bundle size — Shatter doesn't use these
        'tkinter',
        'matplotlib',
        'PIL',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'notebook',
        'pytest',
        # Scapy is lazy-imported; include only if PCAP parsing is needed.
        # Uncomment the line below to EXCLUDE scapy (~50 MB savings):
        # 'scapy',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # one-folder mode (NOT onefile)
    name='Shatter',
    debug=False,
    strip=False,
    upx=True,
    console=False,          # GUI app, no console window
    icon=str(ROOT / 'assets' / 'Shatter.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Shatter',
)
