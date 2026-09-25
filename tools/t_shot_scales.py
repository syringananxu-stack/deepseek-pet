# -*- coding: utf-8 -*-
"""把三档界面大小各开一次,截图 + 量尺寸(靠重启桌宠让配置生效)"""
import ctypes
import io
import json
import os
import subprocess
import time

import win32con
import win32gui
from PIL import ImageGrab

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
CFG = r"D:\Apps\DeepSeekPet\config.json"
EXE = r"D:\Apps\DeepSeekPet\DeepSeekPet.exe"
u = ctypes.windll.user32


def wins():
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and t.startswith("设置"):
            out.append((h, t, win32gui.GetWindowRect(h)))

    win32gui.EnumWindows(cb, None)
    return out


def kill():
    subprocess.run(["taskkill", "/F", "/IM", "DeepSeekPet.exe"], capture_output=True)
    time.sleep(1.2)


def start():
    subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    time.sleep(7)


def open_win():
    pet = win32gui.FindWindow("DSPetWnd", None)
    for _ in range(3):
        u.PostMessageW(ctypes.c_void_p(pet), win32con.WM_APP + 2, ctypes.c_void_p(0),
                       ctypes.c_void_p(0))
        t = time.time()
        while time.time() - t < 6:
            w = wins()
            if w:
                time.sleep(1.2)
                return wins()
            time.sleep(0.3)
    return []


raw = io.open(CFG, encoding="utf-8").read()
orig = json.loads(raw or "{}")
io.open("D:/Temp/dspet_cfg_backup2.json", "w", encoding="utf-8").write(raw)

try:
    for lv, name in ((0, "small"), (1, "mid"), (2, "big")):
        d = dict(orig)
        d["ui_scale"] = lv
        io.open(CFG, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
        kill()
        start()
        w = open_win()
        if not w:
            print(name, "没打开 ✗")
            continue
        h, t, r = w[0]
        print(name, "rect", (r[2] - r[0], r[3] - r[1]), "client", win32gui.GetClientRect(h))
        ImageGrab.grab(bbox=(r[0] - 3, r[1] - 3, r[2] + 3, r[3] + 3)).save(
            os.path.join(WS, "_sc_%s.png" % name))
        for (h2, _, _) in wins():
            win32gui.PostMessage(h2, win32con.WM_CLOSE, 0, 0)
        time.sleep(1.5)
finally:
    io.open(CFG, "w", encoding="utf-8").write(json.dumps(orig, ensure_ascii=False, indent=2))
    kill()
    start()
    w = open_win()
    print("还原:", [((r[2] - r[0]), (r[3] - r[1])) for (_, _, r) in w])
