# -*- coding: utf-8 -*-
"""录一段设置窗口的动画 GIF:打开淡入 → 拨开关 → 切分段 → 关闭淡出"""
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

import customtkinter as ctk                                     # noqa: E402
from PIL import Image, ImageGrab                                # noqa: E402

from dspet import config                                        # noqa: E402
from dspet.settings_ui import SettingsWindow, _animate          # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
OUT = os.path.join(WS, "_ui_demo.gif")
SCALE = 0.5
INTERVAL = 0.06

cfg = config.load()
w = SettingsWindow(cfg)
w.root.attributes("-alpha", 0.0)
w.root.geometry("+%d+%d" % (w._x, w._y))
w.root.update()

frames = []
stop = False
bbox = (w._x - 12, w._y - 12, w._x + w._size[0] + 12, w._y + w._size[1] + 12)


def grabber():
    while not stop:
        try:
            fr = ImageGrab.grab(bbox=bbox)
            frames.append(fr.resize((int(fr.width * SCALE), int(fr.height * SCALE)),
                                    Image.LANCZOS))
        except Exception:
            pass
        time.sleep(INTERVAL)


th = threading.Thread(target=grabber, daemon=True)
th.start()
time.sleep(0.35)

# 1) 打开动画
done = []
_animate(w.root, w._x, w._y, 1.0, slide_from=26, on_done=lambda: done.append(1))
t0 = time.time()
while not done and time.time() - t0 < 3:
    w.root.update()
    time.sleep(0.01)
time.sleep(0.45)

# 2) 拨两个开关(带滑块动画)
find = []


def walk(widget, out):
    for c in widget.winfo_children():
        if hasattr(c, "var") and c.winfo_width() == 46:
            out.append(c)
        walk(c, out)


walk(w.root, find)
for t in find[:2]:
    t.var.set(not bool(t.var.get()))
    t0 = time.time()
    while time.time() - t0 < 0.5:
        w.root.update()
        time.sleep(0.01)
time.sleep(0.2)

# 3) 切分段控件
w.seg.select("彻底删除")
t0 = time.time()
while time.time() - t0 < 0.5:
    w.root.update()
    time.sleep(0.01)

# 4) 关闭动画
closed = []
w._close_anim()
t0 = time.time()
while time.time() - t0 < 2.2:
    try:
        w.root.update()
    except Exception:
        break
    time.sleep(0.01)
stop = True
time.sleep(0.2)

print("frames:", len(frames))
pal = [f.convert("P", palette=Image.ADAPTIVE, colors=96) for f in frames]
pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=int(INTERVAL * 1000),
            loop=0, optimize=True)
print("saved", OUT, os.path.getsize(OUT) // 1024, "KB")
