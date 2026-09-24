# -*- coding: utf-8 -*-
"""只打开设置窗口并截图(自查用)"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

from dspet import config          # noqa: E402
from dspet.settings_ui import SettingsWindow   # noqa: E402
from PIL import ImageGrab         # noqa: E402

cfg = config.load()
w = SettingsWindow(cfg)
w.root.update()
w.root.update_idletasks()
time.sleep(0.6)
w.root.update()
try:
    x, y = w.root.winfo_rootx(), w.root.winfo_rooty()
    ww, hh = w.root.winfo_width(), w.root.winfo_height()
    print("window geometry:", x, y, ww, hh)
    im = ImageGrab.grab(bbox=(x - 6, y - 34, x + ww + 6, y + hh + 6))
    out = os.path.join(os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"), "_ui.png")
    im.save(out)
    print("saved", out, im.size)
finally:
    w.root.destroy()
