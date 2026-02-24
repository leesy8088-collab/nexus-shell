# -*- mode: python ; coding: utf-8 -*-
"""
Nexus Shell — PyInstaller spec (one-dir 모드)

빌드:  pyinstaller nexus_shell.spec
결과:  dist/NexusShell/ 폴더
"""

import os
import site

block_cipher = None

# ctranslate2 네이티브 DLL 경로 탐색
ct2_datas = []
for sp in site.getsitepackages():
    ct2_dir = os.path.join(sp, "ctranslate2")
    if os.path.isdir(ct2_dir):
        ct2_datas.append((ct2_dir, "ctranslate2"))
        break

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets/icon.png", "assets"),       # 트레이 아이콘
    ] + ct2_datas,
    hiddenimports=[
        # PySide6
        "PySide6.QtWidgets",
        "PySide6.QtCore",
        "PySide6.QtGui",
        # faster-whisper / ctranslate2
        "faster_whisper",
        "ctranslate2",
        # 표준 라이브러리 중 동적 임포트
        "urllib.request",
        "urllib.parse",
        "urllib.error",
        "json",
        "shutil",
        "winreg",
        # 프로젝트 내부 모듈
        "version",
        "core.brain",
        "core.brain_router",
        "core.local_brain",
        "core.executor",
        "core.functions",
        "core.shortcuts",
        "core.stt",
        "utils.app_scanner",
        "utils.favorites",
        "utils.clipboard_history",
        "utils.history",
        "utils.system_info",
        "utils.updater",
        "ui.app",
        "ui.hotkey",
        "ui.settings_window",
        "ui.spotlight",
        "ui.tray",
        "ui.worker",
        "ui.shortcut_worker",
        "ui.voice_worker",
        "ui.update_dialog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "pandas", "numpy.testing",
        "pytest", "unittest", "pip", "setuptools",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NexusShell",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # 콘솔 창 숨김 (GUI 앱)
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon="assets/icon.png",  # exe 아이콘
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NexusShell",
)
