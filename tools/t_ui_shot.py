# -*- coding: utf-8 -*-
"""只打开设置窗口并截图(自查用):-a 抓动画过程中的几帧"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from PIL import ImageGrab                                  # noqa: E402

from dspet import config                                   # noqa: E402
from dspet.settings_ui import SettingsWindow               # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
cfg = config.load()
w = SettingsWindow(cfg)
w.root.attributes("-alpha", 1.0)          # 自查:跳过动画,直接看得见
w.root.geometry("+%d+%d" % (w._x, w._y))
w.root.update()
frames = []
if "-a" in sys.argv:
    w.root.attributes("-alpha", 0.0)
    from dspet.settings_ui import _animate
    _animate(w.root, w._x, w._y, 1.0, slide_from=26)
    t0 = time.time()
    while time.time() - t0 < 0.5:
        w.root.update()
        x, y = w.root.winfo_x(), w.root.winfo_y()
        ww, hh = w.root.winfo_width(), w.root.winfo_height()
        frames.append((time.time() - t0, ImageGrab.grab(bbox=(x - 10, y - 10, x + ww + 10, y + hh + 10))))
        time.sleep(0.03)
w.root.update()
time.sleep(0.30)
w.root.update()
x, y = w.root.winfo_x(), w.root.winfo_y()
ww, hh = w.root.winfo_width(), w.root.winfo_height()
print("geometry:", x, y, ww, hh, "compact:", w.compact)
ImageGrab.grab(bbox=(x - 10, y - 10, x + ww + 10, y + hh + 10)).save(os.path.join(WS, "_ui.png"))
if frames:
    pick = frames[::max(1, len(frames) // 6)][:6]
    tw = max(f.width for _, f in pick)
    th = max(f.height for _, f in pick)
    sheet = ImageGrab.grab(bbox=(0, 0, 1, 1)).resize((tw * 3, th * 2))
    for i, (t, f) in enumerate(pick):
        sheet.paste(f, ((i % 3) * tw, (i // 3) * th))
    sheet.save(os.path.join(WS, "_ui_anim.png"))
    print("anim frames:", len(frames))
print("saved")
w.root.destroy()
