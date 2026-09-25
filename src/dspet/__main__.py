# -*- coding: utf-8 -*-
"""入口:python -m dspet"""
import os
import sys


def _single_instance():
    """同一台机器只允许一只大肥鱼(自启 + 手动启动不会变成两只)"""
    import ctypes
    h = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\DeepSeekPetFishSingleton")
    return h, ctypes.windll.kernel32.GetLastError() != 183


def _dpi_aware():
    """高 DPI 适配:per-monitor v2(打包版走 main.py,这里兜住源码运行)"""
    import ctypes
    for fn in (lambda: ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)),
               lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
               lambda: ctypes.windll.user32.SetProcessDPIAware()):
        try:
            fn()
            return
        except Exception:
            continue


def main():
    _dpi_aware()
    _h, first = _single_instance()
    if not first:
        return 0
    from .pet import Pet
    from .paths import resource_path

    if not os.path.exists(resource_path("DSniang1.png")):
        sys.stderr.write("assets missing: %s\n" % resource_path("DSniang1.png"))
        return 2
    Pet().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
