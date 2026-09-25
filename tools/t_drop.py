# -*- coding: utf-8 -*-
"""拖放喂食链路实测(源码版)
⚠️ 消息泵必须和窗口同线程!所以主线程 PumpMessages,喂食动作丢给子线程。
"""
import ctypes
import os
import sys
import threading
import time

import win32con
import win32gui

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

os.environ["DSPET_DEBUG"] = "1"

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
FEED = os.path.join(WS, "_egg_token_test.txt")
WM_DROPFILES = 0x0233

u = ctypes.windll.user32
k = ctypes.windll.kernel32


def drop(path, hwnd):
    data = path.encode("utf-16-le") + b"\x00\x00"
    hdr = ctypes.create_string_buffer(20)
    ctypes.memset(hdr, 0, 20)
    ctypes.cast(hdr, ctypes.POINTER(ctypes.c_uint32))[0] = 20
    ctypes.cast(hdr, ctypes.POINTER(ctypes.c_uint32))[4] = 1
    blk = hdr.raw + data
    k.GlobalAlloc.restype = ctypes.c_void_p
    k.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    hmem = k.GlobalAlloc(0x0042, len(blk))
    p = k.GlobalLock(hmem)
    ctypes.memmove(p, blk, len(blk))
    k.GlobalUnlock(ctypes.c_void_p(hmem))
    u.PostMessageW(hwnd, WM_DROPFILES, hmem, 0)


from dspet.paths import config_path                            # noqa: E402
from dspet.pet import Pet                                      # noqa: E402

LOG = os.path.join(os.path.dirname(config_path()), "_dbg.log")
try:
    os.remove(LOG)
except Exception:
    pass

with open(FEED, "w", encoding="utf-8") as f:
    f.write("token")

p = Pet()
HWND = p.hwnd


def worker():
    time.sleep(1.2)
    print("feed:", FEED)
    drop(FEED, HWND)
    dlg = 0
    t = time.time()
    while time.time() - t < 5 and not dlg:
        time.sleep(0.15)
        dlg = win32gui.FindWindow("#32770", "喂给大肥鱼")
    print("确认框:", dlg)
    if dlg:
        win32gui.PostMessage(dlg, win32con.WM_COMMAND, 6, 0)   # 选“是”
    xs = []
    t0 = time.time()
    while time.time() - t0 < 4.0:
        xs.append((time.time(), win32gui.GetWindowRect(HWND)[:2]))
        time.sleep(0.05)
    spd = 0.0
    for i in range(1, len(xs) - 1):
        dt = xs[i + 1][0] - xs[i][0]
        if dt > 0:
            v = (((xs[i + 1][1][0] - xs[i][1][0]) ** 2 +
                  (xs[i + 1][1][1] - xs[i][1][1]) ** 2) ** 0.5) / dt
            spd = max(spd, v)
    print("最高速度 %.0f px/s" % spd)
    print("文件还在吗:", os.path.exists(FEED))
    print("--- 调试日志尾部 ---")
    try:
        for ln in open(LOG, encoding="utf-8", errors="replace").read().splitlines()[-6:]:
            print(ln.encode("gbk", "replace").decode("gbk"))
    except Exception as e:
        print("no log", e)
    print("RESULT:", "PASS" if (dlg and spd > 120 and not os.path.exists(FEED)) else
          "FAIL(dlg=%s spd=%.0f)" % (dlg, spd))
    sys.stdout.flush()
    os._exit(0)


threading.Thread(target=worker, daemon=True).start()
p.start()                       # ⬅️ 主线程跑消息泵
