# -*- coding: utf-8 -*-
"""装机版端到端:config 里 ui_scale=2 → 打开设置窗应该是「大」(≈700 宽);再看一眼界面大小那一行"""
import ctypes
import io
import json
import os
import shutil
import sys
import time

import win32con
import win32gui
from PIL import ImageGrab

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
CFG = r"D:\Apps\DeepSeekPet\config.json"
BAK = r"D:\Temp\dspet_cfg_ui.bak"
u = ctypes.windll.user32


def find_settings():
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and t.startswith("设置"):
            out.append((h, t, win32gui.GetWindowRect(h)))

    win32gui.EnumWindows(cb, None)
    return out


def close_settings():
    for (h, _, _) in find_settings():
        win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
    time.sleep(1.2)


def open_settings():
    pet = win32gui.FindWindow("DSPetWnd", None)
    u.PostMessageW(ctypes.c_void_p(pet), win32con.WM_APP + 2, ctypes.c_void_p(0), ctypes.c_void_p(0))
    t = time.time()
    while time.time() - t < 8:
        s = find_settings()
        if s:
            time.sleep(1.0)
            return s
        time.sleep(0.3)
    return []


shutil.copyfile(CFG, BAK)
try:
    close_settings()
    # 1) 大档
    cfg = json.load(io.open(CFG, encoding="utf-8-sig"))
    cfg["ui_scale"] = 2
    io.open(CFG, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=1))
    s = open_settings()
    print("ui_scale=2 →", [(t, r[2] - r[0], r[3] - r[1]) for (_, t, r) in s])
    if s:
        r = s[0][2]
        ImageGrab.grab(bbox=(r[0] - 4, r[1] - 4, r[2] + 4, r[3] + 4)).save(
            os.path.join(WS, "_ui_installed_big.png"))
    big_ok = bool(s) and (s[0][2][2] - s[0][2][0]) > 660

    # 2) 小档
    close_settings()
    cfg["ui_scale"] = 0
    io.open(CFG, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=1))
    s2 = open_settings()
    print("ui_scale=0 →", [(t, r[2] - r[0], r[3] - r[1]) for (_, t, r) in s2])
    if s2:
        r = s2[0][2]
        ImageGrab.grab(bbox=(r[0] - 4, r[1] - 4, r[2] + 4, r[3] + 4)).save(
            os.path.join(WS, "_ui_installed_small.png"))
    small_ok = bool(s2) and (s2[0][2][2] - s2[0][2][0]) < 540
    print("RESULT:", "PASS" if (big_ok and small_ok) else "FAIL")
finally:
    # 还原成 中,并把窗口开回来给东家看
    close_settings()
    shutil.copyfile(BAK, CFG)
    os.remove(BAK)
    s3 = open_settings()
    print("已还原 ui_scale=%s,窗口:" % json.load(io.open(CFG, encoding="utf-8-sig")).get("ui_scale"),
          [(t, r[2] - r[0], r[3] - r[1]) for (_, t, r) in s3])
