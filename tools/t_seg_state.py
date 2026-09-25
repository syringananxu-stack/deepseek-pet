# -*- coding: utf-8 -*-
"""验证:分档打开时「界面大小」选择器是否高亮正确的档 + 「喂文件」是否跟着配置"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dspet import config                                              # noqa: E402
from dspet import settings_ui as SU                                   # noqa: E402

bad = []
for lv in (0, 1, 2):
    cfg = config.load()
    cfg["ui_scale"] = lv
    cfg["hard_delete"] = (lv == 2)          # 顺便验"彻底删除"档显示对不对
    w = SU.SettingsWindow(cfg, None)
    w.root.update()
    time.sleep(0.3)
    got_ui = w.var_uiscale.get()
    got_feed = w.var_feed.get()
    seg_ui = w.seg_ui.var.get()
    seg_feed = w.seg.var.get()
    print("lv=%d  当前窗口宽=%d  界面大小显示=%s  seg内部=%s   喂文件显示=%s/%s" % (
        lv, w._ww(), got_ui, seg_ui, got_feed, seg_feed))
    if got_ui != SU.UI_SCALE_TEXT[lv] or seg_ui != SU.UI_SCALE_TEXT[lv]:
        bad.append("ui_scale lv=%d" % lv)
    want_feed = "彻底删除" if lv == 2 else "回收站"
    if got_feed != want_feed or seg_feed != want_feed:
        bad.append("feed lv=%d" % lv)
    try:
        w.root.destroy()
    except Exception:
        pass
print("RESULT:", "PASS" if not bad else ("FAIL " + ",".join(bad)))
sys.stdout.flush()
os._exit(0)
