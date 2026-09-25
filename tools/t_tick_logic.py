# -*- coding: utf-8 -*-
"""逻辑断言:info 气泡(带倒计时)在 10 秒里应该被重画 ≈10 次(每秒一次)"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from dspet.pet import INFO_SECONDS, Pet          # noqa: E402

p = Pet.__new__(Pet)
p._tickn = 0
p._last_sec = 0
p._spring_active = lambda: False
p._egg_until = 0.0
p._egg_settle = False
p._egg_line_t = 0.0
p._egg_turn_t = 0.0
p.dragging = False
p.wander = False
p.calm_mode = True
p.still_until = time.time() + 9999
p._moving = False
p.chat_until = time.time() + 9999
p.chat = "…"
p.override_txt = ""
p.override_until = 0.0
p.info_until = time.time() + INFO_SECONDS
p._set_tick = lambda ms: None
n = [0]
p._redraw = lambda: n.__setitem__(0, n[0] + 1)

t0 = time.time()
while time.time() - t0 < INFO_SECONDS + 0.6:
    p._on_tick()
    time.sleep(0.02)
el = time.time() - t0
print("INFO_SECONDS =", INFO_SECONDS, " 观察时长 %.1fs" % el, " 重画次数 =", n[0])
print("按旧逻辑(_tickn%20, 怠速 500ms)只会有:", int(el / 10), "次")
print("RESULT:", "PASS" if n[0] >= INFO_SECONDS - 1 else "FAIL")
