# -*- coding: utf-8 -*-
"""界面大小「即改即生效」自测:切到 大 → 应该自动重开一个更大的窗口;未保存的改动不许丢"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import win32con                                                       # noqa: E402
import win32gui                                                       # noqa: E402

from dspet import config                                              # noqa: E402
from dspet.paths import config_path                                   # noqa: E402
from dspet.settings_ui import SettingsWindow                          # noqa: E402

path = config_path()
shutil.copyfile(path, path + ".bak7")
try:
    cfg = config.load()
    cfg["ui_scale"] = 1
    w = SettingsWindow(cfg)
    w.root.update()
    w.var_snd.set(False)               # 一个"未保存"的改动,换挡后必须还在
    w.var_chat.set(False)
    print("切换前 window:", w.root.winfo_width(), "ui_level", w.ui_level)
    w._on_ui_scale("大")               # 触发即改即生效
    t = time.time()
    while time.time() - t < 5.0:
        try:
            w.root.update()
        except Exception:
            pass
        time.sleep(0.05)

    found = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h).startswith("设置"):
            r = win32gui.GetWindowRect(h)
            found.append((h, r[2] - r[0], r[3] - r[1]))

    win32gui.EnumWindows(cb, None)
    print("切换后窗口:", found)
    ok = any(x[1] > 660 for x in found)          # 大档 ≈ 700 宽
    print("未保存改动还在吗: sounds=%s chat=%s (都应为 False)" % (
        w.var_snd.get(), w.var_chat.get()))
    ok = ok and (w.var_snd.get() is False) and (w.var_chat.get() is False)
    print("换了档位后 ui_level =", w.ui_level, "窗口宽 =", w.root.winfo_width())
    print("RESULT:", "PASS" if ok else "FAIL")
    for (h, _, _) in found:
        win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
finally:
    shutil.copyfile(path + ".bak7", path)
    os.remove(path + ".bak7")
    print("config restored: ui_scale =", config.load().get("ui_scale"))
