# -*- coding: utf-8 -*-
"""看一眼桌宠现在到底什么状态"""
import os
import subprocess

import win32gui

r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DeepSeekPet.exe", "/FO", "CSV"],
                   capture_output=True, text=True)
print("procs:", [l.split(",")[1].strip('"') for l in r.stdout.splitlines()[1:] if l.strip()])
print("pet win:", win32gui.FindWindow("DSPetWnd", None))
print("popup #32768:", win32gui.FindWindow("#32768", None))
ls = []


def cb(h, _):
    t = win32gui.GetWindowText(h)
    if win32gui.IsWindowVisible(h) and t:
        ls.append(t)


win32gui.EnumWindows(cb, None)
print("titles:", ls[:12])
for p in (r"D:\Apps\DeepSeekPet\dspet.log", r"D:\Apps\DeepSeekPet\_dbg.log"):
    print("---", p, os.path.exists(p))
    if os.path.exists(p):
        print(open(p, encoding="utf-8", errors="replace").read()[-900:])
