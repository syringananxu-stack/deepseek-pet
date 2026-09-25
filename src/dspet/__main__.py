# -*- coding: utf-8 -*-
"""入口:python -m dspet"""
import os
import sys


def _single_instance():
    """同一台机器只允许一只大肥鱼(自启 + 手动启动不会变成两只)。
    ⚠️ 但**僵尸进程**会一直占着互斥体 → 用户"再也打不开、exe 也删不掉" →
    所以互斥体已存在时还要确认对方真的有宠物窗口;等 1.5 秒都没有 = 僵尸,照常启动。"""
    import ctypes
    import time
    h = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\DeepSeekPetFishSingleton")
    if ctypes.windll.kernel32.GetLastError() != 183:
        return h, True
    try:
        import win32gui
        for _ in range(6):
            if win32gui.FindWindow("DSPetWnd", None):
                return h, False            # 真的有一只在跑 → 本进程直接退出
            time.sleep(0.25)
    except Exception:
        return h, False
    return h, True                         # 只有互斥体没窗口 = 僵尸,允许启动


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
    # ⚠️ 不用 return/sys.exit:tkinter 的守护线程在解释器收尾阶段可能死锁 → 进程会"假活"
    #    (用户看到:关了还在、再开没反应、exe 删不掉)。直接结束进程最干净。
    # ⚠️⚠️ windowed 打包下 sys.stdout 就是 None,别拿它 flush(会 AttributeError → 卡在报错框)
    try:
        if sys.stdout is not None:
            sys.stdout.flush()
    except Exception:
        pass
    os._exit(0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
