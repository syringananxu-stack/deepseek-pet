# -*- coding: utf-8 -*-
"""轻量版统一入口。

与 `main.py` 一样负责 DPI 适配 / 路径引导 / 异常落日志,
区别只在启动前把「轻量版」这个事实告诉 dspet:
  * DSPET_EDITION=lite   -> pet.py 据此隐藏内存优化 / 开机自启 / 喂文件
"""
import os
import sys
import traceback

EDITION = "lite"


def _bootstrap_path():
    if not getattr(sys, "frozen", False):
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
        if src not in sys.path:
            sys.path.insert(0, src)


def _log_exception(exc_text):
    try:
        from dspet.paths import log_path
        p = log_path()
    except Exception:
        p = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "dspet.log")
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(exc_text + "\n")
    except Exception:
        pass


def _dpi_aware():
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


if __name__ == "__main__":
    os.environ["DSPET_EDITION"] = EDITION
    _dpi_aware()
    _bootstrap_path()
    try:
        from dspet.__main__ import main
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        _log_exception(traceback.format_exc())
        raise
