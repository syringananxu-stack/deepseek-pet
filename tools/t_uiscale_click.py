# -*- coding: utf-8 -*-
"""装机版:真点一下「界面大小」的「大」,看窗口是否当场变大(即改即生效)"""
import ctypes
import os
import sys
import time

import win32con
import win32gui
from PIL import ImageGrab

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
u = ctypes.windll.user32


def find_settings():
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and t.startswith("设置"):
            out.append((h, t, win32gui.GetWindowRect(h)))

    win32gui.EnumWindows(cb, None)
    return out


def click(x, y):
    u.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    u.mouse_event(0x0002, 0, 0, 0, 0)     # LEFTDOWN
    time.sleep(0.06)
    u.mouse_event(0x0004, 0, 0, 0, 0)     # LEFTUP


# 确保设置窗开着
pet = win32gui.FindWindow("DSPetWnd", None)
u.PostMessageW(ctypes.c_void_p(pet), win32con.WM_APP + 2, ctypes.c_void_p(0), ctypes.c_void_p(0))
t = time.time()
while time.time() - t < 8 and not find_settings():
    time.sleep(0.3)
s = find_settings()
print("settings:", [(t2, r[2] - r[0], r[3] - r[1]) for (_, t2, r) in s])
if not s:
    sys.exit(1)
h, title, r = s[0]
w0 = r[2] - r[0]
ImageGrab.grab(bbox=(r[0] - 4, r[1] - 4, r[2] + 4, r[3] + 4)).save(os.path.join(WS, "_ui_clk_before.png"))

# 「界面大小」那行右端 = 小/中/大,取 大 的位置(参考截图 604 宽:大 在 x≈519,行 y≈804)
base = (r[0] - 4, r[1] - 4)
ok = False
for (dx, dy) in ((525, 843), (515, 843), (535, 843), (525, 850)):
    click(base[0] + dx, base[1] + dy)
    time.sleep(1.4)
    s2 = find_settings()
    if not s2:
        print("窗口不见了?!", (dx, dy))
        break
    r2 = s2[0][2]
    w1 = r2[2] - r2[0]
    print("click(%d,%d) → 宽 %d (原 %d)" % (dx, dy, w1, w0))
    if w1 != w0:
        ImageGrab.grab(bbox=(r2[0] - 4, r2[1] - 4, r2[2] + 4, r2[3] + 4)).save(
            os.path.join(WS, "_ui_clk_after.png"))
        ok = True
        break
print("RESULT:", "PASS" if ok else "FAIL")
# 点回「中」,把窗口留给东家
if ok:
    time.sleep(0.6)
    s3 = find_settings()
    if s3:
        r3 = s3[0][2]
        click(r3[0] - 4 + 477, r3[1] - 4 + 843)
        time.sleep(1.4)
        s4 = find_settings()
        if s4:
            print("点回中 →", s4[0][2][2] - s4[0][2][0], "宽")
            ImageGrab.grab(bbox=(s4[0][2][0] - 4, s4[0][2][1] - 4,
                                 s4[0][2][2] + 4, s4[0][2][3] + 4)).save(
                                     os.path.join(WS, "_ui_clk_mid.png"))
print("留下来的窗口:", [(r[2] - r[0], r[3] - r[1]) for (_, _, r) in find_settings()])
