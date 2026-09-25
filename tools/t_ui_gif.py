# -*- coding: utf-8 -*-
"""录一段设置窗口的动画 GIF:打开淡入 → 拨开关 → 切分段 → 关闭淡出

按真实时间戳存帧,所以 GIF 播放速度跟实际操作一致(不会忽快忽慢)。
"""
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from PIL import Image, ImageGrab                                # noqa: E402

from dspet import config                                        # noqa: E402
from dspet.settings_ui import SettingsWindow, _animate          # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
OUT = os.path.join(WS, "_ui_demo.gif")
SCALE = 0.5
INTERVAL = 0.05

cfg = config.load()
w = SettingsWindow(cfg)
w.root.attributes("-alpha", 0.0)
w.root.geometry("+%d+%d" % (w._x, w._y))
w.root.update()

shots = []
stop = False
bbox = (w._x - 14, w._y - 14, w._x + w._size[0] + 14, w._y + w._size[1] + 40)


def grabber():
    while not stop:
        try:
            fr = ImageGrab.grab(bbox=bbox)
            shots.append((time.time(), fr.resize((int(fr.width * SCALE),
                                                  int(fr.height * SCALE)),
                                                 Image.LANCZOS)))
        except Exception:
            pass
        time.sleep(INTERVAL)


th = threading.Thread(target=grabber, daemon=True)
th.start()
t0 = time.time()
time.sleep(0.4)

# 1) 打开动画
done = []
_animate(w.root, w._x, w._y, 1.0, slide_from=26, on_done=lambda: done.append(1))
while not done and time.time() - t0 < 3:
    w.root.update()
    time.sleep(0.01)
time.sleep(0.5)


def pump(sec):
    t = time.time()
    while time.time() - t < sec:
        w.root.update()
        time.sleep(0.01)


# 2) 拨两个开关(带滑块动画)
find = []


def walk(widget, out):
    for c in widget.winfo_children():
        if hasattr(c, "var") and c.winfo_width() >= 45:
            out.append(c)
        walk(c, out)


walk(w.root, find)
for t in find[:2]:
    t.var.set(not bool(t.var.get()))
    pump(0.55)
pump(0.25)

# 3) 切分段控件
w.seg.select("彻底删除")
pump(0.55)

# 4) 再拨回一个开关
if find:
    find[0].var.set(not bool(find[0].var.get()))
    pump(0.55)

# 5) 关闭动画
w._close_anim()
t = time.time()
while time.time() - t < 1.6:
    try:
        w.root.update()
    except Exception:
        break
    time.sleep(0.01)
stop = True
time.sleep(0.25)

print("frames:", len(shots))
imgs = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for _, f in shots]
durs = []
for i in range(len(shots) - 1):
    d = (shots[i + 1][0] - shots[i][0]) * 1000
    durs.append(int(max(40, min(220, d))))
durs.append(80)
imgs[0].save(OUT, save_all=True, append_images=imgs[1:], duration=durs, loop=0,
             optimize=False, disposal=2)
print("saved", OUT, os.path.getsize(OUT) // 1024, "KB", "总时长 %.1fs" % (sum(durs) / 1000.0))
