# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
onedir = os.environ.get('PT_ONEDIR') == '1'

a = Analysis(
    ['src/participation_tracker/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/participation_tracker/db/schema.sql', 'participation_tracker/db'), ('assets/icon.ico', 'assets'), ('assets/chime.wav', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['QtWebEngineCore', 'QtQuick', 'QtQml', 'Qt3DCore', 'Qt3DRender', 'Qt3DWidgets', 'QtMultimedia', 'QtCharts', 'QtNetwork'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
if onedir:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Participation Tracker', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False, disable_windowed_traceback=False, icon='assets/icon.ico')
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name='Participation Tracker')
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Participation Tracker', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False, disable_windowed_traceback=False, icon='assets/icon.ico')
