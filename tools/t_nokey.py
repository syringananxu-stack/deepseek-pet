# -*- coding: utf-8 -*-
"""没填 API Key 时:①首启不再弹设置窗 ②点桌宠也不弹设置窗(只气泡提示)
用源码版跑(配置写在项目目录),跑完还原配置"""
import ctypes
import io
import json
import os
import shutil
import subprocess
import sys
import time

import win32con
import win32gui

PROJ = r"D:\Projects\deepseek-pet"
CFG = os.path.join(PROJ, "config.json")
BAK = r"D:\Temp\dspet_src_cfg_bak.json"
u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass


def wins(prefix):
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and t.startswith(prefix):
            out.append(t)

    win32gui.EnumWindows(cb, None)
    return out


def procs():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DeepSeekPet.exe", "/FO", "CSV"],
                       capture_output=True, text=True)
    n1 = [l for l in r.stdout.splitlines()[1:] if l.strip()]
    r2 = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                        capture_output=True, text=True)
    return n1


def click(x, y):
    u.SetCursorPos(int(x), int(y))
    time.sleep(0.25)
    u.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.1)
    u.mouse_event(0x0004, 0, 0, 0, 0)


subprocess.run(["taskkill", "/F", "/IM", "DeepSeekPet.exe"], capture_output=True)
time.sleep(1.2)
if os.path.exists(CFG):
    shutil.copy2(CFG, BAK)
json.dump({"first_run_done": False, "api_key": "", "pos": [1200, 400]},
          io.open(CFG, "w", encoding="utf-8"), ensure_ascii=False)

env = dict(os.environ)
env["PYTHONPATH"] = os.path.join(PROJ, "src")
p = subprocess.Popen([r"C:\Python314\python.exe", "-W", "ignore", "main.py"],
                     cwd=PROJ, env=env)
try:
    hwnd = 0
    for _ in range(30):
        time.sleep(0.5)
        hwnd = win32gui.FindWindow("DSPetWnd", None)
        if hwnd:
            break
    print("pet hwnd:", hwnd)
    time.sleep(2.0)
    print("首启后设置窗数量:", len(wins("设置 — ")), "(应为 0)")
    r = win32gui.GetWindowRect(hwnd)
    for i in range(4):
        click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)
        time.sleep(0.7)
    time.sleep(1.5)
    n = len(wins("设置 — "))
    print("连点 4 次后设置窗数量:", n, "(应为 0)")
    print("RESULT:", "PASS" if n == 0 else "FAIL")
finally:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    time.sleep(1.0)
    if os.path.exists(BAK):
        shutil.copy2(BAK, CFG)
        print("配置已还原")
