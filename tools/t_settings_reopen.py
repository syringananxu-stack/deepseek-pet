# -*- coding: utf-8 -*-
"""设置窗「关掉→再打开」自测(源码版):验证复用同一个 root,不再卡死"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import win32con                                                       # noqa: E402
import win32gui                                                       # noqa: E402

from dspet import config                                              # noqa: E402
from dspet import settings_ui as SU                                   # noqa: E402


def wins():
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and t.startswith("设置"):
            out.append((h, win32gui.GetWindowRect(h)))

    win32gui.EnumWindows(cb, None)
    return out


def wait_open(timeout=8):
    t = time.time()
    while time.time() - t < timeout:
        w = wins()
        if w:
            time.sleep(0.6)
            return wins()
        time.sleep(0.2)
    return []


def close_all():
    for (h, _) in wins():
        win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
    t = time.time()
    while time.time() - t < 3 and wins():
        time.sleep(0.2)


cfg = config.load()
closes = []
for i in range(3):
    SU.open_settings(cfg, on_close=lambda: closes.append(1))
    w = wait_open()
    print("第%d次打开:" % (i + 1), [(r[2] - r[0], r[3] - r[1]) for (_, r) in w] or "失败")
    if not w:
        break
    close_all()
    time.sleep(0.6)
print("on_close 回调次数:", len(closes), "(应为 3)")
print("RESULT:", "PASS" if (len(closes) == 3) else "FAIL")
sys.stdout.flush()
os._exit(0)
