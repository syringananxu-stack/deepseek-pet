# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置:轻量版单文件 exe。

轻量版 = 只保留「游玩 / 观赏 / 陪伴 / 看余额」:
  * 不含内存优化(memopt)
  * 不含开机自启写入(autostart)
  * 不含喂文件(拖文件到她身上)
交互与动画与完全版一致。
"""
import os

PROJ = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = os.path.join(PROJ, "src", "dspet", "assets")
VER = os.path.join(PROJ, "build", "version_info_lite.txt")
ICON = os.path.join(PROJ, "dspet.ico")

a = Analysis(
    [os.path.join(PROJ, "main_lite.py")],
    pathex=[os.path.join(PROJ, "src")],
    binaries=[],
    datas=[(ASSETS, "assets")],
    hiddenimports=["win32timezone"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "matplotlib", "scipy", "pandas", "IPython", "notebook", "jupyter",
        "PyQt5", "PyQt6", "PySide2", "wx", "pytest",
        "pip", "wheel", "pydoc", "numpy.f2py", "PIL.ImageQt",
        "pywin.dialogs", "pywin.debugger",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    # 启动画面改为自绘(splashwin.py),不再用 PyInstaller Splash():
    # 实测 onefile 下 bootloader 解包耗时吃掉了整个启动窗口,且是打包黑盒、难调试。
    a.binaries,
    a.datas,
    [],
    name="DeepSeekPet-Lite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=ICON if os.path.exists(ICON) else None,
    version=VER if os.path.exists(VER) else None,
)
