# -*- coding: utf-8 -*-
"""界面大小三档自测:量窗口尺寸/字号/紧凑滚动,并出对比图"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import win32gui                                                       # noqa: E402
from PIL import Image, ImageDraw, ImageGrab                           # noqa: E402

from dspet import config                                              # noqa: E402
from dspet.paths import config_path                                   # noqa: E402
from dspet.settings_ui import UI_SCALES, SettingsWindow               # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
path = config_path()
shutil.copyfile(path, path + ".bak6")
shots = {}
try:
    base = config.load()
    for lv in range(3):
        cfg = dict(base)
        cfg["ui_scale"] = lv
        w = SettingsWindow(cfg)
        w._x = 40
        w.root.geometry("+40+%d" % w._y)
        w.root.attributes("-alpha", 1.0)
        t = time.time()
        while time.time() - t < 0.9:
            w.root.update()
            time.sleep(0.02)
        hwnd = w.root.winfo_id()
        top = win32gui.GetParent(hwnd) or hwnd
        r = win32gui.GetWindowRect(top)
        print("lv%d scale=%.2f compact=%s win=%dx%d font=%d" % (
            lv, UI_SCALES[lv], w.compact, r[2] - r[0], r[3] - r[1],
            w.lbl_level.cget("font").cget("size")))
        im = ImageGrab.grab(bbox=(r[0] - 4, r[1] - 4, r[2] + 4, r[3] + 4)).convert("RGB")
        shots[lv] = im.crop((0, 0, im.width, min(im.height, 430)))
        w.root.destroy()
        time.sleep(0.4)
finally:
    shutil.copyfile(path + ".bak6", path)
    os.remove(path + ".bak6")

n = len(shots)
wid = sum(im.width for im in shots.values()) + 12 * (n + 1)
hei = max(im.height for im in shots.values()) + 34
sheet = Image.new("RGB", (wid, hei), "#F1F1F3")
d = ImageDraw.Draw(sheet)
x = 12
for lv in sorted(shots):
    sheet.paste(shots[lv], (x, 26))
    d.text((x, 8), "UI %s (%.2fx)" % (["小", "中", "大"][lv], UI_SCALES[lv]), fill="#333")
    x += shots[lv].width + 12
sheet.save(os.path.join(WS, "_ui_scales.png"))
print("sheet", sheet.size, "saved")
