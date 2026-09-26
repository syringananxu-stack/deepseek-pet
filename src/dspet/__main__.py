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
    # 「工具箱 → 内存优化」提权后的那个自己:只清内存,不建窗口、不抢单实例互斥体
    if "--mem-purge" in sys.argv:
        from .memopt import helper_main
        return helper_main()
    _dpi_aware()

    # 启动自清洁:清掉历次单文件运行在 %TEMP% 留下的 _MEI* 解包残渣
    # (异常退出/强杀/多开时会残留,每份约 80MB,不清会越堆越大)。
    # 放在建窗口之前、失败静默 —— 绝不拖慢/影响主程序。
    try:
        from . import selfclean
        selfclean.clean_on_startup()
    except Exception:
        pass

    _h, first = _single_instance()
    if not first:
        return 0

    from .paths import resource_path

    if not os.path.exists(resource_path("DSniang1.png")):
        sys.stderr.write("assets missing: %s\n" % resource_path("DSniang1.png"))
        return 2

    # 自绘启动画面:必须在 import pet(重)之前起,才能盖住加载耗时。
    # 失败时静默降级,绝不影响主程序。
    # min_seconds 就是"人为拉长"的总时长 —— 真实加载远快于此,
    # 这段完全是给观感的(Microsoft Office 那种启动仪式感)。
    # 横幅启动画面(launcher 风格):整张插画铺满 + 底部渐变叠标题/进度条。
    # 素材缺失时降级用角色图,再不行才放弃 —— 绝不影响主程序。
    try:
        from . import splashwin
        _banner = resource_path("splash_banner_clean.png")
        _fallback = resource_path("DSniang1.png")
        splashwin.start(_banner if os.path.exists(_banner) else _fallback,
                        min_seconds=3.0, text="正在启动…")
    except Exception:
        splashwin = None

    try:
        from .pet import Pet
        if splashwin is not None:
            splashwin.set_progress(0.55, "正在唤醒鱼儿…")
        Pet().start()

        # Pet().start() 会一直阻塞(跑消息循环),到这里说明窗口已建好、splash 已关。
    except Exception:
        if splashwin is not None:
            splashwin.close()
        raise
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
