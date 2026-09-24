# -*- coding: utf-8 -*-
"""验证:①桌宠窗口是否置顶 ②全屏窗口出现时桌宠是否自动让位 ③全屏消失后是否自动回来"""
import ctypes
import time
import win32con
import win32gui

user32 = ctypes.windll.user32
PET_CLS = "DSPetWnd"


def pet_state():
    h = win32gui.FindWindow(PET_CLS, None)
    if not h:
        return None
    ex = win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE)
    return {"hwnd": h,
            "topmost": bool(ex & win32con.WS_EX_TOPMOST),
            "visible": bool(win32gui.IsWindowVisible(h)),
            "rect": win32gui.GetWindowRect(h)}


def pump(sec):
    t = time.time()
    while time.time() - t < sec:
        win32gui.PumpWaitingMessages()
        time.sleep(0.02)


def force_fg(h, sw, sh):
    user32.keybd_event(0x12, 0, 0, 0)
    try:
        win32gui.SetForegroundWindow(h)
    except Exception:
        pass
    user32.keybd_event(0x12, 0, 2, 0)
    if user32.GetForegroundWindow() != h:
        user32.SetCursorPos(sw // 2, sh // 2)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
    return user32.GetForegroundWindow() == h


st = pet_state()
print("PET NOW      :", st)
assert st and st["visible"], "桌宠没在跑?"

sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
hInst = win32gui.GetModuleHandle(None)
wc = win32gui.WNDCLASS()
wc.hInstance = hInst
wc.lpszClassName = "FSTESTWnd"
wc.lpfnWndProc = win32gui.DefWindowProc
try:
    win32gui.RegisterClass(wc)
except Exception:
    pass
h = win32gui.CreateWindowEx(win32con.WS_EX_TOPMOST, "FSTESTWnd", "FSTEST",
                            win32con.WS_POPUP, 0, 0, sw, sh, 0, 0, hInst, None)
win32gui.ShowWindow(h, win32con.SW_SHOW)
win32gui.SetWindowPos(h, win32con.HWND_TOPMOST, 0, 0, sw, sh,
                      win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE)
pump(0.4)
fg_ok = force_fg(h, sw, sh)
print("fullscreen shown %dx%d, is_foreground=%s, waiting 3.5s ..." % (sw, sh, fg_ok))
pump(3.5)
st2 = pet_state()
print("PET WHILE FS :", st2)

win32gui.DestroyWindow(h)
print("fullscreen closed, waiting 3.5s ...")
pump(3.5)
st3 = pet_state()
print("PET AFTER FS :", st3)

print("RESULT: topmost=%s  hidden_during_fs=%s  back_after=%s"
      % (st["topmost"], bool(st2 and not st2["visible"]), bool(st3 and st3["visible"])))
