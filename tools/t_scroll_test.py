# -*- coding: utf-8 -*-
"""小档滚动验证:滚到底看内容是否真的动、底栏是否钉住"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from PIL import ImageGrab                                              # noqa: E402

from dspet import config                                               # noqa: E402
from dspet import settings_ui as SU                                    # noqa: E402

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
cfg = config.load()
cfg["ui_scale"] = 0
w = SU.SettingsWindow(cfg, None)
for _ in range(10):
    w.root.update()
    time.sleep(0.12)
cv = w._scroll._parent_canvas
print("compact=", w.compact, "yview=", cv.yview(), "scrollregion=", cv.cget("scrollregion"))
try:
    print("滚动条可见=", w._scroll._scrollbar.winfo_ismapped())
except Exception as e:
    print("滚动条查询失败", e)
ImageGrab.grab().save(os.path.join(WS, "_scroll_top.png"))
cv.yview_moveto(1.0)
for _ in range(6):
    w.root.update()
    time.sleep(0.1)
print("滚到底 yview=", cv.yview())
ImageGrab.grab().save(os.path.join(WS, "_scroll_bot.png"))
sys.stdout.flush()
os._exit(0)
