# -*- coding: utf-8 -*-
"""源码版单档整屏截图(看真实观感):python t_shot_full.py <0|1|2>"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from PIL import ImageGrab                                              # noqa: E402

from dspet import config                                               # noqa: E402
from dspet import settings_ui as SU                                    # noqa: E402

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
lv = int(sys.argv[1]) if len(sys.argv) > 1 else 1
cfg = config.load()
cfg["ui_scale"] = lv
w = SU.SettingsWindow(cfg, None)
for _ in range(10):
    w.root.update()
    time.sleep(0.15)
im = ImageGrab.grab()
im.crop((900, 200, 1700, 1400)).save(os.path.join(WS, "_full_lv%d.png" % lv))
print("lv=%d h=%d compact=%s saved" % (lv, w.h, w.compact))
sys.stdout.flush()
os._exit(0)
