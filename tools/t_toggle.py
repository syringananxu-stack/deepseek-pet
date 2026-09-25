# -*- coding: utf-8 -*-
"""自查:开关滑块动画 + 窗口打开动画(连拍成图)"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from PIL import Image, ImageGrab                            # noqa: E402

from dspet import config                                    # noqa: E402
from dspet.settings_ui import SettingsWindow                # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
cfg = config.load()
w = SettingsWindow(cfg)
w.root.attributes("-alpha", 1.0)
w.root.geometry("+%d+%d" % (w._x, w._y))
w.root.update()
time.sleep(0.3)
w.root.update()

# 找到第一个开关的屏幕坐标,连拍它
tg = None
for child in w.root.winfo_children():
    pass
tg = None
for attr in ("var_wander", "var_calm", "var_top"):
    pass
# 直接抓窗口里 y≈350 行的那两个滑块
x, y = w.root.winfo_x(), w.root.winfo_y()
btns = []


def find_canvas(widget, out):
    for c in widget.winfo_children():
        if c.winfo_class() == "Canvas":
            out.append(c)
        find_canvas(c, out)


find_canvas(w.root, btns)
togs = [c for c in btns if hasattr(c, "var") and c.winfo_width() >= 45]
print("toggles found:", len(btns), "->", len(togs))
tog = togs[0]
frames = []
tog.var.set(not bool(tog.var.get()))          # 触发动画
t0 = time.time()
while time.time() - t0 < 0.45:
    w.root.update()
    cx = tog.winfo_rootx()
    cy = tog.winfo_rooty()
    frames.append(ImageGrab.grab(bbox=(cx - 6, cy - 6, cx + tog.winfo_width() + 6,
                                       cy + tog.winfo_height() + 6)))
    time.sleep(0.025)
print("frames:", len(frames))
pick = frames[::max(1, len(frames) // 5)][:6]
fw = max(f.width for f in pick)
fh = max(f.height for f in pick)
sheet = Image.new("RGB", (fw * 6, fh), (255, 255, 255))
for i, f in enumerate(pick):
    sheet.paste(f, (i * fw, 0))
sheet = sheet.resize((sheet.width * 3, sheet.height * 3), Image.LANCZOS)
sheet.save(os.path.join(WS, "_toggle_anim.png"))
print("saved")
w.root.destroy()
