# -*- coding: utf-8 -*-
"""右键菜单实测:给桌宠发 WM_RBUTTONUP,截图看菜单项,再 ESC 关掉"""
import ctypes
import os
import time

import win32con
import win32gui
from PIL import ImageGrab

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
u = ctypes.windll.user32

hwnd = win32gui.FindWindow("DSPetWnd", None)
r = win32gui.GetWindowRect(hwnd)
cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
u.SetCursorPos(cx, cy)
time.sleep(0.2)
win32gui.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, 0)
time.sleep(1.2)

# 菜单是弹出窗,类名 #32768
menu = win32gui.FindWindow("#32768", None)
print("menu hwnd:", menu, "visible:", win32gui.IsWindowVisible(menu) if menu else None)
if menu:
    mr = win32gui.GetWindowRect(menu)
    print("menu rect:", mr)
    pad = 12
    ImageGrab.grab(bbox=(mr[0] - pad, mr[1] - pad, mr[2] + pad, mr[3] + pad)).save(
        os.path.join(WS, "_menu.png"))
    print("saved _menu.png")
# ESC 关掉菜单
u.keybd_event(0x1B, 0, 0, 0)
u.keybd_event(0x1B, 0, 2, 0)
time.sleep(0.5)
print("after esc, menu exists:", bool(win32gui.FindWindow("#32768", None)))
