# -*- coding: utf-8 -*-
"""点一下桌宠 → 抓余额气泡,看峰谷那段有没有 render 问题"""
import ctypes
import os
import time

import win32gui
from PIL import ImageGrab

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
u = ctypes.windll.user32

hwnd = win32gui.FindWindow("DSPetWnd", None)
r = win32gui.GetWindowRect(hwnd)
cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
print("pet hwnd", hwnd, "rect", r)

u.SetCursorPos(cx, cy)
time.sleep(0.2)
u.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.08)
u.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.7)

r2 = win32gui.GetWindowRect(hwnd)
print("after click rect", r2)
pad = 40
box = (max(0, r2[0] - pad), max(0, r2[1] - 120), min(2560, r2[2] + pad), min(1440, r2[3] + pad))
ImageGrab.grab(bbox=box).save(os.path.join(WS, "_bubble.png"))
print("saved", box)
