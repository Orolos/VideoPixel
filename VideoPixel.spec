# -*- mode: python ; coding: utf-8 -*-
# Rulează cu:  pyinstaller --noconfirm --clean VideoPixel.spec
a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=[("assets", "assets")],
    hiddenimports=["vlc"],
    excludes=["tkinter", "pytest", "unittest", "PySide6.QtNetwork", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtSvg", "PySide6.QtOpenGL"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="VideoPixel",
    console=False,
    icon="assets/videopixel.ico",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="VideoPixel")
