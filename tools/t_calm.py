# -*- coding: utf-8 -*-
"""自查:①启动后先静止 ②冷落够了才溜达 ③点击后静止 ④拖拽后静止更久
用法:先用 DSPET_FAST_STILL=6 启动桌宠,再跑本脚本(6 秒真空期便于观测)
"""
import ctypes
import sys
import time

import win32con
import win32gui

u = ctypes.windll.user32
h = win32gui.FindWindow("DSPetWnd", None)
if not h:
    print("桌宠没在跑")
    sys.exit(1)


def post(m, l=0):
    u.PostMessageW(h, m, 0, l)


def rect():
    return win32gui.GetWindowRect(h)


def sample(sec, tag, expect_still):
    t0 = time.time()
    last = rect()
    moves = 0
    while time.time() - t0 < sec:
        time.sleep(0.2)
        r = rect()
        if r != last:
            moves += 1
            last = r
    ok = (moves == 0) if expect_still else (moves > 0)
    print("[%s] %-22s %4.1fs -> 移动 %2d 次 : %s"
          % ("OK " if ok else "FAIL", tag, sec, moves,
             "静止" if moves == 0 else "在动"))
    return ok


results = []
print("== 刚启动(真空期内应静止)==")
results.append(sample(4, "start", True))

print("== 冷落 8s 后应开始溜达 ==")
time.sleep(8)
results.append(sample(6, "idle->wander", False))

print("== 点一下 → 应立刻老实 6s ==")
r = rect()
u.SetCursorPos((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)
post(win32con.WM_LBUTTONDOWN)
time.sleep(0.12)
post(win32con.WM_LBUTTONUP)
time.sleep(0.5)
results.append(sample(4, "after-click", True))

time.sleep(8)
print("== 再冷落 8s → 应继续溜达 ==")
results.append(sample(4, "click->resume", False))

print("== 拖一下 → 应老实更久 ==")
r = rect()
u.SetCursorPos((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)
post(win32con.WM_LBUTTONDOWN)
time.sleep(0.15)
u.SetCursorPos((r[0] + r[2]) // 2 + 150, (r[1] + r[3]) // 2 - 40)
post(win32con.WM_MOUSEMOVE)
time.sleep(0.15)
u.SetCursorPos((r[0] + r[2]) // 2 + 210, (r[1] + r[3]) // 2 - 70)
post(win32con.WM_MOUSEMOVE)
time.sleep(0.15)
post(win32con.WM_LBUTTONUP)
time.sleep(0.5)
results.append(sample(5, "after-drag", True))

print("结果:", "%d/%d 通过" % (sum(results), len(results)))
