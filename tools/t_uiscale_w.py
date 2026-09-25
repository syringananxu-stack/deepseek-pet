# -*- coding: utf-8 -*-
"""单档自测:python t_uiscale_w.py <0|1|2>  → 打印 宽度/高度/字号/sc"""
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
print("lv=%d 宽=%d 高=%d 客户区=%s 字号12.5=%s 字号10=%s 字号17=%s sc=%.2f 选择器=%s" % (
    lv, w._ww(), w.root.winfo_height(), (w.root.winfo_width(), w.root.winfo_height()),
    SU._font(12.5).cget("size"), SU._font(10).cget("size"), SU._font(17).cget("size"),
    w.sc, w.seg_ui.var.get()))
sys.stdout.flush()
os._exit(0)
