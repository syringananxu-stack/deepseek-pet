# -*- coding: utf-8 -*-
"""右键行为自测:①她先停住(位置不动)②临时不置顶(不挡别的窗口)③菜单点「打开设置界面」后置顶恢复
用法: python t_menu2.py
"""
import ctypes
import os
import subprocess
import sys
import time

import win32con
import win32gui
from PIL import ImageGrab

EXE = r"D:\Apps\DeepSeekPet\DeepSeekPet.exe"
SHOT = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace\_menu_fix.png"
u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass


def topmost(h):
    return bool(win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOPMOST)


def popup():
    out = []

    def cb(h, _):
        if win32gui.GetClassName(h) == "#32768" and win32gui.IsWindowVisible(h):
            out.append((h, win32gui.GetWindowRect(h)))

    win32gui.EnumWindows(cb, None)
    return out


def wins(prefix):
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and t.startswith(prefix):
            out.append(h)

    win32gui.EnumWindows(cb, None)
    return out


def click(x, y, right=False):
    u.SetCursorPos(int(x), int(y))
    time.sleep(0.25)
    dn, up = (0x0008, 0x0010) if right else (0x0002, 0x0004)
    u.mouse_event(dn, 0, 0, 0, 0)
    time.sleep(0.1)
    u.mouse_event(up, 0, 0, 0, 0)


subprocess.run(["taskkill", "/F", "/IM", "DeepSeekPet.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
hwnd = 0
for _ in range(30):
    time.sleep(0.5)
    hwnd = win32gui.FindWindow("DSPetWnd", None)
    if hwnd:
        break
time.sleep(4)
r0 = win32gui.GetWindowRect(hwnd)
print("pet hwnd:", hwnd, "topmost:", topmost(hwnd), "rect:", r0)

click((r0[0] + r0[2]) // 2, (r0[1] + r0[3]) // 2, right=True)
time.sleep(1.0)
pp = popup()
print("popup:", pp)
m_top = topmost(hwnd)
print("菜单开着时 topmost:", m_top, "(应为 False)")
m0 = win32gui.GetWindowRect(hwnd)
time.sleep(1.6)
m1 = win32gui.GetWindowRect(hwnd)
print("1.6 秒内位置:", m0, "->", m1, "停住:", m0 == m1)
try:
    x1, y1 = pp[0][1][0], pp[0][1][1]
    x2, y2 = pp[0][1][2], pp[0][1][3]
    big = (max(0, x1 - 30), max(0, y1 - 30), min(2560, x2 + 30), min(1440, y2 + 30))
    ImageGrab.grab(bbox=big).save(SHOT)
    print("截图:", SHOT)
except Exception as e:
    print("截图失败:", e)

if pp:
    pr = pp[0][1]
    click((pr[0] + pr[2]) // 2, pr[1] + 12)          # 第一项 = 打开设置界面…
    time.sleep(1.5)
print("菜单关掉后 topmost:", topmost(hwnd), "(应为 True)")
print("设置窗:", len(wins("设置 — ")))
for w in wins("设置 — "):
    win32gui.PostMessage(w, win32con.WM_CLOSE, 0, 0)
ok = (not m_top) and (m0 == m1) and topmost(hwnd)
print("RESULT:", "PASS" if ok else "FAIL")
