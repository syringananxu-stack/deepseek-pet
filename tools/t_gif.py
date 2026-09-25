# -*- coding: utf-8 -*-
"""录一小段 GIF 演示:点击一下 / 连点一下 / 被拎起来。输出到 workspace。"""
import ctypes
import os
import sys
import threading
import time

import win32con
import win32gui
from PIL import Image, ImageGrab

OUT = os.path.join(os.environ.get(
    "WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"), "_pet_demo.gif")
u = ctypes.windll.user32
h = win32gui.FindWindow("DSPetWnd", None)
if not h:
    print("桌宠没在跑")
    sys.exit(1)

frames = []
stop = False


def grabber():
    while not stop:
        r = win32gui.GetWindowRect(h)
        x0, y0, x1, y1 = r[0] - 30, r[1] - 10, r[2] + 30, r[3] + 30
        y0 = max(0, y0)
        try:
            frames.append(ImageGrab.grab(bbox=(x0, y0, x1, y1)))
        except Exception:
            pass
        time.sleep(0.07)


def click():
    r = win32gui.GetWindowRect(h)
    u.SetCursorPos((r[0] + r[2]) // 2, r[1] + r[3] - 40)
    u.PostMessageW(h, win32con.WM_LBUTTONDOWN, 1, 0)
    time.sleep(0.08)
    u.PostMessageW(h, win32con.WM_LBUTTONUP, 0, 0)


th = threading.Thread(target=grabber, daemon=True)
th.start()
time.sleep(0.7)
print("click #1")
click()
time.sleep(0.75)
print("click #2(立刻再点)")
click()
time.sleep(0.9)
print("grab & stretch")
r = win32gui.GetWindowRect(h)
cx, cy = (r[0] + r[2]) // 2, r[1] + r[3] - 40
u.SetCursorPos(cx, cy)
u.PostMessageW(h, win32con.WM_LBUTTONDOWN, 1, 0)
time.sleep(0.12)
for i in range(8):
    u.SetCursorPos(cx, cy - i * 12)
    u.PostMessageW(h, win32con.WM_MOUSEMOVE, 1, 0)
    time.sleep(0.06)
time.sleep(0.5)
print("release")
u.PostMessageW(h, win32con.WM_LBUTTONUP, 0, 0)
time.sleep(0.9)
stop = True
time.sleep(0.2)

print("frames:", len(frames))
w0 = max(f.width for f in frames)
norm = []
for f in frames:
    im = Image.new("RGBA", (w0, f.height), (0, 0, 0, 0))
    im.paste(f, ((w0 - f.width) // 2, 0))
    norm.append(im.convert("P", palette=Image.ADAPTIVE, colors=128))
dur = int(1000 * 0.07)
norm[0].save(OUT, save_all=True, append_images=norm[1:], duration=dur, loop=0, optimize=True)
print("saved", OUT, os.path.getsize(OUT) // 1024, "KB")
