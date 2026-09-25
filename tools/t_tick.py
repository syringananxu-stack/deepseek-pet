# -*- coding: utf-8 -*-
"""点一下桌宠 → 气泡里的倒计时是不是每秒都在走?
做法:点完立刻开始,每秒抓一次桌宠窗口那块屏幕,比较相邻帧是否变化。
(点击后桌宠会进入"老实"状态不移动,所以画面变化基本只来自气泡文字)
用法: python t_tick.py
"""
import ctypes
import os
import subprocess
import sys
import time

import win32gui
from PIL import ImageGrab

EXE = r"D:\Apps\DeepSeekPet\DeepSeekPet.exe"
OUT = r"D:\Temp\dspet_tick"
u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass


def click(x, y):
    u.SetCursorPos(int(x), int(y))
    time.sleep(0.2)
    u.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.08)
    u.mouse_event(0x0004, 0, 0, 0, 0)


os.makedirs(OUT, exist_ok=True)
subprocess.run(["taskkill", "/F", "/IM", "DeepSeekPet.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
hwnd = 0
for _ in range(30):
    time.sleep(0.5)
    hwnd = win32gui.FindWindow("DSPetWnd", None)
    if hwnd:
        break
print("hwnd:", hwnd)
time.sleep(4)

r = win32gui.GetWindowRect(hwnd)
print("rect:", r)
click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)

frames = []
for i in range(12):
    t0 = time.time()
    rr = win32gui.GetWindowRect(hwnd)
    img = ImageGrab.grab(bbox=(rr[0], rr[1], rr[2], rr[3])).convert("L")
    frames.append(img)
    if i:
        pass
    time.sleep(max(0.0, 1.0 - (time.time() - t0)))

same = []
for i in range(1, len(frames)):
    import PIL.ImageChops as C
    d = C.difference(frames[i - 1], frames[i])
    bbox = d.getbbox()
    n = sum(1 for p in d.getdata() if p > 24)
    same.append((i, n, bool(bbox)))
    print("sec %2d -> diff px=%5d changed=%s" % (i, n, bool(bbox)))
for i, n, ch in same:
    frames[i - 1].save(os.path.join(OUT, "f%02d.png" % (i - 1)))
live = sum(1 for _, n, _ in same if n > 5)
print("前 10 秒里变化的次数:", live, "/", len(same))
print("RESULT:", "PASS" if live >= 8 else ("PARTIAL(%d)" % live))
