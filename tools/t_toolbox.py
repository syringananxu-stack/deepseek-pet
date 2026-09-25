# -*- coding: utf-8 -*-
"""设置界面「工具箱 → 内存优化」自测(禁提权,只看按钮→结果文字这条链跑通)"""
import os
import sys
import time

os.environ["DSPET_MEMOPT_NOELEVATE"] = "1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from dspet import config                                    # noqa: E402
from dspet.settings_ui import SettingsWindow                # noqa: E402

cfg = config.load()
LOG = []
w = SettingsWindow(cfg)
w.root.update()


def say(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s)


say("工具箱卡片存在:", hasattr(w, "btn_mem"), "按钮:",
    w.btn_mem.itemcget(w.btn_mem._tid, "text").encode("gbk", "replace").decode("gbk"))
say("初始提示:", w.lbl_mem.cget("text")[:40].encode("gbk", "replace").decode("gbk"))
w._mem_optimize()
t = time.time()
while time.time() - t < 25:
    w.root.update()
    time.sleep(0.05)
    if not w._mem_busy:
        break
txt = w.lbl_mem.cget("text")
say("结果:", txt.encode("gbk", "replace").decode("gbk"))
say("按钮复原:", w.btn_mem.itemcget(w.btn_mem._tid, "text").encode("gbk", "replace").decode("gbk"))
say("RESULT:", "PASS" if (not w._mem_busy) and ("可用" in txt) else "FAIL")
try:
    import io
    io.open(r"D:\Temp\dspet_toolbox.txt", "w", encoding="utf-8").write("\n".join(LOG))
    sys.stdout.flush()
except Exception:
    pass
os._exit(0)
