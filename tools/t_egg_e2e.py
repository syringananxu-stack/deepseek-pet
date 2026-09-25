# -*- coding: utf-8 -*-
"""端到端:给装好的桌宠喂一个名字带 token 的文件 → 抓 GIF 看它是不是乱窜+颤抖"""
import ctypes
import os
import sys
import time

import win32con
import win32gui
from PIL import Image, ImageGrab

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
FEED = os.path.join(WS, "_egg_token_test.txt")
WM_DROPFILES = 0x0233

u = ctypes.windll.user32
k = ctypes.windll.kernel32

sys.stdout.write("pet hwnd find...\n")
hwnd = win32gui.FindWindow("DSPetWnd", None)
sys.stdout.write("hwnd=%s\n" % hwnd)
if not hwnd:
    sys.exit(1)

r0 = win32gui.GetWindowRect(hwnd)


def drop(path, hwnd):
    data = path.encode("utf-16-le") + b"\x00\x00"
    header = ctypes.create_string_buffer(20)
    ctypes.memset(header, 0, 20)
    ctypes.cast(header, ctypes.POINTER(ctypes.c_uint32))[0] = 20      # pFiles
    ctypes.cast(header, ctypes.POINTER(ctypes.c_uint32))[4] = 1       # fWide
    blk = header.raw + data
    k.GlobalAlloc.restype = ctypes.c_void_p
    k.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    hmem = k.GlobalAlloc(0x0042, len(blk))                            # GMEM_MOVEABLE|ZEROINIT
    p = k.GlobalLock(hmem)
    ctypes.memmove(p, blk, len(blk))
    k.GlobalUnlock(hmem)
    u.PostMessageW(hwnd, WM_DROPFILES, hmem, 0)


with open(FEED, "w", encoding="utf-8") as f:
    f.write("token token token")
sys.stdout.write("feed: %s\n" % FEED)
drop(FEED, hwnd)

dlg = 0
t = time.time()
while time.time() - t < 6 and not dlg:
    time.sleep(0.15)
    dlg = win32gui.FindWindow("#32770", "喂给大肥鱼")
sys.stdout.write("dialog=%s\n" % dlg)
if dlg:
    btns = []
    def _cb(b, _):
        btns.append((b, win32gui.GetClassName(b), win32gui.GetWindowText(b),
                     win32gui.GetDlgCtrlID(b)))
    win32gui.EnumChildWindows(dlg, _cb, None)
    sys.stdout.write("buttons=%s\n" % (btns,))
    # 点“是/Yes”:直接给按钮发 BM_CLICK 最稳
    target = None
    for (b, cls, txt, cid) in btns:
        if cid == 6 or ("是" in txt) or ("Yes" in txt):
            target = b
    if target is None and btns:
        target = btns[0][0]
    if target:
        win32gui.PostMessage(target, 0x00F5, 0, 0)          # BM_CLICK
        sys.stdout.write("BM_CLICK on %s\n" % target)
    gone = False
    t1 = time.time()
    while time.time() - t1 < 3.0:
        if not os.path.exists(FEED):
            gone = True
            break
        time.sleep(0.1)
    sys.stdout.write("file recycled=%s\n" % gone)
    if not gone and win32gui.IsWindow(dlg):
        win32gui.PostMessage(dlg, win32con.WM_COMMAND, 6, 0)
        sys.stdout.write("fallback WM_COMMAND sent\n")
        time.sleep(0.6)

# 采样 + 录 GIF
class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


_r = _RECT()
u.SystemParametersInfoW(0x0030, 0, ctypes.byref(_r), 0)     # SPI_GETWORKAREA
wa = (_r.left, _r.top, _r.right, _r.bottom)
sys.stdout.write("workarea=%s\n" % (wa,))

frames, offs = [], []
t0 = time.time()
rect = None
MOVIE = os.environ.get("NOMOVIE") != "1"
while time.time() - t0 < 4.2:
    if rect is None:
        rect = wa
    x, y = win32gui.GetWindowRect(hwnd)[:2]
    offs.append((time.time(), x, y))
    if MOVIE:
        im = ImageGrab.grab(bbox=rect).convert("RGB")
        im = im.resize((int(im.width * 0.30), int(im.height * 0.30)), Image.LANCZOS)
        frames.append(im.convert("P", palette=Image.ADAPTIVE, colors=128))
    time.sleep(0.03 if not MOVIE else 0.20)
    time.sleep(0.10)
sys.stdout.write("frames=%d\n" % len(frames))

spd = 0.0
for i in range(1, len(offs) - 1):
    dt = offs[i + 1][0] - offs[i][0]
    if dt > 0:
        v = (((offs[i + 1][1] - offs[i][1]) ** 2 + (offs[i + 1][2] - offs[i][2]) ** 2) ** 0.5) / dt
        spd = max(spd, v)
xs = [o[1] for o in offs]
ys = [o[2] for o in offs]
sys.stdout.write("max_speed=%.0f px/s  x range=%d..%d  y range=%d..%d\n"
                 % (spd, min(xs), max(xs), min(ys), max(ys)))

frames[0].save(os.path.join(WS, "_egg.gif"), save_all=True, append_images=frames[1:],
               duration=140, loop=0, optimize=True) if frames else sys.stdout.write("no frames\n")
sys.stdout.write("gif saved %.1f KB\n" % (os.path.getsize(os.path.join(WS, "_egg.gif")) / 1024.0))
sys.stdout.write("fed file still there? %s\n" % os.path.exists(FEED))
sys.stdout.write("EGG E2E: %s\n" % ("PASS" if spd > 120 else "FAIL"))
