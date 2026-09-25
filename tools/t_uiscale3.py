# -*- coding: utf-8 -*-
"""小屏 × 界面档位:验证 小档/大档 在小屏下是否自动切「上下滚」且底栏仍在"""
import os
import shutil
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import win32gui                                                       # noqa: E402
from PIL import ImageGrab                                             # noqa: E402

from dspet import config                                              # noqa: E402
from dspet.paths import config_path                                   # noqa: E402
from dspet.settings_ui import UI_SCALES, SettingsWindow               # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
FAKE_H = int(os.environ.get("FAKE_H", "800"))
tk.Misc.winfo_screenheight = lambda self: FAKE_H

path = config_path()
shutil.copyfile(path, path + ".bak9")
try:
    base = config.load()
    for lv in (0, 2):
        cfg = dict(base)
        cfg["ui_scale"] = lv
        w = SettingsWindow(cfg)
        w._x = 40
        w.root.geometry("+40+%d" % w._y)
        w.root.attributes("-alpha", 1.0)
        t = time.time()
        while time.time() - t < 0.9:
            w.root.update()
            time.sleep(0.02)
        hwnd = w.root.winfo_id()
        top = win32gui.GetParent(hwnd) or hwnd
        r = win32gui.GetWindowRect(top)
        has_scroll = hasattr(w, "_scroll") and w._scroll.winfo_exists() == 1
        print("假屏高%d 档位%s scale=%.2f compact=%s 滚动区=%s 窗口=%dx%d font=%d" % (
            FAKE_H, ["小", "中", "大"][lv], UI_SCALES[lv], w.compact, has_scroll,
            r[2] - r[0], r[3] - r[1], w.lbl_level.cget("font").cget("size")))
        if has_scroll:
            w._scroll._parent_canvas.yview_moveto(1.0)
            t = time.time()
            while time.time() - t < 0.4:
                w.root.update()
                time.sleep(0.02)
        ImageGrab.grab(bbox=(r[0] - 4, r[1] - 4, r[2] + 4, r[3] + 4)).save(
            os.path.join(WS, "_ui_small_L%d.png" % lv))
        w.root.destroy()
        time.sleep(0.4)
finally:
    shutil.copyfile(path + ".bak9", path)
    os.remove(path + ".bak9")
print("saved _ui_small_L0/L2.png")
