# -*- coding: utf-8 -*-
"""单档自测:python t_uiscale_w.py <0|1|2> → 宽/高/字号/是否滚动 + 滚动区信息"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dspet import config                                              # noqa: E402
from dspet import settings_ui as SU                                   # noqa: E402

lv = int(sys.argv[1]) if len(sys.argv) > 1 else 1
cfg = config.load()
cfg["ui_scale"] = lv
w = SU.SettingsWindow(cfg, None)
w.root.update()
time.sleep(0.4)
info = ""
if getattr(w, "compact", False):
    try:
        sr = w._scroll._parent_canvas.cget("scrollregion")
        ch = w._scroll._parent_canvas.winfo_height()
        info = " 滚动区=%s 可视高=%d" % (sr, ch)
    except Exception as e:
        info = " 滚动区读取失败:%s" % e
print("lv=%d 宽=%d 高=%d(客户区 %s) 字号12.5=%s 字号17=%s compact=%s 滚动条=%s%s" % (
    lv, w._ww(), w.h, (w.root.winfo_width(), w.root.winfo_height()),
    SU._font(12.5).cget("size"), SU._font(17).cget("size"), w.compact, w.compact, info))
sys.stdout.flush()
os._exit(0)
