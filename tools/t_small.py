# -*- coding: utf-8 -*-
"""小屏适配自测:把屏幕高度假装成 800,看是否自动切滚动布局且不错位"""
import os
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from PIL import ImageGrab                                        # noqa: E402

from dspet import config                                         # noqa: E402
from dspet.settings_ui import SettingsWindow                     # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
FAKE_H = int(os.environ.get("FAKE_H", "800"))

_orig = tk.Misc.winfo_screenheight
tk.Misc.winfo_screenheight = lambda self: FAKE_H

cfg = config.load()
w = SettingsWindow(cfg)
print("compact:", w.compact, "| 高:", w.h, "| 假屏高:", FAKE_H)
w.root.attributes("-alpha", 1.0)
w._x = 40                                   # 挪到左边,别和已在屏上的设置窗重叠
w.root.geometry("+%d+%d" % (w._x, w._y))
w.root.update()
t = time.time()
while time.time() - t < 1.0:
    w.root.update()
    time.sleep(0.02)

# 滚到底看看 footer 在不在
if w.compact:
    try:
        w._scroll._parent_canvas.yview_moveto(1.0)
        t = time.time()
        while time.time() - t < 0.5:
            w.root.update()
            time.sleep(0.02)
    except Exception as e:
        print("scroll err", e)

import win32gui
hwnd = w.root.winfo_id()
top = win32gui.GetParent(hwnd) or hwnd
r = win32gui.GetWindowRect(top)
print("rect", r)
ImageGrab.grab(bbox=(r[0]-4, r[1]-4, r[2]+4, r[3]+4)).save(
    os.path.join(WS, "_ui_small.png"))
print("saved")
w.root.destroy()
