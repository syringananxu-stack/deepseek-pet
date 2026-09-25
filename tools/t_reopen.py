# -*- coding: utf-8 -*-
"""诊断:设置窗关掉后还能不能再打开(标志位有没有卡死)"""
import ctypes
import subprocess
import time

import win32con
import win32gui

u = ctypes.windll.user32


def wins():
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and t.startswith("设置"):
            out.append(h)

    win32gui.EnumWindows(cb, None)
    return out


def open_req(n=1):
    pet = win32gui.FindWindow("DSPetWnd", None)
    for _ in range(n):
        u.PostMessageW(ctypes.c_void_p(pet), win32con.WM_APP + 2, ctypes.c_void_p(0),
                       ctypes.c_void_p(0))
        time.sleep(0.8)
    t = time.time()
    while time.time() - t < 6:
        w = wins()
        if w:
            return w
        time.sleep(0.3)
    return []


print("重启桌宠…")
subprocess.run(["taskkill", "/F", "/IM", "DeepSeekPet.exe"], capture_output=True)
time.sleep(1.5)
subprocess.Popen([r"D:\Apps\DeepSeekPet\DeepSeekPet.exe"], cwd=r"D:\Apps\DeepSeekPet")
time.sleep(9)

print("A 首次打开:", wins() or open_req())
print("B 关掉(WM_CLOSE)…")
for h in wins():
    win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
time.sleep(3.5)
print("C 再打开:", open_req())
print("D 再关一次…")
for h in wins():
    win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
time.sleep(3.5)
print("E 第三次打开:", open_req())
print("当前窗口:", wins())
