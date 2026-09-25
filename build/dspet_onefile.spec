# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置(单文件 exe)"""
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
        "pip", "wheel", "pydoc", "numpy.f2py", "PIL.ImageQt",
        "pywin.dialogs", "pywin.debugger",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DeepSeekPet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(PROJ, "dspet.ico"),
)
