# -*- coding: utf-8 -*-
"""换挡(重建)自测:调 _on_ui_scale 看窗口宽度是否变、未保存改动是否保留、有没有异常"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dspet import config                                              # noqa: E402
from dspet import settings_ui as SU                                   # noqa: E402

cfg = config.load()
cfg["ui_scale"] = 0
w = SU.SettingsWindow(cfg, None)
w.root.update()
time.sleep(0.4)
w0 = w._ww()
w.var_snd.set(False)          # 未保存的改动
w.var_chat.set(False)
print("换挡前 宽=%d 音效=%s" % (w0, w.var_snd.get()))

w._on_ui_scale("大")
for _ in range(30):
    w.root.update()
    time.sleep(0.05)
print("换挡后 宽=%d(应 700) 档位=%s 选择器=%s 音效=%s(应 False) 碎嘴=%s" % (
    w._ww(), w.ui_level, w.seg_ui.var.get(), w.var_snd.get(), w.var_chat.get()))
w._on_ui_scale("中")
for _ in range(30):
    w.root.update()
    time.sleep(0.05)
print("再换回 宽=%d(应 580) 音效=%s" % (w._ww(), w.var_snd.get()))
ok = (w0 == 470 and w._ww() == 580 and w.var_snd.get() is False)
print("RESULT:", "PASS" if ok else "FAIL")
sys.stdout.flush()
os._exit(0)
