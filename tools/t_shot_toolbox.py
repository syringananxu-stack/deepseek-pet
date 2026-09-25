# -*- coding: utf-8 -*-
"""截设置界面(含新「工具箱」卡片):python t_shot_toolbox.py [小|中|大]"""
import os
import sys
import time

os.environ["DSPET_MEMOPT_NOELEVATE"] = "1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from PIL import ImageGrab                              # noqa: E402

from dspet import config                               # noqa: E402
from dspet import settings_ui as SU                    # noqa: E402

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
lv = {"小": 0, "中": 1, "大": 2}.get(sys.argv[1] if len(sys.argv) > 1 else "中", 1)
cfg = config.load()
cfg["ui_scale"] = lv
w = SU.SettingsWindow(cfg, None)
try:
    w.show()
except Exception as e:
    print("show 失败:", e)
t = time.time()
while time.time() - t < 2.5:
    w.root.update()
    time.sleep(0.04)
im = ImageGrab.grab()
x, y = w.root.winfo_rootx(), w.root.winfo_rooty()
im.crop((x - 10, y - 34, x + w.root.winfo_width() + 10, y + w.root.winfo_height() + 10)).save(
    os.path.join(WS, "_toolbox_ui.png"))
print("saved lv=%s rect=(%d,%d,%d,%d)" % (lv, x, y, w.root.winfo_width(), w.root.winfo_height()))
sys.stdout.flush()
os._exit(0)
