# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')
branding_datas = [('assets/branding', 'assets/branding')]
runtime_datas = [('assets/runtime', 'assets/runtime')]
legal_datas = [
    ('LICENSE', '.'),
    ('THIRD_PARTY_NOTICES.txt', '.'),
    ('KREA_SAFETY_AND_USE.txt', '.'),
    ('GPL_DISTRIBUTION_CHECKLIST.txt', '.'),
    ('build/legal', 'licenses'),
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=cv2_binaries,
    datas=cv2_datas + branding_datas + runtime_datas + legal_datas,
    hiddenimports=cv2_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest.mock'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UnumSuntSpriteStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='build/windows_version_info.txt',
    icon='assets/branding/app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='UnumSuntSpriteStudio',
)
