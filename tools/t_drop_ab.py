# -*- coding: utf-8 -*-
"""A/B:先验证我拼的 WM_DROPFILES 消息本身能不能被普通窗口收到"""
import ctypes
import os
import sys
import time

import win32api
import win32con
import win32gui

WS = r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace"
OUT = os.path.join(WS, "_ab_drop.txt")
FEED = os.path.join(WS, "_egg_token_test.txt")
WM_DROPFILES = 0x0233

u = ctypes.windll.user32
k = ctypes.windll.kernel32


def drop(path, hwnd):
    data = path.encode("utf-16-le") + b"\x00\x00"
    hdr = ctypes.create_string_buffer(20)
    ctypes.memset(hdr, 0, 20)
    ctypes.cast(hdr, ctypes.POINTER(ctypes.c_uint32))[0] = 20
    ctypes.cast(hdr, ctypes.POINTER(ctypes.c_uint32))[4] = 1
    blk = hdr.raw + data
    k.GlobalAlloc.restype = ctypes.c_void_p
    k.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    u.PostMessageW.restype = ctypes.c_int
    hmem = k.GlobalAlloc(0x0042, len(blk))
    p = k.GlobalLock(hmem)
    ctypes.memmove(p, blk, len(blk))
    k.GlobalUnlock(ctypes.c_void_p(hmem))
    ok = u.PostMessageW(hwnd, WM_DROPFILES, hmem, 0)
    return hmem, ok


with open(OUT, "w", encoding="utf-8") as f:
    f.write("start\n")
with open(FEED, "w", encoding="utf-8") as f:
    f.write("token")


def log(s):
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


msgs = []


def proc(hwnd, msg, wparam, lparam):
    if msg == WM_DROPFILES:
        log("WM_DROPFILES wparam=%r" % (wparam,))
        n = ctypes.windll.shell32.DragQueryFileW(ctypes.c_void_p(wparam), 0xFFFFFFFF, None, 0)
        log("count=%s" % n)
        buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.shell32.DragQueryFileW(ctypes.c_void_p(wparam), 0, buf, 1024)
        log("path=%s" % buf.value)
        return 0
    if msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


wc = win32gui.WNDCLASS()
wc.lpszClassName = "DropABTest"
wc.lpfnWndProc = proc
try:
    win32gui.RegisterClass(wc)
except Exception as e:
    log("register: %s" % e)
hwnd = win32gui.CreateWindow("DropABTest", "ab", win32con.WS_OVERLAPPED,
                             0, 0, 100, 100, 0, 0, 0, None)
win32gui.DragAcceptFiles(hwnd, True)
hmem, ok = drop(FEED, hwnd)
log("posted hmem=%r ok=%s err=%s" % (hmem, ok, ctypes.get_last_error()))

t = time.time()
while time.time() - t < 2:
    win32gui.PumpWaitingMessages()
    time.sleep(0.05)
log("done")
sys.stdout.write("ab done, see %s\n" % OUT)
sys.stdout.flush()
