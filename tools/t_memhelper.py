# -*- coding: utf-8 -*-
"""--mem-purge 自模式自测:提权后的那个自己应该 不建窗口/不抢互斥体/干完就走 + 写结果 json"""
import json
import os
import subprocess
import sys
import tempfile
import time

import win32gui

EXE = r"D:\Apps\DeepSeekPet\DeepSeekPet.exe"
J = os.path.join(tempfile.gettempdir(), "dspet_mempurge.json")

subprocess.run(["taskkill", "/F", "/IM", "DeepSeekPet.exe"], capture_output=True)
time.sleep(1.2)
if os.path.exists(J):
    os.remove(J)

t0 = time.time()
p = subprocess.Popen([EXE, "--mem-purge"], cwd=os.path.dirname(EXE))
ok_exit = False
while time.time() - t0 < 30:
    if p.poll() is not None:
        ok_exit = True
        break
    time.sleep(0.3)
print("helper 退出:", ok_exit, "耗时 %.1fs" % (time.time() - t0), "code:", p.poll())
print("宠物窗口(应为 0):", win32gui.FindWindow("DSPetWnd", None))
time.sleep(0.5)
data = None
if os.path.exists(J):
    try:
        data = json.load(open(J, encoding="utf-8"))
    except Exception as e:
        data = {"read_error": str(e)}
print("结果 json:", data)
procs = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DeepSeekPet.exe", "/FO", "CSV"],
                       capture_output=True, text=True).stdout
n = len([l for l in procs.splitlines()[1:] if l.strip()])
print("残留进程(应为 0):", n)
ok = ok_exit and (win32gui.FindWindow("DSPetWnd", None) == 0) and n == 0 and data
print("RESULT:", "PASS" if ok else "FAIL")
