# -*- coding: utf-8 -*-
"""复现:退出桌宠后是否还有残留进程 / exe 是否还被占用"""
import os
import subprocess
import time

import win32con
import win32gui

EXE = r"D:\Apps\DeepSeekPet\DeepSeekPet.exe"


def procs():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DeepSeekPet.exe", "/FO", "CSV"],
                       capture_output=True, text=True)
    return [l.split(",")[1].strip('"') for l in r.stdout.splitlines()[1:] if l.strip()]


subprocess.run(["taskkill", "/F", "/IM", "DeepSeekPet.exe"], capture_output=True)
time.sleep(1.5)
print("start-before:", procs() or "none")
subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
time.sleep(9)
print("start-after :", procs())
hwnd = win32gui.FindWindow("DSPetWnd", None)
print("pet window  :", hwnd)

print("-> send WM_CLOSE")
win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
for i in range(1, 11):
    time.sleep(1.0)
    p = procs()
    print("   %2ds later: %s" % (i, p or "ALL GONE"))
    if not p:
        break

print("-> can we rename the exe? (file lock check)")
try:
    os.rename(EXE, EXE + ".probe")
    os.rename(EXE + ".probe", EXE)
    print("rename OK (not locked)")
except Exception as e:
    print("rename FAILED (locked):", e)
