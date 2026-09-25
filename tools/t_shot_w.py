# -*- coding: utf-8 -*-
"""源码版单档截图:python t_shot_w.py <0|1|2> → workspace/_w_lvN.png"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import win32gui                                                        # noqa: E402
from PIL import ImageGrab                                              # noqa: E402

from dspet import config                                               # noqa: E402
from dspet import settings_ui as SU                                    # noqa: E402

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
lv = int(sys.argv[1]) if len(sys.argv) > 1 else 1
cfg = config.load()
cfg["ui_scale"] = lv
w = SU.SettingsWindow(cfg, None)
for _ in range(8):
    w.root.update()
    time.sleep(0.12)
hwnd = w.root.winfo_id()
r = win32gui.GetWindowRect(hwnd)
src = win32gui.GetParent(hwnd)
for cand in (src, hwnd):
    rr = win32gui.GetWindowRect(cand)
    if (rr[2] - rr[0]) > 100:
        r = rr
print("lv=%d rect=%s size=%s 内容高=%d" % (lv, r, (r[2] - r[0], r[3] - r[1]),
                                           w.root.winfo_reqheight()))
ImageGrab.grab(bbox=(r[0] - 3, r[1] - 3, r[2] + 3, r[3] + 3)).save(
    os.path.join(WS, "_w_lv%d.png" % lv))
sys.stdout.flush()
os._exit(0)
