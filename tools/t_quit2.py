# -*- coding: utf-8 -*-
"""退出/启动健壮性测试(真实鼠标操作):
1) menu    右键 → 点「退出桌宠」→ 进程是否全清、exe 是否解锁
2) withwin 设置窗开着时退出 → 是否照样退得掉
3) zombie  只有互斥体没有窗口时能否照样启动
用法: python t_quit2.py <menu|withwin|zombie>
"""
import ctypes
import os
import subprocess
import sys
import time

import win32con
import win32gui

EXE = r"D:\Apps\DeepSeekPet\DeepSeekPet.exe"
u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass


def procs():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DeepSeekPet.exe", "/FO", "CSV"],
                       capture_output=True, text=True)
    return [l.split(",")[1].strip('"') for l in r.stdout.splitlines()[1:] if l.strip()]


def wins(prefix):
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and t.startswith(prefix):
            out.append(h)

    win32gui.EnumWindows(cb, None)
    return out


def popup():
    out = []

    def cb(h, _):
        if win32gui.GetClassName(h) == "#32768" and win32gui.IsWindowVisible(h):
            out.append((h, win32gui.GetWindowRect(h)))

    win32gui.EnumWindows(cb, None)
    return out


def click(x, y, right=False):
    u.SetCursorPos(int(x), int(y))
    time.sleep(0.25)
    dn, up = (0x0008, 0x0010) if right else (0x0002, 0x0004)
    u.mouse_event(dn, 0, 0, 0, 0)
    time.sleep(0.1)
    u.mouse_event(up, 0, 0, 0, 0)


def start():
    subprocess.run(["taskkill", "/F", "/IM", "DeepSeekPet.exe"], capture_output=True)
    time.sleep(1.5)
    subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    time.sleep(9)


def wait_gone(secs=12):
    for i in range(secs):
        time.sleep(1.0)
        if not procs():
            return i + 1
    return None


mode = sys.argv[1] if len(sys.argv) > 1 else "menu"

if mode == "zombie":
    print("-> zombie mutex holder (no window)")
    code = ("import ctypes,time;"
            "ctypes.windll.kernel32.CreateMutexW(None, False, "
            "'Global\\\\DeepSeekPetFishSingleton');"
            "time.sleep(30)")
    subprocess.Popen([r"C:\Python314\python.exe", "-c", code])
    time.sleep(3)
    subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    time.sleep(10)
    ok = win32gui.FindWindow("DSPetWnd", None)
    print("   procs:", procs(), "pet window:", ok)
    print("   RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0)

start()
print("after start:", procs(), "window:", win32gui.FindWindow("DSPetWnd", None))

if mode == "withwin":
    pet = win32gui.FindWindow("DSPetWnd", None)
    u.PostMessageW(ctypes.c_void_p(pet), win32con.WM_APP + 2, ctypes.c_void_p(0),
                   ctypes.c_void_p(0))
    for _ in range(20):
        if wins("设置 — "):
            break
        time.sleep(0.5)
    print("   settings window open:", len(wins("设置 — ")))

pet = win32gui.FindWindow("DSPetWnd", None)
r = win32gui.GetWindowRect(pet)
click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2, right=True)      # 真实右键
time.sleep(1.2)
pp = popup()
print("   popup:", pp)
if not pp:
    print("   RESULT: FAIL (no popup)")
    sys.exit(1)
_, pr = pp[0]
click((pr[0] + pr[2]) // 2, pr[3] - 13)                          # 点最后一项=退出桌宠
t = wait_gone(12)
print("   procs gone after:", ("%ds" % t) if t else "NOT gone in 12s")
try:
    os.rename(EXE, EXE + ".probe")
    os.rename(EXE + ".probe", EXE)
    lock = "unlocked"
except Exception as e:
    lock = "LOCKED %s" % e
print("   exe:", lock)
print("   RESULT:", "PASS" if (t and lock == "unlocked") else "FAIL")
