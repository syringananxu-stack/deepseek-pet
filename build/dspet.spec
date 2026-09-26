# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置:免安装(onedir)+ 无控制台窗口"""
import os

PROJ = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = os.path.join(PROJ, "src", "dspet", "assets")

a = Analysis(
    [os.path.join(PROJ, "main.py")],
    pathex=[os.path.join(PROJ, "src")],
    binaries=[],
    datas=[(ASSETS, "assets")],
    hiddenimports=["win32timezone"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "matplotlib", "scipy", "pandas", "IPython", "notebook", "jupyter",
        "PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "pytest",
        "pip", "wheel", "pydoc",
        "numpy.f2py", "PIL.ImageQt", "pywin.dialogs", "pywin.debugger",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DeepSeekPet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(PROJ, "dspet.ico"),
    version=os.path.join(PROJ, "build", "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DeepSeekPet",
)
