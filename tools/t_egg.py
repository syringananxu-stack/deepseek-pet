# -*- coding: utf-8 -*-
"""🥚 彩蛋自测:token 名字识别 + 兴奋乱窜/颤抖/平息"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

import tempfile                                                       # noqa: E402

from dspet.pet import EGG_DONE, Pet                                   # noqa: E402


def say(*a):
    sys.stdout.write(" ".join(str(x) for x in a).encode("gbk", "replace").decode("gbk") + "\n")


# ---------- 1. 名字识别 ----------
tmp = tempfile.mkdtemp(prefix="egg_")
os.makedirs(os.path.join(tmp, "plain"), exist_ok=True)
os.makedirs(os.path.join(tmp, "has_token_dir"), exist_ok=True)
os.makedirs(os.path.join(tmp, "outer", "inner"), exist_ok=True)
os.makedirs(os.path.join(tmp, "big"), exist_ok=True)
open(os.path.join(tmp, "token_file.txt"), "w").write("x")
open(os.path.join(tmp, "notes.txt"), "w").write("x")
open(os.path.join(tmp, "has_token_dir", "TokenTOKEN.md"), "w").write("x")
open(os.path.join(tmp, "outer", "inner", "my_tOkEn_2.bin"), "w").write("x")
open(os.path.join(tmp, "plain", "a.txt"), "w").write("x")
for i in range(40):
    open(os.path.join(tmp, "big", "f%02d.txt" % i), "w").write("x")

cases = [
    ("普通文件", [os.path.join(tmp, "notes.txt")], False),
    ("文件名带 token", [os.path.join(tmp, "token_file.txt")], True),
    ("TokenTOKEN 文件", [os.path.join(tmp, "has_token_dir", "TokenTOKEN.md")], True),
    ("普通文件夹", [os.path.join(tmp, "plain")], False),
    ("文件夹名带 token", [os.path.join(tmp, "has_token_dir")], True),
    ("子目录深处的 token", [os.path.join(tmp, "outer")], True),
    ("大文件夹(无 token)", [os.path.join(tmp, "big")], False),
    ("多个一起", [os.path.join(tmp, "plain"), os.path.join(tmp, "outer")], True),
]
bad = 0
for label, paths, want in cases:
    got = Pet._find_token(None, paths)
    ok = (got == want)
    bad += 0 if ok else 1
    say(("[ok] " if ok else "[FAIL] ") + label, "->", got)
say("识别用例:", "全过" if bad == 0 else "%d 个没过" % bad)

# ---------- 2. 兴奋行为 ----------
p = Pet()
p._egg_until = time.time() + 3.0        # 缩短,便于测
p._go_egg()
p._egg_until = time.time() + 3.0        # _go_egg 会重设,再压一次
say("兴奋开始:", "still_until=0" if p.still_until == 0 else "still_until!=0",
    "| 台词:", p.override_txt.encode("gbk", "replace").decode("gbk"))

pos, spd_max, tremble_max = [], 0.0, 0.0
t0 = time.time()
while time.time() - t0 < 3.6:
    p._on_tick()
    x, y = p.x, p.y
    pos.append((time.time(), x, y))
    tremble_max = max(tremble_max, abs(x - p.fx), abs(y - p.fy))
    time.sleep(0.02)

for i in range(1, len(pos) - 1):
    dt = pos[i + 1][0] - pos[i][0]
    if dt <= 0:
        continue
    v = (((pos[i + 1][1] - pos[i][1]) ** 2 + (pos[i + 1][2] - pos[i][2]) ** 2) ** 0.5) / dt
    spd_max = max(spd_max, v)
say("最高速度: %.0f px/s (>200 算飞起来)" % spd_max)
say("颤抖幅度: %.1f px (>0 即在抖)" % tremble_max)

for _ in range(40):                     # 再跑一会儿让它自然平息
    p._on_tick()
    time.sleep(0.02)
# 强迫"歇着",再看颤抖位移有没有彻底收回(有 jitter 的话偏移会一直跳)
p.still_until = time.time() + 10.0
p._moving = False
offs = []
for _ in range(12):
    p._on_tick()
    offs.append((p.x - p.fx, p.y - p.fy))
    time.sleep(0.02)
settled = all(abs(o[0]) <= 1.5 and abs(o[1]) <= 1.5 for o in offs)   # 只允许取整误差
calm = p.still_until > time.time() - 0.1
say("平息: 位移收回=%s 进入安静=%s 台词=%s" % (
    settled, calm, p.override_txt.encode("gbk", "replace").decode("gbk")))
say("台词是收尾语:", p.override_txt == EGG_DONE)

ok = (bad == 0 and spd_max > 200 and tremble_max > 0 and settled and calm)
say("RESULT:", "PASS" if ok else "FAIL")
try:
    import win32gui
    win32gui.DestroyWindow(p.hwnd)
except Exception:
    pass
